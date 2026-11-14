# Ground Truth: Earth analog finder

NASA Space Apps Challenge 2026 project. Ground Truth scores every land cell on Earth against a chosen Artemis III Moon base region or Mars site, ranks the best matches, and flags new candidates far from all catalogued analog sites.

The full write-up (method, data sources, caveats) is in [analog-finder/README.md](analog-finder/README.md).

## Run it

The app is a static site with no build step. It needs Python only to serve files.

- **Windows:** double-click `analog-finder/start.bat`, then open http://localhost:8000
- **Any system:** `cd analog-finder/web` then `python -m http.server 8000`

## Layout

| Path | What it is |
|---|---|
| `analog-finder/web/` | The app (HTML, CSS, JS, prebuilt data pack in `web/data/`) |
| `analog-finder/pipeline/` | Python scripts `01_` to `08_` that fetch source data and build the data pack, run in number order |
| `analog-finder/FINDINGS.md` | Results summary |
| `download_data.ps1`, `fetch_official.py`, `fetch_earth_data.py` | Fetch raw NASA / JAXA / ESA data into `data/` |
| `data/` | Small CSVs are committed; `data/raw/` and the large `data/official/*.npz` files are not (re-download them) |

## Secrets

API keys live in a local `.env` file that is never committed. Create your own with:

```
OPENTOPO_API_KEY=...
CESIUM_TOKEN=...
```
