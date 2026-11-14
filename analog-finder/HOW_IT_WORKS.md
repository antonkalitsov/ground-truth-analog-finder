# Ground Truth: how it works, where the data comes from and where it lives

## 1. The idea in one paragraph

Pick a place on the Moon (south pole, Artemis III regions) or on Mars. Ground Truth describes that place with 17 numbers (its traits), describes every land cell of the Earth with the same 17 numbers, and scores how close each Earth cell is to the target. The best-scoring cells that are far from all known analog sites are shown as "new candidates". Everything is computed in the browser from a small pre-built data pack.

## 2. Two halves

| Half | Language | Runs where | Job |
|---|---|---|---|
| `pipeline/` | Python (numpy, rasterio, zarr, Pillow) | on a computer, once | download NASA/JAXA/ESA/USGS data, turn it into trait grids, write the data pack |
| `web/` | JavaScript, HTML, CSS, a little GLSL | in the browser | load the pack, score, draw globes, lists and charts |

No framework, no build step, no server code. `start.bat` only runs `python -m http.server`.

## 3. Where the data comes from

### Earth (every land cell, 0.25 degree grid, 1440 x 720, 318,332 land cells)

| Trait group | Dataset | Host | Script |
|---|---|---|---|
| Elevation, slope, roughness, local relief | AWS Terrain Tiles (Mapzen "terrarium", zoom 7; a mosaic of SRTM, GMTED2010, ETOPO1, ArcticDEM) | AWS Open Data (`elevation-tiles-prod`) | `01_fetch_earth_tiles.py`, `03_build_earth_dem.py` |
| Air temperature, daily range, precipitation, surface pressure, soil wetness, wind, snow fraction | NASA POWER climatology, MERRA-2 (0.5 x 0.625 degrees) | AWS Open Data (`nasa-power`, Zarr) | `02_fetch_power.py` |
| Surface albedo, aerosol (dust) | NASA POWER, CERES SYN1deg | same | `02_fetch_power.py` |
| Bare ground, vegetation, ice cover | ESA WorldCover 2021 v200 (10 m, read from the coarse overviews) | AWS Open Data (`esa-worldcover`) | `04_fetch_worldcover.py` |
| Land mask, country and region names | Natural Earth 1:10m vectors | GitHub / Natural Earth | `05_earth_traits.py` |
| Sun angle | computed from latitude (mean noon sun elevation) | none | `terrainlib.py` |
| **Day-night surface temperature swing** | JAXA GCOM-C SGLI land surface temperature, day minus night, 2023 | JAXA Earth API (G-Portal) | `fetch_official.py`, `05b_official_earth.py` |
| **Precipitation** (within 60 degrees) | JAXA GSMaP gauge-adjusted precipitation normal 2012-2021 | JAXA Earth API (EORC) | same |
| **Plant cover** | MODIS NDVI normal 2012-2021 | JAXA JASMES via the JAXA Earth API | same |
| **Rock type** | GLiM global lithological map (Hartmann and Moosdorf 2012), 0.5 degree | PANGAEA | same (`glim_05deg.zip`) |

Tested and rejected: AMSR2 soil moisture (it lowered the validation score).

### Moon (south pole, 75 to 90 S)

| What | Dataset | Host | Script |
|---|---|---|---|
| Terrain (slope, roughness, relief, sun) | LRO LOLA south-pole DEM, 30 m | USGS Astrogeology on AWS | `06_mars_moon_grids.py` |
| Mean and maximum temperature, depth to stable ice | LRO Diviner polar resource product (`dlre_prp_south`) | NASA PDS Geosciences Node | `fetch_official.py`, `06b_lro_layers.py` |
| Rock family | USGS Unified Geologic Map of the Moon (1:5M) | USGS Astrogeology on AWS | `06b_lro_layers.py` |
| Picker map | LROC WAC south-pole mosaic, 100 m | USGS Astrogeology on AWS | `06b_lro_layers.py` |
| Globe picture | SELENE (Kaguya) Terrain Camera mosaic, with the polar cap from LROC WAC | JAXA / USGS | `06c_moon_texture_pole.py` |

The Moon is a 119 x 119 grid of 7.7 km cells in polar stereographic projection. The 9 Artemis III regions plus Shackleton's rim are listed with coordinates and sources in `pipeline/targets.json`.

### Mars

| What | Dataset | Host |
|---|---|---|
| Terrain | MGS MOLA global DEM, 463 m | USGS Astrogeology on AWS |
| Albedo | MGS TES albedo | USGS Astrogeology on AWS |
| Temperature, ice | latitude-based models (documented in `traits.py`) | none |
| Mars sites (15) | Mission and literature coordinates in `targets.json` | each entry has its own source URL |

Mars is a 1 degree grid. Thermal inertia was dropped because the server returned truncated files.

### Known analog sites (107)
NASA Planetary Analog Explorer, Foucher et al. 2021, and the "Terrestrial analogue site" catalogue. Stored in `pipeline/known_sites.json`, one source URL per site. A 72-site subset is the validation set (`earth_sites_validation.csv`).

### Fetched live, by the browser, only when you ask
- Earth terrain close-ups: AWS Terrain Tiles (the side-by-side picture).
- Satellite view in the detail card: Copernicus Sentinel-2 cloudless (EOX), NASA GIBS (MODIS and VIIRS).
- Nothing else leaves the page. There is no analytics, login or third-party script.

## 4. The pipeline, step by step

1. `01_fetch_earth_tiles.py` downloads all zoom-7 terrain tiles (16,384 PNGs).
2. `02_fetch_power.py` mirrors the NASA POWER Zarr variables into `.npy`.
3. `03_build_earth_dem.py` turns the tiles into a global DEM.
4. `04_fetch_worldcover.py` reads WorldCover into 0.25 degree class fractions.
5. `05_earth_traits.py` builds every Earth trait layer.
6. `fetch_official.py` (originally run on a local PC, because NASA PDS and JAXA were blocked from the cloud build container) saves Diviner and the JAXA layers as `.npz`.
7. `05b_official_earth.py` regrids those JAXA layers and GLiM to 0.25 degrees and replaces or adds Earth traits.
8. `06_mars_moon_grids.py` and `06b_lro_layers.py` build the Mars and Moon trait grids.
9. `07_build_pack.py` quantizes everything into the web data pack and writes `manifest.json`.
10. `07c_hires_images.py` makes the sharper close-ups and the 8k Earth image. `06c_moon_texture_pole.py` patches the Moon texture.
11. `08_findings.py` runs the validation and writes `FINDINGS.md` and `findings.json`.
12. `09_stage2.py` re-ranks the top 10 candidates at 30 m for Jezero and the ten Moon regions (see section 4b) and writes `stage2.json`. It reads everything it needs straight from public buckets, so it needs no files in `raw/` except the 10 MB Jezero terrain model it downloads itself. `09b_stage2_validation.py` then scores the validation sites at 30 m and adds the result to `stage2.json` and FINDINGS.md.

## 4b. Stage 2: from a 28 km cell to an 8 km landing zone

A rover does not land on a 28 km square. Stage 2 keeps the stage 1 search as the screen and then looks inside each of its ten best cells.

| Step | What happens |
|---|---|
| Targets | Jezero (Mars 2020 CTX terrain model, 20 m, USGS) and the nine Artemis III regions plus Shackleton's ridge (LRO LOLA, 30 m). Each target is described by an 8 km zone around its coordinates. |
| Candidates | The script repeats the app's scoring and picking for all six purposes, so every cell the app can list as a top 10 candidate for these targets is covered (about 20 to 40 cells per target). |
| Earth data | A 30 km window of Copernicus GLO-30 (ESA, 30 m, AWS Open Data) around each cell, with its water mask. |
| One grid | All three worlds are resampled to the same 30 m local grid and smoothed with the same 3 x 3 mean. |
| Sliding zone | An 8 km disc (the Perseverance landing ellipse is 7.7 x 6.6 km) moves across the 28 km cell in 2 km steps: 121 placements. Placements with more than 2% water or missing data are dropped. |
| Measured | Slope distribution (60 m baseline), RMS height difference at 60, 150, 300 and 900 m steps, and relief (95th minus 5th percentile). |
| Kept | The placement closest to the target zone: 0.4 slope + 0.4 roughness + 0.2 relief. Its centre, numbers and the three similarities go into `stage2.json`. |

In the app, "Refine these ten at 30 m" re-ranks the list. The score is the stage 1 weighted average with the three coarse terrain similarities replaced by the 30 m ones, so the chosen purpose still applies. The detail card shows the zone's coordinates, a slope curve against the target and a table, and both close-ups show the zone as a circle. Targets picked by hand, the other Mars sites and custom weights that surface a cell outside the precomputed set are not refined.

## 5. What is in the data pack (`web/data/`, about 6 MB)

| File | Size | Content |
|---|---|---|
| `earth.bin.gz` | 2.1 MB | 17 layers x 1440 x 720, one byte per cell, quantized between a per-trait min and max |
| `names.bin.gz`, `names.json` | 0.13 MB | per cell: region, country and geographic area (index into a name list) |
| `mars_grid.bin.gz` | 0.19 MB | 17 traits x 360 x 180 |
| `moon_grid.bin.gz` | 0.05 MB | 119 x 119 traits, valid mask, geologic unit, Diviner coverage |
| `manifest.json` | 0.07 MB | trait definitions (range, tolerance, Earth percentiles), purposes and weights, body constants, 25 targets with trait vectors, 107 known sites, sources |
| `chips/*.bin.gz` | 3.5 MB | 28 km elevation close-ups of the named Moon and Mars sites (int16, 512 px Moon, 256 px Mars) |
| `findings.json` | 0.01 MB | validation numbers |
| `stage2.json` | about 0.1 MB | per fine target: its 8 km zone statistics and, for each candidate cell, the best 30 m landing zone |

Images in `web/assets/`: `earth.jpg` (4k) and `earth_8k.jpg` (8k, loaded after the first paint), `moon.jpg`, `mars.jpg`, `moon_spole.jpg`. Fonts in `web/fonts/`.

## 6. What the browser does (`web/js/`)

- `score.js`: loads and decompresses the pack, builds a 256-entry lookup table per trait, and scores all 318,332 cells for the chosen target and weights. For each trait the similarity is 1 minus the distance divided by a tolerance. If the target lies outside what Earth reaches (for example the Moon's cold), similarity is how close the cell sits to Earth's own extreme. Rock type is a lookup table of rock families. The score is the weighted average, scaled 0 to 100.
- `app.js`: stages (title, choice, app), menus and purposes, search, list, candidate picking (10 best, 300 km apart, over 150 km from known sites), detail card, tour.
- `globe.js`: a small raw-WebGL globe used for the Earth, the target, and the Mars picker.
- `planets.js`: the two lit planets on the choice screen.
- `terrain.js`: fetches live Earth elevation tiles and draws the hillshade.

## 7. Validation

Known analog sites are ranked against ordinary land without the search ever being told where they are. Area under the curve (0.5 is chance): environment traits Mars 0.75, Moon 0.82; geology alone Mars 0.60, Moon 0.70. Details and an ablation table are in `FINDINGS.md`.

## 8. Where everything is stored

- **Git:** the code, the docs and the built data pack (`web/`, about 11 MB including images) are in this repository: https://github.com/antonkalitsov/ground-truth-analog-finder. The `.gitignore` excludes `raw/` (about 6 GB of source data), `__pycache__/`, `.venv/` and `.env`.
- **Raw downloads:** `analog-finder/raw/` (about 6.3 GB) and `data/official/` on the machine that ran the pipeline. They are not committed.
- **Local keys:** an optional `.env` with OpenTopography and Cesium keys. The final site does not use them and the file is never committed.
- The raw downloads can be rebuilt: every script above re-downloads its source (`setup.bat rebuild` or `sh setup.sh rebuild` runs the whole chain).

## 9. Known limits

- Candidates are 28 km averages. Features smaller than a cell are not seen. They are tagged "Approximate".
- Stage 2 is a locator, not a detector: on its own, 30 m terrain separates known Mars analogs from non-analogs worse than the 28 km terrain (AUC 0.60 against 0.75), because most plains contain a Jezero-like 8 km patch. The full score holds (Mars 0.73 to 0.68, Moon 0.74 to 0.74). See FINDINGS.md.
- Stage 2 refines terrain only, for Jezero and the Moon regions only. At 30 m it sees slopes and landforms, not rocks. GLO-30 (radar), CTX (stereo) and LOLA (laser tracks, sparser away from the pole) have different noise, which the shared 3 x 3 smoothing reduces but does not remove.
- Mars close-ups are limited by the 463 m MOLA pixels. Earth close-ups poleward of 60 N are coarse.
- Moon traits beyond Earth (cold, vacuum, gravity, radiation) cannot be matched anywhere on Earth. The detail card says so under "Where it breaks down".
