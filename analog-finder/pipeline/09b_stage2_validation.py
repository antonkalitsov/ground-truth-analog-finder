"""Stage 2 validation: does measuring terrain at 30 m still tell known analog sites apart from clear non-analogs?

Same sites and the same split as the stage 1 validation in 08_findings.py: analogs chosen for their environment and terrain,
analogs chosen for their rocks only, and clear non-analogs (rainforest, farmland, cities, wetlands, taiga, ice sheet).
Nothing is tuned on these sites.

For every site's 28 km cell the best 8 km zone is found exactly as in 09_stage2.py, and four scores are compared:
  terrain at 28 km   stage 1 slope, roughness and relief similarities only (equal weights)
  terrain at 30 m    the stage 2 zone match (0.4 slope + 0.4 roughness + 0.2 relief)
  full at 28 km      the stage 1 score, Overall preset
  full at 30 m       the same score with the three terrain similarities replaced by the 30 m ones
Mars uses Jezero (the one Mars target with a 30 m model); the Moon uses the best of its ten regions, as stage 1 does.

Usage: python 09b_stage2_validation.py <web_dir> <raw_dir>   (run after 09_stage2.py, which leaves the Jezero model in raw/stage2)
Writes the results into web/data/stage2.json under "validation" and prints a table.
"""
import sys, os, csv, json, importlib.util
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s2", os.path.join(HERE, "09_stage2.py")); S2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S2)

ENV = {"Atacama Desert (Yungay)", "Haughton Crater (Devon Island)", "Death Valley (Badwater)", "Mars Desert Research Station (Utah)",
       "Wright Valley (Antarctic Dry Valleys)", "Wadi Rum (Jordan)", "Bockfjord (Svalbard)", "Dresser Formation (Pilbara)",
       "Gypsum Hill (Axel Heiberg Island)", "Dallol (Danakil Depression)", "Dome C (Antarctica)", "Pilot Valley (Utah)",
       "Meteor Crater (Arizona)", "Black Point Lava Flow (Arizona)", "Verde Valley (Arizona)", "Craters of the Moon (Idaho)"}
PARTIAL = ("plausible", "sand sea", "desert", "dune", "salt flat", "canyon")
TERRAIN = ("slope", "rough", "relief")


def clean(o):
    """Replace NaN (a site with no usable 30 m zone) by null, which JSON allows."""
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    return o


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    web = sys.argv[1]; D = os.path.join(web, "data")
    P = S2.Pack(D); man = P.man
    s2 = json.load(open(os.path.join(D, "stage2.json")))
    W = {p["id"]: p["weights"] for p in man["presets"]}["overall"]
    rows = list(csv.DictReader(open(os.path.join(HERE, "earth_sites_validation.csv"), encoding="utf-8")))

    def cell_of(lat, lon):
        d = S2.hav(lat, lon, P.lat, P.lon); i = int(np.argmin(d))
        return i if d[i] < 40 else None

    def sims(t, i):
        """Per-trait stage 1 similarity of land cell i to target t, and the weights in use."""
        out = {}
        for tr in man["traits"]:
            if (W.get(tr["id"], 0) or 0) > 0:
                out[tr["id"]] = float(P.lut(tr, float(P.toT(tr, t["traits"][tr["id"]])))[P.layer[tr["id"]][i]])
        return out

    def full(sm, swap=None):
        num = den = 0.0
        for k, v in sm.items():
            w = W[k]; num += w * (swap[TERRAIN.index(k)] if swap and k in TERRAIN else v); den += w
        return 100 * num / den

    # which cells, and their 30 m placements (computed once per cell)
    sites = []
    for r in rows:
        i = cell_of(float(r["lat"]), float(r["lon"]))
        if i is None:
            continue
        sites.append((r, i))
    cells = sorted({i for _, i in sites})
    print(len(sites), "sites in", len(cells), "cells; measuring at 30 m", flush=True)
    with ThreadPoolExecutor(8) as ex:
        pl = dict(zip(cells, ex.map(lambda i: S2.cell_placements(float(P.lat[i]), float(P.lon[i])), cells)))

    tstats = {}
    for t in man["targets"]:
        if t["id"] in s2["targets"]:
            # rebuild the target zone statistics from the stored summary is lossy, so measure it again (cheap)
            if t["body"] == "mars":
                z = S2.warp(os.path.join(sys.argv[2] if len(sys.argv) > 2 else "../raw", "stage2", S2.FINE_MARS[t["id"]]["file"]), t["lat"], t["lon"], S2.ZONE_KM + 2.0, S2.R_MARS, S2.Resampling.average)
            else:
                z = S2.warp("/vsicurl/" + S2.LOLA_URL, t["lat"], t["lon"], S2.ZONE_KM + 2.0, S2.R_MOON, S2.Resampling.bilinear, scale=0.5)
            tstats[t["id"]] = S2.target_zone(z)

    def best(i, tid):
        b = None
        for st in pl[i]:
            s = S2.fine_sim(st, tstats[tid]); f = sum(a * c for a, c in zip(S2.W_FINE, s))
            if b is None or f > b[0]:
                b = (f, s)
        return b

    res = {}
    for body in ("mars", "moon"):
        ts = [t for t in man["targets"] if t["body"] == body and t["id"] in tstats]
        groups = {"env": [], "geo": [], "neg": []}
        for r, i in sites:
            if r["type"] == "analog" and body in r["analog_for"].lower():
                g = "env" if r["name"] in ENV else "geo"
            elif r["type"] == "decoy" and not any(w in r["notes"].lower() for w in PARTIAL):
                g = "neg"
            else:
                continue
            sc = {"t28": [], "t30": [], "f28": [], "f30": []}
            for t in ts:
                sm = sims(t, i); b = best(i, t["id"])
                sc["t28"].append(100 * np.mean([sm[k] for k in TERRAIN]))
                sc["f28"].append(full(sm))
                sc["t30"].append(100 * b[0] if b else np.nan)
                sc["f30"].append(full(sm, b[1]) if b else full(sm))
            groups[g].append(dict(name=r["name"], **{k: float(np.nanmax(v)) if np.isfinite(v).any() else float("nan") for k, v in sc.items()}))
        out = dict(targets=[t["id"] for t in ts], n={g: len(v) for g, v in groups.items()})
        for k in ("t28", "t30", "f28", "f30"):
            neg = [x[k] for x in groups["neg"] if np.isfinite(x[k])]
            out[k] = dict(env=auc([x[k] for x in groups["env"] if np.isfinite(x[k])], neg),
                          geo=auc([x[k] for x in groups["geo"] if np.isfinite(x[k])], neg),
                          all=auc([x[k] for x in groups["env"] + groups["geo"] if np.isfinite(x[k])], neg))
        out["no30m"] = [x["name"] for g in groups.values() for x in g if not np.isfinite(x["t30"])]
        out["sites"] = {g: [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in x.items()} for x in vs] for g, vs in groups.items()}
        res[body] = out
        print(f"\n{body.upper()}  ({', '.join(out['targets'][:3])}{'...' if len(ts) > 3 else ''})  n={out['n']}")
        print(f"{'':16s}{'env vs non':>12s}{'rock vs non':>13s}{'all vs non':>12s}")
        for k, lab in (("t28", "terrain 28 km"), ("t30", "terrain 30 m"), ("f28", "full 28 km"), ("f30", "full 30 m")):
            print(f"{lab:16s}{out[k]['env']:12.2f}{out[k]['geo']:13.2f}{out[k]['all']:12.2f}")
        if out["no30m"]:
            print("  no usable 30 m zone:", ", ".join(out["no30m"]))
    s2["validation"] = clean(res)
    # allow_nan=False: a NaN would make the file invalid JSON and the browser would silently drop stage 2
    json.dump(s2, open(os.path.join(D, "stage2.json"), "w"), separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
