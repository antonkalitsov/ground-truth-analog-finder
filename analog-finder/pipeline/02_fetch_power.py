"""Mirror selected NASA POWER climatology variables (Zarr on AWS Open Data) and save as .npy
Source: https://registry.opendata.aws/nasa-power/  (MERRA-2 meteorology 0.5x0.625 deg, CERES SYN1deg 1 deg)
Usage: python 02_fetch_power.py <out_dir>
Output: <out_dir>/<VAR>.npy  (13 x lat x lon; index 12 = annual), plus lat/lon arrays.
"""
import sys, os, json, urllib.request, concurrent.futures as cf, itertools, time
import numpy as np, zarr

out = sys.argv[1] if len(sys.argv) > 1 else "../raw/power"
os.makedirs(out, exist_ok=True)
BASE = "https://nasa-power.s3.amazonaws.com/{s}/temporal/power_{s}_climatology_temporal_utc.zarr/"
WANT = {
    "merra2": ["T2M", "T2M_MAX", "T2M_MIN", "T2M_RANGE", "TS", "PRECTOTCORR", "PS", "GWETTOP", "WS10M", "FRSNO", "RH2M", "lat", "lon"],
    "syn1deg": ["ALLSKY_SRF_ALB", "AOD_55", "ALLSKY_SFC_SW_DWN", "ALLSKY_SFC_UV_INDEX", "lat", "lon"],
}

def fetch(url, path):
    if os.path.exists(path):
        return
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                d = r.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(d)
            os.replace(path + ".tmp", path)
            return
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return  # missing chunk = fill value
            time.sleep(1 + a)
        except Exception:
            time.sleep(1 + a)
    print("FAILED", url, flush=True)

for s, names in WANT.items():
    base = BASE.format(s=s)
    store = os.path.join(out, s + ".zarr")
    os.makedirs(store, exist_ok=True)
    fetch(base + ".zmetadata", os.path.join(store, ".zmetadata"))
    meta = json.load(open(os.path.join(store, ".zmetadata")))["metadata"]
    for k in (".zgroup", ".zattrs"):
        if k in meta:
            json.dump(meta[k], open(os.path.join(store, k), "w"))
    jobs = []
    for v in names:
        za = meta[v + "/.zarray"]
        os.makedirs(os.path.join(store, v), exist_ok=True)
        json.dump(za, open(os.path.join(store, v, ".zarray"), "w"))
        json.dump(meta.get(v + "/.zattrs", {}), open(os.path.join(store, v, ".zattrs"), "w"))
        sep = za.get("dimension_separator", ".")
        n = [int(np.ceil(sh / ch)) for sh, ch in zip(za["shape"], za["chunks"])]
        for idx in itertools.product(*[range(x) for x in n]):
            key = sep.join(map(str, idx))
            jobs.append((base + v + "/" + key, os.path.join(store, v, key)))
    with cf.ThreadPoolExecutor(24) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))
    g = zarr.open(store, mode="r")
    for v in names:
        a = np.asarray(g[v][:])
        np.save(os.path.join(out, f"{s}_{v}.npy"), a)
        if a.ndim == 3:
            print(s, v, a.shape, float(np.nanmin(a[-1])), float(np.nanmean(a[-1])), float(np.nanmax(a[-1])), "nan%", round(float(np.isnan(a[-1]).mean() * 100), 1), flush=True)
        else:
            print(s, v, a.shape, a[:3], a[-3:], flush=True)
