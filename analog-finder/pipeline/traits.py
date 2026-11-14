"""Trait catalogue, physical models for Moon/Mars and the scoring rule (mirrored in web/js/score.js)."""
import numpy as np
from terrainlib import mean_noon_sun_elevation

# id, label, unit, group, transform, qmin, qmax (in transformed units), tolerance (transformed units)
TRAITS = [
    ("slope",    "Mean slope",            "deg",  "Terrain",      "lin",   0.0, 25.0,  3.0),
    ("rough",    "Roughness",             "m",    "Terrain",      "log",   0.0, 3.2,   0.35),
    ("relief",   "Local relief",          "m",    "Terrain",      "log",   0.0, 3.8,   0.35),
    ("albedo",   "Surface albedo",        "",     "Surface",      "lin",   0.0, 0.85,  0.08),
    ("bare",     "Barren ground",         "frac", "Surface",      "lin",   0.0, 1.0,   0.35),
    ("icecover", "Ice / snow cover",      "frac", "Surface",      "lin",   0.0, 1.0,   0.35),
    ("temp",     "Mean temperature",      "C",    "Thermal",      "lin", -150.0, 40.0, 15.0),
    ("trange",   "Day-night swing",       "C",    "Thermal",      "lin",   0.0, 150.0, 12.0),
    ("sun",      "Noon sun elevation",    "deg",  "Illumination", "lin",   0.0, 90.0,  10.0),
    ("ice",      "Ground ice likelihood", "frac", "Water & ice",  "lin",   0.0, 1.0,   0.4),
    ("dry",      "Precipitation",         "mm/yr","Water & ice",  "log",   0.0, 3.8,   1.0),
    ("soil",     "Soil moisture",         "frac", "Water & ice",  "lin",   0.0, 1.0,   0.3),
    ("dust",     "Dust / aerosol",        "AOD",  "Atmosphere",   "lin",   0.0, 1.2,   0.25),
    ("wind",     "Mean wind",             "m/s",  "Atmosphere",   "lin",   0.0, 18.0,  3.0),
    ("pressure", "Air pressure",          "kPa",  "Atmosphere",   "lin",   0.0, 110.0, 10.0),
    ("ndvi",     "Plant greenness (NDVI)", "",    "Biology",      "lin",  -0.1, 0.9,   0.12),
    ("rock",     "Rock type",             "",     "Geology",      "cat",   0.0, 255.0, 1.0),
]
TID = [t[0] for t in TRAITS]

# ---------------------------------------------------------------- geology
# Rock family of a Moon / Mars target. Moon: from the USGS Unified Geologic Map of the Moon (2020).
# Mars: from the published geology of each landing site; any other Mars cell defaults to basalt
# (TES / OMEGA show the Martian crust is overwhelmingly basaltic).
FAMILY = ["highland", "basalt", "pyroclastic", "sediment", "evaporite", "loose", "ice"]
FAMILY_LABEL = {
    "highland": "Feldspathic highland crust (anorthosite, impact breccia)",
    "basalt": "Basaltic lava plains",
    "pyroclastic": "Volcanic glass / pyroclastic mantle",
    "sediment": "Lake and delta sediments (clays, mudstone, carbonate)",
    "evaporite": "Sulfate and salt deposits (evaporites)",
    "loose": "Loose regolith, outwash and periglacial soil",
    "ice": "Ice-rich ground and debris-covered glaciers",
}
def moon_unit_family(code):
    if code in ("Em", "Im1", "Im2", "Imd", "EIp"): return "basalt"
    if code == "Id": return "pyroclastic"
    return "highland"
# GLiM (Hartmann & Moosdorf 2012) first-level lithology classes
GLIM = ["su", "vb", "ss", "pb", "sm", "sc", "va", "mt", "pa", "vi", "wb", "py", "pi", "ev", "nd", "ig"]
GLIM_LABEL = {"su": "Unconsolidated sediments", "vb": "Basic volcanic rock (basalt)", "ss": "Siliciclastic sedimentary rock",
              "pb": "Basic plutonic rock (gabbro, anorthosite)", "sm": "Mixed sedimentary rock", "sc": "Carbonate rock",
              "va": "Acid volcanic rock", "mt": "Metamorphic rock", "pa": "Acid plutonic rock (granite)",
              "vi": "Intermediate volcanic rock", "wb": "Water", "py": "Pyroclastic rock", "pi": "Intermediate plutonic rock",
              "ev": "Evaporites", "nd": "No data", "ig": "Ice and glaciers"}
# how well each Earth rock class stands in for each target rock family (0..1)
ROCK_SIM = {
    "highland":    dict(pb=1.0, pi=0.75, mt=0.6, pa=0.45, vb=0.3, vi=0.3, va=0.2, py=0.2, su=0.15, ss=0.1, sm=0.1, ig=0.05),
    "basalt":      dict(vb=1.0, py=0.7, pb=0.65, vi=0.55, su=0.25, va=0.25, mt=0.15, pi=0.2, ss=0.1, sm=0.1, ig=0.05),
    "pyroclastic": dict(py=1.0, vb=0.75, vi=0.5, va=0.45, su=0.3, pb=0.2),
    "sediment":    dict(ss=1.0, sm=0.85, sc=0.7, ev=0.65, su=0.6, py=0.3, vb=0.3, mt=0.15),
    "evaporite":   dict(ev=1.0, ss=0.6, sm=0.6, sc=0.55, su=0.45, py=0.2, vb=0.2),
    "loose":       dict(su=1.0, ss=0.5, sm=0.45, py=0.45, ig=0.4, ev=0.4, vb=0.35, sc=0.2),
    "ice":         dict(ig=1.0, su=0.6, ss=0.2, sm=0.2, mt=0.15, vb=0.15),
}
ROCK_MATRIX = np.array([[ROCK_SIM[f].get(g, 0.0) for g in GLIM] for f in FAMILY], np.float32)
MARS_SITE_ROCK = {
    "jezero-perseverance": "sediment", "gale-curiosity": "sediment", "oxia-planum-rosalind-franklin": "sediment",
    "meridiani-opportunity": "evaporite", "melas-chasma": "evaporite", "utopia-viking-2": "basalt", "utopia-zhurong": "basalt",
    "elysium-insight": "basalt", "gusev-spirit": "basalt", "chryse-viking-1": "basalt", "arsia-mons-skylights": "basalt",
    "green-valley-phoenix": "loose", "arcadia-planitia": "loose", "ares-vallis-pathfinder": "loose", "deuteronilus-mensae": "ice",
}

PRESETS = {
    "overall":     ("Overall analog",          "Every trait counts equally (air pressure excluded: no place on Earth comes close).",
                    dict(slope=1, rough=1, relief=1, albedo=1, bare=1, icecover=1, temp=1, trange=1, sun=1, ice=1, dry=1, soil=1, dust=0.3, wind=0.3, pressure=0, ndvi=1, rock=0.25)),
    "landing":     ("Rover & landing terrain (regional)", "Regional terrain like the target's: kilometre-scale slope, roughness and relief over bare, loose ground. A first screen for where to look for rover and landing test areas; lander-scale hazards (metre-scale slopes, rocks, small craters) are not measured.",
                    dict(slope=3, rough=3, relief=2, albedo=0.5, bare=1.5, icecover=0.5, temp=0.3, trange=0.3, sun=0.3, ice=0.3, dry=0.5, soil=0.5, dust=1, wind=0.3, pressure=0, ndvi=0.5, rock=0.5)),
    "polar":       ("Polar base operations",   "Low sun, long shadows, cold and ice nearby: lighting, power and thermal design for a south-pole base.",
                    dict(slope=1, rough=0.5, relief=1.5, albedo=0.5, bare=1, icecover=1, temp=2, trange=1, sun=3, ice=1.5, dry=0.5, dust=0.3, wind=0.3, pressure=0, ndvi=0.3, rock=0.5)),
    "isru":        ("Ice prospecting & ISRU",  "Frozen ground under dry, bare terrain: drilling, ground-penetrating radar and water extraction trials.",
                    dict(slope=0.5, rough=0.5, relief=0.5, albedo=0.5, bare=1.5, icecover=1, temp=2, trange=0.5, sun=0.5, ice=3, dry=1.5, soil=1, dust=0.3, wind=0.3, pressure=0, ndvi=0.5, rock=1)),
    "instruments": ("Instrument & remote sensing", "Surfaces that look the same to cameras and spectrometers: albedo, bare ground, no vegetation, dry air.",
                    dict(slope=0.5, rough=1, relief=1, albedo=3, bare=3, icecover=1, temp=0.3, trange=0.3, sun=0.5, ice=0.3, dry=1.5, soil=1.5, dust=1, wind=0.3, pressure=0, ndvi=1.5, rock=2)),
    "crew":        ("Crew & EVA training",     "Places where people can rehearse surface operations: walkable slopes, harsh cold and dry conditions, isolation.",
                    dict(slope=2, rough=2, relief=1, albedo=0.5, bare=1.5, icecover=0.5, temp=1.5, trange=1, sun=1, ice=0.5, dry=1.5, soil=1, dust=0.5, wind=1, pressure=0, ndvi=0.5, rock=0.5)),
}

BODY = {
    "earth": dict(gravity=9.81, pressure_kpa=101.3, radiation="~2.4 mSv/yr at sea level (magnetic field + atmosphere)", radius_km=6371.0, obliquity=23.44),
    "mars":  dict(gravity=3.71, pressure_kpa=0.61, radiation="~230 mSv/yr on the surface (Curiosity RAD)", radius_km=3389.5, obliquity=25.19),
    "moon":  dict(gravity=1.62, pressure_kpa=0.0, radiation="~380 mSv/yr on the surface (Chang'e-4 LND)", radius_km=1737.4, obliquity=1.54),
}

def to_t(tid, v):
    tr = TRAITS[TID.index(tid)][4]
    v = np.asarray(v, dtype=np.float64)
    if tr == "cat": return v
    return np.log10(np.maximum(v, 0) + 1) if tr == "log" else v

def quantize(tid, v):
    _, _, _, _, tr, lo, hi, _ = TRAITS[TID.index(tid)]
    if tr == "cat": return np.clip(np.nan_to_num(np.asarray(v, np.float64)), 0, 255).astype(np.uint8)
    t = to_t(tid, v)
    return np.clip(np.round((t - lo) / (hi - lo) * 255), 0, 255).astype(np.uint8)

def dequant_t(tid, q):
    _, _, _, _, tr, lo, hi, _ = TRAITS[TID.index(tid)]
    if tr == "cat": return q.astype(np.float64)
    return lo + q.astype(np.float64) / 255 * (hi - lo)

def earth_pressure(elev):
    return 101.325 * (1 - 2.25577e-5 * np.clip(elev, -500, 9000)) ** 5.25588

def earth_ice(temp):
    return np.clip((1.0 - temp) / 7.0, 0, 1)

def mars_model(lat, elev, albedo, slope, rough, relief, ice_flag=None, rock=None):
    a = np.abs(np.asarray(lat, dtype=np.float64))
    icecover = np.clip((a - 78) / 6, 0, 1) * (np.asarray(albedo) > 0.25)
    ice = np.clip((a - 35) / 20, 0, 1)
    if ice_flag is not None:
        ice = np.where(ice_flag, np.maximum(ice, 0.9), ice)
    return dict(slope=slope, rough=rough, relief=relief, albedo=albedo, bare=1 - icecover, icecover=icecover,
                temp=-58 - 55 * (a / 90) ** 2, trange=10 + 65 * np.cos(np.radians(a)),
                sun=mean_noon_sun_elevation(lat, 25.19), ice=ice, dry=np.zeros_like(a), soil=np.zeros_like(a),
                dust=np.full_like(a, 0.5), wind=np.full_like(a, 5.0), pressure=0.61 * np.exp(-np.asarray(elev) / 11100.0),
                ndvi=np.zeros_like(a), rock=np.full_like(a, FAMILY.index("basalt")) if rock is None else np.asarray(rock, np.float64))

def moon_model(lat, elev, slope, rough, relief, ice_flag=None, rock=None, diviner=None):
    """diviner: optional dict(tavg=K, tmax=K, ice=share of surface with stable ice within ~1 m) from the LRO Diviner
    polar resource product; NaN entries fall back to the latitude model."""
    a = np.abs(np.asarray(lat, dtype=np.float64))
    ice = np.clip((a - 80) / 5, 0, 1) * 0.8
    temp = -70 - 40 * np.clip((a - 75) / 15, 0, 1)
    trange = np.full_like(a, 80.0)
    if diviner is not None:
        tavg = np.asarray(diviner["tavg"], np.float64) - 273.15
        tmax = np.asarray(diviner["tmax"], np.float64) - 273.15
        temp = np.where(np.isfinite(tavg), tavg, temp)
        # day-night swing ~ 2 x (max - mean) for a roughly symmetric diurnal curve (approximation, flagged in the UI)
        trange = np.where(np.isfinite(tmax) & np.isfinite(tavg), np.clip(2 * (tmax - tavg), 0, 300), trange)
        dice = np.asarray(diviner["ice"], np.float64)
        ice = np.where(np.isfinite(dice), np.clip(dice * 3, 0, 1), ice)   # 33 % of facets ice-stable -> likelihood 1
    if ice_flag is not None:
        ice = np.where(ice_flag, np.maximum(ice, 0.8), ice)
    z = np.zeros_like(a)
    return dict(slope=slope, rough=rough, relief=relief, albedo=np.full_like(a, 0.15), bare=np.ones_like(a), icecover=z,
                temp=temp, trange=trange, sun=mean_noon_sun_elevation(lat, 1.54), ice=ice, dry=z, soil=z, dust=z, wind=z, pressure=z,
                ndvi=z, rock=np.full_like(a, FAMILY.index("highland")) if rock is None else np.asarray(rock, np.float64))

def score(earth_t, target_t, weights, earth_lo, earth_hi, quant):
    """earth_t: dict tid -> transformed arrays; target_t: dict tid -> transformed scalar; quant: tid -> 101 Earth percentiles.
    In range: sim = 1 - |earth - target| / tolerance (clipped to 0..1).
    Target beyond what Earth offers (outside Earth's 1st..99th percentile): sim = 1 - 2 * F, where F is the fraction of
    Earth's land that is more extreme in the target's direction than this cell. Earth's most extreme places score 1 and
    the median place 0, so the trait still ranks places toward the target (the UI flags it as 'beyond Earth')."""
    num = 0; den = 0; sims = {}
    pc = np.linspace(0, 1, 101)
    for t in TRAITS:
        tid, tol = t[0], t[7]
        w = weights.get(tid, 0)
        if w <= 0 or tid not in earth_t or tid not in target_t: continue
        tv = target_t[tid]; e = earth_t[tid]
        if t[4] == "cat":
            s = ROCK_MATRIX[int(tv)][np.clip(np.asarray(e).astype(int), 0, len(GLIM) - 1)]
        elif tv < earth_lo[tid]:
            F = np.interp(e, quant[tid], pc); s = np.clip(1 - 2 * F, 0, 1)
        elif tv > earth_hi[tid]:
            F = 1 - np.interp(e, quant[tid], pc); s = np.clip(1 - 2 * F, 0, 1)
        else:
            s = np.clip(1 - np.abs(e - tv) / tol, 0, 1)
        sims[tid] = s; num = num + w * s; den += w
    return 100 * num / den, sims
