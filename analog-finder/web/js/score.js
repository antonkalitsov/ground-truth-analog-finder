// score.js — data loading and the scoring engine for Ground Truth.
// Same rule as pipeline/traits.py (blend_sim), per trait:
//   closeness  C = 1 - |earth - target| / tolerance                                       (clipped 0..1)
//   extremity  X = 1 - 2F, F = share of Earth's land more extreme toward the target       (clipped 0..1)
//   sim = (1 - b) C + b X, b = how far the target lies beyond Earth's 1st..99th percentile range, in tolerances (max 1)
// Inside Earth's range b = 0; a tolerance or more beyond it b = 1; in between the two blend, so scores never jump.
// Every Earth trait is a byte per land cell, so each trait's similarity is a 256-entry lookup table
// and a full global re-score (318k cells x 15 traits) takes a few milliseconds.

const DEG = Math.PI / 180;

export async function fetchBytes(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  const buf = new Uint8Array(await r.arrayBuffer());
  if (buf[0] === 0x1f && buf[1] === 0x8b && 'DecompressionStream' in window) {
    const s = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
    return new Uint8Array(await new Response(s).arrayBuffer());
  }
  return buf;
}

export const toT = (tr, v) => (tr.transform === 'log' ? Math.log10(Math.max(v, 0) + 1) : v);
export const fromT = (tr, t) => (tr.transform === 'log' ? Math.pow(10, t) - 1 : t);
const deq = (tr, b) => tr.min + (b / 255) * (tr.max - tr.min);

export function noonSun(latDeg, obliquity, n = 360) {
  let s = 0;
  const so = Math.sin(obliquity * DEG);
  for (let i = 0; i < n; i++) {
    const decl = Math.asin(so * Math.sin(((i + 0.5) / n) * 2 * Math.PI)) / DEG;
    s += Math.max(0, 90 - Math.abs(latDeg - decl));
  }
  return s / n;
}

function interp(x, xs, ys) {           // xs ascending
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xs[m] <= x) lo = m; else hi = m; }
  const d = xs[hi] - xs[lo];
  return d > 0 ? ys[lo] + ((x - xs[lo]) / d) * (ys[hi] - ys[lo]) : ys[hi];
}
const PCT = Array.from({ length: 101 }, (_, i) => i / 100);

// similarity of an Earth value (transformed units) to a target (transformed units)
export function similarity(tr, e, tv) {
  if (tr.transform === 'cat') { const row = tr.matrix && tr.matrix[Math.round(tv)]; return row ? (row[Math.round(e)] ?? 0) : 0; }
  const close = Math.max(0, 1 - Math.abs(e - tv) / tr.tol);
  const out = tv < tr.earthLo ? tr.earthLo - tv : tv > tr.earthHi ? tv - tr.earthHi : 0;
  if (out <= 0) return close;
  const F = interp(e, tr.quant, PCT);
  const extreme = Math.max(0, 1 - 2 * (tv < tr.earthLo ? F : 1 - F));
  const b = Math.min(1, out / tr.tol);
  return (1 - b) * close + b * extreme;
}
export const beyondEarth = (tr, tv) => tv < tr.earthLo || tv > tr.earthHi;

export async function loadData(base = 'data/') {
  const man = await (await fetch(base + 'manifest.json')).json();
  const [earth, names, namesTxt, mars, moon] = await Promise.all([
    fetchBytes(base + 'earth.bin.gz'), fetchBytes(base + 'names.bin.gz'),
    fetch(base + 'names.json').then((r) => r.json()),
    fetchBytes(base + 'mars_grid.bin.gz'), fetchBytes(base + 'moon_grid.bin.gz'),
  ]);
  const { nx, ny, cells, stored } = man.grid;
  const T = {}; man.traits.forEach((t, i) => { T[t.id] = t; t.index = i; if (t.transform === 'cat' && man.rock) t.matrix = man.rock.matrix; });
  // --- unpack the Earth cells
  const maskBytes = Math.ceil((nx * ny) / 8);
  const cellOf = new Int32Array(nx * ny).fill(-1);
  const lat = new Float32Array(cells), lon = new Float32Array(cells), row = new Uint16Array(cells);
  let k = 0;
  for (let p = 0; p < nx * ny; p++) {
    if (earth[p >> 3] & (1 << (p & 7))) {
      cellOf[p] = k; const r = (p / nx) | 0, c = p % nx;
      row[k] = r; lat[k] = 90 - (r + 0.5) * man.grid.res; lon[k] = -180 + (c + 0.5) * man.grid.res; k++;
    }
  }
  const layer = {};
  stored.forEach((id, i) => { layer[id] = earth.subarray(maskBytes + i * cells, maskBytes + (i + 1) * cells); });
  const elevQ = earth.subarray(maskBytes + stored.length * cells, maskBytes + (stored.length + 1) * cells);
  const E = man.grid.elev;
  const elev = (b) => E.min + (b / 255) * (E.max - E.min);
  // derived layers, quantised the same way as stored ones
  const quant = (tr, v) => Math.max(0, Math.min(255, Math.round(((toT(tr, v) - tr.min) / (tr.max - tr.min)) * 255)));
  const sunQ = new Uint8Array(cells), iceQ = new Uint8Array(cells), presQ = new Uint8Array(cells);
  const sunRow = new Uint8Array(ny);
  for (let r = 0; r < ny; r++) sunRow[r] = quant(T.sun, noonSun(90 - (r + 0.5) * man.grid.res, man.bodies.earth.obliquity));
  for (let i = 0; i < cells; i++) {
    sunQ[i] = sunRow[row[i]];
    const temp = deq(T.temp, layer.temp[i]);
    iceQ[i] = quant(T.ice, Math.min(1, Math.max(0, (1 - temp) / 7)));
    presQ[i] = quant(T.pressure, 101.325 * Math.pow(1 - 2.25577e-5 * Math.min(9000, Math.max(-500, elev(elevQ[i]))), 5.25588));
  }
  layer.sun = sunQ; layer.ice = iceQ; layer.pressure = presQ;
  const nm = new Uint16Array(names.buffer, names.byteOffset, names.byteLength / 2);
  return {
    man, T, cells, nx, ny, cellOf, lat, lon, layer, elevQ, elev,
    names: namesTxt, nameIdx: nm,
    mars: { bytes: mars, nx: man.marsGrid.nx, ny: man.marsGrid.ny },
    moon: (() => {
      const n2 = man.moonGrid.n ** 2, nt = man.traits.length;
      return { valid: moon.subarray(0, n2), bytes: moon.subarray(n2), n: man.moonGrid.n,
        unit: moon.length >= n2 * (nt + 2) ? moon.subarray(n2 * (nt + 1), n2 * (nt + 2)) : null,
        divHas: moon.length >= n2 * (nt + 3) ? moon.subarray(n2 * (nt + 2), n2 * (nt + 3)) : null };
    })(),
  };
}

// value of a trait at an Earth cell, in display units
export function earthValue(D, id, i) {
  const tr = D.T[id];
  return fromT(tr, deq(tr, D.layer[id][i]));
}

export function placeName(D, i) {
  const n = D.cells;
  const a1 = D.names[D.nameIdx[i]], a0 = D.names[D.nameIdx[n + i]], rg = D.names[D.nameIdx[2 * n + i]];
  const title = [a1, a0].filter(Boolean).filter((v, j, a) => a.indexOf(v) === j).join(', ') || 'Remote land';
  const region = rg && !title.includes(rg) ? rg.replace(/\b([A-Z])([A-Z]+)\b/g, (m, a, b) => a + b.toLowerCase()) : '';
  return { title, region };
}

// target trait vector from the Mars / Moon grids (display units)
function gridVector(D, bytes, nCells, cell) {
  const v = {};
  D.man.traits.forEach((tr, ti) => { v[tr.id] = fromT(tr, deq(tr, bytes[ti * nCells + cell])); });
  return v;
}
export function marsCellTarget(D, lat, lon) {
  const { nx, ny } = D.mars;
  const r = Math.min(ny - 1, Math.max(0, Math.floor(90 - lat))), c = Math.min(nx - 1, Math.max(0, Math.floor(lon + 180)));
  return gridVector(D, D.mars.bytes, nx * ny, r * nx + c);
}
export function moonXY(D, lat, lon) {
  const R = D.man.moonGrid.R, c = (90 + lat) * DEG, rho = 2 * R * Math.tan(c / 2);
  return { x: rho * Math.sin(lon * DEG), y: rho * Math.cos(lon * DEG) };
}
export function moonLatLon(D, x, y) {
  const R = D.man.moonGrid.R, rho = Math.hypot(x, y);
  return { lat: -90 + (2 * Math.atan(rho / (2 * R))) / DEG, lon: Math.atan2(x, y) / DEG };
}
export function moonCellTarget(D, x, y) {
  const g = D.man.moonGrid, n = g.n;
  const j = Math.floor((x - g.left) / g.mpp / g.cellPx), i = Math.floor((g.top - y) / g.mpp / g.cellPx);
  if (i < 0 || j < 0 || i >= n || j >= n || !D.moon.valid[i * n + j]) return null;
  const v = gridVector(D, D.moon.bytes, n * n, i * n + j);
  const u = D.moon.unit ? D.moon.unit[i * n + j] : 0, U = D.man.moonUnits;
  return { v, geoUnit: U && u ? { code: U.codes[u], name: U.names[u], age: U.ages[u] } : null, diviner: !!(D.moon.divHas && D.moon.divHas[i * n + j]) };
}

// --- scoring
export function scoreAll(D, target, weights, out) {
  const luts = [];
  for (const tr of D.man.traits) {
    const w = weights[tr.id] || 0;
    if (w <= 0) continue;
    const tv = toT(tr, target[tr.id]);
    const lut = new Float32Array(256);
    for (let b = 0; b < 256; b++) lut[b] = w * similarity(tr, deq(tr, b), tv);
    luts.push([lut, D.layer[tr.id], w]);
  }
  const wsum = luts.reduce((s, l) => s + l[2], 0) || 1;
  const n = D.cells; out = out || new Float32Array(n);
  out.fill(0);
  for (const [lut, lay] of luts) for (let i = 0; i < n; i++) out[i] += lut[lay[i]];
  const f = 100 / wsum;
  for (let i = 0; i < n; i++) out[i] *= f;
  return out;
}

// per-trait breakdown for one Earth cell
export function explain(D, target, weights, i) {
  return D.man.traits.map((tr) => {
    const tv = toT(tr, target[tr.id]);
    const e = deq(tr, D.layer[tr.id][i]);
    const sim = similarity(tr, e, tv);
    return { tr, w: weights[tr.id] || 0, target: target[tr.id], earth: fromT(tr, e), sim, beyond: beyondEarth(tr, tv) };
  });
}

export function haversineKm(lat1, lon1, lat2, lon2) {
  const p1 = lat1 * DEG, p2 = lat2 * DEG;
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(((lon2 - lon1) * DEG) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(Math.min(1, a)));
}

// greedy pick of the best cells, at least sepKm apart, optionally skipping known analog regions
export function pickCandidates(D, scores, { n = 10, sepKm = 300, excludeKm = 150, known = [] } = {}) {
  // take the top ~0.5% cells via a histogram threshold
  const hist = new Uint32Array(1001);
  for (let i = 0; i < D.cells; i++) hist[Math.min(1000, Math.max(0, Math.round(scores[i] * 10)))]++;
  let acc = 0, thr = 0;
  for (let b = 1000; b >= 0; b--) { acc += hist[b]; if (acc >= 4000) { thr = b / 10; break; } }
  const top = [];
  for (let i = 0; i < D.cells; i++) if (scores[i] >= thr) top.push(i);
  top.sort((a, b) => scores[b] - scores[a]);
  const picked = [];
  for (const i of top) {
    const la = D.lat[i], lo = D.lon[i];
    let nearest = Infinity, nearName = '';
    for (const k of known) { const d = haversineKm(la, lo, k.lat, k.lon); if (d < nearest) { nearest = d; nearName = k.name; } }
    if (excludeKm > 0 && nearest < excludeKm) continue;
    if (picked.some((p) => haversineKm(la, lo, p.lat, p.lon) < sepKm)) continue;
    picked.push({ i, lat: la, lon: lo, score: scores[i], nearestKm: nearest, nearestName: nearName });
    if (picked.length >= n) break;
  }
  return picked;
}

export function percentileOf(scores, v) {
  let below = 0;
  for (let i = 0; i < scores.length; i++) if (scores[i] < v) below++;
  return (100 * below) / scores.length;
}

export function nearestCell(D, lat, lon, maxSteps = 3) {
  const res = D.man.grid.res;
  const r0 = Math.floor((90 - lat) / res), c0 = Math.floor((lon + 180) / res);
  for (let s = 0; s <= maxSteps; s++) {
    let best = -1, bd = Infinity;
    for (let dr = -s; dr <= s; dr++) for (let dc = -s; dc <= s; dc++) {
      const r = r0 + dr, c = (((c0 + dc) % D.nx) + D.nx) % D.nx;
      if (r < 0 || r >= D.ny) continue;
      const k = D.cellOf[r * D.nx + c];
      if (k >= 0) { const d = dr * dr + dc * dc; if (d < bd) { bd = d; best = k; } }
    }
    if (best >= 0) return best;
  }
  return -1;
}
