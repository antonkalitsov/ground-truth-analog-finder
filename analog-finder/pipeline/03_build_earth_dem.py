"""Mosaic the zoom-7 terrarium tiles (Web Mercator) and reproject to a global 1 arc-minute
equirectangular elevation grid (21600 x 10800, int16 metres, row 0 = 90N).
Usage: python 03_build_earth_dem.py <tiles_dir> <out.npy>
"""
import sys, os, numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio.crs import CRS

tiles, out = sys.argv[1], sys.argv[2]
Z = 7; n = 2 ** Z; T = 256
mosaic = np.zeros((n * T, n * T), dtype=np.int16)

def load(xy):
    x, y = xy
    a = np.asarray(Image.open(os.path.join(tiles, f"{x}_{y}.png")).convert("RGB"), dtype=np.float32)
    elev = a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0
    mosaic[y * T:(y + 1) * T, x * T:(x + 1) * T] = np.round(elev).astype(np.int16)

with ThreadPoolExecutor(4) as ex:
    list(ex.map(load, [(x, y) for x in range(n) for y in range(n)]))
print("mosaic", mosaic.shape, mosaic.min(), mosaic.max(), flush=True)

R = 20037508.342789244
src_tr = from_origin(-R, R, 2 * R / (n * T), 2 * R / (n * T))
W, H = 21600, 10800
dst = np.full((H, W), -32768, dtype=np.int16)
dst_tr = from_origin(-180.0, 90.0, 1 / 60, 1 / 60)
reproject(mosaic, dst, src_transform=src_tr, src_crs=CRS.from_epsg(3857),
          dst_transform=dst_tr, dst_crs=CRS.from_epsg(4326),
          resampling=Resampling.average, dst_nodata=-32768, num_threads=4)
print("dem", dst.shape, "nodata rows top:", int((dst[:, 0] == -32768).argmin()),
      "valid frac", float((dst != -32768).mean()), dst[dst != -32768].min(), dst.max(), flush=True)
np.save(out, dst)
