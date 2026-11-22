# GEE_HotSpot
Google Earthengine HotSpot Regions of Permafrost Change Production and Visualization

### Version History
#### v0.6 [2022-10-28]
* converted python code to package
#### v0.5 [2022-10-28]
* added masking (e.g. only water areas) in trend calculation
#### v0.4 [2022-03-09]
* TCVIS (almost global coverage)
* added global DEM coverage with nice visualization (by G.Donchyts)
* link to J.Braaten's annual Landsat mosaic tool
#### v0.3.2 [2021-09-10]
* adapted panel styling
* added Anaktuvuk to examples
* changed starting location
#### v0.3.1 [2021-07-25]
* fixed sharable link bug (did not work before)
* code cleanup (unnecessary code e.g. imports)
#### v0.3 [2021-06-08]
* added swiping functionality
#### v0.2 [2021-04-06]
* added shareable link option
#### v0.1
* first github version

### Visualization
https://ingmarnitze.users.earthengine.app/view/hotspottcvisapp
#### Startup Screen
![grafik](https://user-images.githubusercontent.com/4864803/132829830-b1a6f798-8542-40d5-8780-5762d9435d38.png)
#### Example Drew Point Coastal Erosion
![grafik](https://user-images.githubusercontent.com/4864803/132829945-febe202c-75d2-46d4-ad0c-43175fa15050.png)
#### Example Drew Point Coastal Erosion - with time series plot
![grafik](https://user-images.githubusercontent.com/4864803/132830052-eea168af-9f0a-4b85-ba38-82793bb7e3cf.png)
#### Example Batagaika Crater - ArcticDEM
![grafik](https://user-images.githubusercontent.com/4864803/132830161-4b6afc31-12c8-446b-b5a9-86b04951c829.png)
#### Example Batagaika Crater - TCVIS Layer
![grafik](https://user-images.githubusercontent.com/4864803/132830241-9f7e7fe2-3262-4c47-ad0c-0be5621ade4a.png)

### Regional sample → local COG / Zarr

`modules/regional_trend.py` wraps the production trend (`runTCTrend`) for a single
bounding box and delivers the result locally instead of exporting an EE asset:

```python
from modules.regional_trend import RegionalTrend

run = RegionalTrend(
    lon=(-154.0, -153.5), lat=(70.7, 70.9),      # 154.0W-153.5W, 70.7-70.9N
    years=(2007, 2026),                          # Jul-Aug, cloud < 70 %
    project="pdg-wg-workflow",
)
run.to_cog("out/TCTrend_2007-2026_slope.tif")    # 3 slope bands, EPSG:3413, 30 m
run.to_cog("out/TCTrend_2007-2026_nobs.tif", kind="observations")
run.to_zarr("out/TCTrend_2007-2026_slope.zarr")
run.quicklook("out/TCTrend_2007-2026.png")
run.verify("out/TCTrend_2007-2026_slope.tif")    # CRS / bands / AOI-coverage checks
```

The same run from the shell:

```bash
uv sync
uv run python scripts/regional_sample_cog.py --out-dir ../out
```

`notebooks/Regional_Sample_2007-2026.ipynb` walks through it cell by cell. Band values are
TC slope × 10 — the factor exists only so the published uint8 visual fits 0..255 — and the
`_nobs` band records per-pixel observation counts, which is how the thin early years (L5/L7
only before 2013) show up.

