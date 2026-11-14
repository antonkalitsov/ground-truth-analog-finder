"""Download every raw input the pipeline needs into analog-finder/raw/ (about 6 GB, all public, no keys).
Safe to re-run: files that already exist are skipped, so an interrupted download just resumes on the next run.
Usage (from pipeline/): python get_data.py ../raw
The pipeline steps that download their own data (01, 02, 04) and the official challenge datasets
(fetch_official.py: LRO Diviner, JAXA Earth API, GLiM) are run by rebuild.py, not here.
"""
import os, sys, urllib.request, zipfile

raw = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "../raw")
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
ASTRO = "https://asc-astropedia.s3.us-west-2.amazonaws.com/"
FILES = [
    # (url, path inside raw/)
    ("https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif", "mars_mola_463m.tif"),     # 2.1 GB
    ("https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif", "mars_tes_albedo.tif"),  # 17 MB
    (ASTRO + "Moon/LRO/LOLA/ancillary/LRO_LOLA_DEM_SPole75_30m.tif", "moon_lola_spole75_30m.tif"),                 # 2.1 GB
    (ASTRO + "Moon/LRO/LROC_WAC/ancillary/LRO_WAC_Mosaic_SPole60_100m_v2.jp2", "lro/wac_spole60_100m.jp2"),        # 190 MB
    (ASTRO + "Moon/Geology/Ancillary/unified_geologic_map_of_the_moon_raster.zip", "lro/unified_geologic_map_of_the_moon_raster.zip"),
    ("https://naciscdn.org/naturalearth/10m/raster/SR_HR.zip", "ne_hr_dl/SR_HR.zip"),                              # 44 MB
    ("https://unpkg.com/three-globe@2.31.0/example/img/earth-blue-marble.jpg", "earth_orig.jpg"),
] + [(NE + n + ".geojson", "ne/" + n + ".geojson") for n in (
    "ne_10m_land", "ne_10m_lakes", "ne_10m_antarctic_ice_shelves_polys", "ne_10m_glaciated_areas",
    "ne_10m_admin_0_countries", "ne_10m_admin_1_states_provinces", "ne_10m_geography_regions_polys")]


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print("  have", os.path.relpath(path, raw)); return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("  get ", os.path.relpath(path, raw), "<-", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ground-truth-pipeline"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or 0); done = 0; step = 1 << 20
        while chunk := r.read(step):
            f.write(chunk); done += len(chunk)
            if total > 50 * step and done % (100 * step) < step:
                print(f"        {done >> 20} / {total >> 20} MB", flush=True)
    os.replace(path + ".part", path)


def main():
    print("Downloading raw data into", raw)
    failed = []
    for url, rel in FILES:
        try:
            download(url, os.path.join(raw, rel))
        except Exception as e:
            print("  FAILED", rel, type(e).__name__, e); failed.append(rel)
    gz = os.path.join(raw, "lro", "unified_geologic_map_of_the_moon_raster.zip")
    if os.path.exists(gz) and not os.path.isdir(os.path.join(raw, "lro", "Unified_Geologic_Map_of_the_Moon_RASTER")):
        zipfile.ZipFile(gz).extractall(os.path.join(raw, "lro")); print("  unzipped lunar geologic map")
    if failed:
        sys.exit("Some downloads failed (re-run to retry): " + ", ".join(failed))
    print("Raw data complete.")


if __name__ == "__main__":
    main()
