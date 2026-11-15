"""Build the browser data pack (web/data) from the trait grids.
Usage: python 07_build_pack.py <raw_dir> <web_dir>
"""
import sys, os, json, gzip, numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from rasterio.warp import transform as wtransform
from rasterio import features
from rasterio.transform import from_origin
from terrainlib import window_stats, WIN
import traits as T

raw, web = sys.argv[1:3]
D = os.path.join(web, "data"); os.makedirs(os.path.join(D, "chips"), exist_ok=True)
E = np.load(os.path.join(raw, "earth_traits.npz"))
ok = E["ok"]; NY, NX = ok.shape
lat_c, lon_c = E["lat"], E["lon"]
LAT = np.repeat(lat_c[:, None], NX, 1)
earth = dict(slope=E["slope"], rough=E["rough"], relief=E["relief"], albedo=E["albedo"], bare=E["bare"],
             icecover=E["snow"], temp=E["temp"], trange=E["trange"], sun=E["sun"], ice=T.earth_ice(E["temp"]),
             dry=E["precip"], soil=E["wet"], dust=E["dust"], wind=E["wind"], pressure=T.earth_pressure(E["elev"]))
SOURCES = {}
# official challenge datasets (JAXA G-Portal / EORC / JASMES via the JAXA Earth API, GLiM), built by 05b_official_earth.py
OFF = os.path.join(raw, "earth_official.npz")
if os.path.exists(OFF):
    O = np.load(OFF, allow_pickle=True)
    for k in O.files:
        if k in ("sources",): continue
        if k in earth or k in ("ndvi", "rock"):
            earth[k] = O[k]; print("official layer replaces/adds", k)
    SOURCES = O["sources"].item() if "sources" in O.files else {}
ACTIVE = [t for t in T.TRAITS if t[0] in earth]
TIDS = [t[0] for t in ACTIVE]
STORED = [t for t in ["slope", "rough", "relief", "albedo", "bare", "icecover", "temp", "trange", "dry", "soil", "dust", "wind", "ndvi", "rock"] if t in earth]  # sun, ice, pressure derived in JS
ELEV = ("elev", -500.0, 7000.0)

# ---------------------------------------------------------------- earth pack
idx = np.flatnonzero(ok.ravel())
bits = np.packbits(ok.ravel().astype(np.uint8), bitorder="little")
layers = [T.quantize(t, earth[t].ravel()[idx]) for t in STORED]
qelev = np.clip(np.round((E["elev"].ravel()[idx] - ELEV[1]) / (ELEV[2] - ELEV[1]) * 255), 0, 255).astype(np.uint8)
blob = bits.tobytes() + b"".join(l.tobytes() for l in layers) + qelev.tobytes()
open(os.path.join(D, "earth.bin.gz"), "wb").write(gzip.compress(blob, 9))
print("earth cells", len(idx), "pack", os.path.getsize(os.path.join(D, "earth.bin.gz")))

# earth range in transformed units (from the quantised values so JS and Python agree)
def deq_all(tid):
    if tid in STORED:
        return T.dequant_t(tid, layers[STORED.index(tid)])
    return T.to_t(tid, earth[tid].ravel()[idx])
earth_t = {t: deq_all(t) for t in TIDS}
# derived layers in JS are computed from dequantised inputs; mirror that here
elev_d = ELEV[1] + qelev / 255 * (ELEV[2] - ELEV[1])
temp_d = T.dequant_t("temp", layers[STORED.index("temp")])
earth_t["pressure"] = T.to_t("pressure", T.earth_pressure(elev_d))
earth_t["ice"] = T.to_t("ice", T.earth_ice(temp_d))
earth_t["sun"] = T.to_t("sun", earth["sun"].ravel()[idx])
lo = {t: float(np.percentile(earth_t[t], 1)) for t in TIDS}
hi = {t: float(np.percentile(earth_t[t], 99)) for t in TIDS}
quant = {t: [round(float(x), 5) for x in np.percentile(earth_t[t], np.arange(101))] for t in TIDS}
for t in ACTIVE:
    if t[4] == "cat": lo[t[0]], hi[t[0]] = -1e9, 1e9

# ---------------------------------------------------------------- names grid (admin1 + admin0 + geographic region)
def ne(name):
    return json.load(open(os.path.join(raw, "ne", name + ".geojson"), encoding="utf-8"))["features"]
tr = from_origin(-180, 90, 0.25, 0.25)
names = [""]; nid = {}
def code(s):
    if s not in nid: nid[s] = len(names); names.append(s)
    return nid[s]
def rast(feats, key):
    sh = [(f["geometry"], code(f["properties"].get(key) or "")) for f in feats if f["geometry"]]
    return features.rasterize(sh, out_shape=(NY, NX), transform=tr, fill=0, dtype="int32", all_touched=True)
a0 = rast(ne("ne_10m_admin_0_countries"), "NAME")
a1 = rast(ne("ne_10m_admin_1_states_provinces"), "name")
rg = rast([f for f in ne("ne_10m_geography_regions_polys") if f["properties"].get("SCALERANK", 9) <= 6], "NAME")
nm = np.stack([a1.ravel()[idx], a0.ravel()[idx], rg.ravel()[idx]]).astype(np.uint16)
open(os.path.join(D, "names.bin.gz"), "wb").write(gzip.compress(nm.tobytes(), 9))
json.dump(names, open(os.path.join(D, "names.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("names", len(names), os.path.getsize(os.path.join(D, "names.bin.gz")))

# ---------------------------------------------------------------- Mars + Moon grids (full trait vectors)
G = os.path.join(raw, "grids")
M = np.load(os.path.join(G, "mars_grid.npz"))
mlat = np.repeat((90 - (np.arange(180) + 0.5))[:, None], 360, 1)
mv = T.mars_model(mlat, M["elev"], M["albedo"], M["slope"], M["rough"], M["relief"])
marsq = np.stack([T.quantize(t, mv[t]) for t in TIDS])
open(os.path.join(D, "mars_grid.bin.gz"), "wb").write(gzip.compress(marsq.tobytes(), 9))
L = np.load(os.path.join(G, "moon_grid.npz"))
n = L["slope"].shape[0]; P = int(L["P"]); C = int(L["cell_px"]); left, bottom, right, top = L["bounds"]
mpp = (right - left) / P
xs = left + (np.arange(n) * C + C / 2 + 0.5) * mpp
ys = top - (np.arange(n) * C + C / 2 + 0.5) * mpp
X, Y = np.meshgrid(xs, ys)
MOONCRS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
MOONGEO = "+proj=longlat +R=1737400 +no_defs"
lon_m, lat_m = wtransform(MOONCRS, MOONGEO, X.ravel(), Y.ravel())
lat_m = np.array(lat_m).reshape(n, n); lon_m = np.array(lon_m).reshape(n, n)
valid_m = ~np.isnan(L["slope"]) & (lat_m <= -75.3)
MO = np.load(os.path.join(G, "moon_official.npz")) if os.path.exists(os.path.join(G, "moon_official.npz")) else None
moon_rock = MO["rock"] if MO is not None and "rock" in MO.files else None
moon_div = dict(tavg=MO["div_tavg"], tmax=MO["div_tmax"], ice=MO["div_ice"]) if MO is not None and "div_tavg" in MO.files else None
lv = T.moon_model(lat_m, L["elev"], np.nan_to_num(L["slope"]), np.nan_to_num(L["rough"]), np.nan_to_num(L["relief"]), rock=moon_rock, diviner=moon_div)
moonq = np.stack([T.quantize(t, lv[t]) for t in TIDS])
moonq[:, ~valid_m] = 0
moon_unit = (MO["geo_unit"].astype(np.uint8) if moon_rock is not None else np.zeros((n, n), np.uint8))
moon_div_has = (np.isfinite(moon_div["tavg"]).astype(np.uint8) if moon_div is not None else np.zeros((n, n), np.uint8))
open(os.path.join(D, "moon_grid.bin.gz"), "wb").write(gzip.compress(valid_m.astype(np.uint8).tobytes() + moonq.tobytes() + moon_unit.tobytes() + moon_div_has.tobytes(), 9))
def moon_cell(x, y):
    j = int((x - left) / mpp / C); i = int((top - y) / mpp / C)
    return min(n - 1, max(0, i)), min(n - 1, max(0, j))

# ---------------------------------------------------------------- named targets + chips
targets = [t for t in json.load(open("targets.json")) if not (t["body"] == "moon" and t["lat"] > -75.5)]
with rasterio.open(os.path.join(raw, "mars_mola_463m.tif")) as d:
    mars_dem = d.read(1, out_shape=(5760, 11520), resampling=Resampling.average).astype(np.float32)
with rasterio.open(os.path.join(raw, "moon_lola_spole75_30m.tif")) as d:
    moon_dem = d.read(1, out_shape=(P, P), resampling=Resampling.average).astype(np.float32) * 0.5
MARS_R = 3396190.0
alb_grid = M["albedo"]
CHIP_KM = 28.0
for t in targets:
    if t["body"] == "mars":
        H, W = mars_dem.shape; my = np.pi * MARS_R / H
        k = max(1, round(1 / np.cos(np.radians(t["lat"]))))
        r = int((90 - t["lat"]) / 180 * H); c = int((t["lon"] + 180) / 360 * W)
        h = WIN // 2 + 2
        rows = np.clip(np.arange(r - h, r - h + WIN + 4), 0, H - 1)
        cols = (c + (np.arange(-(WIN // 2 + 2) * k, (WIN // 2 + 3) * k))) % W
        sub = mars_dem[np.ix_(rows, cols)][:, :((WIN + 4) * k)].reshape(len(rows), WIN + 4, k).mean(-1)
        s = window_stats(sub, None, k * my * np.cos(np.radians(t["lat"])), my)
        a = float(alb_grid[min(179, int(90 - t["lat"])), min(359, int(t["lon"] + 180))])
        rk = T.MARS_SITE_ROCK.get(t["id"], "basalt"); t["rock"] = rk
        v = T.mars_model(np.array(t["lat"]), np.array(s["elev"]), np.array(a), s["slope"], s["rough"], s["relief"], ice_flag=np.array(t["ice"]), rock=np.array(T.FAMILY.index(rk)))
        if t["id"] in T.MARS_SITE_MEASURED:                     # lander measurements replace the latitude model
            ms = T.MARS_SITE_MEASURED[t["id"]]; v.update({k: np.array(x) for k, x in ms["values"].items()})
            t["measured"] = dict(label=ms["label"], traits=sorted(ms["values"]), refs=ms["refs"])
        # chip from the native 463 m DEM
        with rasterio.open(os.path.join(raw, "mars_mola_463m.tif")) as d:
            px_m = 463.0836
            ny = int(round(CHIP_KM * 1000 / px_m)); nx = int(round(ny / np.cos(np.radians(t["lat"]))))
            rr = int((90 - t["lat"]) / 180 * d.height); cc = int((t["lon"] + 180) / 360 * d.width)
            chip = d.read(1, window=Window(cc - nx // 2, rr - ny // 2, nx, ny), out_shape=(96, 96), resampling=Resampling.bilinear, boundless=True, fill_value=-32768)
    else:
        x, y = wtransform(MOONGEO, MOONCRS, [t["lon"]], [t["lat"]])
        cj = (x[0] - left) / mpp; ci = (top - y[0]) / mpp
        h = WIN // 2 + 2; r0 = int(round(ci)) - h; c0 = int(round(cj)) - h
        s = window_stats(moon_dem[r0:r0 + WIN + 4, c0:c0 + WIN + 4], None, mpp, mpp)
        ci_, cj_ = moon_cell(x[0], y[0])
        rk = T.FAMILY[int(moon_rock[ci_, cj_])] if moon_rock is not None else "highland"; t["rock"] = rk
        if moon_rock is not None:
            u = int(MO["geo_unit"][ci_, cj_]); t["geoUnit"] = dict(code=str(MO["unit_codes"][u]), name=str(MO["unit_names"][u]), age=str(MO["unit_ages"][u]))
        dv = {k: np.array(moon_div[k][ci_, cj_]) for k in moon_div} if moon_div is not None else None
        if dv is not None and np.isfinite(dv["tavg"]): t["diviner"] = dict(tavgK=round(float(dv["tavg"]), 1), tmaxK=round(float(dv["tmax"]), 1), iceShare=round(float(dv["ice"]), 3))
        v = T.moon_model(np.array(t["lat"]), np.array(s["elev"]), s["slope"], s["rough"], s["relief"], ice_flag=np.array(t["ice"]), rock=np.array(T.FAMILY.index(rk)), diviner=dv)
        with rasterio.open(os.path.join(raw, "moon_lola_spole75_30m.tif")) as d:
            npx = int(round(CHIP_KM * 1000 / 30.0))
            col = int((x[0] - left) / 30.0); row = int((top - y[0]) / 30.0)
            chip = d.read(1, window=Window(col - npx // 2, row - npx // 2, npx, npx), out_shape=(192, 192), resampling=Resampling.average).astype(np.float32) * 0.5
            chip = np.round(chip).astype(np.int16)
    open(os.path.join(D, "chips", t["id"] + ".bin.gz"), "wb").write(gzip.compress(chip.astype("<i2").tobytes(), 9))
    t["chip"] = dict(px=int(chip.shape[0]), metersPerPixel=CHIP_KM * 1000 / chip.shape[0], sizeKm=CHIP_KM)
    t["traits"] = {k: round(float(np.asarray(v[k]).ravel()[0]), 4) for k in TIDS}
    t["elev"] = round(float(s["elev"]), 1)
    print(t["id"], {k: round(float(np.asarray(v[k]).ravel()[0]), 2) for k in ("slope", "rough", "relief", "temp", "sun", "ice")})

# ---------------------------------------------------------------- manifest
known = json.load(open("known_sites.json"))
manifest = dict(
    version=1,
    grid=dict(nx=NX, ny=NY, res=0.25, cells=int(len(idx)), stored=STORED, elev=dict(min=ELEV[1], max=ELEV[2])),
    traits=[dict(id=t[0], label=t[1], unit=t[2], group=t[3], transform=t[4], min=t[5], max=t[6], tol=t[7],
                 earthLo=lo[t[0]], earthHi=hi[t[0]], quant=quant[t[0]]) for t in ACTIVE],
    rock=dict(families=T.FAMILY, familyLabels=[T.FAMILY_LABEL[f] for f in T.FAMILY], classes=T.GLIM,
              classLabels=[T.GLIM_LABEL[g] for g in T.GLIM], matrix=T.ROCK_MATRIX.round(3).tolist()),
    moonUnits=dict(codes=[str(c) for c in MO["unit_codes"]], names=[str(c) for c in MO["unit_names"]], ages=[str(c) for c in MO["unit_ages"]]) if moon_rock is not None else None,
    moonDiviner=moon_div is not None,
    sources=SOURCES,
    presets=[dict(id=k, label=v[0], blurb=v[1], weights=v[2]) for k, v in T.PRESETS.items()],
    bodies=T.BODY,
    marsGrid=dict(nx=360, ny=180, res=1.0),
    moonGrid=dict(n=int(n), cellPx=C, P=P, mpp=float(mpp), left=float(left), top=float(top), R=1737400.0),
    targets=targets, known=known,
)
json.dump(manifest, open(os.path.join(D, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
np.savez_compressed(os.path.join(raw, "earth_t.npz"), idx=idx, **{k: v.astype(np.float32) for k, v in earth_t.items()})
os.system(f"du -sh {D}; ls -la {D}")
