# Ground Truth

**A global search of Earth's land for new analogs of Artemis III Moon base regions and Mars sites.**

Built for the NASA Space Apps Challenge 2026, challenge *"Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars"*.

It is built on the official challenge resources: **NASA LRO (LOLA, LROC, Diviner) and PDS, NASA Earthdata / Worldview (GIBS), JAXA G-Portal products (GCOM-C, GSMaP, MODIS NDVI via the JAXA Earth API), ESA Copernicus (WorldCover, Sentinel-2) and links to CSA RADARSAT**, plus USGS Astrogeology maps.

Analog sites are usually picked by experience: Atacama, Antarctica, Iceland, Hawaii. Ground Truth instead scores **every land cell on Earth** (318,332 cells of 0.25°, about 28 km) against a chosen place on the Moon or Mars, ranks the best matches, flags the ones that are **far from every catalogued analog site**, and explains for each one where the analogy holds, where it breaks down and how it can help exploration.

## Run it

The site is static (HTML, CSS, plain JavaScript modules, no build step, no dependencies, no 3D library, about 5.5 MB).

- **Windows:** double-click `start.bat`, then open http://localhost:8000
- **Any system:** `cd web` then `python -m http.server 8000`, then open http://localhost:8000

It must be served over http (not opened as a file) because the browser loads the data pack with `fetch`. Scoring works offline; only the live Earth terrain close-ups need the internet. Deploys as-is to GitHub Pages or any static host (publish the `web` folder).

Share a view with the URL hash, for example `#moon/shackleton-connecting-ridge/polar` or `#mars/jezero-perseverance/overall`.

## How to use

1. **Title card, then choose a destination.** The Moon and Mars turn slowly under one light; click one. The wordmark stays in the header and takes you back to this choice.
2. **Read the sentence at the top:** *Earth analogs of [place] for [purpose]*. Both underlined parts are menus. The place menu lists the 9 Artemis III candidate regions plus Shackleton's rim (Moon) or 15 landing, human-mission and cave sites (Mars), and "Pick any point" opens the LROC WAC south-pole map or a Mars globe. The purpose menu holds six mission purposes; the trait weights behind each are one click further down.
2b. **Search.** The box above the list finds Earth countries, regions and geographic areas (offline, from the data pack), catalogued analog sites, Moon and Mars targets, or plain coordinates (`64.1, -21.9`). Choosing an Earth area opens its best-matching cell.
3. **See the target.** Beside the Earth, a small Moon or Mars turns to the place being searched for and marks it. Drag to turn it; click another marker or any point to search for that instead.
4. **Scan the list.** "New candidates" are the 10 best-matching places on Earth that are at least 300 km apart and more than 150 km from all 107 catalogued analog sites. "Field-validated sites" ranks the catalogued sites for the same target. Each row gives the place, coordinates, analog type and a one-line reason. "Filter by type" narrows the list.
5. **Open a site.** The panel shows the score, a provenance tag, side-by-side terrain (LOLA or MOLA against live Earth elevation), where the analogy holds, where it breaks down and what it is good for. The full trait table, satellite view (Copernicus Sentinel-2, NASA MODIS, NASA VIIRS night lights) and links to NASA Worldview, Earthdata Search, Copernicus Browser, the JAXA Earth viewer, G-Portal and EODMS (RADARSAT) are folded away until asked for.
6. **Play tour** runs a one-minute walk-through (made for the demo video).

## Interface notes

- **Three stages, one page:** title card, destination choice, instrument. No reloads; a URL hash such as `#moon/haworth/isru` opens the instrument directly.
- **No 3D library.** The Moon and Mars are each one full-canvas triangle whose fragment shader ray-casts a sphere, wraps a real map on it (Kaguya Terrain Camera mosaic; MOLA shaded relief tinted with TES albedo), bends the normal with the map's own brightness and lights it from one side (`web/js/planets.js`, about 100 lines). The Earth globe is a small raw-WebGL module (`web/js/globe.js`). Both are fetched only when their stage opens, and pixel ratio is capped at 2.
- **Reading the score:** one colour language everywhere. Blue is match score and likeness (map, radar, bars), orange is the Moon or Mars target, white is the Earth place. Every list row has a small radar: one spoke per aspect, always in the same order, the further out the more alike, the dashed outer ring meaning identical; a labelled example above the list names the spokes. The card opens with a large radar with each aspect's percentage, then "How the score adds up": the score as 100 points split by aspect (track = points the aspect is worth for the chosen purpose, blue = points earned), adding up exactly to the score. The full trait table sits under "All traits". The map legend shows the score at both ends and the middle, and hovering the map gives a place's score and percentile.
- **Landing zone at 30 m:** the slope mix of the Earth zone and the target zone drawn as two distribution curves, rebuilt from the 8 stored percentiles and lightly smoothed, with medians marked and the shared area in blue (overlap coefficient). The scored slope match is stricter and is shown separately, with a before and after score for the cell.
- **Motion** uses transform and opacity only, with `cubic-bezier(0.16, 1, 0.3, 1)` for entrances and `cubic-bezier(0.65, 0, 0.2, 1)` for moves. With `prefers-reduced-motion` the title card is skipped, the planets hold still and every state change is instant.
- **Type:** Newsreader (variable, self-hosted, SIL Open Font License) for display, the system sans for everything else, tabular numerals for all figures. One accent colour.
- **Measured** in headless Chromium at 1440x900: title painted in under 0.1 s, cumulative layout shift 0, no third-party scripts, no horizontal overflow at 390x844.

## Where the analog sites come from, and what is approximate

Every site in the interface carries one of two tags.

| Tag | What it is | Source |
|---|---|---|
| **Field-validated** | 107 analog sites that agencies or published studies have used | NASA Planetary Analog Explorer, Foucher et al. 2021 (Planet. Space Sci. 197:105162), the "Terrestrial analogue site" catalogue on Wikipedia and the mission pages each entry links to (`pipeline/known_sites.json`, one source URL per site, shown in the panel) |
| **Approximate** | Candidates computed by this project; nobody has validated them in the field | The scoring described under Method, on the datasets listed under References |

Approximations to keep in mind:

- **Cell size.** Earth is scored on 0.25 degree cells (about 28 km). Values are cell averages, so single craters, lava tubes and outcrops are not seen. Mars targets are read from a 1 degree grid, the Moon from 4 km cells.
- **Coordinates** of catalogued sites and of Moon and Mars targets are approximate (a named region reduced to one point).
- **Place names** of candidates are the nearest Natural Earth administrative or geographic region, not surveyed locality names.
- **Analog type** of a candidate (polar desert, volcanic plain and so on) is a rule on its trait values, not a geological survey.
- **Sunlight** on Earth is derived from latitude (noon sun elevation), not from terrain shadowing.
- **Day-night temperature swing** is JAXA GCOM-C surface temperature for 2023; cells cloudy all year are filled from MERRA-2 air temperature through a fitted line.
- **Rock** on Earth is the dominant GLiM class of a 0.5 degree cell; on the Moon the USGS unified geologic map unit; on Mars a family assigned per site from the literature.
- **Lunar ice** is the LRO Diviner model of ice stability depth, not a detection of ice.
- **Beyond-Earth values** (lunar cold, Martian pressure and radiation) have no match on Earth; such traits score by how close a cell sits to Earth's own extreme, and the panel says so under "Where it breaks down".
- **Image sharpness** is set by the sources: Moon close-ups are LRO LOLA 30 m (shown at 55 m per pixel); Mars close-ups are MGS MOLA 463 m, so only about 60 real pixels span 28 km and they look soft; Earth close-ups come from AWS Terrain Tiles (about 30 m where SRTM covers, coarser and sometimes streaky poleward of 60 N). The Earth globe is 8192 px (Blue Marble colour with Natural Earth 1:10m shaded relief, `pipeline/07c_hires_images.py`); the heat map on it is the 0.25 degree scoring grid, so it turns blocky when zoomed far in.
- **Terrain close-ups** are hillshades drawn from elevation data, not photographs. Earth close-ups poleward of about 80 degrees are stretched by the tile projection.
- **Moon texture:** the globe's south polar cap (poleward of 75 S) is filled from the LROC WAC polar mosaic, because the Kaguya mosaic breaks into shadow streaks there (`pipeline/06c_moon_texture_pole.py`). The star field is decorative, not a real sky.
- **Planet textures** on the choice screen are real mosaics, but the bump lighting is derived from image brightness, not from topography.

## Method

| Group | Trait | Earth source | Moon / Mars source |
|---|---|---|---|
| Terrain | mean slope, roughness, local relief | AWS Terrain Tiles (SRTM, GMTED2010, ETOPO1 mosaic), resampled to 1 arc-minute | **LRO LOLA** 30 m south pole DEM; MGS MOLA 463 m DEM |
| Geology | rock type | GLiM global lithological map (Hartmann & Moosdorf 2012) | **USGS Unified Geologic Map of the Moon** (2020); published geology of each Mars site, basalt elsewhere |
| Surface | albedo, barren ground, ice/snow cover | NASA POWER CERES SYN1deg albedo; **ESA WorldCover** 2021 | TES albedo; Moon 0.15; Mars polar caps |
| Thermal | mean temperature, day-night swing | MERRA-2 air temperature (lapse-rate corrected); **JAXA GCOM-C SGLI** land surface temperature, day minus night, 2023 | **LRO Diviner** polar resource product (Moon); latitude averages (Mars) |
| Illumination | annual mean noon sun elevation | latitude and obliquity 23.44° | obliquity 1.54° (Moon), 25.19° (Mars) |
| Water and ice | ground-ice likelihood, precipitation, soil moisture | MERRA-2 temperature; **JAXA GSMaP** precipitation normal (MERRA-2 beyond 60°); MERRA-2 GWETTOP | **LRO Diviner** depth to stable ice (Moon); SWIM ground-ice latitudes (Mars) |
| Biology | plant greenness | **MODIS NDVI normal (JAXA JASMES)** | none |
| Atmosphere | dust (aerosol optical depth), wind, pressure | CERES SYN1deg AOD, MERRA-2 wind, elevation | typical Mars values; Moon none |

* **Same ruler on three worlds.** Terrain statistics use the same definitions everywhere: elevation averaged to about 1.85 km pixels; slope by central differences; roughness = RMS of elevation minus its 5 × 5 neighbourhood mean; relief = 95th minus 5th percentile, all inside a 15 × 15 pixel (about 28 km) window.
* **Similarity per trait** = 1 − |Earth − target| / tolerance. When the target lies beyond anything on Earth (a 1° noon sun, −100 °C), the trait ranks places toward Earth's own extreme instead (1 for Earth's most extreme land, 0 for the median), and the card labels it "Earth limit". The two blend smoothly: past the edge of Earth's range (1st to 99th percentile) the extreme-ranking share grows from 0 to 100 % over one tolerance, so nearby targets always get nearby scores.
* **Score** = weighted mean of trait similarities × 100. Mission presets weight traits for what the analog is for, following the *functional analogue* idea of Foucher et al. (2021). Precipitation and plant greenness overlap (rank correlation 0.80 across Earth's land), so in every purpose their weights are cut to 0.75 of the rest: together they count as 1.5 traits, not 2. Soil moisture is not part of this: on Earth it follows cold and ground ice more than rainfall.
* **Never reproducible** factors (gravity, vacuum or thin CO₂ air, surface radiation) are listed on every card.

## The challenge's considerations

| Consideration | How it is covered |
|---|---|
| Geology and mineralogy | Rock-type trait (GLiM vs USGS lunar geologic map and Mars site geology), albedo, barren ground |
| Terrain | Slope, roughness, relief measured identically on all three bodies; side-by-side terrain close-ups |
| Temperature and illumination | LRO Diviner (Moon), JAXA GCOM-C surface temperature swing (Earth), noon sun elevation; LROC WAC polar imagery |
| Water, ice, permafrost | LRO Diviner ice stability (Moon), SWIM latitudes (Mars), Earth permafrost from temperature, JAXA GSMaP rainfall |
| Dust and wind | NASA CERES aerosol optical depth, MERRA-2 wind |
| Biology | JAXA / MODIS NDVI and ESA WorldCover bare ground |
| Caves and lava tubes | Arsia Mons cave skylights as a Mars target; basaltic rock type points to lava plains on Earth |
| Exploration operations | Mission presets, a "how it helps exploration" list per card, VIIRS night lights as a remoteness check |
| Processes | Rock families are formation processes: impact, volcanism, lake sedimentation, evaporation, periglacial, glacial |
| Scale | 28 km global search, 1.85 km terrain ruler, live elevation close-up, 10 m Sentinel-2 view |
| Earth's limits | Gravity, vacuum or thin CO₂ air and radiation on every card; every beyond-Earth trait is flagged |

## Validation

Nothing was tuned on known sites. Each Earth cell takes its best score over all targets of a body (Overall preset). AUC is the chance that a known analog outscores a clear non-analog (rainforest, farmland, cities, wetlands, taiga, ice sheet).

| Body | Environment analogs vs clear non-analogs (AUC) | Geology-only analogs vs non-analogs (AUC) | 107 catalogued sites: median percentile |
|---|---|---|---|
| Mars | 0.75 | 0.60 | 74th |
| Moon | 0.82 | 0.70 | 68th |

Every official dataset was checked against this validation. JAXA Diviner, GCOM-C, GSMaP and NDVI layers raised it (Moon 0.75 to 0.82). JAXA AMSR2 soil moisture lowered it and was dropped (its retrieval reads high over sand seas and fails under forest). The GLiM rock map at 0.5° mostly sees sedimentary cover, so rock type carries a small weight in the Overall preset and full weight in the Instruments and ISRU presets. See [FINDINGS.md](FINDINGS.md) for the step-by-step table and per-target candidates.

## Headline findings

* **Lunar south pole (Shackleton, de Gerlache, polar-ops preset):** Peary Land and the ice-free north coast of Greenland and Ellesmere Island (80–83°N) are the closest Earth gets to a low sun over bare, steep, frozen ground, and lie 450–850 km from the nearest catalogued analog.
* **Malapert Massif and Slater Plain:** the high dry Andes of Coquimbo and Catamarca (Argentina) and Atacama (Chile), plus western Tibet and Qinghai, match the slopes and roughness while staying bare and dry.
* **Jezero and Gale (Mars):** the Tibesti foothills of Borkou (Chad), the Red Sea hills of Egypt and Sudan, central Iran (Yazd) and Djibouti combine Mars-like terrain with extreme dryness, 550–900 km from the nearest catalogued analog.
* **Arcadia and Utopia Planitia (ice prospecting):** the frozen, bare, dry Tibetan Plateau and Qinghai (Xinjiang, Xizang) give the best combination of ground ice and Mars-like dryness.

## Limitations

* 28 km cells: small craters, lava tubes and outcrops are invisible at this scale; use the live terrain close-up and field data to confirm.
* Moon temperature and ice come from LRO Diviner; the Moon day-night swing is approximated as 2 × (maximum − mean). Mars thermal, ice, dust and wind traits are published averages by latitude, not climate-model output. Moon coverage is 75–90°S.
* Artemis III region coordinates are approximate points inside each region (NASA has not published centres).
* Rock type is a first-level class (basalt, granite, sandstone and so on), not mineralogy; no accessibility, permits or logistics layer.
* Not yet scored: radar roughness (CSA RADARSAT, Sentinel-1, ALOS-2 vs LRO Mini-RF) and neutron hydrogen (LRO LEND). These are the next traits.

## Rebuild the data

Python 3.10+ with `numpy rasterio pillow zarr numcodecs`. About 5 GB of downloads (all public, no keys).

```
cd pipeline
python 01_fetch_earth_tiles.py ../raw/terrarium7      # 16,384 Earth elevation tiles (AWS)
python 02_fetch_power.py ../raw/power                  # NASA POWER climatology (AWS Zarr)
python 03_build_earth_dem.py ../raw/terrarium7 ../raw/earth_1min.npy
python 04_fetch_worldcover.py ../raw/worldcover_025.npz  # ESA WorldCover overviews (AWS)
# Natural Earth geojson into ../raw/ne/ (land, lakes, antarctic ice shelves, glaciated areas, admin 0, admin 1, geography regions)
# Mars and Moon DEMs into ../raw/: Mars_MGS_MOLA_DEM_mosaic_global_463m.tif, Mars_MGS_TES_Albedo_mosaic_global_7410m.tif, LRO_LOLA_DEM_SPole75_30m.tif (USGS Astrogeology on AWS)
python 05_earth_traits.py ../raw ../raw/earth_traits.npz
# official challenge datasets: run ../fetch_official.py on a machine that can reach NASA PDS and JAXA,
# then copy data/official/*.npz and glim_05deg.zip into ../raw/official/
python 05b_official_earth.py ../raw                      # JAXA GCOM-C, GSMaP, MODIS NDVI and GLiM onto the Earth grid
python 06_mars_moon_grids.py ../raw ../raw/grids ../web/assets
# LROC WAC south pole mosaic and the Unified Geologic Map of the Moon raster into ../raw/lro/ (USGS Astrogeology on AWS)
python 06b_lro_layers.py ../raw ../web/assets            # WAC picker map, lunar geology, Diviner gridding
python 07_build_pack.py ../raw ../web
python 08_findings.py ../raw ../web ../FINDINGS.md
python 09_stage2.py ../raw ../web                        # stage 2: 30 m landing zones for Jezero and the Moon regions
python 09b_stage2_validation.py ../web ../raw            # stage 2 checked against the validation sites
```

`pipeline/targets.json` lists the Moon and Mars targets with sources; `pipeline/known_sites.json` lists the 107 known analog sites; `pipeline/earth_sites_validation.csv` is the analog / non-analog validation set.

## References and data

* AWS Terrain Tiles (Mapzen terrarium), registry.opendata.aws/terrain-tiles
* NASA POWER climatology (MERRA-2, CERES SYN1deg), power.larc.nasa.gov, AWS Open Data
* ESA WorldCover 2021 v200 (Zanaga et al. 2022)
* Natural Earth 1:10m vectors
* NASA Blue Marble (Visible Earth), via the three-globe example images, desaturated for the globe
* Natural Earth 1:10m shaded relief (SR_HR), public domain, multiplied into the 8k globe
* SELENE (Kaguya) Terrain Camera ortho mosaic 64 ppd, JAXA / USGS Astrogeology (Moon on the choice screen)
* Newsreader typeface, Production Type, SIL Open Font License 1.1
* MGS MOLA global DEM 463 m, MGS TES albedo, LRO LOLA south pole DEM 30 m, LROC WAC south pole mosaic 100 m: USGS Astrogeology Science Center / NASA PDS
* LRO Diviner polar resource product (dlre_prp_south), NASA PDS Geosciences Node; Paige et al. 2010, Science 330
* Fortezzo, Spudis & Harrel 2020, Unified Geologic Map of the Moon 1:5M, USGS
* JAXA Earth API: GCOM-C SGLI L3 land surface temperature (G-Portal), GSMaP gauge-adjusted precipitation normal (EORC), MODIS NDVI normal (JASMES), AMSR2 soil moisture (tested)
* Hartmann & Moosdorf 2012, GLiM, Geochem. Geophys. Geosyst. 13, doi:10.1594/PANGAEA.788537
* Copernicus Sentinel-2 cloudless by EOX (CC BY-NC-SA 4.0); NASA GIBS Blue Marble and VIIRS Black Marble (live, in the detail card)
* Cushing et al. 2007, Mars cave skylights on Arsia Mons (NASA PIA09929)
* NASA Artemis III candidate regions (2024); Wueller et al. 2026, JGR Planets, doi:10.1029/2025JE009434; Boazman et al. 2022, Planet. Sci. J. 3:275
* NASA Planetary Analog Explorer; Foucher et al. 2021, Planet. Space Sci. 197:105162; Wikipedia "Terrestrial analogue site"
* Hassler et al. 2014, Science 343 (Curiosity RAD); Zhang et al. 2020, Sci. Adv. 6 (Chang'e-4 LND); Williams et al. 2019 (Diviner polar temperatures); Morgan et al. 2021, Nature Astronomy (SWIM)

## License

Code: MIT. Data products inherit the licences of their sources (all open).
