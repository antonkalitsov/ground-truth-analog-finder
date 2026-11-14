# Ground Truth: findings

Every land cell on Earth (318,332 cells of 0.25 degrees, about 28 km) was scored against each Moon and Mars target.
Scores are 0 to 100: the weighted mean of per-trait similarities. 'New' means more than 150 km from all 107 catalogued analog sites.

## Validation

For each body, every land cell gets its best score over all targets (Overall preset). We then check where known analog sites fall.
Clear non-analogs are 26 hand-picked places: rainforest, farmland, cities, wetlands, taiga, the Greenland ice sheet. Desert and dune 'look-alikes' are left out because they are partial analogs by design.

| Target body | Environment analogs vs non-analogs (AUC) | Geology-only analogs vs non-analogs (AUC) | All 107 catalogued sites: median percentile | In Earth's top 10% |
|---|---|---|---|---|
| Mars | 0.75 (13 vs 26) | 0.60 (15 vs 26) | 74th (92 sites) | 32% |
| Moon | 0.82 (5 vs 26) | 0.70 (13 vs 26) | 68th (39 sites) | 18% |

AUC is the chance that a random analog outscores a random non-analog (0.5 = coin flip, 1.0 = perfect). Nothing was tuned on these sites.
Analogs chosen for their environment and terrain (deserts, polar sites, dry lava fields) are recognised best. Analogs chosen mainly for their rocks (wet volcanic islands, impact craters in farmland) score lower. The GLiM rock map is 0.5 degree and mostly sees sedimentary cover, so rock type adds little here; telling clays and sulfates apart would need imaging spectroscopy (for example NASA EMIT or ASTER), the natural next layer.

### What each official challenge dataset added

| Step | Mars AUC (environment / geology) | Moon AUC (environment / geology) |
|---|---|---|
| Before official resources (MERRA-2 / NASA POWER climate, latitude model for Moon) | 0.72 / 0.57 | 0.75 / 0.67 |
| + JAXA GCOM-C LST swing, JAXA GSMaP rain, LRO Diviner Moon temperature and ice, USGS lunar geologic map | 0.72 / 0.63 | 0.78 / 0.69 |
| + JAXA JASMES MODIS NDVI (biology) | 0.74 / 0.63 | 0.82 / 0.71 |
| + GLiM rock type at weight 1 (USGS lunar map and Mars site geology on the target side) (rejected) | 0.75 / 0.58 | 0.79 / 0.69 |
| + GLiM rock type at weight 0.25 in the Overall preset (kept; full weight in Instruments and ISRU) | 0.75 / 0.60 | 0.82 / 0.70 |
| JAXA AMSR2 soil moisture instead of MERRA-2 (rejected) | 0.75 / 0.59 | 0.77 / 0.63 |

JAXA AMSR2 soil moisture was dropped: its retrieval reads high over sand seas (Sahara about 10-14 %) and is invalid under forest, and swapping it in lowered every geology AUC.

## Shackleton rim / Connecting Ridge (Moon), preset: Polar base operations

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Nationalparken, Greenland (NORTH AMERICA) | 82.88, -33.62 | 69 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, dust / aerosol | surface albedo, day-night swing, mean wind, rock type | Bockfjorden volcanic complex, Svalbard (857 km) |
| 2 | Nunavut, Canada (ARCTIC ARCHIPELAGO) | 82.88, -77.88 | 69 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, dust / aerosol | surface albedo, day-night swing, precipitation, rock type | Gypsum Hill springs, Axel Heiberg Island (441 km) |
| 3 | Nationalparken, Greenland (NORTH AMERICA) | 82.12, -54.38 | 66 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, dust / aerosol | surface albedo, day-night swing, mean wind, rock type | Gypsum Hill springs, Axel Heiberg Island (700 km) |
| 4 | Nunavut, Canada (ARCTIC ARCHIPELAGO) | 79.62, -81.62 | 64 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, dust / aerosol | surface albedo, day-night swing, precipitation, plant greenness (ndvi), rock type | Gypsum Hill springs, Axel Heiberg Island (186 km) |
| 5 | Antarctica, Antarctica (Transantarctic Mountains) | -84.12, 168.12 | 63 | mean slope, roughness, local relief, mean temperature, noon sun elevation, dust / aerosol | surface albedo, barren ground, ice / snow cover, day-night swing, mean wind | University Valley (707 km) |

Best-ranked known analog for this target: Lost Hammer spring, Axel Heiberg Island (99.9th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean slope, Roughness, Local relief, Mean temperature, Day-night swing, Noon sun elevation, Precipitation, Mean wind, Plant greenness (NDVI). Never reproducible: gravity (1.62 m/s2), vacuum or thin air, surface radiation.

## de Gerlache Rim 2 (Moon), preset: Polar base operations

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Nationalparken, Greenland (NORTH AMERICA) | 82.88, -33.62 | 74 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, dust / aerosol | surface albedo, day-night swing, mean wind, rock type | Bockfjorden volcanic complex, Svalbard (857 km) |
| 2 | Nunavut, Canada (ARCTIC ARCHIPELAGO) | 82.88, -77.88 | 73 | mean slope, roughness, local relief, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, dust / aerosol | surface albedo, day-night swing, precipitation, rock type | Gypsum Hill springs, Axel Heiberg Island (441 km) |
| 3 | Nationalparken, Greenland (NORTH AMERICA) | 82.12, -54.38 | 70 | mean slope, local relief, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, dust / aerosol | roughness, surface albedo, day-night swing, mean wind, rock type | Gypsum Hill springs, Axel Heiberg Island (700 km) |
| 4 | Nunavut, Canada (ARCTIC ARCHIPELAGO) | 80.12, -71.88 | 68 | mean slope, roughness, local relief, ice / snow cover, noon sun elevation, ground ice likelihood, dust / aerosol | surface albedo, day-night swing, rock type | Gypsum Hill springs, Axel Heiberg Island (379 km) |
| 5 | Antarctica, Antarctica (Transantarctic Mountains) | -83.88, 168.12 | 68 | mean slope, roughness, local relief, mean temperature, noon sun elevation, ground ice likelihood, dust / aerosol | surface albedo, barren ground, ice / snow cover, day-night swing, mean wind | University Valley (680 km) |

Best-ranked known analog for this target: Lost Hammer spring, Axel Heiberg Island (99.9th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean slope, Local relief, Mean temperature, Day-night swing, Noon sun elevation, Precipitation, Mean wind, Plant greenness (NDVI). Never reproducible: gravity (1.62 m/s2), vacuum or thin air, surface radiation.

## Malapert Massif (Moon), preset: Overall analog

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Coquimbo, Argentina (SOUTH AMERICA) | -30.12, -69.88 | 70 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, dust / aerosol | mean temperature, noon sun elevation, mean wind, rock type | Laguna Negra, Puna (304 km) |
| 2 | Xizang, China (ASIA) | 33.12, 79.88 | 66 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture | surface albedo, mean temperature, noon sun elevation, mean wind, plant greenness (ndvi) | Tso Kar, Ladakh (176 km) |
| 3 | Atacama, Chile (SOUTH AMERICA) | -26.62, -69.62 | 66 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, precipitation, soil moisture, dust / aerosol | mean temperature, noon sun elevation, ground ice likelihood, mean wind, rock type | Laguna Negra, Puna (156 km) |
| 4 | Xinjiang, China (ASIA) | 38.88, 74.38 | 65 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood | surface albedo, mean temperature, noon sun elevation, dust / aerosol, rock type | Tso Kar, Ladakh (700 km) |
| 5 | Tarapacá, Chile (SOUTH AMERICA) | -19.12, -69.88 | 65 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, precipitation, soil moisture | mean temperature, noon sun elevation, ground ice likelihood, rock type | Salar Grande (203 km) |

Best-ranked known analog for this target: Salar Grande (100.0th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean slope, Roughness, Local relief, Mean temperature, Day-night swing, Noon sun elevation, Precipitation, Soil moisture, Mean wind, Plant greenness (NDVI). Never reproducible: gravity (1.62 m/s2), vacuum or thin air, surface radiation.

## Slater Plain (Moon), preset: Rover & landing tests

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Lima Province, Peru (SOUTH AMERICA) | -12.38, -76.62 | 79 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, soil moisture, rock type | mean temperature, noon sun elevation, ground ice likelihood, dust / aerosol, plant greenness (ndvi) | Pampas de La Joya (704 km) |
| 2 | Arequipa, Peru (SOUTH AMERICA) | -15.38, -74.62 | 78 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, soil moisture, rock type | mean temperature, noon sun elevation, ground ice likelihood, mean wind | Pampas de La Joya (329 km) |
| 3 | Catamarca, Argentina (SOUTH AMERICA) | -25.12, -68.62 | 77 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, soil moisture, dust / aerosol | mean temperature, noon sun elevation, ground ice likelihood, mean wind, rock type | Yungay, Atacama Desert (181 km) |
| 4 | Qinghai, China (ASIA) | 36.12, 95.38 | 77 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, soil moisture | surface albedo, mean temperature, noon sun elevation, ground ice likelihood, dust / aerosol, mean wind | Lenghu (Mars Camp), Qaidam Basin (345 km) |
| 5 | Atacama, Chile (SOUTH AMERICA) | -28.12, -70.12 | 77 | mean slope, roughness, local relief, ice / snow cover, day-night swing, precipitation, soil moisture, dust / aerosol | mean temperature, noon sun elevation, ground ice likelihood, plant greenness (ndvi), rock type | Laguna Negra, Puna (164 km) |

Best-ranked known analog for this target: Licancabur (100.0th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Noon sun elevation, Precipitation, Soil moisture, Mean wind, Plant greenness (NDVI). Never reproducible: gravity (1.62 m/s2), vacuum or thin air, surface radiation.

## Haworth (Moon), preset: Ice prospecting & ISRU

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Xinjiang, China (ASIA) | 37.38, 87.12 | 69 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture | surface albedo, mean temperature, noon sun elevation, dust / aerosol, mean wind, rock type | Dalangtan playa, Qaidam Basin (423 km) |
| 2 | Xizang, China (ASIA) | 33.12, 79.62 | 68 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture | surface albedo, mean temperature, noon sun elevation, mean wind | Tso Kar, Ladakh (152 km) |
| 3 | Xinjiang, China (ASIA) | 35.88, 81.88 | 68 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture | surface albedo, mean temperature, noon sun elevation, dust / aerosol, mean wind, rock type | Tso Kar, Ladakh (456 km) |
| 4 | Nunavut, Canada (ARCTIC ARCHIPELAGO) | 81.38, -71.38 | 68 | mean slope, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, dust / aerosol | surface albedo, day-night swing, rock type | Gypsum Hill springs, Axel Heiberg Island (417 km) |
| 5 | Badakhshan, Afghanistan (ASIA) | 37.38, 72.88 | 67 | mean slope, roughness, local relief, ice / snow cover, ground ice likelihood | surface albedo, mean temperature, noon sun elevation | Tso Kar, Ladakh (649 km) |

Best-ranked known analog for this target: Tso Kar, Ladakh (99.8th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean slope, Local relief, Mean temperature, Day-night swing, Noon sun elevation, Precipitation, Soil moisture, Mean wind, Plant greenness (NDVI). Never reproducible: gravity (1.62 m/s2), vacuum or thin air, surface radiation.

## Jezero crater (Perseverance) (Mars), preset: Overall analog

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Borkou, Chad (AFRICA) | 20.62, 18.12 | 80 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, precipitation, soil moisture | mean temperature, dust / aerosol, rock type | Gilf Kebir, Western Desert (862 km) |
| 2 | Al Bahr al Ahmar, Egypt (AFRICA) | 22.12, 35.62 | 79 | mean slope, roughness, surface albedo, barren ground, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, precipitation, soil moisture | mean temperature, dust / aerosol | Wadi Rum (828 km) |
| 3 | Red Sea, Sudan (AFRICA) | 18.38, 37.12 | 79 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, precipitation, soil moisture, mean wind | mean temperature, plant greenness (ndvi) | Dallol, Danakil Depression (571 km) |
| 4 | Arica y Parinacota, Chile (SOUTH AMERICA) | -18.88, -70.12 | 79 | mean slope, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, precipitation, soil moisture | mean temperature, dust / aerosol | Salar Grande (231 km) |
| 5 | Atacama, Chile (SOUTH AMERICA) | -25.88, -69.88 | 76 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture | mean temperature, dust / aerosol, plant greenness (ndvi) | Yungay, Atacama Desert (198 km) |

Best-ranked known analog for this target: Yungay, Atacama Desert (99.9th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Gale crater (Curiosity) (Mars), preset: Rover & landing tests

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Borkou, Chad (AFRICA) | 19.88, 18.38 | 83 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture, mean wind | mean temperature, dust / aerosol, rock type | Gilf Kebir, Western Desert (876 km) |
| 2 | Yazd, Iran (ASIA) | 32.62, 54.62 | 78 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture | mean temperature, noon sun elevation, dust / aerosol | Dhofar desert (AMADEE-18) (1526 km) |
| 3 | Tadjourah, Djibouti (AFRICA) | 11.62, 42.62 | 76 | mean slope, roughness, local relief, ice / snow cover, noon sun elevation, ground ice likelihood, soil moisture, mean wind | surface albedo, mean temperature, precipitation, plant greenness (ndvi), rock type | Dallol, Danakil Depression (385 km) |
| 4 | Sistan and Baluchestan, Iran (ASIA) | 29.62, 59.88 | 76 | roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind | surface albedo, mean temperature, noon sun elevation, dust / aerosol | Matanomadh, Kutch (1129 km) |
| 5 | Al Mahrah, Yemen (ASIA) | 15.38, 51.38 | 76 | roughness, local relief, surface albedo, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, precipitation, soil moisture | mean temperature, plant greenness (ndvi) | Dhofar desert (AMADEE-18) (507 km) |

Best-ranked known analog for this target: Badwater Basin, Death Valley (100.0th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Local relief, Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Utopia Planitia (Viking 2) (Mars), preset: Ice prospecting & ISRU

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Xinjiang, China (ASIA) | 37.12, 87.12 | 66 | surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture, mean wind | mean slope, roughness, local relief, mean temperature, noon sun elevation, dust / aerosol | Dalangtan playa, Qaidam Basin (434 km) |
| 2 | Xizang, China (ASIA) | 34.12, 84.62 | 64 | mean slope, roughness, barren ground, ice / snow cover, day-night swing, ground ice likelihood, mean wind | local relief, mean temperature, noon sun elevation, dust / aerosol, plant greenness (ndvi), rock type | Tso Kar, Ladakh (619 km) |
| 3 | Xinjiang, China (ASIA) | 34.88, 79.12 | 62 | mean slope, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, mean wind | roughness, local relief, mean temperature, noon sun elevation, dust / aerosol, rock type | Tso Kar, Ladakh (203 km) |
| 4 | Gorno-Badakhshan, Tajikistan (ASIA) | 38.62, 74.12 | 60 | surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture | mean slope, roughness, local relief, mean temperature, noon sun elevation, dust / aerosol, rock type | Tso Kar, Ladakh (687 km) |
| 5 | Xizang, China (ASIA) | 32.12, 80.62 | 59 | barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind | mean slope, roughness, local relief, mean temperature, noon sun elevation, dust / aerosol, plant greenness (ndvi), rock type | Tso Kar, Ladakh (278 km) |

Best-ranked known analog for this target: Tso Kar, Ladakh (98.9th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Arcadia Planitia (SpaceX Starship candidate) (Mars), preset: Ice prospecting & ISRU

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Xinjiang, China (ASIA) | 37.12, 87.62 | 75 | surface albedo, barren ground, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, precipitation, soil moisture, mean wind, rock type | local relief, mean temperature, dust / aerosol | Dalangtan playa, Qaidam Basin (393 km) |
| 2 | Xinjiang, China (ASIA) | 35.88, 84.12 | 72 | mean slope, roughness, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind, rock type | local relief, mean temperature, dust / aerosol | Tso Kar, Ladakh (629 km) |
| 3 | Xinjiang, China (ASIA) | 34.88, 79.38 | 71 | mean slope, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind, rock type | mean temperature, dust / aerosol | Tso Kar, Ladakh (216 km) |
| 4 | Xinjiang, China (ASIA) | 36.38, 90.88 | 69 | mean slope, roughness, surface albedo, barren ground, ice / snow cover, ground ice likelihood, mean wind, rock type | local relief, mean temperature, dust / aerosol | Dalangtan playa, Qaidam Basin (258 km) |
| 5 | Qinghai, China (ASIA) | 38.88, 95.62 | 66 | surface albedo, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, rock type | mean slope, roughness, local relief, mean temperature, dust / aerosol | Lenghu (Mars Camp), Qaidam Basin (202 km) |

Best-ranked known analog for this target: Gilf Kebir, Western Desert (99.7th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Meridiani Planum (Opportunity) (Mars), preset: Instrument & remote sensing

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Makkah, Saudi Arabia (ASIA) | 23.12, 38.88 | 78 | mean slope, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture | mean temperature, noon sun elevation, dust / aerosol | Wadi Rum (795 km) |
| 2 | Ash Sharqiyah South, Oman (ASIA) | 21.62, 59.38 | 78 | mean slope, roughness, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind | mean temperature, noon sun elevation | Dhofar desert (AMADEE-18) (601 km) |
| 3 | Abyan, Yemen (ASIA) | 13.62, 47.12 | 75 | mean slope, roughness, surface albedo, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, precipitation, mean wind | local relief, mean temperature | Dallol, Danakil Depression (740 km) |
| 4 | Tabuk, Saudi Arabia (ASIA) | 25.88, 36.88 | 74 | mean slope, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture, mean wind | roughness, mean temperature, noon sun elevation, dust / aerosol | Wadi Rum (435 km) |
| 5 | Hormozgan, Iran (ASIA) | 25.62, 58.88 | 73 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture | mean temperature, noon sun elevation | Dhofar desert (AMADEE-18) (878 km) |

Best-ranked known analog for this target: Dallol, Danakil Depression (100.0th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Green Valley (Phoenix) (Mars), preset: Ice prospecting & ISRU

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Xinjiang, China (ASIA) | 35.62, 84.12 | 76 | mean slope, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind, rock type | mean temperature, noon sun elevation, dust / aerosol | Tso Kar, Ladakh (618 km) |
| 2 | Xinjiang, China (ASIA) | 34.88, 79.12 | 75 | mean slope, roughness, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, mean wind, rock type | mean temperature, noon sun elevation, dust / aerosol | Tso Kar, Ladakh (203 km) |
| 3 | Xizang, China (ASIA) | 36.12, 88.12 | 73 | mean slope, local relief, barren ground, ice / snow cover, ground ice likelihood, soil moisture, mean wind, rock type | roughness, mean temperature, day-night swing, noon sun elevation, dust / aerosol | Dalangtan playa, Qaidam Basin (419 km) |
| 4 | Qinghai, China (ASIA) | 38.38, 97.12 | 65 | surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, mean wind, rock type | roughness, mean temperature, noon sun elevation, precipitation, dust / aerosol, plant greenness (ndvi) | Lenghu (Mars Camp), Qaidam Basin (335 km) |
| 5 | Nationalparken, Greenland (NORTH AMERICA) | 81.62, -60.88 | 64 | barren ground, ice / snow cover, ground ice likelihood, mean wind | roughness, surface albedo, day-night swing, noon sun elevation, dust / aerosol | Gypsum Hill springs, Axel Heiberg Island (591 km) |

Best-ranked known analog for this target: Haughton impact crater, Devon Island (99.5th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

## Melas Chasma (Valles Marineris) (Mars), preset: Crew & EVA training

| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |
|---|---|---|---|---|---|---|
| 1 | Borkou, Chad (AFRICA) | 19.88, 18.38 | 70 | mean slope, local relief, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture, mean wind | surface albedo, mean temperature, dust / aerosol, rock type | Gilf Kebir, Western Desert (876 km) |
| 2 | Sistan and Baluchestan, Iran (ASIA) | 29.62, 59.88 | 68 | mean slope, local relief, surface albedo, barren ground, ice / snow cover, day-night swing, ground ice likelihood, soil moisture, mean wind | mean temperature, noon sun elevation, dust / aerosol | Matanomadh, Kutch (1129 km) |
| 3 | Abyan, Yemen (ASIA) | 13.62, 46.12 | 68 | roughness, surface albedo, barren ground, ice / snow cover, noon sun elevation, ground ice likelihood, precipitation, soil moisture | local relief, mean temperature, plant greenness (ndvi), rock type | Dallol, Danakil Depression (632 km) |
| 4 | Ica, Peru (SOUTH AMERICA) | -14.38, -75.38 | 68 | mean slope, local relief, barren ground, ice / snow cover, day-night swing, noon sun elevation, ground ice likelihood, precipitation, soil moisture | mean temperature, dust / aerosol, plant greenness (ndvi), rock type | Pampas de La Joya (456 km) |
| 5 | Atacama, Chile (SOUTH AMERICA) | -25.88, -69.38 | 67 | mean slope, barren ground, ice / snow cover, day-night swing, ground ice likelihood, precipitation, soil moisture, mean wind | mean temperature, noon sun elevation, dust / aerosol, plant greenness (ndvi) | Yungay, Atacama Desert (208 km) |

Best-ranked known analog for this target: El Tatio (100.0th percentile).
Beyond anything on Earth (ranked toward Earth's most extreme places): Mean temperature, Day-night swing, Precipitation, Soil moisture, Plant greenness (NDVI). Never reproducible: gravity (3.71 m/s2), vacuum or thin air, surface radiation.

