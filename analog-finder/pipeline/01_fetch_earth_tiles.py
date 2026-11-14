"""Download all zoom-7 AWS Terrain Tiles (Mapzen terrarium PNG) = global Earth elevation.
Source: https://registry.opendata.aws/terrain-tiles/ (SRTM, GMTED2010, ETOPO1, ArcticDEM ... mosaic)
Usage: python 01_fetch_earth_tiles.py <out_dir>
"""
import sys, os, concurrent.futures as cf, urllib.request, time
Z = 7
out = sys.argv[1] if len(sys.argv) > 1 else "../raw/terrarium7"
os.makedirs(out, exist_ok=True)
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

def get(xy):
    x, y = xy
    p = os.path.join(out, f"{x}_{y}.png")
    if os.path.exists(p) and os.path.getsize(p) > 100:
        return True
    for attempt in range(5):
        try:
            with urllib.request.urlopen(URL.format(z=Z, x=x, y=y), timeout=60) as r:
                data = r.read()
            with open(p + ".tmp", "wb") as f:
                f.write(data)
            os.replace(p + ".tmp", p)
            return True
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
    print("FAILED", x, y, flush=True)
    return False

n = 2 ** Z
jobs = [(x, y) for x in range(n) for y in range(n)]
with cf.ThreadPoolExecutor(24) as ex:
    ok = sum(ex.map(get, jobs))
print(f"{ok}/{len(jobs)} tiles ok")
