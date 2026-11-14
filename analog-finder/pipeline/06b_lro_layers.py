"""Moon south-pole layers from official LRO / USGS products (NASA Space Apps resource list: LRO LROC, LOLA, Diviner).

  * LROC WAC south-pole mosaic (100 m, USGS Astrogeology S3) -> the picker base map web/assets/moon_spole.jpg
  * Unified Geologic Map of the Moon (USGS 2020, 64 ppd)      -> geologic unit + rock family per Moon cell
  * LRO Diviner polar resource product (Paige et al. 2010)    -> mean / max temperature and depth to stable ice per cell
    (data/official/diviner_prp_south_476.npz, produced by fetch_official.py on a machine that can reach PDS)

Writes raw/grids/moon_official.npz on the 119 x 119 Moon cell grid used by 07_build_pack.py.
Usage: python 06b_lro_layers.py <raw_dir> <web_assets_dir>
"""
import sys, os, csv, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform as wtransform
from PIL import Image
import traits as T

raw, assets = sys.argv[1:3]
L = np.load(os.path.join(raw, "grids", "moon_grid.npz"))
n = L["slope"].shape[0]; P = int(L["P"]); C = int(L["cell_px"]); left, bottom, right, top = L["bounds"]
mpp = (right - left) / P
MOONCRS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
MOONGEO = "+proj=longlat +R=1737400 +no_defs"
out = {}

# ---------------------------------------------------------------- LROC WAC picker map
wac = os.path.join(raw, "lro", "wac_spole60_100m.jp2")
if os.path.exists(wac):
    with rasterio.open(wac) as d:
        a = d.read(1, window=from_bounds(left, bottom, right, top, d.transform), out_shape=(1024, 1024)).astype(np.float32)
    g = np.clip(a / 210.0, 0, 1) ** 0.85
    img = np.stack([g * 0.97, g * 0.98, g * 1.0], -1)
    Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8)).save(os.path.join(assets, "moon_spole.jpg"), quality=78, optimize=True)
    # mean WAC brightness per cell: shows where the pole is in near-permanent shadow at the mosaic's sun angles
    a476 = np.array(Image.fromarray(a).resize((P, P), Image.BILINEAR))
    out["wac_dn"] = a476.reshape(n, C, n, C).mean((1, 3)).astype(np.float32)
    print("WAC picker map written")

# ---------------------------------------------------------------- cell centres
xs = left + (np.arange(n) * C + C / 2 + 0.5) * mpp
ys = top - (np.arange(n) * C + C / 2 + 0.5) * mpp
X, Y = np.meshgrid(xs, ys)
lon_m, lat_m = wtransform(MOONCRS, MOONGEO, X.ravel(), Y.ravel())
lat_m = np.array(lat_m).reshape(n, n); lon_m = np.array(lon_m).reshape(n, n)

# ---------------------------------------------------------------- unified geologic map
gdir = os.path.join(raw, "lro", "Unified_Geologic_Map_of_the_Moon_RASTER", "numerical_versions")
gtif = os.path.join(gdir, "Unified_Geologic_Map_of_the_Moon_64ppd.tif")
if os.path.exists(gtif):
    units = {}
    for r in csv.DictReader(open(os.path.join(gdir, "Dn_GeologicUnit_RGBcolor.csv"), encoding="utf-8-sig")):
        units[int(r["DN"])] = (r["Unit"], r["Unit_Name"], r["Unit_Age"])
    with rasterio.open(gtif) as d:
        geo = d.read(1)
        H, W = geo.shape
        # sample a 5 x 5 pattern of points inside every cell, take the most common unit
        sub = (np.arange(5) + 0.5) / 5 - 0.5
        votes = np.zeros((n, n, 5 * 5), np.int16); k = 0
        for dy in sub:
            for dx in sub:
                lo, la = wtransform(MOONCRS, MOONGEO, (X + dx * C * mpp).ravel(), (Y - dy * C * mpp).ravel())
                lo = (np.array(lo) + 180) % 360 - 180
                r = np.clip(((90 - np.array(la)) / 180 * H).astype(int), 0, H - 1)
                c = np.clip(((np.array(lo) + 180) / 360 * W).astype(int), 0, W - 1)
                votes[:, :, k] = geo[r, c].reshape(n, n); k += 1
    unit = np.zeros((n, n), np.int16)
    for i in range(n):
        for j in range(n):
            v = votes[i, j][votes[i, j] > 0]
            unit[i, j] = np.bincount(v).argmax() if len(v) else 0
    fam = np.full((n, n), T.FAMILY.index("highland"), np.uint8)
    for dn, (code, name, age) in units.items():
        f = T.moon_unit_family(code)
        fam[unit == dn] = T.FAMILY.index(f)
    out["geo_unit"] = unit; out["rock"] = fam
    out["unit_codes"] = np.array([units.get(i, ("", "", ""))[0] for i in range(max(units) + 1)])
    out["unit_names"] = np.array([units.get(i, ("", "", ""))[1] for i in range(max(units) + 1)])
    out["unit_ages"] = np.array([units.get(i, ("", "", ""))[2] for i in range(max(units) + 1)])
    vals, cnt = np.unique(unit[lat_m < -75.3], return_counts=True)
    print("geologic units in the south-pole grid:", [(units.get(int(v), ("?",))[0], int(c)) for v, c in sorted(zip(vals, cnt), key=lambda x: -x[1])[:10]])

# ---------------------------------------------------------------- Diviner polar resource product
div = os.path.join(raw, "official", "diviner_prp_south_476.npz")
if os.path.exists(div):
    D = np.load(div)
    def cells(a): return a.reshape(n, C, n, C).sum((1, 3))
    N = cells(D["n"])
    has = N > 0
    tavg = np.where(has, cells(D["tavg"]) / np.maximum(N, 1), np.nan)
    tmax = np.where(has, cells(D["tmax"]) / np.maximum(N, 1), np.nan)
    ice_frac = np.where(has, cells(D["ice_any"]) / np.maximum(N, 1), np.nan)            # share of facets with stable ice within ~1 m
    shallow = np.where(has, cells(D["ice_shallow"]) / np.maximum(N, 1), np.nan)
    out.update(div_n=N.astype(np.float32), div_tavg=tavg.astype(np.float32), div_tmax=tmax.astype(np.float32),
               div_ice=ice_frac.astype(np.float32), div_ice_shallow=shallow.astype(np.float32))
    if bool(D["has_tmin"]):
        out["div_tmin"] = np.where(has, cells(D["tmin_n"]) / np.maximum(N, 1), np.nan).astype(np.float32)
    print("Diviner cells with data:", int(has.sum()), "of", n * n,
          "Tavg K p5/50/95", np.nanpercentile(tavg, [5, 50, 95]).round(1), "ice share p50/95", np.nanpercentile(ice_frac, [50, 95]).round(3))
else:
    print("no Diviner file yet (run fetch_official.py); Moon thermal and ice traits keep the latitude model")

np.savez_compressed(os.path.join(raw, "grids", "moon_official.npz"), lat=lat_m, lon=lon_m, **out)
print("wrote", os.path.join(raw, "grids", "moon_official.npz"), sorted(out))
