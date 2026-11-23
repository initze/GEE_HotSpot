#!/usr/bin/env python3
"""Tiled TCVIS runner: 10x5 degree tiles, N workers, crash-resumable.

Designed for the pan-Arctic run but defaults to an Alaska-sized subset so it can
be rehearsed cheaply. One tile = one job = one pair of COGs (`visual` + `nobs`,
EPSG:3413, 30 m) plus a per-tile PNG. No Zarr.

Typical use (you trigger it, this does not start anything by itself):

    # 1. see the queue, the pixel count and the estimated runtime -- touches no data
    uv run python scripts/panarctic_run.py --list-tiles

    # 2. rehearsal on one tile, watch the wall time
    uv run python scripts/panarctic_run.py --limit 1 --workers 1

    # 3. the real run (resumes automatically if it dies)
    uv run python scripts/panarctic_run.py --workers 4

Restart after a crash: run the same command. Tiles whose `.done.json` marker
matches the current configuration fingerprint are skipped; everything else is
re-queued. A tile is only marked done after both COGs are written, validated and
renamed into place, so a half-written tile can never be mistaken for a finished
one.

Runtime model: 1681 px/s per worker, measured on the EPSG:3857 benchmark. At
30 m a 10x5 degree tile is 190-285 Mpx, i.e. 30-48 h per tile per worker -- this
is a multi-day campaign, not a coffee break. Use `--scale 120` to rehearse the
whole pipeline in hours instead of weeks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DEFAULT_OUT = r"N:/isipd/projects-noreplica/p_alex/TCVIS_data/TCVIS_Landsat/2007-2026/tiles"
MEASURED_PX_PER_S = 1681.0          # per worker, from the 3857 benchmark
R = 6371.0088

PRODUCTS = ("visual", "nobs")


# ----------------------------------------------------------------- tile grid
def hemi(value: float, positive: str, negative: str) -> str:
    return "%s%02d" % (positive if value >= 0 else negative, abs(int(value)))


def tile_id(lon0: float, lat0: float) -> str:
    """Production-style corner id, e.g. W170N60."""
    return "%s%s" % (hemi(lon0, "E", "W"), hemi(lat0, "N", "S"))


def tile_name(lon0: float, lat0: float, start: int, end: int,
              cell_lon: float = 10.0, cell_lat: float = 5.0) -> str:
    """Production-style product name, e.g. TCTrend_SR_W170N60_2007-2026_TCVIS.

    A grid other than the legacy 10x5 gets a `_g<lon>x<lat>` suffix: `W170N60`
    alone would mean both the 10x5 tile and the 1x1 cell at (-170, 60), and two
    grids writing to one filename is how a product silently gets overwritten.
    """
    name = "TCTrend_SR_%s_%d-%d_TCVIS" % (tile_id(lon0, lat0), start, end)
    if (float(cell_lon), float(cell_lat)) != (10.0, 5.0):
        name += "_g%gx%g" % (float(cell_lon), float(cell_lat))
    return name


def build_tiles(lon_min, lon_max, lat_min, lat_max, cell_lon=10.0, cell_lat=5.0,
                start=2007, end=2026):
    """All grid tiles whose cell overlaps the requested bounds."""
    lon0 = math.floor(lon_min / cell_lon) * cell_lon
    lat0 = math.floor(lat_min / cell_lat) * cell_lat
    tiles = []
    lon = lon0
    while lon < lon_max:
        lat = lat0
        while lat < lat_max:
            tiles.append({
                "id": tile_id(lon, lat),
                "name": tile_name(lon, lat, start, end, cell_lon, cell_lat),
                "lon": [lon, lon + cell_lon],
                "lat": [lat, lat + cell_lat],
                "mpx": tile_area(lat, cell_lat, cell_lon) / 0.0009 / 1e6,
            })
            lat += cell_lat
        lon += cell_lon
    return tiles


def tile_area(low_lat, size_lat, size_lon):
    a1, a2 = math.radians(low_lat), math.radians(low_lat + size_lat)
    return R * R * math.radians(size_lon) * (math.sin(a2) - math.sin(a1))


# ------------------------------------------------------------------- config
def make_config(args) -> dict:
    return {
        "start_year": args.start_year,
        "end_year": args.end_year,
        "start_month": args.start_month,
        "end_month": args.end_month,
        "max_cloud": args.max_cloud,
        "scale": args.scale,
        "crs": args.crs,
        "project": args.project,
        "products": list(PRODUCTS),
        "cell_lon": args.cell_lon,
        "cell_lat": args.cell_lat,
        "pin_native_grid": True,
        "snap": True,
    }


def fingerprint(config: dict) -> str:
    """Hash only the product-defining keys.

    The parent hashes ``make_config()`` output while the child re-hashes the
    config file, which also carries ``out_root``, ``tiles`` and runtime knobs.
    Hashing everything made those two hashes differ, so `.done.json` markers were
    written with one hash and compared against another -- i.e. resume never
    skipped anything and every restart redid the whole queue.
    """
    from modules.regional_trend import FINGERPRINT_KEYS

    canonical = {k: config[k] for k in FINGERPRINT_KEYS if k in config}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()[:12]


# --------------------------------------------------------------- per tile
def paths_for(out_root: Path, name: str) -> dict:
    return {
        "visual": out_root / f"{name}_visual.tif",
        "nobs": out_root / f"{name}_nobs.tif",
        "png": out_root / f"{name}.png",
        "marker": out_root / f"{name}.done.json",
        "log": out_root / "logs" / f"{name}.log",
    }


def validate_outputs(p: dict, config: dict) -> tuple[bool, str]:
    """A finished tile must be *readable and correct*, not merely present."""
    import rasterio

    expected = {"visual": "uint8", "nobs": "uint16"}
    for kind, path in (("visual", p["visual"]), ("nobs", p["nobs"])):
        if not path.exists():
            return False, f"missing {kind}"
        try:
            with rasterio.open(path) as src:
                if src.crs.to_epsg() != int(config["crs"].split(":")[1]):
                    return False, f"{kind} crs {src.crs}"
                if src.dtypes[0] != expected[kind]:
                    return False, f"{kind} dtype {src.dtypes[0]}"
                if src.width < 1 or src.height < 1:
                    return False, f"{kind} empty raster"
        except Exception as exc:                                  # unreadable = invalid
            return False, f"{kind} unreadable ({exc.__class__.__name__})"
    return True, "ok"


def is_done(p: dict, config: dict, fp: str) -> tuple[bool, str]:
    if not p["marker"].exists():
        return False, "no marker"
    try:
        marker = json.loads(p["marker"].read_text())
    except Exception:
        return False, "marker unreadable"
    if marker.get("config_hash") != fp:
        return False, "config changed"
    return validate_outputs(p, config)


def run_tile(tile: dict, config: dict, out_root: Path) -> dict:
    """The child process: one tile, both COGs, PNG, marker. Raises on failure."""
    import rasterio

    from modules.regional_trend import RegionalTrend

    p = paths_for(out_root, tile["name"])
    p["log"].parent.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(config)
    config = dict(config, _fingerprint=fp, _tile=tile["id"])

    started = time.time()

    def log(msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] +{time.time() - started:6.0f}s {tile['id']}: {msg}", flush=True)

    log("building trend on Earth Engine (20 annual medians + 2-sigma mask)")
    run = RegionalTrend(
        lon=tuple(tile["lon"]),
        lat=tuple(tile["lat"]),
        years=(config["start_year"], config["end_year"]),
        start_month=config["start_month"],
        end_month=config["end_month"],
        max_cloud=config["max_cloud"],
        scale=config["scale"],
        crs=config["crs"],
        project=config["project"],
        pin_native_grid=config["pin_native_grid"],
        snap=config["snap"],
        concurrency=config.get("xee_concurrency", 1),
        fetch_retries=config.get("fetch_retries", 4),
    )
    grid = run.grid()
    width, height = grid["shape_2d"]
    log(f"grid {width} x {height} px, {run.scale:g} m {run.crs}")

    written = {}
    for kind, ee_kind in (("visual", "visual"), ("nobs", "observations")):
        final = p[kind]
        tmp = final.with_suffix(".tmp.tif")
        tmp.unlink(missing_ok=True)
        log(f"fetching {kind} ...")
        run.to_cog(tmp, kind=ee_kind)
        log(f"{kind} fetched, COG written")
        # a COG is only allowed to appear under its final name once complete
        with rasterio.open(tmp, "r+") as src:
            src.update_tags(tile=tile["id"], config_hash=fp)
        os.replace(tmp, final)
        written[kind] = final

    log("rendering quicklook")
    run.quicklook(p["png"], kind="visual")
    log("verifying")
    checks = {"visual": run.verify(written["visual"], kind="visual"),
              "nobs": run.verify(written["nobs"], kind="observations")}
    log("verified: " + ", ".join(
        f"{b} valid {100 * s['valid_fraction']:.1f}%" for b, s in checks["visual"]["stats"].items()))

    marker = {
        "tile": tile["id"],
        "name": tile["name"],
        "config_hash": fp,
        "seconds": round(time.time() - started, 1),
        "grid": {"width": width, "height": height, "crs": grid["crs"]},
        "shape": checks["visual"]["shape"],
        "stats": checks["visual"]["stats"],
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    p["marker"].write_text(json.dumps(marker, indent=2))
    return marker


# ------------------------------------------------------------------- driver
def child(args, config_file: Path, tile_id_wanted: str):
    config = json.loads(config_file.read_text())
    out_root = Path(config["out_root"])
    tile = next(t for t in config["tiles"] if t["id"] == tile_id_wanted)
    run_tile(tile, config, out_root)
    return 0


def list_tiles(args, config, tiles, fp):
    total_mpx = sum(t["mpx"] for t in tiles)
    hours = total_mpx / (MEASURED_PX_PER_S * args.workers) / 3600
    print(f"grid          {args.cell_lon:g} x {args.cell_lat:g} deg, lat >= {args.lat_min:g}")
    print(f"bounds        lon {args.lon_min:g}..{args.lon_max:g}  lat {args.lat_min:g}..{args.lat_max:g}")
    print(f"window        {args.start_year}-{args.end_year}, months {args.start_month}-{args.end_month}"
          f", cloud < {args.max_cloud}")
    print(f"product       {', '.join(PRODUCTS)} @ {args.scale:g} m, {args.crs}, no zarr")
    print(f"workers       {args.workers}")
    print(f"config hash   {fp}")
    if (args.cell_lon, args.cell_lat) != (10.0, 5.0):
        print(f"note          non-legacy grid -> filenames carry _g{args.cell_lon:g}x{args.cell_lat:g}")
    print()
    print("%-12s %-40s %9s %8s" % ("tile", "name", "Mpx", "est. h"))
    ordered = sorted(tiles, key=lambda t: (-t["mpx"], t["lon"][0], t["lat"][0]))
    for t in ordered:
        print("%-12s %-40s %9.1f %8.1f" % (
            t["id"], t["name"], t["mpx"],
            t["mpx"] * 1e6 / (MEASURED_PX_PER_S * 3600)))
    print()
    print(f"{len(tiles)} tiles, {total_mpx:.0f} Mpx total")
    hours = total_mpx * 1e6 / (MEASURED_PX_PER_S * args.workers) / 3600
    print(f"estimated wall time at {args.workers} workers: {hours:.1f} h "
          f"({hours / 24:.1f} days) -- {MEASURED_PX_PER_S:.0f} px/s/worker, measured, varies with EE load")
    print(f"estimated disk: ~{total_mpx * 1e6 * 4.5 / 1e9:.0f} GB (3x uint8 + mask + uint16 nobs, DEFLATE)")
    print(f"per-worker RAM at this tile size: ~{total_mpx / len(tiles) * 1e6 * 4 * 3 / 1e9:.1f} GB while writing")
    print(f"rehearse cheaply with --scale 120 (roughly {hours / 16:.1f} h) before committing to 30 m")


def preflight(args) -> int:
    """Everything a tile needs before an hour of compute is spent discovering it."""
    import shutil

    ok = True

    def check(label, fn):
        nonlocal ok
        try:
            detail = fn()
            print(f"  OK    {label}" + (f" -- {detail}" if detail else ""))
        except Exception as exc:
            ok = False
            print(f"  FAIL  {label} -- {exc.__class__.__name__}: {exc}")

    def imports():
        import ee  # noqa: F401
        import rasterio
        import xarray  # noqa: F401
        import xee  # noqa: F401
        from modules.regional_trend import RegionalTrend  # noqa: F401
        return f"rasterio {rasterio.__version__} (GDAL {rasterio.__gdal_version__})"

    def ee_auth():
        import ee
        ee.Initialize(project=args.project)
        return "project %s answers, Number(1) = %s" % (args.project, ee.Number(1).getInfo())

    def outdir():
        path = Path(args.out_root)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        free_gb = shutil.disk_usage(path).free / 1e9
        return "%s, %.0f GB free" % (path, free_gb)

    print(f"preflight: {args.out_root}")
    check("imports (ee, xarray, xee, rasterio, modules)", imports)
    check("Earth Engine auth + compute", ee_auth)
    check("output directory writable", outdir)
    print("preflight", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # region / grid
    ap.add_argument("--lon-min", type=float, default=-170.0, help="Alaska bbox default")
    ap.add_argument("--lon-max", type=float, default=-130.0)
    ap.add_argument("--lat-min", type=float, default=60.0, help="southern edge; tiles start here")
    ap.add_argument("--lat-max", type=float, default=72.0)
    ap.add_argument("--cell-lon", type=float, default=10.0)
    ap.add_argument("--cell-lat", type=float, default=5.0)
    # product
    ap.add_argument("--start-year", type=int, default=2007)
    ap.add_argument("--end-year", type=int, default=2026)
    ap.add_argument("--start-month", type=int, default=7)
    ap.add_argument("--end-month", type=int, default=8)
    ap.add_argument("--max-cloud", type=int, default=70)
    ap.add_argument("--scale", type=float, default=30.0)
    ap.add_argument("--crs", default="EPSG:3413")
    ap.add_argument("--project", default="pdg-wg-workflow")
    # runner
    ap.add_argument("--out-root", default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--xee-concurrency", type=int, default=1,
                    help="concurrent computePixels per worker (default 1; EE caps concurrent "
                         "interactive requests, and xee's own default is min(32, cpu+4))")
    ap.add_argument("--fetch-retries", type=int, default=4,
                    help="retries per fetch on a throttling error, with exponential backoff")
    ap.add_argument("--limit", type=int, default=0, help="run at most N tiles (rehearsal)")
    ap.add_argument("--only", default="", help="comma-separated tile ids to run, e.g. W160N65,W150N70")
    ap.add_argument("--exclude", default="", help="comma-separated tile ids to skip")
    ap.add_argument("--tile-timeout", type=int, default=0, help="seconds per tile; 0 = no limit")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--list-tiles", action="store_true", help="show the queue and estimates, touch nothing")
    ap.add_argument("--preflight", action="store_true",
                    help="check imports, Earth Engine auth, output dir and free space, then exit")
    ap.add_argument("--force", action="store_true", help="re-run tiles that already look complete")
    # internal
    ap.add_argument("--run-tile", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--config-file", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.run_tile:
        return child(args, Path(args.config_file), args.run_tile)

    if args.preflight:
        return preflight(args)

    out_root = Path(args.out_root)
    config = make_config(args)
    fp = fingerprint(config)
    tiles = build_tiles(args.lon_min, args.lon_max, args.lat_min, args.lat_max,
                        args.cell_lon, args.cell_lat, args.start_year, args.end_year)

    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        tiles = [t for t in tiles if t["id"] in wanted]
    if args.exclude:
        skip = {s.strip() for s in args.exclude.split(",") if s.strip()}
        tiles = [t for t in tiles if t["id"] not in skip]

    if args.list_tiles:
        list_tiles(args, config, tiles, fp)
        return 0

    if not tiles:
        print("no tiles selected", file=sys.stderr)
        return 2

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "logs").mkdir(exist_ok=True)
    config["out_root"] = str(out_root)
    config["tiles"] = tiles
    config["xee_concurrency"] = args.xee_concurrency
    config["fetch_retries"] = args.fetch_retries
    config_file = out_root / "run_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    # ---- resume: build the queue from what is actually on disk
    queue, skipped = [], []
    for t in tiles:
        p = paths_for(out_root, t["name"])
        ok, why = (False, "forced") if args.force else is_done(p, config, fp)
        if ok:
            skipped.append(t)
        else:
            queue.append(t)
    queue.sort(key=lambda t: (-t["mpx"], t["lon"][0], t["lat"][0]))

    total_mpx = sum(t["mpx"] for t in queue)
    print(f"config {fp} | {len(tiles)} tiles selected | {len(skipped)} already complete")
    print(f"queue {len(queue)} tiles, {total_mpx:.0f} Mpx, "
          f"~{total_mpx * 1e6 / (MEASURED_PX_PER_S * args.workers) / 3600:.1f} h at {args.workers} workers")
    if args.limit:
        queue = queue[:args.limit]
        print(f"limited to {len(queue)} tiles")
    if not queue:
        print("nothing to do")
        return 0
    print("first up:", ", ".join(t["id"] for t in queue[:min(8, len(queue))]))
    print(f"tile size: {queue[0]['lat'][1] - queue[0]['lat'][0]:g} x "
          f"{queue[0]['lon'][1] - queue[0]['lon'][0]:g} deg "
          f"({queue[0]['mpx']:.1f} Mpx each) | "
          f"xee concurrency {args.xee_concurrency}/worker "
          f"= {args.workers * args.xee_concurrency} concurrent computePixels")

    manifest = out_root / "run_manifest.jsonl"
    running: dict[str, tuple[subprocess.Popen, float, int]] = {}
    failures: list[tuple[str, str]] = []
    done = 0
    t0 = time.time()
    last_beat = 0.0
    logged_tail: set[str] = set()

    def record(entry: dict):
        with manifest.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def spawn(tile: dict, append_log: bool = False) -> subprocess.Popen:
        p = paths_for(out_root, tile["name"])
        handle = p["log"].open("a" if append_log else "w")
        cmd = [sys.executable, "-u", str(REPO / "scripts" / "panarctic_run.py"),
               "--run-tile", tile["id"], "--config-file", str(config_file)]
        print(f"  start {tile['id']} ({tile['mpx']:.0f} Mpx) -> {p['log']}")
        return subprocess.Popen(cmd, cwd=str(REPO), stdout=handle, stderr=subprocess.STDOUT)

    def show_tail(tile: dict, lines: int = 15):
        """A failed tile is useless without its traceback in the driver's output."""
        if tile["id"] in logged_tail:
            return
        logged_tail.add(tile["id"])
        log = paths_for(out_root, tile["name"])["log"]
        try:
            body = log.read_text(errors="replace").splitlines()
        except OSError:
            return
        interesting = [ln for ln in body if ln.strip()] or ["(log is empty)"]
        print(f"  --- last {min(lines, len(interesting))} lines of {log.name} ---")
        for line in interesting[-lines:]:
            print(f"  | {line}")
        print("  ---")

    try:
        while queue or running:
            # start jobs up to the worker limit
            while queue and len(running) < args.workers:
                tile = queue.pop(0)
                running[tile["id"]] = (spawn(tile), time.time(), 0)

            time.sleep(5)
            if running and time.time() - last_beat >= 60:
                last_beat = time.time()
                now = time.time()
                print("  ... " + ", ".join(
                    f"{tid} {int((now - t_started) / 60)} min"
                    for tid, (_proc, t_started, _a) in running.items()), flush=True)
            for tid, (proc, started, attempts) in list(running.items()):
                finished = proc.poll() is not None
                timed_out = bool(args.tile_timeout) and (time.time() - started > args.tile_timeout)
                if timed_out and not finished:
                    proc.kill()
                    finished = True
                if not finished:
                    continue

                del running[tid]
                elapsed = round(time.time() - started, 1)
                tile = next(t for t in tiles if t["id"] == tid)
                p = paths_for(out_root, tile["name"])
                ok, why = validate_outputs(p, config) if proc.returncode == 0 else (False, f"exit {proc.returncode}")

                if ok:
                    done += 1
                    record({"tile": tid, "state": "done", "seconds": elapsed,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
                    print(f"  done  {tid} in {elapsed / 60:.1f} min ({done} done, {len(queue)} queued)")
                else:
                    reason = "timeout" if timed_out else why
                    show_tail(tile)
                    if attempts < args.retries:
                        print(f"  retry {tid} ({reason}, attempt {attempts + 2} of {args.retries + 1})")
                        # re-register as running; do NOT also re-queue, or the same
                        # tile gets picked up twice and a hard failure loops forever
                        running[tid] = (spawn(tile, append_log=True), time.time(), attempts + 1)
                    else:
                        failures.append((tid, reason))
                        record({"tile": tid, "state": "failed", "reason": reason,
                                "seconds": elapsed, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
                        print(f"  FAIL  {tid}: {reason}")
    except KeyboardInterrupt:
        print("\ninterrupted - terminating workers so they stop consuming EE quota ...")
        for _tid, (proc, _started, _attempts) in running.items():
            if proc.poll() is None:
                proc.terminate()
        deadline = time.time() + 20
        for tid, (proc, _started, _attempts) in running.items():
            try:
                proc.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                proc.kill()
                print(f"  killed {tid}")
        print("workers stopped; re-run the same command to resume")

    wall = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"done {done} | failed {len(failures)} | skipped {len(skipped)} | wall {wall / 3600:.1f} h")
    if failures:
        print("failures:")
        for tid, why in failures:
            print(f"  {tid}: {why}")
    print(f"outputs: {out_root}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
