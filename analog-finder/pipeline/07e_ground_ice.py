"""Refresh the Earth ground-ice range and percentiles in manifest.json of an already built data pack.

Ground-ice likelihood on Earth is derived, not stored: the app and the pipeline compute it from the temperature and
ice-cover layers (traits.earth_ice). When that rule changes, the 1st..99th percentile range and the percentile table
kept in manifest.json must follow. The pack's stored layers do not change.
Usage: python 07e_ground_ice.py <web_dir>
"""
import sys, os, gzip, json, numpy as np
import traits as T

D = os.path.join(sys.argv[1], "data")
man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
g = man["grid"]; NX, NY, N, STORED = g["nx"], g["ny"], g["cells"], g["stored"]
b = gzip.decompress(open(os.path.join(D, "earth.bin.gz"), "rb").read())
nb = (NX * NY + 7) // 8
layer = lambda t: np.frombuffer(b[nb + STORED.index(t) * N: nb + (STORED.index(t) + 1) * N], np.uint8)
ice = T.to_t("ice", T.earth_ice(T.dequant_t("temp", layer("temp")), T.dequant_t("icecover", layer("icecover"))))
tr = next(t for t in man["traits"] if t["id"] == "ice")
tr["earthLo"] = float(np.percentile(ice, 1)); tr["earthHi"] = float(np.percentile(ice, 99))
tr["quant"] = [round(float(x), 5) for x in np.percentile(ice, np.arange(101))]
json.dump(man, open(os.path.join(D, "manifest.json"), "w"), separators=(",", ":"))
print("ground ice: range", tr["earthLo"], tr["earthHi"], "share of land with likelihood > 0.5:", round(float((ice > 0.5).mean()), 3))
