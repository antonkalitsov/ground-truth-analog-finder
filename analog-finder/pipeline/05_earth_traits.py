"""Build every Earth trait layer on the 0.25 degree global grid (1440 x 720, row 0 = 90N).
Usage: python 05_earth_traits.py <raw_dir> <out.npz>
"""
import sys, json, os, numpy as np
from rasterio import features
from rasterio.transform import from_origin
from terrainlib import equirect_grid_stats, mean_noon_sun_elevation

raw, out = sys.argv[1], sys.argv[2]
NX, NY = 1440, 720
lat_c = 90 - (np.arange(NY) + 0.5) * 0.25
lon_c = -180 + (np.arange(NX) + 0.5) * 0.25

# ---------------------------------------------------------------- land mask at 1 arc-minute
def shapes(name, prop=None):
    gj = json.load(open(os.path.join(raw, "ne", name + ".geojson"), encoding="utf-8"))
    return gj["features"]

tr1 = from_origin(-180, 90, 1 / 60, 1 / 60)
land = features.rasterize(((f["geometry"], 1) for f in shapes("ne_10m_land") if f["geometry"]),
                          out_shape=(10800, 21600), transform=tr1, fill=0, dtype="uint8")
lakes = features.rasterize(((f["geometry"], 1) for f in shapes("ne_10m_lakes") if f["geometry"]),
                           out_shape=(10800, 21600), transform=tr1, fill=0, dtype="uint8")
shelf = features.rasterize(((f["geometry"], 1) for f in shapes("ne_10m_antarctic_ice_shelves_polys") if f["geometry"]),
                           out_shape=(10800, 21600), transform=tr1, fill=0, dtype="uint8")
glac = features.rasterize(((f["geometry"], 1) for f in shapes("ne_10m_glaciated_areas") if f["geometry"]),
                          out_shape=(10800, 21600), transform=tr1, fill=0, dtype="uint8")
dem = np.load(os.path.join(raw, "earth_1min.npy"))
has = dem != -32768
solid = (land == 1) & (lakes == 0) & (shelf == 0) & has
print("land px frac", solid.mean(), flush=True)
z = np.where(solid, dem, 0).astype(np.float32)

def blockmean(a, f=15):
    return a.reshape(NY, f, NX, f).mean((1, 3)).astype(np.float32)

landfrac = blockmean(solid.astype(np.float32))
glacfrac = blockmean(((glac == 1) & solid).astype(np.float32)) / np.maximum(landfrac, 1e-6)

# ---------------------------------------------------------------- terrain
t = equirect_grid_stats(z, solid, 6371008.8, 15, log=lambda s: print(s, flush=True))

# ---------------------------------------------------------------- climate (NASA POWER climatology)
def load(name):
    return np.load(os.path.join(raw, "power", name + ".npy"))

def regrid(a, lat, lon):
    """bilinear from a (lat ascending, lon ascending) grid to the 0.25 deg grid; NaN-aware; wraps lon"""
    a = np.where(np.isnan(a), np.nanmean(a), a)
    fi = np.interp(lat_c, lat, np.arange(len(lat)))
    dl = lon[1] - lon[0]
    fj = ((lon_c - lon[0]) / dl) % len(lon)
    i0 = np.floor(fi).astype(int); i1 = np.minimum(i0 + 1, len(lat) - 1); wi = (fi - i0)[:, None]
    j0 = np.floor(fj).astype(int) % len(lon); j1 = (j0 + 1) % len(lon); wj = (fj - np.floor(fj))[None, :]
    return ((a[i0][:, j0] * (1 - wj) + a[i0][:, j1] * wj) * (1 - wi) + (a[i1][:, j0] * (1 - wj) + a[i1][:, j1] * wj) * wi).astype(np.float32)

mlat, mlon = load("merra2_lat"), load("merra2_lon")
slat, slon = load("syn1deg_lat"), load("syn1deg_lon")
ANN = 12
T2M = regrid(load("merra2_T2M")[ANN], mlat, mlon)
TRANGE = regrid(load("merra2_T2M_RANGE")[ANN], mlat, mlon)
PREC = regrid(load("merra2_PRECTOTCORR")[ANN], mlat, mlon) * 365.25      # mm / year
PS = regrid(load("merra2_PS")[ANN], mlat, mlon)                           # hPa (MERRA-2 model surface)
WIND = regrid(load("merra2_WS10M")[ANN], mlat, mlon)
WET = regrid(load("merra2_GWETTOP")[ANN], mlat, mlon)
ALB = regrid(load("syn1deg_ALLSKY_SRF_ALB")[ANN], slat, slon)
AOD = regrid(load("syn1deg_AOD_55")[ANN], slat, slon)
UV = regrid(load("syn1deg_ALLSKY_SFC_UV_INDEX")[ANN], slat, slon)
# warmest / coldest month means
t12 = load("merra2_T2M")[:12]
TWARM = regrid(t12.max(0), mlat, mlon); TCOLD = regrid(t12.min(0), mlat, mlon)

# downscale temperature with a standard lapse rate, using the height of the MERRA-2 model surface
h_model = 44330.8 * (1 - (PS / 1013.25) ** 0.190263)
elev = t["elev"]
dz = np.where(np.isnan(elev), 0, elev - h_model)
dz = np.clip(dz, -2500, 2500)
temp = T2M - 0.0065 * dz
twarm = TWARM - 0.0065 * dz
# pressure from our own elevation (ICAO standard atmosphere), kPa
pressure = 101.325 * (1 - 2.25577e-5 * np.clip(np.nan_to_num(elev), -500, 9000)) ** 5.25588

# ---------------------------------------------------------------- land cover (ESA WorldCover)
wc = np.load(os.path.join(raw, "worldcover_025.npz"))
frac, total, classes = wc["frac"], wc["total"], list(wc["classes"])
ci = {c: i for i, c in enumerate(classes)}
water = frac[ci[80]]
nonwater = np.maximum(1 - water, 1e-3)
# barren index: bare/sparse 1, moss & lichen 0.7, shrubland and grassland 0.4 (sparse desert scrub), everything else 0
bare = (frac[ci[60]] + 0.7 * frac[ci[100]] + 0.4 * (frac[ci[20]] + frac[ci[30]])) / nonwater
snow = frac[ci[70]] / nonwater
veg = (frac[ci[10]] + frac[ci[20]] + frac[ci[30]] + frac[ci[40]] + frac[ci[90]] + frac[ci[95]] + frac[ci[100]]) / nonwater
nowc = total < 50
# no WorldCover (Antarctica): Natural Earth glaciated areas give ice vs. exposed rock
bare = np.where(nowc, 1 - glacfrac, bare); snow = np.where(nowc, glacfrac, snow); veg = np.where(nowc, 0, veg)

# ---------------------------------------------------------------- illumination and ground ice
sun = np.repeat(mean_noon_sun_elevation(lat_c, 23.44)[:, None], NX, 1).astype(np.float32)
# ground-ice (permafrost) likelihood from mean annual air temperature: continuous below -6 C, none above +1 C
ice = np.clip((1.0 - temp) / 7.0, 0, 1).astype(np.float32)

ok = (landfrac >= 0.3) & ~np.isnan(t["slope"])
print("land cells:", int(ok.sum()), flush=True)
np.savez_compressed(out, ok=ok, landfrac=landfrac, lat=lat_c, lon=lon_c,
                    slope=t["slope"], rough=t["rough"], relief=t["relief"], elev=elev,
                    albedo=ALB, bare=bare.astype(np.float32), snow=snow.astype(np.float32), veg=veg.astype(np.float32),
                    temp=temp.astype(np.float32), twarm=twarm.astype(np.float32), trange=TRANGE, precip=PREC,
                    pressure=pressure.astype(np.float32), uv=UV, dust=AOD, wind=WIND, wet=WET, sun=sun, ice=ice)
for k in ["slope", "rough", "relief", "elev", "albedo", "bare", "snow", "temp", "trange", "precip", "pressure", "uv", "dust", "wind", "sun", "ice"]:
    a = np.load(out)[k][ok]
    print(f"{k:9s} p1={np.nanpercentile(a,1):9.2f} p50={np.nanpercentile(a,50):9.2f} p99={np.nanpercentile(a,99):9.2f} min={np.nanmin(a):9.2f} max={np.nanmax(a):9.2f} nan={int(np.isnan(a).sum())}")
