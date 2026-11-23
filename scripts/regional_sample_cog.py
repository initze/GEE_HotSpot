#!/usr/bin/env python3
"""Run a regional TCVIS trend and write it locally as COG + Zarr.

Everything scientific comes from ``modules.high_level_functions_CO2.runTCTrend``
via :class:`modules.regional_trend.RegionalTrend`; this script only picks the
window/AOI from the command line and writes the files.

    uv run python scripts/regional_sample_cog.py --out-dir ../out

Defaults are the agreed sample: 2007-2026, lat 70.7-70.9 N, lon 154.0-153.5 W
(i.e. -154.0..-153.5), Jul-Aug, EPSG:3413, 30 m, project pdg-wg-workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.regional_trend import RegionalTrend  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lon0", type=float, default=-154.0)
    p.add_argument("--lon1", type=float, default=-153.5)
    p.add_argument("--lat0", type=float, default=70.7)
    p.add_argument("--lat1", type=float, default=70.9)
    p.add_argument("--start-year", type=int, default=2007)
    p.add_argument("--end-year", type=int, default=2026)
    p.add_argument("--start-month", type=int, default=7)
    p.add_argument("--end-month", type=int, default=8)
    p.add_argument("--max-cloud", type=int, default=70)
    p.add_argument("--scale", type=float, default=30.0)
    p.add_argument("--crs", default="EPSG:3857")
    p.add_argument("--project", default="pdg-wg-workflow")
    p.add_argument(
        "--kind", default="visual", choices=("visual", "slopes"),
        help="visual = production 3-band uint8 (default); slopes = float trend",
    )
    p.add_argument("--out-dir", default="out", help="output directory (kept out of git)")
    p.add_argument("--no-zarr", action="store_true", help="skip the Zarr store")
    return p.parse_args(argv)


def slug(run: RegionalTrend) -> str:
    return (
        f"TCTrend_TCVIS_{run.years[0]}-{run.years[1]}"
        f"_lat{run.lat[0]:g}_{run.lat[1]:g}"
        f"_lon{run.lon[0]:g}_{run.lon[1]:g}"
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    run = RegionalTrend(
        lon=(args.lon0, args.lon1),
        lat=(args.lat0, args.lat1),
        years=(args.start_year, args.end_year),
        start_month=args.start_month,
        end_month=args.end_month,
        max_cloud=args.max_cloud,
        scale=args.scale,
        crs=args.crs,
        project=args.project,
    )
    print("sample:", run.describe())

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = slug(run)

    print("building trend on Earth Engine ...")
    trend = run.trend()
    print("  bands:", trend["data"].bandNames().getInfo())

    print(f"fetching {args.kind} to xarray ...")
    ds = run.dataset(args.kind)
    print("  grid:", ds.sizes, "| crs:", ds.attrs.get("crs"),
          "| product:", ds.attrs.get("product"), "| bands:", list(ds.data_vars))

    cog = run.to_cog(out / f"{name}_{args.kind}.tif", kind=args.kind)
    print("wrote:", cog)
    nobs_cog = run.to_cog(out / f"{name}_nobs.tif", kind="observations")
    print("wrote:", nobs_cog)
    if not args.no_zarr:
        print("wrote:", run.to_zarr(out / f"{name}_{args.kind}.zarr", kind=args.kind))
    print("wrote:", run.quicklook(out / f"{name}.png", kind=args.kind))

    print("verifying ...")
    checks = run.verify(cog, kind=args.kind)
    checks["observations"] = run.verify(nobs_cog, kind="observations")
    stats = run.ee_stats(kind=args.kind)
    checks["ee"] = stats

    # compare COG band means with Earth Engine's own reduceRegion
    worst = 0.0
    for band in checks["stats"]:
        ee_mean = stats["mean"].get(band)
        valid = ds[band].values
        valid = valid[~np.isnan(valid)]
        if ee_mean is None or valid.size == 0:
            continue
        rel = abs(float(valid.mean()) - ee_mean) / max(abs(ee_mean), 1e-6)
        checks["stats"][band].update(
            ee_mean=ee_mean, cog_mean=float(valid.mean()), mean_rel_diff=round(rel, 4)
        )
        worst = max(worst, rel)

    checks["worst_mean_rel_diff"] = round(worst, 4)
    sidecar = out / f"{name}_verification.json"
    sidecar.write_text(json.dumps(checks, indent=2, default=str))
    print("wrote:", sidecar)
    print(json.dumps(checks["stats"], indent=2, default=str))
    print(f"worst COG-vs-EE band-mean difference: {worst:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
