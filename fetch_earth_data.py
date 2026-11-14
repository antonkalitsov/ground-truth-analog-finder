"""Fetch Earth data for every site in data/earth_sites.csv.

For each site it downloads:
  - a ~10 x 10 km elevation tile (Copernicus GLO-90; global, incl. polar sites).
    Source: the free AWS Open Data mirror (no key, no daily limit).
    OpenTopography (50 calls/day) is only used with --opentopo.
  - NASA POWER climatology (temperature, precipitation, humidity, surface albedo)

Run from "D:\\NASA APP":   python fetch_earth_data.py
Needs: pip install requests rasterio   (OPENTOPO_API_KEY in .env only for --opentopo)
Safe to re-run: files that already exist are skipped.
"""
import csv, json, math, os, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
SITES = ROOT / "data" / "earth_sites.csv"
DEM_DIR = ROOT / "data" / "raw" / "earth_dem"
POWER_DIR = ROOT / "data" / "raw" / "earth_power"
TILE_DIR = ROOT / "data" / "raw" / "cop90_tiles"
AWS = "https://copernicus-dem-90m.s3.amazonaws.com"
HALF_KM = 5.0  # half window size -> 10 x 10 km


def load_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("OPENTOPO_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENTOPO_API_KEY missing from .env")


def slug(name):
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


def bbox(lat, lon):
    dlat = HALF_KM / 111.0
    dlon = HALF_KM / (111.0 * max(math.cos(math.radians(lat)), 0.05))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def fetch_dem(site, key):
    out = DEM_DIR / f"{slug(site['name'])}.tif"
    if out.exists() and out.stat().st_size > 1000:
        return "skip"
    s, n, w, e = bbox(float(site["lat"]), float(site["lon"]))
    r = requests.get("https://portal.opentopography.org/API/globaldem", params={
        "demtype": "COP90", "south": s, "north": n, "west": w, "east": e,
        "outputFormat": "GTiff", "API_Key": key}, timeout=120)
    if r.status_code != 200 or r.content[:4] not in (b"II*\x00", b"MM\x00*"):
        return f"FAILED ({r.status_code}): {r.text[:120]}"
    out.write_bytes(r.content)
    return f"{len(r.content)//1024} KB"


def tile_name(lat_floor, lon_floor):
    ns = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{-lat_floor:02d}"
    ew = f"E{lon_floor:03d}" if lon_floor >= 0 else f"W{-lon_floor:03d}"
    return f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"


def get_tile(lat_floor, lon_floor):
    name = tile_name(lat_floor, lon_floor)
    path = TILE_DIR / f"{name}.tif"
    if path.exists():
        return path
    r = requests.get(f"{AWS}/{name}/{name}.tif", timeout=300)
    if r.status_code == 404:
        return None  # ocean-only tile, no data
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def fetch_dem_aws(site):
    out = DEM_DIR / f"{slug(site['name'])}.tif"
    if out.exists() and out.stat().st_size > 1000:
        return "skip"
    import rasterio
    from rasterio.merge import merge
    s, n, w, e = bbox(float(site["lat"]), float(site["lon"]))
    tiles = []
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            try:
                t = get_tile(la, lo)
            except Exception as ex:
                return f"FAILED: {ex}"
            if t:
                tiles.append(rasterio.open(t))
    if not tiles:
        return "FAILED: no land tile"
    mosaic, transform = merge(tiles, bounds=(w, s, e, n))
    meta = tiles[0].meta.copy()
    meta.update(driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2], transform=transform, compress="deflate")
    for t in tiles:
        t.close()
    with rasterio.open(out, "w", **meta) as dst:
        dst.write(mosaic)
    return f"{out.stat().st_size//1024} KB (aws)"


def fetch_power(site):
    out = POWER_DIR / f"{slug(site['name'])}.json"
    if out.exists():
        return "skip"
    r = requests.get("https://power.larc.nasa.gov/api/temporal/climatology/point", params={
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SRF_ALB",
        "community": "RE", "longitude": site["lon"], "latitude": site["lat"],
        "format": "JSON"}, timeout=120)
    if r.status_code != 200:
        return f"FAILED ({r.status_code})"
    out.write_text(json.dumps(r.json()))
    return "ok"


def main():
    use_opentopo = "--opentopo" in sys.argv
    key = load_key() if use_opentopo else None
    TILE_DIR.mkdir(parents=True, exist_ok=True)
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    POWER_DIR.mkdir(parents=True, exist_ok=True)
    sites = list(csv.DictReader(open(SITES, encoding="utf-8")))
    failed = 0
    for i, site in enumerate(sites, 1):
        dem = fetch_dem(site, key) if use_opentopo else fetch_dem_aws(site)
        pwr = fetch_power(site)
        failed += ("FAILED" in dem) + ("FAILED" in pwr)
        print(f"[{i:2}/{len(sites)}] {site['name'][:38]:38}  dem: {dem:12}  power: {pwr}")
        time.sleep(0.5)  # be polite to the APIs
    print(f"\nDone. {failed} failures. Re-run to retry only the failed ones.")


if __name__ == "__main__":
    main()
