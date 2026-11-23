"""Reusable wrapper for a single-AOI TCVIS trend run, delivered to a local file.

The trend maths is *not* reimplemented: this drives
``modules.high_level_functions_CO2.runTCTrend`` -- the production path behind the
published ``TCTrend_SR_*_TCVIS`` assets -- and then replaces the asset export
with a local delivery (xarray via xee -> COG / Zarr).

Basic use::

    from modules.regional_trend import RegionalTrend

    run = RegionalTrend(
        lon=(-154.0, -153.5), lat=(70.7, 70.9),
        years=(2007, 2026), project="pdg-wg-workflow",
    )
    run.to_cog("out/TCTrend_2007-2026.tif")     # 3 x uint8, EPSG:3413, 30 m
    run.to_zarr("out/TCTrend_2007-2026.zarr")   # same grid, xarray-native
    run.quicklook("out/TCTrend_2007-2026.png")

Two products are available through the ``kind`` argument:

``visual`` (default) — what ``Production_2005-2024.ipynb`` exports with
``toByte()``: 3 bands (TCB/TCG/TCW slope), uint8, ``unitScale(-0.12, 0.12)*255``.
Masked pixels live in an internal mask band, not a nodata sentinel, because all
of 0..255 are legitimate values of that scale.

``slopes`` — the raw float trend (``runTCTrend``'s ``data``), i.e. TC slope x 10,
stored as float32 with NaN for masked pixels. Use it when you need the numbers
rather than the picture; ``slope_scale_factor=10`` is recorded in the metadata.
"""

from __future__ import annotations

import math
import random
import time
from pathlib import Path

import ee
import numpy as np
import xarray as xr
import xee

from modules import high_level_functions_CO2 as hlf

SLOPE_BANDS = ("TCB_slope", "TCG_slope", "TCW_slope")
SLOPE_SCALE_FACTOR = 10  # runTCTrend multiplies by 10; see module docstring

# Keys that define the *product*. Runtime knobs (workers, concurrency) are
# deliberately excluded: raising the worker count must never invalidate tiles.
FINGERPRINT_KEYS = (
    "start_year", "end_year", "start_month", "end_month", "max_cloud",
    "scale", "scale_mode", "crs", "project", "products", "cell_lon", "cell_lat",
    "pin_native_grid", "snap",
)

THROTTLE_MARKERS = ("too many requests", "concurrency", "429", "rate limit")

__all__ = ["RegionalTrend", "SLOPE_BANDS", "SLOPE_SCALE_FACTOR"]


class RegionalTrend:
    """One tasseled-cap trend run for one bounding box.

    Nothing touches Earth Engine until :meth:`trend` (or a delivery method) is
    called, so constructing the object is free and can happen in tests.
    """

    def __init__(
        self,
        lon: tuple[float, float],
        lat: tuple[float, float],
        years: tuple[int, int],
        start_month: int = 7,
        end_month: int = 8,
        max_cloud: int = 70,
        scale: float = 30,
        crs: str = "EPSG:3857",
        project: str | None = None,
        pin_native_grid: bool = True,
        snap: bool = False,
        concurrency: int = 1,
        fetch_retries: int = 4,
    ):
        self.lon = (float(min(lon)), float(max(lon)))
        self.lat = (float(min(lat)), float(max(lat)))
        self.years = (int(min(years)), int(max(years)))
        self.start_month = int(start_month)
        self.end_month = int(end_month)
        self.max_cloud = int(max_cloud)
        self.scale = float(scale)
        self.crs = crs
        self.project = project
        self.pin_native_grid = bool(pin_native_grid)
        self.snap = bool(snap)
        # xee defaults to ThreadPoolExecutor() with min(32, cpu+4) threads, i.e.
        # up to 32 concurrent computePixels per process -- enough to blow Earth
        # Engine's concurrent-interactive-request quota from a handful of workers.
        self.concurrency = max(1, int(concurrency))
        self.fetch_retries = max(1, int(fetch_retries))
        self._trend: dict | None = None
        self._datasets: dict[str, xr.Dataset] = {}
        self._validate()

    # ------------------------------------------------------------------ config
    def _validate(self) -> None:
        lon0, lon1 = self.lon
        lat0, lat1 = self.lat
        if not (-180 <= lon0 < lon1 <= 180):
            raise ValueError(f"longitudes must increase within -180..180, got {self.lon}")
        if not (-90 <= lat0 < lat1 <= 90):
            raise ValueError(f"latitudes must increase within -90..90, got {self.lat}")
        # A hemisphere slip turns a patch into a hemisphere-scale request; refuse
        # anything wider than 10 degrees and say why.
        for name, (a, b) in (("longitude", self.lon), ("latitude", self.lat)):
            if b - a > 10:
                raise ValueError(
                    f"{name} span {b - a:.2f} deg is not a regional sample "
                    "(hemisphere slip?); reduce to <10 deg or override explicitly"
                )
        start, end = self.years
        if start >= end:
            raise ValueError(f"years must increase, got {self.years}")

    @property
    def aoi(self) -> ee.Geometry.Rectangle:
        return ee.Geometry.Rectangle(
            [self.lon[0], self.lat[0], self.lon[1], self.lat[1]], proj="EPSG:4326"
        )

    @property
    def config(self) -> dict:
        """The exact key set ``runTCTrend`` requires."""
        start, end = self.years
        return {
            "STARTYEAR": start,
            "ENDYEAR": end,
            "max_cloud_cover": self.max_cloud,
            "date_filter_yr": ee.Filter.calendarRange(start, end, "year"),
            "date_filter_mth": ee.Filter.calendarRange(self.start_month, self.end_month, "month"),
            "meta_filter_cld": ee.Filter.lt("CLOUD_COVER", self.max_cloud),
            "select_bands_visible": ["SR_B1", "SR_B2", "SR_B3", "SR_B4"],
            "select_indices": ["TCB", "TCG", "TCW"],
            "select_TCtrend_bands": list(SLOPE_BANDS),
            "geom": self.aoi,
            # EE reduces on the 1-degree default projection unless the grid is
            # pinned; for a small AOI that collapses the trend to one value.
            "pin_native_grid": self.pin_native_grid,
            "longitudes": [self.lon[0]],
            "latitudes": [self.lat[0]],
        }

    def describe(self) -> str:
        """Extent and pixel count -- the cheap pre-flight before spending compute."""
        lat0, lat1 = self.lat
        lon0, lon1 = self.lon
        r = 6371.0088
        lat_km = math.radians(lat1 - lat0) * r
        lon_km = math.radians(lon1 - lon0) * r * math.cos(math.radians((lat0 + lat1) / 2))
        rows, cols = lat_km * 1000 / self.scale, lon_km * 1000 / self.scale
        start, end = self.years
        return (
            f"lon {lon0}..{lon1}, lat {lat0}..{lat1} | "
            f"{lat_km:.1f} x {lon_km:.1f} km ({lat_km * lon_km:.0f} km2) | "
            f"~{rows:.0f} x {cols:.0f} px at {self.scale:.0f} m | "
            f"{start}-{end}, months {self.start_month}-{self.end_month}, "
            f"cloud<{self.max_cloud}% | target {self.crs}"
        )

    # --------------------------------------------------------------- EE compute
    def initialize(self) -> None:
        ee.Initialize(project=self.project) if self.project else ee.Initialize()

    def trend(self) -> dict:
        """``runTCTrend`` output, computed once per instance."""
        if self._trend is None:
            self.initialize()
            self._trend = hlf.runTCTrend(self.config)
        return self._trend

    def slopes_image(self) -> ee.Image:
        """The three slope bands, bilinear-resampled for the projection change.

        ``system:time_start``/``time_end`` are set explicitly: without a
        timestamp xee has to fall back to an index coordinate, and the property
        is the honest description of the window anyway.
        """
        start, end = self.years
        return (
            self.trend()["data"]
            .select(list(SLOPE_BANDS))
            .resample("bilinear")
            .set("system:time_start", ee.Date.fromYMD(start, self.start_month, 1).millis())
            .set("system:time_end", ee.Date.fromYMD(end, self.end_month, 1).millis())
        )

    def observations_image(self) -> ee.Image:
        start = self.years[0]
        return self.trend()["n_observations"].set(
            "system:time_start", ee.Date.fromYMD(start, self.start_month, 1).millis()
        )

    def visual_image(self) -> ee.Image:
        """The production product: 3 x uint8, ``unitScale(-0.12, 0.12) * 255``.

        This is what ``Production_2005-2024.ipynb`` exports with ``toByte()``, so
        it is the default delivery here too.
        """
        return self.trend()["visual"].select(list(SLOPE_BANDS))

    # ------------------------------------------------------------------ delivery
    def grid(self) -> dict:
        """Target grid (crs / affine / shape).

        ``snap=True`` puts the grid origin on a global lattice of ``scale`` in
        the target CRS, so tiles written by different runs/processes are
        pixel-aligned and mosaic without resampling. ``snap=False`` keeps the
        original behaviour (xee fits the bbox independently), which is fine for
        a one-off sample but leaves neighbours off by up to one pixel.
        """
        import shapely.geometry

        if not self.snap:
            return dict(
                xee.fit_geometry(
                    shapely.geometry.box(self.lon[0], self.lat[0], self.lon[1], self.lat[1]),
                    geometry_crs="EPSG:4326",
                    grid_crs=self.crs,
                    grid_scale=(self.scale, -self.scale),  # negative y = north-up
                )
            )

        from pyproj import Transformer

        transformer = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        xs, ys = transformer.transform(
            [self.lon[0], self.lon[1], self.lon[0], self.lon[1]],
            [self.lat[0], self.lat[0], self.lat[1], self.lat[1]],
        )
        res = self.scale
        x0 = math.floor(min(xs) / res) * res
        y1 = math.ceil(max(ys) / res) * res
        width = int(math.ceil((max(xs) - x0) / res))
        height = int(math.ceil((y1 - min(ys)) / res))
        return dict(
            crs=self.crs,
            crs_transform=(res, 0.0, x0, 0.0, -res, y1),
            shape_2d=(width, height),
        )

    def _fetch(self, image: ee.Image) -> xr.Dataset:
        """One request stream, retried with backoff when EE throttles us."""
        grid = self.grid()
        last: Exception | None = None
        for attempt in range(self.fetch_retries):
            try:
                return xr.open_dataset(
                    image,
                    engine="ee",
                    crs=grid["crs"],
                    crs_transform=grid["crs_transform"],
                    shape_2d=grid["shape_2d"],
                    ee_init_if_necessary=True,
                    ee_init_kwargs={"project": self.project} if self.project else None,
                    executor_kwargs={"max_workers": self.concurrency},
                ).compute()
            except Exception as exc:                              # noqa: BLE001
                if not any(m in str(exc).lower() for m in THROTTLE_MARKERS):
                    raise
                last = exc
                wait = min(300, 30 * (2 ** attempt)) + random.uniform(0, 5)
                print(f"    EE throttled ({attempt + 1}/{self.fetch_retries}), "
                      f"waiting {wait:.0f}s: {str(exc).splitlines()[0][:120]}", flush=True)
                time.sleep(wait)
        raise last if last else RuntimeError("fetch failed")

    def dataset(self, kind: str = "visual") -> xr.Dataset:
        """Fetch one of ``visual`` / ``slopes`` / ``observations`` into memory.

        ``visual`` is the production product (uint8 0..255 on the GeoTIFF, kept
        here as float with NaN where masked so the mask survives until writing);
        ``slopes`` is the raw float trend (TC slope x 10).
        """
        if kind not in self._datasets:
            if kind == "visual":
                ds = self._fetch(self.visual_image())
            elif kind == "slopes":
                ds = self._fetch(self.slopes_image())
            elif kind == "observations":
                ds = self._fetch(self.observations_image()).fillna(0).astype("uint16")
            else:
                raise ValueError(f"unknown dataset {kind!r}")
            # xee always reports a single-image collection as a `time` dimension
            # of length 1; drop it so the data is plain (y, x).
            if "time" in ds.sizes and ds.sizes["time"] == 1:
                ds = ds.isel(time=0, drop=True)
            start, end = self.years
            ds.attrs.update(
                source="GEE_HotSpot modules.high_level_functions_CO2.runTCTrend",
                product=kind,
                start_year=start,
                end_year=end,
                start_month=self.start_month,
                end_month=self.end_month,
                max_cloud_cover=self.max_cloud,
                crs=self.crs,
                scale=float(self.scale),
                lon=f"{self.lon[0]},{self.lon[1]}",
                lat=f"{self.lat[0]},{self.lat[1]}",
            )
            if kind == "slopes":
                ds.attrs["slope_scale_factor"] = SLOPE_SCALE_FACTOR
            elif kind == "visual":
                ds.attrs["unit_scale"] = "-0.12,0.12 -> 0..255"
            self._datasets[kind] = ds
        return self._datasets[kind]

    # --------------------------------------------------------------- COG / Zarr
    @staticmethod
    def _north_up(ds: xr.Dataset) -> xr.Dataset:
        y = ds["y"].values
        return ds if y[0] > y[-1] else ds.sortby("y", ascending=False)

    def to_cog(self, path: str | Path, kind: str = "visual",
               tags: dict | None = None) -> Path:
        """Write a Cloud-Optimized GeoTIFF in ``self.crs``.

        ``visual`` (default) is the production product: 3 x uint8, with masked
        pixels carried in an **internal mask band** rather than a nodata value —
        0..255 are all legitimate values of the ±0.12 scale, so a nodata
        sentinel would destroy the extremes. ``slopes`` writes float32 with NaN.

        ``tags`` are extra dataset-level tags. They must be applied here: a COG
        cannot be reopened with "r+" to add them afterwards (GDAL raises
        CPLE_AppDefinedError — updating would break the COG layout).
        """
        import rasterio
        from rasterio.transform import from_origin

        ds = self._north_up(self.dataset(kind))
        bands = list(ds.data_vars)
        x = ds["x"].values
        y = ds["y"].values
        res_x = float(abs(x[1] - x[0]))
        res_y = float(abs(y[1] - y[0]))
        transform = from_origin(
            float(x.min() - res_x / 2), float(y.max() + res_y / 2), res_x, res_y
        )

        stack = np.stack([ds[b].values for b in bands])
        mask = None
        if kind == "visual":
            mask = ~np.isnan(stack).any(axis=0)
            arr = np.where(mask, np.nan_to_num(stack), 0).astype("uint8")
            dtype, nodata, predictor = "uint8", None, 2
        elif kind == "observations":
            arr = stack.astype("uint16")
            dtype, nodata, predictor = "uint16", 0, 2
        else:
            arr = stack.astype("float32")
            dtype, nodata, predictor = "float32", float("nan"), 3

        profile = dict(
            driver="COG",
            dtype=dtype,
            count=arr.shape[0],
            width=arr.shape[2],
            height=arr.shape[1],
            crs=self.crs,
            transform=transform,
            compress="DEFLATE",
            predictor=predictor,
            blocksize=512,
            overview_resampling="average",
            BIGTIFF="IF_SAFER",
        )
        if nodata is not None:
            profile["nodata"] = nodata
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr)
            for i, name in enumerate(bands, 1):
                dst.set_band_description(i, name)
            merged = dict(ds.attrs)
            if tags:
                merged.update(tags)
            dst.update_tags(**{k: str(v) for k, v in merged.items()})
            if mask is not None:
                dst.write_mask(mask.astype("uint8") * 255)
        return path

    def to_zarr(self, path: str | Path, kind: str = "visual") -> Path:
        """Write the same grid as a Zarr store (handy for quick xarray work).

        Zarr v2 with consolidated metadata: no warnings on either side with
        xarray 2026.9 / zarr 3.4, and readable by older clients too. Zarr has no
        nodata concept, so ``visual`` is written as uint8 plus a ``valid``
        variable (255 where the product has data, 0 where it is masked).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ds = self.dataset(kind)
        if kind == "visual":
            first = next(iter(ds.data_vars))
            ds = ds.copy()
            ds["valid"] = (~ds[first].isnull()).astype("uint8") * 255
            ds = ds.fillna(0).astype("uint8")
        ds.to_zarr(path, mode="w", consolidated=True, zarr_format=2)
        return path

    def quicklook(
        self, path: str | Path, kind: str = "visual", vmin: float | None = None,
        vmax: float | None = None,
    ) -> Path:
        """3-panel PNG of the three slope bands (uint8 product by default)."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if vmin is None or vmax is None:
            vmin, vmax = (0, 255) if kind == "visual" else (-1.2, 1.2)
        label = "uint8 (+-0.12 -> 0..255)" if kind == "visual" else "slope x10"

        ds = self.dataset(kind)
        fig, axes = plt.subplots(1, len(SLOPE_BANDS), figsize=(4 * len(SLOPE_BANDS), 4.2))
        for ax, band in zip(np.atleast_1d(axes), SLOPE_BANDS):
            im = ax.imshow(ds[band].values, vmin=vmin, vmax=vmax, cmap="RdBu_r")
            ax.set_title(band)
            ax.set_xticks([])
            ax.set_yticks([])
        fig.colorbar(im, ax=list(np.atleast_1d(axes)), shrink=0.8, label=label)
        start, end = self.years
        fig.suptitle(f"{start}-{end}  {self.lon[0]}..{self.lon[1]}E  {self.lat[0]}..{self.lat[1]}N")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    # ---------------------------------------------------------------- verification
    def verify(self, cog_path: str | Path, kind: str = "visual") -> dict:
        """Structural + geometric checks on a written COG; returns what it found."""
        import rasterio
        from pyproj import Transformer

        expected_dtype = {
            "visual": "uint8", "slopes": "float32", "observations": "uint16"
        }[kind]
        expected_bands = list(SLOPE_BANDS) if kind in ("visual", "slopes") else ["nObservations"]
        out: dict = {}
        with rasterio.open(cog_path) as src:
            out["crs"] = src.crs.to_string()
            out["shape"] = (src.height, src.width)
            out["bands"] = list(src.descriptions)
            out["dtypes"] = src.dtypes
            out["nodata"] = src.nodata
            out["block_shapes"] = tuple(set(src.block_shapes))
            out["compression"] = src.compression.name if src.compression else None
            bounds = src.bounds
            out["overviews"] = src.overviews(1)
            mask_values = sorted(set(np.unique(src.read_masks(1)).tolist()))
            out["mask_values"] = mask_values

            if src.crs.to_epsg() != int(self.crs.split(":")[1]):
                raise AssertionError(f"CRS is {out['crs']}, expected {self.crs}")
            if out["bands"] != expected_bands:
                raise AssertionError(f"unexpected band set: {out['bands']}")
            if set(out["dtypes"]) != {expected_dtype}:
                raise AssertionError(f"dtype {out['dtypes']}, expected {expected_dtype}")
            if kind == "visual":
                # The mask must be a real 0/255 mask. An all-valid tile is
                # legitimate (all-land AOI), so all-255 is not an error; values
                # outside {0, 255} would mean the mask was not written.
                if not set(mask_values) <= {0, 255}:
                    raise AssertionError(f"unexpected mask values: {mask_values}")
                out["masked_pixels"] = int((src.read_masks(1) == 0).sum())

            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            xs, ys = transformer.transform(
                [self.lon[0], self.lon[1], self.lon[0], self.lon[1]],
                [self.lat[0], self.lat[0], self.lat[1], self.lat[1]],
            )
            pad = max(src.res)
            if not (
                bounds.left - pad <= min(xs)
                and bounds.right + pad >= max(xs)
                and bounds.bottom - pad <= min(ys)
                and bounds.top + pad >= max(ys)
            ):
                raise AssertionError(
                    "COG does not cover the requested AOI: "
                    f"bounds={tuple(bounds)}, aoi_3413=({min(xs):.0f},{min(ys):.0f},"
                    f"{max(xs):.0f},{max(ys):.0f})"
                )
            out["covers_aoi"] = True
            out["stats"] = {}
            for i, name in enumerate(out["bands"], 1):
                a = src.read(i, masked=True)
                out["stats"][name] = dict(
                    min=float(a.min()),
                    median=float(np.ma.median(a)),
                    max=float(a.max()),
                    valid_fraction=round(float(a.count() / a.size), 4),
                )
        return out

    def ee_stats(self, kind: str = "visual") -> dict:
        """Reference statistics straight from Earth Engine, for the COG comparison."""
        image = self.visual_image() if kind == "visual" else self.slopes_image()
        geom = self.aoi
        mm = image.reduceRegion(
            reducer=ee.Reducer.minMax(), geometry=geom, scale=self.scale, maxPixels=1e13
        ).getInfo()
        mean = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=self.scale, maxPixels=1e13
        ).getInfo()
        return {"min": {k: v for k, v in mm.items() if k.endswith("_min")},
                "max": {k: v for k, v in mm.items() if k.endswith("_max")},
                "mean": mean}
