"""Mars global and Moon south-pole terrain grids + base textures.
Mars: MGS MOLA 463 m DEM averaged to 1852 m, stats on a 1 deg grid (360 x 180), TES albedo.
Moon: LRO LOLA south pole 30 m DEM (75-90 S, polar stereographic) averaged to 1906 m (476 px),
      stats every 4 px (119 x 119 cells, about 7.6 km).
Usage: python 06_mars_moon_grids.py <raw_dir> <out_dir_npz> <web_assets_dir>
"""
import sys, os, numpy as np, rasterio
from rasterio.enums import Resampling
from PIL import Image
from terrainlib import equirect_grid_stats, window_stats, WIN

raw, outd, assets = sys.argv[1:4]
LOLA_SCALE = 0.5  # LOLA int16 DN -> metres

def hillshade(z, dx, az=315, alt=40, ex=1.0):
    gy, gx = np.gradient(z * ex, dx, dx)
    slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    a, al = np.radians(az), np.radians(alt)
    hs = np.sin(al) * np.cos(slope) + np.cos(al) * np.sin(slope) * np.cos(a - aspect - np.pi)
    return np.clip(hs, 0, 1)

# ------------------------------------------------------------------ Mars
with rasterio.open(os.path.join(raw, "mars_mola_463m.tif")) as d:
    mars = d.read(1, out_shape=(5760, 11520), resampling=Resampling.average).astype(np.float32)
print("mars dem", mars.shape, mars.min(), mars.max(), flush=True)
st = equirect_grid_stats(mars, None, 3396190.0, 32)          # 1 deg cells
with rasterio.open(os.path.join(raw, "mars_tes_albedo.tif")) as d:
    alb = d.read(1).astype(np.float32)
alb[alb < -1] = np.nan
alb1 = np.nanmean(alb.reshape(180, 8, 360, 8), axis=(1, 3))
alb1 = np.where(np.isnan(alb1), np.nanmean(alb1), alb1)
np.savez_compressed(os.path.join(outd, "mars_grid.npz"), slope=st["slope"], rough=st["rough"],
                    relief=st["relief"], elev=st["elev"], albedo=alb1.astype(np.float32))
for k in ("slope", "rough", "relief", "elev"):
    print("mars", k, np.percentile(st[k], [1, 50, 99]))
print("mars albedo", np.nanpercentile(alb1, [1, 50, 99]))
# texture 2048 x 1024: elevation colour ramp * hillshade * albedo tint
zt = mars.reshape(1024, 5.625 if False else 1, 1, 1) if False else None
with rasterio.open(os.path.join(raw, "mars_mola_463m.tif")) as d:
    zt = d.read(1, out_shape=(1024, 2048), resampling=Resampling.average).astype(np.float32)
hs = hillshade(zt, 3396190 * np.pi / 1024, ex=6)
t = np.clip((zt + 8000) / 20000, 0, 1)
lo = np.array([0.36, 0.20, 0.12]); mid = np.array([0.76, 0.45, 0.27]); hi = np.array([0.95, 0.80, 0.62])
col = np.where(t[..., None] < 0.5, lo + (mid - lo) * (t[..., None] / 0.5), mid + (hi - mid) * ((t[..., None] - 0.5) / 0.5))
albi = np.array(Image.fromarray(alb1).resize((2048, 1024), Image.BILINEAR))
shade = (0.35 + 0.75 * hs)[..., None] * (0.75 + 1.2 * (albi[..., None] - 0.18))
img = np.clip(col * shade * 255, 0, 255).astype(np.uint8)
Image.fromarray(img).save(os.path.join(assets, "mars.jpg"), quality=82, optimize=True)

# ------------------------------------------------------------------ Moon south pole
P = 476
with rasterio.open(os.path.join(raw, "moon_lola_spole75_30m.tif")) as d:
    moon = d.read(1, out_shape=(P, P), resampling=Resampling.average).astype(np.float32) * LOLA_SCALE
    hsz = d.read(1, out_shape=(1024, 1024), resampling=Resampling.average).astype(np.float32) * LOLA_SCALE
    b = d.bounds
mpp = (b.right - b.left) / P
print("moon dem", moon.shape, mpp, moon.min(), moon.max(), flush=True)
C = 4; n = P // C
ms = {k: np.full((n, n), np.nan, np.float32) for k in ("slope", "rough", "relief", "elev")}
half = WIN // 2 + 2
for i in range(n):
    for j in range(n):
        ci, cj = i * C + C // 2, j * C + C // 2
        r0, c0 = ci - half, cj - half
        if r0 < 0 or c0 < 0 or r0 + WIN + 4 > P or c0 + WIN + 4 > P:
            continue
        s = window_stats(moon[r0:r0 + WIN + 4, c0:c0 + WIN + 4], None, mpp, mpp)
        for k in ms: ms[k][i, j] = s[k]
np.savez_compressed(os.path.join(outd, "moon_grid.npz"), cell_px=C, mpp=mpp, P=P, bounds=np.array([b.left, b.bottom, b.right, b.top]), **ms)
for k in ms: print("moon", k, np.nanpercentile(ms[k], [1, 50, 99]))
hs = hillshade(hsz, (b.right - b.left) / 1024, az=315, alt=25)
t = np.clip((hsz + 7000) / 14000, 0, 1)
g = (0.12 + 0.88 * hs) * (0.8 + 0.3 * t)
img = np.clip(np.stack([g * 0.96, g * 0.97, g * 1.0], -1) * 255, 0, 255).astype(np.uint8)
Image.fromarray(img).save(os.path.join(assets, "moon_spole.jpg"), quality=80, optimize=True)
print("done")
