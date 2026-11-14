"""Sharper pictures for the interface, without touching the scores.

  * Moon target close-ups: re-read from the LRO LOLA 30 m south-pole DEM at 512 x 512 px (55 m per pixel) instead of 192.
  * Mars target close-ups: MGS MOLA is 463 m per pixel, so a 28 km window holds only about 60 real pixels. They are
    resampled to 256 px with cubic interpolation so they look smooth instead of blocky; no detail is added.
  * Earth globe: web/assets/earth_8k.jpg, 8192 x 4096. Colours are NASA Blue Marble (the 4096 px image), relief is the
    Natural Earth 1:10m shaded relief (SR_HR, 21600 x 10800, public domain) multiplied in, so mountains and valleys stay
    crisp when the globe is zoomed. The app shows the 4k image first and swaps in this one once it has loaded.

Usage (from pipeline/): python 07c_hires_images.py ../raw ../web
"""
import sys, os, io, json, gzip, zipfile, numpy as np, rasterio
from rasterio.windows import Window
from rasterio.enums import Resampling
from rasterio.warp import transform as wtransform
from PIL import Image, ImageEnhance

raw, web = sys.argv[1], sys.argv[2]
man_p = os.path.join(web, "data", "manifest.json")
man = json.load(open(man_p))
CHIP_KM = 28.0
MOONGEO = "+proj=longlat +a=1737400 +b=1737400 +no_defs"

with rasterio.open(os.path.join(raw, "moon_lola_spole75_30m.tif")) as d:
    crs, tr = d.crs, d.transform
    left, top, res = tr.c, tr.f, tr.a
    for t in man["targets"]:
        if t["body"] != "moon" or not t.get("chip"): continue
        x, y = wtransform(MOONGEO, crs, [t["lon"]], [t["lat"]])
        npx = int(round(CHIP_KM * 1000 / res)); col = int((x[0] - left) / res); row = int((top - y[0]) / res)
        chip = d.read(1, window=Window(col - npx // 2, row - npx // 2, npx, npx), out_shape=(512, 512), resampling=Resampling.average).astype(np.float32) * 0.5
        open(os.path.join(web, "data", "chips", t["id"] + ".bin.gz"), "wb").write(gzip.compress(np.round(chip).astype("<i2").tobytes(), 9))
        t["chip"] = dict(px=512, metersPerPixel=CHIP_KM * 1000 / 512, sizeKm=CHIP_KM)
print("moon chips at 512 px")

with rasterio.open(os.path.join(raw, "mars_mola_463m.tif")) as d:
    for t in man["targets"]:
        if t["body"] != "mars" or not t.get("chip"): continue
        ny = int(round(CHIP_KM * 1000 / 463.0836)); nx = int(round(ny / np.cos(np.radians(t["lat"]))))
        rr = int((90 - t["lat"]) / 180 * d.height); cc = int((t["lon"] + 180) / 360 * d.width)
        chip = d.read(1, window=Window(cc - nx // 2, rr - ny // 2, nx, ny), out_shape=(256, 256), resampling=Resampling.cubic, boundless=True, fill_value=-32768)
        open(os.path.join(web, "data", "chips", t["id"] + ".bin.gz"), "wb").write(gzip.compress(chip.astype("<i2").tobytes(), 9))
        t["chip"] = dict(px=256, metersPerPixel=CHIP_KM * 1000 / 256, sizeKm=CHIP_KM)
print("mars chips at 256 px (MOLA-limited)")
json.dump(man, open(man_p, "w"), separators=(",", ":"))

# ---------------------------------------------------------------- Earth globe 8k
Image.MAX_IMAGE_PIXELS = None
z = zipfile.ZipFile(os.path.join(raw, "ne_hr_dl", "SR_HR.zip"))
sr = Image.open(io.BytesIO(z.read("SR_HR.tif"))).convert("L").resize((8192, 4096), Image.LANCZOS)
s = np.asarray(sr).astype(np.float32)
flat = np.median(s[s > 0])                                   # value of flat ground (and sea) in the relief image
rel = np.clip(s / flat, 0.45, 1.5) ** 0.75                   # >1 lit slopes, <1 shaded slopes
bm = Image.open(os.path.join(raw, "earth_orig.jpg")).convert("RGB").resize((8192, 4096), Image.BICUBIC)
bm = ImageEnhance.Color(bm).enhance(0.45); bm = ImageEnhance.Brightness(bm).enhance(0.9)
out = np.clip(np.asarray(bm).astype(np.float32) * rel[..., None], 0, 255).astype(np.uint8)
Image.fromarray(out).save(os.path.join(web, "assets", "earth_8k.jpg"), quality=80, optimize=True, progressive=True)
print("earth_8k.jpg", os.path.getsize(os.path.join(web, "assets", "earth_8k.jpg")) // 1024, "kB")
