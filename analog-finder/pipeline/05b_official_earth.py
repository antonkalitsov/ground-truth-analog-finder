"""Earth layers from the official challenge resources (JAXA G-Portal / EORC / JASMES products via the JAXA Earth API,
fetched by fetch_official.py) and the GLiM global lithological map, regridded to Ground Truth's 0.25 degree grid.

  trange  <- GCOM-C SGLI land surface temperature, day minus night, mean of the 12 months of 2023 (surface, not air:
             the right quantity to compare with the regolith temperature swing on the Moon and Mars).
             Cells that stay cloudy all year are filled from MERRA-2 air-temperature range through a fitted linear relation.
  dry     <- GSMaP gauge-adjusted precipitation normal 2012-2021 (60 S - 60 N); MERRA-2 poleward of 60 degrees.
  ndvi    <- MODIS NDVI normal 2012-2021 (JAXA JASMES), annual mean; ice sheets and bare cells without data = 0.
  soil    <- AMSR2 soil moisture only if SOIL=amsr2 (off by default: see FINDINGS.md, the retrieval is biased high over
             sand seas and invalid under forest, and it lowered validation AUC). Default keeps MERRA-2 GWETTOP.
  rock    <- GLiM 0.5 degree first-level lithology class (index into traits.GLIM), when data/official/glim_05deg.zip exists.

Usage: python 05b_official_earth.py <raw_dir>      (reads raw/official/*.npz, writes raw/earth_official.npz)
"""
import sys, os, io, zipfile, warnings, numpy as np
import traits as T
warnings.filterwarnings("ignore", category=RuntimeWarning)

raw = sys.argv[1]
O = os.path.join(raw, "official")
E = np.load(os.path.join(raw, "earth_traits.npz"))
ok = E["ok"]; NY, NX = ok.shape
out, sources = {}, {}

def to025(a, top, res):
    """area-average a north-up global grid (rows from `top`, cell `res` degrees) onto the 0.25 degree grid; NaN aware"""
    f = int(round(res / 0.05)); a = np.repeat(np.repeat(a, f, 0), f, 1)          # -> 0.05 deg
    full = np.full((3600, 7200), np.nan, np.float32)
    r0 = int(round((90 - top) / 0.05)); full[r0:r0 + a.shape[0]] = a
    b = full.reshape(NY, 5, NX, 5)
    n = np.isfinite(b).sum((1, 3)); s = np.nansum(b, (1, 3))
    return np.where(n > 0, s / np.maximum(n, 1), np.nan).astype(np.float32)

def load(name):
    p = os.path.join(O, name + ".npz")
    if not os.path.exists(p): return None
    d = np.load(p, allow_pickle=False)
    lat = d["latlim"].ravel(); lon = d["lonlim"].ravel(); img = d["img"]
    res = (lat[1] - lat[0]) / img.shape[1]
    assert abs((lon[1] - lon[0]) / img.shape[2] - res) < 1e-6
    return img, float(lat[1]), float(res), str(d["collection"])

# ---------------------------------------------------------------- day-night surface temperature swing
day, night = load("gcomc_lst_day_2023"), load("gcomc_lst_night_2023")
if day is not None and night is not None:
    rng = np.nanmean(day[0] - night[0], 0)                 # months where both exist
    r = to025(rng, day[1], day[2])
    air = E["trange"]
    m = ok & np.isfinite(r)
    b, a = np.polyfit(air[m], r[m], 1)
    filled = np.where(np.isfinite(r), r, a + b * air)
    out["trange"] = np.clip(filled, 0, 80).astype(np.float32)
    sources["trange"] = f"JAXA GCOM-C SGLI LST day-night, 2023 ({100*m.sum()/ok.sum():.0f}% of land cells observed; rest from MERRA-2 via fit r={a:.1f}+{b:.2f}*airrange)"
    print(sources["trange"])

# ---------------------------------------------------------------- precipitation
pr = load("gsmap_precip_normal")
if pr is not None:
    p = np.nanmean(pr[0], 0) * 24 * 365.25                # mm/h monthly normals -> mm/yr
    g = to025(p, pr[1], pr[2])
    lat = E["lat"][:, None] * np.ones((1, NX))
    use = np.isfinite(g) & (np.abs(lat) < 59.9)
    out["dry"] = np.where(use, g, E["precip"]).astype(np.float32)
    sources["dry"] = f"JAXA GSMaP gauge-adjusted precipitation normal 2012-2021 ({100*(use & ok).sum()/ok.sum():.0f}% of land cells; poleward of 60 deg: MERRA-2)"
    print(sources["dry"])

# ---------------------------------------------------------------- vegetation greenness (biology)
nd = load("modis_ndvi_normal")
if nd is not None:
    v = to025(np.nanmean(nd[0], 0), nd[1], nd[2])
    v = np.where(np.isfinite(v), v, 0.0)                   # no NDVI retrieval: ice sheets / permanent snow -> no plants
    out["ndvi"] = np.clip(v, -0.1, 0.9).astype(np.float32)
    sources["ndvi"] = "JAXA JASMES MODIS NDVI normal 2012-2021, annual mean"
    print(sources["ndvi"])

# ---------------------------------------------------------------- soil moisture (opt-in)
sm = load("amsr2_soil_normal")
if sm is not None and os.environ.get("SOIL") == "amsr2":
    s = to025(np.nanmean(sm[0], 0), sm[1], sm[2]) / 100.0
    wet = E["wet"]; m = ok & np.isfinite(s)
    b, a = np.polyfit(wet[m], s[m], 1)
    out["soil"] = np.clip(np.where(np.isfinite(s), s, a + b * wet), 0, 1).astype(np.float32)
    sources["soil"] = "JAXA GCOM-W AMSR2 soil moisture normal 2012-2021"
    print(sources["soil"])

# ---------------------------------------------------------------- lithology (geology)
gz = os.path.join(O, "glim_05deg.zip")
if os.path.exists(gz):
    z = zipfile.ZipFile(gz)
    asc = [n for n in z.namelist() if n.lower().endswith(".asc")][0]
    names = [l.split(";")[-1].strip().strip('"') for l in z.read("Classnames.txt").decode().splitlines()[1:] if l.strip()]
    assert names == T.GLIM, names                      # GLiM value v -> traits.GLIM[v-1]
    g = np.loadtxt(io.StringIO(z.read(asc).decode()), skiprows=6)   # 360 x 720, row 0 = 90 N, 0.5 deg, -9999 = none
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)                          # -> 0.25 deg (each 0.5 deg cell holds its dominant class)
    cls = np.where(g > 0, g - 1, -1).astype(np.int16)
    # land cells on coasts and small islands without a GLiM value: take the nearest classed neighbour (up to 3 cells)
    for _ in range(3):
        miss = ok & (cls < 0)
        if not miss.any(): break
        pad = np.pad(cls, 1, mode="edge"); pad[:, 0] = pad[:, -2]; pad[:, -1] = pad[:, 1]
        nb = np.stack([pad[1 + di:1 + di + NY, 1 + dj:1 + dj + NX] for di in (-1, 0, 1) for dj in (-1, 0, 1)])
        best = np.where((nb >= 0).any(0), nb.max(0), -1)
        cls = np.where(miss, best, cls)
    cls = np.where(cls < 0, T.GLIM.index("nd"), cls)
    out["rock"] = cls.astype(np.float32)
    vals, cnt = np.unique(cls[ok], return_counts=True)
    print("GLiM classes on land cells:", {T.GLIM[v]: int(c) for v, c in zip(vals, cnt)})
    sources["rock"] = "GLiM global lithological map (Hartmann & Moosdorf 2012), 0.5 degree dominant class"
    print(sources["rock"])

np.savez_compressed(os.path.join(raw, "earth_official.npz"), sources=np.array(sources, dtype=object), **out)
print("wrote earth_official.npz", sorted(out))
