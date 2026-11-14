"""ESA WorldCover 2021 v200 (10 m land cover, AWS Open Data) -> class fractions on a 0.25 deg grid.
Reads only the coarsest COG overview of every 3x3 degree tile (about 600 m pixels) over HTTP.
Usage: python 04_fetch_worldcover.py <out.npz>
Output: frac[class_index, 720, 1440] float32 (row 0 = 90N), classes list, valid mask.
"""
import sys, re, urllib.request, numpy as np, rasterio, time
from concurrent.futures import ThreadPoolExecutor

out = sys.argv[1]
B = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
CLASSES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
keys, token = [], None
while True:
    u = B + "?list-type=2&prefix=v200/2021/map/" + (("&continuation-token=" + urllib.request.quote(token, safe="")) if token else "")
    x = urllib.request.urlopen(u, timeout=60).read().decode()
    keys += re.findall(r"<Key>([^<]+_Map\.tif)</Key>", x)
    m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
    if not m: break
    token = m.group(1)
print(len(keys), "tiles", flush=True)

counts = np.zeros((len(CLASSES), 720, 1440), dtype=np.float32)
total = np.zeros((720, 1440), dtype=np.float32)
P = 45  # pixels per 0.25 deg cell after decimation

def work(k):
    m = re.search(r"_([NS])(\d\d)([EW])(\d\d\d)_Map", k)
    lat0 = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon0 = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    for a in range(4):
        try:
            with rasterio.open(B + k) as ds:
                arr = ds.read(1, out_shape=(12 * P, 12 * P))
            break
        except Exception as e:
            time.sleep(2 + a); arr = None
    if arr is None:
        print("FAILED", k, flush=True); return
    blocks = arr.reshape(12, P, 12, P).transpose(0, 2, 1, 3).reshape(12, 12, P * P)
    r0 = int(round((90 - (lat0 + 3)) * 4)); c0 = int(round((lon0 + 180) * 4))
    for i, c in enumerate(CLASSES):
        counts[i, r0:r0 + 12, c0:c0 + 12] += (blocks == c).sum(-1)
    total[r0:r0 + 12, c0:c0 + 12] += (blocks != 0).sum(-1)

with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="3"):
    with ThreadPoolExecutor(16) as ex:
        for i, _ in enumerate(ex.map(work, keys)):
            if i % 300 == 0: print(i, flush=True)
frac = counts / np.maximum(total, 1)
np.savez_compressed(out, frac=frac, total=total, classes=np.array(CLASSES))
print("done; cells with data:", int((total > 0).sum()))
