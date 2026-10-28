// CALI-32 — the design session: a viewport and a conversation.
//
// Three surfaces: the chat (left), the 3D view (centre), and an inspector (right) for whatever is
// selected — the design as a whole, or the part you clicked. Clicking a part scopes the chat to it;
// that one rule replaces the old panel's mode toggles. Long work (a chat turn, a whittle study) runs as
// a job on the server and streams its progress here over Server-Sent Events (CALI-31).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const $ = (id) => document.getElementById(id);
const IN = 25.4;

const S = {
  slug: null,          // the open design
  design: null,        // its last state from the server
  scope: null,         // the selected part (the chat is about it), or null = the whole design
  busy: false,         // a turn is in flight
  station: null,       // {run, index} when previewing a whittle station in the viewport
  whittle: { ok: false },
  runIndex: {},        // part id -> which whittle run the inspector shows
  aeroRun: {}, frameRun: {},         // part id -> which parametric study the inspector shows
  built: {},           // part id -> {version, tried, report, balance}: what it's built from (CALI-41)
  balance: null,       // {key, data}: the whole design's weight and what the hitch carries
  payload: 0,          // lb of gear or people on the floor, for the balance
};

// ------------------------------------------------------------------------------------------ api
async function api(method, url, body) {
  const r = await fetch(url, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { const j = await r.json(); msg = j.detail || j.error || msg; } catch (e) { /* not JSON */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return r.json();
}

// Follow a job: Server-Sent Events, de-duplicated by sequence number, falling back to polling if the
// stream drops (a browser reconnect would otherwise replay events from the start).
function follow(jobId, onEvent) {
  return new Promise((resolve, reject) => {
    let seen = -1, done = false, es = null;
    const finish = (p) => {
      if (done) return; done = true; if (es) es.close();
      p.status === 'done' ? resolve(p.result) : reject(new Error(p.error || 'the job failed'));
    };
    const handle = (ev) => {
      if (ev.kind === 'end') return finish(ev);
      if (typeof ev.seq === 'number') { if (ev.seq <= seen) return; seen = ev.seq; }
      if (onEvent) onEvent(ev);
    };
    const poll = async () => {
      while (!done) {
        try {
          const j = await api('GET', `/api/jobs/${jobId}?after=${seen + 1}`);
          j.events.forEach(handle);
          if (j.status === 'done' || j.status === 'error') return finish(j);
        } catch (e) { done = true; return reject(e); }
        await new Promise((r) => setTimeout(r, 700));
      }
    };
    try {
      es = new EventSource(`/api/jobs/${jobId}/events`);
      es.onmessage = (m) => { try { handle(JSON.parse(m.data)); } catch (e) { showErr('event: ' + e.message); } };
      es.onerror = () => { if (done) return; es.close(); es = null; poll(); };
    } catch (e) { poll(); }
  });
}

// --------------------------------------------------------------------------------------- units
const inches = () => S.design && S.design.display_units === 'in';
function len(mm, digits) {
  if (mm == null || isNaN(mm)) return '—';
  return inches() ? `${(mm / IN).toFixed(digits ?? 1)}″` : `${mm.toFixed(digits ?? 0)} mm`;
}
function sizeText(size) {
  // x = along travel (depth), y = across (width), z = up (height) — the vehicle convention
  return `${len(size[1])} W × ${len(size[0])} D × ${len(size[2])} H`;
}

// ---------------------------------------------------------------------------------- text bits
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function md(text) {
  // just enough markdown for Caliper's replies: **bold**, `code`, _italic_, line breaks
  return esc(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])_([^_\n]+)_(?=[\s.,;:)!?]|$)/g, '$1<i>$2</i>')
    .replace(/\n/g, '<br>');
}
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const fixed = (v, d) => (v == null ? '—' : Number(v).toFixed(d));

// ------------------------------------------------------------------------------------- viewer
const viewer = $('viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
viewer.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0f13);
const camera = new THREE.PerspectiveCamera(40, 1, 1, 100000);
camera.up.set(0, 0, 1);                       // CAD convention: Z is up (CadQuery's frame)
camera.position.set(-3000, -3000, 2000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.screenSpacePanning = true;
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN };
scene.add(new THREE.HemisphereLight(0xffffff, 0x222a33, 1.05));
const sun = new THREE.DirectionalLight(0xffffff, 1.3); sun.position.set(-0.6, -1, 1.4); scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.35); fill.position.set(1, 0.8, 0.3); scene.add(fill);

let grid = null;
const meshes = new Map();       // part id -> THREE.Mesh
let stationMesh = null;         // a whittle station shown in place of its part
const loader = new STLLoader();

function resize() {
  const w = viewer.clientWidth || 1, h = viewer.clientHeight || 1;
  renderer.setPixelRatio(devicePixelRatio);
  renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewer);
resize();
(function loop() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); })();

function contentBox() {
  const box = new THREE.Box3();
  for (const m of meshes.values()) if (m.visible) box.expandByObject(m);
  if (stationMesh) box.expandByObject(stationMesh);
  return box;
}

function fitGrid(box) {
  if (grid) { scene.remove(grid); grid.geometry.dispose(); }
  const size = box.getSize(new THREE.Vector3());
  const span = Math.max(size.x, size.y, 200) * 2.2;
  const step = inches() ? IN * 12 : 250;                   // a foot, or 250 mm
  const n = Math.max(4, Math.min(80, Math.round(span / step)));
  grid = new THREE.GridHelper(n * step, n, 0x2a333d, 0x1a2027);
  grid.rotation.x = Math.PI / 2;                             // XZ → XY (the ground under Z-up)
  const c = box.getCenter(new THREE.Vector3());
  grid.position.set(c.x, c.y, Math.min(0, box.min.z));      // the ground, if the design sits on it
  scene.add(grid);
}

function frame() {
  const box = contentBox();
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2 || 100;
  const d = r * 2.3;
  controls.target.copy(c);
  camera.position.set(c.x - d * 0.75, c.y - d * 0.95, c.z + d * 0.55);   // from behind-left, above
  camera.near = r / 200; camera.far = r * 200; camera.updateProjectionMatrix();
  controls.update();
  fitGrid(box);
}
$('fitView').onclick = frame;
addEventListener('keydown', (e) => {
  if (e.key === 'f' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) frame();
});

function material(p) {
  const fixedRole = p.role === 'fixed';
  return new THREE.MeshStandardMaterial({
    color: fixedRole ? 0x9aa4ae : p.origin === 'whittled' ? 0xffb454 : 0x4ea1ff,
    transparent: fixedRole, opacity: fixedRole ? 0.32 : 1, depthWrite: !fixedRole,
    metalness: 0.08, roughness: 0.6,
  });
}

async function syncParts(design, refit) {
  const want = new Map(design.parts.map((p) => [p.id, p]));
  for (const [pid, m] of meshes) {
    if (!want.has(pid)) { scene.remove(m); m.geometry.dispose(); meshes.delete(pid); }
  }
  const loads = [];
  for (const p of design.parts) {
    const have = meshes.get(p.id);
    if (have && have.userData.version === p.version && have.userData.origin === p.origin
        && have.userData.role === p.role) continue;
    loads.push((async () => {
      const r = await fetch(p.stl_url);
      if (!r.ok) {
        let msg = `HTTP ${r.status}`;
        try { msg = (await r.json()).detail || msg; } catch (e) { /* not JSON */ }
        throw new Error(`${p.id}: ${msg}`);
      }
      const geom = loader.parse(await r.arrayBuffer());
      geom.computeVertexNormals();
      const mesh = new THREE.Mesh(geom, material(p));
      mesh.userData = { partId: p.id, version: p.version, origin: p.origin, role: p.role };
      const old = meshes.get(p.id);
      if (old) { scene.remove(old); old.geometry.dispose(); }
      meshes.set(p.id, mesh);
      scene.add(mesh);
    })());
  }
  const results = await Promise.allSettled(loads);
  const failed = results.filter((x) => x.status === 'rejected');
  if (failed.length) showErr(failed.map((f) => f.reason.message).join(' · '));
  paint();
  if (refit || (loads.length && meshes.size === loads.length)) frame();
}

// colour by what's true: selected, colliding, reference, whittled
function colliding() {
  const out = new Set();
  const rep = S.design && S.design.report;
  if (!rep) return out;
  for (const r of rep.results) {
    if (r.status === 'pass') continue;
    const m = /interference\((\w+),\s*(\w+)\)/.exec(r.expr);
    if (m) { out.add(m[1]); out.add(m[2]); }
  }
  return out;
}
function paint() {
  const hit = colliding();
  for (const [pid, m] of meshes) {
    const p = S.design.parts.find((x) => x.id === pid);
    if (!p) continue;
    const base = material(p);
    m.material.color.copy(hit.has(pid) ? new THREE.Color(0xf85149) : base.color);
    const sel = S.scope === pid;
    m.material.emissive.setHex(sel ? 0x1f6feb : 0x000000);
    m.material.emissiveIntensity = sel ? 0.55 : 0;
    m.visible = !(S.station && S.station.part === pid);
    // while previewing one part's design, fade the rest — the box would otherwise hide the frame
    const fade = !!S.station && S.station.part !== pid;
    const transparent = fade || base.transparent;
    if (m.material.transparent !== transparent) m.material.needsUpdate = true;   // recompiles the shader
    m.material.transparent = transparent;
    m.material.opacity = fade ? Math.min(0.18, base.opacity) : base.opacity;
    m.material.depthWrite = !transparent;
  }
}

// click a part to talk about it; click empty space to go back to the whole design
const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY, e.button]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  const d = down; down = null;
  if (!d || d[2] !== 0 || e.button !== 0) return;
  if (Math.hypot(e.clientX - d[0], e.clientY - d[1]) > 5) return;    // an orbit drag, not a click
  const hit = pick(e);
  setScope(hit ? hit.object.userData.partId : null);
});
renderer.domElement.addEventListener('pointermove', (e) => {
  const tip = $('tip');
  if (down) { tip.hidden = true; return; }
  const hit = pick(e);
  if (!hit) { tip.hidden = true; return; }
  const p = S.design.parts.find((x) => x.id === hit.object.userData.partId);
  tip.textContent = p ? `${p.id}${p.intent ? ' — ' + p.intent : ''}` : '';
  const rect = viewer.getBoundingClientRect();
  tip.style.left = `${e.clientX - rect.left + 14}px`;
  tip.style.top = `${e.clientY - rect.top + 10}px`;
  tip.hidden = !p;
});
function pick(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects([...meshes.values()].filter((m) => m.visible), false);
  return hits[0] || null;
}

// ------------------------------------------------------------------------------- the session
async function loadDesigns(select) {
  const { designs } = await api('GET', '/api/designs');
  const pickEl = $('designPick');
  pickEl.innerHTML = designs.length
    ? designs.map((d) => `<option value="${esc(d.slug)}">${esc(d.name)}</option>`).join('')
    : '<option value="">— no designs yet —</option>';
  const want = select || (location.hash ? decodeURIComponent(location.hash.slice(1)) : null);
  const slug = designs.find((d) => d.slug === want) ? want : (designs[0] && designs[0].slug);
  if (slug) { pickEl.value = slug; await openDesign(slug); } else { startNew(); }
}
$('designPick').onchange = (e) => e.target.value && openDesign(e.target.value);
$('newBtn').onclick = startNew;

async function openDesign(slug) {
  const first = S.slug !== slug;
  S.slug = slug; S.scope = null; S.station = null;
  location.hash = encodeURIComponent(slug);
  S.design = await api('GET', `/api/designs/${slug}`);
  if (first) { for (const m of meshes.values()) scene.remove(m); meshes.clear(); clearStation(); }
  render();
  await syncParts(S.design, first);
}

async function refresh() {
  if (!S.slug) return;
  S.design = await api('GET', `/api/designs/${S.slug}`);
  if (S.scope && !S.design.parts.find((p) => p.id === S.scope)) S.scope = null;
  render();
  await syncParts(S.design, false);
}

function render() {
  renderUnits(); renderThread(); renderInspector(); renderScope(); paint();
  $('viewHint').textContent = S.design && S.design.parts.length
    ? (S.scope ? '' : 'click a part to talk about it')
    : '';
}

function renderUnits() {
  for (const b of $('unitSeg').querySelectorAll('button')) {
    b.classList.toggle('on', !!S.design && b.dataset.u === S.design.display_units);
  }
}
$('unitSeg').onclick = async (e) => {
  const u = e.target.dataset.u;
  if (!u || !S.slug || u === S.design.display_units) return;
  S.design = await api('PATCH', `/api/designs/${S.slug}`, { display_units: u });
  render(); frame();
};

function setScope(pid) {
  S.scope = pid;
  if (S.station && S.station.part !== pid) clearStation();
  render();
  if (pid) $('msg').focus();
}
function renderScope() {
  $('scopeRow').hidden = !S.scope;
  $('scopeChip').textContent = S.scope || '';
  $('msg').placeholder = S.scope
    ? `What should change about ${S.scope}?`
    : (S.design && S.design.parts.length
      ? 'Click a part to talk about it, or ask about the whole design…'
      : 'Tell me which part to build first…');
}
$('scopeClear').onclick = () => setScope(null);

// --------------------------------------------------------------------------------- the thread
function renderThread() {
  const t = $('thread');
  const d = S.design;
  if (!d) return;
  const html = [];
  for (const e of d.log) {
    if (e.kind === 'created') {
      html.push(`<div class="note">Started <b>${esc(d.name)}</b> — ${esc(e.prompt)}</div>`);
    } else if (e.kind === 'clarify' && e.action === 'updated') {
      html.push(`<div class="note">Requirement changed — ${esc(e.question || '')} → <b>${esc(e.answer || '')}</b></div>`);
    } else if (e.kind === 'clarify' && e.action !== 'asked') {
      html.push(`<div class="note">Requirements recorded — ${e.answered || 0} answered, ` +
        `${e.assumed || 0} assumed. Tell me which part to build first.</div>`);
    } else if (e.kind === 'message') {
      html.push(`<div class="msg you">${e.scope ? `<div class="scope">on ${esc(e.scope)}</div>` : ''}` +
        `${md(e.text)}</div>`);
    } else if (e.kind === 'reply' && e.reply) {
      const tone = e.ok === false ? 'bad' : (e.action === 'answer' ? '' : 'good');
      html.push(`<div class="msg cal ${tone}"><div class="who">Caliper</div>${md(e.reply)}</div>`);
    } else if (e.kind === 'assertion') {
      html.push(`<div class="note">${e.action === 'promoted'
        ? `🔒 locked in <code>${esc(e.id)}</code>` : `left <code>${esc(e.id)}</code> as a one-off`}</div>`);
    } else if (e.kind === 'frame' && e.action === 'studied') {
      html.push(`<div class="note">whittle sized <b>${esc(e.part)}</b>'s tubes — results in the inspector</div>`);
    } else if (e.kind === 'frame' && e.action === 'adopted') {
      html.push(`<div class="note">used design ${e.station}'s tubes as v${e.version} — ${esc(Object.entries(e.design || {}).map(([g, k]) => `${g} ${k}`).join(', '))}</div>`);
    } else if (e.kind === 'aero' && e.action === 'studied') {
      html.push(`<div class="note">whittle searched <b>${esc(e.part)}</b>'s shape — results in the inspector</div>`);
    } else if (e.kind === 'aero' && e.action === 'adopted') {
      const nums = Object.entries(e.params || {}).map(([k, v]) => `${esc(k)} ${(+v).toFixed(0)}`).join(', ');
      html.push(`<div class="note">used station ${e.station}'s numbers as v${e.version} (${nums}) — still a parametric script</div>`);
    } else if (e.kind === 'whittle' && e.action === 'studied') {
      html.push(`<div class="note">whittle studied <b>${esc(e.part)}</b> — results in the inspector</div>`);
    } else if (e.kind === 'whittle' && e.action === 'adopted') {
      const grew = e.grew_mm ? Object.entries(e.grew_mm) : [];
      html.push(`<div class="note">brought whittle station ${e.station} back as v${e.version}</div>`);
      if (grew.length) {
        html.push(`<div class="msg cal bad"><div class="who">Caliper</div>⚠ The shape whittle sent back
          reaches past where this part used to be: ${grew.map(([side, mm]) => `<b>${len(mm)}</b> on ${esc(side)}`).join(', ')}.
          whittle rebuilds parts on a voxel grid, so its stations can come back slightly bigger — check the
          clearances, or say <b>roll it back</b>.</div>`);
      }
    }
  }
  if (d.clarify && d.clarify.length) html.push(clarifyCard(d.clarify));
  if (d.proposal && !S.busy) {
    html.push(`<div class="actions">
      <button class="ok" data-say="yes">Yes, lock it in</button>
      <button data-say="no">No, one-off</button></div>`);
  }
  t.innerHTML = html.join('') || '<div class="note">Nothing yet.</div>';
  t.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => send(b.dataset.say, null); });
  wireClarify();
  t.scrollTop = t.scrollHeight;
}

function clarifyCard(qs) {
  return `<div class="card" id="clarify">
    <h3>A few questions first</h3>
    <p class="muted small">Asked once, then they're fixed requirements every part is built against.
      Leave one blank and I'll use the suggestion, marked as an assumption.</p>
    ${qs.map((q) => `<div class="q"><label for="q_${esc(q.id)}">${esc(q.question)}</label>
      ${q.why ? `<div class="why">${esc(q.why)}</div>` : ''}
      <input type="text" id="q_${esc(q.id)}" data-q="${esc(q.id)}" placeholder="${esc(q.default)}"></div>`).join('')}
    <div class="actions">
      <button class="primary" id="clarifyGo">Use these answers</button>
      <button id="clarifySkip">Just build it</button>
    </div></div>`;
}
function wireClarify() {
  const go = $('clarifyGo'), skip = $('clarifySkip');
  if (!go) return;
  const submit = async (isSkip) => {
    const answers = {};
    document.querySelectorAll('#clarify [data-q]').forEach((i) => { answers[i.dataset.q] = i.value; });
    go.disabled = skip.disabled = true;
    try { S.design = await api('POST', `/api/designs/${S.slug}/clarify`, { answers, skip: isSkip }); render(); }
    catch (e) { showErr(e.message); go.disabled = skip.disabled = false; }
  };
  go.onclick = () => submit(false);
  skip.onclick = () => submit(true);
}

// a turn in flight: your message, then a reply bubble that narrates as events stream in
function liveTurn(text, scope) {
  const t = $('thread');
  t.querySelectorAll('.actions').forEach((n) => n.remove());
  const you = document.createElement('div');
  you.className = 'msg you';
  you.innerHTML = `${scope ? `<div class="scope">on ${esc(scope)}</div>` : ''}${md(text)}`;
  const cal = document.createElement('div');
  cal.className = 'msg cal';
  cal.innerHTML = '<div class="who">Caliper</div><div><span class="spin"></span>thinking…</div><ul class="steps"></ul>';
  t.append(you, cal);
  t.scrollTop = t.scrollHeight;
  const steps = cal.querySelector('.steps'), head = cal.children[1];
  return {
    step(ev) {
      const label = STEP_TEXT[ev.kind] ? STEP_TEXT[ev.kind](ev) : ev.text;
      if (!label) return;
      steps.querySelectorAll('li.now').forEach((li) => li.classList.remove('now'));
      const li = document.createElement('li');
      li.className = 'now'; li.textContent = label;
      steps.appendChild(li);
      head.innerHTML = `<span class="spin"></span>${esc(label)}`;
      t.scrollTop = t.scrollHeight;
    },
    fail(msg) {
      cal.classList.add('bad');
      head.innerHTML = `⚠ ${esc(msg)}`;
    },
  };
}
const STEP_TEXT = {
  started: () => '', finished: () => '', done: () => '',
  classified: (e) => (e.action === 'answer' ? 'reading the design'
    : e.action === 'author' ? `building a new part: ${e.part}`
      : e.action === 'refine' ? `revising ${e.part}`
        : e.action === 'revert' ? `rolling ${e.part} back` : e.text),
};

async function send(text, scope) {
  if (S.busy || !text.trim()) return;
  if (!S.slug) return createDesign(text);
  S.busy = true; $('send').disabled = true;
  const live = liveTurn(text, scope);
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/chat`, { message: text, scope });
    await follow(job_id, (ev) => live.step(ev));
    S.busy = false;
    await refresh();
  } catch (e) {
    live.fail(e.message);
  } finally {
    S.busy = false; $('send').disabled = false;
  }
}
$('composer').onsubmit = (e) => {
  e.preventDefault();
  const text = $('msg').value;
  $('msg').value = '';
  send(text, S.scope);
};
$('msg').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('composer').requestSubmit(); }
});

// a brand-new design: the first message is the root prompt, then the clarify round
function startNew() {
  // remember where we were: the button sits beside the design picker and is easy to hit by mistake
  const was = S.slug ? { slug: S.slug, name: S.design ? S.design.name : S.slug } : null;
  S.slug = null; S.design = null; S.scope = null;
  for (const m of meshes.values()) scene.remove(m);
  meshes.clear(); clearStation();
  history.replaceState(null, '', location.pathname);
  $('inspector').innerHTML = '<div class="empty">Your design will show up here.</div>';
  $('scopeRow').hidden = true;
  $('thread').innerHTML = `<div class="card">
    <h3>What are you building?</h3>
    <p class="muted small">Describe the whole thing — sizes, what it attaches to, what it carries.
      I'll ask a few questions, then we build it part by part.</p>
    <textarea id="newPrompt" rows="5" placeholder="e.g. a cargo box on my car's trailer hitch, 74″ wide…"></textarea>
    <div class="actions"><button class="primary" id="newGo">Start</button>
      ${was ? `<button id="newBack" class="ghost">← back to ${esc(was.name)}</button>` : ''}</div></div>`;
  $('msg').placeholder = 'Or type it here…';
  $('newGo').onclick = () => createDesign($('newPrompt').value);
  if (was) $('newBack').onclick = () => { $('designPick').value = was.slug; openDesign(was.slug); };
  $('newPrompt').focus();
}
async function createDesign(prompt) {
  if (!prompt.trim()) return;
  S.busy = true;
  $('thread').innerHTML = `<div class="msg you">${md(prompt)}</div>
    <div class="msg cal"><div class="who">Caliper</div><span class="spin"></span>working out what to ask…</div>`;
  try {
    const { slug, job_id } = await api('POST', '/api/designs', { prompt });
    await follow(job_id);
    S.busy = false;
    await loadDesigns(slug);
  } catch (e) {
    showErr(e.message);
  } finally { S.busy = false; }
}

// ------------------------------------------------------------------------------- inspector
function renderInspector() {
  const el = $('inspector'), d = S.design;
  if (!d) return;
  const p = S.scope && d.parts.find((x) => x.id === S.scope);
  el.innerHTML = p ? partView(p) : designView(d);
  wireInspector(p);
}

function checks(report, only) {
  if (!report) return '<div class="empty">Nothing to measure yet.</div>';
  const rows = report.results.filter((r) => !only || only(r));
  if (!rows.length) return '<div class="empty">No checks.</div>';
  return '<ul class="list">' + rows.map((r) => `<li class="check ${r.status}">
    <span class="s">${r.status === 'pass' ? '✓' : r.status === 'deferred' ? '·' : '✗'}</span>
    <span><b>${esc(r.id)}</b> <code>${esc(r.expr)}</code>${r.actual != null && r.status !== 'pass'
      ? ` <span class="muted">→ ${esc(typeof r.actual === 'number' ? r.actual.toFixed(3) : r.actual)}</span>` : ''}</span>
    </li>`).join('') + '</ul>';
}

function designView(d) {
  const rep = d.report;
  const status = rep ? (rep.all_pass ? '<span class="badge ok">all checks pass</span>'
    : '<span class="badge bad">checks failing</span>') : '';
  return `<h2>${esc(d.name)} ${status}</h2>
    <div class="muted small">${esc(d.prompt)}</div>
    <h4>Scorecard</h4><div id="scoreBox">${scoreView(d)}</div>
    <h4>Requirements</h4>
    ${d.requirements.length ? '<ul class="list">' + d.requirements.map((r) => `<li>${esc(r.question)}
      <div><b>${esc(r.answer)}</b>${r.source === 'assumed' ? ' <span class="badge">assumed</span>' : ''}</div></li>`).join('') + '</ul>'
    : '<div class="empty">None yet.</div>'}
    <h4>Parts</h4>
    ${d.parts.length ? '<ul class="list">' + d.parts.map((p) => `<li><span class="partlink" data-part="${esc(p.id)}">${esc(p.id)}</span>
      <span class="muted small">v${p.version}</span>
      ${p.role === 'fixed' ? '<span class="badge ref">reference</span>' : ''}
      ${p.origin === 'whittled' ? '<span class="badge whittled">whittled</span>' : ''}
      <div class="muted small">${esc(p.intent)}</div>
      ${p.bbox ? `<div class="small">${sizeText(p.bbox.size)}</div>` : ''}</li>`).join('') + '</ul>'
    : '<div class="empty">None yet — say what to build first.</div>'}
    ${Object.keys(d.part_errors || {}).length ? '<h4>Won\'t build</h4><ul class="list">' +
      Object.entries(d.part_errors).map(([k, v]) => `<li><b>${esc(k)}</b> <span class="muted small">${esc(v)}</span></li>`).join('') + '</ul>' : ''}
    ${d.parts.some((p) => p.built) ? `<h4>Weight &amp; balance</h4><div id="balanceBox">${balanceView()}</div>` : ''}
    <h4>Design checks</h4>
    ${checks(rep)}`;
}

// ------------------------------------------------------------- the scorecard (CALI-47)
// One card for the design as it stands: every check (pass/fail, margin) and every objective (value, change
// since the last card) across design, optimization, making and cost — each with how far to trust it.
const TRUST = { measured: 'measured', model: 'a model (on the safe side)', rough: 'rough', guess: 'a guess' };
function scoreView(d) {
  const card = (d.scorecards || [])[0];
  const stale = card && d.parts.some((p) => card.versions && card.versions[p.id] !== undefined && card.versions[p.id] !== p.version);
  const num = (v, u) => {
    if (v == null) return '—';
    const n = typeof v === 'number' ? (Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : `${+v.toFixed(2)}`) : esc(String(v));
    return u === '$' ? `$${n}` : `${n}${u ? ' ' + esc(u) : ''}`;
  };
  const tag = (t) => t ? `<span class="badge" title="how far to trust it">${esc(TRUST[t] || t)}</span>` : '';
  const goals = d.has_goals ? '' : '<div class="muted small">No <code>scorecard.yaml</code> yet: only the design\'s own rules are checked. Tell me what it must do and I\'ll write it.</div>';
  if (!card) return `${goals}<div class="actions"><button id="scGo">Score it</button></div><div id="scProgress"></div>`;
  const delta = (o) => {
    if (o.change == null || Math.abs(o.change) < 1e-9) return '';
    const better = o.direction === 'max' ? o.change > 0 : o.change < 0;
    return ` <span class="small" style="color:var(${better ? '--ok' : '--bad'})">${o.change > 0 ? '+' : ''}${num(o.change)}</span>`;
  };
  return `<div class="small">${card.summary.pass} pass · <b style="color:var(--bad)">${card.summary.fail} fail</b>${card.summary.unknown ? ` · ${card.summary.unknown} unknown` : ''}
      <span class="muted">· scored ${new Date(card.created * 1000).toLocaleString()}</span>
      ${stale ? '<span class="badge bad">a part has changed since</span>' : ''}</div>
    <ul class="list small" style="margin-top:6px">${card.checks.map((c) => `<li>${c.status === 'pass' ? '✓' : c.status === 'fail' ? '<span style="color:var(--bad)">✗</span>' : '?'}
      ${esc(c.label || c.id)} ${c.value != null ? `— ${num(c.value, c.unit)}` : ''}${c.assumed ? ' <span class="badge">assumed</span>' : ''} ${tag(c.trust)}</li>`).join('')}</ul>
    <table class="st" style="margin-top:6px">${card.objectives.map((o) => `<tr><td style="text-align:left">${esc(o.label)}</td>
      <td>${num(o.value, o.unit)}${delta(o)}</td><td>${tag(o.trust)}</td></tr>`).join('')}</table>
    ${card.cost ? `<details class="small" style="margin-top:6px"><summary>Stock: $${Math.round(card.cost.usd)} · offcut $${Math.round(card.cost.waste_usd)}</summary>
      <table class="st">${card.cost.lines.map((l) => `<tr><td style="text-align:left">${esc(l.part)}</td><td style="text-align:left">${esc(l.item)}</td>
        <td>$${l.usd.toFixed(0)}</td><td class="muted">${l.waste_usd ? `$${l.waste_usd.toFixed(0)} offcut` : ''}</td></tr>`).join('')}</table>
      <div class="muted">${esc(card.cost.basis)}</div></details>` : ''}
    ${(card.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    ${goals}<div class="actions"><button id="scGo">${stale ? 'Score it again' : 'Score it'}</button></div><div id="scProgress"></div>`;
}

function wireScore() {
  const go = $('scGo');
  if (!go) return;
  go.onclick = async () => {
    const prog = $('scProgress');
    go.disabled = true;
    prog.innerHTML = '<div class="small muted" id="scMsg">scoring…</div>';
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/scorecard`);
      await follow(job_id, (ev) => { const m = $('scMsg'); if (m && ev.text && ev.kind !== 'started') m.textContent = ev.text; });
      await refresh();
    } catch (e) { prog.innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`; go.disabled = false; }
  };
}

function historyItem(h) {
  if (h.kind === 'revision') {
    const what = h.action === 'frame' ? `tubes sized — design ${h.station} (${h.mass_lb} lb, ${h.safety}x)`
      : h.action === 'aero' ? `shaped for drag — station ${h.station}`
      : h.action === 'whittle' ? `from whittle${h.station != null ? ' — station ' + h.station : ''}`
      : h.action === 'build' ? 'construction changed'
      : h.action === 'restore' ? `rolled back to v${h.restored_from}` : h.action;
    return `<li class="hist"><span class="v">v${h.version}</span>${esc(what)}
      ${h.feedback && h.action !== 'author' ? `<div>“${esc(h.feedback)}”</div>` : ''}
      ${h.result ? `<span class="badge ${h.result === 'all_pass' ? 'ok' : 'bad'}">${h.result === 'all_pass' ? 'passed' : 'failing'}</span>` : ''}</li>`;
  }
  if (h.kind === 'assertion') {
    return `<li class="hist">${h.action === 'promoted' ? '🔒 locked in' : 'declined'} <code>${esc(h.expr || h.id)}</code></li>`;
  }
  if (h.kind === 'whittle') return `<li class="hist">studied in whittle (${esc(h.study)}, ${h.stations} stations)</li>`;
  if (h.kind === 'frame' && h.action === 'studied') return `<li class="hist">frame study (${h.stations} designs)</li>`;
  if (h.kind === 'aero' && h.action === 'studied') return `<li class="hist">shape search: ${esc((h.searched || []).join(', '))}</li>`;
  if (h.kind === 'setting') return `<li class="hist">marked ${h.role === 'fixed' ? 'as a reference' : 'as a design part'}</li>`;
  return '';
}

function partView(p) {
  const d = S.design;
  const mine = (r) => new RegExp(`\\b${p.id}\\b`).test(r.expr);
  const designRules = d.rules.filter(mine);
  const origin = p.origin === 'whittled' ? '<span class="badge whittled">whittled mesh</span>'
    : p.scripted ? '<span class="badge">parametric</span>' : '<span class="badge">imported</span>';
  return `<h2>${esc(p.id)} ${origin}</h2>
    <div class="muted small">${esc(p.intent)} · v${p.version}</div>
    <h4>Size</h4>
    ${p.bbox ? `<div class="kv">
      <span class="k">width</span><span>${len(p.bbox.size[1])}</span>
      <span class="k">depth</span><span>${len(p.bbox.size[0])}</span>
      <span class="k">height</span><span>${len(p.bbox.size[2])}</span>
      <span class="k">bottom at</span><span>${len(p.bbox.min[2])}</span></div>` : '<div class="empty">won\'t build</div>'}
    <label class="small muted" style="display:block;margin-top:8px">
      <input type="checkbox" id="roleRef" ${p.role === 'fixed' ? 'checked' : ''}> treat as a reference (context, e.g. the car)</label>
    <h4>Rules on this part</h4>
    ${p.rules.length || designRules.length ? '<ul class="list">' +
      [...p.rules, ...designRules].map((r) => `<li class="rule">🔒 <b>${esc(r.id)}</b> <code>${esc(r.expr)}</code></li>`).join('') + '</ul>'
    : '<div class="empty">None yet. Say something like “it must clear the car by 2 in” and I\'ll offer to lock it in.</div>'}
    ${p.built ? `<h4>Built from <span class="badge">weight &amp; shopping list</span></h4>
    <div id="buildBox">${buildView(p)}</div>` : ''}
    ${p.framed ? `<h4>Size the frame <span class="badge">tubes back</span></h4>
    <div id="frameBox">${frameView(p)}</div>` : `<h4>Shape it for drag <span class="badge">numbers back</span></h4>
    <div id="aeroBox">${aeroView(p)}</div>
    <h4>whittle carving <span class="badge">mesh back</span></h4>
    <div id="whittleBox">${whittleView(p)}</div>`}
    <h4>History</h4>
    <ul class="list">${p.history.slice().reverse().map(historyItem).join('')}</ul>
    <details id="adv"><summary>Advanced — script &amp; spec</summary><div id="advBody" class="small muted">loading…</div></details>`;
}

function wireInspector(p) {
  document.querySelectorAll('#inspector [data-part]').forEach((a) => { a.onclick = () => setScope(a.dataset.part); });
  showMarks();
  if (!p) { wireBalance(); wireScore(); return; }
  wireBuilt(p);
  const role = $('roleRef');
  if (role) role.onchange = async () => {
    S.design = await api('PATCH', `/api/designs/${S.slug}/parts/${p.id}`, { role: role.checked ? 'fixed' : 'movable' });
    render(); syncParts(S.design, false);
  };
  const adv = $('adv');
  if (adv) adv.ontoggle = async () => {
    if (!adv.open || adv.dataset.loaded) return;
    adv.dataset.loaded = '1';
    try {
      const s = await api('GET', `/api/designs/${S.slug}/parts/${p.id}/script`);
      $('advBody').innerHTML = `${s.scripted ? '' : '<div>The current revision is a mesh; this is the script underneath it.</div>'}
        <pre>${esc(s.script)}</pre>${s.spec_yaml ? `<pre>${esc(s.spec_yaml)}</pre>` : ''}`;
    } catch (e) { $('advBody').textContent = e.message; }
  };
  wireWhittle(p);
  wireAero(p);
  wireFrame(p);
}

// ------------------------------------------------------------- what it's built from (CALI-41)
// A part that declares construction() (or a frame's members()) is weighed piece by piece: its weight,
// where its centre of gravity sits, and what to buy. The pickers try other choices without saving;
// "Use these" writes them into the part's BUILD dict — its shape doesn't change.
const lbs = (v) => (v == null ? '—' : `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 })} lb`);
const lbin = (v) => (v == null ? '—' : `${Number(v).toLocaleString()} lb·in`);
const sheetFt = (mm) => `${+(mm[1] / IN / 12).toFixed(1)}×${+(mm[0] / IN / 12).toFixed(1)} ft`;
const HITCH_NOTE = 'Compare with your hitch\'s rating: tongue weight × the distance from the pin to the ball — ' +
  'e.g. 350 lb × ~7″ ≈ 2,450 lb·in for a typical Class II.';

function triedFor() {      // every part's what-ifs, so the balance shows them too
  const out = {};
  for (const [pid, c] of Object.entries(S.built)) if (c.tried && Object.keys(c.tried).length) out[pid] = c.tried;
  return out;
}

function buildView(p) {
  const c = S.built[p.id];
  if (!c || c.version !== p.version) { loadBuilt(p, c && c.version === p.version ? c.tried : {}); return '<div class="small muted">weighing…</div>'; }
  if (c.loading) return '<div class="small muted">weighing…</div>';
  if (c.error) return `<div class="small" style="color:var(--bad)">⚠ ${esc(c.error)}</div>`;
  return builtResults(p, c);
}

async function loadBuilt(p, tried) {
  S.built[p.id] = { version: p.version, tried: tried || {}, loading: true };
  try {
    const [report, balance] = await Promise.all([
      api('POST', `/api/designs/${S.slug}/parts/${p.id}/construction`, { build: tried || {} }),
      api('POST', `/api/designs/${S.slug}/balance`, { build: { ...triedFor(), [p.id]: tried || {} }, payload_lb: S.payload }),
    ]);
    S.built[p.id] = { version: p.version, tried: tried || {}, report, balance };
  } catch (e) { S.built[p.id] = { version: p.version, tried: tried || {}, error: e.message }; }
  S.balance = null;                       // the design's balance changes with any part's what-if
  const box = $('buildBox');
  if (box && S.scope === p.id) { box.innerHTML = buildView(p); wireBuilt(p); showMarks(); }
}

function picker(k, ch, v) {
  if (ch.kind === 'number') return `<input type="number" data-bk="${esc(k)}" step="any" value="${v}">`;
  const label = (o) => (ch.labels && ch.labels[String(o)]) || o;
  return `<select data-bk="${esc(k)}" data-num="${typeof v === 'number' ? 1 : ''}">${ch.options.map((o) =>
    `<option value="${esc(o)}" ${String(o) === String(v) || (typeof v === 'number' && Math.abs(o - v) < 1e-6) ? 'selected' : ''}>${esc(label(o))}</option>`).join('')}</select>`;
}

function cogText(p, cog) {
  if (!p.bbox) return '';
  const back = p.bbox.max[0] - cog[0], up = cog[2] - p.bbox.min[2];
  const side = Math.abs(cog[1]) < 5 ? 'centred side to side' : `${len(Math.abs(cog[1]), 1)} to the ${cog[1] > 0 ? 'left' : 'right'}`;
  return `${len(back, 1)} behind its front, ${len(up, 1)} above its bottom, ${side}`;
}

function cutsText(cuts) {
  const n = new Map();
  for (const c of cuts) { const k = len(c.length_mm, 1); n.set(k, (n.get(k) || 0) + 1); }
  return [...n].map(([k, v]) => `${v} @ ${k}`).join(', ');
}

function builtResults(p, c) {
  const r = c.report, b = c.balance, changed = Object.keys(r.changed || {}).length;
  const mine = b && (b.parts || []).find((x) => x.part === p.id);
  const bom = r.bom;
  return `<div class="card">
      <b style="font-size:1.3em">${lbs(r.mass_lb)}</b> ${changed ? '<span class="badge">trying — not saved</span>' : ''}
      <div class="small">centre of gravity ${cogText(p, r.cog)} <span class="muted">(the red dot)</span></div>
      ${(r.keeps || []).map((k) => `<div class="small" style="margin-top:4px">${k.clear
        ? `✓ holds the <b>${esc(k.name)}</b>`
        : `<span style="color:var(--bad)">✗ the <b>${esc(k.name)}</b> doesn't fit — the outside cuts ${len(k.depth_mm, 1)} into it</span>`}
        <span class="muted">(${esc(k.note || '')}${k.note ? '; ' : ''}the pale slab)</span></div>`).join('')}
      ${b && b.moment_lbin != null ? `<div class="small" style="margin-top:4px">With the rest of the design the hitch carries
        <b>${lbs(b.force_lb)}</b> and <b>${lbin(b.moment_lbin)}</b>${mine ? ` — this part ${lbin(mine.moment_lbin)} of it, ${len(mine.arm_in * IN, 1)} behind the hitch` : ''}.</div>` : ''}
    </div>
    ${Object.keys(r.choices || {}).length ? `<div class="form" style="margin-top:10px">
      ${Object.entries(r.choices).map(([k, ch]) => `<span>${esc(k.replace(/_/g, ' '))}</span><span>${picker(k, ch, r.build[k])}</span>`).join('')}
    </div>
    <div class="actions">${changed ? '<button class="primary" id="bUse">Use these</button> <button class="ghost" id="bReset">Back to saved</button>'
      : '<span class="small muted">Change a choice to see what it weighs — nothing is saved until you say so.</span>'}</div>` : ''}
    <table class="st"><tr><th style="text-align:left">made of</th><th>lb</th><th>share</th></tr>
      ${r.materials.map((m) => `<tr><td style="text-align:left">${esc(m.label)}</td><td>${m.mass_lb}</td>
        <td>${pct(m.mass_kg / r.mass_kg)}</td></tr>`).join('')}</table>
    <h5 style="margin:12px 0 4px">To buy</h5>
    <ul class="list small">
      ${bom.sheets.map((g) => `<li><b>${g.count} × ${esc(g.label)}</b> <span class="muted">${sheetFt(g.stock_mm)} sheets · ${g.area_ft2} ft² of panels</span>
        <div class="muted">${g.panels.map((x) => `${esc(x.name)} ${len(x.size_mm[0], 1)} × ${len(x.size_mm[1], 1)}${x.flat ? '' : ' (bent)'}`).join(' · ')}</div></li>`).join('')}
      ${bom.sticks.map((g) => `<li><b>${g.count} × ${esc(g.label)}</b> <span class="muted">${+(g.stock_len_mm / IN / 12).toFixed(1)} ft lengths</span>
        <div class="muted">cuts: ${cutsText(g.cuts)}</div></li>`).join('')}
      ${bom.coverings.map((g) => `<li><b>${esc(g.label)}</b> <span class="muted">${g.area_ft2} ft²</span>
        <div class="muted">${[g.canvas_yd != null ? `${g.canvas_yd} yd of ${g.canvas_roll_in}″ canvas` : '',
          g.cloth_yd != null ? `${g.cloth_yd} yd of ${g.cloth_roll_in}″ glass cloth (${g.layers} layer${g.layers > 1 ? 's' : ''})` : '',
          g.epoxy_gal != null ? `${g.epoxy_gal} gal epoxy` : '',
          g.glue_gal != null ? `${g.glue_gal} gal glue` : '',
          g.paint_gal != null ? `${g.paint_gal} gal paint (${g.coats} coats)` : ''].filter(Boolean).join(' · ')}</div></li>`).join('')}
      ${bom.lumps.map((g) => `<li><b>${esc(g.name)}</b> <span class="muted">${lbs(g.mass_kg * 2.20462)}</span></li>`).join('')}
    </ul>
    ${(r.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    <div class="muted small" style="margin-top:4px">Counts are a shopping estimate (panels packed on whole sheets, cuts on
      whole sticks); the cut plan below nests the real shapes. Densities: <code>materials.py</code>.</div>
    <div id="cutplanBox">${cutplanView(p)}</div>`;
}

// --------------------------------------------------------------------- cut plan (CALI-45)
// Every panel flattened and nested onto the sheets it's cut from by Theo's unfold-to-sheets — score lines
// where a panel bends — and every stick cut-listed. Sheets as SVG (click for full size) and DXF for CAM.
function cutplanView(p) {
  if (S.design.cutplan_unavailable) return `<h5 style="margin:14px 0 4px">Cut plan</h5>
    <div class="muted small">Not here: ${esc(S.design.cutplan_unavailable)}.</div>`;
  const run = (S.design.cutplans || []).find((r) => r.part === p.id);
  const url = (path) => `/api/designs/${S.slug}/cutplans/${run.id}/files/${path}`;
  const sheets = run ? run.sheets.map((g) => {
    const svgs = g.files.filter((f) => f.name.startsWith('sheets/') && f.name.endsWith('.svg')).map((f) => f.name);
    return `<div style="margin-top:10px"><b>${g.sheets} × ${esc(g.stock)}</b>
        <span class="muted small">· ${esc(g.label)} · ${g.pieces} piece${g.pieces === 1 ? '' : 's'} · ${pct(g.utilisation)} used${g.scored ? ` · ${g.scored} score lines` : ''}</span>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px">${svgs.map((n) => `<a href="${url(`${g.key}/${n}`)}" target="_blank"
          title="${esc(n)} — open full size"><img src="${url(`${g.key}/${n}`)}" alt="${esc(n)}" style="width:100%;background:#fff;border-radius:4px;display:block"></a>`).join('')}</div>
        <div class="small" style="margin-top:4px">${svgs.map((n, i) => `<a href="${url(`${g.key}/${n.replace(/\.svg$/, '.dxf')}`)}">sheet ${i + 1} DXF</a>`).join(' · ')}
          · <a href="${url(`${g.key}/pattern.pdf`)}" target="_blank">printable PDF</a>
          · <a href="${url(`${g.key}/assembly.svg`)}" target="_blank">which piece is which</a>
          · <a href="${url(`${g.key}/assembly.txt`)}" target="_blank">seam list</a></div>
        ${g.worst_edge_error > 0.5 ? `<div class="muted small">Curved pieces don't lie perfectly flat: an edge is out by up to ${len(g.worst_edge_error, 1)}.</div>` : ''}
        ${(g.bevels || []).length ? `<div class="small" style="margin-top:4px">Bevels (each edge at half the angle the pieces meet at):
          ${g.bevels.map((b) => `${esc(b.a)}/${esc(b.b)} ${b.bevel_max - b.bevel_min >= 1 ? `${b.bevel_min.toFixed(0)}–${b.bevel_max.toFixed(0)}°` : `${b.bevel_max.toFixed(0)}°`}`).join(' · ')}</div>` : ''}
        ${(g.missing || []).length ? `<div class="small" style="color:var(--bad)">✗ ${g.missing.length} piece(s) didn't fit a sheet: ${g.missing.map((m) => esc(m.label)).join(', ')}</div>` : ''}
      </div>`;
  }).join('') : '';
  const endText = (e) => e.butts ? `${e.miter_deg >= 0.5 ? `mitre ${e.miter_deg.toFixed(0)}°` : 'square'} to the ${esc(e.butts)}`
    : e.carries ? `square, ${len(e.extend_mm, 2)} past the joint` : 'square';
  const tubes = run && (run.tubes || []).length ? `<table class="st" style="margin-top:10px"><tr><th style="text-align:left">tube</th><th>cut to</th><th style="text-align:left">ends</th></tr>
      ${run.tubes.map((g) => `<tr><td colspan="3" style="text-align:left"><b>${esc(g.label)}</b> <span class="muted">${g.count} × ${+(g.stock_len_mm / IN / 12).toFixed(1)} ft</span></td></tr>
        ${g.cuts.map((t) => `<tr><td style="text-align:left">${esc(t.name)}</td><td>${len(t.length_mm, 2)}</td>
          <td style="text-align:left" class="small">${t.ends.map(endText).join(' · ')}</td></tr>`).join('')}`).join('')}</table>` : '';
  const plates = run && (run.plates || []).length ? `<div style="margin-top:10px"><b>Gusset plates</b> <span class="muted small">plasma, DXF in mm</span>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px">${run.plates.map((pl) => `<div class="small">
        <a href="${url(`plates/${pl.name}.svg`)}" target="_blank"><img src="${url(`plates/${pl.name}.svg`)}" alt="${esc(pl.name)}"
          style="width:100%;max-height:140px;object-fit:contain;background:#fff;border-radius:4px;display:block"></a>
        <b>${pl.count} × ${esc(pl.name)}</b> · ${esc(pl.label)} · ${len(pl.size_mm[0], 1)} × ${len(pl.size_mm[1], 1)} · ${pl.safety}x
        · takes ${pct(pl.relief)} off the ${esc(pl.members.join('/'))} weld · <a href="${url(`plates/${pl.name}.dxf`)}">DXF</a></div>`).join('')}</div>
      ${[...new Set(run.plates.flatMap((pl) => pl.notes))].map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}</div>` : '';
  const sticks = run && run.sticks.length ? `<table class="st" style="margin-top:10px"><tr><th style="text-align:left">cut</th><th>length</th><th style="text-align:left">piece</th></tr>
      ${run.sticks.map((g) => `<tr><td colspan="3" style="text-align:left"><b>${esc(g.label)}</b> <span class="muted">${g.count} × ${+(g.stock_len_mm / IN / 12).toFixed(1)} ft</span></td></tr>
        ${g.cuts.map((c) => `<tr><td></td><td>${len(c.length_mm, 1)}</td><td style="text-align:left">${esc(c.name)}</td></tr>`).join('')}`).join('')}</table>
` : '';
  const stale = run && run.version !== p.version
    ? `<div class="small" style="color:var(--bad)">Made for v${run.version}; the part is v${p.version} now — make it again.</div>` : '';
  return `<h5 style="margin:14px 0 4px">Cut plan</h5>
    ${run ? `${stale}${sheets}${plates}${tubes}${sticks}<div class="small"><a href="${url('cutlist.txt')}" target="_blank">cut list as text</a></div>
      ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`
      : `<div class="muted small">Flatten every panel onto the sheets it's cut from — score lines where it bends — and list every
         stick to cut. Uses unfold-to-sheets.</div>`}
    <div class="actions"><button id="cpGo">${run ? 'Make it again' : 'Make the cut plan'}</button></div><div id="cpProgress"></div>`;
}

function wireCutplan(p) {
  const go = $('cpGo');
  if (!go) return;
  go.onclick = async () => {
    const prog = $('cpProgress');
    go.disabled = true;
    prog.innerHTML = '<div class="small muted" id="cpMsg">unfolding…</div>';
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/cutplan`);
      await follow(job_id, (ev) => { const m = $('cpMsg'); if (m && ev.text && ev.kind !== 'started') m.textContent = ev.text; });
      await refresh();
    } catch (e) {
      prog.innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`;
      go.disabled = false;
    }
  };
}

function wireBuilt(p) {
  const c = S.built[p.id];
  if (!c || !c.report) return;
  wireCutplan(p);
  document.querySelectorAll('#buildBox [data-bk]').forEach((el) => {
    el.onchange = () => {
      const tried = {};
      document.querySelectorAll('#buildBox [data-bk]').forEach((e) => {
        const k = e.dataset.bk;
        const v = e.tagName === 'INPUT' || e.dataset.num ? +e.value : e.value;
        if (String(v) !== String(c.report.saved[k])) tried[k] = v;
      });
      loadBuilt(p, tried);
    };
  });
  const use = $('bUse');
  if (use) use.onclick = async () => {
    use.disabled = true;
    try {
      const got = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/construction/use`, { build: c.tried });
      S.design = got.design;
      S.built[p.id] = { version: got.version, tried: {}, report: got.report, balance: c.balance };
      S.balance = null;
      render();
      loadBuilt(S.design.parts.find((x) => x.id === p.id), {});
    } catch (e) { showErr(e.message); use.disabled = false; }
  };
  const reset = $('bReset');
  if (reset) reset.onclick = () => loadBuilt(p, {});
}

function balanceKey() {
  return JSON.stringify([S.design.parts.map((p) => `${p.id}:${p.version}`), S.payload, triedFor()]);
}

function balanceView() {
  const key = balanceKey();
  if (!S.balance || S.balance.key !== key) { loadBalance(key); return '<div class="small muted">weighing…</div>'; }
  if (S.balance.loading) return '<div class="small muted">weighing…</div>';
  if (S.balance.error) return `<div class="small" style="color:var(--bad)">⚠ ${esc(S.balance.error)}</div>`;
  const b = S.balance.data, tried = Object.keys(triedFor()).length;
  return `<div class="card"><b style="font-size:1.3em">${lbs(b.mass_lb)}</b> ${tried ? '<span class="badge">with what-ifs</span>' : ''}
      ${b.moment_lbin != null ? `<div class="small">The hitch carries <b>${lbs(b.force_lb)}</b> with its centre of gravity
        ${len(b.arm_in * IN, 1)} behind it: <b>${lbin(b.moment_lbin)}</b> standing still.</div>` : ''}
      <div class="muted small" style="margin-top:4px">${HITCH_NOTE}</div></div>
    <div class="form" style="margin-top:8px"><span>payload</span>
      <span><input type="number" id="payload" value="${S.payload}" min="0" step="10"> lb on the floor</span></div>
    <table class="st"><tr><th style="text-align:left">part</th><th>lb</th><th>behind hitch</th><th>lb·in</th></tr>
      ${b.parts.map((x) => `<tr><td style="text-align:left">${x.part === 'payload' ? 'payload' : `<span class="partlink" data-part="${esc(x.part)}">${esc(x.part)}</span>`}</td>
        <td>${x.mass_lb}</td><td>${x.arm_in != null ? len(x.arm_in * IN, 1) : '—'}</td>
        <td>${x.moment_lbin != null ? Number(x.moment_lbin).toLocaleString() : '—'}</td></tr>`).join('')}</table>
    ${(b.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    <div class="muted small" style="margin-top:4px">Red dot: the centre of gravity. Green: the hitch point.</div>`;
}

async function loadBalance(key) {
  S.balance = { key, loading: true };
  try {
    const data = await api('POST', `/api/designs/${S.slug}/balance`, { build: triedFor(), payload_lb: S.payload });
    S.balance = { key, data };
  } catch (e) { S.balance = { key, error: e.message }; }
  const box = $('balanceBox');
  if (box && !S.scope) {
    box.innerHTML = balanceView();
    wireBalance();
    box.querySelectorAll('[data-part]').forEach((a) => { a.onclick = () => setScope(a.dataset.part); });
    showMarks();
  }
}

function wireBalance() {
  const pl = $('payload');
  if (pl) pl.onchange = () => {
    S.payload = Math.max(0, +pl.value || 0);
    const box = $('balanceBox');
    box.innerHTML = balanceView();
  };
}

// the centre of gravity (red) and hitch point (green), drawn through everything
const marks = new THREE.Group();
marks.renderOrder = 10;
scene.add(marks);
function showMarks() {
  for (const m of [...marks.children]) { marks.remove(m); m.geometry && m.geometry.dispose(); }
  const c = S.scope && S.built[S.scope];
  const b = S.scope ? (c && c.balance) : (S.balance && S.balance.data);
  const cog = S.scope ? (c && c.report && c.report.cog) : (b && b.mass_kg ? b.cog : null);
  const size = Math.max(contentBox().getSize(new THREE.Vector3()).length() / 160, 8);
  const dot = (at, color) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(size, 20, 14),
      new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true }));
    m.position.set(...at); m.renderOrder = 10;
    marks.add(m);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...at), new THREE.Vector3(at[0], at[1], 0)]),
      new THREE.LineDashedMaterial({ color, dashSize: size, gapSize: size * 0.7, depthTest: false, transparent: true }));
    line.computeLineDistances(); line.renderOrder = 10;
    marks.add(line);
  };
  if (cog) dot(cog, 0xff4d3d);
  if (b && b.hitch && (!S.scope || cog)) dot(b.hitch, 0x3fb950);
  // what the part has to hold (keeps(): the mattress) — a pale slab if it fits, red if the outside cuts in
  for (const k of (S.scope && c && c.report && c.report.keeps) || []) {
    const lo = new THREE.Vector3(...k.lo), hi = new THREE.Vector3(...k.hi);
    const geom = new THREE.BoxGeometry(...hi.clone().sub(lo).toArray()), color = k.clear ? 0xd8ecff : 0xff4d3d;
    const at = lo.clone().add(hi).multiplyScalar(0.5);
    const fill = new THREE.Mesh(geom, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, depthTest: false, depthWrite: false }));
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geom), new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true }));
    for (const m of [fill, edges]) { m.position.copy(at); m.renderOrder = 9; marks.add(m); }
  }
}

// --------------------------------------------------------------------- size the frame (CALI-40)
// whittle's FrameStudy treats each tube the part declares as a beam: stress, sag, what the hitch holds,
// and a slider from the frame as drawn to the lightest tubes that pass. Sizes come back into PARAMS.
function frameRuns(pid) { return (S.design.frame_runs || []).filter((r) => r.part === pid); }

function frameView(p) {
  if (!S.design.aero_available) return '<div class="empty">whittle isn\'t installed in Caliper\'s environment.</div>';
  const runs = frameRuns(p.id);
  // what it carries: the other parts as they're built (each piece where it sits), or a flat load (CALI-43)
  const built = S.design.parts.some((x) => x.id !== p.id && x.built && !x.framed);
  const layouts = Object.keys(p.layouts || {});
  const pick = Math.min(S.frameRun[p.id] || 0, Math.max(runs.length - 1, 0));
  return `<div class="form">
      <span>carries</span><select id="fFrom">
        ${built ? '<option value="design" selected>the design as built, where it sits</option>' : ''}
        <option value="flat">a flat load on the rails</option></select>
      <span id="fLoadLbl">${built ? 'payload on the floor' : 'box + gear'}</span>
      <span><input type="number" id="fLoad" value="100" min="0" step="10"> lb</span>
      ${S.design.parts.some((x) => x.shell) ? `<span>walls</span><label><input type="checkbox" id="fWalls" checked>
        the box's walls carry load too</label>` : ''}
      ${layouts.length ? `<span>layout</span><select id="fLayout"><option value="">as drawn</option>
        ${layouts.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join('')}</select>` : ''}
      <span>bumps</span><span>×<input type="number" id="fFactor" value="2.5" min="1" max="5" step="0.5"> when driving</span>
      <span>least safety</span><span><input type="number" id="fSafety" value="3.5" min="1" max="10" step="0.5"> ×</span>
    </div>
    <div class="actions"><button class="primary" id="fGo">Size it</button></div>
    <div id="fProgress"></div>
    ${runs.length ? frameResults(p, runs[pick], runs) : ''}
    ${(p.gussets || []).length ? gussetView(p) : ''}`;
}

// gusset plates (CALI-46): whittle's plate mode at the joints the frame names (GUSSETS) — a slider from a
// solid plate to the lightest that still holds, each cleaned for plasma; "Use these" writes PLATES.
function gussetView(p) {
  const run = (S.design.gusset_runs || []).find((r) => r.part === p.id);
  const file = (joint, i, ext) => `/api/designs/${S.slug}/gussets/${run.id}/${joint}/station_${String(i).padStart(2, '0')}.${ext}`;
  const t = run ? run.thickness : 3.175;
  return `<h5 style="margin:14px 0 4px">Gusset plates</h5>
    <div class="muted small">Cheek plates at ${p.gussets.map(esc).join(', ')}, carrying the frame's own corner loads; each design is cleaned for a plasma table.</div>
    <div class="form"><span>plate</span><select id="gThick">${[[3.175, '1/8 in'], [4.7625, '3/16 in'], [6.35, '1/4 in']].map(([v, l]) =>
      `<option value="${v}" ${Math.abs(v - t) < 0.01 ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
    <div class="actions"><button id="gGo">Size the gussets</button>${run ? ' <button class="primary" id="gUse">Use these plates</button>' : ''}</div>
    <div id="gProgress"></div>
    ${run ? Object.entries(run.joints).map(([name, j]) => `<div style="margin-top:8px"><b>${esc(name)}</b>
        <span class="muted small">${esc(j.members.join(' / '))} · ${run.plates} plates of ${(run.thickness / IN).toFixed(3).replace(/0+$/, '')} in</span>
        <div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:start">
          <a href="${file(name, j.pick, 'svg')}" target="_blank"><img src="${file(name, j.pick, 'svg')}" style="width:110px;background:#fff;border-radius:4px"></a>
          <table class="st"><tr><th>#</th><th>holes</th><th>kg each</th><th>safety</th><th>weld relief</th></tr>
            ${j.stations.map((st) => `<tr class="${st.index === j.pick ? 'on' : ''}"><td>${st.index}</td><td>${pct(st.removed)}</td><td>${st.mass_kg}</td>
              <td>${st.safety}x</td><td>${pct(st.relief)}</td></tr>`).join('')}</table></div>
        ${j.notes.map((n) => `<div class="muted small">• ${esc(n)}</div>`).join('')}</div>`).join('') : ''}`;
}

function wireGussets(p) {
  const go = $('gGo');
  if (go) go.onclick = async () => {
    const prog = $('gProgress');
    go.disabled = true;
    prog.innerHTML = '<div class="small muted" id="gMsg">sizing…</div>';
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/gussets`, {
        part: p.id, thickness: +$('gThick').value, payload_lb: $('fLoad') ? (+$('fLoad').value || 0) : 100,
        walls: $('fWalls') ? $('fWalls').checked : true });
      await follow(job_id, (ev) => { const m = $('gMsg'); if (m && ev.text && ev.kind !== 'started') m.textContent = ev.text; });
      await refresh();
    } catch (e) { prog.innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`; go.disabled = false; }
  };
  const use = $('gUse');
  if (use) use.onclick = async () => {
    const run = (S.design.gusset_runs || []).find((r) => r.part === p.id);
    use.disabled = true;
    try {
      const got = await api('POST', `/api/designs/${S.slug}/gussets/${run.id}/adopt`, { picks: {} });
      S.design = got.design; await refresh();
    } catch (e) { $('gProgress').innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`; use.disabled = false; }
  };
}

function frameLabel(r) {
  const what = r.carrying ? `${r.carrying.parts.map((x) => `${x.part} ${lbs(x.mass_lb)}`).join(' + ')}`
    + (r.walls ? ' · walls count' : '')
    + Object.entries(r.build || {}).map(([pid, b]) => ` · ${pid} ${Object.values(b).join(', ')}`).join('')
    : `${lbs(r.load_lb)} on ${(r.on_groups || []).join(', ')}`;
  return `${r.layout || (Object.keys(r.params || {}).length ? JSON.stringify(r.params) : 'as drawn')} · ${what}`;
}

function frameResults(p, run, runs) {
  const d = run.drawn, on = S.station && S.station.run === run.id ? S.station.index : -1;
  const groups = Object.keys(run.stations[0].design);
  const stand = (st) => st.receiver.standing, drive = (st) => st.receiver.driving;
  const c = run.carrying;
  const joint = (st) => (st.joints || [])[0];
  const best = run.stations.reduce((x, y) => (y.safety > x.safety ? y : x));
  return `<div class="small" style="margin-top:12px">${runs.length > 1 ? `<select id="fRun">${runs.map((r, k) =>
      `<option value="${k}" ${r.id === run.id ? 'selected' : ''}>${esc(frameLabel(r))}</option>`).join('')}</select>`
      : `<b>Last sizing</b> · ${esc(frameLabel(run))}`}</div>
    <div class="card" style="margin-top:8px">
      ${c ? `<div class="small" style="margin-bottom:6px">Carrying <b>${lbs(c.mass_lb)}</b> — ${c.parts.map((x) => `${esc(x.part)} ${lbs(x.mass_lb)}`).join(', ')} —
        each piece where it sits; the floor takes it sideways to the nearest tube (up to ${len(c.reach_in * IN, 1)} away).</div>` : ''}
      <b>As drawn</b>: ${d.mass_lb} lb of steel · weakest member <b>${d.safety}x</b> (${esc(d.governing.member)}, ${esc(d.governing.case)}) ·
      sags ${len(d.deflection_mm, 2)} at ×${run.factor}<br>
      <b>Your hitch holds</b>: ${stand(d).force_lb} lb and <b>${Number(stand(d).moment_lbin).toLocaleString()} lb·in</b> standing still,
      ${Number(drive(d).moment_lbin).toLocaleString()} lb·in on a ×${run.factor} bump.
      ${best.safety < run.min_safety ? `<div class="small" style="margin-top:4px;color:var(--bad)">No tubes in the catalog reach ${run.min_safety}x:
        the best is ${best.safety}x, held back by <b>${esc(best.governing.member)}</b> — that's the load and how far back it sits, not the layout.</div>` : ''}
      ${best.walls ? (() => { const w = best.walls.reduce((a, b) => (b.safety < a.safety ? b : a));
        return `<div class="small" style="margin-top:4px">The box's walls carry it to where it's fastened
          (${(c.fastened || []).length} fixings): weakest wall <b>${esc(w.name)}</b> ${w.safety}x
          (skin ${w.skin_safety}x, foam ${w.foam_safety}x)${best.fixing ? ` · a fixing carries up to <b>${lbs(best.fixing.force_lb)}</b> on a bump` : ''}.</div>`; })() : ''}
      ${joint(best) ? `<div class="small" style="margin-top:4px">Hardest-worked joint (design ${best.index}, on a bump): where ${esc(joint(best).members.join(', '))} meet —
        ${Number(joint(best).bending_lbin).toLocaleString()} lb·in of bending from ${esc(joint(best).worst_member)}: what a gusset there has to carry.</div>` : ''}
      <div class="muted small" style="margin-top:4px">Compare with your hitch's rating: tongue weight × the distance from the pin to
        the ball — e.g. 350 lb × ~7″ ≈ 2,450 lb·in for a typical Class II.</div></div>
    <div class="tw"><table class="st"><tr><th>#</th><th>steel lb</th><th>weakest</th><th>sag</th><th>hitch lb·in</th>
      ${groups.map((g) => `<th>${esc(g)}</th>`).join('')}</tr>
      ${run.stations.map((st) => `<tr class="pick ${st.index === on ? 'on' : ''}" data-fst="${st.index}"><td>${st.index}</td>
        <td>${st.mass_lb}</td><td>${st.safety}x</td><td>${len(st.deflection_mm, 2)}</td>
        <td>${Number(stand(st).moment_lbin).toLocaleString()}</td>
        ${groups.map((g) => `<td>${esc(st.design[g])}</td>`).join('')}</tr>`).join('')}</table></div>
    <div class="muted small" style="margin-top:6px">Click a row to see that frame in place. Sizes are inches (2x2x1/8 = 2″ square, ⅛″ wall).
      The plywood and the foam walls bonded to it stiffen the platform too; the study leaves them out, so it's on the safe side.</div>
    ${[...(d.notes || []), ...(run.note ? run.note.split('\n') : []), ...((c && c.notes) || [])].filter(Boolean)
      .map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`;
}

function wireFrame(p) {
  const go = $('fGo');
  if (go) go.onclick = () => runFrame(p);
  wireGussets(p);
  const from = $('fFrom');
  if (from) from.onchange = () => { $('fLoadLbl').textContent = from.value === 'design' ? 'payload on the floor' : 'box + gear'; };
  const sel = $('fRun');
  if (sel) sel.onchange = () => { S.frameRun[p.id] = +sel.value; clearStation(); renderInspector(); };
  document.querySelectorAll('#inspector tr[data-fst]').forEach((tr) => {
    const runs = frameRuns(p.id);
    tr.onclick = () => showStation(p.id, runs[Math.min(S.frameRun[p.id] || 0, runs.length - 1)], +tr.dataset.fst);
  });
}

async function runFrame(p) {
  const prog = $('fProgress'), go = $('fGo');
  go.disabled = true;
  prog.innerHTML = '<div class="small muted" id="fMsg">sizing…</div>';
  const design = $('fFrom') && $('fFrom').value === 'design';
  const layout = $('fLayout') ? $('fLayout').value : '';
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/frame-study`, {
      part: p.id, factor: +$('fFactor').value || 2.5, min_safety: +$('fSafety').value || 3.5,
      from_design: design, payload_lb: +$('fLoad').value || 0, load_lb: +$('fLoad').value || 100,
      walls: $('fWalls') ? $('fWalls').checked : true,
      params: layout ? p.layouts[layout] : {},
    });
    await follow(job_id, (ev) => { const m = $('fMsg'); if (m && ev.text && ev.kind !== 'started') m.textContent = ev.text; });
    S.frameRun[p.id] = 0;
    await refresh();
  } catch (e) {
    prog.innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`;
    go.disabled = false;
  }
}

// ------------------------------------------------------------- shape it for drag (CALI-39)
// whittle searches the numbers in the part's PARAMS; a design comes back as numbers written into the
// script, so the part stays parametric. The carving study below it returns a mesh instead.
const MAKE_TUNABLE = 'Restructure this part\'s script so every key dimension lives in a module-level PARAMS ' +
  'dict (mm), and add tail_len, tail_drop, tail_pinch and tail_edge_r, all 0 so the shape does not change: ' +
  'tail_len is how much of the back tapers, tail_drop how far the top falls by the very back, tail_pinch how ' +
  'far each side draws in by the very back, tail_edge_r the rounding of the back\'s top and side edges ' +
  '(0 = sharp). Build the taper as flat panels (a ruled loft) and keep the bottom flat.';

function aeroRuns(pid) { return (S.design.aero_runs || []).filter((r) => r.part === pid); }

function aeroView(p) {
  if (!S.design.aero_available) {
    return '<div class="empty">whittle\'s parametric search isn\'t installed in Caliper\'s environment.</div>';
  }
  if (!p.scripted) return '<div class="empty">This part is a mesh right now — say <b>roll it back</b> to get its script back.</div>';
  if (!p.params || !Object.keys(p.params).length) {
    return `<div class="empty">Its script doesn't keep its dimensions in <code>PARAMS</code> yet, so there's
      nothing for whittle to vary.</div>
      <div class="actions"><button id="aTunable">Make it tunable</button></div>`;
  }
  const mph = inches();
  const behind = S.design.parts.filter((x) => x.id !== p.id && x.role === 'fixed');
  const rows = Object.entries(p.params).map(([k, v]) => {
    const sg = (p.suggest || {})[k] || { search: false, bounds: [v, v] };
    return `<tr><td><label><input type="checkbox" class="aOn" data-k="${esc(k)}" ${sg.search ? 'checked' : ''}> ${esc(k)}</label></td>
      <td>${fixed(v, 1)}</td>
      <td><input type="number" class="aLo" data-k="${esc(k)}" value="${sg.bounds[0]}" step="any" style="width:70px"></td>
      <td><input type="number" class="aHi" data-k="${esc(k)}" value="${sg.bounds[1]}" step="any" style="width:70px"></td></tr>`;
  }).join('');
  const runs = aeroRuns(p.id);
  const own = Object.values(p.suggest || {}).some((sg) => sg.from === 'part');
  return `<div class="tw"><table class="st"><tr><th>search</th><th>now</th><th>from</th><th>to</th></tr>${rows}</table></div>
    <div class="muted small" style="margin:4px 0 8px">Values in mm (or degrees). The current value must sit inside its range.
      ${own ? 'Ticked ranges are the part’s own (its <code>RANGES</code>).' : ''}
      ${p.keeps ? 'What it has to hold (its <code>keeps()</code> — the pale slab when you open <b>Built from</b>) is kept clear whatever the search tries.' : ''}</div>
    <div class="form">
      ${behind.length ? `<span>rides behind</span><span>${behind.map((b) => `<label><input type="checkbox" class="aObs" value="${esc(b.id)}" checked> ${esc(b.id)}</label>`).join(' ')}</span>` : ''}
      <span>${mph ? 'speed (mph)' : 'speed (km/h)'}</span><input type="number" id="aSpeed" value="${mph ? 65 : 105}" min="5" max="200">
      <span>give up at most</span><span><input type="number" id="aBudget" value="15" min="1" max="60"> % of the volume</span>
      <span>protect interior</span><span><input type="number" id="aKeep" placeholder="none" min="0" step="0.5"> ${mph ? 'in' : 'mm'} inset</span>
      <span>designs</span><input type="number" id="aStations" value="4" min="2" max="8">
      <span>search</span><select id="aEffort"><option value="0.3">quick</option><option value="0.6" selected>normal</option><option value="1">thorough</option></select>
    </div>
    <div class="actions"><button class="primary" id="aGo">Shape it</button></div>
    <div id="aProgress"></div>
    ${runs.length ? aeroResults(p, runs[Math.min(S.aeroRun[p.id] || 0, runs.length - 1)], runs) : ''}`;
}

// what a run varied, in words: comparing "straight panels" with "curve free" is the point of a re-run
function aeroLabel(r) {
  const held = Object.entries(r.start || {}).filter(([k]) => /curve/.test(k) && !r.searched.includes(k));
  const shape = r.searched.some((k) => /curve/.test(k)) ? 'curve free'
    : held.length ? `curve held at ${held.map(([, v]) => +v).join('/')}` : 'searched';
  return `${shape} · ${r.searched.length} numbers · ${r.builds} builds`;
}

function aeroResults(p, run, runs) {
  const on = S.station && S.station.run === run.id ? S.station.index : -1;
  const saved = (s) => s.derived ? fixed(inches() ? s.derived.saved_lbf : s.derived.saved_n, 1) : '—';
  return `<div class="small" style="margin-top:12px">
      ${runs.length > 1 ? `<select id="aRun">${runs.map((r, k) => `<option value="${k}" ${r.id === run.id ? 'selected' : ''}>
        ${esc(aeroLabel(r))}</option>`).join('')}</select>` : `<b>Last search</b> · ${esc(aeroLabel(run))}`}
      · ${run.seconds}s${run.obstacles && run.obstacles.length ? ' · behind ' + esc(run.obstacles.join(', ')) : ' · free air'}</div>
    <div class="tw"><table class="st"><tr><th>#</th><th>volume</th><th>drag</th><th>${inches() ? 'saved lbf' : 'saved N'}</th><th>kWh/100mi</th>
      ${run.searched.map((k) => `<th>${esc(k)}</th>`).join('')}</tr>
      ${run.stations.map((s) => `<tr class="pick ${s.index === on ? 'on' : ''}" data-ast="${s.index}"><td>${s.index}</td>
        <td>${pct(-s.removed)}</td><td>${pct(s.metrics.drag)}</td><td>${saved(s)}</td>
        <td>${s.derived ? fixed(s.derived.saved_kwh_per_100mi, 2) : '—'}</td>
        ${run.searched.map((k) => `<td>${fixed(s.design[k], 0)}</td>`).join('')}</tr>`).join('')}</table></div>
    <div class="muted small" style="margin-top:6px">Click a row to see it in place; “volume” is the change against the part as it stands.
      Using a design writes those numbers into the script — it stays parametric.</div>
    ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`;
}

function wireAero(p) {
  const tun = $('aTunable');
  if (tun) tun.onclick = () => send(MAKE_TUNABLE, p.id);
  const go = $('aGo');
  if (go) go.onclick = () => runAero(p);
  const sel = $('aRun');
  if (sel) sel.onchange = () => { S.aeroRun[p.id] = +sel.value; clearStation(); renderInspector(); };
  document.querySelectorAll('#inspector tr[data-ast]').forEach((tr) => {
    const runs = aeroRuns(p.id);
    tr.onclick = () => showStation(p.id, runs[Math.min(S.aeroRun[p.id] || 0, runs.length - 1)], +tr.dataset.ast);
  });
}

async function runAero(p) {
  const bounds = {};
  for (const cb of document.querySelectorAll('.aOn:checked')) {
    const k = cb.dataset.k;
    bounds[k] = [+document.querySelector(`.aLo[data-k="${k}"]`).value, +document.querySelector(`.aHi[data-k="${k}"]`).value];
  }
  const prog = $('aProgress'), go = $('aGo');
  if (!Object.keys(bounds).length) { prog.innerHTML = '<div class="small" style="color:var(--bad)">Tick at least one number to search.</div>'; return; }
  const mph = inches();
  const speed = +$('aSpeed').value || 65;
  const keep = $('aKeep').value === '' ? null : (+$('aKeep').value) * (mph ? IN : 1);
  const body = {
    part: p.id, bounds, obstacles: [...document.querySelectorAll('.aObs:checked')].map((c) => c.value),
    speed_kmh: mph ? speed * 1.609344 : speed, remove_up_to: (+$('aBudget').value || 15) / 100,
    keep_inset_mm: keep, stations: +$('aStations').value || 4, effort: +$('aEffort').value,
  };
  go.disabled = true;
  prog.innerHTML = '<div class="bar"><i></i></div><div class="small muted" id="aMsg">starting…</div>';
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/aero`, body);
    S.aeroRun[p.id] = 0;
    await follow(job_id, (ev) => {
      const msg = $('aMsg'), bar = prog.querySelector('.bar > i');
      if (ev.text && msg && ev.kind !== 'started' && ev.kind !== 'finished') msg.textContent = ev.text;
      if (bar && typeof ev.progress === 'number') bar.style.width = `${Math.round(ev.progress * 100)}%`;
    });
    await refresh();
  } catch (e) {
    prog.innerHTML = `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(e.message)}</div>`;
    go.disabled = false;
  }
}

// --------------------------------------------------------------------------------- whittle
function runsFor(pid) { return (S.design.whittle_runs || []).filter((r) => r.part === pid); }

function whittleView(p) {
  if (!S.whittle.ok) {
    return `<div class="empty">whittle isn't reachable${S.whittle.error ? ' — ' + esc(S.whittle.error) : ''}.
      Start it with <code>python -m whittle.gui</code> in the whittle repo.</div>`;
  }
  // something marked as a reference (the car) means this part probably rides behind it
  const behind = S.design.parts.some((x) => x.id !== p.id && x.role === 'fixed');
  const mph = inches();
  const runs = runsFor(p.id);
  return `<div class="form">
      <span>study</span><select id="wKind"><option value="flow">airflow — carve for drag</option>
        <option value="dual">airflow + load — carve and lighten</option></select>
      <span>${mph ? 'speed (mph)' : 'speed (km/h)'}</span><input type="number" id="wSpeed" value="${mph ? 65 : 105}" min="5" max="200">
      <span>remove up to</span><span><input type="number" id="wBudget" value="20" min="2" max="60"> % of the part</span>
      <span>protect interior</span><span><input type="number" id="wKeep" placeholder="none" min="0" step="0.5"> ${mph ? 'in' : 'mm'} inset</span>
      <span>stations</span><input type="number" id="wStations" value="6" min="2" max="12">
      <span class="dualonly" hidden>cargo</span><span class="dualonly" hidden><input type="number" id="wCargo" value="0" min="0"> kg</span>
      <span>carve</span><select id="wCarve">
        <option value="tail" ${behind ? 'selected' : ''}>the tail only — it rides behind something</option>
        <option value="anywhere" ${behind ? '' : 'selected'}>anywhere — free air</option></select>
      <span class="full muted small">Air moves −X (the car drives +X). Kept symmetric left/right; the bottom stays flat.
        Behind a car the front sits in its wake, which whittle can't model yet — so carving the front
        would chase drag that isn't there.</span>
    </div>
    <div class="actions"><button class="primary" id="wGo">Send to whittle</button></div>
    <div id="wProgress"></div>
    ${runs.length ? whittleResults(p, runs) : ''}`;
}

function whittleResults(p, runs) {
  const i = Math.min(S.runIndex[p.id] || 0, runs.length - 1);
  const run = runs[i];
  const flow = run.kind === 'flow';
  const cols = flow
    ? [['removed', (s) => pct(s.removed_part)], ['drag', (s) => pct(s.metrics.drag)],
      ['Cd', (s) => fixed(s.metrics.cd, 3)],
      [inches() ? 'saved lbf' : 'saved N', (s) => s.derived ? fixed(inches() ? s.derived.saved_lbf : s.derived.saved_n, 1) : '—'],
      ['kWh/100mi', (s) => s.derived ? fixed(s.derived.saved_kwh_per_100mi, 2) : '—']]
    : [['removed', (s) => pct(s.removed_part)],
      ...run.columns.map((c) => [c.label, (s) => (s.metrics[c.key] == null ? '—'
        : c.format.includes('%') ? pct(s.metrics[c.key]) : fixed(s.metrics[c.key], 2))])];
  const on = S.station && S.station.run === run.id ? S.station.index : -1;
  return `<div class="small" style="margin-top:12px">
      ${runs.length > 1 ? `<select id="wRun">${runs.map((r, k) => `<option value="${k}" ${k === i ? 'selected' : ''}>
        ${esc(r.id)} · ${esc(r.kind)} · ${r.carve === 'tail' ? 'tail only' : 'free air'}</option>`).join('')}</select>`
      : `<b>${esc(run.kind)} study</b> · ${run.carve === 'tail' ? 'tail only' : 'free air'}`}
    </div>
    <div class="tw"><table class="st"><tr><th>#</th>${cols.map((c) => `<th>${esc(c[0])}</th>`).join('')}</tr>
      ${run.stations.map((s) => `<tr class="pick ${s.index === on ? 'on' : ''}" data-st="${s.index}"><td>${s.index}</td>
        ${cols.map((c) => `<td>${c[1](s)}</td>`).join('')}</tr>`).join('')}</table></div>
    <div class="muted small" style="margin-top:6px">Click a row to see that shape in place.
      “removed” is measured against your part as built (negative = whittle's remesh came back bigger).
      ${flow ? 'Savings are against the starting shape, at the study speed.' : ''}</div>
    ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`;
}

function wireWhittle(p) {
  const kind = $('wKind');
  if (kind) kind.onchange = () => document.querySelectorAll('.dualonly').forEach((n) => { n.hidden = kind.value !== 'dual'; });
  const go = $('wGo');
  if (go) go.onclick = () => runWhittle(p);
  const sel = $('wRun');
  if (sel) sel.onchange = () => { S.runIndex[p.id] = +sel.value; clearStation(); renderInspector(); };
  document.querySelectorAll('#inspector tr[data-st]').forEach((tr) => {
    tr.onclick = () => {
      const runs = runsFor(p.id);
      const run = runs[Math.min(S.runIndex[p.id] || 0, runs.length - 1)];
      showStation(p.id, run, +tr.dataset.st);
    };
  });
}

async function runWhittle(p) {
  const mph = inches();
  const speed = +$('wSpeed').value || 65;
  const keep = $('wKeep').value === '' ? null : (+$('wKeep').value) * (mph ? IN : 1);
  const body = {
    part: p.id, kind: $('wKind').value,
    speed_kmh: mph ? speed * 1.609344 : speed,
    remove_up_to: (+$('wBudget').value || 20) / 100,
    keep_inset_mm: keep, stations: +$('wStations').value || 6,
    cargo_kg: +($('wCargo') && $('wCargo').value) || 0,
    carve: $('wCarve').value,
  };
  const prog = $('wProgress'), go = $('wGo');
  go.disabled = true;
  prog.innerHTML = '<div class="bar"><i></i></div><div class="small muted" id="wMsg">sending…</div>';
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/whittle`, body);
    await follow(job_id, (ev) => {
      const msg = $('wMsg'), bar = prog.querySelector('.bar > i');
      if (ev.text && msg) msg.textContent = ev.text;
      if (bar && typeof ev.progress === 'number') bar.style.width = `${Math.round(ev.progress * 100)}%`;
      if (bar && ev.kind === 'fetching') bar.style.width = '100%';
    });
    S.runIndex[p.id] = 0;
    await refresh();
  } catch (e) {
    prog.innerHTML = `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(e.message)}</div>`;
    go.disabled = false;
  }
}

// show a station in place of its part, with the part's current shape as a ghost around it
const STUDY_PATH = { parametric: 'aero', frame: 'frame-study' };
async function showStation(pid, run, index) {
  const parametric = run.kind === 'parametric', framed = run.kind === 'frame';
  try {
    const r = await fetch(`/api/designs/${S.slug}/${STUDY_PATH[run.kind] || 'whittle'}/${run.id}/stations/${index}.stl`);
    if (!r.ok) throw new Error(`station ${index}: HTTP ${r.status}`);
    const geom = loader.parse(await r.arrayBuffer());
    geom.computeVertexNormals();
    clearStation(true);
    stationMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: 0xffb454, roughness: 0.55, metalness: 0.05 }));
    const ghost = meshes.get(pid);
    if (ghost) {
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(ghost.geometry, 25),
        new THREE.LineBasicMaterial({ color: 0x4ea1ff, transparent: true, opacity: 0.55 }));
      stationMesh.add(edges);
    }
    scene.add(stationMesh);
    S.station = { part: pid, run: run.id, index };
    const st = run.stations.find((s) => s.index === index) || {};
    const bar = $('stationBar');
    bar.hidden = false;
    const removed = parametric ? st.removed : st.removed_part;
    const what = framed
      ? `<span>design <b>${index}</b> · ${st.mass_lb} lb of steel · weakest ${st.safety}x · sags ${len(st.deflection_mm, 2)}</span>`
      : `<span>${parametric ? 'design' : 'whittle station'} <b>${index}</b> · gives up ${pct(removed)} of the volume
      ${st.metrics && st.metrics.drag != null ? ` · drag ${pct(st.metrics.drag)}` : ''}</span>`;
    bar.innerHTML = `${what}
      <button class="primary" id="adoptBtn">${framed ? 'Use these sizes for ' : parametric ? 'Use these numbers for ' : 'Bring this back as '}${esc(pid)}</button>
      <button id="stationClose" class="ghost">×</button>`;
    $('stationClose').onclick = () => { clearStation(); renderInspector(); };
    $('adoptBtn').onclick = () => adoptStation(pid, run.id, index, run.kind);
    paint(); renderInspector();
  } catch (e) { showErr(e.message); }
}
function clearStation(keepBar) {
  if (stationMesh) { scene.remove(stationMesh); stationMesh.geometry.dispose(); stationMesh = null; }
  S.station = null;
  if (!keepBar) $('stationBar').hidden = true;
  if (S.design) paint();
}
async function adoptStation(pid, wid, index, kind) {
  $('adoptBtn').disabled = true;
  try {
    await api('POST', `/api/designs/${S.slug}/${STUDY_PATH[kind] || 'whittle'}/${wid}/adopt`, { station: index });
    clearStation();
    await refresh();
  } catch (e) { showErr(e.message); $('adoptBtn').disabled = false; }
}

// ------------------------------------------------------------------------------------ boot
async function checkWhittle() {
  const was = S.whittle.ok;
  try {
    S.whittle = await api('GET', '/api/whittle/health');
  } catch (e) { S.whittle = { ok: false, error: e.message }; }
  const dot = $('whittleDot');
  dot.className = 'dot ' + (S.whittle.ok ? 'ok' : 'bad');
  dot.title = S.whittle.ok ? `whittle is running at ${S.whittle.url}` : (S.whittle.error || 'whittle is not reachable');
  // redraw only when whittle came up or went down — a periodic redraw would wipe a half-filled form
  if (was !== S.whittle.ok && S.scope && !document.querySelector('#wProgress .bar, #aProgress .bar')) renderInspector();
}
checkWhittle();
setInterval(checkWhittle, 15000);
window.__design = S;            // debug seam (like the classic page's window.__asm)
loadDesigns().catch((e) => showErr(e.message));
