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
  aeroRun: {},         // part id -> which parametric study the inspector shows
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
    <h4>Design checks</h4>
    ${checks(rep)}`;
}

function historyItem(h) {
  if (h.kind === 'revision') {
    const what = h.action === 'aero' ? `shaped for drag — station ${h.station}`
      : h.action === 'whittle' ? `from whittle${h.station != null ? ' — station ' + h.station : ''}`
      : h.action === 'restore' ? `rolled back to v${h.restored_from}` : h.action;
    return `<li class="hist"><span class="v">v${h.version}</span>${esc(what)}
      ${h.feedback && h.action !== 'author' ? `<div>“${esc(h.feedback)}”</div>` : ''}
      ${h.result ? `<span class="badge ${h.result === 'all_pass' ? 'ok' : 'bad'}">${h.result === 'all_pass' ? 'passed' : 'failing'}</span>` : ''}</li>`;
  }
  if (h.kind === 'assertion') {
    return `<li class="hist">${h.action === 'promoted' ? '🔒 locked in' : 'declined'} <code>${esc(h.expr || h.id)}</code></li>`;
  }
  if (h.kind === 'whittle') return `<li class="hist">studied in whittle (${esc(h.study)}, ${h.stations} stations)</li>`;
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
    <h4>Shape it for drag <span class="badge">numbers back</span></h4>
    <div id="aeroBox">${aeroView(p)}</div>
    <h4>whittle carving <span class="badge">mesh back</span></h4>
    <div id="whittleBox">${whittleView(p)}</div>
    <h4>History</h4>
    <ul class="list">${p.history.slice().reverse().map(historyItem).join('')}</ul>
    <details id="adv"><summary>Advanced — script &amp; spec</summary><div id="advBody" class="small muted">loading…</div></details>`;
}

function wireInspector(p) {
  document.querySelectorAll('#inspector [data-part]').forEach((a) => { a.onclick = () => setScope(a.dataset.part); });
  if (!p) return;
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
  return `<div class="tw"><table class="st"><tr><th>search</th><th>now</th><th>from</th><th>to</th></tr>${rows}</table></div>
    <div class="muted small" style="margin:4px 0 8px">Values in mm (or degrees). The current value must sit inside its range.</div>
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
async function showStation(pid, run, index) {
  const parametric = run.kind === 'parametric';
  try {
    const r = await fetch(`/api/designs/${S.slug}/${parametric ? 'aero' : 'whittle'}/${run.id}/stations/${index}.stl`);
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
    bar.innerHTML = `<span>${parametric ? 'design' : 'whittle station'} <b>${index}</b> · gives up ${pct(removed)} of the volume
      ${st.metrics && st.metrics.drag != null ? ` · drag ${pct(st.metrics.drag)}` : ''}</span>
      <button class="primary" id="adoptBtn">${parametric ? 'Use these numbers for ' : 'Bring this back as '}${esc(pid)}</button>
      <button id="stationClose" class="ghost">×</button>`;
    $('stationClose').onclick = () => { clearStation(); renderInspector(); };
    $('adoptBtn').onclick = () => adoptStation(pid, run.id, index, parametric);
    paint(); renderInspector();
  } catch (e) { showErr(e.message); }
}
function clearStation(keepBar) {
  if (stationMesh) { scene.remove(stationMesh); stationMesh.geometry.dispose(); stationMesh = null; }
  S.station = null;
  if (!keepBar) $('stationBar').hidden = true;
  if (S.design) paint();
}
async function adoptStation(pid, wid, index, parametric) {
  $('adoptBtn').disabled = true;
  try {
    await api('POST', `/api/designs/${S.slug}/${parametric ? 'aero' : 'whittle'}/${wid}/adopt`, { station: index });
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
