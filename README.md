# Ground Truth: Earth analog finder

Ground Truth is our NASA Space Apps Challenge 2026 project for the challenge "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars".

It scores every land cell on Earth (318,332 cells of 0.25 degrees, about 28 km) against a chosen place on the Moon or Mars. It ranks the best matches and flags new candidates that are far from every catalogued analog site. For each match it explains where the analogy holds, where it breaks down and how the site could help exploration. The data comes from NASA (LRO, MGS, POWER, Blue Marble), JAXA (GCOM-C, GSMaP, JASMES), ESA (WorldCover), USGS Astrogeology and Natural Earth.

The method, data sources, validation and limitations are written up in [analog-finder/README.md](analog-finder/README.md). The results are in [analog-finder/FINDINGS.md](analog-finder/FINDINGS.md).

## Quick start (about 2 minutes)

The repository already contains the built data pack, so the app runs straight after cloning. Python is the only requirement, and it is used only to serve the files.

1. Install **Python 3.10 or newer** from https://www.python.org/downloads/. On Windows, tick "Add python.exe to PATH" in the installer.
2. Clone the repository:

   ```
   git clone https://github.com/antonkalitsov/ground-truth-analog-finder.git
   cd ground-truth-analog-finder
   ```

3. Start the app:
   - **Windows:** double-click `setup.bat`, or run `setup.bat` in a terminal.
   - **Mac or Linux:** run `sh setup.sh`.
4. Your browser opens http://localhost:8000. If it does not, open that address yourself. Close the terminal window (or press Ctrl+C) to stop the app.

The app must be served over http rather than opened as a file, because the browser loads the data pack with `fetch`. Scoring works offline. Only the live Earth terrain close-ups and satellite views need the internet.

## Full rebuild from raw data (optional, a few hours)

You only need this to change the scoring inputs or reproduce the data pack from scratch. The script downloads about 6 GB of public data (no accounts or API keys), runs the processing pipeline and then starts the app.

You need Python 3.10 or newer, about 8 GB of free disk space and a steady internet connection.

- **Windows:** `setup.bat rebuild`
- **Mac or Linux:** `sh setup.sh rebuild`

The script does the following:

1. Creates a Python virtual environment in `.venv/` and installs the packages in [analog-finder/requirements.txt](analog-finder/requirements.txt) (numpy, rasterio, pillow, zarr, numcodecs, jaxa-earth).
2. Runs [analog-finder/pipeline/rebuild.py](analog-finder/pipeline/rebuild.py), which:
   - downloads the Mars and Moon elevation models, the LROC WAC south pole mosaic, the USGS lunar geologic map, Natural Earth vectors and shaded relief, and the Blue Marble image into `analog-finder/raw/` (`pipeline/get_data.py`)
   - downloads 16,384 Earth elevation tiles, NASA POWER climatology and ESA WorldCover (steps 01, 02 and 04)
   - fetches the official challenge datasets: LRO Diviner from NASA PDS, JAXA GCOM-C, GSMaP and MODIS NDVI through the JAXA Earth API, and the GLiM rock map (`analog-finder/fetch_official.py`)
   - runs pipeline steps 03 to 08, which write the data pack to `analog-finder/web/data/` and regenerate `FINDINGS.md`
3. Starts the app.

If the rebuild is interrupted or one download fails, run the same command again. Files that are already downloaded and slow steps that already finished are skipped. To start over completely, delete `analog-finder/raw/`.

The individual steps and their arguments are listed under "Rebuild the data" in [analog-finder/README.md](analog-finder/README.md).

## Repository layout

| Path | What it is |
|---|---|
| `setup.bat`, `setup.sh` | One-command start (and `rebuild`) for Windows and Mac/Linux |
| `analog-finder/web/` | The app: plain HTML, CSS and JavaScript modules, no build step, plus the prebuilt data pack in `web/data/` |
| `analog-finder/start.bat`, `analog-finder/start.sh` | Serve `web/` at http://localhost:8000 |
| `analog-finder/pipeline/` | Python scripts `01_` to `08_` that build the data pack, plus `get_data.py` and `rebuild.py` that run the whole chain |
| `analog-finder/pipeline/targets.json` | Moon and Mars target sites, with sources |
| `analog-finder/pipeline/known_sites.json` | The 107 catalogued Earth analog sites, with sources |
| `analog-finder/fetch_official.py` | Fetches the official challenge datasets (LRO Diviner, JAXA, GLiM) |
| `analog-finder/FINDINGS.md` | Validation results and candidates per target |
| `data/` | Site lists from early exploration (`earth_sites.csv`, `validation_pairs.csv`) |
| `download_data.ps1`, `fetch_earth_data.py`, `fetch_official.py` (top level) | Earlier data scripts from the exploration phase. The current pipeline does not need them |

Downloaded data (`analog-finder/raw/`, `data/raw/`, `data/official/*.npz`) is not stored in git. The rebuild re-creates it.

## Deploying

The `analog-finder/web` folder is a static site. To share a live link, publish that folder on any static host, such as GitHub Pages, Netlify or Cloudflare Pages.

## API keys

The app and the rebuild need no keys. Two optional keys used by the earlier exploration scripts go in a local `.env` file at the repository root. That file is ignored by git, so never commit it.

```
OPENTOPO_API_KEY=your-key
CESIUM_TOKEN=your-token
```

## Troubleshooting

- **"Python was not found"** on Windows: reinstall Python and tick "Add python.exe to PATH", or disable the Microsoft Store "App execution aliases" for python.
- **Port 8000 is in use:** stop the other server, or run `python -m http.server 8080` inside `analog-finder/web` and open http://localhost:8080.
- **rasterio fails to install:** use Python 3.10 to 3.13, which have prebuilt rasterio packages, or install it with conda (`conda install -c conda-forge rasterio`).
- **The JAXA or NASA PDS step fails:** those servers are sometimes slow or blocked on some networks. Run the rebuild again later. Steps 05b and 06b fall back to the other sources when an official layer is missing.

## License

See [analog-finder/LICENSE](analog-finder/LICENSE).
