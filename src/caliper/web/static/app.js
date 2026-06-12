import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

// ---------------------------------------------------------------- DOM
const $ = (id) => document.getElementById(id);
const intentEl = $('intent'), refineEl = $('refine'), statusEl = $('status');
const runBtn = $('runBtn'), refineBtn = $('refineBtn'), useLLM = $('useLLM');
const reportEl = $('report'), specEl = $('spec'), downloadEl = $('download');
const spaceBtn = $('spaceBtn'), spaceStatus = $('spaceStatus'), axesEl = $('axes');
const authorMode = $('authorMode'), scriptbox = $('scriptbox'), scriptpre = $('scriptpre');
// fit-to-reference (M3 / CALI-10)
const refFile = $('refFile'), fitBtn = $('fitBtn'), fitClear = $('fitClear');
const fitNoOverlap = $('fitNoOverlap'), fitHint = $('fitHint');
const fitClassEl = $('fitClass'), clearRow = $('clearRow');
const gizmoEl = $('gizmo'), gMove = $('gMove'), gRot = $('gRot'), gClear = $('gClear');

let currentRunId = null;

// SpaceMouse state — declared up here so the render loop (animate) can read `smOn` from frame 1
// without hitting the temporal dead zone. Driver/wiring is in the WebHID section below.
const SM = { tx: 0, ty: 0, tz: 0, rx: 0, ry: 0, rz: 0 };
const SM_GAIN_ROT = 0.00018, SM_GAIN_PAN = 0.02, SM_GAIN_DOLLY = 0.0016, SM_DEAD = 0.03, SM_SCALE = 350;
let smOn = false;

// ---------------------------------------------------------------- API
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

function busy(msg) { statusEl.textContent = msg; statusEl.className = 'status busy'; }
function done(msg) { statusEl.textContent = msg; statusEl.className = 'status'; }
function fail(msg) { statusEl.textContent = msg; statusEl.className = 'status bad'; }

async function doRun() {
  const intent = intentEl.value.trim();
  if (!intent) return;
  runBtn.disabled = true;
  try {
    if (authorMode.checked) {
      // CALI-16/17: the LLM authors + iterates the CadQuery itself (any part). Slow (LLM + builds).
      busy('authoring + iterating… (the LLM writes the CAD; can take ~30–60s)');
      const data = await postJSON('/api/gen', { intent, max_rounds: 4 });
      applyResult(data);
      const notes = [data.heals ? `${data.heals} build-heal(s)` : '',
                     data.revisions ? `${data.revisions} revision(s)` : ''].filter(Boolean).join(', ');
      done(`${data.status} · ${data.rounds} round(s)${notes ? ' (' + notes + ')' : ''}`);
    } else {
      busy('building…');
      const data = await postJSON('/api/run', { intent, no_llm: !useLLM.checked, max_iter: 4 });
      applyResult(data);
      done(`${data.status} · ${data.iterations} iter · ${data.source}`);
    }
  } catch (e) { fail(e.message); }
  finally { runBtn.disabled = false; }
}

async function doRefine() {
  if (!currentRunId) return;
  const instruction = refineEl.value.trim();
  if (!instruction) return;
  refineBtn.disabled = true; busy('refining…');
  try {
    const data = await postJSON('/api/refine', { run_id: currentRunId, instruction, no_llm: !useLLM.checked });
    applyResult(data);
    refineEl.value = '';
    done(`${data.status} · ${data.source}`);
  } catch (e) { fail(e.message); }
  finally { refineBtn.disabled = false; }
}

function applyResult(data) {
  currentRunId = data.run_id;
  refineBtn.disabled = false;
  specEl.textContent = data.spec_yaml || '';
  // authored parts carry their CadQuery source (part.py) — show it as the editable source of truth
  if (data.script) { scriptpre.textContent = data.script; scriptbox.style.display = ''; }
  else { scriptbox.style.display = 'none'; }
  renderReport(data);
  if (data.stl_url) {
    loadSTL(data.stl_url + '?t=' + Date.now());
    downloadEl.href = data.stl_url; downloadEl.style.display = '';
  } else {
    downloadEl.style.display = 'none';
  }
  // render any imported references at their pose (or clear a stale one on a plain build/refine)
  renderReferences(data.references);
  fitBtn.disabled = !(currentRunId && refMesh);
  updateFitHint();
  markActiveRun();
  refreshRuns();  // keep the Recent list current
}

// ---------------------------------------------------------------- Recent parts (CALI-15)
const recentEl = $('recent'), recentCountEl = $('recentCount');

async function refreshRuns() {
  try {
    const { runs } = await (await fetch('/api/runs', { cache: 'no-store' })).json();
    recentCountEl.textContent = runs.length ? `(${runs.length})` : '';
    if (!runs.length) { recentEl.innerHTML = '<div class="empty">no parts yet — build one above</div>'; return; }
    recentEl.innerHTML = runs.map((r) => {
      const dot = r.status === 'passed' ? 'pass' : (r.build_ok === false ? 'fail' : '');
      const when = r.created ? r.created.replace('T', ' ').slice(5) : '';
      return `<div class="item" data-run="${esc(r.run_id)}" title="${esc(r.label || '')}">` +
        `<span class="dot ${dot}"></span>` +
        `<span class="lbl">${esc(r.label || r.part || r.run_id)}</span>` +
        `<span class="rid">${esc(r.run_id.replace('run_', '#'))} ${when}</span></div>`;
    }).join('');
    recentEl.querySelectorAll('.item').forEach((el) =>
      el.addEventListener('click', () => loadRun(el.dataset.run)));
    markActiveRun();
  } catch (e) { /* list is best-effort */ }
}

function markActiveRun() {
  recentEl.querySelectorAll('.item').forEach((el) =>
    el.classList.toggle('active', el.dataset.run === currentRunId));
}

async function loadRun(runId) {
  busy('loading ' + runId.replace('run_', '#') + '…');
  try {
    const data = await (await fetch('/api/runs/' + runId, { cache: 'no-store' })).json();
    if (data.detail) throw new Error(data.detail);
    applyResult(data);
    done('loaded ' + runId.replace('run_', '#') + ' (refine to fork a new part)');
  } catch (e) { fail('load failed: ' + e.message); }
}

function renderReport(data) {
  const rep = data.report || { results: [], all_pass: false };
  const bits = [];
  bits.push(`<div class="verdict ${rep.all_pass ? 'pass' : 'fail'}">${rep.all_pass ? 'ALL PASS ✓' : 'FAILURES'}</div>`);
  if (data.changes && data.changes.length)
    bits.push(`<div class="changes">changes: ${data.changes.map(esc).join(' · ')}</div>`);
  if (data.questions && data.questions.length)
    bits.push(`<div class="questions">⚠ ${data.questions.map(esc).join(' ')}</div>`);
  for (const r of rep.results) {
    const margin = r.margin === null || r.margin === undefined ? '' : `margin ${r.margin > 0 ? '+' : ''}${r.margin}`;
    const actual = (r.actual === null || r.actual === undefined) ? '' : `= ${fmt(r.actual)}`;
    bits.push(`<div class="assert"><span class="sym ${r.status}">${r.symbol}</span>` +
      `<span class="id">${esc(r.id)} <span class="num">${actual}</span></span>` +
      `<span class="margin">${margin}</span>` +
      `<span class="expr">${esc(r.expr)}</span></div>`);
  }
  if (!data.build_ok) bits.push(`<div class="questions">build failed — see server log</div>`);
  reportEl.innerHTML = bits.join('');
}

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const fmt = (v) => Array.isArray(v) ? '[' + v.map(fmt).join(', ') + ']' : v;

// ---------------------------------------------------------------- three.js
const viewer = $('viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
viewer.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0f13);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
camera.position.set(120, 90, 160);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x222a33, 1.1));
const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(1, 1.4, 1); scene.add(key);

const modelGroup = new THREE.Group();
scene.add(modelGroup);
// grid lives in the model group so SpaceMouse rotation (which spins the group) carries the plane
// with the part — keeps pan/zoom (camera) and rotation (group) visually consistent.
const grid = new THREE.GridHelper(400, 20, 0x283039, 0x1b2127);
modelGroup.add(grid);
let partMesh = null;      // the generated part (rendered in its TRUE build frame, corner at origin)
let refMesh = null;       // the imported reference, posable with the gizmo (null when none)
let refBytes = null;      // the reference STL bytes — base64'd and sent on Fit

// Both part and reference live in modelGroup at their real coordinates (no recentring), so the pose
// you set in the viewer is exactly the pose the backend measures — what you see is what's measured.
const partMat = () => new THREE.MeshStandardMaterial({ color: 0x4ea1ff, metalness: 0.1, roughness: 0.55 });
const refMat = () => new THREE.MeshStandardMaterial({ color: 0xffb454, transparent: true, opacity: 0.45, roughness: 0.85 });

// gizmo to place the reference in the part's frame (M3). Added to the scene (not modelGroup) but it
// tracks the reference's world matrix; reading refMesh.position gives the pose in the part frame.
const gizmo = new TransformControls(camera, renderer.domElement);
gizmo.setSpace('local');
gizmo.setSize(0.8);
gizmo.addEventListener('dragging-changed', (e) => { controls.enabled = !e.value; });
gizmo.addEventListener('objectChange', updateFitHint);
scene.add(gizmo);

const stlLoader = new STLLoader();

async function loadSTL(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  setPart(stlLoader.parse(buf));
}

function setPart(geom) {
  geom.computeVertexNormals();
  if (partMesh) modelGroup.remove(partMesh);
  partMesh = new THREE.Mesh(geom, partMat());
  modelGroup.add(partMesh);
  modelGroup.rotation.set(0, 0, 0);
  frameScene();
}

function frameScene() {
  const box = new THREE.Box3();
  if (partMesh) box.expandByObject(partMesh);
  if (refMesh) box.expandByObject(refMesh);
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2 || 50;
  controls.target.copy(c);
  const d = r * 2.4;
  camera.position.set(c.x + d * 0.6, c.y + d * 0.5, c.z + d * 0.9);
  camera.near = r / 100; camera.far = r * 100; camera.updateProjectionMatrix();
  controls.update();
}

// ---------------------------------------------------------------- reference + fit (M3)
function clearReference() {
  gizmo.detach();
  if (refMesh) { modelGroup.remove(refMesh); refMesh = null; }
  refBytes = null;
  if (refFile) refFile.value = '';
  gizmoEl.style.display = 'none';
  fitBtn.disabled = true;
  updateFitHint();
}

function addReference(geom, bytes, pose) {
  if (refMesh) modelGroup.remove(refMesh);
  geom.computeVertexNormals();
  refMesh = new THREE.Mesh(geom, refMat());
  if (pose) {
    refMesh.position.fromArray(pose.position || [0, 0, 0]);
    const r = (pose.rotation || [0, 0, 0]).map(THREE.MathUtils.degToRad);
    refMesh.rotation.set(r[0], r[1], r[2], 'XYZ');
  }
  modelGroup.add(refMesh);
  if (bytes) refBytes = bytes;
  gizmo.attach(refMesh);
  setGizmoMode('translate');
  gizmoEl.style.display = '';
  fitBtn.disabled = !currentRunId;
  frameScene();
  updateFitHint();
}

async function onRefFile(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const bytes = await file.arrayBuffer();
  let geom;
  try { geom = stlLoader.parse(bytes); }
  catch (e) { window.showErr('could not parse STL: ' + e.message); return; }
  addReference(geom, bytes, null);
  done('reference added — drag/rotate it into place, then Fit');
}

function refPose() {
  const p = refMesh.position, e = refMesh.rotation;
  return {
    position: [p.x, p.y, p.z].map((v) => +v.toFixed(4)),
    rotation: [e.x, e.y, e.z].map((v) => +THREE.MathUtils.radToDeg(v).toFixed(3)),
  };
}

function updateFitHint() {
  if (!refMesh) { fitHint.textContent = 'add an STL, place it, then Fit'; return; }
  if (!currentRunId) { fitHint.textContent = 'build or load a part first'; return; }
  fitHint.textContent = `ref @ [${refPose().position.join(', ')}] mm`;
}

function setGizmoMode(mode) {
  gizmo.setMode(mode);
  gMove.classList.toggle('gactive', mode === 'translate');
  gRot.classList.toggle('gactive', mode === 'rotate');
}

function bytesToB64(buf) {
  let bin = ''; const arr = new Uint8Array(buf);
  const chunk = 0x8000;
  for (let i = 0; i < arr.length; i += chunk) bin += String.fromCharCode.apply(null, arr.subarray(i, i + chunk));
  return btoa(bin);
}

async function doFit() {
  if (!currentRunId || !refMesh || !refBytes) return;
  fitBtn.disabled = true; busy('fitting…');
  try {
    const pose = refPose();
    const fitClass = fitClassEl.value || null;   // a fit class (slip/press/…) overrides clearance
    const data = await postJSON('/api/fit', {
      run_id: currentRunId, reference_b64: bytesToB64(refBytes), reference_id: 'reference',
      position: pose.position, rotation: pose.rotation,
      fit: fitClass,
      no_overlap: fitClass ? false : fitNoOverlap.checked,
      min_clearance: fitClass || fitClear.value === '' ? null : parseFloat(fitClear.value),
    });
    applyResult(data);
    done(`${data.status} · fit · ${data.iterations} iter`);
  } catch (e) { fail(e.message); }
  finally { fitBtn.disabled = !(currentRunId && refMesh); }
}

// render server-returned references (after a fit, or when loading a fit run) at their stored pose
async function renderReferences(refs) {
  const r = refs && refs[0];   // v1: a single reference
  if (!r || !r.stl_url) { clearReference(); return; }
  try {
    const bytes = await (await fetch(r.stl_url + '?t=' + Date.now())).arrayBuffer();
    addReference(stlLoader.parse(bytes), bytes, { position: r.position, rotation: r.rotation });
  } catch (e) { /* best-effort render */ }
}

function resize() {
  const w = viewer.clientWidth, h = viewer.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewer);
resize();

function animate() {
  requestAnimationFrame(animate);
  applySpaceMouse();
  controls.update();
  renderer.render(scene, camera);
}
animate();

// ---------------------------------------------------------------- SpaceMouse (WebHID)
// 3Dconnexion devices report 6DOF as signed int16 axes. We drive the model's rotation and the
// camera's pan/dolly. Axis mapping & gains are intentionally tweakable (hardware varies).
// (SM state + smOn are declared near the top so the render loop can read them from frame 1.)
function norm(v) { const n = Math.max(-1, Math.min(1, v / SM_SCALE)); return Math.abs(n) < SM_DEAD ? 0 : n; }

let smReports = 0;

function onInputReport(e) {
  smReports++;
  const d = e.data; // DataView
  const a = (i) => d.byteLength > i + 1 ? d.getInt16(i, true) : 0;
  if (e.reportId === 1) {            // translation (some devices pack rotation at bytes 6..11)
    SM.tx = a(0); SM.ty = a(2); SM.tz = a(4);
    if (d.byteLength >= 12) { SM.rx = a(6); SM.ry = a(8); SM.rz = a(10); }
  } else if (e.reportId === 2) {     // rotation
    SM.rx = a(0); SM.ry = a(2); SM.rz = a(4);
  }
  // live diagnostics: report id, byte length, parsed axes, raw bytes (helps confirm data + calibrate)
  axesEl.style.display = 'block';
  const raw = []; for (let i = 0; i < d.byteLength; i++) raw.push(d.getUint8(i).toString(16).padStart(2, '0'));
  axesEl.textContent =
    `rpt ${e.reportId} · ${d.byteLength}B · #${smReports}\n` +
    `T ${pad(SM.tx)} ${pad(SM.ty)} ${pad(SM.tz)}\nR ${pad(SM.rx)} ${pad(SM.ry)} ${pad(SM.rz)}\n${raw.join(' ')}`;
  spaceStatus.textContent = `live · ${smReports} reports`;
}
const pad = (n) => String(n).padStart(6);

function applySpaceMouse() {
  if (!smOn) return;
  // rotation → spin the model (independent of mouse-orbit)
  modelGroup.rotation.x += norm(SM.rx) * SM_GAIN_ROT * SM_SCALE;
  modelGroup.rotation.y += norm(SM.rz) * SM_GAIN_ROT * SM_SCALE;   // twist → yaw
  modelGroup.rotation.z += norm(SM.ry) * SM_GAIN_ROT * SM_SCALE;
  // translation → pan (x, vertical) + dolly (forward/back)
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
  const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
  const pan = new THREE.Vector3()
    .addScaledVector(right, -norm(SM.tx) * SM_GAIN_PAN * SM_SCALE)
    .addScaledVector(up, norm(SM.tz) * SM_GAIN_PAN * SM_SCALE);
  camera.position.add(pan); controls.target.add(pan);
  const dir = camera.position.clone().sub(controls.target);
  camera.position.copy(controls.target).add(dir.multiplyScalar(1 - norm(SM.ty) * SM_GAIN_DOLLY * SM_SCALE));
}

function attachDevice(dev) {
  dev.addEventListener('inputreport', onInputReport);
  smOn = true;
  smReports = 0;
  const vid = dev.vendorId.toString(16).padStart(4, '0'), pid = dev.productId.toString(16).padStart(4, '0');
  spaceStatus.textContent = `${dev.productName || 'device'} (${vid}:${pid}) opened — move the cap…`;
  spaceStatus.className = 'space-status on';
  spaceBtn.textContent = '🖱️ SpaceMouse on';
  // watchdog: opened but silent almost always means the OS driver is holding the device
  setTimeout(() => {
    if (smReports === 0)
      window.showErr('SpaceMouse opened but sent no data. On macOS the 3Dconnexion driver (3DxWare) ' +
        'usually holds the device — quit it (menu-bar icon → Quit 3DxWare, or Activity Monitor → quit ' +
        '"3DconnexionHelper") and click Connect again. Otherwise wiggle/twist the cap.');
  }, 2500);
}

async function connectSpaceMouse() {
  if (!('hid' in navigator)) { window.showErr('WebHID unsupported — use Chrome or Edge (not Safari).'); return; }
  try {
    // multi-axis controller usage (0x01/0x08) catches 3D mice regardless of vendor; plus known vendors
    const filters = [{ usagePage: 0x01, usage: 0x08 }, { vendorId: 0x256f }, { vendorId: 0x046d }];
    const devices = await navigator.hid.requestDevice({ filters });
    if (!devices.length) {
      spaceStatus.textContent = 'no device chosen';
      window.showErr('No device picked. If your SpaceMouse was not listed in the chooser, it may be ' +
        'held by the 3Dconnexion driver — quit 3DxWare and retry. (Run the console snippet to inspect HID.)');
      return;
    }
    const dev = devices[0];
    if (!dev.opened) await dev.open();
    attachDevice(dev);
  } catch (e) {
    const driverHint = /open/i.test(e.message)
      ? ' — the 3Dconnexion driver (3DxWare) is holding the device exclusively. Quit it (menu-bar ' +
        'icon → Quit, or Activity Monitor → quit "3DconnexionHelper") and click Connect again. ' +
        'WebHID reads the raw device, so it can\'t share with the driver (or Fusion) at the same time.'
      : '';
    window.showErr('SpaceMouse connect failed: ' + e.message + driverHint);
  }
}

// --- Driver / NL-Proxy mode (CALI-14, phase 1: connect + introspect) -----------------------------
// Coexists with 3DxWare/Fusion (no quitting). Loads 3Dconnexion's own proxy lib, which speaks the
// WAMP/WSS + navlib protocol. The exact API varies by driver version, so phase 1 connects + reports
// the surface/telemetry; phase 2 wires the navlib camera callbacks from what we learn here.
const NLPROXY_LIB = 'https://127.51.68.120:8181/3dconnexion/3dconnexion.js';

function loadScript(src) {
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.onload = res; s.onerror = () => rej(new Error('script load failed'));
    document.head.appendChild(s);
  });
}

async function connectViaDriver() {
  spaceStatus.textContent = 'loading 3Dconnexion proxy lib…';
  try {
    await loadScript(NLPROXY_LIB);
  } catch (e) {
    window.showErr('Could not load the NL-Proxy lib from ' + NLPROXY_LIB + '. Check: (1) 3DxWare is ' +
      'running; (2) open ' + NLPROXY_LIB + ' in a tab once to accept the driver certificate, then ' +
      'retry. (This path coexists with Fusion — no need to quit the driver.)');
    return;
  }
  if (typeof window._3Dconnexion === 'undefined') {
    window.showErr('proxy lib loaded but window._3Dconnexion is undefined — unexpected driver version.');
    return;
  }
  try {
    // introspect: report the API surface so we can finish phase 2 (navlib camera) for this driver.
    const sm = new window._3Dconnexion(document.getElementById('viewer'));
    window.__caliperSM = sm;
    const keys = []; for (const k in sm) keys.push(k);
    spaceStatus.textContent = '_3Dconnexion ready · methods: ' + keys.slice(0, 16).join(',');
    axesEl.style.display = 'block';
    axesEl.textContent = 'NL-Proxy API:\n' + keys.join('\n');
    if (typeof sm.onconnect !== 'undefined') {
      sm.onconnect = () => { spaceStatus.textContent = 'NL-Proxy connected ✓'; spaceStatus.className = 'space-status on'; };
    }
    if (typeof sm.connect === 'function') sm.connect();
    else window.showErr('phase 1: _3Dconnexion has no connect(); methods are shown top-right — send me that list and I\'ll wire phase 2.');
  } catch (e) {
    window.showErr('NL-Proxy init error: ' + e.message + ' — send me this + the method list and I\'ll finish it.');
  }
}

function onConnectClick() {
  const mode = document.getElementById('smMode').value;
  if (mode === 'driver') connectViaDriver();
  else connectSpaceMouse();
}

// auto-reattach a device we were already granted, so a reload doesn't need re-picking
if ('hid' in navigator) {
  navigator.hid.getDevices().then((ds) => {
    const dev = ds.find((d) => d.collections.some((c) => c.usagePage === 0x01 && c.usage === 0x08))
      || ds.find((d) => [0x256f, 0x046d].includes(d.vendorId));
    if (dev) dev.open().then(() => attachDevice(dev)).catch(() => {});
  });
}

// ---------------------------------------------------------------- wire up
runBtn.addEventListener('click', doRun);
authorMode.addEventListener('change', () => {
  runBtn.textContent = authorMode.checked ? 'Author ▶' : 'Build it ▶';
  if (authorMode.checked) useLLM.checked = true;  // authoring drafts the spec with Claude too
});
refineBtn.addEventListener('click', doRefine);
refineEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') doRefine(); });
intentEl.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) doRun(); });
spaceBtn.addEventListener('click', onConnectClick);

// fit-to-reference wiring (M3)
refFile.addEventListener('change', onRefFile);
fitBtn.addEventListener('click', doFit);
gMove.addEventListener('click', () => setGizmoMode('translate'));
gRot.addEventListener('click', () => setGizmoMode('rotate'));
gClear.addEventListener('click', clearReference);
fitClassEl.addEventListener('change', () => {
  clearRow.style.display = fitClassEl.value ? 'none' : '';  // a fit class supersedes manual clearance
});
addEventListener('keydown', (e) => {
  if (!refMesh || /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === 'w' || e.key === 'W') setGizmoMode('translate');
  else if (e.key === 'e' || e.key === 'E' || e.key === 'r' || e.key === 'R') setGizmoMode('rotate');
});

fetch('/api/health').then((r) => r.json()).then((d) => {
  const h = $('health'); h.textContent = d.ok ? 'ready' : 'down'; if (d.ok) h.className = 'health ok';
}).catch(() => { $('health').textContent = 'offline'; });

refreshRuns();  // populate the Recent parts list on load
