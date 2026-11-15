// globe.js — zero-dependency WebGL globe for Terra Twin.
//
// The planet is not a mesh: one full-screen triangle is drawn and every pixel is
// ray-cast against a unit sphere in the fragment shader. That gives an exact,
// analytically antialiased limb, exact picking (same maths in JS), and room for
// the heat overlay, graticule, highlight ring and atmosphere in a single pass.
// Rendering is on demand: a frame is drawn only when something changed.
//
//   import { createGlobe } from './js/globe.js';
//   const globe = createGlobe(el, { baseUrl: 'assets/earth.jpg', planetRadiusKm: 6371 });
//
// Textures are equirectangular: u=0 is lon -180, u=1 is lon +180, top row is lat +90.

const DEG = Math.PI / 180;
const FOV = 25 * DEG;      // field of view across the shorter canvas side
const FILL = 0.86;         // globe diameter / shorter canvas side at zoom 1
const D1 = Math.hypot(1, 1 / (Math.tan(FOV / 2) * FILL));   // camera distance (radii) at zoom 1
const MAX_MARKERS = 400;

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const clampLat = (l) => clamp(l, -89.5, 89.5);
const wrapLon = (l) => ((l + 180) % 360 + 360) % 360 - 180;
const isPOT = (n) => (n & (n - 1)) === 0;
const unit = (lat, lon) => {            // lat/lon (deg) -> world unit vector (y = north, lon 0 = +z, lon 90E = +x)
  const c = Math.cos(lat * DEG);
  return [c * Math.sin(lon * DEG), Math.sin(lat * DEG), c * Math.cos(lon * DEG)];
};
function cssRgb(css) {                  // any CSS colour -> [r, g, b] in 0..1
  const c = document.createElement('canvas').getContext('2d');
  c.fillStyle = css; c.fillRect(0, 0, 1, 1);
  const d = c.getImageData(0, 0, 1, 1).data;
  return [d[0] / 255, d[1] / 255, d[2] / 255];
}

const CSS = `
.ag-globe{position:relative;width:100%;height:100%;overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;cursor:grab;-webkit-tap-highlight-color:transparent}
.ag-globe>canvas{position:absolute;left:0;top:0;width:100%;height:100%;display:block}
.ag-markers{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
.ag-marker{position:absolute;left:0;top:0;pointer-events:auto;cursor:pointer;white-space:nowrap;will-change:transform}
.ag-marker:empty{width:10px;height:10px;box-sizing:border-box;border-radius:50%;background:#fff;border:2px solid rgba(8,12,20,.85)}`;

const FRAG = `
uniform vec2 uRes;        // drawing buffer size, px
uniform float uF;         // focal length, px
uniform float uD;         // camera distance, planet radii
uniform mat3 uRot;        // camera space -> world space
uniform sampler2D uBase;  // equirectangular base map
uniform sampler2D uOver;  // equirectangular overlay, premultiplied alpha
uniform float uHasBase, uOverOp, uGrat, uTime;
uniform vec4 uAtm;        // atmosphere rgb, strength
uniform vec4 uHi;         // highlight centre (world unit vector), angular radius (<0 = off)
uniform vec3 uHiCol;
const float PI = 3.14159265359;

vec3 hit(vec2 px) {       // camera-space point where the ray through pixel px meets the unit sphere
  vec3 d = normalize(vec3(px - 0.5 * uRes, -uF));
  float b = uD * d.z;
  return normalize(vec3(0.0, 0.0, uD) + d * (-b - sqrt(max(b * b - uD * uD + 1.0, 0.0))));
}

void main() {
  vec2 px = gl_FragCoord.xy;
  float Rs = uF / sqrt(uD * uD - 1.0);              // the silhouette is an exact circle of this radius
  float r = length(px - 0.5 * uRes);
  float cover = clamp(Rs - r + 0.5, 0.0, 1.0);      // antialiased limb

  float h = max(r - Rs, 0.0) / Rs;                  // atmosphere halo outside the limb
  float glow = (exp(-h * 30.0) * 0.5 + exp(-h * 7.0) * 0.14) * uAtm.a;
  vec4 col4 = vec4(uAtm.rgb * glow, glow);

  if (cover > 0.0) {
    vec3 n = hit(px);                               // camera-space normal
    vec3 p = uRot * n;                              // world-space point on the sphere
    vec3 dx = uRot * hit(px + vec2(1.0, 0.0)) - p;  // surface step per screen pixel, used for
    vec3 dy = uRot * hit(px + vec2(0.0, 1.0)) - p;  // seam-free, pole-safe texture gradients
    float h2 = max(p.x * p.x + p.z * p.z, 1e-7);
    vec2 uv = vec2(atan(p.x, p.z) / (2.0 * PI) + 0.5, acos(clamp(p.y, -1.0, 1.0)) / PI);
    vec2 gx = vec2((p.z * dx.x - p.x * dx.z) / (2.0 * PI * h2), -dx.y / (PI * sqrt(h2)));
    vec2 gy = vec2((p.z * dy.x - p.x * dy.z) / (2.0 * PI * h2), -dy.y / (PI * sqrt(h2)));

    vec3 col = mix(vec3(0.055, 0.075, 0.105), TEXG(uBase, uv, gx, gy).rgb, uHasBase);
    vec4 ov = TEXG(uOver, uv, gx, gy);
    col = col * (1.0 - ov.a * uOverOp) + ov.rgb * uOverOp;

    if (uGrat > 0.0) {                              // lat/lon lines every 30 degrees, ~1 px wide
      vec2 g = uv * vec2(12.0, 6.0);
      vec2 w = vec2(length(vec2(gx.x, gy.x)) * 12.0, length(vec2(gx.y, gy.y)) * 6.0);
      vec2 a = clamp(1.2 - abs(fract(g + 0.5) - 0.5) / max(w, 1e-7), 0.0, 1.0);
      a.x *= smoothstep(0.03, 0.2, sqrt(h2));       // meridians fade out at the poles
      col = mix(col, vec3(1.0), max(a.x, a.y) * 0.2 * uGrat);
    }

    // camera-tied light, slightly up and to the left, with gentle limb darkening
    float mu = clamp(dot(n, normalize(vec3(0.0, 0.0, uD) - n)), 0.0, 1.0);
    float diff = clamp(dot(n, normalize(vec3(-0.32, 0.36, 1.0))), 0.0, 1.0);
    col *= (0.46 + 0.6 * pow(diff, 0.8)) * (0.8 + 0.2 * sqrt(mu));
    col += uAtm.rgb * pow(1.0 - mu, 3.0) * 0.55 * uAtm.a;   // atmospheric rim

    if (uHi.w > 0.0) {                              // highlight ring, drawn after lighting so it stays bright
      float pa = sqrt(length(dx) * length(dy));     // radians per pixel here
      float ang = 2.0 * asin(clamp(0.5 * length(p - uHi.xyz), 0.0, 1.0));
      float ra = max(uHi.w, 7.0 * pa);              // never smaller than ~7 px on screen
      float dpx = abs(ang - ra) / pa;
      float pulse = 0.5 + 0.5 * sin(uTime * 2.6);
      float ring = 1.0 - smoothstep(0.9, 2.3, dpx);
      float halo = exp(-dpx / (4.0 + 6.0 * pulse)) * (0.22 + 0.2 * pulse);
      float fill = step(ang, ra) * 0.07;
      col = mix(col, uHiCol, clamp(ring + halo + fill, 0.0, 1.0));
    }
    col4 = mix(col4, vec4(col, 1.0), cover);
  }
  col4.rgb += (fract(sin(dot(px, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0 * col4.a;   // dither
  fragColor = col4;
}`;

export function createGlobe(container, opts = {}) {
  const o = Object.assign({
    baseUrl: null, planetRadiusKm: 6371, atmosphere: '#5aa9ff', graticule: false,
    minZoom: 0.8, maxZoom: 40, autoRotate: false, pulse: true,
  }, opts);
  const view = { lat: 20, lon: 10, zoom: 1, ...(opts.view || {}) };
  view.lat = clampLat(view.lat); view.lon = wrapLon(view.lon); view.zoom = clamp(view.zoom, o.minZoom, o.maxZoom);

  // ---- DOM ------------------------------------------------------------------
  if (!document.getElementById('ag-globe-css')) {
    const st = document.createElement('style');
    st.id = 'ag-globe-css'; st.textContent = CSS; document.head.appendChild(st);
  }
  const root = document.createElement('div'); root.className = 'ag-globe';
  const canvas = document.createElement('canvas');
  const layer = document.createElement('div'); layer.className = 'ag-markers';
  root.append(canvas, layer); container.appendChild(root);

  const attrs = { alpha: true, antialias: false, depth: false, stencil: false, premultipliedAlpha: true };
  let gl = canvas.getContext('webgl2', attrs);
  const gl2 = !!gl;
  if (!gl) gl = canvas.getContext('webgl', attrs) || canvas.getContext('experimental-webgl', attrs);
  if (!gl) { root.remove(); throw new Error('WebGL is not available in this browser'); }

  // ---- state ----------------------------------------------------------------
  const listeners = {};
  const markers = new Map();         // id -> { el, p, data, html, shown }
  const ptrs = new Map();            // active pointers: id -> { x, y }
  let W = 0, H = 0, raf = 0, lastT = 0, lastDraw = 0, dirty = true, dead = false, lost = false;
  let U = {}, baseTex = null, overTex = null, lod = true, aniso = null, maxAniso = 1;
  let baseImg = null, baseToken = 0, hasBase = false, ready = false;
  let overSrc = null, overW = 0, overH = 0, overOpacity = 1, overNearest = false;
  let atm = o.atmosphere ? cssRgb(o.atmosphere) : null, grat = o.graticule ? 1 : 0;
  let hi = null, hiCol = [1, 1, 1];
  let zoomTarget = view.zoom, anchor = null;
  let fly = null, inertia = false, vel = [0, 0], lastMoveT = 0, drag = null;
  let auto = { on: !!o.autoRotate, speed: 4 };
  let hoverPos = null, hoverDirty = false, hoverOn = false, lastView = '';

  const emit = (ev, arg) => (listeners[ev] || []).slice().forEach((cb) => cb(arg));
  const requestFrame = () => { if (!raf && !dead) raf = requestAnimationFrame(frame); };
  const invalidate = () => { dirty = true; requestFrame(); };

  // ---- GL resources (re-created after a context loss) -------------------------
  function setupGL() {
    lod = gl2 || !!gl.getExtension('EXT_shader_texture_lod');
    aniso = gl.getExtension('EXT_texture_filter_anisotropic');
    maxAniso = aniso ? Math.min(8, gl.getParameter(aniso.MAX_TEXTURE_MAX_ANISOTROPY_EXT)) : 1;
    const vs = (gl2 ? '#version 300 es\nin vec2 a;' : 'attribute vec2 a;') + 'void main(){gl_Position=vec4(a,0.,1.);}';
    const fs = (gl2
      ? '#version 300 es\nprecision highp float;\nout vec4 fragColor;\n#define TEXG textureGrad\n'
      : (lod ? '#extension GL_EXT_shader_texture_lod : enable\n' : '') + 'precision highp float;\n#define fragColor gl_FragColor\n' +
        (lod ? '#define TEXG texture2DGradEXT\n' : '#define TEXG(s,uv,dx,dy) texture2D(s,uv)\n')) + FRAG;
    const prog = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS) && !gl.isContextLost()) throw new Error('Globe shader: ' + gl.getShaderInfoLog(s));
      gl.attachShader(prog, s);
    }
    gl.bindAttribLocation(prog, 0, 'a');
    gl.linkProgram(prog); gl.useProgram(prog);
    U = {};
    for (const n of ['uRes', 'uF', 'uD', 'uRot', 'uBase', 'uOver', 'uHasBase', 'uOverOp', 'uGrat', 'uTime', 'uAtm', 'uHi', 'uHiCol']) U[n] = gl.getUniformLocation(prog, n);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);   // one full-screen triangle
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
    const blank = (unitIdx) => {
      const t = gl.createTexture();
      gl.activeTexture(gl.TEXTURE0 + unitIdx); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
      return t;
    };
    baseTex = blank(0); overTex = blank(1); overW = overH = 0;
    gl.uniform1i(U.uBase, 0); gl.uniform1i(U.uOver, 1);
    if (baseImg) uploadBase();
    if (overSrc) uploadOverlay();
  }

  function texParams(w, h, nearest) {
    const T = gl.TEXTURE_2D, pot = gl2 || (isPOT(w) && isPOT(h)), mips = pot && lod;
    gl.texParameteri(T, gl.TEXTURE_WRAP_S, pot ? gl.REPEAT : gl.CLAMP_TO_EDGE);
    gl.texParameteri(T, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(T, gl.TEXTURE_MIN_FILTER, mips ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
    gl.texParameteri(T, gl.TEXTURE_MAG_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
    if (aniso) gl.texParameterf(T, aniso.TEXTURE_MAX_ANISOTROPY_EXT, nearest ? 1 : maxAniso);
    if (mips) gl.generateMipmap(T);
  }

  function uploadBase() {
    const max = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    const w = baseImg.naturalWidth || baseImg.width, h = baseImg.naturalHeight || baseImg.height;
    let tw = Math.min(w, max), th = Math.min(h, max), src = baseImg;
    if (!gl2) { tw = 2 ** Math.floor(Math.log2(tw)); th = 2 ** Math.floor(Math.log2(th)); }   // WebGL1 needs power-of-two for mipmaps
    if (tw !== w || th !== h) {
      src = document.createElement('canvas'); src.width = tw; src.height = th;
      src.getContext('2d').drawImage(baseImg, 0, 0, tw, th);
    }
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, baseTex);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, src);
    texParams(tw, th, false);
  }

  function uploadOverlay() {
    const s = overSrc, T = gl.TEXTURE_2D;
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(T, overTex);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);    // premultiplied -> no dark fringes when filtered
    if (s.width === overW && s.height === overH) gl.texSubImage2D(T, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, s);
    else gl.texImage2D(T, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, s);
    overW = s.width; overH = s.height;
    texParams(overW, overH, overNearest);
  }

  // ---- camera ---------------------------------------------------------------
  function cam() {       // focal length (CSS px) and camera distance (planet radii)
    return { f: (Math.min(W, H) || 1) / 2 / Math.tan(FOV / 2), D: 1 + (D1 - 1) / view.zoom };
  }
  function basis() {     // camera axes in world space, column-major: east, north, towards the camera
    const la = view.lat * DEG, lo = view.lon * DEG;
    const cl = Math.cos(la), sl = Math.sin(la), co = Math.cos(lo), so = Math.sin(lo);
    return [co, 0, -so, -sl * so, cl, -sl * co, cl * so, sl, cl * co];
  }
  function pick(clientX, clientY) {      // exact ray-sphere pick -> { lat, lon } or null
    const r = canvas.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    const { f, D } = cam();
    let x = ((clientX - r.left) / r.width - 0.5) * W, y = (0.5 - (clientY - r.top) / r.height) * H, z = -f;
    const l = Math.hypot(x, y, z); x /= l; y /= l; z /= l;
    const b = D * z, disc = b * b - D * D + 1;
    if (disc < 0) return null;
    const t = -b - Math.sqrt(disc), px = x * t, py = y * t, pz = D + z * t, R = basis();
    const wx = R[0] * px + R[3] * py + R[6] * pz, wy = R[1] * px + R[4] * py + R[7] * pz, wz = R[2] * px + R[5] * py + R[8] * pz;
    return { lat: Math.asin(clamp(wy, -1, 1)) / DEG, lon: Math.atan2(wx, wz) / DEG };
  }
  function rotateBy(dx, dy) {            // pan by a screen-space delta so the surface at the centre follows the pointer
    const { f, D } = cam(), k = (D - 1) / f / DEG;
    view.lat = clampLat(view.lat + dy * k);
    view.lon = wrapLon(view.lon - dx * k / Math.max(Math.cos(view.lat * DEG), 0.25));
    invalidate();
  }

  // ---- drawing --------------------------------------------------------------
  function render(now = performance.now()) {
    dirty = false; lastDraw = now;
    if (dead || lost || !W || !H) return;
    const { f, D } = cam(), R = basis(), dpr = canvas.width / W;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(U.uRes, canvas.width, canvas.height);
    gl.uniform1f(U.uF, f * dpr); gl.uniform1f(U.uD, D);
    gl.uniformMatrix3fv(U.uRot, false, R);
    gl.uniform1f(U.uHasBase, hasBase ? 1 : 0);
    gl.uniform1f(U.uOverOp, overSrc ? overOpacity : 0);
    gl.uniform1f(U.uGrat, grat);
    gl.uniform1f(U.uTime, o.pulse ? (now / 1000) % 1000 : 0.6);
    gl.uniform4f(U.uAtm, ...(atm || [0, 0, 0]), atm ? 1 : 0);
    if (hi) gl.uniform4f(U.uHi, ...unit(hi.lat, hi.lon), Math.max(hi.radiusKm / o.planetRadiusKm, 1e-5));
    else gl.uniform4f(U.uHi, 0, 0, 1, -1);
    gl.uniform3f(U.uHiCol, ...hiCol);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    // DOM markers: project, hide the far side, nearer ones on top
    for (const m of markers.values()) {
      const [x, y, z] = m.p;
      const cz = R[6] * x + R[7] * y + R[8] * z;
      let vis = cz > 1 / D + 0.03;
      if (vis) {
        const s = f / (D - cz);
        const sx = W / 2 + (R[0] * x + R[1] * y + R[2] * z) * s, sy = H / 2 - (R[3] * x + R[4] * y + R[5] * z) * s;
        vis = sx > -60 && sy > -60 && sx < W + 60 && sy < H + 60;
        if (vis) {
          m.el.style.transform = `translate(${sx.toFixed(1)}px,${sy.toFixed(1)}px) translate(-50%,-50%)`;
          m.el.style.zIndex = String(Math.round(cz * 1000));
        }
      }
      if (vis !== m.shown) { m.shown = vis; m.el.style.display = vis ? '' : 'none'; }
    }

    const key = view.lat.toFixed(4) + ',' + view.lon.toFixed(4) + ',' + view.zoom.toFixed(4);
    if (key !== lastView) { lastView = key; emit('viewchange', getView()); }
  }

  function frame(now) {
    raf = 0;
    if (dead) return;
    const dt = lastT ? Math.min(50, now - lastT) : 16;
    lastT = now;
    let busy = false;

    if (fly) {                                              // eased camera flight
      fly.t = Math.min(1, fly.t + dt / fly.dur);
      const t = fly.t, e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      view.lat = clampLat(fly.from.lat + (fly.to.lat - fly.from.lat) * e);
      view.lon = wrapLon(fly.from.lon + fly.dLon * e);
      view.zoom = clamp(Math.exp(Math.log(fly.from.zoom) + (Math.log(fly.to.zoom) - Math.log(fly.from.zoom)) * e - fly.arc * Math.sin(Math.PI * t)), o.minZoom, o.maxZoom);
      zoomTarget = view.zoom; dirty = true;
      if (t >= 1) endFly(true); else busy = true;
    } else {
      if (auto.on && !drag) { view.lon = wrapLon(view.lon - auto.speed * dt / 1000); dirty = busy = true; }
      if (inertia) {                                        // coast after a drag
        const k = Math.exp(-dt / 280);
        rotateBy(vel[0] * dt, vel[1] * dt); vel[0] *= k; vel[1] *= k;
        if (Math.hypot(vel[0], vel[1]) < 0.01) inertia = false; else busy = true;
      }
      if (Math.abs(Math.log(zoomTarget / view.zoom)) > 1e-4) {   // smooth wheel zoom, anchored on the cursor
        const before = anchor && pick(anchor.x, anchor.y);
        view.zoom *= Math.pow(zoomTarget / view.zoom, 1 - Math.exp(-dt / 70));
        const after = before && pick(anchor.x, anchor.y);
        if (after) {
          view.lat = clampLat(view.lat + before.lat - after.lat);
          view.lon = wrapLon(view.lon + wrapLon(before.lon - after.lon));
        }
        dirty = busy = true;
      } else if (view.zoom !== zoomTarget) { view.zoom = zoomTarget; dirty = true; }
    }

    if (hi && o.pulse) { busy = true; if (now - lastDraw > 32) dirty = true; }   // pulsing ring at ~30 fps

    if (hoverDirty) {
      hoverDirty = false;
      const p = hoverPos && !drag ? pick(hoverPos.x, hoverPos.y) : null;
      if (p) emit('hover', { lat: p.lat, lon: p.lon, clientX: hoverPos.x, clientY: hoverPos.y });
      else if (hoverOn) emit('hover', null);
      hoverOn = !!p;
    }
    if (dirty) render(now);
    if (busy) requestFrame(); else lastT = 0;
  }

  function resize() {
    const w = root.clientWidth, h = root.clientHeight, dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cw = Math.max(1, Math.round(w * dpr)), ch = Math.max(1, Math.round(h * dpr));
    if (w === W && h === H && cw === canvas.width && ch === canvas.height) return;
    W = w; H = h; canvas.width = cw; canvas.height = ch;
    render();                                               // draw at once: resizing clears the canvas
  }

  // ---- interaction ------------------------------------------------------------
  function endFly(done) {
    if (!fly) return;
    const f = fly; fly = null; zoomTarget = view.zoom; f.resolve(done);
  }
  function interact() {                   // any user input cancels flights, coasting and auto-rotation
    endFly(false); inertia = false; auto.on = false;
  }
  function onDown(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    interact();
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (ptrs.size === 1) drag = { x0: e.clientX, y0: e.clientY, moved: false, marker: e.target.closest ? e.target.closest('.ag-marker') : null };
    else if (drag) drag.moved = true;
    vel = [0, 0]; zoomTarget = view.zoom;
  }
  function onMove(e) {
    const p = ptrs.get(e.pointerId);
    if (!p) {
      if (e.pointerType !== 'touch') { hoverPos = { x: e.clientX, y: e.clientY }; hoverDirty = true; requestFrame(); }
      return;
    }
    if (!drag) return;
    if (!drag.moved) {                   // a press only becomes a drag after 5 px, so clicks stay clicks
      if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) <= 5) return;
      drag.moved = true; root.style.cursor = 'grabbing';
      try { root.setPointerCapture(e.pointerId); } catch (_) { /* pointer already gone */ }
    }
    const dx = e.clientX - p.x, dy = e.clientY - p.y, now = performance.now();
    if (ptrs.size === 1) {
      rotateBy(dx, dy);
      const dtm = Math.max(1, now - lastMoveT);
      vel = dtm > 100 ? [0, 0] : [vel[0] * 0.4 + dx / dtm * 0.6, vel[1] * 0.4 + dy / dtm * 0.6];
      lastMoveT = now;
    } else if (ptrs.size === 2) {        // pinch: zoom by the change in finger distance, pan by half the motion
      let q = null;
      for (const [id, v] of ptrs) if (id !== e.pointerId) q = v;
      const d0 = Math.hypot(p.x - q.x, p.y - q.y), d1 = Math.hypot(e.clientX - q.x, e.clientY - q.y);
      if (d0 > 0) view.zoom = zoomTarget = clamp(view.zoom * d1 / d0, o.minZoom, o.maxZoom);
      rotateBy(dx / 2, dy / 2);
    }
    p.x = e.clientX; p.y = e.clientY;
  }
  function onUp(e) {
    if (!ptrs.delete(e.pointerId) || ptrs.size) return;
    const d = drag; drag = null; root.style.cursor = '';
    if (!d) return;
    if (!d.moved && e.type === 'pointerup') {
      const m = d.marker && markers.get(d.marker._agId);
      if (m) emit('markerclick', { id: m.data.id, marker: m.data });
      else if (!d.marker) {
        const p = pick(e.clientX, e.clientY);
        if (p) emit('click', { lat: p.lat, lon: p.lon, clientX: e.clientX, clientY: e.clientY });
      }
    } else if (d.moved && performance.now() - lastMoveT < 60 && Math.hypot(vel[0], vel[1]) > 0.05) {
      inertia = true; requestFrame();
    }
  }
  function onLeave() { hoverPos = null; hoverDirty = true; requestFrame(); }
  function onWheel(e) {
    e.preventDefault(); interact();
    const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1);
    zoomTarget = clamp(zoomTarget * Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0015)), o.minZoom, o.maxZoom);
    anchor = { x: e.clientX, y: e.clientY };
    requestFrame();
  }
  function onDbl(e) {
    if (e.target.closest && e.target.closest('.ag-marker')) return;
    const p = pick(e.clientX, e.clientY);
    if (p) flyTo({ lat: p.lat, lon: p.lon, zoom: view.zoom * 2, duration: 450 });
  }
  function onLost(e) { e.preventDefault(); lost = true; }
  function onRestored() { lost = false; setupGL(); invalidate(); }

  root.addEventListener('pointerdown', onDown);
  root.addEventListener('pointermove', onMove);
  root.addEventListener('pointerup', onUp);
  root.addEventListener('pointercancel', onUp);
  root.addEventListener('pointerleave', onLeave);
  root.addEventListener('wheel', onWheel, { passive: false });
  root.addEventListener('dblclick', onDbl);
  canvas.addEventListener('webglcontextlost', onLost);
  canvas.addEventListener('webglcontextrestored', onRestored);
  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
  if (ro) ro.observe(root); else window.addEventListener('resize', resize);

  // ---- public API -------------------------------------------------------------
  function getView() { return { lat: view.lat, lon: view.lon, zoom: view.zoom }; }

  function setView(v = {}) {
    endFly(false); inertia = false;
    if (v.lat != null) view.lat = clampLat(v.lat);
    if (v.lon != null) view.lon = wrapLon(v.lon);
    if (v.zoom != null) view.zoom = clamp(v.zoom, o.minZoom, o.maxZoom);
    zoomTarget = view.zoom;
    invalidate();
  }

  function flyTo(t = {}) {
    endFly(false); inertia = false;
    const from = getView();
    const to = {
      lat: clampLat(t.lat != null ? t.lat : view.lat), lon: wrapLon(t.lon != null ? t.lon : view.lon),
      zoom: clamp(t.zoom != null ? t.zoom : view.zoom, o.minZoom, o.maxZoom),
    };
    const dur = t.duration != null ? t.duration : 1400;
    if (!(dur > 0)) { setView(to); return Promise.resolve(true); }
    // long hops between close-up views pull back far enough to see both ends
    const a = unit(from.lat, from.lon), b = unit(to.lat, to.lon);
    const ang = Math.acos(clamp(a[0] * b[0] + a[1] * b[1] + a[2] * b[2], -1, 1)) / DEG;
    const zLow = Math.min(from.zoom, to.zoom), zFit = Math.max(o.minZoom, 1, 70 / Math.max(ang, 1e-3));
    const arc = Math.max(0, Math.log(zLow / zFit)) * 0.9;
    return new Promise((resolve) => {
      fly = { from, to, dLon: wrapLon(to.lon - from.lon), dur, t: 0, arc, resolve };
      requestFrame();
    });
  }

  function setOverlay(src) {
    if (src && !(typeof HTMLCanvasElement !== 'undefined' && src instanceof HTMLCanvasElement) && !(src instanceof ImageData)) {
      const d = src.data instanceof Uint8ClampedArray ? src.data : new Uint8ClampedArray(src.data.buffer, src.data.byteOffset, src.data.length);
      src = new ImageData(d, src.width, src.height);        // no copy; uploaded like any image source
    }
    overSrc = src || null;
    if (overSrc && !lost) uploadOverlay();
    invalidate();
  }

  function setBase(url) {
    const token = ++baseToken;
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous'; img.decoding = 'async';
      img.onload = () => {
        if (dead || token !== baseToken) return resolve(false);
        baseImg = img; hasBase = true;
        if (!lost) uploadBase();
        if (!W) resize();
        render();
        if (!ready) { ready = true; emit('ready'); }
        resolve(true);
      };
      img.onerror = () => { emit('error', { message: 'Could not load ' + url }); resolve(false); };
      img.src = url;
    });
  }

  function setMarkers(list) {
    const seen = new Set();
    for (const d of (list || []).slice(0, MAX_MARKERS)) {
      seen.add(d.id);
      let m = markers.get(d.id);
      if (!m) {
        m = { el: document.createElement('div'), html: null, shown: null };
        m.el._agId = d.id; m.el.style.display = 'none'; m.shown = false;
        layer.appendChild(m.el); markers.set(d.id, m);
      }
      const cls = 'ag-marker' + (d.className ? ' ' + d.className : '');
      if (m.el.className !== cls) m.el.className = cls;
      if (m.html !== (d.html || '')) { m.html = d.html || ''; m.el.innerHTML = m.html; }
      if (m.el.title !== (d.title || '')) m.el.title = d.title || '';
      m.p = unit(d.lat, d.lon); m.data = d;
    }
    for (const [id, m] of markers) if (!seen.has(id)) { m.el.remove(); markers.delete(id); }
    invalidate();
  }

  const api = {
    setOverlay,
    setOverlayOpacity(a) { overOpacity = clamp(+a, 0, 1); invalidate(); },
    setOverlayFilter(mode) {
      overNearest = mode === 'nearest';
      if (overSrc && !lost) { gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, overTex); texParams(overW, overH, overNearest); }
      invalidate();
    },
    setBase, setView, getView, flyTo, setMarkers,
    setHighlight(h) {                    // { lat, lon, radiusKm, color? } | null
      hi = h ? { lat: h.lat, lon: h.lon, radiusKm: h.radiusKm || 100 } : null;
      hiCol = h && h.color ? cssRgb(h.color) : [1, 1, 1];
      invalidate();
    },
    setGraticule(on) { grat = on ? 1 : 0; invalidate(); },
    setAtmosphere(color) { atm = color ? cssRgb(color) : null; invalidate(); },
    setAutoRotate(on, degPerSec = 4) { auto = { on: !!on, speed: degPerSec }; if (on) requestFrame(); },
    on(ev, cb) {
      (listeners[ev] = listeners[ev] || []).push(cb);
      if (ev === 'ready' && ready) Promise.resolve().then(() => { if (!dead && listeners.ready.includes(cb)) cb(); });
      return () => { listeners[ev] = (listeners[ev] || []).filter((f) => f !== cb); };
    },
    pick,                                // (clientX, clientY) -> { lat, lon } | null
    resize,
    destroy() {
      if (dead) return;
      endFly(false); dead = true;
      cancelAnimationFrame(raf);
      if (ro) ro.disconnect(); else window.removeEventListener('resize', resize);
      const ext = gl.getExtension('WEBGL_lose_context');
      if (ext) ext.loseContext();
      root.remove(); markers.clear();
      for (const k in listeners) delete listeners[k];
    },
    canvas, element: root,
  };

  setupGL();
  resize();
  if (o.baseUrl) setBase(o.baseUrl);
  invalidate();
  return api;
}
