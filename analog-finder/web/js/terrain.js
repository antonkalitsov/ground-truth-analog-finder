// terrain.js — runtime "terrain detail" for Ground Truth. Zero dependencies, plain ES module.
//
// Fetches open elevation tiles (AWS Terrain Tiles, "terrarium" PNG encoding) for any Earth
// location, resamples them onto a local equal-distance grid, computes terrain statistics and
// draws shaded-relief chips. The same statistics and renderer work on precomputed Moon/Mars
// grids loaded through gridFromInt16().
//
// Grid shape used everywhere:
//   { z: Float32Array(px*px) metres, px, sizeKm, metersPerPixel }   row 0 = north, col 0 = west

const TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium';
const TILE = 256;                 // tile edge in pixels
const MAX_LAT = 85.0511;          // Web Mercator limit
const M_PER_DEG = 111320;         // metres per degree of latitude
const MIN_ZOOM = 5, MAX_ZOOM = 12;
const CACHE_MAX = 96;             // decoded tiles kept (about 25 MB)
const SEA_M = 0.5;                // at or below this counts as sea (the tiles ripple slightly around 0 m)

const cache = new Map();          // "z/x/y" -> Promise<Float32Array(256*256)>, in LRU order

// Dry land below sea level [latMin, latMax, lonMin, lonMax]. For a chip centred inside one of
// these boxes low ground is not ocean: oceanFraction is 0 and nothing is painted as water.
const DRY_DEPRESSIONS = [
  [35.5, 37.0, -117.6, -116.3],   // Death Valley
  [32.0, 33.9, -116.3, -114.9],   // Salton Trough, Laguna Salada
  [30.8, 33.0, 35.3, 35.75],      // Dead Sea, Jordan Valley
  [12.8, 14.5, 39.9, 40.75],      // Danakil Depression
  [11.5, 11.8, 42.3, 42.47],      // Lake Assal
  [28.5, 30.5, 25.0, 29.0],       // Qattara Depression, Siwa
  [33.7, 34.7, 5.5, 8.3],         // Chott Melrhir, Chott el Gharsa
  [42.3, 43.2, 88.5, 90.5],       // Turpan Depression
  [36.4, 48.5, 44.0, 58.5],       // Caspian Depression (sea surface is at -28 m)
  [-29.7, -27.5, 136.5, 138.2],   // Lake Eyre
  [-49.7, -49.4, -68.6, -68.1],   // Laguna del Carbon
];

function fail(code, message, cause) {
  const e = new Error(message);
  e.code = code;
  if (cause) e.cause = cause;
  return e;
}

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

// ---------------------------------------------------------------------------------------------
// Tile decoding. A canvas can alter pixel values (colour management), so the PNG is decoded by
// hand: collect IDAT chunks, inflate with DecompressionStream, undo the scanline filters.
// ---------------------------------------------------------------------------------------------

async function decodeTerrarium(buf) {
  const b = new Uint8Array(buf), dv = new DataView(buf);
  let w = 0, h = 0, bpp = 0, plain = false;
  const idat = [];
  for (let p = 8; p + 12 <= b.length;) {
    const len = dv.getUint32(p);
    const type = String.fromCharCode(b[p + 4], b[p + 5], b[p + 6], b[p + 7]);
    if (type === 'IHDR') {
      w = dv.getUint32(p + 8); h = dv.getUint32(p + 12);
      const colour = b[p + 17];
      bpp = colour === 2 ? 3 : colour === 6 ? 4 : 0;          // RGB or RGBA
      plain = b[p + 16] === 8 && bpp > 0 && b[p + 20] === 0;  // 8-bit, not interlaced
    } else if (type === 'IDAT') idat.push(b.subarray(p + 8, p + 8 + len));
    else if (type === 'IEND') break;
    p += 12 + len;
  }
  if (w !== TILE || h !== TILE) throw new Error('unexpected elevation tile size');
  if (!plain || typeof DecompressionStream === 'undefined') return decodeViaCanvas(buf);

  const inflated = new Blob(idat).stream().pipeThrough(new DecompressionStream('deflate'));
  const raw = new Uint8Array(await new Response(inflated).arrayBuffer());
  const stride = w * bpp, out = new Float32Array(w * h);
  if (raw.length < (stride + 1) * h) throw new Error('truncated elevation tile');
  let prev = new Uint8Array(stride);
  for (let y = 0, p = 0; y < h; y++) {
    const filter = raw[p++], cur = raw.subarray(p, p + stride);
    p += stride;
    if (filter) for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0, up = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let pred = a;                                            // 1 Sub
      if (filter === 2) pred = up;                             // 2 Up
      else if (filter === 3) pred = (a + up) >> 1;             // 3 Average
      else if (filter === 4) {                                 // 4 Paeth
        const pa = Math.abs(up - c), pb = Math.abs(a - c), pc = Math.abs(a + up - 2 * c);
        pred = pa <= pb && pa <= pc ? a : pb <= pc ? up : c;
      }
      cur[i] += pred;                                          // Uint8 wraps mod 256
    }
    for (let x = 0, i = 0; x < w; x++, i += bpp) {
      out[y * w + x] = cur[i] * 256 + cur[i + 1] + cur[i + 2] / 256 - 32768;
    }
    prev = cur;
  }
  return out;
}

// Fallback for browsers without DecompressionStream or for unusual PNG variants.
async function decodeViaCanvas(buf) {
  const bmp = await createImageBitmap(new Blob([buf], { type: 'image/png' }),
    { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
  const cv = document.createElement('canvas');
  cv.width = cv.height = TILE;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0);
  const d = ctx.getImageData(0, 0, TILE, TILE).data, out = new Float32Array(TILE * TILE);
  for (let i = 0, j = 0; i < out.length; i++, j += 4) out[i] = d[j] * 256 + d[j + 1] + d[j + 2] / 256 - 32768;
  return out;
}

function loadTile(key, signal) {
  let p = cache.get(key);
  if (p) { cache.delete(key); cache.set(key, p); return p; }   // refresh LRU position
  p = fetch(`${TILE_URL}/${key}.png`, { signal })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer(); })
    .then(decodeTerrarium);
  p.catch(() => { if (cache.get(key) === p) cache.delete(key); });   // never cache failures
  cache.set(key, p);
  while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
  return p;
}

async function getTile(key, signal) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await loadTile(key, signal);
    } catch (e) {
      if (signal?.aborted) throw e.name === 'AbortError' ? e : new DOMException('Aborted', 'AbortError');
      // A request shared with another caller was aborted by that caller: start it again.
      if (e.name === 'AbortError' && attempt < 2) continue;
      throw fail('NETWORK', `Could not load elevation tile ${key} (${e.message})`, e);
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------------------------

/**
 * Fetch a square elevation chip centred on (lat, lon).
 * Rejects with an Error whose .code is 'OUT_OF_COVERAGE' (beyond +-85.05 deg), 'NETWORK'
 * (a tile failed to load or decode) or 'BAD_INPUT'; an aborted signal rejects with AbortError.
 */
export async function fetchEarthTerrain({ lat, lon, sizeKm = 28, px = 192, signal } = {}) {
  lat = Number(lat); lon = Number(lon); px = Math.round(px);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || !(sizeKm > 0) || !(px >= 2)) {
    throw fail('BAD_INPUT', 'fetchEarthTerrain needs numeric lat, lon, sizeKm > 0 and px >= 2');
  }
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  const mpp = sizeKm * 1000 / px;
  if (Math.abs(lat) + sizeKm * 500 / M_PER_DEG > MAX_LAT) {
    throw fail('OUT_OF_COVERAGE', `No elevation tiles beyond ${MAX_LAT} degrees latitude`);
  }
  lon = ((lon + 180) % 360 + 360) % 360 - 180;

  // Coarsest zoom whose ground resolution at this latitude is at least as fine as the grid.
  const rad = Math.PI / 180;
  const zoom = clamp(Math.ceil(Math.log2(156543.03392 * Math.cos(lat * rad) / mpp)), MIN_ZOOM, MAX_ZOOM);
  const world = TILE * 2 ** zoom;

  // Sample positions (pixel centres of the output grid) in global tile-pixel coordinates.
  // Longitude is left unwrapped so a chip can straddle the antimeridian.
  const gx = new Float64Array(px * px), gy = new Float64Array(px);
  let xMin = Infinity, xMax = -Infinity;
  for (let r = 0; r < px; r++) {
    const la = lat + (px / 2 - 0.5 - r) * mpp / M_PER_DEG;
    gy[r] = clamp((1 - Math.asinh(Math.tan(la * rad)) / Math.PI) / 2 * world - 0.5, 0, world - 1);
    const degPerCol = mpp / (M_PER_DEG * Math.cos(la * rad));
    for (let c = 0; c < px; c++) {
      const x = (lon + (c - px / 2 + 0.5) * degPerCol + 180) / 360 * world - 0.5;
      gx[r * px + c] = x;
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
    }
  }
  const tx0 = Math.floor(xMin / TILE), tx1 = Math.floor((xMax + 1) / TILE);
  const ty0 = Math.floor(gy[0] / TILE), ty1 = Math.floor(Math.min(gy[px - 1] + 1, world - 1) / TILE);
  const cols = tx1 - tx0 + 1, rows = ty1 - ty0 + 1;
  if (cols * rows > 64) throw fail('BAD_INPUT', 'Requested area needs too many elevation tiles');

  // Fetch every tile in parallel and stitch them into one mosaic.
  const n = 2 ** zoom, jobs = [];
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      jobs.push(getTile(`${zoom}/${((tx % n) + n) % n}/${ty}`, signal));
    }
  }
  const tiles = await Promise.all(jobs);
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  const mw = cols * TILE, mh = rows * TILE, mosaic = new Float32Array(mw * mh);
  tiles.forEach((t, i) => {
    const ox = (i % cols) * TILE, oy = Math.floor(i / cols) * TILE;
    for (let y = 0; y < TILE; y++) mosaic.set(t.subarray(y * TILE, (y + 1) * TILE), (oy + y) * mw + ox);
  });

  // Bilinear resampling onto the local grid.
  const z = new Float32Array(px * px), offX = tx0 * TILE, offY = ty0 * TILE;
  let below = 0;
  for (let r = 0; r < px; r++) {
    const y = gy[r] - offY, y0 = Math.floor(y), fy = y - y0, y1 = Math.min(y0 + 1, mh - 1);
    for (let c = 0; c < px; c++) {
      const x = gx[r * px + c] - offX, x0 = Math.floor(x), fx = x - x0, x1 = Math.min(x0 + 1, mw - 1);
      const top = mosaic[y0 * mw + x0] * (1 - fx) + mosaic[y0 * mw + x1] * fx;
      const bot = mosaic[y1 * mw + x0] * (1 - fx) + mosaic[y1 * mw + x1] * fx;
      const v = top * (1 - fy) + bot * fy;
      z[r * px + c] = v;
      if (v <= SEA_M) below++;
    }
  }

  const dryDepression = DRY_DEPRESSIONS.some(b => lat >= b[0] && lat <= b[1] && lon >= b[2] && lon <= b[3]);
  return {
    z, px, sizeKm, metersPerPixel: mpp, zoom, tiles: tiles.length,
    oceanFraction: dryDepression ? 0 : below / z.length,
    dryDepression, lat, lon,
    source: `AWS Terrain Tiles (terrarium) z${zoom}`,
  };
}

/** Wrap a raw little-endian Int16 elevation raster (metres, row 0 = north) as a grid. -32768 = no data. */
export function gridFromInt16(arrayBuffer, px, metersPerPixel, sizeKm = px * metersPerPixel / 1000) {
  const dv = new DataView(arrayBuffer), z = new Float32Array(px * px);
  for (let i = 0; i < z.length; i++) {
    const v = dv.getInt16(i * 2, true);
    z[i] = v === -32768 ? NaN : v;
  }
  return { z, px, sizeKm, metersPerPixel };
}

// Percentile with linear interpolation (same as numpy's default) of an ascending array.
function percentile(sorted, p) {
  if (!sorted.length) return NaN;
  const i = p / 100 * (sorted.length - 1), lo = Math.floor(i), hi = Math.min(lo + 1, sorted.length - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

/**
 * Terrain statistics at a fixed baseline, so bodies sampled at different resolutions compare
 * fairly. The grid is block-averaged by f = max(1, round(baselineM / metersPerPixel)) (incomplete
 * edge blocks dropped); every statistic is measured on that averaged grid of cell size f * mpp.
 *   slope      central differences at interior cells, degrees (mean and 90th percentile)
 *   roughnessM RMS of (z - mean of the 5x5 neighbourhood), cells at least 2 from the edge
 *   reliefM    95th minus 5th percentile of elevation
 * Cells without data (NaN) are skipped.
 */
export function terrainStats(grid, { baselineM = 500 } = {}) {
  const { z, px, metersPerPixel } = grid;
  const f = Math.max(1, Math.round(baselineM / metersPerPixel));
  const n = Math.floor(px / f), cellM = f * metersPerPixel;
  const a = new Float64Array(n * n);
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      let s = 0;
      for (let y = 0; y < f; y++) for (let x = 0; x < f; x++) s += z[(r * f + y) * px + c * f + x];
      a[r * n + c] = s / (f * f);
    }
  }

  const elev = Float64Array.from(a).filter(Number.isFinite).sort();
  let sum = 0;
  for (const v of elev) sum += v;

  const slopes = [];
  for (let r = 1; r < n - 1; r++) {
    for (let c = 1; c < n - 1; c++) {
      const i = r * n + c;
      const dx = (a[i + 1] - a[i - 1]) / (2 * cellM), dy = (a[i + n] - a[i - n]) / (2 * cellM);
      const s = Math.atan(Math.hypot(dx, dy)) * 180 / Math.PI;
      if (Number.isFinite(s)) slopes.push(s);
    }
  }
  const sl = Float64Array.from(slopes).sort();
  let slopeSum = 0;
  for (const v of sl) slopeSum += v;

  let sq = 0, count = 0;
  for (let r = 2; r < n - 2; r++) {
    for (let c = 2; c < n - 2; c++) {
      let m = 0;
      for (let y = -2; y <= 2; y++) for (let x = -2; x <= 2; x++) m += a[(r + y) * n + c + x];
      const d = a[r * n + c] - m / 25;
      if (Number.isFinite(d)) { sq += d * d; count++; }
    }
  }

  return {
    slopeMeanDeg: sl.length ? slopeSum / sl.length : NaN,
    slopeP90Deg: percentile(sl, 90),
    roughnessM: count ? Math.sqrt(sq / count) : NaN,
    reliefM: percentile(elev, 95) - percentile(elev, 5),
    elevMeanM: elev.length ? sum / elev.length : NaN,
    elevMinM: elev.length ? elev[0] : NaN,
    elevMaxM: elev.length ? elev[elev.length - 1] : NaN,
    cellM,
  };
}

// Hypsometric tints, low to high. Each chip stretches its own 2nd-98th percentile over the ramp.
const PALETTES = {
  earth: [[84, 110, 88], [136, 150, 106], [192, 180, 128], [204, 160, 108], [170, 124, 94], [176, 160, 146], [228, 222, 210]],
  mars: [[86, 38, 28], [130, 56, 32], [176, 88, 46], [210, 132, 78], [230, 178, 126], [240, 214, 178]],
  moon: [[72, 74, 80], [112, 113, 118], [152, 152, 154], [194, 193, 189], [230, 228, 222]],
  mono: [[66, 72, 82], [228, 231, 236]],
};
const WATER = [34, 74, 120];

// Colour ramp as a 256-entry lookup table.
function rampLUT(stops) {
  const lut = new Uint8Array(256 * 3), last = stops.length - 1;
  for (let i = 0; i < 256; i++) {
    const t = i / 255 * last, k = Math.min(Math.floor(t), last - 1), f = t - k;
    for (let ch = 0; ch < 3; ch++) lut[i * 3 + ch] = stops[k][ch] + (stops[k + 1][ch] - stops[k][ch]) * f;
  }
  return lut;
}

// Catmull-Rom tap positions and weights for resizing n samples to m.
function taps(n, m) {
  const idx = new Int32Array(m * 4), wt = new Float32Array(m * 4);
  for (let i = 0; i < m; i++) {
    const s = (i + 0.5) * n / m - 0.5, k = Math.floor(s), t = s - k;
    const w = [((2 - t) * t - 1) * t / 2, ((3 * t - 5) * t * t + 2) / 2, ((4 - 3 * t) * t + 1) * t / 2, (t - 1) * t * t / 2];
    for (let j = 0; j < 4; j++) { idx[i * 4 + j] = clamp(k - 1 + j, 0, n - 1); wt[i * 4 + j] = w[j]; }
  }
  return { idx, wt };
}

// Smooth (bicubic) resize of a square n*n raster to w*h, so upscaled relief has no facets.
function resize(src, n, w, h) {
  const tx = taps(n, w), ty = taps(n, h), tmp = new Float32Array(w * n), out = new Float32Array(w * h);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < w; x++) {
      let s = 0;
      for (let j = 0; j < 4; j++) s += src[y * n + tx.idx[x * 4 + j]] * tx.wt[x * 4 + j];
      tmp[y * w + x] = s;
    }
  }
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let s = 0;
      for (let j = 0; j < 4; j++) s += tmp[ty.idx[y * 4 + j] * w + x] * ty.wt[y * 4 + j];
      out[y * w + x] = s;
    }
  }
  return out;
}

/**
 * Draw a shaded-relief chip filling the canvas at its current pixel size (set canvas.width and
 * canvas.height to CSS size * devicePixelRatio first for a sharp image).
 * palette 'earth' | 'mars' | 'moon' | 'mono'. With seaLevel, sea is drawn as flat water on grids
 * that report some (grid.oceanFraction > 0, set by fetchEarthTerrain). Moon and Mars grids from
 * gridFromInt16 carry no oceanFraction, so their negative elevations are never painted as water.
 */
export function renderHillshade(canvas, grid, {
  palette = 'earth', azimuthDeg = 315, altitudeDeg = 40, exaggeration = 1.5, seaLevel = true,
} = {}) {
  const { z, px, sizeKm } = grid;
  const w = canvas.width, h = canvas.height;
  const water = seaLevel && grid.oceanFraction > 0;

  // Tint range from the land part of the chip; cells without data take the mean elevation.
  const land = [];
  let sum = 0, finite = 0;
  for (const v of z) {
    if (!Number.isFinite(v)) continue;
    sum += v; finite++;
    if (!water || v > SEA_M) land.push(v);
  }
  const mean = finite ? sum / finite : 0;
  const sorted = Float64Array.from(land).sort();
  const lo = sorted.length ? percentile(sorted, 2) : 0;
  const span = Math.max(sorted.length ? percentile(sorted, 98) - lo : 1, 1);
  const filled = finite === z.length ? z : Float32Array.from(z, v => (Number.isFinite(v) ? v : mean));

  const e = resize(filled, px, w, h);
  const lut = rampLUT(PALETTES[palette] || PALETTES.earth);
  const az = azimuthDeg * Math.PI / 180, alt = altitudeDeg * Math.PI / 180;
  const lx = Math.sin(az) * Math.cos(alt), ly = Math.cos(az) * Math.cos(alt), lz = Math.sin(alt);  // east, north, up
  const kx = exaggeration / (2 * sizeKm * 1000 / w), ky = exaggeration / (2 * sizeKm * 1000 / h);

  const img = new ImageData(w, h), d = img.data;
  for (let y = 0; y < h; y++) {
    const yn = Math.max(y - 1, 0) * w, ys = Math.min(y + 1, h - 1) * w;
    for (let x = 0; x < w; x++) {
      const i = y * w + x, v = e[i], o = i * 4;
      const gxv = (e[y * w + Math.min(x + 1, w - 1)] - e[y * w + Math.max(x - 1, 0)]) * kx;   // rise to the east
      const gyv = (e[yn + x] - e[ys + x]) * ky;                                              // rise to the north
      // Lambert shading, scaled so level ground keeps its tint colour.
      const lambert = Math.max(0, (lz - gxv * lx - gyv * ly) / Math.sqrt(1 + gxv * gxv + gyv * gyv)) / lz;
      let r, g, b, light;
      if (water && v <= SEA_M) {
        // One flat colour: the tiles mix "sea = 0 m" and coarse bathymetry, which shades badly.
        r = WATER[0]; g = WATER[1]; b = WATER[2]; light = 1;
      } else {
        const k = Math.round(clamp((v - lo) / span, 0, 1) * 255) * 3;
        r = lut[k]; g = lut[k + 1]; b = lut[k + 2];
        light = lambert < 1 ? 0.28 + 0.72 * lambert : 1 + 0.4 * (Math.min(lambert, 1.5) - 1);   // soft highlights
      }
      d[o] = Math.min(255, r * light);
      d[o + 1] = Math.min(255, g * light);
      d[o + 2] = Math.min(255, b * light);
      d[o + 3] = 255;
    }
  }
  canvas.getContext('2d').putImageData(img, 0, 0);
  return canvas;
}

/** Drop every cached tile (frees memory; later requests fetch again). */
export function clearTerrainCache() {
  cache.clear();
}
