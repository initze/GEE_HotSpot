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
    run.to_cog("out/TCTrend_2007-2026.tif")     # slopes, EPSG:3413, 30 m
    run.to_zarr("out/TCTrend_2007-2026.zarr")   # same grid, xarray-native
    run.quicklook("out/TCTrend_2007-2026.png", vmin=-1.2, vmax=1.2)

Band values are the raw ``runTCTrend`` output, i.e. TC slope * 10 (the factor
exists only so the published uint8 visual fits in 0..255). It is recorded in the
file metadata as ``slope_scale_factor=10``.
"""

from __future__ import annotations

import math
from pathlib import Path

import ee
import numpy as np
import xarray as xr
import xee

from modules import high_level_functions_CO2 as hlf

SLOPE_BANDS = ("TCB_slope", "TCG_slope", "TCW_slope")
SLOPE_SCALE_FACTOR = 10  # runTCTrend multiplies by 10; see module docstring

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
        crs: str = "EPSG:3413",
        project: str | None = None,
        pin_native_grid: bool = True,
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

    # ------------------------------------------------------------------ delivery
    def grid(self) -> dict:
        """Target grid (crs / affine / shape), derived from the bbox by xee."""
        import shapely.geometry

        return dict(
            xee.fit_geometry(
                shapely.geometry.box(self.lon[0], self.lat[0], self.lon[1], self.lat[1]),
                geometry_crs="EPSG:4326",
                grid_crs=self.crs,
                grid_scale=(self.scale, -self.scale),  # negative y = north-up
            )
        )

    def _fetch(self, image: ee.Image) -> xr.Dataset:
        grid = self.grid()
        return xr.open_dataset(
            image,
            engine="ee",
            crs=grid["crs"],
            crs_transform=grid["crs_transform"],
            shape_2d=grid["shape_2d"],
            ee_init_if_necessary=True,
            ee_init_kwargs={"project": self.project} if self.project else None,
        ).compute()

    def dataset(self, kind: str = "slopes") -> xr.Dataset:
        """Fetch one of ``slopes`` / ``observations`` into memory (cached)."""
        if kind not in self._datasets:
            if kind == "slopes":
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
                start_year=start,
                end_year=end,
                start_month=self.start_month,
                end_month=self.end_month,
                max_cloud_cover=self.max_cloud,
                crs=self.crs,
                scale=float(self.scale),
                lon=f"{self.lon[0]},{self.lon[1]}",
                lat=f"{self.lat[0]},{self.lat[1]}",
                slope_scale_factor=SLOPE_SCALE_FACTOR,
            )
            self._datasets[kind] = ds
        return self._datasets[kind]

    # --------------------------------------------------------------- COG / Zarr
    @staticmethod
    def _north_up(ds: xr.Dataset) -> xr.Dataset:
        y = ds["y"].values
        return ds if y[0] > y[-1] else ds.sortby("y", ascending=False)

    def to_cog(self, path: str | Path, kind: str = "slopes") -> Path:
        """Write a Cloud-Optimized GeoTIFF in ``self.crs``."""
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
        arr = np.stack([ds[b].values for b in bands])
        is_float = np.issubdtype(arr.dtype, np.floating)
        profile = dict(
            driver="COG",
            dtype=arr.dtype.name,
            count=arr.shape[0],
            width=arr.shape[2],
            height=arr.shape[1],
            crs=self.crs,
            transform=transform,
            nodata=(float("nan") if is_float else 0),
            compress="DEFLATE",
            predictor=(3 if is_float else 2),
            blocksize=512,
            overview_resampling="average",
            BIGTIFF="IF_SAFER",
        )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr)
            for i, name in enumerate(bands, 1):
                dst.set_band_description(i, name)
            dst.update_tags(**{k: str(v) for k, v in ds.attrs.items()})
        return path

    def to_zarr(self, path: str | Path, kind: str = "slopes") -> Path:
        """Write the same grid as a Zarr store (handy for quick xarray work).

        Zarr v2 with consolidated metadata: no warnings on either side with
        xarray 2026.9 / zarr 3.4, and readable by older clients too.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.dataset(kind).to_zarr(path, mode="w", consolidated=True, zarr_format=2)
        return path

    def quicklook(self, path: str | Path, vmin: float = -1.2, vmax: float = 1.2) -> Path:
        """3-panel PNG of the slope bands (scale is slope*10, hence +-1.2)."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ds = self.dataset("slopes")
        fig, axes = plt.subplots(1, len(SLOPE_BANDS), figsize=(4 * len(SLOPE_BANDS), 4.2))
        for ax, band in zip(np.atleast_1d(axes), SLOPE_BANDS):
            im = ax.imshow(ds[band].values, vmin=vmin, vmax=vmax, cmap="RdBu_r")
            ax.set_title(band)
            ax.set_xticks([])
            ax.set_yticks([])
        fig.colorbar(im, ax=list(np.atleast_1d(axes)), shrink=0.8, label="slope x10")
        start, end = self.years
        fig.suptitle(f"{start}-{end}  {self.lon[0]}..{self.lon[1]}E  {self.lat[0]}..{self.lat[1]}N")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    # ---------------------------------------------------------------- verification
    def verify(self, cog_path: str | Path) -> dict:
        """Structural + geometric checks on a written COG; returns what it found."""
        import rasterio
        from pyproj import Transformer

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

            if src.crs.to_epsg() != int(self.crs.split(":")[1]):
                raise AssertionError(f"CRS is {out['crs']}, expected {self.crs}")
            if out["bands"] != list(SLOPE_BANDS):
                raise AssertionError(f"unexpected band set: {out['bands']}")

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

    def ee_stats(self) -> dict:
        """Reference statistics straight from Earth Engine, for the COG comparison."""
        image = self.slopes_image()
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
