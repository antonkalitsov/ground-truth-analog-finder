"""Stage 2: re-rank the stage 1 candidates at 30 m.

Stage 1 (the app) scores 28 km cells. A lander needs a spot, not a 28 km square. For each fine target
(Jezero on Mars, the Artemis III regions and Shackleton's ridge on the Moon) this step:

  1. reproduces the app's top 10 new candidates for every purpose preset (same scoring, same picking rule);
  2. reads a 28 km window of the Copernicus GLO-30 terrain model around each candidate cell;
  3. slides a landing zone 8 km across (the size of the Perseverance landing ellipse, 7.7 x 6.6 km)
     over the window in 2 km steps and measures every placement at 30 m;
  4. keeps the placement whose terrain is closest to the target's own 8 km zone, measured the same way.

One grid (30 m), one zone (8 km disc), one function (zone_stats) on all three worlds:

  slope    distribution of slope in degrees (central differences, 60 m baseline, after a 3 x 3 mean
           that brings every source to about 90 m effective resolution)
  rough    RMS height difference at step lengths of 60, 150, 300 and 900 m
  relief   95th minus 5th percentile of elevation inside the zone

Similarity (0..1), mirroring the stage 1 tolerances:
  slope    1 - W / 3 deg, W = mean absolute difference between the two slope quantile curves
  rough    mean over the four step lengths of 1 - |log10(e+1) - log10(t+1)| / 0.35
  relief   1 - |log10(e+1) - log10(t+1)| / 0.35
The zone is chosen by fine = 0.4 slope + 0.4 rough + 0.2 relief. The app then replaces the three coarse
terrain similarities of stage 1 with these three and keeps every other trait, so purposes still apply.

Sources: Mars 2020 CTX terrain model, 20 m (USGS Astrogeology); LRO LOLA south pole, 30 m (USGS / NASA);
Copernicus GLO-30 and its water mask (ESA, AWS Open Data). All read straight from public buckets.

Polar close-ups: the live Earth close-up in the app comes from AWS Terrain Tiles, which poleward of about 60 degrees
are built from coarse GMTED2010 and look blurred. For every refined cell at or beyond 60 degrees this step also writes
a 28 km close-up from GLO-30 (256 px, about 109 m per pixel; int16 metres, each row stored as differences from the
previous pixel so it compresses better) to web/data/chips/earth/<cell>.bin.gz, and lists the cells in stage2.json.

Usage: python 09_stage2.py <raw_dir> <web_dir>
Writes web/data/stage2.json, replaces the Jezero close-up chip with the CTX one and notes it in manifest.json.
"""
import sys, os, json, gzip, math, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from scipy.ndimage import uniform_filter

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

GSD = 30.0                      # common ground sampling, metres
ZONE_KM = 8.0                   # landing zone diameter
CELL_KM = 28.0                  # stage 1 window
STEP_KM = 2.0                   # sliding step
LAGS_PX = (2, 5, 10, 30)        # 60, 150, 300, 900 m
QS = np.arange(1, 100)          # slope quantiles 1..99 %
TOL_SLOPE, TOL_LOG = 3.0, 0.35
W_FINE = (0.4, 0.4, 0.2)
STEEP_DEG = 15.0
R_MARS, R_MOON = 3396190.0, 1737400.0
CTX_URL = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif"
LOLA_URL = "https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/LRO/LOLA/ancillary/LRO_LOLA_DEM_SPole75_30m.tif"
GLO = "https://copernicus-dem-30m.s3.amazonaws.com/"
FINE_MARS = {"jezero-perseverance": dict(url=CTX_URL, file="jez_ctx_dtm20.tif", label="MRO CTX terrain model, 20 m (USGS Mars 2020)")}


# ------------------------------------------------------------------ the one shared measurement
def aeqd(lat, lon, radius=None):
    if radius:
        return CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +R={radius} +units=m +no_defs")
    return CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")


def local_grid(size_km):
    n = int(round(size_km * 1000 / GSD))
    return n, from_origin(-n * GSD / 2, n * GSD / 2, GSD, GSD)


def warp(src_path, lat, lon, size_km, radius=None, resampling=Resampling.bilinear, scale=1.0, dtype=np.float32, fill=np.nan):
    n, tf = local_grid(size_km)
    out = np.full((n, n), fill, dtype)
    with rasterio.open(src_path) as d:
        reproject(rasterio.band(d, 1), out, dst_transform=tf, dst_crs=aeqd(lat, lon, radius), dst_nodata=fill,
                  src_nodata=d.nodata, resampling=resampling)
    return out * scale if scale != 1.0 else out


def fields(z):
    """Per-pixel slope (deg) and squared height differences at each step length, from a 30 m grid."""
    zs = uniform_filter(z, 3, mode="nearest")
    gy = (zs[2:, 1:-1] - zs[:-2, 1:-1]) / (2 * GSD)
    gx = (zs[1:-1, 2:] - zs[1:-1, :-2]) / (2 * GSD)
    slope = np.full(z.shape, np.nan, np.float32)
    slope[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(gx, gy)))
    d2 = []
    for L in LAGS_PX:
        a = np.full(z.shape, np.nan, np.float32)
        h = L // 2
        dx = zs[:, L:] - zs[:, :-L]; dy = zs[L:, :] - zs[:-L, :]
        # centre both differences on the same pixel
        a[h:h + dy.shape[0], h:h + dx.shape[1]] = 0.5 * (dx[h:h + dy.shape[0], :] ** 2 + dy[:, h:h + dx.shape[1]] ** 2)
        d2.append(a)
    return zs, slope, d2


def disc_mask():
    r = int(round(ZONE_KM * 500 / GSD))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return r, (x * x + y * y) <= r * r


def zone_stats(zs, slope, d2, ci, cj, r, mask):
    sl = (slice(ci - r, ci + r + 1), slice(cj - r, cj + r + 1))
    s = slope[sl][mask]; z = zs[sl][mask]
    ok = np.isfinite(s) & np.isfinite(z)
    if ok.mean() < 0.98:
        return None
    s = s[ok]; z = z[ok]
    rough = [float(np.sqrt(np.nanmean(a[sl][mask]))) for a in d2]
    p5, p95 = np.percentile(z, [5, 95])
    return dict(q=np.percentile(s, QS).astype(np.float32), rough=rough, relief=float(p95 - p5),
                steep=float((s > STEEP_DEG).mean()), mean=float(s.mean()))


def fine_sim(e, t):
    lg = lambda v: math.log10(max(v, 0.0) + 1.0)
    s_slope = max(0.0, 1.0 - float(np.abs(e["q"] - t["q"]).mean()) / TOL_SLOPE)
    s_rough = float(np.mean([max(0.0, 1.0 - abs(lg(a) - lg(b)) / TOL_LOG) for a, b in zip(e["rough"], t["rough"])]))
    s_relief = max(0.0, 1.0 - abs(lg(e["relief"]) - lg(t["relief"])) / TOL_LOG)
    return s_slope, s_rough, s_relief


def summary(st):
    q = st["q"]
    return dict(p50=round(float(q[49]), 2), p90=round(float(q[89]), 2), steep=round(st["steep"], 4), relief=round(st["relief"], 1),
                rough=[round(v, 2) for v in st["rough"]], q=[round(float(q[k]), 2) for k in (4, 9, 24, 49, 74, 89, 94, 98)])


# ------------------------------------------------------------------ stage 1, exactly as web/js/score.js does it
class Pack:
    def __init__(self, data_dir):
        self.man = man = json.load(open(os.path.join(data_dir, "manifest.json")))
        raw = np.frombuffer(gzip.decompress(open(os.path.join(data_dir, "earth.bin.gz"), "rb").read()), np.uint8)
        g = man["grid"]; nx, ny, n = g["nx"], g["ny"], g["cells"]
        mb = (nx * ny + 7) // 8
        bits = np.unpackbits(raw[:mb], bitorder="little")[: nx * ny].astype(bool)
        self.p = np.flatnonzero(bits)                                   # flat grid index of every land cell
        self.lat = 90 - (self.p // nx + 0.5) * g["res"]; self.lon = -180 + (self.p % nx + 0.5) * g["res"]
        self.layer = {tid: raw[mb + i * n: mb + (i + 1) * n] for i, tid in enumerate(g["stored"])}
        self.T = {t["id"]: t for t in man["traits"]}
        deq = lambda tr, b: tr["min"] + (b / 255.0) * (tr["max"] - tr["min"])
        quant = lambda tr, v: np.clip(np.floor((self.toT(tr, v) - tr["min"]) / (tr["max"] - tr["min"]) * 255 + 0.5), 0, 255).astype(np.uint8)
        temp = deq(self.T["temp"], self.layer["temp"].astype(np.float64))
        self.layer["ice"] = quant(self.T["ice"], np.clip((1 - temp) / 7, 0, 1))
        self.layer["sun"] = quant(self.T["sun"], np.array([self.noon_sun(la, man["bodies"]["earth"]["obliquity"]) for la in 90 - (np.arange(ny) + 0.5) * g["res"]]))[self.p // nx]
        self.n = n

    @staticmethod
    def toT(tr, v):
        return np.log10(np.maximum(v, 0) + 1) if tr["transform"] == "log" else np.asarray(v, np.float64)

    @staticmethod
    def noon_sun(lat, obl, n=360):
        i = (np.arange(n) + 0.5) / n * 2 * np.pi
        decl = np.degrees(np.arcsin(np.sin(np.radians(obl)) * np.sin(i)))
        return float(np.maximum(0, 90 - np.abs(lat - decl)).mean())

    def lut(self, tr, tv):
        """Similarity of each of the 256 stored byte values to the target value (transformed units)."""
        e = tr["min"] + (np.arange(256) / 255.0) * (tr["max"] - tr["min"])
        if tr["transform"] == "cat":
            row = self.man["rock"]["matrix"][int(round(tv))]
            return np.array([row[int(round(v))] if int(round(v)) < len(row) and row[int(round(v))] is not None else 0 for v in e], np.float64)
        pct = np.linspace(0, 1, 101)
        if tv < tr["earthLo"]:
            return np.maximum(0, 1 - 2 * np.interp(e, tr["quant"], pct))
        if tv > tr["earthHi"]:
            return np.maximum(0, 1 - 2 * (1 - np.interp(e, tr["quant"], pct)))
        return np.maximum(0, 1 - np.abs(e - tv) / tr["tol"])

    def score(self, target, weights):
        out = np.zeros(self.n, np.float32); wsum = 0.0
        for tr in self.man["traits"]:
            w = weights.get(tr["id"], 0) or 0
            if w <= 0:
                continue
            l = (w * self.lut(tr, float(self.toT(tr, target[tr["id"]])))).astype(np.float32)
            out += l[self.layer[tr["id"]]]; wsum += w
        return out * np.float32(100 / (wsum or 1))

    def pick(self, sc, n=10, sep_km=300, exclude_km=150):
        hist = np.bincount(np.clip(np.floor(sc * 10 + 0.5), 0, 1000).astype(int), minlength=1001)
        acc = 0; thr = 0.0
        for b in range(1000, -1, -1):
            acc += hist[b]
            if acc >= 4000:
                thr = b / 10; break
        top = np.flatnonzero(sc >= thr)
        top = top[np.argsort(-sc[top], kind="stable")]
        kn = np.array([[k["lat"], k["lon"]] for k in self.man["known"]])
        picked = []
        for i in top:
            la, lo = self.lat[i], self.lon[i]
            if hav(la, lo, kn[:, 0], kn[:, 1]).min() < exclude_km:
                continue
            if any(hav(la, lo, self.lat[j], self.lon[j]) < sep_km for j in picked):
                continue
            picked.append(int(i))
            if len(picked) >= n:
                break
        return picked


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(np.minimum(1, a)))


# ------------------------------------------------------------------ Earth windows from Copernicus GLO-30
def glo_tiles(lat, lon, half_km):
    dlat = half_km / 111.0; dlon = min(180.0, half_km / (111.0 * max(0.02, math.cos(math.radians(lat)))))
    out = []
    for la in range(math.floor(lat - dlat), math.floor(lat + dlat) + 1):
        if la < -90 or la > 89:
            continue
        lons = range(-180, 180) if dlon >= 180 else range(math.floor(lon - dlon), math.floor(lon + dlon) + 1)
        for lo in lons:
            lo = (lo + 180) % 360 - 180
            out.append(f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00")
    return sorted(set(out))


def earth_window(lat, lon):
    """30 m elevation (NaN where there is no land tile) and water flag for a 30 km square centred on the cell."""
    size = CELL_KM + 2.0
    n, tf = local_grid(size); crs = aeqd(lat, lon)
    z = np.full((n, n), np.nan, np.float32); w = np.zeros((n, n), np.uint8)
    for name in glo_tiles(lat, lon, size * 0.75):
        for arr, url, rs, nod in ((z, f"{GLO}{name}_DEM/{name}_DEM.tif", Resampling.bilinear, np.nan),
                                  (w, f"{GLO}{name}_DEM/AUXFILES/{name}_WBM.tif", Resampling.nearest, 255)):
            try:
                with rasterio.open("/vsicurl/" + url) as d:
                    tmp = np.full((n, n), nod, arr.dtype)
                    reproject(rasterio.band(d, 1), tmp, dst_transform=tf, dst_crs=crs, dst_nodata=nod, resampling=rs)
                    if arr is z:
                        m = np.isfinite(tmp); arr[m] = tmp[m]
                    else:
                        tmp[tmp == 255] = 0; np.maximum(arr, tmp, out=arr)
            except rasterio.errors.RasterioIOError:
                pass                                                     # no tile: open sea
    return z, w


CHIP_PX, CHIP_MIN_LAT = 256, 60.0


def write_earth_chip(z, path):
    """28 km close-up from the 30 km window, row-differenced int16 (the app adds each row back up)."""
    from scipy.ndimage import zoom as rezoom
    n = z.shape[0]; c = n // 2; h = int(round(CELL_KM * 500 / GSD))
    a = z[c - h:c + h, c - h:c + h]
    a = np.where(np.isfinite(a), a, 0.0)
    a = rezoom(a, CHIP_PX / a.shape[0], order=1)[:CHIP_PX, :CHIP_PX].round().astype(np.int32)
    d = np.diff(a, axis=1, prepend=0).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(gzip.compress(d.tobytes(), 9))


def cell_placements(lat, lon, chip_path=None):
    """Zone statistics for every 8 km placement inside the 28 km cell. Target-independent, so computed once per cell."""
    z, water = earth_window(lat, lon)
    if chip_path and np.isfinite(z).any():
        write_earth_chip(z, chip_path)
    if not np.isfinite(z).any():
        return []
    zs, slope, d2 = fields(z)
    r, mask = disc_mask(); n = z.shape[0]; c = n // 2
    reach = (CELL_KM - ZONE_KM) / 2
    offs = np.arange(-reach, reach + 1e-6, STEP_KM)
    out = []
    for dy in offs:                 # km north
        for dx in offs:             # km east
            ci = c - int(round(dy * 1000 / GSD)); cj = c + int(round(dx * 1000 / GSD))
            sl = (slice(ci - r, ci + r + 1), slice(cj - r, cj + r + 1))
            if (water[sl][mask] > 0).mean() > 0.02:
                continue
            st = zone_stats(zs, slope, d2, ci, cj, r, mask)
            if st:
                st["dx"], st["dy"] = float(dx), float(dy); out.append(st)
    return out


def offset_latlon(lat, lon, dx_km, dy_km):
    la = lat + dy_km / 110.574
    lo = lon + dx_km / (111.320 * max(0.02, math.cos(math.radians(lat))))
    return round(la, 4), round((lo + 180) % 360 - 180, 4)


# ------------------------------------------------------------------ targets
def fetch(url, path):
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("  get", url, flush=True)
        urllib.request.urlretrieve(url, path)
    return path


def target_zone(z):
    zs, slope, d2 = fields(z)
    r, mask = disc_mask(); c = z.shape[0] // 2
    return zone_stats(zs, slope, d2, c, c, r, mask)


def main():
    raw, web = sys.argv[1:3]
    D = os.path.join(web, "data")
    P = Pack(D); man = P.man
    out = dict(version=1, gsdM=GSD, zoneKm=ZONE_KM, cellKm=CELL_KM, stepKm=STEP_KM, lagsM=[L * GSD for L in LAGS_PX],
               steepDeg=STEEP_DEG, tolSlopeDeg=TOL_SLOPE, tolLog=TOL_LOG, weights=list(W_FINE),
               earthSource="Copernicus GLO-30 (ESA), 30 m", targets={})

    # --- fine targets
    tstats = {}
    for t in man["targets"]:
        if t["body"] == "mars" and t["id"] in FINE_MARS:
            f = FINE_MARS[t["id"]]; path = fetch(f["url"], os.path.join(raw, "stage2", f["file"]))
            z = warp(path, t["lat"], t["lon"], ZONE_KM + 2.0, R_MARS, Resampling.average)
            src = f["label"]
            # sharper close-up for the side-by-side picture: 28 km at 320 px from the same model
            n = 320; tf = from_origin(-14000, 14000, 28000 / n, 28000 / n)
            chip = np.full((n, n), np.nan, np.float32)
            with rasterio.open(path) as d:
                reproject(rasterio.band(d, 1), chip, dst_transform=tf, dst_crs=aeqd(t["lat"], t["lon"], R_MARS), dst_nodata=np.nan,
                          src_nodata=d.nodata, resampling=Resampling.average)
            if np.isnan(chip).any():                                    # the model stops a little short of the window edge
                from scipy.ndimage import distance_transform_edt
                idx = distance_transform_edt(np.isnan(chip), return_distances=False, return_indices=True)
                chip = chip[tuple(idx)]
            open(os.path.join(D, "chips", t["id"] + ".bin.gz"), "wb").write(gzip.compress(np.round(chip).astype("<i2").tobytes(), 9))
            t["chip"] = dict(px=n, metersPerPixel=28000 / n, sizeKm=28.0, source="MRO CTX 20 m")
        elif t["body"] == "moon":
            z = warp("/vsicurl/" + LOLA_URL, t["lat"], t["lon"], ZONE_KM + 2.0, R_MOON, Resampling.bilinear, scale=0.5)
            src = "LRO LOLA south pole terrain model, 30 m"
        else:
            continue
        st = target_zone(z)
        if not st:
            print("  no fine terrain for", t["id"]); continue
        tstats[t["id"]] = st
        out["targets"][t["id"]] = dict(source=src, target=summary(st), cells={})
        print(f"target {t['id']:32s} p50 {st['q'][49]:5.2f} p90 {st['q'][89]:5.2f} relief {st['relief']:7.1f} rough {np.round(st['rough'], 2)}", flush=True)

    # --- stage 1 candidates for every purpose
    need = {}                                                           # land cell index -> targets that list it
    for t in man["targets"]:
        if t["id"] not in tstats:
            continue
        for pr in man["presets"]:
            for i in P.pick(P.score(t["traits"], pr["weights"])):
                need.setdefault(i, set()).add(t["id"])
    print(len(need), "candidate cells to refine", flush=True)

    # --- stage 2
    def work(i):
        try:
            la = float(P.lat[i])
            chip = os.path.join(D, "chips", "earth", f"{int(P.p[i])}.bin.gz") if abs(la) >= CHIP_MIN_LAT else None
            return i, cell_placements(la, float(P.lon[i]), chip)
        except Exception as e:                                         # one bad window must not stop the run
            print("  failed", i, type(e).__name__, e, flush=True); return i, []
    done = 0
    with ThreadPoolExecutor(8) as ex:
        for i, pl in ex.map(work, sorted(need)):
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(need)}", flush=True)
            for tid in need[i]:
                best = None
                for st in pl:
                    s = fine_sim(st, tstats[tid]); f = sum(a * b for a, b in zip(W_FINE, s))
                    if best is None or f > best[0]:
                        best = (f, s, st)
                key = str(int(P.p[i]))
                if best is None:
                    out["targets"][tid]["cells"][key] = None            # sea, ice shelf edge or no data: not refined
                    continue
                f, s, st = best
                la, lo = offset_latlon(float(P.lat[i]), float(P.lon[i]), st["dx"], st["dy"])
                out["targets"][tid]["cells"][key] = dict(lat=la, lon=lo, dx=st["dx"], dy=st["dy"], fine=round(100 * f, 1),
                                                         sim=[round(v, 3) for v in s], n=len(pl), **summary(st))
    chips = sorted(int(f.split(".")[0]) for f in os.listdir(os.path.join(D, "chips", "earth"))) if os.path.isdir(os.path.join(D, "chips", "earth")) else []
    out["earthChips"] = dict(px=CHIP_PX, sizeKm=CELL_KM, minAbsLat=CHIP_MIN_LAT, encoding="int16 metres, row differences",
                             source="Copernicus GLO-30 (ESA)", cells=chips)
    json.dump(out, open(os.path.join(D, "stage2.json"), "w"), separators=(",", ":"), allow_nan=False)
    json.dump(man, open(os.path.join(D, "manifest.json"), "w"), separators=(",", ":"))
    print("wrote stage2.json", os.path.getsize(os.path.join(D, "stage2.json")), "bytes")


if __name__ == "__main__":
    main()
