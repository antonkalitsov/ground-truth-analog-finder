"""Fill the south polar cap of the Moon globe texture (web/assets/moon.jpg, equirectangular Kaguya TC mosaic) from the
LROC WAC south-pole mosaic (web/assets/moon_spole.jpg, polar stereographic, 75-90 S). The Kaguya mosaic breaks up into
streaks of shadow poleward of about 80 S; the WAC polar mosaic is clean there, and the pole is where the targets are.

Usage: python 06c_moon_texture_pole.py <web_assets_dir>     (run once; rewrites moon.jpg in place)
"""
import sys, os, numpy as np
from PIL import Image

assets = sys.argv[1]
R, HALF = 1737400.0, 457440.0                      # lunar radius, half-width of the polar image (m)
eq = np.asarray(Image.open(os.path.join(assets, "moon.jpg")).convert("L")).astype(np.float32)
sp = np.asarray(Image.open(os.path.join(assets, "moon_spole.jpg")).convert("L")).astype(np.float32)
H, W = eq.shape; N = sp.shape[0]
lat = 90 - (np.arange(H) + 0.5) * 180 / H
lon = (np.arange(W) + 0.5) * 360 / W - 180
rows = np.where(lat < -75.2)[0]
LA, LO = np.meshgrid(np.radians(lat[rows]), np.radians(lon), indexing="ij")
rho = 2 * R * np.tan((np.pi / 2 + LA) / 2)
x, y = rho * np.sin(LO), rho * np.cos(LO)
px = np.clip((x + HALF) / (2 * HALF) * N - 0.5, 0, N - 1.001); py = np.clip((HALF - y) / (2 * HALF) * N - 0.5, 0, N - 1.001)
x0, y0 = px.astype(int), py.astype(int); fx, fy = px - x0, py - y0
s = (sp[y0, x0] * (1 - fx) * (1 - fy) + sp[y0, x0 + 1] * fx * (1 - fy) + sp[y0 + 1, x0] * (1 - fx) * fy + sp[y0 + 1, x0 + 1] * fx * fy)
# match brightness and contrast to the Kaguya mosaic over the blend band, then cross-fade 75.2 -> 79 S
band = (lat[rows] > -79)
k = eq[rows][band]; w = s[band]
s = (s - w.mean()) * min(1.5, k.std() / max(w.std(), 1e-3)) + k.mean()
t = np.clip((-75.2 - lat[rows]) / 3.8, 0, 1)[:, None]
out = eq.copy(); out[rows] = eq[rows] * (1 - t) + s * t
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(assets, "moon.jpg"), quality=82, optimize=True)
print("moon.jpg south cap replaced from LROC WAC,", len(rows), "rows")
