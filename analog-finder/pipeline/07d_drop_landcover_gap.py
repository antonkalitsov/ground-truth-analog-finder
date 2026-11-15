"""Drop Earth cells north of ESA WorldCover's northern limit from an already built data pack.

WorldCover 2021 (Sentinel-2) stops at about 82.75 N. 05_earth_traits.py used to fill those cells (north Greenland,
north Ellesmere Island) from the Natural Earth 1:10m glacier outlines, which were meant for Antarctica: they are too
coarse to see local ice caps, and they set barren ground to exactly 100 % because they carry no moss, lichen or
shrub classes. The result was 0 % snow/ice on cells next to ice caps and inflated scores for barren, cold targets
(several Moon top-10 lists were led by such cells). 05_earth_traits.py now leaves these cells out; this script
applies the same change to a pack built before that fix, without the raw downloads.

Rewrites web/data/earth.bin.gz, names.bin.gz, the Earth ranges and percentiles in manifest.json (computed exactly as
07_build_pack.py does), and removes the dropped cells from stage2.json. Writes <raw_dir>/earth_t.npz for 08_findings.py.
Usage: python 07d_drop_landcover_gap.py <web_dir> [<raw_dir>]
"""
import sys, os, gzip, json, numpy as np
import traits as T
from terrainlib import mean_noon_sun_elevation

WC_NORTH = 82.75            # northern edge of ESA WorldCover 2021 v200 data
web = sys.argv[1]; raw = sys.argv[2] if len(sys.argv) > 2 else None
D = os.path.join(web, "data")
man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
NX, NY = man["grid"]["nx"], man["grid"]["ny"]; STORED = man["grid"]["stored"]; EL = man["grid"]["elev"]
b = gzip.decompress(open(os.path.join(D, "earth.bin.gz"), "rb").read())
nb = (NX * NY + 7) // 8
ok = np.unpackbits(np.frombuffer(b[:nb], np.uint8), bitorder="little")[:NX * NY].astype(bool)
idx = np.flatnonzero(ok); N = len(idx); off = nb
layers = []
for _ in STORED: layers.append(np.frombuffer(b[off:off + N], np.uint8)); off += N
qelev = np.frombuffer(b[off:off + N], np.uint8); assert off + N == len(b), "unexpected pack layout"

lat = 90 - (idx // NX + 0.5) * 0.25
keep = lat < WC_NORTH
drop = idx[~keep]
print(f"cells {N} -> {int(keep.sum())}, dropping {len(drop)} north of {WC_NORTH} N")
if not len(drop): sys.exit("nothing to drop (pack already fixed)")
idx = idx[keep]; layers = [l[keep] for l in layers]; qelev = qelev[keep]
ok2 = np.zeros(NX * NY, np.uint8); ok2[idx] = 1
bits = np.packbits(ok2, bitorder="little")
open(os.path.join(D, "earth.bin.gz"), "wb").write(gzip.compress(bits.tobytes() + b"".join(l.tobytes() for l in layers) + qelev.tobytes(), 9))

nm = np.frombuffer(gzip.decompress(open(os.path.join(D, "names.bin.gz"), "rb").read()), np.uint16).reshape(3, N)
open(os.path.join(D, "names.bin.gz"), "wb").write(gzip.compress(np.ascontiguousarray(nm[:, keep]).tobytes(), 9))

# Earth ranges and percentiles, as in 07_build_pack.py (dequantised stored layers; sun, ice, pressure derived)
earth_t = {t: T.dequant_t(t, layers[STORED.index(t)]) for t in STORED}
elev_d = EL["min"] + qelev / 255 * (EL["max"] - EL["min"])
earth_t["pressure"] = T.to_t("pressure", T.earth_pressure(elev_d))
earth_t["ice"] = T.to_t("ice", T.earth_ice(T.dequant_t("temp", layers[STORED.index("temp")]), T.dequant_t("icecover", layers[STORED.index("icecover")])))
earth_t["sun"] = T.to_t("sun", mean_noon_sun_elevation(90 - (idx // NX + 0.5) * 0.25, 23.44))
for tr in man["traits"]:
    t = tr["id"]
    if tr["transform"] == "cat":
        tr["earthLo"], tr["earthHi"] = -1e9, 1e9
    else:
        tr["earthLo"] = float(np.percentile(earth_t[t], 1)); tr["earthHi"] = float(np.percentile(earth_t[t], 99))
    tr["quant"] = [round(float(x), 5) for x in np.percentile(earth_t[t], np.arange(101))]
man["grid"]["cells"] = int(len(idx))
json.dump(man, open(os.path.join(D, "manifest.json"), "w"), separators=(",", ":"))   # same format as 09_stage2.py

p2 = os.path.join(D, "stage2.json")
if os.path.exists(p2):
    s2 = json.load(open(p2, encoding="utf-8")); gone = {str(int(k)) for k in drop}; n0 = 0
    for tg in s2.get("targets", {}).values():
        for k in list(tg.get("cells", {})):
            if k in gone: del tg["cells"][k]; n0 += 1
    if "earthChips" in s2:
        s2["earthChips"]["cells"] = [c for c in s2["earthChips"]["cells"] if str(c) not in gone]
    json.dump(s2, open(p2, "w", encoding="utf-8"), separators=(",", ":"))
    print("stage2 entries removed:", n0)
if raw:
    os.makedirs(raw, exist_ok=True)
    np.savez_compressed(os.path.join(raw, "earth_t.npz"), idx=idx, **{k: v.astype(np.float32) for k, v in earth_t.items()})
