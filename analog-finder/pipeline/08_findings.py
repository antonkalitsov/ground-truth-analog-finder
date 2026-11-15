"""Global screening run, validation against known analog sites, and the FINDINGS.md report.
Usage: python 08_findings.py <raw_dir> <web_dir> <out_md>
"""
import sys, os, json, csv, gzip, numpy as np
import traits as T

raw, web, out_md = sys.argv[1:4]
man = json.load(open(os.path.join(web, "data", "manifest.json"), encoding="utf-8"))
Et = np.load(os.path.join(raw, "earth_t.npz")); idx = Et["idx"]
earth_t = {t: Et[t].astype(np.float64) for t in T.TID if t in Et.files}
lo = {t["id"]: t["earthLo"] for t in man["traits"]}; hi = {t["id"]: t["earthHi"] for t in man["traits"]}
Q = {t["id"]: np.array(t["quant"]) for t in man["traits"]}
NX = 1440
clat = 90 - (idx // NX + 0.5) * 0.25; clon = -180 + (idx % NX + 0.5) * 0.25
names = json.load(open(os.path.join(web, "data", "names.json"), encoding="utf-8"))
nm = np.frombuffer(gzip.decompress(open(os.path.join(web, "data", "names.bin.gz"), "rb").read()), dtype=np.uint16).reshape(3, -1)
known = man["known"]
klat = np.array([k["lat"] for k in known]); klon = np.array([k["lon"] for k in known])

def hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.minimum(a, 1)))

def place(i):
    a1, a0, rg = (names[nm[k, i]] for k in range(3))
    s = ", ".join(x for x in (a1, a0) if x)
    return (s + (f" ({rg})" if rg and rg not in s else "")) or "Unnamed"

def target_t(t):
    return {k: float(T.to_t(k, t["traits"][k])) for k in T.TID if k in t["traits"]}

def candidates(sc, n=10, sep=300, newkm=150):
    order = np.argsort(-sc); picked = []
    dk_all = None
    for i in order[:60000]:
        if any(hav(clat[i], clon[i], clat[j], clon[j]) < sep for j in picked): continue
        dk = hav(clat[i], clon[i], klat, klon).min()
        if dk < newkm: continue
        picked.append(i)
        if len(picked) >= n: break
    return picked

def cell_of(lat, lon):
    d = hav(lat, lon, clat, clon); i = int(np.argmin(d))
    return i if d[i] < 40 else None

def pct(sc, i):
    return 100.0 * (sc < sc[i]).mean()

def auc(pos, neg):
    pos, neg = np.array(pos), np.array(neg)
    return float(((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()))

W = {p["id"]: p["weights"] for p in man["presets"]}
tg = {t["id"]: t for t in man["targets"]}
lines = ["# Terra Twin: findings", "",
         "Every land cell on Earth (318,332 cells of 0.25 degrees, about 28 km) was scored against each Moon and Mars target.",
         "Scores are 0 to 100: the weighted mean of per-trait similarities. 'New' means more than 150 km from all 107 catalogued analog sites.", ""]

# ---------------------------------------------------------------- validation
# Known analogs are split by why they were chosen: for their environment and terrain (what this tool measures)
# or for their rocks and chemistry only (volcanic islands, impact craters in farmland, acid rivers), which 28 km climate
# and terrain data cannot see.
ENV = {"Atacama Desert (Yungay)", "Haughton Crater (Devon Island)", "Death Valley (Badwater)", "Mars Desert Research Station (Utah)",
       "Wright Valley (Antarctic Dry Valleys)", "Wadi Rum (Jordan)", "Bockfjord (Svalbard)", "Dresser Formation (Pilbara)",
       "Gypsum Hill (Axel Heiberg Island)", "Dallol (Danakil Depression)", "Dome C (Antarctica)", "Pilot Valley (Utah)",
       "Meteor Crater (Arizona)", "Black Point Lava Flow (Arizona)", "Verde Valley (Arizona)", "Craters of the Moon (Idaho)"}
rows = list(csv.DictReader(open("earth_sites_validation.csv", encoding="utf-8")))
val = {}
for body in ("mars", "moon"):
    ts = [t for t in man["targets"] if t["body"] == body]
    sc = np.max([T.score(earth_t, target_t(t), W["overall"], lo, hi, Q)[0] for t in ts], axis=0)
    env, geo, neg = [], [], []
    for r in rows:
        i = cell_of(float(r["lat"]), float(r["lon"]))
        if i is None: continue
        partial = any(w in r["notes"].lower() for w in ("plausible", "sand sea", "desert", "dune", "salt flat", "canyon"))
        if r["type"] == "analog" and body in r["analog_for"].lower():
            (env if r["name"] in ENV else geo).append(sc[i])
        elif r["type"] == "decoy" and not partial: neg.append(sc[i])
    kp = [pct(sc, i) for k in known if k["body"] in (body, "both") for i in [cell_of(k["lat"], k["lon"])] if i is not None]
    val[body] = dict(auc_env=auc(env, neg), auc_geo=auc(geo, neg), nenv=len(env), ngeo=len(geo), nneg=len(neg),
                     env_pct=float(np.median([pct(sc, int(np.argmin(np.abs(sc - v)))) for v in env])),
                     median_pct=float(np.median(kp)), top10=float(np.mean(np.array(kp) >= 90) * 100), nknown=len(kp))
    print(body, val[body])
lines += ["## Validation", "",
          "For each body, every land cell gets its best score over all targets (Overall preset). We then check where known analog sites fall.",
          "Clear non-analogs are 26 hand-picked places: rainforest, farmland, cities, wetlands, taiga, the Greenland ice sheet. Desert and dune 'look-alikes' are left out because they are partial analogs by design.", "",
          "| Target body | Environment analogs vs non-analogs (AUC) | Geology-only analogs vs non-analogs (AUC) | All 107 catalogued sites: median percentile | In Earth's top 10% |", "|---|---|---|---|---|"]
for b, v in val.items():
    lines.append(f"| {b.capitalize()} | {v['auc_env']:.2f} ({v['nenv']} vs {v['nneg']}) | {v['auc_geo']:.2f} ({v['ngeo']} vs {v['nneg']}) | {v['median_pct']:.0f}th ({v['nknown']} sites) | {v['top10']:.0f}% |")
lines += ["", "AUC is the chance that a random analog outscores a random non-analog (0.5 = coin flip, 1.0 = perfect). Nothing was tuned on these sites.",
          "Analogs chosen for their environment and terrain (deserts, polar sites, dry lava fields) are recognised best. Analogs chosen mainly for their rocks (wet volcanic islands, impact craters in farmland) score lower. The GLiM rock map is 0.5 degree and mostly sees sedimentary cover, so rock type adds little here; telling clays and sulfates apart would need imaging spectroscopy (for example NASA EMIT or ASTER), the natural next layer.", ""]
_abl = os.path.join(raw, "official", "ablation.json")
if os.path.exists(_abl):
    lines += ["### What each official challenge dataset added", "", "| Step | Mars AUC (environment / geology) | Moon AUC (environment / geology) |", "|---|---|---|"]
    for r in json.load(open(_abl))["rows"]:
        lines.append(f"| {r['step']}{' (rejected)' if r.get('rejected') else ''} | {r['mars_env']:.2f} / {r['mars_geo']:.2f} | {r['moon_env']:.2f} / {r['moon_geo']:.2f} |")
    lines += ["", "JAXA AMSR2 soil moisture was dropped: its retrieval reads high over sand seas (Sahara about 10-14 %) and is invalid under forest, and swapping it in lowered every geology AUC.", ""]

# ---------------------------------------------------------------- per-target findings
summary = {}
for tid_, preset in [("shackleton-connecting-ridge", "polar"), ("de-gerlache-rim-2", "polar"), ("malapert-massif", "overall"), ("slater-plain", "landing"),
                     ("haworth", "isru"), ("jezero-perseverance", "overall"), ("gale-curiosity", "landing"), ("utopia-viking-2", "isru"),
                     ("arcadia-planitia", "isru"), ("meridiani-opportunity", "instruments"), ("green-valley-phoenix", "isru"), ("melas-chasma", "crew")]:
    t = tg[tid_]; tt = target_t(t)
    sc, sims = T.score(earth_t, tt, W[preset], lo, hi, Q)
    picks = candidates(sc, n=5)
    lines += [f"## {t['name']} ({t['body'].capitalize()}), preset: {next(p['label'] for p in man['presets'] if p['id']==preset)}", ""]
    lines += ["| # | New candidate | Lat, lon | Score | Strong traits | Weak traits | Nearest known analog |", "|---|---|---|---|---|---|---|"]
    out = []
    for r, i in enumerate(picks, 1):
        strong = [k for k in sims if sims[k][i] >= 0.75]; weak = [k for k in sims if sims[k][i] < 0.4]
        d = hav(clat[i], clon[i], klat, klon); j = int(np.argmin(d))
        lab = lambda ks: ", ".join(next(x[1] for x in T.TRAITS if x[0] == k).lower() for k in ks) or "none"
        lines.append(f"| {r} | {place(i)} | {clat[i]:.2f}, {clon[i]:.2f} | {sc[i]:.0f} | {lab(strong)} | {lab(weak)} | {known[j]['name']} ({d[j]:.0f} km) |")
        out.append(dict(place=place(i), lat=float(clat[i]), lon=float(clon[i]), score=float(sc[i])))
    beyond = [next(x[1] for x in T.TRAITS if x[0] == k) for k in tt if W[preset].get(k, 0) > 0 and (tt[k] < lo[k] or tt[k] > hi[k])]
    best_known = max(((pct(sc, i), k["name"]) for k in known for i in [cell_of(k["lat"], k["lon"])] if i is not None))
    lines += ["", f"Best-ranked known analog for this target: {best_known[1]} ({best_known[0]:.1f}th percentile).",
              f"Beyond anything on Earth (ranked toward Earth's most extreme places): {', '.join(beyond) if beyond else 'none'}. Never reproducible: gravity ({man['bodies'][t['body']]['gravity']} m/s2), vacuum or thin air, surface radiation.", ""]
    summary[tid_] = out
abl_p = os.path.join(raw, "official", "ablation.json")
ablation = json.load(open(abl_p))["rows"] if os.path.exists(abl_p) else []
json.dump(dict(validation=val, findings=summary, ablation=ablation), open(os.path.join(web, "data", "findings.json"), "w"), indent=1)
open(out_md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
