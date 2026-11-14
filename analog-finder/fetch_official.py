"""Fetch the official NASA Space Apps challenge #10 datasets that are only reachable from your PC.

  1. LRO Diviner polar resource product, south (NASA PDS Geosciences): surface temperature and
     depth to stable water ice, gridded onto Analog Finder's Moon south-pole grid.
  2. JAXA G-Portal products through the JAXA Earth API (open, no login):
       GCOM-C SGLI land surface temperature, day and night, monthly 2023  -> Earth day-night swing
       GSMaP precipitation normal 2012-2021                                -> Earth dryness
       GCOM-W AMSR2 soil moisture normal 2012-2021                         -> Earth soil moisture
       MODIS NDVI normal 2012-2021 (JASMES)                                -> Earth biology / vegetation
     All at 0.25 degree (4 pixels per degree), the same as Analog Finder's Earth grid.

Run from "D:\\NASA APP":
    & "$HOME\\analog-env\\Scripts\\python.exe" -m pip install jaxa-earth
    & "$HOME\\analog-env\\Scripts\\python.exe" fetch_official.py

Outputs go to data\\official\\ (small .npz files, about 30 MB in total). The raw Diviner table
(605 MB) is kept in data\\raw\\diviner\\ so a rerun does not download it again.
Each part is independent: if one fails the others still run. Rerun to retry only what is missing.
"""
import os, sys, time, json, urllib.request
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw", "diviner")
OUT = os.path.join(HERE, "data", "official")
os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)
summary = {}

# --------------------------------------------------------------------------- 1. Diviner
DIV_URL = ("https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/"
           "data_derived_prp/dlre_prp_south.tab")
DIV_LBL = DIV_URL[:-4] + ".xml"
DIV_TAB = os.path.join(RAW, "dlre_prp_south.tab")
DIV_SIZE = 604_800_210

def download(url, path, size=None):
    have = os.path.getsize(path) if os.path.exists(path) else 0
    if size and have == size:
        print("  already have", os.path.basename(path)); return
    req = urllib.request.Request(url, headers={"User-Agent": "analog-finder/1.0"})
    if have: req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        mode = "ab" if (have and r.status == 206) else "wb"
        if mode == "wb": have = 0
        total = size or (have + int(r.headers.get("Content-Length", 0)))
        t0 = time.time(); done = have
        with open(path, mode) as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b); done += len(b)
                if total:
                    print(f"\r  {os.path.basename(path)} {done/1e6:7.1f}/{total/1e6:.1f} MB "
                          f"({(done-have)/1e6/max(time.time()-t0,1e-3):.1f} MB/s)", end="", flush=True)
    print()

# Analog Finder Moon grid: south polar stereographic, R=1737.4 km, 476 px of 1922.0168 m, 4 px per cell
R = 1737400.0; LEFT = -457440.0; TOP = 457440.0; P = 476; MPP = 914880.0 / P

def diviner():
    print("[1/3] LRO Diviner polar resource product (south)")
    try: download(DIV_LBL, os.path.join(RAW, "dlre_prp_south.xml"))
    except Exception as e: print("  label download failed (not needed):", e)
    download(DIV_URL, DIV_TAB, DIV_SIZE)
    with open(DIV_TAB, "r", errors="replace") as f:
        header = f.readline(); first = f.readline()
    delim = "," if "," in first else None
    names = [h.strip().strip('"').lower() for h in (header.split(",") if "," in header else header.split())]
    want = ["tri_clon", "tri_clat", "temp_avg", "temp_max", "ice_depth"]
    default = [9, 10, 12, 13, 14]
    cols = [names.index(w) if w in names else d for w, d in zip(want, default)]
    print("  header:", header.strip()[:200]); print("  using columns", dict(zip(want, cols)))
    acc = {k: np.zeros(P * P, np.float64) for k in ("tavg", "tmax", "tmin_n", "n", "ice_any", "ice_shallow", "ice_depth_sum", "ice_n")}
    tmin_col = names.index("temp_min") if "temp_min" in names else None
    use = cols + ([tmin_col] if tmin_col is not None else [])
    allv = []
    rows = 0; t0 = time.time()
    with open(DIV_TAB, "r", errors="replace") as f:
        f.readline()
        while True:
            lines = f.readlines(50 << 20)
            if not lines: break
            a = np.loadtxt(lines, delimiter=delim, usecols=use, ndmin=2)
            lon, lat, tavg, tmax, ice = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]
            rows += len(a)
            if rows <= len(a): allv.append(a[:2000])
            rho = 2 * R * np.tan(np.radians(90 + lat) / 2)
            x = rho * np.sin(np.radians(lon)); y = rho * np.cos(np.radians(lon))
            j = np.floor((x - LEFT) / MPP).astype(int); i = np.floor((TOP - y) / MPP).astype(int)
            ok = (i >= 0) & (j >= 0) & (i < P) & (j < P) & (tavg > 0) & (tavg < 500)
            idx = (i * P + j)[ok]
            acc["tavg"] += np.bincount(idx, tavg[ok], P * P)
            acc["tmax"] += np.bincount(idx, tmax[ok], P * P)
            acc["n"] += np.bincount(idx, None, P * P)
            if tmin_col is not None:
                acc["tmin_n"] += np.bincount(idx, a[ok, 5], P * P)
            iv = ice[ok]; good = iv > -900
            acc["ice_any"] += np.bincount(idx, good.astype(float), P * P)
            acc["ice_shallow"] += np.bincount(idx, (good & (iv <= 1.0)).astype(float), P * P)
            acc["ice_depth_sum"] += np.bincount(idx[good], iv[good], P * P)
            acc["ice_n"] += np.bincount(idx[good], None, P * P)
            print(f"\r  parsed {rows:,} rows ({time.time()-t0:.0f}s)", end="", flush=True)
    print()
    sample = allv[0] if allv else np.zeros((0, 5))
    out = {k: v.reshape(P, P).astype(np.float32) for k, v in acc.items()}
    np.savez_compressed(os.path.join(OUT, "diviner_prp_south_476.npz"), header=header, columns=np.array(cols),
                        has_tmin=tmin_col is not None, sample=sample.astype(np.float32), **out)
    n = acc["n"]
    summary["diviner"] = dict(rows=rows, cells_with_data=int((n > 0).sum()),
                              tavg_K=[float(np.nanmin(sample[:, 2])), float(np.nanmax(sample[:, 2]))] if len(sample) else None,
                              ice_depth_values=[float(v) for v in np.unique(np.round(sample[:, 4], 2))[:12]] if len(sample) else None)
    print("  saved data/official/diviner_prp_south_476.npz")

# --------------------------------------------------------------------------- 2. JAXA Earth API
JAXA = [
    # name, collection, band, date limits, bbox
    ("gcomc_lst_day_2023",  "JAXA.G-Portal_GCOM-C.SGLI_standard.L3-LST.daytime.v3_global_monthly",   "LST",
     ["2023-01-01T00:00:00", "2023-12-31T23:59:59"], [-180, -90, 180, 90]),
    ("gcomc_lst_night_2023", "JAXA.G-Portal_GCOM-C.SGLI_standard.L3-LST.nighttime.v3_global_monthly", "LST",
     ["2023-01-01T00:00:00", "2023-12-31T23:59:59"], [-180, -90, 180, 90]),
    ("gsmap_precip_normal", "JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_monthly-normal", "PRECIP_2012_2021",
     ["2021-01-01T00:00:00", "2021-12-31T23:59:59"], [-180, -60, 180, 60]),
    ("amsr2_soil_normal",   "JAXA.G-Portal_GCOM-W.AMSR2_standard.L3-SMC.daytime.v3_global_monthly-normal", "SMC_2012_2021",
     ["2021-01-01T00:00:00", "2021-12-31T23:59:59"], [-180, -90, 180, 90]),
    ("modis_ndvi_normal",   "JAXA.JASMES_Terra.MODIS-Aqua.MODIS_ndvi.v811_global_monthly-normal", "ndvi_2012_2021",
     ["2021-01-01T00:00:00", "2021-12-31T23:59:59"], [-180, -90, 180, 90]),
]

def jaxa():
    print("[2/3] JAXA Earth API (G-Portal / EORC / JASMES products)")
    try:
        from jaxa.earth import je
    except ImportError:
        print("  jaxa-earth is not installed. Run:  python -m pip install jaxa-earth"); summary["jaxa"] = "not installed"; return
    for name, col, band, dlim, bbox in JAXA:
        path = os.path.join(OUT, name + ".npz")
        if os.path.exists(path):
            print("  already have", name); summary[name] = "cached"; continue
        for attempt in range(3):
            try:
                ic = (je.ImageCollection(col).filter_date(dlim).filter_resolution(4)
                      .filter_bounds(bbox).select(band).get_images())
                imgs = np.stack([np.asarray(m, np.float32) for m in ic.raster.img])
                if imgs.ndim == 4: imgs = imgs[..., 0]
                ids = [str(s) for s in getattr(ic.stac_date, "id", [])]
                np.savez_compressed(path, img=imgs, latlim=np.asarray(ic.raster.latlim, np.float64),
                                    lonlim=np.asarray(ic.raster.lonlim, np.float64), dates=np.array(ids), band=band, collection=col)
                summary[name] = dict(shape=list(imgs.shape), nan_frac=float(np.isnan(imgs).mean()),
                                     p5_p95=[float(np.nanpercentile(imgs, 5)), float(np.nanpercentile(imgs, 95))])
                print("  saved", name, imgs.shape); break
            except Exception as e:
                print(f"  {name} attempt {attempt+1} failed: {type(e).__name__}: {e}")
                summary[name] = f"failed: {type(e).__name__}: {e}"; time.sleep(5)

# --------------------------------------------------------------------------- 3. Earth rock types
# GLiM global lithological map (Hartmann & Moosdorf 2012), gridded to 0.5 degree, PANGAEA doi:10.1594/PANGAEA.788537
GLIM_URL = "https://hdl.handle.net/10013/epic.39939.d001"

def geology():
    print("[3/3] GLiM global lithology (rock types for the geology dimension)")
    path = os.path.join(OUT, "glim_05deg.zip")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print("  already have glim_05deg.zip"); summary["glim"] = "cached"; return
    download(GLIM_URL, path)
    summary["glim"] = dict(bytes=os.path.getsize(path)); print("  saved data/official/glim_05deg.zip")

if __name__ == "__main__":
    parts = sys.argv[1:] or ["diviner", "jaxa", "geology"]
    if "diviner" in parts:
        try: diviner()
        except Exception as e: print("  Diviner failed:", type(e).__name__, e); summary["diviner"] = f"failed: {e}"
    if "jaxa" in parts: jaxa()
    if "geology" in parts:
        try: geology()
        except Exception as e: print("  GLiM failed:", type(e).__name__, e); summary["glim"] = f"failed: {e}"
    with open(os.path.join(OUT, "summary.json"), "w") as f: json.dump(summary, f, indent=1)
    print("\nSUMMARY"); print(json.dumps(summary, indent=1))
    print("\nDone.")
