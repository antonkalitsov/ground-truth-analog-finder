// app.js — Ground Truth interface.
// Three stages share one page and one state object: intro (title card) -> choose (Moon / Mars) -> app.
// The scoring engine (score.js), the Earth globe (globe.js) and the terrain close-ups (terrain.js) are unchanged.
import * as S from './score.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const BASELINE_M = 1850;   // the terrain scale every trait grid was computed at
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const state = {
  body: null, target: null, preset: 'polar', weights: {}, scores: null, sorted: null,
  cands: [], known: [], tab: 'new', type: null, showAll: false, detail: null, touring: false,
};
let D, earth, mars, tgt = {}, chipSeq = 0, abortChip, planets = null, appReady = null;
let createGlobe, fetchEarthTerrain, gridFromInt16, terrainStats, renderHillshade;
window.__af = { state, get D() { return D; } };

// The 3 MB data pack starts downloading at once, in parallel with the title card, so the app is ready by the time a planet is chosen.
const dataP = S.loadData('data/');
dataP.catch(() => {});

// ------------------------------------------------------------------ formatting
const UNITS = {
  slope: (v) => `${v.toFixed(1)}°`, rough: (v) => `${Math.round(v)} m`, relief: (v) => `${Math.round(v).toLocaleString('en')} m`,
  albedo: (v) => v.toFixed(2), bare: (v) => `${Math.round(v * 100)}%`, icecover: (v) => `${Math.round(v * 100)}%`,
  temp: (v) => `${Math.round(v)} °C`, trange: (v) => `${Math.round(v)} °C`, sun: (v) => `${v.toFixed(1)}°`,
  ice: (v) => `${Math.round(v * 100)}%`, dry: (v) => `${Math.round(v).toLocaleString('en')} mm/yr`, soil: (v) => `${Math.round(v * 100)}%`,
  dust: (v) => v.toFixed(2), wind: (v) => `${v.toFixed(1)} m/s`, pressure: (v) => (v < 10 ? `${v.toFixed(2)} kPa` : `${Math.round(v)} kPa`),
  ndvi: (v) => v.toFixed(2), rock: (v) => String(Math.round(v)),
};
const FAMILY_SHORT = { highland: 'Highland anorthosite', basalt: 'Basalt', pyroclastic: 'Volcanic glass', sediment: 'Lake sediments', evaporite: 'Sulfates / salts', loose: 'Loose regolith', ice: 'Ice-rich ground' };
const GLIM_SHORT = { su: 'Loose sediments', vb: 'Basalt', ss: 'Sandstone / shale', pb: 'Gabbro / anorthosite', sm: 'Mixed sedimentary', sc: 'Limestone', va: 'Rhyolite', mt: 'Metamorphic', pa: 'Granite', vi: 'Andesite', wb: 'Water', py: 'Volcanic ash rock', pi: 'Diorite', ev: 'Evaporites', nd: 'No data', ig: 'Ice' };
const rockName = (v, side) => {
  const R = D.man.rock; if (!R) return '–';
  return side === 'target' ? (FAMILY_SHORT[R.families[Math.round(v)]] || '–') : (GLIM_SHORT[R.classes[Math.round(v)]] || '–');
};
const fmt = (id, v, side = 'earth') => (v == null || !Number.isFinite(v) ? '–' : id === 'rock' ? rockName(v, side) : UNITS[id](v));
const latlon = (la, lo) => `${Math.abs(la).toFixed(2)}° ${la >= 0 ? 'N' : 'S'}, ${Math.abs(lo).toFixed(2)}° ${lo >= 0 ? 'E' : 'W'}`;
const label = (sim) => (sim >= 0.75 ? 'strong' : sim >= 0.4 ? 'partial' : 'weak');
const shortName = (t) => t.name.replace(/\s*\(.*?\)\s*/g, ' ').trim();
const bodyName = (b) => (b === 'moon' ? 'the Moon' : 'Mars');
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };
const presetById = (id) => D.man.presets.find((p) => p.id === id);
const PURPOSE = { overall: 'an all-round comparison', landing: 'rover and landing tests', polar: 'polar base operations', isru: 'ice prospecting and ISRU', instruments: 'instrument and remote-sensing tests', crew: 'crew and EVA training' };

const USE = {
  slope: 'rover traverse, wheel slip and landing-hazard tests on comparable slopes',
  rough: 'hazard-avoidance and landing-sensor tests on a surface just as rough',
  relief: 'navigation, line-of-sight and communication tests among similar hills and crater walls',
  albedo: 'camera exposure and orbital remote-sensing calibration on a surface just as bright',
  bare: 'instrument, drill and sampling tests on bare ground without plant cover',
  icecover: 'operations on similarly ice-free (or ice-covered) ground',
  temp: 'cold-soak tests of batteries, seals and lubricants',
  trange: 'thermal-cycling tests of hardware between day and night',
  sun: 'solar-power, lighting and visual-navigation tests under a similarly low sun with long shadows',
  ice: 'ground-penetrating radar, drilling and water-extraction (ISRU) trials in frozen ground',
  dry: 'life-detection and contamination-control tests in near-sterile dry ground',
  soil: 'regolith handling and excavation tests in bone-dry soil',
  dust: 'dust-mitigation tests for seals, optics and solar panels',
  wind: 'tests of wind-blown dust and sand transport',
  ndvi: 'life-detection and contamination-control tests where almost nothing grows',
  rock: 'drilling, sample-handling and spectrometer tests on the same family of rock',
};

// ------------------------------------------------------------------ stages
const setStage = (s) => { document.body.dataset.stage = s; };

// Place the wordmark in the header: scale so the name is 22 px tall type, and centre it on the 56 px bar.
function fitMark() {
  const name = $('.mark-name'), mark = $('#mark');
  const fs = parseFloat(getComputedStyle(name).fontSize), ms = 22 / fs;
  const st = document.documentElement.style, pad = innerWidth <= 860 ? 16 : 24;
  st.setProperty('--ms', ms.toFixed(4));
  st.setProperty('--mx', `${pad - name.offsetLeft * ms}px`);
  st.setProperty('--my', `${(56 - name.offsetHeight * ms) / 2 - name.offsetTop * ms}px`);
  st.setProperty('--mw', `${Math.round(name.offsetWidth * ms + pad - 24)}px`);
  mark.dataset.fit = '1';
}

async function boot() {
  drawStars(); let st = 0; addEventListener('resize', () => { clearTimeout(st); st = setTimeout(drawStars, 200); });
  fitMark(); addEventListener('resize', fitMark);
  $('#mark').onclick = (e) => { e.preventDefault(); if (document.body.dataset.stage === 'app') goChoose(); };
  $$('.planet').forEach((b) => {
    b.onclick = () => choose(b.dataset.body, b);
    b.onpointerenter = () => planets && planets[b.dataset.body] && planets[b.dataset.body].hover(true);
    b.onpointerleave = () => planets && planets[b.dataset.body] && planets[b.dataset.body].hover(false);
    b.onfocus = b.onpointerenter; b.onblur = b.onpointerleave;
  });
  // deep link (#moon/haworth/isru): go straight to the app, no title card
  const [hb, tid, p] = decodeURIComponent(location.hash.slice(1)).split('/');
  if (hb === 'moon' || hb === 'mars') {
    document.body.classList.add('instant'); setStage('app'); $('#choose').hidden = true;
    await enterApp(hb, tid, p);
    requestAnimationFrame(() => document.body.classList.remove('instant'));
    return;
  }
  if (REDUCED) { goChoose(); return; }
  // Title card. Wait for the display face (at most 500 ms) so the reveal never shows a fallback font swap.
  await Promise.race([document.fonts.load('400 100px Newsreader'), sleep(500)]);
  fitMark();
  document.body.classList.add('play');
  let done = false;
  const next = () => { if (done) return; done = true; removeEventListener('pointerdown', next); removeEventListener('keydown', next); goChoose(); };
  addEventListener('pointerdown', next); addEventListener('keydown', next);   // never trap the user in the animation
  setTimeout(next, 2300);
}

// Static star field: a few hundred 1 px dots from a seeded generator (same sky every visit), drawn once and on resize.
function drawStars() {
  const c = $('#stars'), dpr = Math.min(2, devicePixelRatio || 1), w = innerWidth, h = innerHeight;
  c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
  const g = c.getContext('2d'); g.scale(dpr, dpr);
  let s = 20261113; const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const n = Math.round((w * h) / 2600);
  for (let i = 0; i < n; i++) {
    const x = rnd() * w, y = rnd() * h, m = rnd() ** 3;                 // most stars faint, a few bright
    const tint = rnd(); g.fillStyle = tint < 0.15 ? '#E8D9A8' : tint < 0.3 ? '#BFD0E6' : '#F2EEE8';
    g.globalAlpha = 0.16 + 0.74 * m;
    g.beginPath(); g.arc(x, y, 0.45 + 0.75 * m, 0, 6.2832); g.fill();
  }
}

async function goChoose() {
  closeMenu(); if (state.touring) stopTour();
  $('#choose').hidden = false; $('#choose').inert = false; $$('.planet').forEach((b) => b.classList.remove('chosen'));
  if (location.hash) history.replaceState(null, '', location.pathname);
  // two frames so the browser has painted the hidden->visible change before the transition starts
  requestAnimationFrame(() => requestAnimationFrame(() => setStage('choose')));
  setTimeout(() => { if (document.body.dataset.stage === 'choose') $('#app').hidden = true; }, 800);
  setTimeout(() => { if (document.body.dataset.stage === 'choose') $('#choose').classList.add('settled'); }, REDUCED ? 0 : 1700);   // hover growth only after the entrance
  if (!planets) {
    // lazy: the planet renderer is fetched only now, after the title card is already on screen
    const { createPlanet } = await import('./planets.js');
    const cv = $$('.planet canvas');
    planets = {
      moon: createPlanet(cv[0], { src: 'assets/moon.jpg', tilt: 0.03, speed: 0.045, bump: 5, spin0: 0.4, gain: 1.75, still: REDUCED }),
      mars: createPlanet(cv[1], { src: 'assets/mars.jpg', tilt: 0.44, speed: 0.06, bump: 3, spin0: 2.2, gain: 1.3, still: REDUCED }),
    };
    for (const [k, c] of [['moon', cv[0]], ['mars', cv[1]]]) if (!planets[k]) c.parentNode.classList.add('flat');   // no WebGL: plain disc
  }
  for (const k of ['moon', 'mars']) planets[k] && planets[k].start();
}

async function choose(body, btn) {
  if (document.body.dataset.stage !== 'choose') return;
  $('#choose').classList.remove('settled'); btn.classList.add('chosen');
  $('#app').hidden = false;
  requestAnimationFrame(() => setStage('app'));
  setTimeout(() => { if (document.body.dataset.stage === 'app') { $('#choose').hidden = true; for (const k of ['moon', 'mars']) planets && planets[k] && planets[k].stop(); } }, 1000);
  await enterApp(body);
}

async function enterApp(body, tid, preset) {
  $('#app').hidden = false;
  if (!appReady) appReady = initApp();
  try { await appReady; } catch (e) { console.error(e); $('#loading').textContent = `Could not load data: ${e.message}. Serve this folder over http (run start.bat).`; return; }
  const def = body === 'mars' ? 'jezero-perseverance' : 'shackleton-connecting-ridge';
  const t = D.man.targets.find((x) => x.id === tid && x.body === body) || D.man.targets.find((x) => x.id === def);
  setPreset(preset && presetById(preset) ? preset : body === 'mars' ? 'overall' : 'polar', false);
  setBody(body);
  setTarget({ ...t, named: true });
  $('#loading').classList.add('done');
}

async function initApp() {
  // globe and terrain code is fetched only when the app stage is first needed
  const [g, t] = await Promise.all([import('./globe.js'), import('./terrain.js')]);
  createGlobe = g.createGlobe; ({ fetchEarthTerrain, gridFromInt16, terrainStats, renderHillshade } = t);
  D = await dataP;
  earth = createGlobe($('#earth'), { baseUrl: 'assets/earth.jpg', planetRadiusKm: 6371, atmosphere: null, graticule: false, view: { lat: 15, lon: 20, zoom: 1 }, minZoom: 0.8, maxZoom: 40 });
  earth.on('click', (e) => { const i = S.nearestCell(D, e.lat, e.lon, 2); if (i >= 0) openDetail({ i }); });
  earth.on('markerclick', (e) => {
    const m = e.marker;
    if (m.kind === 'cand') openDetail({ i: state.cands[m.rank].i, rank: m.rank + 1 });
    else if (m.kind === 'known') { const i = S.nearestCell(D, m.lat, m.lon, 3); if (i >= 0) openDetail({ i, site: m.site }); }
  });
  earth.on('hover', onHover);
  // Sharper Earth: the 4k map paints first; the 8k map with Natural Earth relief replaces it when it arrives (never blocks).
  earth.on('ready', () => setTimeout(() => earth.setBase('assets/earth_8k.jpg'), 600));
  setupSearch();
  tgt.moon = createGlobe($('#tgtMoon'), { baseUrl: 'assets/moon.jpg', planetRadiusKm: 1737.4, atmosphere: null, graticule: false, view: { lat: -76, lon: 0, zoom: 2.3 }, minZoom: 0.9, maxZoom: 10 });
  tgt.mars = createGlobe($('#tgtMars'), { baseUrl: 'assets/mars.jpg', planetRadiusKm: 3389.5, atmosphere: null, graticule: false, view: { lat: 15, lon: 77, zoom: 1.14 }, minZoom: 0.9, maxZoom: 10 });
  for (const b of ['moon', 'mars']) tgt[b].on('markerclick', (e) => { if (e.id && e.id !== 'pin') selectNamed(e.id); });
  tgt.moon.on('click', (e) => pickMoonLatLon(e.lat, e.lon));
  tgt.mars.on('click', (e) => pickMarsPoint(e.lat, e.lon));
  $('#dest').onclick = goChoose;
  $('#btnAbout').onclick = openAbout;
  $('#btnTour').onclick = () => (state.touring ? stopTour() : runTour());
  $('#detailClose').onclick = closeDetail;
  $('#qTarget').onclick = (e) => openMenu(e.currentTarget, targetMenu);
  $('#qPurpose').onclick = (e) => openMenu(e.currentTarget, purposeMenu);
  $$('.tab').forEach((b) => (b.onclick = () => { state.tab = b.dataset.tab; state.type = null; state.showAll = false; renderList(); }));
  $('#btnFilter').onclick = () => { const t = $('#types'); t.hidden = !t.hidden; $('#btnFilter').setAttribute('aria-expanded', String(!t.hidden)); if (t.hidden && state.type) { state.type = null; renderList(); } };
  $('#btnMore').onclick = () => { state.showAll = true; renderList(); };
  $$('dialog [data-close]').forEach((b) => (b.onclick = () => b.closest('dialog').close()));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (!$('#menu').hidden) closeMenu(); else { closeDetail(); stopTour(); } } });
  document.addEventListener('pointerdown', (e) => { if (!$('#menu').hidden && !e.target.closest('#menu') && !e.target.closest('.pick')) closeMenu(); });
}

// ------------------------------------------------------------------ search
const fold = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
let searchIdx = null;
function buildSearchIndex() {
  // one entry per named area: admin-1 region (with its country), country, and geographic region; centre = mean of its cells
  const n = D.cells, m = new Map();
  const add = (key, label, sub, kind, i) => {
    let e = m.get(key); if (!e) m.set(key, (e = { label, sub, kind, la: 0, lo: 0, c: 0, cells: [] }));
    e.la += D.lat[i]; e.lo += D.lon[i]; e.c++; e.cells.push(i);
  };
  for (let i = 0; i < n; i++) {
    const a1 = D.nameIdx[i], a0 = D.nameIdx[n + i], rg = D.nameIdx[2 * n + i];
    if (a1 && a1 !== a0) add(`1:${a1}:${a0}`, D.names[a1], D.names[a0] || '', 'Region', i);
    if (a0) add(`0:${a0}`, D.names[a0], 'Country', 'Country', i);
    if (rg && rg !== a0 && rg !== a1) add(`2:${rg}`, D.names[rg].replace(/\b([A-Z])([A-Z]+)\b/g, (x, a, b) => a + b.toLowerCase()), 'Geographic area', 'Area', i);
  }
  searchIdx = [...m.values()].map((e) => ({ ...e, la: e.la / e.c, lo: e.lo / e.c, f: fold(e.label) }));
}
function searchResults(q) {
  const out = [], f = fold(q.trim());
  const ll = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (ll && Math.abs(+ll[1]) <= 90 && Math.abs(+ll[2]) <= 180) out.push({ kind: 'Point', label: latlon(+ll[1], +ll[2]), sub: 'Coordinates on Earth', la: +ll[1], lo: +ll[2] });
  if (f.length < 2) return out;
  const rank = (s) => (s.startsWith(f) ? 0 : s.includes(' ' + f) ? 1 : s.includes(f) ? 2 : -1);
  const pick = (list, key, n) => list.map((x) => ({ x, r: rank(fold(key(x))) })).filter((o) => o.r >= 0).sort((a, b) => a.r - b.r).slice(0, n).map((o) => o.x);
  for (const t of pick(D.man.targets, (t) => t.name, 4)) out.push({ kind: t.body === 'moon' ? 'Moon' : 'Mars', label: shortName(t), sub: t.mission || 'Search for analogs of this place', target: t });
  for (const k of pick(D.man.known, (k) => k.name, 4)) out.push({ kind: 'Analog site', label: k.name, sub: `${k.country || ''} · field-validated`, site: k });
  const areas = searchIdx.map((e) => ({ e, r: rank(e.f) })).filter((o) => o.r >= 0)
    .sort((a, b) => a.r - b.r || b.e.c - a.e.c).slice(0, 8).map((o) => o.e);
  for (const e of areas) out.push({ kind: e.kind, label: e.label, sub: e.sub, area: e });
  return out.slice(0, 14);
}
function chooseResult(r) {
  if (r.target) { selectNamed(r.target.id); return; }
  if (r.site) {
    const i = S.nearestCell(D, r.site.lat, r.site.lon, 3); if (i >= 0) openDetail({ i, site: r.site }); return;
  }
  if (r.area) {
    // the best-matching cell inside the area, so the card answers "how close does this region get?"
    let best = r.area.cells[0];
    for (const i of r.area.cells) if (state.scores[i] > state.scores[best]) best = i;
    openDetail({ i: best, searched: r.area.label }); return;
  }
  const i = S.nearestCell(D, r.la, r.lo, 2);
  if (i >= 0) openDetail({ i, searched: r.label }); else { $('#q').value = ''; $('#q').placeholder = 'That point is in the sea. Try a point on land.'; }
}
function setupSearch() {
  const inp = $('#q'), ul = $('#qList'); let res = [], on = -1;
  const close = () => { ul.hidden = true; inp.setAttribute('aria-expanded', 'false'); on = -1; };
  const draw = () => {
    ul.innerHTML = '';
    if (!res.length) { ul.appendChild(el('li', 'none', inp.value.trim().length < 2 ? 'Type at least two letters' : 'No match. Try a country, region or "lat, lon".')); }
    res.forEach((r, k) => {
      const li = el('li', k === on ? 'on' : '', `<span class="k">${esc(r.kind)}</span>${esc(r.label)}<small>${esc(r.sub || '')}</small>`);
      li.setAttribute('role', 'option'); li.onpointerdown = (e) => { e.preventDefault(); go(k); };
      ul.appendChild(li);
    });
    ul.hidden = false; inp.setAttribute('aria-expanded', 'true');
  };
  const go = (k) => { const r = res[k]; if (!r) return; close(); inp.value = r.label; inp.blur(); chooseResult(r); };
  inp.addEventListener('input', () => { if (!searchIdx) buildSearchIndex(); res = searchResults(inp.value); on = res.length ? 0 : -1; inp.value.trim() ? draw() : close(); });
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (res.length) { on = (on + (e.key === 'ArrowDown' ? 1 : res.length - 1)) % res.length; draw(); } }
    else if (e.key === 'Enter') { e.preventDefault(); go(Math.max(0, on)); }
    else if (e.key === 'Escape') { e.stopPropagation(); close(); }
  });
  inp.addEventListener('blur', () => setTimeout(close, 120));
  inp.addEventListener('focus', () => { if (!searchIdx) setTimeout(buildSearchIndex, 0); });
}

function setBody(body) {
  state.body = body;
  document.body.classList.toggle('mars', body === 'mars'); document.body.classList.toggle('moon', body === 'moon');
  $('#destName').textContent = body === 'moon' ? 'Moon' : 'Mars';
  if (tgt[body]) requestAnimationFrame(() => tgt[body].resize());
}

function selectNamed(id) {
  const t = D.man.targets.find((x) => x.id === id);
  if (t.body !== state.body) setBody(t.body);
  setTarget({ ...t, named: true });
}

function setTarget(t) {
  if (t.body !== state.body) setBody(t.body);          // the body always follows the target, whatever path set it
  const tgtGlobe = tgt[t.body];
  if (state.detail) closeDetail();
  state.target = t; state.type = null; state.showAll = false;
  $('#qTarget').textContent = t.named ? shortName(t) : t.name;
  // one quiet line of context under the sentence: what the place is and where its numbers come from
  const bits = [];
  if (t.named) bits.push(`${t.blurb || ''}`);
  else bits.push(t.blurb || '');
  if (t.rock) bits.push(`Rock: ${FAMILY_SHORT[t.rock] || t.rock}${t.geoUnit ? ` (USGS unit ${t.geoUnit.code}, ${t.geoUnit.age})` : ''}.`);
  if (t.diviner) bits.push(`LRO Diviner: ${Math.round(t.diviner.tavgK)} K mean, ${Math.round(t.diviner.tmaxK)} K maximum.`);
  if (t.coord_confidence === 'approximate') bits.push('Coordinates approximate.');
  $('#qNote').innerHTML = esc(bits.filter(Boolean).join(' ')) + (t.source ? ` <a href="${esc(t.source)}" target="_blank" rel="noopener">Source: ${esc(host(t.source))}</a>` : '');
  $('#tgtName').textContent = t.named ? shortName(t) : `Picked point`;
  $('#tgtWhere').textContent = `${t.body === 'moon' ? 'Moon' : 'Mars'} · ${latlon(t.lat, t.lon)}`;
  // the target body turns to face the chosen place; the Moon is held tilted so the south pole stays in view
  const named = D.man.targets.filter((x) => x.body === t.body && x.id !== t.id).map((x) => ({ id: x.id, lat: x.lat, lon: x.lon, className: 'mk mtgt', title: x.name, html: '<i></i>' }));
  tgtGlobe.setMarkers([...named, { id: 'pin', lat: t.lat, lon: t.lon, className: 'mk tpin', html: '<i></i>' }]);
  tgtGlobe.flyTo({ lat: t.body === 'moon' ? -76 : t.lat * 0.75, lon: t.lon, zoom: t.body === 'moon' ? 2.3 : 1.14, duration: REDUCED ? 0 : 1200 });
  updateHash(); rescore();
  if (state.cands[0] && !state.touring) earth.flyTo({ lat: state.cands[0].lat * 0.7, lon: state.cands[0].lon, zoom: 1, duration: REDUCED ? 0 : 1400 });
}

function setPreset(id, go = true) {
  state.preset = id; state.weights = { ...presetById(id).weights };
  $('#qPurpose').textContent = PURPOSE[id] || presetById(id).label.toLowerCase();
  if (go) { updateHash(); rescore(); }
}

function updateHash() {
  if (!state.target) return;
  const h = `#${state.body}/${state.target.id || 'point'}/${state.preset}`;
  if (location.hash !== h) history.replaceState(null, '', h);
}

// ------------------------------------------------------------------ menus (the two words in the sentence)
function openMenu(anchor, build) {
  const m = $('#menu');
  if (!m.hidden && m.dataset.for === anchor.id) { closeMenu(); return; }
  m.innerHTML = ''; build(m); m.dataset.for = anchor.id; m.hidden = false;
  const r = anchor.getBoundingClientRect();
  m.style.left = Math.max(12, Math.min(r.left, innerWidth - m.offsetWidth - 12)) + 'px';
  m.style.top = Math.min(r.bottom + 8, innerHeight - Math.min(m.offsetHeight, innerHeight * 0.7) - 12) + 'px';
  const on = m.querySelector('.on'); if (on) on.scrollIntoView({ block: 'nearest' });
}
function closeMenu() { const m = $('#menu'); if (m) m.hidden = true; }

function targetMenu(m) {
  for (const t of D.man.targets.filter((x) => x.body === state.body)) {
    const b = el('button', state.target.id === t.id ? 'on' : '', `${esc(shortName(t))}<small>${esc(t.mission || '')}</small>`);
    b.onclick = () => { closeMenu(); selectNamed(t.id); };
    m.appendChild(b);
  }
  m.appendChild(el('div', 'sep'));
  const b = el('button', '', `Pick any point on the map…<small>${state.body === 'moon' ? 'Lunar south pole, 75 to 90° S' : 'Anywhere on Mars'}</small>`);
  b.onclick = () => { closeMenu(); openPicker(); };
  m.appendChild(b);
}

function purposeMenu(m) {
  for (const p of D.man.presets) {
    const b = el('button', state.preset === p.id ? 'on' : '', `${esc(p.label)}<small>${esc(p.blurb)}</small>`);
    b.onclick = () => { closeMenu(); setPreset(p.id); };
    m.appendChild(b);
  }
  // progressive disclosure: the 17 trait weights exist, but only for people who ask
  m.appendChild(el('div', 'sep'));
  const adv = el('button', '', `Adjust trait weights…<small>${state.preset === 'custom' ? 'Custom weights in use' : 'Advanced'}</small>`);
  adv.onclick = () => {
    adv.remove();
    const box = el('div', 'wts');
    for (const tr of D.man.traits) {
      const r = el('label', 'wrow', `<span>${esc(tr.label)}</span><input type="range" min="0" max="3" step="0.5" value="${state.weights[tr.id] || 0}"><span>${state.weights[tr.id] || 0}</span>`);
      const inp = r.querySelector('input');
      inp.oninput = () => { state.weights[tr.id] = +inp.value; r.lastChild.textContent = inp.value; state.preset = 'custom'; $('#qPurpose').textContent = 'custom weights'; rescoreSoon(); };
      box.appendChild(r);
    }
    m.appendChild(box);
  };
  m.appendChild(adv);
}
let rsTimer; const rescoreSoon = () => { clearTimeout(rsTimer); rsTimer = setTimeout(rescore, 60); };

// ------------------------------------------------------------------ point picker dialog (Moon map / Mars globe)
function openPicker() {
  const dlg = $('#picker'), moon = state.body === 'moon';
  $('#pickTitle').textContent = moon ? 'Pick a point near the lunar south pole' : 'Pick a point on Mars';
  $('#moonPick').hidden = !moon; $('#marsPick').hidden = moon;
  $('#pickNote').textContent = moon
    ? 'LROC WAC mosaic, 75 to 90° S. Circles are the Artemis III candidate regions. Traits come from 7.7 km cells (LRO LOLA terrain, LRO Diviner temperature and ice).'
    : 'Drag to turn, click to pick. Traits come from 1° cells (MGS MOLA terrain, TES albedo); rock type is assumed basaltic away from the named sites.';
  dlg.showModal();
  if (moon) setupMoonPicker(); else setupMarsPicker();
}

function setupMoonPicker() {
  const box = $('#moonPick'), marks = $('#moonMarks'), g = D.man.moonGrid;
  if (marks.childElementCount) return;
  const W = g.P * g.mpp;
  for (const t of D.man.targets.filter((t) => t.body === 'moon')) {
    const { x, y } = S.moonXY(D, t.lat, t.lon);
    const m = el('div', 'mmark'); m.style.left = ((x - g.left) / W) * 100 + '%'; m.style.top = ((g.top - y) / W) * 100 + '%';
    m.title = t.name; m.onclick = (e) => { e.stopPropagation(); $('#picker').close(); selectNamed(t.id); };
    marks.appendChild(m);
  }
  box.addEventListener('click', (e) => {
    const r = box.getBoundingClientRect();
    const x = g.left + ((e.clientX - r.left) / r.width) * W, y = g.top - ((e.clientY - r.top) / r.height) * W;
    if (pickMoonXY(x, y)) $('#picker').close();
  });
}
function pickMoonLatLon(lat, lon) { if (lat > -75) return false; const { x, y } = S.moonXY(D, lat, lon); return pickMoonXY(x, y); }
function pickMoonXY(x, y) {
  {
    const tv = S.moonCellTarget(D, x, y);
    if (!tv) return false;
    const ll = S.moonLatLon(D, x, y);
    const gu = tv.geoUnit ? ` Geologic unit ${tv.geoUnit.code}, ${tv.geoUnit.name} (${tv.geoUnit.age}).` : '';
    setTarget({ kind: 'point', body: 'moon', id: null, name: `the point ${latlon(ll.lat, ll.lon)}`, lat: ll.lat, lon: ll.lon, traits: tv.v, geoUnit: tv.geoUnit,
      blurb: `A point you picked on the lunar south pole (7.7 km cell). Terrain from LRO LOLA, ${tv.diviner ? 'temperature and ice from LRO Diviner' : 'temperature from a latitude model (outside Diviner coverage)'}.${gu}` });
    return true;
  }
}

function setupMarsPicker() {
  if (mars) { mars.resize(); return; }
  mars = createGlobe($('#marsPick'), { baseUrl: 'assets/mars.jpg', planetRadiusKm: 3389.5, atmosphere: null, view: { lat: 18, lon: 77, zoom: 1.0 }, minZoom: 0.9, maxZoom: 12 });
  mars.setMarkers(D.man.targets.filter((t) => t.body === 'mars').map((t) => ({ id: t.id, lat: t.lat, lon: t.lon, className: 'mk mtgt', title: t.name, html: '<i></i>' })));
  mars.on('markerclick', (e) => { $('#picker').close(); selectNamed(e.id); });
  mars.on('click', (e) => { $('#picker').close(); pickMarsPoint(e.lat, e.lon); });
}
function pickMarsPoint(lat, lon) {
  const tv = S.marsCellTarget(D, lat, lon);
  setTarget({ kind: 'point', body: 'mars', id: null, name: `the point ${latlon(lat, lon)}`, lat, lon, traits: tv,
    blurb: 'A point you picked on Mars (1° cell). Terrain from MGS MOLA, albedo from TES; rock type assumed basaltic, like most of the Martian crust.' });
}

// ------------------------------------------------------------------ scoring, heat map, lists
const heat = document.createElement('canvas');
// one hue family only: terracotta (weak) to the pale-yellow accent (strong)
const RAMP = [[0, [192, 112, 79, 0]], [0.3, [192, 112, 79, 170]], [0.65, [216, 160, 104, 230]], [0.9, [232, 217, 168, 250]], [1, [244, 234, 196, 255]]];
function rampColor(t) {
  for (let k = 1; k < RAMP.length; k++) if (t <= RAMP[k][0]) {
    const [a, ca] = RAMP[k - 1], [b, cb] = RAMP[k], f = (t - a) / (b - a);
    return ca.map((v, j) => v + (cb[j] - v) * f);
  }
  return RAMP[RAMP.length - 1][1];
}
const LUTC = Array.from({ length: 256 }, (_, i) => rampColor(i / 255));

function rescore() {
  if (!state.target) return;
  state.scores = S.scoreAll(D, state.target.traits, state.weights, state.scores);
  state.sorted = Float32Array.from(state.scores).sort();
  const sc = state.scores, n = sc.length, sorted = state.sorted;
  const lo = sorted[Math.floor(n * 0.75)], hi = sorted[n - 1];
  heat.width = D.nx; heat.height = D.ny;      // heat map: best quarter of Earth's land, brightest = best
  const ctx = heat.getContext('2d'), img = ctx.createImageData(D.nx, D.ny), px = img.data;
  for (let r = 0; r < D.ny; r++) for (let c = 0; c < D.nx; c++) {
    const k = D.cellOf[r * D.nx + c]; if (k < 0) continue;
    const t = (sc[k] - lo) / (hi - lo || 1); if (t <= 0) continue;
    const col = LUTC[Math.min(255, (t * 255) | 0)], o = (r * D.nx + c) * 4;
    px[o] = col[0]; px[o + 1] = col[1]; px[o + 2] = col[2]; px[o + 3] = col[3];
  }
  ctx.putImageData(img, 0, 0);
  earth.setOverlay(heat); earth.setOverlayOpacity(0.9);
  $('#lgLo').textContent = Math.round(lo); $('#lgHi').textContent = `${Math.round(hi)} of 100`;
  state.common = commonness();
  state.cands = S.pickCandidates(D, sc, { n: 10, sepKm: 300, excludeKm: 150, known: D.man.known });
  state.known = D.man.known.filter((k) => k.body === state.body || k.body === 'both').map((k) => {
    const i = S.nearestCell(D, k.lat, k.lon, 3); return i < 0 ? null : { k, i, score: sc[i], pct: pctOf(sc[i]) };
  }).filter(Boolean).sort((a, b) => b.score - a.score);
  renderList(); drawMarkers();
  if (state.detail) openDetail({ ...state.detail, fly: false });
}

const pctOf = (v) => {   // percentile of a score among all Earth land cells
  const a = state.sorted; let lo = 0, hi = a.length;
  while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; }
  return (100 * lo) / a.length;
};
const topPct = (v) => `top ${Math.max(0.1, 100 - pctOf(v)).toFixed(1)}%`;

// A plain-language landscape type for a computed cell, from the same data that was scored.
function cellType(i) {
  const v = (id) => S.earthValue(D, id, i);
  const rock = D.layer.rock && D.man.rock ? D.man.rock.classes[D.layer.rock[i]] : '';
  const lat = Math.abs(D.lat[i]), bare = v('bare'), dry = v('dry'), temp = v('temp');
  if (v('icecover') > 0.5) return 'Glacial';
  if (rock === 'ev') return 'Salt flat';
  if ((rock === 'vb' || rock === 'py') && bare > 0.35) return 'Volcanic terrain';
  if (temp < -4 && bare > 0.4) return lat > 60 ? 'Polar desert' : 'High cold desert';
  if (dry < 60 && bare > 0.6) return 'Hyperarid desert';
  if (dry < 300 && bare > 0.4) return 'Desert';
  if (temp < 0) return 'Tundra';
  return 'Dry upland';
}
const TYPE_LABEL = { planetary: 'Planetary', process: 'Process', astrobiology: 'Astrobiology', petrology: 'Petrology', engineering: 'Engineering', 'human-ops': 'Crew operations' };

// How unusual a strong match is: share of Earth's land that also matches the target on this trait.
// A trait that most of the planet matches (no ice cover, for a Mars equator site) says little, so it is listed last.
function commonness() {
  if (!D.hist) { D.hist = {}; for (const tr of D.man.traits) { const h = new Uint32Array(256), lay = D.layer[tr.id]; for (let k = 0; k < D.cells; k++) h[lay[k]]++; D.hist[tr.id] = h; } }
  const out = {};
  for (const tr of D.man.traits) {
    const tv = S.toT(tr, state.target.traits[tr.id]); let n = 0;
    for (let b = 0; b < 256; b++) if (D.hist[tr.id][b] && S.similarity(tr, tr.transform === 'cat' ? b : tr.min + (b / 255) * (tr.max - tr.min), tv) >= 0.75) n += D.hist[tr.id][b];
    out[tr.id] = n / D.cells;
  }
  return out;
}
const tell = (r) => r.w * r.sim * (1.02 - (state.common[r.tr.id] || 0));

// ---- aspects: the 17 traits folded into 8 groups a reader can hold in mind
const ASPECT = { Terrain: 'Terrain', Surface: 'Surface', Thermal: 'Heat', Illumination: 'Sunlight', 'Water & ice': 'Water, ice', Atmosphere: 'Air', Biology: 'Life', Geology: 'Rock' };
const lvl = (s) => (s >= 0.75 ? 'hi' : s < 0.4 ? 'lo' : '');
function aspects(rows) {
  const g = new Map();
  for (const r of rows) { if (r.w <= 0) continue; const a = g.get(r.tr.group) || { name: r.tr.group, w: 0, s: 0, rows: [] }; a.w += r.w; a.s += r.w * r.sim; a.rows.push(r); g.set(r.tr.group, a); }
  return [...g.values()].map((a) => ({ ...a, sim: a.s / a.w }));
}
function aspectBars(i) {
  const as = aspects(S.explain(D, state.target.traits, state.weights, i));
  return `<div class="asp" role="img" aria-label="${esc(as.map((a) => `${ASPECT[a.name] || a.name} ${Math.round(a.sim * 100)}`).join(', '))}">` +
    as.map((a) => `<span class="${lvl(a.sim)}">${esc(ASPECT[a.name] || a.name)}<i><b style="transform:scaleX(${a.sim.toFixed(2)})"></b></i></span>`).join('') + '</div>';
}
// position of a value (in the trait's transformed space) on Earth's own range, as a 0..1 percentile
function pctT(tr, v) {
  const q = tr.quant; if (!q) return 0.5;
  if (v <= q[0]) return 0; if (v >= q[100]) return 1;
  let lo = 0, hi = 100; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (q[m] <= v) lo = m; else hi = m; }
  return (lo + (q[hi] > q[lo] ? (v - q[lo]) / (q[hi] - q[lo]) : 0)) / 100;
}
function drawProfile(rows, body) {
  $('#pfBody').textContent = body === 'moon' ? 'The Moon target' : 'The Mars target';
  $('#dProfile').innerHTML = aspects(rows).sort((a, b) => b.w - a.w).map((a) => `<section class="pfg ${lvl(a.sim)}"><header><b>${esc(a.name)}</b><span>${Math.round(a.sim * 100)}<small> /100</small></span></header>` +
    a.rows.map((r) => traitScale(r)).join('') + '</section>').join('');
}
// One trait as a dot plot on a value axis that spans Earth's 1st to 99th percentile. Behind it, Earth's distribution
// (rebuilt from the 101 stored percentiles), and the band of values that still earn points against this target.
// Everything is HTML/SVG positioned in percent, so it scales with the panel and needs no chart library.
function traitScale(r) {
  const tr = r.tr, sim = `<span class="sim">${Math.round(r.sim * 100)}% match</span>`;
  if (tr.transform === 'cat') return `<div class="pf ${lvl(r.sim)}"><div class="l"><b>${esc(tr.label)}</b><span>${Math.round(r.sim * 100)}% match</span></div><div class="cat">${esc(fmt(tr.id, r.earth))} here, ${esc(fmt(tr.id, r.target, 'target'))} there</div></div>`;
  const lo = tr.earthLo, hi = tr.earthHi, span = hi - lo || 1;
  const X = (v) => Math.max(0, Math.min(1, (v - lo) / span)) * 100;
  const ev = S.toT(tr, r.earth), tv = S.toT(tr, r.target);
  const below = tv < lo, above = tv > hi;
  // distribution: share of land per bin, from the percentile table
  const B = 40, raw = [];
  for (let b = 0; b < B; b++) raw.push(pctT(tr, lo + (span * (b + 1)) / B) - pctT(tr, lo + (span * b) / B));
  const h = raw.map((v, b) => (raw[Math.max(0, b - 1)] + 2 * v + raw[Math.min(B - 1, b + 1)]) / 4);   // light smoothing: the percentile table is coarse
  const m = Math.max(...h) || 1;
  let d = 'M0 16';
  h.forEach((v, b) => { d += ` L${((b + 0.5) * 100 / B).toFixed(2)} ${(16 - (v / m) * 15).toFixed(2)}`; });
  d += ' L100 16 Z';
  // band of values that still score: target +- tolerance, or for a target beyond Earth, the half of Earth that leans toward it
  let z0, z1;
  if (below) { z0 = 0; z1 = X(tr.quant[50]); } else if (above) { z0 = X(tr.quant[50]); z1 = 100; }
  else { z0 = X(tv - tr.tol); z1 = X(tv + tr.tol); }
  const tPos = X(tv), arrow = below ? '<span class="ar" style="left:-2px">‹</span>' : above ? '<span class="ar" style="right:-2px">›</span>' : '';
  const loLab = fmt(tr.id, S.fromT(tr, lo)), hiLab = fmt(tr.id, S.fromT(tr, hi));
  const tLab = fmt(tr.id, r.target, 'target');
  return `<div class="pf ${lvl(r.sim)}" title="${esc(`${tr.label}: ${fmt(tr.id, r.earth)} here, ${tLab} at the target, ${Math.round(r.sim * 100)}% match`)}">
    <div class="l"><b>${esc(tr.label)}</b><span>${Math.round(r.sim * 100)}% match</span></div><div class="vals">here ${fmt(tr.id, r.earth)} · target ${tLab}</div>
    <div class="sc"><svg viewBox="0 0 100 16" preserveAspectRatio="none" aria-hidden="true"><path d="${d}"/></svg>
      <i class="zn" style="left:${z0.toFixed(1)}%;width:${Math.max(0.6, z1 - z0).toFixed(1)}%"></i><i class="ax"></i>
      <i class="e" style="left:${X(ev).toFixed(1)}%"></i><i class="t" style="left:${(below ? 0 : above ? 100 : tPos).toFixed(1)}%"></i>${arrow}</div>
    <div class="ends"><span>${below ? `<b>‹ ${tLab}</b> · ` : ''}${loLab}</span><span>${hiLab}${above ? ` · <b>${tLab} ›</b>` : ''}</span></div></div>`;
}

function rationale(i) {
  const rows = S.explain(D, state.target.traits, state.weights, i).filter((r) => r.w > 0);
  const strong = rows.filter((r) => r.sim >= 0.75).sort((a, b) => tell(b) - tell(a)).slice(0, 3).map((r) => r.tr.label.toLowerCase());
  const weak = rows.filter((r) => r.sim < 0.4).sort((a, b) => b.w - a.w).slice(0, 1).map((r) => r.tr.label.toLowerCase());
  const join = (a) => (a.length > 1 ? a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1] : a[0] || '');
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  return (strong.length ? `${cap(join(strong))} match` : 'No trait matches strongly') + (weak.length ? `; ${weak[0]} does not.` : '.');
}

function renderList() {
  $$('.tab').forEach((b) => b.classList.toggle('on', b.dataset.tab === state.tab));
  const ol = $('#list'); ol.innerHTML = '';
  const isNew = state.tab === 'new';
  let rows;
  if (isNew) {
    rows = state.cands.map((c, r) => ({ c, rank: r + 1, type: cellType(c.i) }));
    $('#listNote').innerHTML = `The ten best-matching places on Earth that are at least 150 km from every catalogued analog site. <b>Computed, not field-validated.</b><span class="barkey">Bars: how well each aspect matches, from empty (nothing alike) to full (identical).</span>`;
  } else {
    rows = state.known.map((k, r) => ({ k, rank: r + 1, type: TYPE_LABEL[k.k.types[0]] || k.k.types[0] }));
    const pcts = state.known.map((r) => r.pct).sort((a, b) => a - b), med = pcts[Math.floor(pcts.length / 2)] || 0;
    $('#listNote').innerHTML = `${rows.length} sites that agencies and field teams already use, ranked by the same score. The search was never told where they are; their median rank is the <b>${Math.round(med)}th percentile</b> of Earth's land.`;
  }
  // type filter: one row of choices, shown only on request
  const types = [...new Set(rows.map((r) => r.type))];
  const box = $('#types'); box.innerHTML = '';
  for (const ty of ['All', ...types]) {
    const b = el('button', (ty === 'All' ? !state.type : state.type === ty) ? 'on' : '', esc(ty));
    b.onclick = () => { state.type = ty === 'All' ? null : ty; renderList(); };
    box.appendChild(b);
  }
  if (state.type) rows = rows.filter((r) => r.type === state.type);
  const total = rows.length;
  if (!isNew && !state.showAll) rows = rows.slice(0, 12);
  for (const r of rows) {
    let li;
    if (r.c) {
      const p = S.placeName(D, r.c.i);
      li = el('li', 'item', `<span class="n">${String(r.rank).padStart(2, '0')}</span><div>
        <div class="t">${esc(p.title)}</div>
        <div class="w">${p.region ? esc(p.region) + ' · ' : ''}${latlon(r.c.lat, r.c.lon)}</div>
        <div class="why" title="${esc(rationale(r.c.i))}"><span class="ty">${esc(r.type)}</span></div>${aspectBars(r.c.i)}
        <div class="pv">Computed candidate · ${Math.round(r.c.nearestKm).toLocaleString('en')} km from the nearest catalogued site</div></div>
        <span class="sc">${Math.round(r.c.score)}<small>of 100</small></span>`);
      li.onclick = () => openDetail({ i: r.c.i, rank: r.rank });
      li.dataset.key = 'c' + r.c.i;
    } else {
      const k = r.k.k;
      li = el('li', 'item', `<span class="n">${String(r.rank).padStart(2, '0')}</span><div>
        <div class="t">${esc(k.name)}</div>
        <div class="w">${esc(k.country || '')} · ${latlon(k.lat, k.lon)}</div>
        <div class="why"><span class="ty">${esc(r.type)}</span>${esc(k.note || '')}</div>${aspectBars(r.k.i)}
        <div class="pv">Field-validated analog${k.used_by ? ' · used by ' + esc(k.used_by) : ''} · source: ${esc(host(k.source))}</div></div>
        <span class="sc">${Math.round(r.k.score)}<small>of 100</small></span>`);
      li.onclick = () => openDetail({ i: r.k.i, site: k });
      li.dataset.key = 'k' + k.name;
    }
    ol.appendChild(li);
  }
  const more = $('#btnMore'); more.hidden = isNew || state.showAll || total <= 12; more.textContent = `Show all ${total} sites`;
  markActive();
}
function markActive() {
  const d = state.detail, key = d ? (d.site ? 'k' + d.site.name : 'c' + d.i) : null;
  $$('.item').forEach((li) => li.classList.toggle('on', li.dataset.key === key));
}

function drawMarkers() {
  const list = [];
  for (const r of state.known) list.push({ id: 'k:' + r.k.name, lat: r.k.lat, lon: r.k.lon, className: 'mk known', title: `Field-validated analog: ${r.k.name}`, html: '<i></i>', kind: 'known', site: r.k });
  state.cands.forEach((c, r) => list.push({ id: 'c:' + r, lat: c.lat, lon: c.lon, className: 'mk cnd', html: String(r + 1), title: S.placeName(D, c.i).title, kind: 'cand', rank: r }));
  earth.setMarkers(list);
}

function onHover(e) {
  const tip = $('#hoverTip');
  if (!e || !state.scores) { tip.hidden = true; return; }
  const i = S.nearestCell(D, e.lat, e.lon, 0);
  const box = $('.map').getBoundingClientRect();
  tip.style.left = e.clientX - box.left + 'px'; tip.style.top = e.clientY - box.top + 'px';
  if (i < 0) { tip.hidden = true; return; }
  tip.textContent = `${S.placeName(D, i).title} · ${Math.round(state.scores[i])} of 100`;
  tip.hidden = false;
}

// ------------------------------------------------------------------ detail panel
function openDetail({ i, rank = null, site = null, fly = true, searched = null }) {
  const fresh = !state.detail;
  state.detail = { i, rank, site };
  const t = state.target, sc = state.scores[i], p = S.placeName(D, i);
  const la = D.lat[i], lo = D.lon[i];
  $('.main').classList.add('open'); $('#detail').hidden = false; document.body.classList.add('dopen');
  if (fresh) { $('#detail').scrollTop = 0; earth.resize(); }
  if (fly) earth.flyTo({ lat: la, lon: lo, zoom: Math.max(earth.getView().zoom, 3.2), duration: REDUCED ? 0 : 1300 });
  earth.setHighlight({ lat: la, lon: lo, radiusKm: 30, color: '#E8D9A8' });
  markActive();
  const tname = t.named ? shortName(t) : t.name, where = bodyName(t.body);
  $('#dKicker').textContent = site ? 'Field-validated analog' : rank ? `Computed candidate ${String(rank).padStart(2, '0')}` : searched ? `Searched: ${searched}` : 'A place you picked';
  $('#dTitle').textContent = site ? site.name : p.title;
  $('#dSub').textContent = `${site ? p.title + ' · ' : ''}${p.region ? p.region + ' · ' : ''}${latlon(la, lo)} · ${site ? '' : cellType(i) + ' · '}28 km cell`;
  $('#dScore').textContent = Math.round(sc);
  $('#dScoreNote').textContent = `of 100 against ${tname} on ${where}, weighted for ${PURPOSE[state.preset] || 'custom weights'}. That is the ${topPct(sc)} of Earth's land.`;
  // provenance, stated plainly
  $('#dProv').innerHTML = site
    ? `<span class="tag">Field-validated</span>${esc(site.note || '')}${site.used_by ? ` Used by ${esc(site.used_by)}.` : ''} <a href="${esc(site.source)}" target="_blank" rel="noopener">Source: ${esc(host(site.source))}</a>. The score beside it is this tool's own estimate for the surrounding 28 km cell.`
    : `<span class="tag approx">Approximate</span>This match is computed from global satellite data averaged over a 28 km cell. Nobody has validated it in the field, and features smaller than the cell (single craters, lava tubes, outcrops) are not seen.`;
  $('#thTarget').textContent = tname; $('#thT2').textContent = t.body === 'moon' ? 'Moon' : 'Mars';
  const rows = S.explain(D, t.traits, state.weights, i);
  const tb = $('#dTraits'); tb.innerHTML = ''; let group = '';
  for (const r of rows) {
    if (r.tr.group !== group) { group = r.tr.group; tb.appendChild(el('tr', '', `<td class="g" colspan="4">${esc(group)}</td>`)); }
    const tag = r.w <= 0 ? 'not scored' : r.beyond ? 'Earth limit' : label(r.sim);
    tb.appendChild(el('tr', r.w <= 0 ? 'off' : '', `<td>${esc(r.tr.label)}</td><td>${fmt(r.tr.id, r.earth)}</td><td>${fmt(r.tr.id, r.target, 'target')}</td>
      <td><span class="barx"><i class="${r.sim < 0.4 ? 'w' : ''}" style="width:${Math.round(r.sim * 100)}%"></i></span><span class="lbl">${tag}</span></td>`));
  }
  drawProfile(rows, t.body);
  const scored = rows.filter((r) => r.w > 0);
  const holds = scored.filter((r) => r.sim >= 0.75).sort((a, b) => tell(b) - tell(a));
  const weak = scored.filter((r) => r.sim < 0.4).sort((a, b) => b.w - a.w);
  $('#dHolds').innerHTML = holds.length ? holds.slice(0, 5).map((r) => `<li><b>${esc(r.tr.label)}</b>: ${fmt(r.tr.id, r.earth)} here, ${fmt(r.tr.id, r.target, 'target')} on ${where}${r.beyond ? ' (as close as Earth gets)' : ''}</li>`).join('') : '<li>No trait is a strong match at this cell.</li>';
  const B = D.man.bodies[t.body], Eb = D.man.bodies.earth;
  const breaks = weak.slice(0, 4).map((r) => `<li><b>${esc(r.tr.label)}</b>: ${fmt(r.tr.id, r.earth)} here, ${fmt(r.tr.id, r.target, 'target')} on ${where}${r.beyond ? `. Beyond anything on Earth, whose extreme 1% is ${fmt(r.tr.id, S.fromT(r.tr, r.target < S.fromT(r.tr, r.tr.earthLo) ? r.tr.earthLo : r.tr.earthHi))}` : ''}</li>`);
  breaks.push(`<li class="muted"><b>Gravity</b>: ${B.gravity} m/s² there, ${Eb.gravity} m/s² here. No place on Earth reproduces it.</li>`);
  breaks.push(`<li class="muted"><b>Atmosphere</b>: ${fmt('pressure', S.earthValue(D, 'pressure', i))} of air here, ${t.body === 'moon' ? 'hard vacuum' : '0.6 kPa of CO₂'} there.</li>`);
  breaks.push(`<li class="muted"><b>Radiation</b>: ${esc(B.radiation)}, against ${esc(Eb.radiation)}.</li>`);
  $('#dBreaks').innerHTML = breaks.join('');
  const uses = [...new Set(holds.filter((r) => USE[r.tr.id]).map((r) => USE[r.tr.id]))].slice(0, 3);
  $('#dHelps').innerHTML = uses.length ? uses.map((u) => `<li>${u[0].toUpperCase() + u.slice(1)}.</li>`).join('') : '<li>Weak overall match: better used as a contrast site.</li>';
  const src = D.man.sources || {};
  $('#dSources').innerHTML = `Data behind this card. Earth: terrain from AWS Terrain Tiles (SRTM, GMTED2010); temperature, wind and soil moisture from NASA POWER (MERRA-2); day-night swing from JAXA GCOM-C; rainfall from JAXA GSMaP; vegetation from MODIS NDVI (JAXA JASMES); land cover from ESA WorldCover${src.rock ? '; rock type from GLiM (Hartmann &amp; Moosdorf 2012)' : ''}. ${t.body === 'moon' ? 'Moon: LRO LOLA terrain, LRO Diviner temperature and ice, USGS Unified Geologic Map.' : 'Mars: MGS MOLA terrain, TES albedo, latitude averages for temperature and ice.'} Full list under Method &amp; sources.`;
  drawChips(t, la, lo);
  const orb = $('#dOrbit');
  orb.ontoggle = () => { if (orb.open) drawOrbit(t, la, lo); };
  if (orb.open) drawOrbit(t, la, lo); else drawOrbitLinks(t, la, lo);
}

function closeDetail() {
  if (!state.detail && $('#detail').hidden) return;
  $('#detail').hidden = true; $('.main').classList.remove('open'); document.body.classList.remove('dopen'); state.detail = null;
  if (earth) { earth.setHighlight(null); earth.resize(); if (!state.touring) earth.flyTo({ zoom: 1.15, duration: REDUCED ? 0 : 900 }); }
  markActive();
}

const ctxImg = {};
const loadImg = (src) => (ctxImg[src] ||= new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src; }));
// For a point picked by hand there is no prepared elevation close-up, so show the surrounding ground from the body's own mosaic,
// with a square marking the cell that is actually scored.
async function drawContext(c, t) {
  const g = c.getContext('2d'), W = c.width; let sx, sy, sw, spanKm, cellKm, src, im;
  if (t.body === 'moon') {
    im = await loadImg('assets/moon_spole.jpg'); const G = D.man.moonGrid, ext = G.P * G.mpp, { x, y } = S.moonXY(D, t.lat, t.lon);
    spanKm = 120; cellKm = 7.7; sw = (spanKm * 1000 / ext) * im.width; sx = ((x - G.left) / ext) * im.width - sw / 2; sy = ((G.top - y) / ext) * im.height - sw / 2; src = 'LROC WAC mosaic';
  } else {
    im = await loadImg('assets/mars.jpg'); const kmPx = (2 * Math.PI * 3389.5) / im.width;
    spanKm = 1400; cellKm = 59; sw = spanKm / kmPx; sx = ((t.lon + 180) / 360) * im.width - sw / 2; sy = ((90 - t.lat) / 180) * im.height - sw / 2; src = 'MOLA relief with TES albedo';
  }
  g.fillStyle = '#14181B'; g.fillRect(0, 0, W, W); g.imageSmoothingQuality = 'high';
  g.drawImage(im, sx, sy, sw, sw, 0, 0, W, W);
  const s = (cellKm / spanKm) * W; g.strokeStyle = '#E8D9A8'; g.lineWidth = Math.max(1.5, W / 250); g.strokeRect(W / 2 - s / 2, W / 2 - s / 2, s, s);
  return `${spanKm.toLocaleString('en')} km across · ${src} · the square is the ${cellKm} km cell that is scored`;
}

async function drawChips(t, la, lo) {
  const seq = ++chipSeq;                                   // a slower, older request must never paint over a newer one
  const ct = $('#chipTarget'), ce = $('#chipEarth');
  const dpr = Math.min(2, window.devicePixelRatio || 1), sz = Math.round(ct.clientWidth * dpr) || 380;
  for (const c of [ct, ce]) { c.width = sz; c.height = sz; }
  const msg = (c, text) => { const g = c.getContext('2d'); g.fillStyle = '#060708'; g.fillRect(0, 0, c.width, c.height); g.fillStyle = 'rgba(242,238,232,.6)'; g.font = `${13 * dpr}px system-ui`; g.textAlign = 'center'; wrapText(g, text, c.width / 2, c.height / 2, c.width * 0.8, 18 * dpr); };
  const statLine = (s) => `slope ${s.slopeMeanDeg.toFixed(1)}° · roughness ${Math.round(s.roughnessM)} m · relief ${Math.round(s.reliefM).toLocaleString('en')} m`;
  // target chip
  if (t.named && t.chip) {
    try {
      const bytes = await S.fetchBytes(`data/chips/${t.id}.bin.gz`); const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      if (seq !== chipSeq) return;
      const g = gridFromInt16(buf, t.chip.px, t.chip.metersPerPixel, t.chip.sizeKm);
      renderHillshade(ct, g, { palette: 'moon', exaggeration: t.body === 'mars' ? 2 : 1.2, seaLevel: false });
      $('#capTarget').innerHTML = `<b>${esc(shortName(t))}, ${t.body === 'moon' ? 'Moon' : 'Mars'}</b> · ${t.chip.sizeKm} km · ${t.body === 'moon' ? 'LRO LOLA 30 m' : 'MGS MOLA 463 m'}<br>${statLine(terrainStats(g, { baselineM: BASELINE_M }))}`;
    } catch { msg(ct, 'Target terrain unavailable'); }
  } else {
    try {
      const note = await drawContext(ct, t); if (seq !== chipSeq) return;
      $('#capTarget').innerHTML = `<b>Picked point, ${t.body === 'moon' ? 'Moon' : 'Mars'}</b> · ${latlon(t.lat, t.lon)}<br>${note}`;
    } catch { msg(ct, 'Target image unavailable'); $('#capTarget').innerHTML = `<b>${esc(t.name)}</b>`; }
  }
  // Earth chip, live from open elevation tiles
  if (abortChip) abortChip.abort();
  abortChip = new AbortController();
  msg(ce, 'Loading Earth terrain…'); $('#capEarth').innerHTML = '<b>Earth site</b> · loading';
  try {
    const g = await fetchEarthTerrain({ lat: la, lon: lo, sizeKm: 28, px: 512, signal: abortChip.signal });
    if (seq !== chipSeq) return;
    renderHillshade(ce, g, { palette: 'moon', exaggeration: 1.2 });   // same neutral rendering on both sides, so the eye compares shape, not colour
    $('#capEarth').innerHTML = `<b>Earth site</b> · 28 km · AWS Terrain Tiles z${g.zoom}<br>${statLine(terrainStats(g, { baselineM: BASELINE_M }))}`;
  } catch (e) {
    if (e.name === 'AbortError') return;
    msg(ce, e.code === 'OUT_OF_COVERAGE' ? 'Live terrain tiles stop at 85° latitude.' : 'Live terrain needs an internet connection. Scores still work offline.');
    $('#capEarth').innerHTML = '<b>Earth site</b>';
  }
}
function wrapText(g, text, x, y, maxW, lh) {
  const words = text.split(' '), lines = []; let line = '';
  for (const w of words) { const t = line ? line + ' ' + w : w; if (g.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t; }
  lines.push(line);
  lines.forEach((l, k) => g.fillText(l, x, y + (k - (lines.length - 1) / 2) * lh));
}

// ------------------------------------------------------------------ satellite view and official portals (loaded only when opened)
const SAT = {
  s2: { cap: 'Copernicus Sentinel-2 cloudless mosaic (ESA data processed by EOX, CC BY-NC-SA 4.0), 10 m pixels',
    urls: (b) => ['s2cloudless-2023', 's2cloudless-2022', 's2cloudless-2020'].map((l) => `https://tiles.maps.eox.at/wms?service=WMS&request=GetMap&version=1.1.1&layers=${l}&styles=&format=image/jpeg&srs=EPSG:4326&bbox=${b}&width=768&height=480`) },
  modis: { cap: 'NASA Blue Marble from MODIS, served by NASA GIBS (the imagery behind Worldview), 500 m pixels',
    urls: (b) => ['BlueMarble_NextGeneration', 'BlueMarble_ShadedRelief'].map((l) => `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=${l}&STYLES=&FORMAT=image/jpeg&SRS=EPSG:4326&BBOX=${b}&WIDTH=768&HEIGHT=480`) },
  viirs: { cap: 'NASA VIIRS Black Marble night lights (GIBS): dark means remote, a real factor for analog field campaigns',
    urls: (b) => ['VIIRS_Black_Marble', 'VIIRS_CityLights_2012'].map((l) => `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=${l}&STYLES=&FORMAT=image/png&SRS=EPSG:4326&BBOX=${b}&WIDTH=768&HEIGHT=480`) },
};
let satSrc = 's2';
function drawOrbit(t, la, lo) {
  const half = 28 / 111.32, hl = Math.min(30, 1.6 * half / Math.max(0.05, Math.cos(la * Math.PI / 180)));
  const W = (lo - hl).toFixed(4), E = (lo + hl).toFixed(4), Sb = Math.max(-90, la - half).toFixed(4), N = Math.min(90, la + half).toFixed(4);
  const bbox = `${W},${Sb},${E},${N}`;
  const img = $('#dSat'), cap = $('#capSat');
  const show = () => {
    const src = SAT[satSrc];
    cap.textContent = `${src.cap}. Dashed box: the 28 km cell that was scored.`;
    const urls = src.urls(bbox); let k = 0;
    img.style.opacity = 0.35; img.alt = 'Satellite view of the Earth cell';
    img.onload = () => { img.style.opacity = 1; };
    img.onerror = () => {
      if (++k < urls.length) { img.src = urls[k]; return; }
      img.style.opacity = 1; img.alt = ''; img.removeAttribute('src'); cap.textContent = 'Satellite imagery could not be loaded (offline?). Use the links below.';
    };
    img.src = urls[0];
  };
  document.querySelectorAll('.sattabs button').forEach((b) => {
    b.classList.toggle('on', b.dataset.src === satSrc);
    b.onclick = () => { satSrc = b.dataset.src; document.querySelectorAll('.sattabs button').forEach((x) => x.classList.toggle('on', x === b)); show(); };
  });
  show();
  drawOrbitLinks(t, la, lo);
}
function drawOrbitLinks(t, la, lo) {
  const half = 28 / 111.32, hl = Math.min(20, half / Math.max(0.05, Math.cos(la * Math.PI / 180)));
  const W = (lo - hl).toFixed(4), E = (lo + hl).toFixed(4), Sb = Math.max(-90, la - half).toFixed(4), N = Math.min(90, la + half).toFixed(4);
  const L = [
    ['NASA', 'Worldview', 'daily MODIS / VIIRS imagery of this place', `https://worldview.earthdata.nasa.gov/?v=${W},${Sb},${E},${N}&l=MODIS_Terra_CorrectedReflectance_TrueColor,Coastlines_15m`],
    ['NASA', 'Earthdata Search', 'every NASA dataset covering this cell', `https://search.earthdata.nasa.gov/search?sb=${W}%2C${Sb}%2C${E}%2C${N}`],
    ['ESA', 'Copernicus Browser', 'Sentinel-1 radar and Sentinel-2 imagery, any date', `https://browser.dataspace.copernicus.eu/?zoom=11&lat=${la.toFixed(4)}&lng=${lo.toFixed(4)}`],
    ['JAXA', 'JAXA Earth viewer', 'GCOM-C temperature, GSMaP rain, ALOS terrain used here', `https://data.earth.jaxa.jp/app/viewer/v2/?lat=${la.toFixed(3)}&lng=${lo.toFixed(3)}&zoom=8`],
    ['JAXA', 'G-Portal', 'ALOS-2 PALSAR-2 radar and GCOM scenes to order', 'https://gportal.jaxa.jp/gpr/?lang=en'],
    ['CSA', 'EODMS (RADARSAT)', 'RADARSAT-1 / RCM radar scenes for surface roughness', 'https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html'],
  ];
  const T = t.body === 'moon'
    ? [['NASA', 'Moon Trek', `LRO LOLA, LROC and Diviner layers at ${t.name}`, 'https://trek.nasa.gov/moon/'],
       ['NASA', 'LRO Diviner (PDS)', 'the polar temperature and ice product used for this target', 'https://pds-geosciences.wustl.edu/missions/lro/diviner.htm']]
    : [['NASA', 'Mars Trek', `MOLA, HiRISE and CTX layers at ${t.name}`, 'https://trek.nasa.gov/mars/']];
  $('#dLinks').innerHTML = [...L, ...T].map(([ag, name, what, href]) =>
    `<li><a href="${esc(href)}" target="_blank" rel="noopener"><span class="ag">${ag}</span><b>${esc(name)}</b><small>${esc(what)}</small></a></li>`).join('');
  $('#dLinksNote').textContent = 'Earth links open on this exact cell. Radar (Sentinel-1, ALOS-2, RADARSAT) is the next step for comparing surface roughness with LRO Mini-RF.';
}


// ------------------------------------------------------------------ guided tour (for the 60 s demo video)
let tourToken = 0;
function caption(text) {
  let c = $('.caption'); if (!c) { c = el('div', 'caption'); document.body.appendChild(c); }
  c.innerHTML = text; c.hidden = !text;
}
function stopTour() { if (!state.touring) return; state.touring = false; document.body.classList.remove('touring'); tourToken++; caption(''); $('#btnTour').textContent = 'Play tour'; }
async function runTour() {
  state.touring = true; document.body.classList.add('touring'); const tok = ++tourToken; $('#btnTour').textContent = 'Stop tour';
  const alive = () => tok === tourToken;
  const steps = [
    { t: 'shackleton-connecting-ridge', p: 'polar', c: 'Artemis III will land near the lunar south pole. <b>Where on Earth behaves like Shackleton\'s rim?</b>' },
    { c: 'We score all <b>318,332</b> land cells on Earth on 17 traits: terrain, rock, sunlight, cold, ice, dryness, life.', wait: 4200, zoomOut: true },
    { cand: 0, c: 'Low sun, deep cold and bare rocky relief point to <b>Peary Land, North Greenland</b>: 850 km from the nearest catalogued analog.' },
    { t: 'slater-plain', p: 'landing', cand: 0, c: 'Change the mission to <b>rover &amp; landing tests</b> for Slater Plain, and the answer moves to the dry Andes.' },
    { t: 'jezero-perseverance', p: 'overall', cand: 0, c: 'On Mars, Jezero crater\'s closest Earth match is in the eastern Sahara, not one of the usual test sites.' },
    { t: 'arcadia-planitia', p: 'isru', cand: 0, c: 'For ice prospecting at Arcadia Planitia, the Tibetan Plateau\'s frozen dry ground wins.' },
    { c: 'Every match says where the analogy holds, where it breaks, and how it helps exploration. <b>Ground Truth: open data, any browser.</b>', wait: 5000 },
  ];
  try {
    for (const s of steps) {
      if (!alive()) return;
      if (s.t) { if (s.p) setPreset(s.p, false); selectNamed(s.t); }
      caption(s.c);
      if (s.zoomOut) { closeDetail(); await earth.flyTo({ lat: 10, lon: 40, zoom: 1, duration: 1400 }); }
      if (s.cand != null && state.cands[s.cand]) { await sleep(900); if (!alive()) return; openDetail({ i: state.cands[s.cand].i, rank: s.cand + 1 }); }
      await sleep(s.wait || 6500);
    }
  } finally { if (alive()) { closeDetail(); stopTour(); } }
}

// ------------------------------------------------------------------ method and sources
async function openAbout() {
  let F = null; try { F = await (await fetch('data/findings.json')).json(); } catch {}
  const v = F && F.validation;
  const vrow = (b, n) => v && v[b] ? `<tr><td>${n}</td><td>${v[b].auc_env.toFixed(2)} (${v[b].nenv} vs ${v[b].nneg})</td><td>${v[b].auc_geo.toFixed(2)} (${v[b].ngeo} vs ${v[b].nneg})</td><td>${Math.round(v[b].median_pct)}th</td></tr>` : '';
  const has = (id) => D.man.traits.some((t) => t.id === id);
  const src = D.man.sources || {};
  const abl = F && F.ablation ? F.ablation : [];
  const arow = (r) => `<tr${r.rejected ? ' class="muted"' : ''}><td>${esc(r.step)}</td><td>${r.mars_env.toFixed(2)} / ${r.mars_geo.toFixed(2)}</td><td>${r.moon_env.toFixed(2)} / ${r.moon_geo.toFixed(2)}</td></tr>`;
  $('#aboutBody').innerHTML = `
  <h2>How Ground Truth works</h2>
  <p>NASA's challenge asks for <i>new</i> Earth analogs for Moon base and Mars sites, found globally and systematically, with an honest account of where each analogy holds and where it breaks. Ground Truth scores every land cell on Earth against a Moon or Mars target, trait by trait, using the official NASA, ESA, JAXA and CSA resources wherever they could be used.</p>
  <h3>Method</h3>
  <ol>
    <li><b>One grid for Earth.</b> Every land cell of 0.25° (about 28 km, ${D.cells.toLocaleString('en')} cells) gets ${D.man.traits.length} traits.</li>
    <li><b>Same ruler on three worlds.</b> Slope, roughness and relief are measured the same way on Earth, the Moon (LRO LOLA) and Mars (MGS MOLA): elevation at about 1.85 km pixels, 15 × 15 pixel window.</li>
    <li><b>Targets.</b> The nine Artemis III candidate regions and Shackleton's rim, plus 15 Mars landing, human-mission and cave sites. Or click any point on either map.</li>
    <li><b>Similarity.</b> Per trait, 1 − |Earth − target| / tolerance. When the target is beyond anything on Earth (−150 °C, a 2° noon sun), the trait ranks places toward Earth's own extreme and the card says "Earth limit". Rock type uses a published-geology lookup table (how well each Earth rock class stands in for each target rock family).</li>
    <li><b>Mission presets</b> weight traits for what the analog is <i>for</i> (Foucher et al. 2021 "functional analogues"): rover and landing tests, polar base operations, ice prospecting, instruments, crew training.</li>
    <li><b>New candidates</b> are the best cells at least 300 km apart and more than 150 km from all 107 catalogued analog sites, so Antarctica, Atacama, Iceland and Hawaii only show up when they genuinely win.</li>
  </ol>
  <h3>The challenge's considerations, one by one</h3>
  <table>
    <tr><th>Consideration</th><th>How Ground Truth answers it</th></tr>
    <tr><td>Geology and mineralogy</td><td>${has('rock') ? 'Rock type trait: Earth lithology (GLiM) vs the USGS Unified Geologic Map of the Moon and the published geology of each Mars site.' : 'USGS Unified Geologic Map of the Moon gives every Moon cell a rock family; Mars sites carry their published geology. (Earth rock map being added.)'} Surface albedo and barren ground add what cameras and spectrometers see.</td></tr>
    <tr><td>Terrain and topography</td><td>Slope, roughness and local relief on one ruler for all three bodies; live 28 km terrain close-ups side by side.</td></tr>
    <tr><td>Temperature and illumination</td><td>LRO Diviner temperatures for the Moon; JAXA GCOM-C day-night surface temperature swing for Earth; noon sun elevation from latitude and axial tilt; LROC WAC imagery shows the real polar shadows.</td></tr>
    <tr><td>Water, ice, permafrost</td><td>LRO Diviner depth-to-stable-ice for every Moon cell; Mars ground ice by latitude (SWIM); Earth permafrost from air temperature; JAXA GSMaP rainfall; soil moisture.</td></tr>
    <tr><td>Dust and wind</td><td>Aerosol optical depth (NASA CERES) and mean wind (MERRA-2).</td></tr>
    <tr><td>Biology</td><td>Plant greenness from MODIS NDVI (JAXA JASMES) and bare ground from ESA WorldCover: the lifeless end of Earth is what life-detection tests need.</td></tr>
    <tr><td>Caves and lava tubes</td><td>Arsia Mons cave skylights are a Mars target; with rock type they point to basaltic lava plains on Earth where tubes form. Single caves are smaller than a cell, so this is a pointer for field checks.</td></tr>
    <tr><td>Exploration operations</td><td>Mission presets, a "how it helps exploration" list on every card, and NASA VIIRS night lights in the satellite view as a remoteness check.</td></tr>
    <tr><td>Processes, not just places</td><td>Rock families are processes: impact-shattered highland crust, volcanism, lake sedimentation, evaporation, periglacial freeze-thaw, glaciers.</td></tr>
    <tr><td>Scale</td><td>Traits at 28 km for the global search; terrain at 1.85 km; live elevation close-up; 10 m Copernicus Sentinel-2 view of each cell.</td></tr>
    <tr><td>Earth's limits</td><td>Every card lists gravity, vacuum or thin CO₂ air and surface radiation, which no place on Earth reproduces, and flags every trait where the target is beyond Earth.</td></tr>
  </table>
  <h3>Official challenge resources</h3>
  <table>
    <tr><th>Resource</th><th>Used for</th></tr>
    <tr><td>NASA LRO: LOLA</td><td>Moon south-pole terrain (30 m DEM), all terrain traits</td></tr>
    <tr><td>NASA LRO: LROC</td><td>WAC south-pole mosaic as the Moon picker map</td></tr>
    <tr><td>NASA LRO: Diviner (PDS)</td><td>${D.man.moonDiviner ? 'Polar resource product: mean and maximum temperature and depth to stable ice for every Moon cell' : 'Not loaded'}</td></tr>
    <tr><td>NASA PDS / USGS</td><td>MOLA and TES for Mars; Unified Geologic Map of the Moon</td></tr>
    <tr><td>NASA Earthdata / Worldview (GIBS)</td><td>Blue Marble and VIIRS night-light views of each cell; deep links to Worldview and Earthdata Search; NASA POWER (MERRA-2, CERES) climate</td></tr>
    <tr><td>JAXA (G-Portal products via the JAXA Earth API)</td><td>${esc(src.trange || 'GCOM-C land surface temperature')}; ${esc(src.dry || 'GSMaP rainfall')}; ${esc(src.ndvi || 'MODIS NDVI')}. AMSR2 soil moisture was tested and rejected (it lowered validation scores).</td></tr>
    <tr><td>ESA Copernicus</td><td>WorldCover 10 m land cover; Sentinel-2 cloudless view of each cell; Copernicus Browser deep links</td></tr>
    <tr><td>CSA RADARSAT, LRO Mini-RF, LEND</td><td>Linked, not yet scored: radar roughness (RADARSAT, Sentinel-1, ALOS-2 vs Mini-RF) and neutron hydrogen (LEND) are the next traits</td></tr>
  </table>
  <h3>Validation</h3>
  <p>Nothing was tuned on known sites. AUC is the chance a known analog outscores a clear non-analog (rainforest, farmland, cities, wetlands, taiga, ice sheet). 0.5 is a coin flip.</p>
  <table><tr><th>Body</th><th>Environment analogs vs non-analogs</th><th>Geology-only analogs vs non-analogs</th><th>All catalogued sites, median percentile</th></tr>${vrow('mars', 'Mars')}${vrow('moon', 'Moon')}</table>
  ${abl.length ? `<p class="small">What each official dataset added (AUC environment / geology):</p><table><tr><th>Step</th><th>Mars</th><th>Moon</th></tr>${abl.map(arow).join('')}</table>` : ''}
  <h3>Limitations</h3>
  <ul>
    <li>28 km cells: a small crater or lava tube inside a cell is invisible. Use the close-ups and field data to confirm.</li>
    <li>Moon temperature swing is approximated as 2 × (maximum − mean) from Diviner; Mars temperature, dust and wind are latitude averages, not a climate model. Moon coverage is 75–90°S.</li>
    <li>Artemis III region coordinates are approximate points inside each region.</li>
    <li>No permits, access or logistics layer.</li>
  </ul>
  <h3>Other open data</h3>
  <table>
    <tr><td>Earth elevation</td><td>AWS Terrain Tiles (SRTM, GMTED2010, ETOPO1 and others)</td></tr>
    <tr><td>Earth vectors and names</td><td>Natural Earth 1:10m</td></tr>
    <tr><td>Targets</td><td>NASA Artemis III candidate regions (2024); Wueller et al. 2026, doi:10.1029/2025JE009434; Boazman et al. 2022, PSJ 3:275; NASA NSSDC; Cushing et al. 2007 (Mars cave skylights)</td></tr>
    <tr><td>Known analogs</td><td>NASA Planetary Analog Explorer; Foucher et al. 2021, Planet. Space Sci. 197:105162; project literature list (107 sites)</td></tr>
    <tr><td>Body facts</td><td>Hassler et al. 2014 (Curiosity RAD); Zhang et al. 2020 (Chang'e-4 LND); Paige et al. 2010 (Diviner); Morgan et al. 2021 (Mars SWIM)</td></tr>
  </table>
  <p class="small muted">Built for the NASA Space Apps Challenge 2026, challenge "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars". All processing code is in the pipeline folder; the website is static.</p>`;
  $('#about').showModal();
}

boot().catch((e) => { console.error(e); });
