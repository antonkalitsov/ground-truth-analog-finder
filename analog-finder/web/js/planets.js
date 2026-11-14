// planets.js — the two lit spheres of the destination stage. No 3D library.
//
// Each planet is ONE full-canvas triangle; the fragment shader ray-casts a sphere, samples an
// equirectangular map (Kaguya TC mosaic for the Moon, MOLA + TES for Mars), bends the normal with
// the map's own brightness gradient (a cheap bump map) and lights it from one direction so the
// terminator gives volume. Triangle count for both planets together: 2. Pixel ratio is capped at 2.
// Frames are drawn only while the stage is visible and the tab is in front.

const VERT = 'attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }';
const FRAG = `
precision highp float;
uniform vec2 uRes; uniform float uSpin, uTilt, uGain, uBump; uniform vec3 uLight; uniform sampler2D uMap;
const float PI = 3.14159265359;
vec2 uvOf(vec3 b) { return vec2(atan(b.x, b.z) / (2.0 * PI) + 0.5, 0.5 - asin(clamp(b.y, -1.0, 1.0)) / PI); }
float lum(vec2 uv) { return dot(texture2D(uMap, uv).rgb, vec3(0.3, 0.5, 0.2)); }
void main() {
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / (0.5 * min(uRes.x, uRes.y)) * 1.03;
  float r2 = dot(p, p);
  float aa = 2.0 / min(uRes.x, uRes.y);
  float alpha = 1.0 - smoothstep(1.0 - 2.0 * aa, 1.0, sqrt(r2));
  if (alpha <= 0.0) { gl_FragColor = vec4(0.0); return; }
  vec3 n = vec3(p, sqrt(max(1.0 - r2, 0.0)));
  // view space -> body space: undo the axial tilt (about z), then the spin (about y)
  float ct = cos(uTilt), st = sin(uTilt), cs = cos(uSpin), ss = sin(uSpin);
  mat3 tilt = mat3(ct, -st, 0.0, st, ct, 0.0, 0.0, 0.0, 1.0);
  mat3 spin = mat3(cs, 0.0, ss, 0.0, 1.0, 0.0, -ss, 0.0, cs);
  mat3 toBody = spin * tilt;
  vec3 b = toBody * n, l = toBody * normalize(uLight);
  vec2 uv = uvOf(b);
  vec3 col = texture2D(uMap, uv).rgb;
  // bump: brightness gradient along east and north, fading out at the poles where the map is stretched
  vec3 east = normalize(vec3(b.z, 0.0, -b.x) + 1e-5), north = cross(b, east);
  float e = 1.5 / 2048.0;
  float gx = lum(uv + vec2(e, 0.0)) - lum(uv - vec2(e, 0.0));
  float gy = lum(uv - vec2(0.0, e)) - lum(uv + vec2(0.0, e));
  vec3 nb = normalize(b - uBump * (1.0 - b.y * b.y) * (gx * east + gy * north));
  float d = dot(nb, l);
  float lit = smoothstep(-0.08, 0.85, d);            // soft terminator
  lit = 0.03 + lit * (0.62 + 0.38 * max(dot(b, l), 0.0));
  gl_FragColor = vec4(col * lit * uGain, 1.0) * alpha;  // premultiplied alpha
}`;

export function createPlanet(canvas, { src, tilt = 0, speed = 0.05, light = [-0.62, 0.34, 0.7], bump = 6, spin0 = 0, still = false, gain: base = 1 } = {}) {
  const gl = canvas.getContext('webgl', { alpha: true, antialias: false, depth: false, stencil: false, premultipliedAlpha: true, powerPreference: 'low-power' });
  if (!gl) return null;                                 // caller falls back to a flat CSS disc
  const sh = (type, s) => { const o = gl.createShader(type); gl.shaderSource(o, s); gl.compileShader(o); return o; };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
  gl.bindAttribLocation(prog, 0, 'a'); gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const U = {}; for (const n of ['uRes', 'uSpin', 'uTilt', 'uGain', 'uBump', 'uLight', 'uMap']) U[n] = gl.getUniformLocation(prog, n);
  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([40, 40, 40, 255]));
  let ready = false, raf = 0, last = 0, spin = spin0, gain = base, gainTo = base, rate = 1, rateTo = 1, running = false, dead = false;

  const img = new Image();
  img.onload = () => {
    if (dead) return;
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
    // No mipmaps: the map is drawn close to 1:1 and mip selection would show a seam at the date line.
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    ready = true; canvas.classList.add('ready'); draw();
  };
  img.src = src;

  function size() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(2, Math.round(canvas.clientWidth * dpr)), h = Math.max(2, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  }
  function draw() {
    if (dead) return;
    size();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(U.uRes, canvas.width, canvas.height);
    gl.uniform1f(U.uSpin, spin); gl.uniform1f(U.uTilt, tilt); gl.uniform1f(U.uGain, gain); gl.uniform1f(U.uBump, bump);
    gl.uniform3fv(U.uLight, light); gl.uniform1i(U.uMap, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function frame(t) {
    raf = 0; if (!running || dead) return;
    const dt = Math.min(0.05, (t - (last || t)) / 1000); last = t;
    const k = 1 - Math.exp(-dt * 5);                    // weighted ease toward the hover state
    gain += (gainTo - gain) * k; rate += (rateTo - rate) * k;
    if (!still) spin += speed * rate * dt;
    if (ready && !document.hidden) draw();
    if (still && Math.abs(gain - gainTo) < 0.002) { running = false; return; }   // reduced motion: stop once settled
    raf = requestAnimationFrame(frame);
  }
  const kick = () => { if (!raf && !dead) { running = true; last = 0; raf = requestAnimationFrame(frame); } };
  const ro = new ResizeObserver(() => { if (ready) draw(); });
  ro.observe(canvas);

  return {
    start: kick,
    stop() { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; },
    hover(on) { gainTo = on ? base * 1.14 : base; rateTo = on ? 1.7 : 1; kick(); },
    destroy() { dead = true; this.stop(); ro.disconnect(); const x = gl.getExtension('WEBGL_lose_context'); if (x) x.loseContext(); },
  };
}
