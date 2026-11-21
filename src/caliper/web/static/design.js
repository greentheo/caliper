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
  running: {},         // a load check, Lighten or step being taken, by kind, design and part (#159, #175)
  tracked: {},         // job id -> the long job this page is following, whichever way it found it (#178)
  opening: null,       // the design on its way, while it loads (#173)
  scope: null,         // the selected part (the chat is about it), or null = the whole design
  pick: null,          // a face, edge or point picked on it (#109): { part, kind, id, said, local }
  busy: false,         // a turn is in flight
  station: null,       // {run, index} when previewing a whittle station in the viewport
  whittle: { ok: false },
  runIndex: {},        // part id -> which whittle run the inspector shows
  aeroRun: {}, frameRun: {},         // part id -> which parametric study the inspector shows
  loadRun: {},         // part id -> which strength check the inspector shows (CALI-54)
  making: {},          // part id -> {key, data}: how it's made in your shop (CALI-48)
  carveJob: {},        // design and part (carveKey) -> the carve running for it (#175: part ids repeat across designs): {job, text, progress, ...}; a redraw keeps it (CALI-101)
  shop: null, shopOpen: false, shopKey: 0,
  studies: false,      // the studies page is open (CALI-70)
  built: {},           // part id -> {version, tried, report, balance}: what it's built from (CALI-41)
  balance: null,       // {key, data}: the whole design's weight and what the hitch carries
  payload: 0,          // lb of gear or people on the floor, for the balance
};
// S.design only ever holds the open design: an answer for one that's no longer open is dropped, whichever call brought it (#168)
function guardDesign(state) {
  let open = state.design;
  Object.defineProperty(state, 'design', { enumerable: true, get: () => open,
    set: (d) => { if (!d || !d.slug || d.slug === state.slug) open = d; } });
}
guardDesign(S);

// ------------------------------------------------------------------------------------------ api
async function api(method, url, body) {
  const r = await fetch(url, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`, errorId = '';
    try { const j = await r.json(); msg = j.detail || j.error || msg; errorId = j.error_id || ''; } catch (e) { /* not JSON */ }
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    err.status = r.status;                       // what kind of no it was: a 422 is the part's (#331 review)
    if (errorId) { err.errorId = errorId; (window.__errIds = window.__errIds || {})[err.message] = errorId; }   // a crash the server kept (CALI-59)
    // a 409 is a refusal the server meant, not a bug: it shows as a plain line with no Report it (#70 item 24)
    if (r.status === 409) { err.refused = true; (window.__refused = window.__refused || {})[err.message] = true; }
    throw err;
  }
  return r.json();
}

// ------------------------------------------------------------------------- reporting it (CALI-59)
// What broke is kept on this machine. A report is shown in full first; sending it opens a new GitHub issue
// in the browser with it filled in, so the person sends it themselves. Nothing is sent on its own.
async function reportError(errorId, message) {
  try {
    // where on the page, never which design: its name is the person's own words
    const where = shownPart() ? "a part's cards" : (S.slug ? 'a design' : 'the welcome');
    if (!errorId) errorId = (await api('POST', '/api/errors', { where, error: message || 'something broke' })).id;
    const rep = await api('GET', `/api/errors/report?id=${encodeURIComponent(errorId)}`);
    let dlg = $('reportDlg');
    if (!dlg) { dlg = document.createElement('dialog'); dlg.id = 'reportDlg'; dlg.className = 'report'; document.body.append(dlg); }
    dlg.innerHTML = `<h3>Report what broke</h3>
      <p class="small">Nothing has been sent. This is everything the report holds: what broke, where, and which
        Caliper and computer it was. It doesn't name your design. The error's own words can quote what you typed or
        name a part, so read it before you send it. Add what you were doing if you like.</p>
      <textarea id="reportBody" rows="12">${esc(rep.body)}</textarea>
      <div class="actions"><button class="primary" id="reportSend">Open it as a GitHub issue</button>
        <button id="reportCopy">Copy</button><button class="ghost" id="reportClose">Not now</button></div>
      <p class="muted small">Sending opens github.com in your browser with the report filled in; you press
        Submit there (it needs a GitHub account).</p>`;
    $('reportClose').onclick = () => dlg.close();
    $('reportCopy').onclick = async () => {
      try { await navigator.clipboard.writeText($('reportBody').value); $('reportCopy').textContent = 'Copied'; }
      catch (e) { $('reportBody').select(); }
    };
    $('reportSend').onclick = () => {
      const body = trimReport($('reportBody').value, 6500);
      const url = rep.url.split('&body=')[0] + '&body=' + encodeURIComponent(body);
      window.open(url, '_blank', 'noopener'); dlg.close();
    };
    dlg.showModal();
  } catch (e) { showErr('couldn\'t make the report: ' + e.message); }
}
// a report too long for a link: as the server cuts one (errors.report), the trace from its start, because its last
// line is the one that failed, with the fence left closed; only then the words from the end (CALI-92, #70 item 16)
function trimReport(body, most) {
  const m = /^([\s\S]*?```\n)([\s\S]*)(\n```[\s\S]*)$/.exec(body);
  if (m) {
    let trace = m[2];
    while (encodeURIComponent(m[1] + trace + m[3]).length > most && trace.length > 1) {
      trace = '…' + trace.slice(Math.max(2, Math.floor(trace.length / 4)));
    }
    body = m[1] + trace + m[3];
  }
  while (encodeURIComponent(body).length > most) body = `${body.slice(0, Math.floor(body.length * 0.9))}…`;
  return body;
}
function reportLink(errorId, message) {
  const b = document.createElement('button');
  b.className = 'linkish'; b.textContent = 'Report it…';
  b.onclick = () => reportError(errorId, message);
  return b;
}
$('errbar').addEventListener('click', (e) => {
  if (e.target.dataset.report === undefined) return;
  const last = (window.__err || []).slice(-1)[0] || '';
  reportError((window.__errIds || {})[last] || '', last);
});

// Follow a job: Server-Sent Events, de-duplicated by sequence number, falling back to polling if the
// stream drops (a browser reconnect would otherwise replay events from the start).
function follow(jobId, onEvent) {
  return new Promise((resolve, reject) => {
    let seen = -1, done = false, es = null;
    const finish = (p) => {
      if (done) return; done = true; if (es) es.close();
      p.status === 'done' ? resolve(p.result)
        : reject(Object.assign(new Error(plainly(p.error) || (p.status === 'cancelled' ? 'cancelled' : 'the job failed')),
          { errorId: p.error_id || '', status: p.status }));
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
          if (j.status === 'done' || j.status === 'error' || j.status === 'cancelled') return finish(j);
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
// a wall or a voxel, thin: inches to the nearest 1/32 (5/32″), mm where that rounds to nothing; never "0.0″" (CALI-97)
function wallLen(mm) {
  if (mm == null || isNaN(mm)) return '—';
  // walls (and voxels) in mm, whatever the design's units (#139 review); under 1 mm, two places (#137 item 2)
  return `${mm < 1 ? +mm.toFixed(2) : mm < 10 ? +mm.toFixed(1) : Math.round(mm)} mm`;
}
const gcd = (a, b) => (b ? gcd(b, a % b) : a);
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
    .replace(/(^|[\s(])_((?:[^_\n]|(?<=\w)_(?=\w))+)_(?=[\s.,;:)!?]|$)/g, '$1<i>$2</i>')
    .replace(/\n/g, '<br>');
}
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const fixed = (v, d) => (v == null ? '—' : Number(v).toFixed(d));

// ------------------------------------------------------------- the part tree (#94, the mockup Theo approved)
// Every part and its pieces: a colour by material (the legend), an eye, click to select, double-click to rename.
// What's hidden is this viewer's: kept in the browser, per design, and still in every check.
const TREE = { slug: undefined, parts: new Set(), pieces: new Set(), open: true, oneBody: false, rename: null, last: null,
  waiting: new Set(), missed: {} };   // the designs with a move still waiting, and a move that failed while away, by slug (#251)
const WAITING = 'Waiting for the job on this design to finish…';
const pieceId = (pid, key) => `${pid}/${key}`;
function seen() {
  if (TREE.slug !== S.slug) {
    TREE.slug = S.slug;
    let kept = {};
    try { kept = JSON.parse(localStorage.getItem(`caliper-tree:${S.slug}`)) || {}; } catch (e) { /* none, or none allowed */ }
    TREE.parts = new Set(kept.parts || []); TREE.pieces = new Set(kept.pieces || []);
    TREE.open = kept.open !== false; TREE.oneBody = !!kept.oneBody; TREE.rename = null;
    TREE.saying = TREE.waiting.has(S.slug) ? WAITING : null;   // another design's wait isn't this one's; its own still is (#206, #251)
    TREE.drag = null;
  }
  return TREE;
}
function keepTree() {
  try {
    localStorage.setItem(`caliper-tree:${S.slug}`, JSON.stringify({ parts: [...TREE.parts], pieces: [...TREE.pieces],
      open: TREE.open, oneBody: TREE.oneBody }));
  } catch (e) { /* the tree still works for this visit */ }
}
function isHidden(pid, key) {
  const t = seen();
  return t.parts.has(pid) || (key != null && t.pieces.has(pieceId(pid, key)));
}
const EYE_ON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
const EYE_OFF = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 3l18 18"></path><path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.9 8.3 2 12 2 12s3.5 7 10 7c1.8 0 3.4-.5 4.8-1.2"></path></svg>';
function renameRow(part, key, draft) {
  return `<div class="trename"><input id="treeName" aria-label="New name" value="${esc(draft)}" maxlength="60" data-rename-input="1">
    <button class="primary" data-rename-save="1" data-part="${esc(part)}"${key != null ? ` data-key="${esc(key)}"` : ''}>Rename</button></div>`;
}
// the parts as the tree shows them (#94, slice b): [{ p, depth }], each followed by what sits under it. Display only
function treeRows(design) {
  const lay = design.tree || {}, ids = design.parts.map((p) => p.id), parent = lay.parent || {};
  const saved = (lay.order || []).filter((i) => ids.includes(i));
  const order = saved.concat(ids.filter((i) => !saved.includes(i)));
  const out = [];
  const walk = (id, depth) => {
    out.push({ p: design.parts.find((x) => x.id === id), depth });
    order.filter((k) => parent[k] === id).forEach((k) => walk(k, depth + 1));
  };
  order.filter((k) => !ids.includes(parent[k])).forEach((k) => walk(k, 0));
  return out;
}
function underPart(design, id) {           // everything that sits under a part, however deep
  const parent = (design.tree || {}).parent || {};
  return design.parts.map((p) => p.id).filter((k) => { for (let at = parent[k]; at; at = parent[at]) if (at === id) return true; return false; });
}
// where a drop puts a part: before or after another, at that part's level, or into it. null if it's nowhere new (itself, or inside itself)
function dropped(design, drag, target, zone) {
  if (drag === target || underPart(design, drag).includes(target)) return null;
  const lay = design.tree || {}, ids = design.parts.map((p) => p.id);
  const parent = { ...(lay.parent || {}) };
  const saved = (lay.order || []).filter((i) => ids.includes(i));
  const order = saved.concat(ids.filter((i) => !saved.includes(i))).filter((i) => i !== drag);
  order.splice(order.indexOf(target) + (zone === 'before' ? 0 : 1), 0, drag);
  if (zone === 'into') parent[drag] = target;
  else if (parent[target]) parent[drag] = parent[target];
  else delete parent[drag];
  return { order, parent };
}
function dropZone(e, row) {
  const box = row.getBoundingClientRect(), y = (e.clientY - box.top) / (box.height || 1);
  return y < 0.3 ? 'before' : y > 0.7 ? 'after' : 'into';
}
// a part moved one step without a mouse, by its keys or its menu (#94): up or down past the part beside it, in under the part
// above it (as that part's last), or out of the part it sits under (to just after it). A drop the drag already makes, as
// [target, zone] for moveInTree; null where there's nowhere to go
function nudge(design, id, dir) {
  const parent = (design.tree || {}).parent || {}, ids = design.parts.map((p) => p.id);
  const over = (k) => (ids.includes(parent[k]) ? parent[k] : null);
  const rows = treeRows(design).map((r) => r.p.id), up = over(id);
  const level = rows.filter((k) => over(k) === up), at = level.indexOf(id);
  const before = level[at - 1], after = level[at + 1];
  if (dir === 'up') return before ? [before, 'before'] : null;
  if (dir === 'down') return after ? [after, 'after'] : null;
  if (dir === 'in') {
    if (!before) return null;
    const own = rows.filter((k) => over(k) === before);
    return own.length ? [own[own.length - 1], 'after'] : [before, 'into'];
  }
  if (dir === 'out') return up ? [up, 'after'] : null;
  return null;
}
const TREE_KEYS = { ArrowUp: 'up', ArrowDown: 'down', ArrowRight: 'in', ArrowLeft: 'out' };
// what a move by the keys or the menu says, in the page's status line, for someone who can't see the tree (#360 review):
// worked out before the move, from where the part is now; ``to`` null is where it can't go
function treeSaid(design, id, dir, to) {
  const name = (x) => { const q = design.parts.find((p) => p.id === x); return q ? q.label || q.name || x : x; };
  const parent = (design.tree || {}).parent || {}, n = name(id);
  if (!to) {
    return { up: `${n} is already at the top`, down: `${n} is already at the bottom`, in: `${n} has no part above it to go under`,
      out: `${n} isn't under another part` }[dir];
  }
  if (dir === 'up') return `Moved ${n} up, above ${name(to[0])}`;
  if (dir === 'down') return `Moved ${n} down, below ${name(to[0])}`;
  if (dir === 'in') return `Moved ${n} under ${name(dropped(design, id, to[0], to[1]).parent[id])}`;
  return `Moved ${n} out of ${name(parent[id])}`;
}
function treeHtml(design, view) {
  const rows = treeRows(design).map(({ p, depth }) => {
    const fixed = p.role === 'fixed', off = view.parts.has(p.id);
    const cant = view.cant ? view.cant(p.id, p.version) : null, oneBody = view.oneBody || !!cant;   // no piece eye can act then
    const editing = view.rename && view.rename.part === p.id;
    const head = `<div class="trow part${view.scope === p.id && !view.piece ? ' on' : ''}${fixed ? ' ref' : ''}${off ? ' off' : ''}"${view.canDrag === false ? '' : ` draggable="true" data-drag="${esc(p.id)}"`}>
      <button class="eye" aria-label="Show or hide the whole part" data-eye="${esc(p.id)}">${off ? EYE_OFF : EYE_ON}</button>
      <button class="tname" role="treeitem" aria-level="${depth + 1}" aria-selected="${view.scope === p.id && !view.piece}" data-sel="${esc(p.id)}"${fixed ? ' data-fixed="1"' : ''} aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft">${esc(p.name || p.id)}</button>
      <span class="side">${fixed ? 'reference' : `v${p.version}`}</span></div>`
      + (editing && view.rename.key == null ? renameRow(p.id, null, view.rename.draft) : '')
      + (p.mirror_of ? `<div class="tmirror">a mirror of ${esc(p.mirror_of)}: change it there
        <button class="linkish" data-unmirror="${esc(p.id)}">break the mirror</button></div>` : '')   // (#246 review)
      + (cant ? `<div class="tcant">can't draw this part's pieces: ${esc(cant)}</div>` : '');
    const pieces = (p.pieces || []).map((pc) => {
      const pcOff = off || (!oneBody && view.pieces.has(pieceId(p.id, pc.key)));
      const eye = oneBody
        ? `<button class="eye" disabled title="${cant ? "this part can't be drawn as pieces" : 'drawn as one body: choose its pieces to hide one'}" aria-label="Can't hide a piece while it's one body">${EYE_ON}</button>`
        : `<button class="eye" aria-label="Show or hide this piece" data-eye="${esc(p.id)}" data-key="${esc(pc.key)}">${pcOff ? EYE_OFF : EYE_ON}</button>`;
      return `<div class="trow piece${view.scope === p.id && view.piece === pc.key ? ' on' : ''}${fixed ? ' ref' : ''}${pcOff ? ' off' : ''}">
        ${eye}
        <span class="swatch" aria-hidden="true" style="background:${esc(fixed ? '#9aa4ad' : pc.color)}"></span>
        <button class="tname" role="treeitem" aria-level="${depth + 2}" aria-selected="${view.scope === p.id && view.piece === pc.key}" data-sel="${esc(p.id)}" data-key="${esc(pc.key)}"${fixed ? ' data-fixed="1"' : ''}>${esc(pc.name)}</button>
        <span class="side">${esc(pc.material)}</span></div>`
        + (editing && view.rename.key === pc.key ? renameRow(p.id, pc.key, view.rename.draft) : '');
    }).join('');
    return `<div class="tpart" data-tpart="${esc(p.id)}" style="margin-left:${depth * 18}px">${head}${pieces}</div>`;
  }).join('');
  const legend = (design.legend || []).length ? `<div class="tlegend"><div class="tlegend-h">Materials</div>${design.legend.map((m) =>
    `<div class="tlegend-r"><span class="swatch" aria-hidden="true" style="background:${esc(m.color)}"></span>${esc(m.label)} · ${m.count} piece${m.count === 1 ? '' : 's'}</div>`).join('')}</div>` : '';
  return `<div class="tree-head"><button class="fold" data-fold="1" aria-expanded="${view.open}">${view.open ? '▾' : '▸'} Parts</button>
    <span class="note">${view.saying ? esc(view.saying) : `hidden pieces are still checked${view.canDrag === false ? '. Hold a part to move it' : ''}`}</span></div>${view.open
      ? `<div role="tree" aria-label="Parts">${rows}</div>${legend}` : ''}`;   // its depth said, not only drawn (#360 review)
}
function renderTree() {
  const box = $('tree');
  if (!box) return;
  const parts = S.design ? S.design.parts : [];
  box.hidden = !parts.length;
  if (!parts.length || document.activeElement === $('treeName')) return;       // never over a name being typed
  const t = seen();
  const cant = (pid, version) => { const n = noPieces.get(pid); return n && n.version === version ? n.why : null; };
  // the row that has the focus keeps it through the redraw (#360 review: the 600 ms "Waiting…" redraw dropped it to <body>,
  // where the next Alt+← is the browser's Back)
  const was = document.activeElement, held = was && box.contains(was) && was.matches && was.matches('button.tname[data-sel]')
    ? { sel: was.dataset.sel, key: was.dataset.key } : null;
  box.innerHTML = treeHtml(S.design, { parts: t.parts, pieces: t.pieces, open: t.open, rename: t.rename, scope: S.scope, piece: S.pick ? null : S.piece, canDrag: !onPhone(), saying: TREE.saying,
    oneBody: t.oneBody, cant });
  if (t.rename && $('treeName')) { $('treeName').focus(); $('treeName').select(); }
  else if (held) {
    const again = box.querySelector(`button.tname[data-sel="${CSS.escape(held.sel)}"]${held.key != null ? `[data-key="${CSS.escape(held.key)}"]` : ':not([data-key])'}`);
    if (again) again.focus();
  }
}
async function unmirror(part) {             // a mirror made a part of its own again, its shape kept (#246 review)
  try {
    S.design = await api('POST', `/api/designs/${S.slug}/parts/${part}/unmirror`);
  } catch (e) { showErr(plainly(e.message)); }
  render();
}
async function saveTreeName(part, key) {
  const label = $('treeName').value;
  $('treeName').blur();
  TREE.rename = null;
  try {
    S.design = await api('POST', `/api/designs/${S.slug}/parts/${part}/label`, key != null ? { label, piece: key } : { label });
  } catch (e) { showErr(plainly(e.message)); }
  render();
}
// one listener for the tree, so a redraw between the two clicks of a double-click can't lose it
function treeClick(el, now) {
  const d = el.dataset, t = seen();
  if (d.fold) { t.open = !t.open; keepTree(); renderTree(); return 'fold'; }
  if (d.unmirror) { unmirror(d.unmirror); return 'unmirror'; }
  if (d.renameSave) { saveTreeName(d.part, d.key != null ? d.key : null); return 'save'; }
  if (d.eye) { toggleHidden(d.eye, d.key != null ? d.key : null); return 'eye'; }
  if (d.sel) {
    const id = pieceId(d.sel, d.key != null ? d.key : ''), again = t.last && t.last.id === id && now - t.last.at < 400;
    t.last = again ? null : { id, at: now };
    if (again && !d.fixed) {
      const p = S.design.parts.find((x) => x.id === d.sel);
      const pc = d.key != null ? (p.pieces || []).find((x) => x.key === d.key) : null;
      t.rename = { part: d.sel, key: d.key != null ? d.key : null, draft: pc ? pc.name : (p.label || p.name || p.id) };
      renderTree();
      return 'rename';
    }
    setScope(d.sel, d.key != null ? d.key : null);
    return 'select';
  }
  return null;
}
$('tree').addEventListener('click', (e) => {
  if (swallowed($('tree').dataset)) return;    // a long-press opened its menu: its lift isn't also a tap (CALI-183)
  const el = e.target.closest('button');
  if (el) treeClick(el, Date.now());
});
function swallowed(data) {                     // the tap a long-press's lift makes: taken once, then gone
  if (!data.pressed) return false;
  delete data.pressed;
  return true;
}
function viewUp(down, e, data) {               // a release in the view: the menu, a long-press's lift, or a click
  if (swallowed(data)) return 'swallow';
  const still = down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) <= 5;   // past 5 px it's a pan or an orbit
  if (still && (e.button === 2 || (e.button === 0 && e.ctrlKey))) return 'menu';
  return 'click';
}
function toggleHidden(pid, key) {            // the eye, and the menu's Hide / Show: a part takes what sits under it along
  const t = seen(), set = key != null ? t.pieces : t.parts, id = key != null ? pieceId(pid, key) : pid;
  const hide = !set.has(id);
  (key != null ? [id] : [id, ...underPart(S.design, pid)]).forEach((x) => (hide ? set.add(x) : set.delete(x)));
  keepTree(); renderTree(); paint();
}
function showOnly(pid, key) {                // the menu's Show only this: every other part hidden (a piece: its part's others too)
  const t = seen(), keep = new Set([pid, ...underPart(S.design, pid)]);
  t.parts = new Set(S.design.parts.map((p) => p.id).filter((x) => !keep.has(x)));
  t.pieces = new Set();
  if (key != null) {
    const p = S.design.parts.find((x) => x.id === pid);
    (p.pieces || []).forEach((pc) => { if (pc.key !== key) t.pieces.add(pieceId(pid, pc.key)); });
  }
  keepTree(); renderTree(); paint();
}

// ------------------------------------------------------------- a part's menu (CALI-183)
// Right-click a part in the view or its row in the tree (long-press on a phone; Shift+F10 or the menu key for the selected
// one): what can be done to it, each item what its panel or the chat already does. A piece gets what applies to a piece.
const LONG_PRESS_MS = 550;
function menuItems(design, pid, piece) {
  const p = (design.parts || []).find((x) => x.id === pid);
  if (!p) return [];
  const t = seen(), study = {};
  if (piece != null) {                         // a piece: Delete… and Hide too (#324: the fillet strips v6 brought back)
    return [{ id: 'deletePiece', label: 'Delete…' }, { id: 'rename', label: 'Rename…' },
      { id: 'hide', label: t.pieces.has(pieceId(pid, piece)) ? 'Show' : 'Hide' }, { id: 'only', label: 'Show only this' },
      { id: 'ask', label: 'Ask about this' }];
  }
  (((design.studies || {}).menu || {})[pid] || []).forEach((m) => { study[m.kind] = m; });
  const items = [{ id: 'delete', label: 'Delete…' }];
  if (p.role !== 'fixed') items.push({ id: 'rename', label: 'Rename…' });
  items.push({ id: 'hide', label: t.parts.has(pid) ? 'Show' : 'Hide' }, { id: 'only', label: 'Show only this' });
  if (t.parts.size || t.pieces.size) items.push({ id: 'all', label: 'Show everything' });
  items.push({ id: 'ask', label: 'Ask about this' });
  const studied = (kind, id, label) => {      // the panels' own rule: greyed, with why, when it can't run here
    const m = study[kind];
    if (m) items.push({ id, label, off: !m.ready, why: m.ready ? '' : m.why });
  };
  studied('load', 'check', 'Check it holds');
  if (p.study === 'carve') studied('carve', 'carve', 'Carve it');         // whichever made_of says; neither where it says none
  else if (p.study === 'lighten') studied('lighten', 'lighten', 'Lighten it');
  items.push(p.mirror_of ? { id: 'unmirror', label: `Break the mirror (of ${p.mirror_of})` } : { id: 'mirror', label: 'Mirror it…' });
  if (Object.values(TREE_KEYS).some((d) => nudge(design, pid, d))) items.push({ id: 'tmove', label: 'Move in the tree ▸' });   // a phone's drag (#94)
  items.push({ id: 'versions', label: 'Versions ▸' }, { id: 'copyName', label: 'Copy its name' });
  return items;
}
function treeMovesHtml(design, pid) {          // Move in the tree ▸: where it can go, by name, with the keys that do it (#94)
  const p = design.parts.find((x) => x.id === pid), name = (id) => { const q = design.parts.find((x) => x.id === id); return q.label || q.name || id; };
  const parent = (design.tree || {}).parent || {};
  const ways = [['up', 'Move up', 'Alt+↑'], ['down', 'Move down', 'Alt+↓'], ['in', 'Put it under {}', 'Alt+→'], ['out', 'Take it out of {}', 'Alt+←']];
  return `<div class="pmenu-title">${esc(p.label || p.name || p.id)} · in the tree</div>` + ways.map(([dir, label, keys]) => {
    const to = nudge(design, pid, dir);
    if (!to) return '';
    const by = dir === 'in' ? dropped(design, pid, to[0], to[1]).parent[pid] : parent[pid];
    return `<button role="menuitem" data-menu="tmove:${dir}">${esc(label.replace('{}', by ? name(by) : ''))}${onPhone() ? '' : ` <span class="why">${keys}</span>`}</button>`;   // a phone has no keys
  }).join('');
}
function versionsHtml(p) {                     // Versions ▸: each other version, newest first, with what was asked of it (#299)
  const said = {};
  (p.history || []).forEach((h) => { if (h.kind === 'revision' && h.version != null) said[h.version] = h.feedback || h.action || ''; });
  const vs = (p.versions || []).filter((v) => v !== p.version).slice().reverse();
  return `<div class="pmenu-title">${esc(p.label || p.name || p.id)} · versions</div>` + vs.map((v) => {
    const w = String(said[v] || ''); return `<button role="menuitem" data-menu="ver:${v}">v${v}${w ? ` <span class="why">${esc(w.length > 48 ? `${w.slice(0, 47)}…` : w)}</span>` : ''}</button>`;
  }).join('') + '<button role="menuitem" data-menu="history">Its history…</button>';
}
function menuHtml(title, items) {
  return `<div class="pmenu-title">${esc(title)}</div>` + items.map((m) => `<button role="menuitem" data-menu="${m.id}"${
    m.off ? ` aria-disabled="true" class="off" title="${esc('Not yet: ' + m.why)}"` : ''}>${esc(m.label)}${
    m.off ? `<span class="why">${esc(m.why)}</span>` : ''}</button>`).join('');
}
function confirmHtml(pid, said, mirroredBy) {    // the page's own confirm, never the browser's
  if (mirroredBy && mirroredBy.length) {
    return `<div class="pmenu-said">${esc(said)}</div><div class="pmenu-row">
      <button role="menuitem" class="danger" data-menu="deleteBoth">Delete both</button>
      <button role="menuitem" data-menu="unmirrorThem">Break the mirror</button>
      <button role="menuitem" data-menu="keep">Keep it</button></div>`;
  }
  return `<div class="pmenu-said">${esc(said || `Delete ${pid}? It goes to the design's trash; you can put it back.`)}</div>
    <div class="pmenu-row"><button role="menuitem" class="danger" data-menu="deleteYes">Delete</button>
      <button role="menuitem" data-menu="keep">Keep it</button></div>`;
}
function pieceConfirmHtml(plan) {               // Delete… on a piece: what it takes, said before it's done (#324)
  return `<div class="pmenu-said">${esc(plan.said)}</div>
    <div class="pmenu-row"><button role="menuitem" class="danger" data-menu="deletePieceYes">Delete</button>
      <button role="menuitem" data-menu="keep">Keep it</button></div>`;
}
async function deletePiece(pid, piece, plan) {   // by its number, built first to be sure; else the designer's revise, by the piece's key (#332)
  if (plan.how !== 'number') { closeMenu(); return send(`Remove the ${plan.name} from ${pid}.`, pid, null, null, null, piece); }
  try {
    const got = await api('POST', `/api/designs/${S.slug}/parts/${pid}/pieces/${encodeURIComponent(piece)}/delete`);
    if (got.how === 'designer') {                   // built, it does more than take the piece away: said, and asked again
      if (S.menu) S.menu.plan = got;
      return menuConfirm(pieceConfirmHtml(got));
    }
    closeMenu();
    S.design = got.design;
    render();
    say(got.said);
    await syncParts(S.design, false);
  } catch (e) { closeMenu(); showErr(plainly(e.message)); }
}
function openMenu(pid, piece, x, y, from) {
  closeMenu(false);
  const p = S.design && S.design.parts.find((q) => q.id === pid);
  if (!p) return;
  const pc = piece != null ? (p.pieces || []).find((q) => q.key === piece) : null;
  const name = p.label || p.name || p.id;
  S.menu = { pid, piece: piece != null ? piece : null, from: from || document.activeElement };
  const box = document.createElement('div');
  box.id = 'partMenu'; box.className = 'pmenu'; box.setAttribute('role', 'menu');
  box.setAttribute('aria-label', `${pc ? pc.name : name}: what to do`);
  box.innerHTML = menuHtml(pc ? `${name} · ${pc.name}` : name, menuItems(S.design, pid, piece));
  box.addEventListener('click', (e) => {
    const b = e.target.closest('[data-menu]');
    if (b && b.getAttribute('aria-disabled') !== 'true') menuDo(b.dataset.menu);
  });
  document.body.appendChild(box);
  placeMenu(box, x, y);
  menuFocus(0);
}
function placeMenu(box, x, y) {               // where it was asked for, kept on the screen
  const r = box.getBoundingClientRect();
  box.style.left = `${Math.max(8, Math.min(x, innerWidth - r.width - 8))}px`;
  box.style.top = `${Math.max(8, Math.min(y, innerHeight - r.height - 8))}px`;
}
function menuConfirm(html) {
  const box = $('partMenu');
  if (!box) return;
  box.innerHTML = html;
  placeMenu(box, parseFloat(box.style.left) || 8, parseFloat(box.style.top) || 8);
  menuFocus(0);
}
function closeMenu(back = true) {
  const box = $('partMenu'), m = S.menu;
  if (box) box.remove();
  S.menu = null;
  if (back && box && m) menuBack(m);
}
function menuBack(m) {                         // focus where the menu was asked for: its row, or the view; never <body>
  const row = document.querySelector(`#tree button.tname[data-sel="${CSS.escape(m.pid)}"]`);
  const to = m.from && document.contains(m.from) && m.from !== document.body ? m.from
    : row || document.querySelector('#tree button.tname') || renderer.domElement;
  if (to === renderer.domElement && !to.hasAttribute('tabindex')) to.setAttribute('tabindex', '-1');
  to.focus();
}
function menuFocus(step) {                     // the arrow keys move through its items
  const items = [...document.querySelectorAll('#partMenu [data-menu]')];
  if (!items.length) return;
  const at = items.indexOf(document.activeElement);
  items[step === 0 || at < 0 ? 0 : (at + step + items.length) % items.length].focus();
}
function menuAnchor() {                        // where the keyboard's menu opens: the selected row, or the view's middle
  const row = document.querySelector(`#tree [data-sel="${CSS.escape(S.scope)}"]`);
  const r = (row || viewer).getBoundingClientRect();
  return row ? [r.left + 24, r.bottom] : [r.left + r.width / 2, r.top + r.height / 2];
}
async function menuDo(id) {
  const m = S.menu;
  if (!m) return;
  const { pid, piece } = m, t = seen();
  if (id === 'delete') return menuConfirm(confirmHtml(pid));
  if (id === 'deletePiece') {                  // asks what it takes first: a number that turns it off, or the designer
    try { m.plan = await api('GET', `/api/designs/${S.slug}/parts/${pid}/pieces/${encodeURIComponent(piece)}/delete`); }
    catch (e) { closeMenu(); return showErr(plainly(e.message)); }
    return menuConfirm(pieceConfirmHtml(m.plan));
  }
  if (id === 'deletePieceYes') return deletePiece(pid, piece, m.plan);
  if (id === 'versions') return menuConfirm(versionsHtml(S.design.parts.find((x) => x.id === pid)));   // ▸ (#299)
  if (id === 'tmove') return menuConfirm(treeMovesHtml(S.design, pid));
  if (id === 'keep') return closeMenu();
  if (id === 'deleteYes' || id === 'deleteBoth') return deletePart(pid, id === 'deleteBoth' ? m.mirroredBy || [] : []);
  if (id === 'unmirrorThem') {                 // its mirrors become parts of their own; then it's asked again
    for (const f of m.mirroredBy || []) await unmirror(f);
    m.mirroredBy = null;
    return menuConfirm(confirmHtml(pid));
  }
  closeMenu();
  const p = S.design.parts.find((x) => x.id === pid);
  if (id === 'rename') {                       // the tree's own rename, inline
    const pc = piece != null ? (p.pieces || []).find((x) => x.key === piece) : null;
    t.open = true;
    t.rename = { part: pid, key: piece, draft: pc ? pc.name : (p.label || p.name || p.id) };
    return renderTree();
  }
  if (id.startsWith('tmove:')) {               // as the keys do it, and said as they say it (#360 review)
    const dir = id.slice(6), to = nudge(S.design, pid, dir), said = treeSaid(S.design, pid, dir, to);
    if (!to) return say(said);
    if (await moveInTree(pid, to[0], to[1])) say(said);
    return;
  }
  if (id === 'hide') return toggleHidden(pid, piece ?? null);
  if (id === 'only') return showOnly(pid, piece);
  if (id === 'all') { t.parts = new Set(); t.pieces = new Set(); keepTree(); renderTree(); paint(); return; }
  if (id === 'ask') return setScope(pid, piece);
  if (id === 'check' || id === 'lighten' || id === 'carve') return useBetter({ part: pid, action: id === 'check' ? 'load' : id });
  if (id === 'mirror') { setScope(pid); $('msg').value = `Make ${pid} a mirror of `; $('msg').focus(); return; }   // the chat's route (#239)
  if (id === 'unmirror') return unmirror(pid);
  if (id === 'history') { setScope(pid); return goTo('partHistory'); }
  if (id.startsWith('ver:')) { setScope(pid); return showVersion(pid, Number(id.slice(4))); }   // its preview, Go back in its bar
  if (id === 'copyName') {
    try { await navigator.clipboard.writeText(pid); say(`Copied ${pid}.`); } catch (e) { say(`Its name is ${pid}.`); }
  }
}
async function deletePart(pid, also) {
  try {
    const got = await api('POST', `/api/designs/${S.slug}/parts/${pid}/remove`, { also });
    const m = S.menu;
    closeMenu(false);
    S.design = got.state;
    if (S.scope === pid || also.includes(S.scope)) setScope(null); else render();
    if (m) menuBack({ ...m, from: null });      // its row is gone with it: the tree's first, never <body>
    putBack(got.said, [got.removed, ...(got.also || [])]);
    await syncParts(S.design, false);            // and out of the view, as a refresh takes it out
  } catch (e) {
    let said = e.message, by = null;
    try { const j = JSON.parse(e.message); said = j.said; by = j.mirrored_by; } catch (x) { /* words */ }
    if (S.menu) S.menu.mirroredBy = by;
    if (by) return menuConfirm(confirmHtml(pid, said, by));
    menuConfirm(`<div class="pmenu-said">${esc(plainly(said))}</div><div class="pmenu-row"><button role="menuitem" data-menu="keep">OK</button></div>`);
  }
}
function say(text, act) {                      // a line at the foot of the page: what the menu did, and Put back
  let bar = $('putBack');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'putBack'; bar.className = 'putback'; bar.setAttribute('role', 'status');
    document.body.appendChild(bar);
  }
  bar.innerHTML = `<span>${esc(text)}</span>${act ? ' <button class="primary" data-putback="1">Put back</button>' : ''}
    <button class="ghost" data-putback-close="1" aria-label="Close">x</button>`;
  bar.hidden = false;
  bar.onclick = (e) => {
    if (e.target.closest('[data-putback-close]')) bar.hidden = true;
    else if (act && e.target.closest('[data-putback]')) act();
  };
  clearTimeout(say.t);
  if (!act) say.t = setTimeout(() => { bar.hidden = true; }, 4000);
}
function putBack(said, gone) {
  say(said, async () => {
    try {
      let got = null;
      const said = [];
      for (const g of gone) {                  // its source first, then what mirrors it
        got = await api('POST', `/api/designs/${S.slug}/trash/restore`, { id: g.id });
        said.push(got.said);
      }
      S.design = got.state;
      render();
      say(said.join(' '));
      await syncParts(S.design, false);          // back in the view
    } catch (e) { showErr(plainly(e.message)); }
  });
}
function longPress(el, open) {                 // a phone's right-click: held still, then the menu
  let t = null, at = null;
  el.addEventListener('pointerdown', (e) => {
    delete el.dataset.pressed;                 // a press that ended without its tap: never the next one's (#302 review)
    if (e.pointerType !== 'touch') return;
    at = [e.clientX, e.clientY];
    clearTimeout(t);
    t = setTimeout(() => { t = null; el.dataset.pressed = '1'; open(e); }, LONG_PRESS_MS);
  });
  el.addEventListener('pointermove', (e) => {
    if (t && at && Math.hypot(e.clientX - at[0], e.clientY - at[1]) > 8) { clearTimeout(t); t = null; }
  });
  el.addEventListener('pointerup', () => { clearTimeout(t); t = null; });
  el.addEventListener('pointercancel', () => { clearTimeout(t); t = null; delete el.dataset.pressed; });   // no tap follows
}
$('tree').addEventListener('contextmenu', (e) => {
  const b = e.target.closest('[data-sel]');
  if (!b) return;
  e.preventDefault();
  openMenu(b.dataset.sel, b.dataset.key != null ? b.dataset.key : null, e.clientX, e.clientY, b);
});
longPress($('tree'), (e) => {
  const b = e.target.closest('[data-sel]');
  if (b) openMenu(b.dataset.sel, b.dataset.key != null ? b.dataset.key : null, e.clientX, e.clientY, b);
});
addEventListener('pointerdown', (e) => { if ($('partMenu') && !e.target.closest('#partMenu')) closeMenu(false); }, true);   // focus goes where that click goes
addEventListener('keydown', (e) => {
  if ($('partMenu')) {
    if (e.key === 'Escape') { e.preventDefault(); closeMenu(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); menuFocus(e.key === 'ArrowDown' ? 1 : -1); }
    return;
  }
  const a = document.activeElement;
  const empty = a && a.id === 'msg' && !a.value.trim();          // selecting puts the cursor here: an empty box isn't typing
  const typing = !empty && (/INPUT|TEXTAREA|SELECT/.test(a.tagName) || a.isContentEditable);
  if (typing || !S.scope || !S.design) return;
  if ((e.key === 'F10' && e.shiftKey) || e.key === 'ContextMenu') {
    e.preventDefault();
    const [x, y] = menuAnchor();
    openMenu(S.scope, S.piece, x, y);
  } else if (e.key === 'Delete' && S.piece == null && !empty) {   // the same confirm, straight away (never from the box)
    e.preventDefault();
    const [x, y] = menuAnchor();
    openMenu(S.scope, null, x, y);
    menuDo('delete');
  }
});
// drag a part to move it: above or below another, or onto it to sit under it. The tree only (#94, slice b)
const PHONE = window.matchMedia('(max-width: 700px)');   // the drawer (#200): moving a part needs a mouse
function onPhone() { return PHONE.matches; }
PHONE.addEventListener('change', () => renderTree());
function clearDrop() {
  document.querySelectorAll('#tree .drop-before, #tree .drop-after, #tree .drop-into').forEach((r) => r.classList.remove('drop-before', 'drop-after', 'drop-into'));
}
async function moveInTree(drag, target, zone) {
  if (!S.design) return;                           // a design is loading: nothing to move in (#251 review)
  const next = dropped(S.design, drag, target, zone);
  if (!next) return;
  const slug = S.slug;                            // the design it's moved in: another may be open by the time it's done (#206)
  const slow = setTimeout(() => {                  // the lock can be minutes
    TREE.waiting.add(slug);                        // said again if you come back to it while it waits (#251 review)
    if (S.slug !== slug) return;
    TREE.saying = WAITING; renderTree();
  }, 600);
  let got, err, saved = false;
  try {
    got = await api('POST', `/api/designs/${slug}/tree`, next);
  } catch (e) { err = e; }
  clearTimeout(slow);
  TREE.waiting.delete(slug);
  if (S.slug !== slug) {                           // saved there; nothing of it belongs on this one. A failure is said back there
    if (err) TREE.missed[slug] = `Your move of the ${drag.replace(/_/g, ' ')} in ${slug} didn't save: ${plainly(err.message)}`;   // as the drive line says it
    return;
  }
  if (err) showErr(plainly(err.message));
  else {
    saved = true;
    S.design = got;
    const t = seen(), up = next.parent[drag];
    if (up && t.parts.has(up)) {                  // under a hidden part, it's hidden as that part is
      [drag, ...underPart(S.design, drag)].forEach((x) => t.parts.add(x));
      keepTree();
    }
  }
  TREE.saying = null;
  render();
  return saved;                                   // the keys and the menu say a move only once it's saved
}
// where a drop would land, on screen: below a part means below everything that sits under it, so that's where the line goes
function showDrop(row, zone) {
  const id = row.dataset.drag;
  if (zone !== 'after') { row.classList.add(`drop-${zone}`); return; }
  const under = underPart(S.design, id), last = treeRows(S.design).map((r) => r.p.id).filter((x) => x === id || under.includes(x)).pop();
  const block = document.querySelector(`#tree [data-tpart="${CSS.escape(last)}"]`);
  (block || row).classList.add('drop-after');
}
function treeDragStart(e) {
  const row = e.target.closest && e.target.closest('[data-drag]');
  if (!row || TREE.rename || onPhone() || !S.design) { e.preventDefault(); return; }   // nothing to move in while one loads (#251)
  TREE.drag = row.dataset.drag;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', TREE.drag);
}
function treeDragOver(e) {
  const row = e.target.closest('[data-drag]');
  clearDrop();
  if (!row || !TREE.drag || !S.design || !dropped(S.design, TREE.drag, row.dataset.drag, 'into')) return;
  e.preventDefault();
  showDrop(row, dropZone(e, row));
}
function treeDrop(e) {
  const row = e.target.closest('[data-drag]'), drag = TREE.drag;
  clearDrop();
  TREE.drag = null;
  if (!row || !drag || !S.design) return;
  e.preventDefault();
  moveInTree(drag, row.dataset.drag, dropZone(e, row));
}
// a move that failed while another design was open, said once you're back on its design (#251 review)
function sayMissed() {
  const said = TREE.missed[S.slug];
  if (!said) return;
  delete TREE.missed[S.slug];
  showErr(said);
}
function treeDragLeave(e) {
  if (!e.relatedTarget || !$('tree').contains(e.relatedTarget)) clearDrop();
}
$('tree').addEventListener('dragstart', treeDragStart);
$('tree').addEventListener('dragover', treeDragOver);
$('tree').addEventListener('drop', treeDrop);
$('tree').addEventListener('dragleave', treeDragLeave);
$('tree').addEventListener('dragend', () => { TREE.drag = null; clearDrop(); });
// the tree's keys: the rename box's Enter and Escape, and Alt+arrows on a part's row to move it (#94). Alt+← is the
// browser's Back elsewhere, so on a part's row it's always the tree's, even where the part can't go
async function treeKey(e) {
  if (e.target.dataset.renameInput) {
    if (e.key === 'Enter') { e.preventDefault(); e.target.parentElement.querySelector('[data-rename-save]').click(); }
    if (e.key === 'Escape') { TREE.rename = null; e.target.blur(); renderTree(); }
    return;
  }
  const dir = TREE_KEYS[e.key], row = e.target.closest && e.target.closest('.trow');
  if (!row || !dir || !e.altKey || e.ctrlKey || e.metaKey) return;
  e.preventDefault();                          // anywhere on a row, Alt+← is never the browser's Back (#360 review: its eye too)
  const b = row.querySelector('button.tname[data-sel]');
  if (!b || b.dataset.key != null || TREE.rename || !S.design) return;    // a piece's row: its part moves, never the piece alone
  const pid = b.dataset.sel, to = nudge(S.design, pid, dir), said = treeSaid(S.design, pid, dir, to);
  if (!to) { say(said); return; }
  if (!(await moveInTree(pid, to[0], to[1]))) return;
  say(said);
  // focus back on the part only if it's nowhere else: the save can take seconds, and by then the person may be typing in
  // the chat (#360 review: the row took the focus out of a draft). Through the wait the redraw has kept it on the row
  const now = document.activeElement;
  if (now && now !== document.body) return;
  const again = document.querySelector(`#tree button.tname[data-sel="${CSS.escape(pid)}"]:not([data-key])`);
  if (again) again.focus();
}
$('tree').addEventListener('keydown', treeKey);

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
const pieces3d = new Map();     // part id -> {version, byKey: piece -> THREE.Mesh}: the part as its pieces (#94)
const noPieces = new Map();     // part id -> {version, why} that can't be drawn as pieces: one body, and the tree says why
let stationMesh = null;         // a whittle station shown in place of its part
const loader = new STLLoader();

// framed by fit, and not moved since: a resize frames it again for the new shape (reviewer-2 on #250: 1024 to 701 px, or a phone
// turned, cut the stool off at the edge until fit was pressed). Once the person moves the camera, a resize leaves it where they put it
let fitted = false;
function unfit() {
  fitted = false;
}
function resize() {
  const w = viewer.clientWidth || 1, h = viewer.clientHeight || 1;
  renderer.setPixelRatio(devicePixelRatio);
  renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.updateProjectionMatrix();
  if (fitted) frame();
}
new ResizeObserver(resize).observe(viewer);
resize();
(function loop() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); })();

function contentBox() {
  const box = new THREE.Box3();
  for (const m of meshes.values()) if (m.visible) box.expandByObject(m);
  for (const s of pieces3d.values()) for (const m of s.byKey.values()) if (m.visible) box.expandByObject(m);
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

// how much further back a view narrower than it is tall stands, so the part fits across it too (#70 item 20: at a 1024 px
// window, fit cropped the stool). Across, the half-angle's tangent is the height's times the aspect, so the distance
// grows by 1/aspect; 1 for a view as wide as it's tall or wider, as before
function narrowBy(aspect) {
  return aspect >= 1 ? 1 : 1 / aspect;
}

function frame() {
  const box = contentBox();
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2 || 100;
  const d = r * 2.3 * narrowBy(camera.aspect);
  controls.target.copy(c);
  camera.position.set(c.x - d * 0.75, c.y - d * 0.95, c.z + d * 0.55);   // from behind-left, above
  camera.near = r / 200; camera.far = r * 200; camera.updateProjectionMatrix();
  controls.update();
  fitGrid(box);
  fitted = true;
}
$('fitView').onclick = frame;
controls.addEventListener('start', unfit);           // the person moved it: theirs now
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
  const slug = S.slug;                          // what lands after the design is left isn't drawn (#168)
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
      if (S.slug !== slug) return;
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
  if (S.slug !== slug) return;
  const failed = results.filter((x) => x.status === 'rejected');
  if (failed.length) showErr(failed.map((f) => f.reason.message).join(' · '));
  await syncPieces(design);
  paint();
  refreshBuilt3d(design);
  if (refit || (loads.length && meshes.size === loads.length)) frame();
}

// ------------------------------------------------------------- a part as its pieces, in their materials (#94)
function dropPieces(pid) {
  const s = pieces3d.get(pid);
  if (!s) return;
  for (const m of s.byKey.values()) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
  pieces3d.delete(pid);
}
// every piece or none: a part that can't be cut into its pieces stays one body (a shape that isn't closed, say)
async function loadPieces(p) {
  const got = await Promise.all(p.pieces.map(async (pc) => {
    const r = await fetch(`/api/designs/${S.slug}/parts/${p.id}/piece.stl?key=${encodeURIComponent(pc.key)}&v=${p.version}`);
    if (!r.ok) {
      const said = await r.json().catch(() => ({}));
      throw new Error(typeof said.detail === 'string' ? said.detail : `the server answered ${r.status}`);
    }
    return [pc, await r.arrayBuffer()];
  }));
  const byKey = new Map();
  for (const [pc, buf] of got) {
    const geom = loader.parse(buf);
    geom.computeVertexNormals();
    const mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: pc.color, metalness: 0.08, roughness: 0.6 }));
    mesh.userData = { partId: p.id, piece: pc.key, color: pc.color };
    byKey.set(pc.key, mesh);
  }
  return byKey;
}
let piecesOf = null;              // the design they're of: two designs can both have a part called i_want at v8
async function syncPieces(design) {
  const slug = S.slug;
  if (piecesOf !== slug) { [...pieces3d.keys()].forEach(dropPieces); noPieces.clear(); piecesOf = slug; }
  const want = new Map(design.parts.filter((p) => (p.pieces || []).length && p.role !== 'fixed').map((p) => [p.id, p]));
  for (const [pid, s] of pieces3d) if (!want.has(pid) || want.get(pid).version !== s.version) dropPieces(pid);
  await Promise.all([...want.values()].filter((p) => !pieces3d.has(p.id) && (noPieces.get(p.id) || {}).version !== p.version).map(async (p) => {
    try {
      const byKey = await loadPieces(p);
      if (S.slug !== slug) return;                // two designs can share a part's id and version
      if (!S.design || !S.design.parts.some((x) => x.id === p.id && x.version === p.version)) return;   // it moved on
      dropPieces(p.id);
      for (const m of byKey.values()) scene.add(m);
      pieces3d.set(p.id, { version: p.version, byKey });
    } catch (e) {
      if (S.slug !== slug) return;
      noPieces.set(p.id, { version: p.version, why: plainly(e.message) });
      renderTree();
    }
  }));
}
$('oneBody').onclick = () => { TREE.oneBody = !TREE.oneBody; keepTree(); paint(); renderTree(); };

// ------------------------------------------------------------- how it's built, in 3D (CALI-52)
// A part shown as built: every panel, stick, tube and plate where it sits, in layers you can switch off.
const built3d = new Map();       // part id -> {group, layers: Map(layer -> THREE.Group), data, version}
const hiddenLayers = new Set();  // layers switched off, across parts

function pieceMesh(pc, color) {
  const c = new THREE.Color(color);
  if (pc.kind === 'sheet') {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(pc.tris, 3));
    geom.computeVertexNormals();
    const g = new THREE.Group();
    g.add(new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: c, side: THREE.DoubleSide, transparent: true,
      opacity: 0.55, roughness: 0.85, depthWrite: false })));
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geom, 25), new THREE.LineBasicMaterial({ color: c.clone().multiplyScalar(0.55) })));
    return g;
  }
  if (pc.kind === 'stick') {
    const a = new THREE.Vector3(...pc.a), b = new THREE.Vector3(...pc.b), d = b.clone().sub(a);
    const m = new THREE.Mesh(new THREE.BoxGeometry(d.length(), pc.w, pc.h),
      new THREE.MeshStandardMaterial({ color: c, roughness: 0.7, metalness: pc.layer === 'tubes' ? 0.45 : 0 }));
    m.position.copy(a.clone().add(b).multiplyScalar(0.5));
    m.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), d.normalize());
    return m;
  }
  if (pc.kind === 'plate') {
    const shape = new THREE.Shape(pc.outline.map(([u, v]) => new THREE.Vector2(u, v)));
    for (const h of pc.holes) shape.holes.push(new THREE.Path(h.map(([u, v]) => new THREE.Vector2(u, v))));
    const geom = new THREE.ExtrudeGeometry(shape, { depth: pc.thickness, bevelEnabled: false });
    const P = pc.placement, n = new THREE.Vector3(...P.normal);
    const basis = new THREE.Matrix4().makeBasis(new THREE.Vector3(...P.u), new THREE.Vector3(...P.v), n);
    const g = new THREE.Group();
    for (const side of pc.count > 1 ? [1, -1] : [1]) {           // a cheek plate each side of the tubes
      const m = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: c, metalness: 0.55, roughness: 0.45, side: THREE.DoubleSide }));
      m.matrixAutoUpdate = false;
      m.matrix.copy(basis).setPosition(new THREE.Vector3(...P.origin).add(n.clone().multiplyScalar(side * pc.offset - pc.thickness / 2)));
      g.add(m);
    }
    return g;
  }
  return null;
}

async function showBuilt3d(pid, on) {
  const had = built3d.get(pid);
  if (had) { scene.remove(had.group); built3d.delete(pid); }
  if (on) {
    const data = await api('GET', `/api/designs/${S.slug}/parts/${pid}/pieces`);
    const group = new THREE.Group(), layers = new Map();
    const colour = Object.fromEntries(data.layers.map((L) => [L.id, L.color]));
    for (const L of data.layers) { const g = new THREE.Group(); layers.set(L.id, g); group.add(g); }
    for (const pc of data.pieces) { const m = pieceMesh(pc, colour[pc.layer]); if (m) layers.get(pc.layer).add(m); }
    const part = S.design.parts.find((x) => x.id === pid);
    scene.add(group);
    built3d.set(pid, { group, layers, data, version: part && part.version });
  }
  applyLayers(); renderLayers(); paint();
}

function applyLayers() {
  for (const b of built3d.values()) for (const [id, g] of b.layers) g.visible = !hiddenLayers.has(id);
}

function renderLayers() {
  const box = $('layers');
  if (!box) return;
  if (!built3d.size) { box.hidden = true; box.innerHTML = ''; return; }
  const seen = new Map();
  for (const b of built3d.values()) for (const L of b.data.layers) seen.set(L.id, L);
  box.hidden = false;
  box.innerHTML = `<div class="small"><b>How it's built</b></div>
    ${[...built3d.keys()].map((pid) => `<div class="small muted">${esc(pid)} <a href="#" data-unbuild="${esc(pid)}" title="back to the solid">×</a></div>`).join('')}
    ${[...seen.values()].map((L) => `<label class="small"><input type="checkbox" data-layer="${esc(L.id)}" ${hiddenLayers.has(L.id) ? '' : 'checked'}>
      <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${L.color}"></span> ${esc(L.label)}</label>`).join('')}
    <label class="small"><input type="checkbox" id="layerSolid" ${S.showSolid ? 'checked' : ''}> the solid, faint</label>`;
  box.querySelectorAll('[data-layer]').forEach((cb) => {
    cb.onchange = () => { if (cb.checked) hiddenLayers.delete(cb.dataset.layer); else hiddenLayers.add(cb.dataset.layer); applyLayers(); };
  });
  box.querySelectorAll('[data-unbuild]').forEach((a) => { a.onclick = (e) => { e.preventDefault(); showBuilt3d(a.dataset.unbuild, false).then(() => renderInspector()); }; });
  const solid = $('layerSolid');
  if (solid) solid.onchange = () => { S.showSolid = solid.checked; paint(); };
}

// a part that changed since it was shown as built is shown again, as it is now
function refreshBuilt3d(design) {
  for (const [pid, b] of built3d) {
    const p = design.parts.find((x) => x.id === pid);
    if (!p) showBuilt3d(pid, false);
    else if (p.version !== b.version) showBuilt3d(pid, true);
  }
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
    const asPieces = drawnAsPieces(pid);
    m.visible = !(S.station && S.station.part === pid) && !asPieces && !seen().parts.has(pid);
    // while previewing one part's design, fade the rest — the box would otherwise hide the frame
    const fade = !!S.station && S.station.part !== pid;
    const ghost = built3d.has(pid);            // shown as built: the solid is a faint ghost you can still click
    const transparent = fade || ghost || base.transparent;
    if (m.material.transparent !== transparent) m.material.needsUpdate = true;   // recompiles the shader
    m.material.transparent = transparent;
    m.material.opacity = ghost ? (S.showSolid ? 0.25 : 0.04) : fade ? Math.min(0.18, base.opacity) : base.opacity;
    m.material.depthWrite = !transparent;
  }
  for (const [pid, s] of pieces3d) {
    const on = drawnAsPieces(pid), hurt = hit.has(pid);
    for (const [key, m] of s.byKey) {
      m.visible = on && !isHidden(pid, key);
      m.material.color.set(hurt ? 0xf85149 : m.userData.color);
      const sel = S.scope === pid && (!S.piece || S.piece === key);
      m.material.emissive.setHex(sel ? 0x1f6feb : 0x000000);
      m.material.emissiveIntensity = sel ? 0.4 : 0;
    }
  }
  const b = $('oneBody');
  if (b) { b.textContent = TREE.oneBody ? 'its pieces' : 'one body'; b.hidden = !pieces3d.size; }
}
// a part is drawn as its pieces when they're there, and not while a study's step or the built view stands in for it
function drawnAsPieces(pid) {
  return pieces3d.has(pid) && !TREE.oneBody && !built3d.has(pid) && !S.station;
}

// click a part to talk about it; click empty space to go back to the whole design
const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY, e.button]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  const d = down; down = null;
  const act = viewUp(d, e, renderer.domElement.dataset);
  if (act === 'swallow') return;
  if (act === 'menu') {
    const hit = pick(e);                       // right-click, not a right-drag pan: its menu (CALI-183)
    if (hit) openMenu(hit.object.userData.partId, null, e.clientX, e.clientY, renderer.domElement);
    return;
  }
  if (!d || d[2] !== 0 || e.button !== 0) return;
  if (Math.hypot(e.clientX - d[0], e.clientY - d[1]) > 5) return;    // an orbit drag, not a click
  const hit = pick(e);
  if (PICK.mode !== 'part' && (hit || S.scope)) { choose(e, hit); return; }   // just off the silhouette is still its edge
  setScope(hit ? hit.object.userData.partId : null);
});
renderer.domElement.addEventListener('pointermove', (e) => {
  const tip = $('tip');
  if (down) { tip.hidden = true; return; }
  const hit = pick(e);
  if (!hit) { tip.hidden = true; return; }
  const p = S.design.parts.find((x) => x.id === hit.object.userData.partId);
  tip.textContent = p ? `${p.name || p.id}${p.intent ? ' — ' + p.intent : ''}` : '';
  const rect = viewer.getBoundingClientRect();
  tip.style.left = `${e.clientX - rect.left + 14}px`;
  tip.style.top = `${e.clientY - rect.top + 10}px`;
  tip.hidden = !p;
});
renderer.domElement.addEventListener('contextmenu', (e) => e.preventDefault());   // the menu opens on the button's release
longPress(renderer.domElement, (e) => {
  const hit = pick(e);
  if (hit) openMenu(hit.object.userData.partId, null, e.clientX, e.clientY, renderer.domElement);
});
function pick(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const pieces = [...pieces3d.values()].flatMap((s) => [...s.byKey.values()]);
  const hits = ray.intersectObjects([...meshes.values(), ...pieces].filter((m) => m.visible), false);
  return hits[0] || null;
}

// ------------------------------------------------------------- pick a face or an edge (#109, the mockup's bar)
// Part, Face or Edge: a click in Face or Edge says which, and the chat says what it picked. The ids are this version's.
const PICK = { lit: null, mode: 'part', parts: new Map(), overlay: null, turn: 0 };
const pickKey = (pid, version) => `${S.slug}/${pid}/${version}`;
// which face a triangle of the merged mesh belongs to: ``starts`` holds each face's first triangle
function faceOfTriangle(starts, tri) {
  let lo = 0, hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= tri) lo = mid; else hi = mid - 1;
  }
  return lo;
}
// the edge nearest the cursor on screen, within ``px``, among those in front of ``farthest`` (no edges through the part)
function nearestEdge(edges, project, cursor, px, farthest) {
  let best = null;
  for (const e of edges) {
    const pts = e.points.map(project);
    for (let i = 0; i + 1 < pts.length; i += 1) {
      const a = pts[i], b = pts[i + 1], dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy;
      const t = l2 ? Math.min(1, Math.max(0, ((cursor.x - a.x) * dx + (cursor.y - a.y) * dy) / l2)) : 0;
      const d = Math.hypot(a.x + t * dx - cursor.x, a.y + t * dy - cursor.y), depth = a.d + t * (b.d - a.d);
      if (d <= px && depth <= farthest && (!best || d < best.d)) best = { edge: e, d };
    }
  }
  return best ? best.edge : null;
}
// a point on a part with no B-rep: where it is, in the design's units
const pointSaid = (p) => `point on the surface: x ${len(p[0], 1)}, y ${len(p[1], 1)}, z ${len(p[2], 1)}`;
// the same point for the designer: scripts are in millimetres, whatever the page is showing (#181 review)
const pointTold = (p) => `point on the surface: x ${+p[0].toFixed(1)} mm, y ${+p[1].toFixed(1)} mm, z ${+p[2].toFixed(1)} mm`;
// what goes to the designer: what was picked, and where in the script's own millimetres
function aboutPick(pick, text) {
  if (!pick) return text;
  return `About this ${pick.told || pick.said}${pick.local ? ` (at x ${pick.local[0]}, y ${pick.local[1]}, z ${pick.local[2]} mm in the script's coordinates)` : ''}: ${text}`;
}
// what the landing check is told: the ids are the version the pick was made on (#196)
function pickPosted(text) {
  return S.pick && S.pick.id ? { kind: S.pick.kind, id: S.pick.id, version: S.pick.version, text } : null;
}
// a rebuild renumbers the faces and edges and moves them: a pick from before it is about something that's gone (#196)
function dropOldPick() {
  if (!S.pick || !S.design) return;
  const part = S.design.parts.find((p) => p.id === S.pick.part);
  if (part && part.version === S.pick.version) return;
  clearPick();
  pickHint('Rebuilt: click it again');
}
function clearPick() {
  S.pick = null;
  PICK.turn += 1;                                 // a pick still on its way is off too
  if (PICK.overlay) { scene.remove(PICK.overlay); PICK.overlay.geometry.dispose(); PICK.overlay = null; }
}
// a face sits on the part (its far side stays hidden); an edge and a point draw over everything, so they can be seen
function drawPick(geometry, onSurface) {
  const m = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: 0xf5a524, transparent: true, opacity: 0.75, depthTest: !!onSurface,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, side: THREE.DoubleSide }));
  m.renderOrder = 10;
  scene.add(m);
  PICK.overlay = m;
}
const PICK_HINTS = { part: 'Click a part', face: 'Click a face', edge: 'Click an edge' };
function pickHint(text) { $('pickHint').textContent = text || PICK_HINTS[PICK.mode]; }
async function loadFeatures(pid) {
  pickHint('working out its faces and edges…');
  try {
    const got = await api('GET', `/api/designs/${S.slug}/parts/${pid}/features.json`);
    const pos = [], index = [], starts = [];
    let at = 0;
    for (const f of got.faces) {
      starts.push(index.length / 3);
      for (const v of f.verts) pos.push(v);
      for (const i of f.tris) index.push(i + at);
      at += f.verts.length / 3;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(index);
    return { ...got, starts, mesh: got.mesh ? null : new THREE.Mesh(g), solidMesh: !!got.mesh };
  } finally { pickHint(); }                       // whatever happened, it's stopped working
}
// asked once per part, version and unit, however many clicks wait on it
async function features(pid) {
  const part = S.design.parts.find((p) => p.id === pid), key = `${pickKey(pid, part.version)}/${S.design.display_units}`;
  if (!PICK.parts.has(key)) PICK.parts.set(key, loadFeatures(pid));
  try { return await PICK.parts.get(key); } catch (e) { PICK.parts.delete(key); throw e; }
}
function facePicked(data, hit) {
  const near = 0.01 * hit.distance + 1;
  const at = ray.intersectObject(data.mesh, false).find((h) => h.distance >= hit.distance - near);
  return at ? data.faces[faceOfTriangle(data.starts, at.faceIndex)] : null;
}
function edgePicked(data, hit, e, seen) {
  const { rect, camera: view } = seen, v = new THREE.Vector3();
  const project = (p) => {
    v.set(p[0], p[1], p[2]);
    const d = v.distanceTo(view.position);
    v.project(view);
    return { x: (v.x + 1) * rect.width / 2, y: (1 - v.y) * rect.height / 2, d };
  };
  return nearestEdge(data.edges, project, { x: e.clientX - rect.left, y: e.clientY - rect.top }, 12, hit ? 1.01 * hit.distance + 1 : Infinity);
}
async function choose(e, hit) {
  const pid = hit ? hit.object.userData.partId : S.scope, point = hit ? [hit.point.x, hit.point.y, hit.point.z] : null;
  // the click as it was: the pointer and the camera can move while the first pick works out its faces (#172)
  const seen = { ray: ray.ray.clone(), camera: camera.clone(), rect: renderer.domElement.getBoundingClientRect() };
  if (S.scope !== pid) setScope(pid);
  clearPick();
  renderScope();                                  // a click that misses has no pick: the chip and the box say so, as the message will (#181)
  const turn = PICK.turn;                         // only the last click counts
  let data;
  try { data = await features(pid); } catch (err) {
    if (turn === PICK.turn) pickHint(`can't pick on it: ${plainly(err.message)}`);
    return;
  }
  if (turn !== PICK.turn) return;
  ray.ray.copy(seen.ray);
  if (!hit && (data.solidMesh || PICK.mode === 'face')) return;   // only an edge can be picked from just off the part
  if (data.solidMesh) {                                   // carved, whittled, imported: no faces to name
    S.pick = { part: pid, kind: 'point', said: pointSaid(point), told: pointTold(point), local: null, point, version: data.version };
    drawPick(new THREE.SphereGeometry(Math.max(2, 0.006 * hit.distance), 12, 12).translate(...point));
  } else if (PICK.mode === 'face') {
    const f = facePicked(data, hit);
    if (!f) return;
    S.pick = { part: pid, kind: 'face', id: f.id, said: f.said, local: f.local, version: data.version };
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(f.verts, 3));
    g.setIndex(f.tris);
    drawPick(g, true);
  } else {
    const edge = edgePicked(data, hit, e, seen);
    if (!edge) { pickHint('no edge there: click closer to one'); renderScope(); return; }
    S.pick = { part: pid, kind: 'edge', id: edge.id, said: edge.said, local: edge.local, version: data.version };
    const curve = new THREE.CatmullRomCurve3(edge.points.map((p) => new THREE.Vector3(...p)));
    drawPick(new THREE.TubeGeometry(curve, Math.max(2, edge.points.length * 2), Math.max(1, 0.003 * camera.position.distanceTo(new THREE.Vector3(...edge.centre))), 6, false));
  }
  renderScope();
}
function setPickMode(mode) {
  PICK.mode = mode;
  if (mode === 'part') clearPick();
  document.querySelectorAll('#pickBar [data-pick]').forEach((b) => b.classList.toggle('on', b.dataset.pick === mode));
  pickHint();
  renderScope();
}
// the words go to the designer, so they follow the page's units (#172)
async function respeak() {
  const was = S.pick;
  if (!was) return;
  if (was.kind === 'point') was.said = pointSaid(was.point);
  else {
    const data = await features(was.part);
    const got = (was.kind === 'face' ? data.faces : data.edges).find((x) => x.id === was.id);
    if (got) was.said = got.said;
  }
  renderScope();
}
$('pickClear').onclick = () => { clearPick(); renderScope(); };   // only the pick: the part stays
$('pickBar').onclick = (e) => { const b = e.target.closest('[data-pick]'); if (b) setPickMode(b.dataset.pick); };

// ------------------------------------------------------------------------------- the session
async function loadDesigns(select) {
  const { designs, claude } = await api('GET', '/api/designs');
  S.claude = !!claude;
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

// a design with one part shows that part's own view (#362): its action bar (Check it holds, #325), panels and cards are there
// at first look. Theo's step-stool-5 opened on the design view, which has the part's Parameters but no bar. A lone reference
// isn't shown so
function soleFor(design) {
  const parts = design.parts || [];
  return parts.length === 1 && parts[0].role !== 'fixed' ? parts[0].id : null;
}
// the part whose view the panel shows: the one picked, or a one-part design's own part unless the person asked for the whole
// design. Never the chat's scope (#364 review: scoped from the first look, "add a matching bench" revised the stool), so a
// message goes exactly as it did; S.scope stays the chip, the tree's selection and what a message is about
function shownPart() {
  return S.scope || (S.design && !S.whole ? soleFor(S.design) : null);
}
async function openDesign(slug) {
  const first = S.slug !== slug;
  S.slug = slug; S.scope = null; S.station = null;
  S.piece = null; S.focus = null; S.whole = false;     // nothing picked on the last design comes over (#364 review: its "left side")
  if (first) { S.fixes = {}; S.fixOpen = null; }      // the list is this design's; your own rows are kept per design (#318)
  if (first) { dropBuildFollow(); clearPick(); pickHint(); }    // a pick is on this design's part: never posted to another (#196 review)
  location.hash = encodeURIComponent(slug);
  if (first) showLoading(slug);
  let got;
  try { got = await api('GET', `/api/designs/${slug}`); } catch (e) { if (S.slug === slug) loadFailed(slug, e); return; }
  if (S.slug !== slug) return;                  // another design was chosen while this one loaded (#168)
  S.design = got;
  doneLoading();
  render();
  sayMissed();
  await syncParts(S.design, first);
}
// while a design loads the page isn't the old one: the new name, nothing of the old, and the chat off, so a message can't
// go to a design other than the one on screen (#173)
function pickedName(slug) {                     // its name as the dropdown has it, before its own state lands
  const pick = $('designPick').selectedOptions[0];
  return pick && pick.value === slug ? pick.textContent : slug;
}
function showLoading(slug) {
  S.opening = slug;
  S.design = null;
  for (const m of meshes.values()) scene.remove(m);
  meshes.clear();
  [...pieces3d.keys()].forEach(dropPieces);
  clearStation();
  $('inspector').innerHTML = `<h2>${esc(pickedName(slug))}</h2><div class="muted small"><span class="spin"></span>loading…</div>`;
  $('thread').innerHTML = '';
  $('tree').hidden = true;                         // hidden till the new design lands, and nothing of the old left in it (#251)
  $('tree').innerHTML = '';
  TREE.saying = null;
  $('scopeRow').hidden = true;
  $('viewHint').textContent = 'loading…';
  $('msg').disabled = true; $('send').disabled = true;
}
// it couldn't be opened: says why, and the chat stays off, as there's no design on screen to talk about
function loadFailed(slug, e) {
  $('inspector').innerHTML = `<h2>${esc(pickedName(slug))}</h2><div class="note-warn small">Couldn't open it: ${esc(plainly(e.message))}</div>`;
  $('viewHint').textContent = '';
}
function doneLoading() {
  S.opening = null;
  $('msg').disabled = false;
  if (!S.busy) $('send').disabled = false;
}

async function refresh() {
  if (!S.slug) return;
  const slug = S.slug, got = await api('GET', `/api/designs/${slug}`);
  if (S.slug !== slug) return;                  // the design was left while this was on its way (#168)
  S.design = got;
  if (S.scope && !S.design.parts.find((p) => p.id === S.scope)) S.scope = null;
  render();
  await syncParts(S.design, false);
}

function render() {
  syncRunning();
  dropOldPick();
  renderUnits(); renderTree(); renderThread(); renderInspector(); renderScope(); paint(); renderStudies();
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
  respeak();
};

function setScope(pid, piece) {
  clearPick();
  S.scope = pid;
  S.piece = piece || null;
  S.focus = null;
  if (S.station && S.station.part !== pid) clearStation();
  render();
  if (pid) $('msg').focus();
}
// the piece the chat is about. A pick says what it's about itself, and it may be on another piece than the one selected (#181)
function pieceInScope() {
  if (S.pick) return null;
  const part = S.piece && S.design ? S.design.parts.find((p) => p.id === S.scope) : null;
  return (part && (part.pieces || []).find((x) => x.key === S.piece)) || null;
}
function renderScope() {
  const lit = S.pick ? null : S.piece || null;            // a pick is the subject, so the tree stops lighting the piece (#181 review)
  if (PICK.lit !== lit) { PICK.lit = lit; renderTree(); }
  $('scopeRow').hidden = !S.scope;
  const part = S.scope && S.design ? S.design.parts.find((p) => p.id === S.scope) : null;
  const named = part ? part.name || part.id : S.scope;
  const piece = pieceInScope();
  $('scopeChip').textContent = named ? (piece ? `${named} · ${piece.name}` : named) : '';
  $('pickChip').hidden = $('pickClear').hidden = !S.pick;
  $('pickChip').textContent = S.pick ? S.pick.said : '';
  $('msg').placeholder = S.scope
    ? `What should change about ${piece ? piece.name : named}?`
    : (S.design && S.design.parts.length
      ? 'Click a part to talk about it, or ask about the whole design…'
      : 'Tell me more about it, or ask a question…');
}
$('scopeClear').onclick = () => setScope(null);

// --------------------------------------------------------------------------------- the thread
function renderThread() {
  const t = $('thread');
  const d = S.design;
  if (!d) return;
  const html = [];
  // a line of the log that isn't a record (torn, or a NaN from before CALI-86) is left out, and said
  if (d.log_skipped) html.push(`<div class="muted small">${d.log_skipped} line${d.log_skipped > 1 ? 's' : ''} of this design's log couldn't be read and ${d.log_skipped > 1 ? 'are' : 'is'} left out.</div>`);
  for (const e of d.log) {
    if (e.kind === 'created') {
      html.push(`<div class="note">Started <b>${esc(d.name)}</b> — ${esc(e.prompt)}</div>`);
    } else if (e.kind === 'clarify' && e.action === 'updated') {
      html.push(`<div class="note">Requirement changed — ${esc(e.question || '')} → <b>${esc(e.answer || '')}</b></div>`);
    } else if (e.kind === 'clarify' && e.action !== 'asked') {
      html.push(`<div class="note">Requirements recorded — ${e.answered || 0} answered, ` +
        `${e.assumed || 0} assumed.</div>`);
    } else if (e.kind === 'message') {
      html.push(`<div class="msg you">${e.scope ? `<div class="scope">on ${esc(e.scope)}</div>` : ''}` +
        `${md(e.shown || e.text)}</div>`);
    } else if (e.kind === 'reply' && e.action === 'build' && e.ok === false && S.buildBubble) {
      // the bubble still on screen says this, with its report link: read once. A reload has no bubble, and shows this
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
  // answered, nothing built, nothing building: one button (CALI-59)
  const unbuilt = !d.parts.length && !(d.clarify && d.clarify.length) && !d.building && !S.busy;
  if (unbuilt && d.claude === false) {             // a build needs Claude: said, not a job bound to fail (CALI-91)
    html.push('<div class="note">Building a new design needs a Claude key (see .env.example). Until then, open one of ours from New design.</div>');
  } else if (unbuilt) {
    html.push(`<div class="actions"><button class="primary" id="buildFirst">Build it</button>
      <span class="muted small">or say what to build first</span></div>`);
  }
  if (simplerOffered(d)) {
    html.push(`<div class="actions simpler"><button class="ghost small" data-say="Say that again in simpler words, for a kid.">
      Say it simpler</button></div>`);
  }
  if (d.proposal && !S.busy) {
    html.push(`<div class="actions">
      <button class="ok" data-say="yes">Yes, lock it in</button>
      <button data-say="no">No, one-off</button></div>`);
  }
  t.innerHTML = html.join('') || '<div class="note">Nothing yet.</div>';
  t.querySelectorAll('[data-say]').forEach((b) => { b.onclick = () => send(b.dataset.say, null); });
  wireClarify();
  if ($('buildFirst')) {
    $('buildFirst').onclick = async () => {
      const go = $('buildFirst');
      go.disabled = true;                              // a double click starts one build (#66 item 1)
      try {
        followBuild((await api('POST', `/api/designs/${S.slug}/build`)).job_id, 0);
        refresh().catch(() => {});                     // the cards go by d.building: they stop saying "press Build it"
      } catch (e) { showErr(e.message); go.disabled = false; }
    };
  }
  if (typeof d.claude === 'boolean') S.claude = d.claude;
  paintSendNote();
  if (S.buildBubble) t.append(S.buildBubble);          // a redraw mid-build keeps its progress
  if (d.building && S.following !== d.building) followBuild(d.building, ((d.running || []).find((r) => r.job === d.building) || {}).elapsed_s);
  t.scrollTop = t.scrollHeight;
}

// "Say it simpler" needs Claude: offline the answer is the facts again (CALI-92, #70 item 13). After a reply, nothing pending.
function simplerOffered(d) {
  const lastSaid = [...d.log].reverse().find((e) => e.kind === 'message' || e.kind === 'reply');
  return !!(d.claude && lastSaid && lastSaid.kind === 'reply' && lastSaid.reply && !d.proposal && !S.busy);
}

function clarifyCard(qs) {
  return `<div class="card" id="clarify">
    <h3>A few questions first</h3>
    <p class="muted small">Leave any blank and I'll use the grey suggestion, marked as a guess you can
      change later. Then I build it, check it and plan how to make it.</p>
    ${qs.map((q) => `<div class="q"><label for="q_${esc(q.id)}">${esc(q.question)}</label>
      ${q.why ? `<div class="why">${esc(q.why)}</div>` : ''}
      <input type="text" id="q_${esc(q.id)}" data-q="${esc(q.id)}" placeholder="${esc(q.default)}"></div>`).join('')}
    <div class="actions">
      <button class="primary" id="clarifyGo">Build it</button>
    </div></div>`;
}
function wireClarify() {
  const go = $('clarifyGo');
  if (!go) return;
  go.onclick = async () => {
    const answers = {};
    document.querySelectorAll('#clarify [data-q]').forEach((i) => { answers[i.dataset.q] = i.value; });
    go.disabled = true;
    // the answers, then the first build (CALI-59): one sentence in, four answers out
    try { S.design = await api('POST', `/api/designs/${S.slug}/clarify`, { answers, build: true }); render(); }
    catch (e) { showErr(e.message); go.disabled = false; }
  };
}

// the first build, said as it goes: its plan, and the part (CALI-157: the checks wait to be asked for)
const BUILD_STEPS = { plan: 'Planning its parts', build: 'Building it', measured: 'Measuring it for the parts it goes into' };
function elapsedText(s) {
  const t = Math.max(0, Math.round(s));
  return t < 60 ? `${t} s` : `${Math.floor(t / 60)} min ${t % 60} s`;
}
function authoringWords(round) {
  if (!round || round < 2) return 'writing the design';
  const word = { 2: 'second', 3: 'third', 4: 'fourth' }[round];
  return `writing the design: ${word ? `${word} try` : `try ${round}`}`;
}
// leaving a design doesn't stop its build: coming back follows it again, and the design you went to can be talked to
function dropBuildFollow() {
  S.buildBubble = null;
  if (!S.following) return;                     // nothing of a build's to let go: a chat turn in flight keeps Send off
  S.following = null; S.buildFollow = (S.buildFollow || 0) + 1; S.busy = false;
  $('send').disabled = false;
}
// how long it has run comes from the server (its elapsed seconds), so a browser whose clock is off still reads right
function buildRanFor(seconds) {
  const began = Date.now() / 1000 - (seconds || 0);
  if (!S.buildBegan || began < S.buildBegan) S.buildBegan = began;      // a clock that only goes forward
}
async function followBuild(jobId, ranFor) {
  const mine = S.buildFollow = (S.buildFollow || 0) + 1;
  S.following = jobId; S.busy = true; $('send').disabled = true;
  S.buildBegan = null;
  buildRanFor(ranFor);
  const t = $('thread');
  t.querySelectorAll('.actions').forEach((n) => n.remove());
  const cal = document.createElement('div');
  cal.className = 'msg cal';
  cal.innerHTML = `<div class="who">Caliper</div><div class="head"><span class="spin"></span>Starting…</div>
    <ol class="build-steps">${Object.entries(BUILD_STEPS).map(([k, v]) =>
      `<li data-step="${k}">${esc(v)}<span class="detail muted small"></span></li>`).join('')}</ol>`;
  t.append(cal); t.scrollTop = t.scrollHeight;
  S.buildBubble = cal;
  const head = cal.querySelector('.head');
  let at = null;
  const mark = (k, text) => {
    if (!BUILD_STEPS[k]) return;
    cal.querySelectorAll('li').forEach((li) => {
      const before = Object.keys(BUILD_STEPS).indexOf(li.dataset.step) < Object.keys(BUILD_STEPS).indexOf(k);
      li.classList.toggle('done', before || li.classList.contains('done'));
      li.classList.toggle('now', li.dataset.step === k);
    });
    at = k; said = text || BUILD_STEPS[k]; paint();
  };
  // the whole build's time: a reload or a switch of design doesn't restart it
  let said = 'Starting';
  const paint = () => { head.innerHTML = `<span class="spin"></span>${esc(said)}… <span class="muted small">${elapsedText(Date.now() / 1000 - S.buildBegan)}</span>`; };
  paint();
  const tick = setInterval(() => { if (cal.isConnected) paint(); }, 1000);
  try {
    await follow(jobId, (ev) => {
      if (ev.kind === 'wrote') refresh().catch(() => {});         // on screen as soon as it's written: its reply is still being put together
      if (ev.kind === 'step') return ev.step === 'done' ? null : mark(ev.step, ev.text);
      const li = at && cal.querySelector(`li[data-step="${at}"] .detail`);
      const line = ev.kind === 'authoring' ? authoringWords(ev.round)
        : ev.kind === 'built' ? 'it builds' : ev.kind === 'strength' ? ev.text
          : ev.kind === 'error' ? `⚠ ${ev.text}` : '';
      if (li && line) li.textContent = ` · ${line}`;
    });
  } catch (e) {
    cal.classList.add('bad'); head.innerHTML = `⚠ The build stopped: ${esc(e.message)} `;
    head.append(reportLink(e.errorId, e.message));
    cal.querySelectorAll('li.now').forEach((li) => li.classList.remove('now'));
  } finally {
    clearInterval(tick);
    if (mine === S.buildFollow) { S.busy = false; $('send').disabled = false; S.following = null; }
  }
  if (mine !== S.buildFollow) return;                            // left for another design, or followed again since
  if (!cal.classList.contains('bad')) S.buildBubble = null;      // the reply in the log says it now
  await refresh();
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
    fail(msg, errorId) {
      cal.classList.add('bad');
      head.innerHTML = `⚠ ${esc(msg)} `;
      head.append(reportLink(errorId, msg));
    },
  };
}
const STEP_TEXT = {
  started: () => '', finished: () => '', done: () => '',
  classified: (e) => (e.action === 'answer' ? 'reading the design'
    : e.action === 'author' ? `building a new part: ${e.part}`
      : e.action === 'refine' ? `revising ${e.part}`
        : e.action === 'picture' ? `putting a picture on ${e.part}`
        : e.action === 'revert' ? `rolling ${e.part} back` : e.text),
};

// a piece picked in the tree: the part is the chat's scope, and the message says which piece (#94)
function aboutPiece(text) {
  const piece = pieceInScope();
  return piece ? `About the ${piece.name}: ${text}` : text;
}
async function send(text, scope, pick, shown, typed, piece) {
  if (S.busy || S.opening || !text.trim()) return;      // never to a design that isn't on screen yet (#173)
  if (!S.slug) return createDesign(text);
  S.busy = true; $('send').disabled = true;
  const sent = S.pick;                          // the pick this message is about: one made while it's answered isn't it
  const live = liveTurn(shown || text, scope);
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/chat`, { message: text, scope, ...(pick ? { pick } : {}), ...(shown ? { shown } : {}), ...(typed ? { typed } : {}), ...(piece != null ? { piece } : {}) });
    trackJob(job_id, { kind: 'chat', part: scope || null, text: 'reading your message…' }).done.catch(() => {});   // the overlay (#363)
    await follow(job_id, (ev) => live.step(ev));
    S.busy = false;
    if (shown && S.pick === sent) clearPick();                     // it's been used; after an error it stays, so asking again doesn't mean picking again
    await refresh();
  } catch (e) {
    live.fail(e.message, e.errorId);
  } finally {
    S.busy = false; $('send').disabled = false;
  }
}
$('composer').onsubmit = (e) => {
  e.preventDefault();
  if (S.opening) return;                        // what's typed stays
  const text = $('msg').value;
  $('msg').value = '';
  const shown = S.pick ? `About this ${S.pick.said}: ${text}` : null;     // their own bubble: no coordinates (#181)
  const said = aboutPick(S.pick, aboutPiece(text)), pick = pickPosted(text);
  send(said, S.scope, pick, shown, text);     // what was typed, apart from the chip's context (#288 review)
};
$('msg').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('composer').requestSubmit(); }
});

// a brand-new design: one sentence, a few questions, then it's built (CALI-59). Or open one of ours.
function startNew() {
  // remember where we were: the button sits beside the design picker and is easy to hit by mistake
  const was = S.slug ? { slug: S.slug, name: S.design ? S.design.name : S.slug } : null;
  S.slug = null; S.design = null; S.scope = null; dropBuildFollow();
  clearPick(); pickHint();                        // nor to a design that doesn't exist yet (#196 review)
  for (const m of meshes.values()) scene.remove(m);
  meshes.clear(); clearStation();
  [...pieces3d.keys()].forEach(dropPieces);
  doneLoading();                                  // whatever was loading is dropped when it lands (#173)
  $('viewHint').textContent = '';
  history.replaceState(null, '', location.pathname);
  $('inspector').innerHTML = `<div class="empty">The answers show up here: what it is, whether it works, what to
    buy and how to make it.</div>`;
  $('scopeRow').hidden = true;
  $('thread').innerHTML = `<div class="card welcome">
    <h3>What do you want to make?</h3>
    <p class="muted small">Say it in a sentence: what it is, what it's for, what it's made of. I'll ask a few
      questions, then build it, check it holds and plan how to make it with your tools.</p>
    <div class="say"><textarea id="newPrompt" rows="3"
      placeholder="a step stool so my kid can reach the sink, from 3/4 in plywood"></textarea>
      ${micButton('newPrompt')}</div>
    <p class="small muted" id="newNote">${S.claude ? TO_CLAUDE : NEEDS_KEY}</p>
    <div class="actions"><button class="primary" id="newGo">Start</button>
      ${was ? `<button id="newBack" class="ghost">← back to ${esc(was.name)}</button>` : ''}</div>
    <div id="sampleRow" class="samples"></div></div>`;
  $('msg').placeholder = 'Or type it here…';
  $('newGo').onclick = () => createDesign($('newPrompt').value);
  $('newPrompt').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); createDesign($('newPrompt').value); }
  });
  if (was) $('newBack').onclick = () => { $('designPick').value = was.slug; openDesign(was.slug); };
  wireMics($('thread'));
  paintSendNote();
  $('newPrompt').focus();
  showSamples();
}
async function showSamples() {
  let got;
  try { got = await api('GET', '/api/samples'); } catch (e) { return; }
  const row = $('sampleRow');
  if (!row || !got.samples.length) return;
  row.innerHTML = `<div class="muted small">Or open one of ours and look around:</div>` + got.samples.map((x) =>
    `<button class="sample" data-sample="${esc(x.name)}"><b>${esc(x.title)}</b><span>${esc(x.about)}</span></button>`).join('');
  row.querySelectorAll('[data-sample]').forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      try { await loadDesigns((await api('POST', `/api/samples/${encodeURIComponent(b.dataset.sample)}`)).slug); }
      catch (e) { showErr(e.message); b.disabled = false; }
    };
  });
}

// ---------------------------------------------------------------------- talking instead of typing (CALI-59)
// The browser's own speech recognition where it has one. Without it, the Mac's dictation types into any text
// box, so the button says how to start that.
const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
let listening = null;
function micButton(target) {
  return `<button type="button" class="mic ghost" data-mic="${target}" title="talk instead of typing">🎤</button>`;
}
function wireMics(root) {
  root.querySelectorAll('[data-mic]').forEach((b) => { b.onclick = () => dictate($(b.dataset.mic), b); });
}
function micTip(btn, text) {
  let tip = btn.parentElement.querySelector('.mic-tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'mic-tip'; btn.parentElement.append(tip); }
  tip.textContent = text;
  clearTimeout(micTip.t); micTip.t = setTimeout(() => tip.remove(), 9000);
}
// CALI-91 (rule 6): a person's words never leave the machine unless they send them. A browser's speech
// recognition sends the audio to its maker (Google, in Chrome), so the first press asks, and the answer is kept for
// that browser. Where the browser can recognise speech on the device itself, it listens there and doesn't ask.
const DICTATION = "Use your computer's dictation: on a Mac, press the 🎤 key (or Fn twice).";
const MIC_ASK = 'Your browser turns speech into words by sending it to its maker (Google, in Chrome). Talk anyway?';
const MIC_KEY = 'caliper.mic';
function micAnswer() { try { return localStorage.getItem(MIC_KEY); } catch (e) { return null; } }
function micRemember(v) { try { localStorage.setItem(MIC_KEY, v); } catch (e) { /* forgotten: it asks again */ } }
async function onDevice(lang) {
  try { return !!(Speech && Speech.available && (await Speech.available({ langs: [lang], processLocally: true })) === 'available'); }
  catch (e) { return false; }
}
async function dictate(box, btn) {
  if (listening) { listening.stop(); return; }
  box.focus();
  if (!Speech) return micTip(btn, DICTATION);
  const lang = navigator.language || 'en-US';
  const local = await onDevice(lang);
  if (!local && micAnswer() !== 'yes') return micAsk(box, btn, lang);
  listen(box, btn, lang, local);
}
function micAsk(box, btn, lang) {
  let ask = btn.parentElement.querySelector('.mic-ask');
  if (!ask) { ask = document.createElement('div'); ask.className = 'mic-tip mic-ask'; btn.parentElement.append(ask); }
  const no = micAnswer() === 'no';
  ask.innerHTML = `${esc(no ? `${DICTATION} Or let the browser listen: it sends what you say to its maker.` : MIC_ASK)}
    <button type="button" class="small" data-talk="1">Talk</button>${no ? '' : '<button type="button" class="small ghost" data-type="1">Type instead</button>'}`;
  ask.querySelector('[data-talk]').onclick = () => { micRemember('yes'); ask.remove(); listen(box, btn, lang, false); };
  const type = ask.querySelector('[data-type]');
  if (type) type.onclick = () => { micRemember('no'); ask.remove(); box.focus(); };
}
function listen(box, btn, lang, local) {
  const rec = new Speech();
  rec.lang = lang; rec.interimResults = true; rec.continuous = false;
  if (local) rec.processLocally = true;            // on this device: nothing leaves it
  const start = box.value ? box.value.replace(/\s*$/, ' ') : '';
  rec.onresult = (e) => { box.value = start + [...e.results].map((r) => r[0].transcript).join(''); };
  rec.onerror = (e) => micTip(btn, e.error === 'not-allowed' || e.error === 'service-not-allowed'
    ? `The browser isn't allowed to listen. ${DICTATION}` : `I didn't catch that (${e.error}). Try again, or: ${DICTATION}`);
  rec.onend = () => { listening = null; btn.classList.remove('on'); };
  try { rec.start(); listening = rec; btn.classList.add('on'); micTip(btn, 'Listening… press 🎤 again to stop.'); }
  catch (e) { micTip(btn, DICTATION); }
}
// what's typed goes to Claude: said under the first-run box, and under the chat box until the first message
// is sent (CALI-91). Without a key nothing is sent, and a first build can't run: that's said instead
const TO_CLAUDE = "What you type goes to Claude (Anthropic's AI) to design it.";
const NEEDS_KEY = 'Building a new design needs a Claude key (see .env.example). Until then, open one of ours below.';
function sendNote(d) {
  if (!S.claude) return '';
  return d && (d.log || []).some((e) => e.kind === 'message') ? '' : TO_CLAUDE;
}
function paintSendNote() { const n = $('sendNote'); if (n) n.textContent = sendNote(S.slug ? S.design : null); }
wireMics(document);
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
// ------------------------------------------------------------- a part's numbers, set by hand (#108, the mockup)
// Exact numbers, no Claude call. Lengths in the person's units; what's typed is sent as typed and the server converts,
// checks and builds. Rebuild writes everything changed as one version.
const paramKey = (p) => `${S.slug}/${p.id}/${p.version}/${S.design.display_units}`;
function inchText(mm) {
  const inch = mm / IN, x32 = Math.round(inch * 32);
  if (Math.abs(inch * 32 - x32) > 0.02) return `${+inch.toFixed(3)}`;
  const whole = Math.floor(x32 / 32), rest = x32 - whole * 32, g = gcd(rest, 32);
  return rest ? `${whole ? `${whole} ` : ''}${rest / g}/${32 / g}` : `${whole}`;
}
const isLength = (e) => e.unit === 'mm';
const paramText = (e, v) => (isLength(e) && inches() ? inchText(v) : `${+Number(v).toFixed(3)}`);
const paramUnit = (e) => (isLength(e) ? (inches() ? 'in' : 'mm') : e.unit === 'deg' ? 'deg' : '');
// a number in plain words: its comment, unless the comment is only a quantity ("12 in", "~10.5", "18 in base"); then its name
const PARAM_WORD = { dia: 'diameter', bot: 'bottom', t: 'thickness', r: 'radius', h: 'height', w: 'width', d: 'depth', l: 'length' };
function paramName(e) {
  const note = (e.note || '').replace(/\s*\([^)]*\)?\s*$/, '')
    .replace(/^~?\d[\d./]*([\s-]+\d+\/\d+)?\s*(mm|in\b|inch(es)?\b|"|″)?[\s,;:]*/i, '')   // and the comma after it (#267 review)
    .replace(/[\s(]*\b(mm|in|inches|deg|degrees)\b\)?\.?\s*$/i, '').trim();
  const said = note.split(/\s+/).length >= 2 ? note : e.name.split('_').map((w) => PARAM_WORD[w] || w).join(' ');
  return said.charAt(0).toUpperCase() + said.slice(1);
}
// what's typed, as a number and (for a length) its unit: 12.7, 1/2, 1 1/4, 3 mm, 2"; null if it isn't one
function readNumber(text, e) {
  let t = String(text).trim(), unit;
  if (isLength(e)) {
    const m = t.match(/^(.*?)\s*(mm|in|"|″)$/i);
    if (m) { t = m[1]; unit = m[2].toLowerCase() === 'mm' ? 'mm' : 'in'; } else unit = inches() ? 'in' : 'mm';
  }
  const f = t.match(/^(?:(\d+)\s+)?(\d+)\/(\d+)$/);
  if (f) return +f[3] ? { value: +(f[1] || 0) + +f[2] / +f[3], ...(unit ? { unit } : {}) } : null;
  return /^-?(\d+\.?\d*|\.\d+)$/.test(t) ? { value: +t, ...(unit ? { unit } : {}) } : null;
}
function paramRange(e) {
  if (!e.range) return '';
  const u = paramUnit(e);
  return `${paramText(e, e.range[0])} to ${paramText(e, e.range[1])}${u ? ` ${u}` : ''}`;
}
// why this can't be sent, or '': the server checks again and has the last word
function paramProblem(e, read) {
  if (!read) return "That isn't a number.";
  if (e.unit === 'count' && !Number.isInteger(read.value)) return 'A whole number.';
  const v = read.unit === 'in' ? read.value * IN : read.value;
  return e.range && (v < e.range[0] - 1e-9 || v > e.range[1] + 1e-9) ? `Must be ${paramRange(e)}.` : '';
}
function paramRows(st) {
  return st.list.map((e) => {
    const shown = paramText(e, e.value), draft = st.drafts[e.name], text = draft != null ? draft : shown;
    const edited = text.trim() !== shown, read = edited ? readNumber(text, e) : null;
    const v = read && (read.unit === 'in' ? read.value * IN : read.value);
    const changed = edited && (!read || Math.abs(v - e.value) > 1e-6);          // 100.0 for 100, or 0.375 for 3/8, isn't a change (#171)
    return { e, shown, text, changed, read, problem: changed ? paramProblem(e, read) : '' };
  });
}
function paramsHtml(p, st, done) {
  const rows = paramRows(st), dirty = rows.filter((r) => r.changed), blocked = dirty.some((r) => r.problem);
  const body = rows.map(({ e, shown, text, changed, problem }) => {
    const u = paramUnit(e), note = problem || [changed ? `was ${shown}${u ? ` ${u}` : ''}` : '', changed ? paramRange(e) : '',
      e.read ? '' : "its build doesn't use this"].filter(Boolean).join(' · ');
    return `<div class="prow${changed ? ' changed' : ''}${problem ? ' bad' : ''}">
      <label for="param-${esc(e.name)}" title="${esc(e.name)}">${esc(paramName(e))}</label>
      <input id="param-${esc(e.name)}" data-param="${esc(e.name)}" value="${esc(text)}" autocomplete="off" spellcheck="false"${st.saving ? ' disabled' : ''}>
      <span class="punit">${esc(u)}</span></div>${note ? `<div class="pnote${problem ? ' bad' : ''}">${esc(note)}</div>` : ''}`;
  }).join('');
  const foot = dirty.length ? `<div class="pfoot"><span class="small muted">Rebuilds as v${p.version + 1}, then re-checks the whole design.</span>
    <button class="primary" data-param-rebuild="1"${blocked || st.saving ? ' disabled' : ''}>${st.saving ? 'Rebuilding…' : 'Rebuild'}</button></div>` : '';
  const said = done && done.part === p.id && done.version === p.version ? `<div class="pdone">v${done.version} written: ${esc(done.said)} set exactly as typed; the whole design re-measured.</div>
    ${done.followed ? `<div class="pnote">${esc(done.followed.charAt(0).toUpperCase() + done.followed.slice(1))}.</div>` : ''}
    ${done.warning ? `<div class="pnote warn">${esc(done.warning)}.</div>` : ''}${(done.notes || []).map((n) => `<div class="pnote">${esc(n)}.</div>`).join('')}` : '';
  const head = paramsHead(p, rows);
  return `<details class="params psec t-${head.tone}" id="paramSec"${paramsOpen() ? ' open' : ''}><summary class="phead">
      <span class="qmark">${QMARK[head.tone]}</span><b>Parameters</b><span class="small muted">${esc(head.answer)}</span></summary>
    <div class="small muted">set by hand, no Claude call</div>
    ${body}${foot}${st.err ? `<div class="pnote bad">${esc(st.err)}</div>` : ''}${said}</details>`;
}
// Parameters' own header (#325): how many, the sheet's thickness where it has one, and a mark where something needs a
// look: a number that won't do (✗), one typed and not rebuilt yet, one saved outside its range, or a part changed since
// its check (!)
function paramsHead(p, rows) {
  const n = rows.length, bad = rows.filter((r) => r.problem), dirty = rows.filter((r) => r.changed);
  const out = rows.filter((r) => r.e.range && (r.e.value < r.e.range[0] - 1e-9 || r.e.value > r.e.range[1] + 1e-9));
  const run = p.loads ? (loadRuns(p.id) || [])[0] : null, since = !!(run && run.version !== p.version);
  const sheet = rows.find((r) => /(^|_)(t|ply|thick|sheet)(_|$)|thick/i.test(r.e.name));
  const what = `${n} number${n === 1 ? '' : 's'}${sheet ? ` · ${paramName(sheet.e)} ${sheet.shown}${paramUnit(sheet.e) ? ` ${paramUnit(sheet.e)}` : ''}` : ''}`;
  if (bad.length) return { tone: 'bad', answer: `${what} · ${bad.length} won't do` };
  if (dirty.length) return { tone: 'warn', answer: `${what} · ${dirty.length} changed, not rebuilt yet` };
  if (out.length) return { tone: 'warn', answer: `${what} · ${paramName(out[0].e)} is outside its range` };
  if (since) return { tone: 'warn', answer: `${what} · changed since its check` };
  return { tone: 'info', answer: what };
}
function paramsOpen() {                          // open by default; kept as it was left
  try { return localStorage.getItem('caliper.params.open') !== '0'; } catch (e) { return true; }
}
function paramView(p) {
  if (!S.design || !p || !p.scripted || p.role === 'fixed') return '';
  if (p.carved) {                                     // its shape is the carve's mesh: numbers would only move its loads (#171)
    return `<section class="params"><div class="phead"><b>Parameters</b></div>
      <div class="pnote">It's been carved, so its numbers don't change its shape. Say "roll it back" to take the carve off and set them.</div></section>`;
  }
  const st = S.params && S.params.key === paramKey(p) ? S.params : null;
  if (!st) { setTimeout(() => loadParams(p), 0); return ''; }
  return st.list && st.list.length ? paramsHtml(p, st, S.paramsDone) : '';
}
async function loadParams(p) {
  if (!S.design) return;                          // the design was left while this waited its turn (#173's loading state)
  const key = paramKey(p);
  if (S.params && S.params.key === key) return;
  S.params = { key, list: null, drafts: {}, saving: false, err: null };
  let list = [];
  try { list = (await api('GET', `/api/designs/${S.slug}/parts/${p.id}/params`)).params; } catch (e) { /* no numbers to set */ }
  if (S.params.key !== key) return;
  S.params.list = list;
  drawParams(p);
  const said = document.querySelector('#paramBox .pdone');          // the redraw went back to the top of the cards
  if (said) said.scrollIntoView({ block: 'center' });
}
let paramRefocus = false;
function refocusParam(id, at) {
  const el = $(id);
  if (!el) return;
  paramRefocus = true; el.focus(); el.setSelectionRange(at[0], at[1]); paramRefocus = false;
}
function drawParams(p) {
  const box = $('paramBox');
  if (!box) return;
  const was = document.activeElement, id = was && was.dataset && was.dataset.param ? was.id : null;
  const at = id ? [was.selectionStart, was.selectionEnd] : null;
  box.innerHTML = paramView(p);
  if (id) refocusParam(id, at);
}
// the plain names and the numbers as typed, as the mockup says it: no script names (#171)
function paramsSaid(rows) {
  return rows.map((r) => { const u = paramUnit(r.e); return `${paramName(r.e)} ${r.text.trim()}${u && !/[a-z"″]$/i.test(r.text.trim()) ? ` ${u}` : ''}`; }).join(', ');
}
// a thinner sheet's Use (#295): the sheets' thickness number set, as the Parameters panel sets it, with no designer and
// no material in words; where there's no such number, the sheet named, never what's printed on it
function sheetUse(run, label, mm, now, piece, opts = {}) {   // a plate row is one piece's: its own number, never another sheet's (#303)
  const sheet = run.sheet || {};
  const param = piece ? (sheet.pieces || {})[piece] : sheet.param;
  // what it does, in its own words, and waiting while a step is picked, so it can't be read as that step's (#297)
  const word = esc(opts.text || 'Use'), off = opts.off ? ` disabled title="${esc(opts.off)}"` : '';
  if (param) return `<button class="ghost" data-use-param="${esc(param)}" data-use-mm="${mm}"${off}>${word}</button>`;
  const name = sheet.name || (typeof run.material === 'string' ? run.material : (run.plate_material || {}).name) || 'plywood';
  const plain = /printed|\bpla\b|petg/i.test(name) ? 'plywood' : name;          // an older run's headline: never the print
  const said = piece ? `Make the ${piece} ${label} ${plain}, not ${now || sheet.now || 'what it is'}`
    : `Make the ${sheet.now || now || 'sheet'} ${plain} ${label}`;
  return `<button class="ghost" data-use-t="${esc(said)}"${off}>${word}</button>`;
}
// a picked step's own action, by the table it was picked in: the same adopt as the bar's Cut these holes (#297)
function stepAction(p, run, on) {
  const st = run.stations.find((x) => x.index === on);
  if (!st || st.estimate || !on) return '';
  if (run.version != null && run.version !== p.version) {
    return `<div class="small" style="margin-top:6px">This lightening is of v${run.version}, and the part has changed since
      (it's v${p.version}): lighten it again.</div>`;
  }
  const no = run.not_trusted || (!holdsHere(st) ? `It can't be used: ${st.verdict ? st.verdict.word : 'not checked'}` : '');
  return `<div class="actions"><button class="primary" data-step-adopt="${on}"${no ? ` disabled title="${esc(no)}"` : ''}>Cut step ${on}'s holes into ${esc(p.id)} (makes v${p.version + 1})</button></div>${offWhy(no)}`;
}
// why a button is greyed, as a line beside it, not only its title: a phone has no hover (#306 review)
function offWhy(why) {
  return why ? `<div class="small muted" data-off-why="1">${esc(why)}</div>` : '';
}
// a Lighten step picked on this part: its number, else 0. While one is, a sheet row's Ask for waits, so it can't be
// read as that step's (#297, and the strength panel's rows too: #306 review)
function pickedStep(p) {
  return S.station && S.station.part === p.id && (S.design.lighten_runs || []).some((r) => r.id === S.station.run)
    ? S.station.index : 0;
}
function askWait(n) {
  return n > 0 ? `Step ${n} is picked: this asks for another sheet, not step ${n}'s holes` : '';
}
// a case the check can't call: its own why, and the check that made the number named, never "the FEA" where another
// check governs (#297, Theo's v6: "the FEA read 2.2x, too coarse to see its walls" was the top's plate check)
// ``lead``: its word first ("not checked: …"), where no badge beside it says it already (#306 review: "not checked not checked")
function caseWhy(c, run, lead = true) {
  const v = c.verdict || {};
  const said = (t) => (lead ? `${coarseWord(c)}: ${t}` : t.charAt(0).toUpperCase() + t.slice(1));
  if (v.why) return said(esc(v.why));
  // the server's own words for whose check it is ("the step's plate check", load_study.governing_words: #306 review)
  const by = c.governs === 'plate' || c.governs === 'buckling'
    ? c.governing || (c.governs === 'plate' ? 'the plate check' : 'the buckling check') : '';
  return by ? said(`${esc(by)} read ${sx(c.safety, run.min_safety)}; what it couldn't see isn't checked`)
    : said(`the FEA read ${sx(c.safety, run.min_safety)}, too coarse to see its walls`);
}
// a run the check can't call: why, first, in one line, before the scenarios (#297)
function runReason(run) {
  const v = run.verdict || {};
  if (!['unchecked', 'unresolved'].includes(v.kind) || !v.why) return '';
  return `<div class="small" data-reason="1" style="margin-top:6px;color:var(--amber)"><b>${esc(v.word || 'not checked')}:</b> ${esc(v.why)}</div>`;
}
async function useParam(p, name, mm) {
  try {
    const got = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/params`, { name, value: mm, unit: 'mm' });
    S.design = got.design;
    render();
    await syncParts(S.design, false);
  } catch (e) { showErr(plainly(e.message)); }
}
async function rebuildParams(p) {
  const st = S.params, rows = paramRows(st).filter((r) => r.changed);
  if (!rows.length || st.saving || rows.some((r) => r.problem)) return;
  st.saving = true; st.err = null; drawParams(p);
  try {
    const got = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/params`, { values: rows.map((r) => ({
      name: r.e.name, value: r.read.value, ...(r.read.unit ? { unit: r.read.unit } : {}) })) });
    S.paramsDone = { part: p.id, version: got.version, said: paramsSaid(rows), warning: got.warning, notes: got.notes,
      followed: got.followed };                    // the parts that read these numbers moved too: said (#271 review)
    S.design = got.design;
    render();
    await syncParts(S.design, false);             // the model on screen is the new one, not the one it was (#171)
  } catch (e) { st.saving = false; st.err = plainly(e.message); drawParams(p); }
}
function wireParams(p) {
  const box = $('paramBox');
  if (!box || !p) return;
  box.oninput = (e) => {
    if (!e.target.dataset.param || !S.params) return;
    S.params.drafts[e.target.dataset.param] = e.target.value; S.params.err = null; S.paramsDone = null;
    drawParams(p);
  };
  // a click selects the number, so typing replaces it: after the click's own caret, and never when a redraw puts it back
  box.addEventListener('focusin', (e) => { const el = e.target; if (el.dataset.param && !paramRefocus) setTimeout(() => el.select(), 0); });
  box.onclick = (e) => { if (e.target.closest('[data-param-rebuild]')) rebuildParams(p); };
  box.onkeydown = (e) => { if (e.key === 'Enter' && e.target.dataset.param) { e.preventDefault(); rebuildParams(p); } };
}

function renderInspector() {
  const el = $('inspector'), d = S.design;
  if (!d) return;
  const shown = shownPart(), p = shown && d.parts.find((x) => x.id === shown);
  const was = document.activeElement, typing = was && was.dataset && was.dataset.param ? [was.id, was.selectionStart, was.selectionEnd] : null;
  el.innerHTML = `<div id="jobNote"></div>${p ? partView(p) : designView(d)}`;
  wireInspector(p);
  wireParams(p || (d.parts.length === 1 ? d.parts[0] : null));
  if (typing) refocusParam(typing[0], typing.slice(1));   // a redraw mid-number
  paintJobs();
}

// one rule on a part, with its verdict as measured on this version, and what it measured where it doesn't hold
// (#137 item 1: the bar stool's locked shell wall broke, and this list showed no mark)
function ruleItem(r) {
  const v = r.verdict;
  return `<li class="rule">🔒 ${v ? `${verdictBadge(v)} ` : ''}<b>${esc(r.id)}</b> <code>${esc(r.expr)}</code>${
    v && v.kind !== 'holds' && r.said ? `<div class="small">${esc(r.said)}</div>` : ''}</li>`;
}
// the parts' own rules, measured, where the design has no checks of its own (#137 item 1: "Nothing to measure yet"
// over a rule that fails)
function partChecks(d) {
  const results = d.parts.flatMap((p) => (p.rules || []).filter((r) => r.status));
  return results.length ? { results } : null;
}
function checks(report, only) {
  if (!report) return '<div class="empty">Nothing to measure yet.</div>';
  const rows = report.results.filter((r) => !only || only(r));
  if (!rows.length) return '<div class="empty">No checks.</div>';
  return '<ul class="list">' + rows.map((r) => `<li class="check ${r.status}">
    <span class="s">${r.status === 'pass' ? '✓' : r.status === 'deferred' ? '·' : '✗'}</span>
    <span><b>${esc(r.id)}</b> <code>${esc(r.expr)}</code>${r.actual != null && r.status !== 'pass'
      ? ` <span class="muted">→ ${esc(typeof r.actual === 'number' ? r.actual.toFixed(3) : r.actual)}</span>` : ''}${r.status === 'deferred' && r.detail
      ? ` <span class="muted">· ${esc(r.detail)}</span>` : ''}</span>
    </li>`).join('') + '</ul>';
}

// the design's checks in one badge (CALI-35, #103 review): a check that's only waiting (deferred) is never red, and
// never green either: "all checks pass" only when every check ran and passed
function reportBadge(rep) {
  if (!rep || !rep.results.length) return '';
  const waiting = rep.results.filter((r) => r.status === 'deferred').length;
  const passed = rep.results.filter((r) => r.status === 'pass').length;
  if (rep.results.some((r) => r.status === 'fail' || r.status === 'error')) return '<span class="badge bad">checks failing</span>';
  if (waiting === rep.results.length) return '<span class="badge">checks wait for its parts</span>';
  if (waiting) return `<span class="badge">${passed} pass · ${waiting} not checked yet</span>`;
  return '<span class="badge ok">all checks pass</span>';
}
function designView(d) {
  const rep = d.report;
  const status = reportBadge(rep);
  const what = `<div class="muted small">${esc(d.prompt)}</div>
    <h4>Requirements</h4>
    ${d.requirements.length ? '<ul class="list">' + d.requirements.map((r) => `<li>${esc(r.question)}
      <div><b>${esc(r.answer)}</b>${r.source === 'assumed' ? ' <span class="badge">assumed</span>' : ''}</div></li>`).join('') + '</ul>'
    : '<div class="empty">None yet.</div>'}
    ${(d.shop_offers || []).map((o, i) => `<div class="small" style="margin-top:6px">${esc(o.text)}
      ${o.kind === 'note' ? `<button class="ghost small" data-shopoffer="${i}" data-add="0">OK</button>`
        : `<button class="ghost small" data-shopoffer="${i}" data-add="1">Add it</button>
      <button class="ghost small" data-shopoffer="${i}" data-add="0">No</button>`}</div>`).join('')}
    ${d.plan ? `<h4>The plan <span class="badge">${d.plan.status === 'review' ? 'to review' : 'saved'}</span></h4>
      <ol class="list">${d.plan.parts.map((x) => `<li><b>${esc(x.id.replace(/_/g, ' '))}</b>
        ${x.role === 'fixed' ? (x.source === 'assumed' ? '<span class="badge">assumed: you have it? say if not</span>' : '<span class="badge ref">you have it</span>') : ''}${x.built ? '<span class="badge ok">built</span>' : ''}
        <div class="muted small">${esc(x.what)}${x.made ? ` · ${esc(x.made)}` : ''}${x.mounts_on.length
          ? ` · on the ${x.mounts_on.map((m) => esc(m.replace(/_/g, ' '))).join(' and the ')}` : ''}</div></li>`).join('')}</ol>
      ${d.plan.dropped ? `<div class="small muted">${esc(d.plan.dropped[0].toUpperCase() + d.plan.dropped.slice(1))}.</div>` : ''}
      ${(d.plan.dropped_rules || []).map((x) => `<div class="small" style="color:var(--amber)">Left out ${esc(x)}.</div>`).join('')}
      ${(d.plan.notes || []).length ? `<div class="small muted">By the numbers: ${esc(d.plan.notes.join('; '))}.</div>` : ''}
      ${d.plan.numbers.length ? '<div class="small"><b>The numbers they share</b></div><ul class="list">'
        + d.plan.numbers.map((n) => `<li class="small">${esc(n)}</li>`).join('') + '</ul>' : ''}
      ${d.plan.checks.length ? '<div class="small"><b>Checked between them</b></div><ul class="list">'
        + d.plan.checks.map((c) => `<li class="small"><b>${esc(c.id)}</b> <code>${esc(c.expr)}</code>${c.source === 'assumed'
          ? ` <span class="badge">assumed: not checked until you keep it</span>${c.why ? ` <span class="muted">${esc(c.why)}</span>` : ''}
            <button class="ghost small" data-plankeep="${esc(c.id)}">Keep</button>` : ''}</li>`).join('') + '</ul>' : ''}` : ''}
    <h4>Parts</h4>
    ${d.parts.length ? '<ul class="list">' + d.parts.map((p) => `<li><span class="partlink" data-part="${esc(p.id)}">${esc(p.name || p.id)}</span>
      <span class="muted small">v${p.version}</span>
      ${p.role === 'fixed' ? '<span class="badge ref">reference</span>' : ''}
      ${p.origin === 'whittled' ? '<span class="badge whittled">whittled</span>' : ''}
      <div class="muted small">${esc(p.intent)}</div>
      ${p.bbox ? `<div class="small">${sizeText(p.bbox.size)}</div>` : ''}</li>`).join('') + '</ul>'
    : '<div class="empty">None yet — say what to build first.</div>'}
    ${Object.keys(d.part_errors || {}).length ? '<h4>Won\'t build</h4><ul class="list">' +
      Object.entries(d.part_errors).map(([k, v]) => `<li><b>${esc(k)}</b> <span class="muted small">${esc(v)}</span></li>`).join('') + '</ul>' : ''}`;
  const work = `<h4>Scorecard</h4><div id="scoreBox">${scoreView(d)}</div>
    <h4>Design checks</h4>
    ${checks(rep || partChecks(d))}`;
  const buy = d.parts.some((p) => p.built) ? `<h4>Weight &amp; balance</h4><div id="balanceBox">${balanceView()}</div>` : '';
  const make = `<h4>Build package <span class="badge">to the shop</span></h4><div id="relBox">${releaseView(d)}</div>`;
  const back = soleFor(d) ? `<div class="small"><button class="linkish" data-whole="0">◂ ${esc(d.parts[0].name || d.parts[0].id)}: check it, fix it, make it</button></div>` : '';
  return `<h2>${esc(d.name)} ${status}</h2>${back}
    ${d.parts.length === 1 ? `<div id="paramBox">${paramView(d.parts[0])}</div>` : ''}
    ${cardsView({ what, work, buy, make })}`;
}

// ------------------------------------------------------------- the four questions (spec step 1)
// What is it? Will it work? What do I buy? How do I make it? Each card's top lines are the answer, written on
// the server (answers.py) from what's already measured, so anyone can read them; "the numbers" under each is
// today's panels for that question, and once someone opens it, it stays open for them.
const QUESTIONS = [['what', 'What is it?'], ['work', 'Will it work?'], ['buy', 'What do I buy?'], ['make', 'How do I make it?']];
const QMARK = { ok: '✓', warn: '!', bad: '✗', info: '·' };
const GOTO = { load: 'loadBox', frame: 'frameBox', patterns: 'patternBox', release: 'relBox', trial: 'trialBox',
  carve: 'loadBox' };                 // the carve's panel is under Will it hold? (#89 item 6)

function answersKey() {               // what the answers depend on: a change to any of it asks again
  const d = S.design;
  const runs = (list) => (list || []).map((r) => [r.id, r.status]);   // a finished carve or Lighten changes the offers (#159)
  return JSON.stringify([S.slug, shownPart(), d.building || null, d.parts.map((p) => [p.id, p.version, p.role]), (d.load_runs || []).length,
    runs(d.carve_runs), runs(d.lighten_runs),
    (d.pattern_runs || []).length, (d.frame_runs || []).length, (d.scorecards || []).length,
    (d.releases || []).length, ((d.goals || {}).checks || []).length, S.shopKey, d.display_units]);
}
// a card's lines, and under a part's Will it work? its Things to fix (#300): one painter, for the first draw and the
// fill when its answers come in (a fill with qlines alone dropped the list)
function cardLines(k, c) {
  return qlines(c);                             // Things to fix is a section of the card now (#325)
}
function qlines(c) {
  if (!c) return '<div class="qline muted"><span class="spin"></span>answering…</div>';
  if (!c.lines.length) return `<div class="qline muted">${esc(c.hint || 'Nothing to say yet.')}</div>`;
  const offers = c.lines.filter((ln) => ln.better);
  return c.lines.filter((ln) => !ln.better).map((ln, i) => `<div class="qline q-${ln.status}${i === 0 ? ' top' : ''}${gotoFor(ln) ? ' go' : ''}"
    ${gotoFor(ln) ? `data-goto="${gotoFor(ln)}"` : ''}>${esc(ln.text)}</div>
    ${(ln.links || []).length ? `<div class="qlinks">${ln.links.map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank"
      rel="noopener">${esc(l.label)}</a>`).join('')}</div>` : ''}`).join('')
    + betterLines(c, offers)
    + (c.promise ? `<div class="qpromise">${esc(c.promise)}</div>` : '');
}
// Make it better (#92, the mockup Theo approved): what would improve it, what that costs, and a button for it
function betterLines(c, offers) {
  if (!offers.length) return '';
  return `<div class="qbetter"><div class="qbetter-h">Make it better</div>${offers.map((ln) => {
    const i = c.lines.indexOf(ln);
    return `<div class="qoffer"><div class="qoffer-t">${esc(ln.lead)}.<span class="qoffer-c">${esc(ln.cost)}</span></div>
      ${ln.button ? `<button class="ghost" data-better="${i}" data-better-action="${esc(ln.action)}" data-better-part="${esc(ln.part)}" data-card="${esc(c.key)}"${ln.disabled || (ln.action === 'carve' && S.carveJob[carveKey(ln.part)]) ? ' disabled' : trackedFor(ln.action, ln.part) ? ' disabled data-job-off="1"' : ''}>${esc(ln.button)}</button>` : ''}</div>`;
  }).join('')}</div>`;
}
// ------------------------------------------------------------- things to fix (CALI-189, #300 slice A)
// Under Will it work?: what's measured wrong with this part, each a tick, its fix (a choice where there are two), what
// kind of change it is and what it costs; then the known limits apart, never ticked. Asked when it's opened, of this
// version. A row reworded, or one added, is the person's words: said so, never "measured".
// keyed by design and part (#318 review: another design's list painted under this one's part of the same id)
const fixKey = (part) => `${S.slug}/${part}`;
// a row's ticks and words go with it while its measurement is the same: a new number is a new row
const fixRowKey = (r) => `${r.id}|${r.problem}`;
function fixMine(part) {
  S.fixMine = S.fixMine || {};
  const k = fixKey(part);
  return (S.fixMine[k] = S.fixMine[k] || { untick: [], tick: [], words: {}, own: [], pick: {}, editing: null });
}
// ticked: by default, or, where the row says it starts unticked (an open question: it never settles itself, #318), only
// once the person ticks it
function fixTicked(r, mine) {
  const k = fixRowKey(r);
  return r.ticked === false ? (mine.tick || []).includes(k) : !(mine.untick || []).includes(k);
}
function fixRow(r, mine) {
  const k = fixRowKey(r);
  const ticked = fixTicked(r, mine);
  const pick = (mine.pick || {})[k] || 0;
  const words = (mine.words || {})[k];
  const c = r.choices[pick] || r.choices[0];
  // the problem is measured; a fix is proposed (#318 review); a row the person reworded is their words, never measured
  const fix = mine.editing === k
    ? `<input data-fix-words="${esc(k)}" value="${esc(words != null ? words : c.fix)}" style="width:80%">`
    : words != null ? `${esc(words)} <span class="badge">your words</span>`
    : (r.choices.length > 1 ? r.choices.map((x, j) => `<label><input type="radio" name="fx-${esc(k)}" data-fix-pick="${esc(k)}"
        value="${j}"${j === pick ? ' checked' : ''}> ${esc(x.fix)}</label>`).join(' <span class="muted">or</span> ') : esc(c.fix))
      + ' <span class="muted small">proposed</span>';
  return `<div class="fixrow" data-fix-row="${esc(r.id)}"><label><input type="checkbox" data-fix-tick="${esc(k)}"${ticked ? ' checked' : ''}>
      ${esc(r.problem)}${words != null ? '' : r.badge ? ` <span class="badge">${esc(r.badge)}</span>` : ' <span class="badge ok">measured</span>'}</label>
    <div class="small">${fix} ${mine.editing === k ? '' : `<button class="ghost" data-fix-word="${esc(k)}">Reword</button>`}</div>
    <div class="small muted">${esc(words != null ? 'a designer edit, in your words' : c.cost)}</div></div>`;
}
function fixesView(got, mine) {
  mine = mine || {};
  const rows = got.rows || [], own = mine.own || [];
  return `${got.error ? `<div class="small" style="color:var(--bad)">${esc(got.error)}</div>` : ''}
    ${rows.length || own.length || got.error ? '' : '<div class="small muted">Nothing measured wrong with it.</div>'}
    ${rows.map((r) => fixRow(r, mine)).join('')}
    ${own.map((o, i) => `<div class="fixrow own" data-fix-own="${i}"><label><input type="checkbox" data-fix-own-tick="${i}"${o.off ? '' : ' checked'}>
      ${esc(o.fix)}</label>
      <div class="small"><span class="badge">your words</span> <button class="ghost" data-fix-own-del="${i}">Remove</button></div>
      <div class="small muted">a designer edit, in your words</div></div>`).join('')}
    <div class="small fixadd"><input data-fix-add placeholder="add your own: “and round the top’s corners”" style="width:70%">
      <button class="ghost" data-fix-add-go="1">Add</button></div>
    ${fixGo(mine)}
    ${(got.limits || []).length ? `<div class="qbetter-h" style="margin-top:6px">Known limits</div>
      <ul class="small muted fixlimits">${got.limits.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>` : ''}`;
}
// Fix these (#300 slice B): its cost first, from the server's own plan (pressing Go ahead is the person's word for any
// designer call it names); while it runs, said; after, each row Fixed only where measured, Still open, or Not done. The
// button that asks the plan is the part's, top right (fixAct, #325)
function fixGo(mine) {
  const results = (mine.results || []).length ? `<div class="qbetter-h" style="margin-top:6px">The last fix</div><ul class="small fixresults">${
    mine.results.map((x) => `<li>${esc(x.fix || x.id || '')}: <b>${esc(x.status)}</b> <span class="muted">${esc(x.why || '')}</span></li>`).join('')}</ul>` : '';
  if (mine.running) return `<div class="small muted">fixing… ${esc(mine.running === true ? '' : mine.running)}</div>${results}`;
  if (mine.plan) return `<div class="small">It takes ${esc(mine.plan.said)}.
      <button class="primary" data-fix-go="1">Go ahead</button> <button class="ghost" data-fix-cancel="1">Not now</button></div>${results}`;
  return `${mine.error ? `<div class="small" style="color:var(--bad)">${esc(mine.error)}</div>` : ''}${results}`;
}
// Fix these, top right with the part's other actions (#325): where its list, read for this version and its newest check,
// has rows; greyed, with why, while none is ticked; "Fixing…" while it runs. It opens Things to fix (GO_OPENS) and asks
// the plan, whose cost is said there before anything runs
function fixAct(part) {
  if (!fixFresh(part)) return '';
  const got = S.fixes[fixKey(part)], mine = fixMine(part);
  if (!(got.rows || []).length && !(mine.own || []).length) return '';
  const sel = fixPicked(part), n = sel.picked.length + sel.own.length;
  const why = "nothing's ticked in Things to fix";
  const off = n ? '' : ` aria-disabled="true" data-why="${esc(why)}" title="${esc(`Not yet: ${why}`)}"`;
  return `<button class="small${n ? '' : ' off'}" id="fixGo"${off}${mine.running ? ' disabled' : ''}>${
    mine.running ? runningLabel('fix') : 'Fix these'}</button>`;
}
// the bar's Fix these drawn again, alone, as the list lands or a tick changes: the other buttons keep their wiring
function paintFixAct(part) {
  const bar = $('pacts');
  if (!bar || shownPart() !== part) return;
  const old = $('fixGo'), html = fixAct(part);
  if (old) old.remove();
  if (html) bar.insertAdjacentHTML('beforeend', html);
  const b = $('fixGo');
  if (b) b.onclick = () => fixPlan(part);
}
async function fixPlan(part) {
  const mine = fixMine(part), b = $('fixGo');
  if (b) b.disabled = true;
  mine.error = null;
  try { mine.plan = await api('POST', `/api/designs/${S.slug}/parts/${part}/fixes/plan`, fixPicked(part)); }
  catch (e) { mine.error = plainly(e.message); }
  if (b) b.disabled = false;
  paintFixes(part);
}
// what's ticked, as the server reads it: each row by its id and the choice made, the person's words where they gave them
function fixPicked(part) {
  const got = S.fixes[fixKey(part)], mine = fixMine(part);
  return {
    picked: (got.rows || []).filter((r) => fixTicked(r, mine)).map((r) => ({
      id: r.id, choice: mine.pick[fixRowKey(r)] || 0,
      ...(mine.words[fixRowKey(r)] != null ? { words: mine.words[fixRowKey(r)] } : {}) })),
    own: (mine.own || []).filter((o) => !o.off).map((o) => ({ fix: o.fix })),
  };
}
// Things to fix as a section of Will it work? (#325): its mark and its count once its list is read
function fixesSection(part) {
  const got = S.fixes && S.fixes[fixKey(part)], fresh = fixFresh(part), failed = !!got && got.error != null;
  const n = fresh ? (got.rows || []).length : null;
  const unchecked = n === 0 && !fixChecked(part);     // an empty list with nothing measured isn't a ✓ (#331 review)
  return { k: 'fix', title: 'Things to fix', tone: n == null || unchecked ? 'info' : n ? 'warn' : 'ok',
    answer: failed ? "couldn't read them" : n == null ? 'measured, with what each would take' : unchecked ? 'not checked yet'
      : n ? `${n} measured wrong` : 'nothing measured wrong',
    attrs: ` id="fixBox" data-fix-part="${esc(part)}"`,
    body: `<div id="fixBody">${fresh || failed ? fixesView(got, fixMine(part)) : '<div class="small muted">reading them…</div>'}</div>` };
}
// this design's list, read for this version and its newest check, and read: a failed read is never fresh, so the next
// draw reads it again (#331 review: a 500 from /fixes stored an empty list under the stamp and read ✓)
function fixFresh(part) {
  const got = S.fixes && S.fixes[fixKey(part)];
  return !!got && got.v === fixStamp(part) && got.error == null;
}
function fixVersion(part) { return ((S.design.parts.find((p) => p.id === part)) || {}).version; }
// what the list was read against (#331 review): the part's version and its newest strength check, so a check of the same
// version reads it again
function fixStamp(part) {
  const ids = loadRuns(part).map((r) => r.id).sort();
  return `${fixVersion(part)}|${ids.length ? ids[ids.length - 1] : ''}`;
}
function fixChecked(part) {
  const v = fixVersion(part);
  return loadRuns(part).some((r) => r.version === v);
}
async function loadFixes(part) {
  S.fixes = S.fixes || {};
  const v = fixStamp(part), k = fixKey(part);
  S.fixReading = S.fixReading || {};
  if (S.fixReading[k] === v) return;                // already asked, for this stamp
  S.fixReading[k] = v;
  let got;
  try { got = { ...(await api('GET', `/api/designs/${S.slug}/parts/${part}/fixes`)), v }; }
  catch (e) { got = { rows: [], limits: [], error: plainly(e.message), v }; }
  if (S.fixReading[k] === v) delete S.fixReading[k];
  if (k !== fixKey(part)) return;                 // another design opened while it asked
  S.fixes[k] = got;
  paintFixes(part);
}
function paintFixes(part) {
  paintFixAct(part);
  const b = $('fixBody'), got = S.fixes && S.fixes[fixKey(part)];
  if (!b || !got || (($('fixBox') || {}).dataset || {}).fixPart !== part) return;
  b.innerHTML = fixesView(got, fixMine(part));
  const head = $('fixBox').querySelector('summary'), x = fixesSection(part);   // its header: the count, its mark
  if (head) head.innerHTML = subHead(x);
  $('fixBox').classList.toggle('attn', ATTN(x.tone));
  wireFixRows(part);
}
function wireFixes() {
  const box = $('fixBox');
  if (!box) return;
  const part = box.dataset.fixPart;
  paintFixAct(part);
  // of this design (its key) and this version only
  const fresh = () => fixFresh(part);
  box.ontoggle = () => { S.fixOpen = box.open ? fixKey(part) : null; if (box.open) { if (fresh()) paintFixes(part); else loadFixes(part); } };
  // its header's mark shows closed too: read the list again once a check lands, open or not (#331 review)
  if (!fresh()) loadFixes(part);
  else if (box.open) wireFixRows(part);
}
function wireFixRows(part) {
  const mine = fixMine(part), body = $('fixBody');
  if (!body) return;
  body.querySelectorAll('[data-fix-tick]').forEach((t) => { t.onchange = () => {
    const id = t.dataset.fixTick;
    mine.untick = mine.untick.filter((x) => x !== id).concat(t.checked ? [] : [id]);
    mine.tick = (mine.tick || []).filter((x) => x !== id).concat(t.checked ? [id] : []);
    paintFixAct(part);
  }; });
  body.querySelectorAll('[data-fix-pick]').forEach((t) => { t.onchange = () => { mine.pick[t.dataset.fixPick] = +t.value; paintFixes(part); }; });
  body.querySelectorAll('[data-fix-word]').forEach((b) => { b.onclick = () => { mine.editing = b.dataset.fixWord; paintFixes(part); }; });
  body.querySelectorAll('[data-fix-words]').forEach((i) => {
    i.focus(); i.select();                                  // typing replaces it
    const done = () => {
      const r = (S.fixes[fixKey(part)].rows || []).find((x) => fixRowKey(x) === i.dataset.fixWords);
      const was = r ? (r.choices[mine.pick[i.dataset.fixWords] || 0] || r.choices[0]).fix : '';
      const v = i.value.trim();
      if (v && v !== was) mine.words[i.dataset.fixWords] = v; else delete mine.words[i.dataset.fixWords];   // as it was: measured again
      mine.editing = null; paintFixes(part);
    };
    i.onkeydown = (e) => { if (e.key === 'Enter') done(); if (e.key === 'Escape') { mine.editing = null; paintFixes(part); } };
    i.onblur = done;
  });
  body.querySelectorAll('[data-fix-own-tick]').forEach((t) => { t.onchange = () => {
    mine.own[+t.dataset.fixOwnTick].off = !t.checked; paintFixAct(part);
  }; });
  body.querySelectorAll('[data-fix-own-del]').forEach((b) => { b.onclick = () => { mine.own.splice(+b.dataset.fixOwnDel, 1); paintFixes(part); }; });
  const cancel = body.querySelector('[data-fix-cancel]');
  if (cancel) cancel.onclick = () => { mine.plan = null; paintFixes(part); };
  const goNow = body.querySelector('[data-fix-go]');
  if (goNow) goNow.onclick = async () => {
    const slug = S.slug;
    mine.plan = null; mine.running = true; paintFixes(part);
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/parts/${part}/fixes`, fixPicked(part));
      const res = await trackJob(job_id, { kind: 'fix', part, text: 'fixing…' }).done;
      if (S.slug !== slug) return;
      mine.results = res.results || []; mine.untick = []; mine.words = {}; mine.own = []; mine.pick = {};
    } catch (e) { mine.error = plainly(e.message); }
    mine.running = false;
    await refresh().catch(() => {});                // the new version: its list is read again, measured
    paintFixes(part);
  };
  const add = body.querySelector('[data-fix-add]'), go = body.querySelector('[data-fix-add-go]');
  const put = () => { const v = add.value.trim(); if (v) { mine.own.push({ fix: v }); paintFixes(part); } };
  if (go) go.onclick = put;
  if (add) add.onkeydown = (e) => { if (e.key === 'Enter') put(); };
}
// each goes through what its panel already does: the chat, the carve, the lightening, or taking a step
// a carve or Lighten of this version that's already finished, as the server has it now
function studyDone(action, pid) {
  const p = S.design.parts.find((x) => x.id === pid);
  const runs = S.design[action === 'carve' ? 'carve_runs' : 'lighten_runs'] || [];
  return !!p && runs.some((r) => r.part === pid && r.version === p.version && (r.status === undefined || r.status === 'done'));   // a Lighten's only record is its finished one
}
function tellOffer(text) {                  // a plain word beside the offers: nothing's gone wrong, so no Report it
  const box = document.querySelector('#inspector .qbetter');
  if (!box) return;
  let say = box.querySelector('.qbetter-say');
  if (!say) { say = document.createElement('div'); say.className = 'qbetter-say small muted'; box.appendChild(say); }
  say.textContent = text;
}
async function useBetter(ln) {
  const p = S.design.parts.find((x) => x.id === ln.part);
  if (!p || ln.disabled) return;
  if (ln.action === 'use_t') {
    if (!S.claude && !ln.local) { tellOffer("Changing it needs Claude, which isn't set up here."); return; }   // not an error to report
    return send(ln.say, ln.part);
  }
  if (ln.action === 'carve' || ln.action === 'lighten') {    // a tab left open: look again before hours of machine (#159)
    await refresh();
    if (studyDone(ln.action, ln.part)) return;               // the card it was clicked on is redrawn as it now is
  }
  if (S.scope !== ln.part) setScope(ln.part);                 // their panels are the part's, under its numbers
  goTo('loadBox');
  if (ln.action === 'load') return runLoad(p);
  if (ln.action === 'carve') return runCarve(p);
  if (ln.action === 'lighten') return runLighten(p);
  if (ln.action === 'carve_use') return adoptStation(p.id, ln.run, ln.station, 'carve');
  if (ln.action === 'lighten_use') return adoptStation(p.id, ln.run, ln.station, 'lighten');
}

// the viewport follows the question (spec step 4): the stress for "will it work", the pieces for "what do I buy"
// and "how do I make it", the part itself for "what is it"
async function focusCard(k) {
  S.focus = k;
  document.querySelectorAll('#inspector .qcard').forEach((c) => c.classList.toggle('focus', c.dataset.card === k));
  const pid = shownPart();                       // the part whose cards these are, picked or not (#364)
  if (!pid) return;
  const p = S.design.parts.find((x) => x.id === pid);
  if (!p) return;
  if (S.station) clearStation();
  if (k === 'work') {
    const run = loadRuns(pid)[0];
    if (built3d.has(pid)) await showBuilt3d(pid, false);
    if (run && run.version === p.version) {
      const worst = run.cases.reduce((a, c, i) => (c.heat && (a < 0 || (c.safety ?? 1e9) < (run.cases[a].safety ?? 1e9)) ? i : a), -1);
      if (worst >= 0) showHeat(pid, run, worst);
    }
  } else if ((k === 'buy' || k === 'make') && p.built) {
    if (!built3d.has(pid)) await showBuilt3d(pid, true);
  } else if (built3d.has(pid)) {
    await showBuilt3d(pid, false);
  }
  renderLayers && renderLayers();
}
// the four questions as an accordion (#325): one open at a time, each header keeping its mark and its answer line, so a
// closed card still says how it stands. Which is open is kept per design and part; else the first that fails, else Will it
// work?
// kept per the part shown, picked or not (#364)
const cardStore = () => `${S.slug}/${shownPart() || ''}`;
function openCardFor(a) {
  const k = cardStore();
  if (S.openCard && k in S.openCard) return S.openCard[k];
  try { const kept = localStorage.getItem(`caliper.open.${k}`); if (kept !== null) return kept; } catch (e) { /* none allowed */ }
  const bad = a && a.cards.find((c) => c.status === 'bad');
  return bad ? bad.key : 'work';
}
function cardsView(groups) {
  const a = S.answers && S.answers.key === answersKey() && S.answers.cards ? S.answers : null;
  if (!a && !(S.answers && S.answers.key === answersKey() && S.answers.loading)) setTimeout(loadAnswers, 0);
  const open = openCardFor(a);
  return QUESTIONS.map(([k, q]) => {
    const c = a ? a.cards.find((x) => x.key === k) : null, on = k === open;
    return `<section class="qcard q-${c ? c.status : 'info'}${on ? ' open' : ''}${S.focus === k && shownPart() ? ' focus' : ''}" data-card="${k}">
      <h3 class="qhead"><button type="button" class="qtoggle" aria-expanded="${on}" aria-controls="qbody-${k}" data-qopen="${k}"${shownPart() ? ' title="show this in 3D"' : ''}><span class="qmark">${c ? QMARK[c.status] : '·'}</span><span class="qtitle">${q}</span>${/class="ssec[^"]*\battn\b/.test(groups[k] || '') ? '<span class="qinside" title="something inside needs a look">● inside</span>' : ''}<span class="qcaret" aria-hidden="true">${on ? '▾' : '▸'}</span></button></h3>
      <div class="qlines" id="q-${k}">${cardLines(k, c)}</div>
      ${k === 'what' && picturePart() ? '<div class="qlinks"><button class="btn" data-picture="1">🦖 Put a picture on it</button></div>' : ''}
      <div class="qbody" id="qbody-${k}" role="region" aria-label="${q}"${on ? '' : ' hidden'}>${groups[k] || '<div class="empty">Nothing here yet.</div>'}</div>
    </section>`;
  }).join('');
}
function openCard(k) {                          // opening one closes the others; the open one closes again on its head
  const now = document.querySelector('#inspector .qcard.open');
  const to = now && now.dataset.card === k ? '' : k;
  S.openCard = S.openCard || {};
  S.openCard[cardStore()] = to;
  try { localStorage.setItem(`caliper.open.${cardStore()}`, to); } catch (e) { /* private window */ }
  showOpen(to);
}
function showOpen(to) {
  document.querySelectorAll('#inspector .qcard').forEach((sec) => {
    const on = sec.dataset.card === to, b = sec.querySelector('.qtoggle'), body = sec.querySelector('.qbody');
    sec.classList.toggle('open', on);
    if (b) { b.setAttribute('aria-expanded', String(on)); b.querySelector('.qcaret').textContent = on ? '▾' : '▸'; }
    if (body) body.hidden = !on;
  });
}
// a block one level down, closed until opened, kept open or closed by what it is (#325)
// the sections inside a card (#325, Theo's refinements): a sub-accordion, each header with its own mark and its one-line
// answer, so a problem shows while everything is closed. SUB_ONE is the one switch: true, one open at a time within a
// card; false, each opens and closes on its own (Theo isn't sure which he wants)
const SUB_ONE = true;
const subKey = (card, k) => `${cardStore()}/${card}${SUB_ONE ? '' : `/${k}`}`;
function subKept(card, k) {
  const key = subKey(card, k);
  if (S.subOpen && key in S.subOpen) return S.subOpen[key];
  try { return localStorage.getItem(`caliper.ssec.${key}`); } catch (e) { return null; }
}
const ATTN = (tone) => tone === 'bad' || tone === 'warn';
// which are open: SUB_ONE, the one kept, else the first that needs attention, else the first; else each by what it was
// left as, else open where it needs attention
function subsOpen(card, list) {
  if (!SUB_ONE) return new Set(list.filter((x) => { const kept = subKept(card, x.k); return kept != null ? kept === '1' : ATTN(x.tone); }).map((x) => x.k));
  const kept = subKept(card, null);
  if (kept != null && (kept === '' || list.some((x) => x.k === kept))) return new Set(kept ? [kept] : []);
  const first = list.find((x) => x.tone === 'bad') || list.find((x) => x.tone === 'warn') || list[0];
  return new Set(first ? [first.k] : []);
}
const subHead = (x) => `<span class="qmark">${QMARK[x.tone] || '·'}</span><span class="stitle">${x.title}</span>${x.answer ? `<span class="sanswer">${x.answer}</span>` : ''}`;
function ssecs(card, list) {
  const open = subsOpen(card, list.filter(Boolean));
  return list.filter(Boolean).map((x) => `<details class="ssec t-${x.tone}${ATTN(x.tone) ? ' attn' : ''}" data-ssec="${x.k}" data-in="${card}"${x.attrs || ''}${open.has(x.k) ? ' open' : ''}>
    <summary>${subHead(x)}</summary><div class="sbody">${x.body}</div></details>`).join('');
}
function keepSub(dt) {                          // what's left open is kept; with SUB_ONE, opening one closes the others
  const card = dt.dataset.in, k = dt.dataset.ssec;
  if (SUB_ONE && dt.open) {
    document.querySelectorAll(`#inspector details.ssec[data-in="${card}"]`).forEach((o) => { if (o !== dt && o.open) o.open = false; });
  }
  const now = SUB_ONE ? (dt.open ? k : ([...document.querySelectorAll(`#inspector details.ssec[data-in="${card}"]`)].find((o) => o.open) || {}).dataset?.ssec || '')
    : (dt.open ? '1' : '0');
  S.subOpen = S.subOpen || {};
  S.subOpen[subKey(card, k)] = now;
  try { localStorage.setItem(`caliper.ssec.${subKey(card, k)}`, now); } catch (e) { /* private window */ }
}
// what each action opens (#325): the section it feeds, in its card, so its progress and its result are in view
const GO_OPENS = { lGo: ['work', 'result'], lightGo: ['work', 'lighten'], carveGo: ['work', 'carve'], aGo: ['work', 'aero'],
  cpGo: ['make', 'cutplan'], fixGo: ['work', 'fix'] };
function showSection(card, k) {
  const sec = document.querySelector(`#inspector .qcard[data-card="${card}"]`);
  if (sec && !sec.classList.contains('open')) openCard(card);
  const dt = document.querySelector(`#inspector details.ssec[data-in="${card}"][data-ssec="${k}"]`);
  if (dt && !dt.open) { dt.open = true; keepSub(dt); }
  if (dt) dt.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
// ------------------------------------------------------------------- test it (CALI-80)
// What the strength check predicts at each load step, what to measure the sag with, and what the real one did.
const sagText = (mm) => (inches() ? `${(mm / IN).toFixed(3)} in` : `${mm.toFixed(2)} mm`);
// A predicted sag's two ends, to enough places that they differ (trials.sag_range, op for op)
function sagRange(a, b) {
  const [x, y, unit] = inches() ? [a / IN, b / IN, ' in'] : [a, b, ' mm'];
  let places = inches() ? 3 : 2;
  if (x === y) return `${x.toFixed(places)}${unit}`;
  while (places < 6 && x.toFixed(places) === y.toFixed(places)) places += 1;
  return `${x.toFixed(places)}–${y.toFixed(places)}${unit}`;
}
function trialView(p) {
  const t = S.trial && S.trial.part === p.id && S.trial.key === p.version ? S.trial.data : null;
  if (!t) { setTimeout(() => loadTrial(p), 0); return '<div class="muted small"><span class="spin"></span>working out what to expect…</div>'; }
  const pr = t.prediction;
  if (!pr) return '<div class="empty">Check it holds first: the test is set beside what that predicts.</div>';
  const rows = t.rows.filter((r) => !r.stale);
  const show = pr.steps.filter((st, i) => i < 3 || st.lb === pr.lb || i === pr.steps.length - 1
    || st.lb % (pr.steps.length > 20 ? 200 : 100) === 0);
  const chart = trialChart(pr, rows);
  return `<p class="small">Put the load where <b>${esc(pr.case)}</b> goes, in steps, and measure how far ${pr.closed_under ? `the ${esc(pr.where || 'top')} sags ${esc(pr.measured_at)}` : `the middle of
      the ${esc(pr.where || 'top')} sags`}. Measure it with ${esc(pr.measure_with)}.${pr.other_way ? ` ${esc(pr.other_way)}` : ''}
      ${pr.breaks_lb ? `It should break at about <b>${pr.breaks_lb.toLocaleString()} lb</b>.` : pr.why_no_break ? (pr.why_no_break.startsWith('no prediction') ? `No prediction of where it breaks: ${esc(pr.why_no_break.replace(/^no prediction: /, ''))}.`   // (#248)
        : `Where it would break isn't settled: ${esc(pr.why_no_break)}.`) : 'Where it would break isn\'t settled: the check was too coarse to see its walls.'}
      ${pr.over ? `That's ${esc(pr.over)}, as its card says.` : ''}</p>
    ${chart}
    <table class="st"><tr><th>load</th><th>should sag</th><th>sagged</th><th></th></tr>
      ${show.map((st) => {
        const got = rows.filter((r) => r.load_lb === st.lb).slice(-1)[0];
        return `<tr><td>${st.lb.toLocaleString()} lb</td><td>${sagRange(st.sag_mm[0], st.sag_mm[1])}</td>
          <td>${got ? (got.broke ? '<b class="bad">broke</b>' : got.sag_mm != null ? sagText(got.sag_mm) : 'held') : ''}</td>
          <td class="muted">${got && got.ratio ? `${got.ratio}×` : ''}</td></tr>`;
      }).join('')}
    </table>
    ${rows.filter((r) => !show.some((st) => st.lb === r.load_lb)).length ? `<div class="muted small">and ${rows.filter((r) => !show.some((st) => st.lb === r.load_lb)).map((r) => `${r.load_lb} lb${r.broke ? ' (broke)' : ''}`).join(', ')}</div>` : ''}
    <div class="trial-add">
      <label>load <input id="trLoad" type="number" min="1" step="10" placeholder="200"> lb</label>
      <label>sag <input id="trSag" type="number" min="0" step="0.001" placeholder="${inches() ? '0.004' : '0.10'}"> ${inches() ? 'in' : 'mm'}</label>
      <label><input id="trBroke" type="checkbox"> it broke</label>
      <button class="small" id="trAdd">Record</button></div>
    <div class="muted small">${esc(pr.basis)}. Every step is kept with the design for calibrating the check.</div>
    ${t.skipped_note ? `<div class="small"><b class="bad">Left out:</b> ${esc(t.skipped_note)}.</div>` : ''}`;
}
function trialChart(pr, rows) {
  // load across, sag up: the predicted band, and what was measured
  const W = 300, H = 120, maxLb = Math.max(pr.breaks_lb || 0, ...rows.map((r) => r.load_lb), pr.lb);
  const maxSag = Math.max(pr.per_lb_mm[1] * maxLb, ...rows.map((r) => r.sag_mm || 0)) || 1;
  const x = (lb) => 30 + (W - 40) * lb / maxLb, y = (mm) => H - 18 - (H - 28) * mm / maxSag;
  const band = `M${x(0)},${y(0)} L${x(maxLb)},${y(pr.per_lb_mm[1] * maxLb)} L${x(maxLb)},${y(pr.per_lb_mm[0] * maxLb)} Z`;
  const dots = rows.filter((r) => r.sag_mm != null).map((r) => `<circle cx="${x(r.load_lb)}" cy="${y(r.sag_mm)}" r="3.5"
    class="${r.broke ? 'bad' : 'ok'}"/>`).join('');
  const breaks = pr.breaks_lb ? `<line x1="${x(pr.breaks_lb)}" x2="${x(pr.breaks_lb)}" y1="8" y2="${H - 18}" class="brk"/>
    <text x="${x(pr.breaks_lb) - 4}" y="16" text-anchor="end">breaks ~${pr.breaks_lb.toLocaleString()} lb</text>` : '';
  return `<svg class="trial-chart" viewBox="0 0 ${W} ${H}"><path d="${band}" class="band"/>${breaks}${dots}
    <line x1="30" x2="${W - 10}" y1="${H - 18}" y2="${H - 18}" class="axis"/><text x="${W - 10}" y="${H - 4}" text-anchor="end">load (lb)</text>
    <text x="30" y="${H - 4}">0</text><text x="4" y="12">sag</text></svg>`;
}
async function loadTrial(p) {
  if (S.trialLoading === p.id + p.version) return;
  S.trialLoading = p.id + p.version;
  try {
    S.trial = { part: p.id, key: p.version, data: await api('GET', `/api/designs/${S.slug}/parts/${encodeURIComponent(p.id)}/trial`) };
    const box = $('trialBox');
    if (box) { box.innerHTML = trialView(p); wireTrial(p); }
  } catch (e) { const box = $('trialBox'); if (box) box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  finally { S.trialLoading = null; }
}
function wireTrial(p) {
  const add = $('trAdd');
  if (!add) return;
  add.onclick = async () => {
    const load = +$('trLoad').value, sag = $('trSag').value;
    if (!load) { $('trLoad').focus(); return; }
    add.disabled = true;
    try {
      const body = { load_lb: load, broke: $('trBroke').checked,
        sag_mm: sag === '' ? null : (+sag) * (inches() ? IN : 1) };
      S.trial = { part: p.id, key: p.version,
        data: await api('POST', `/api/designs/${S.slug}/parts/${encodeURIComponent(p.id)}/trial`, body) };
      S.answers = null;                          // the card says what the test found
      await refresh();
    } catch (e) { showErr(e.message); add.disabled = false; }
  };
}

// ------------------------------------------------------------------- a picture on it (CALI-78)
// Say what it is or draw it; it's cut out of a panel nobody stands on, smooth enough for a jigsaw, and the
// strength check says whether it still holds (it's made smaller until it does).
function picturePart() {
  const d = S.design;
  if (!d) return null;
  if (S.scope) { const p = d.parts.find((x) => x.id === S.scope); return p && p.built && !p.not_accounted ? p : null; }
  const parts = d.parts.filter((p) => p.role !== 'fixed');
  return parts.length === 1 && parts[0].built && !parts[0].not_accounted ? parts[0] : null;
}
document.addEventListener('click', (e) => { if (e.target.dataset && e.target.dataset.picture) openPicture(); });
async function openPicture() {
  const p = picturePart();
  if (!p) return;
  let dlg = $('pictureDlg');
  if (!dlg) { dlg = document.createElement('dialog'); dlg.id = 'pictureDlg'; dlg.className = 'report'; document.body.append(dlg); }
  dlg.innerHTML = `<h3>Put a picture on it</h3>
    <p class="small muted">Say what it is, or draw it. I cut it out of a panel nobody stands on, as big as fits and
      smooth enough for a jigsaw, then check it still holds.</p>
    <div class="say"><input id="picSubject" type="text" placeholder="a T-rex">${micButton('picSubject')}</div>
    <div class="muted small" style="margin-top:8px">or draw it, all the way round:</div>
    <canvas id="picPad" class="pad" width="320" height="220"></canvas>
    <div class="actions" style="margin-top:4px"><button class="ghost small" id="picClear">Clear</button>
      <label class="small muted">on the <select id="picWhere"><option value="">front</option></select></label></div>
    <div class="actions"><button class="primary" id="picGo">Cut it out</button>
      <button class="ghost" id="picClose">Not now</button></div>`;
  wireMics(dlg);
  const pad = $('picPad'), ctx = pad.getContext('2d');
  let pts = [], down = false;
  const at = (e) => { const r = pad.getBoundingClientRect(); return [(e.clientX - r.left) * pad.width / r.width, (e.clientY - r.top) * pad.height / r.height]; };
  const paint = () => {
    ctx.clearRect(0, 0, pad.width, pad.height);
    if (pts.length < 2) return;
    ctx.beginPath(); ctx.moveTo(...pts[0]); pts.forEach((q) => ctx.lineTo(...q));
    if (!down) { ctx.closePath(); ctx.fillStyle = 'rgba(78,161,255,.18)'; ctx.fill(); }
    ctx.strokeStyle = '#4ea1ff'; ctx.lineWidth = 3; ctx.lineJoin = ctx.lineCap = 'round'; ctx.stroke();
  };
  pad.onpointerdown = (e) => {
    down = true; pts = [at(e)];
    try { pad.setPointerCapture(e.pointerId); } catch (err) { /* a pen or finger the page didn't start */ }
    paint();
  };
  pad.onpointermove = (e) => { if (down) { pts.push(at(e)); paint(); } };
  pad.onpointerup = () => { down = false; paint(); };
  $('picClear').onclick = () => { pts = []; paint(); };
  $('picClose').onclick = () => dlg.close();
  try {
    const got = await api('GET', `/api/designs/${S.slug}/parts/${encodeURIComponent(p.id)}/picture`);
    $('picWhere').innerHTML = got.panels.map((x) => `<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('');
    const front = got.panels.find((x) => /front/i.test(x.name));
    if (front) $('picWhere').value = front.name;
  } catch (e) { /* the server picks */ }
  $('picGo').onclick = async () => {
    const subject = $('picSubject').value.trim(), where = $('picWhere').value;
    if (!subject && pts.length < 8) { $('picSubject').focus(); return; }
    dlg.close();
    const text = pts.length >= 8 ? `(drew ${subject || 'a picture'} to cut out)` : `put ${subject} on the ${where || 'front'}`;
    S.busy = true; $('send').disabled = true;
    const live = liveTurn(text, p.id);
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/parts/${encodeURIComponent(p.id)}/picture`,
        { subject: subject || 'picture', where, points: pts.length >= 8 ? pts.map(([x, y]) => [Math.round(x), Math.round(y)]) : [] });
      await follow(job_id, (ev) => live.step(ev));
      S.busy = false;
      await refresh();
    } catch (e) { live.fail(e.message, e.errorId); }
    finally { S.busy = false; $('send').disabled = false; }
  };
  dlg.showModal();
}

async function loadAnswers() {
  if (!S.design) return;
  const key = answersKey();
  if (S.answers && S.answers.key === key && (S.answers.loading || S.answers.cards)) return;
  S.answers = { key, loading: true };
  try {
    const got = await api('GET', `/api/designs/${S.slug}/answers${shownPart() ? `?part=${encodeURIComponent(shownPart())}` : ''}`);
    if (!S.answers || S.answers.key !== key) return;              // it moved on while we asked
    S.answers = { key, cards: got.cards };
  } catch (e) { S.answers = { key, cards: [], error: e.message }; }
  // fill the cards in place: redrawing the inspector would wipe a half-filled form
  for (const c of S.answers.cards) {
    const card = document.querySelector(`#inspector .qcard[data-card="${c.key}"]`);
    if (!card) continue;
    card.className = `qcard q-${c.status}${card.classList.contains('open') ? ' open' : ''}${card.classList.contains('focus') ? ' focus' : ''}`;
    card.querySelector('.qmark').textContent = QMARK[c.status];
    card.querySelector('.qlines').innerHTML = cardLines(c.key, c);
  }
  showOpen(openCardFor(S.answers));                    // drawn before its marks: the first that fails, unless one was kept
  wireCards();
  // a print time still being worked out (#97): ask again until it's in, while the same cards are showing
  if ((S.answers.cards || []).some((c) => c.lines.some((ln) => ln.working))) {
    setTimeout(() => { if (S.answers && S.answers.key === key && S.answers.cards) { S.answers = null; loadAnswers(); } }, 4000);
  }
}
function wireCards() {
  wireFixes();                                            // Things to fix, under Will it work? (#300)
  document.querySelectorAll('#inspector details.ssec').forEach((dt) => {
    if (dt.dataset.wiredSub) return;
    dt.dataset.wiredSub = '1';
    dt.addEventListener('toggle', () => keepSub(dt));     // its own ontoggle (Things to fix's, Advanced's) stays its own
  });
  document.querySelectorAll('#inspector .qtoggle').forEach((b) => {
    b.onclick = () => { openCard(b.dataset.qopen); focusCard(b.dataset.qopen); };
  });
  document.querySelectorAll('#inspector .qline[data-goto]').forEach((ln) => { ln.onclick = () => goTo(ln.dataset.goto); });
  document.querySelectorAll('#inspector [data-better]').forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();                                    // the card's head has its own click
      const c = ((S.answers && S.answers.cards) || []).find((x) => x.key === b.dataset.card);
      if (c && c.lines[+b.dataset.better].action === 'carve') b.disabled = true;       // on while it isn't running only
      if (c) useBetter(c.lines[+b.dataset.better]);
    };
  });
}
// where a line's click goes, or '' (no link): a panel on a part's view needs a part to open, so with several parts and
// none selected there's nowhere to go, and it isn't drawn as a link (CALI-92, #70 item 19)
const PART_PANELS = new Set(['patternBox', 'loadBox', 'frameBox', 'trialBox']);
function gotoFor(ln) {
  const id = GOTO[ln.study || ln.action];
  if (!id) return '';
  if (PART_PANELS.has(id) && !S.scope && S.design.parts.filter((p) => p.role !== 'fixed').length !== 1) return '';
  return id;
}
function goTo(id, again) {            // open the card's numbers and bring that panel into view
  const box = $(id);
  if (!box) {                         // on the other view: go there first, once
    if (again) return;
    if (PART_PANELS.has(id) && !S.scope) {
      const only = S.design.parts.filter((p) => p.role !== 'fixed');
      if (only.length !== 1) return;
      setScope(only[0].id);
    } else if (id === 'relBox' && shownPart()) { S.whole = true; setScope(null); }   // the build package is the whole design's (#364)
    else return;
    setTimeout(() => goTo(id, true), 50);
    return;
  }
  const sec = box.closest('.qcard');                // its card open, and every block it sits in (#325)
  if (sec && !sec.classList.contains('open')) openCard(sec.dataset.card);
  for (let dt = box.closest('details'); dt; dt = dt.parentElement && dt.parentElement.closest('details')) dt.open = true;
  (box.previousElementSibling || box).scrollIntoView({ behavior: 'smooth', block: 'start' });
  box.classList.add('flash');
  setTimeout(() => box.classList.remove('flash'), 1600);
}

// ------------------------------------------------------------- the scorecard (CALI-47)
// One card for the design as it stands: every check (pass/fail, margin) and every objective (value, change
// since the last card) across design, optimization, making and cost — each with how far to trust it.
const TRUST = { measured: 'measured', model: 'a model (on the safe side)', rough: 'rough', guess: 'a guess' };
// which version a stale card's numbers are of: "as of v1" (#138 item 2)
function asOf(card) {
  const v = Object.values(card.versions || {});
  return v.length === 1 ? `as of v${v[0]}` : 'as of an older version';
}
// a scorecard row's mark: a stale card's pass is no ✓ (it was the part as it was), amber, said as of when; a fail
// stays a ✗ (#138 item 2: "✓ holds … 2.58x" from v1 beside v4's 1.7x ✗)
function scoreMark(c, stale, when) {
  if (c.status === 'fail') return '<span style="color:var(--bad)">✗</span>';
  if (stale && c.status === 'pass') return `<span style="color:var(--amber)" title="${esc(when)}">·</span>`;
  if (c.joints && c.status === 'pass') return c.joints_kind === 'holds' ? `<span title="${esc(c.joints)}">✓</span>`   // (#265)
    : `<span style="color:var(--amber)" title="${esc(c.joints)}">!</span>`;
  return c.status === 'pass' ? '✓' : c.status === 'proposed' ? '◇'
    : c.status === 'unresolved' || c.status === 'untrusted' || c.status === 'estimate' ? '<span style="color:var(--amber)">!</span>' : '?';
}
// a goal's own limit beside its number (#137 item 5): "13.1 lb (cap 10 lb)"
// a scorecard number as the panel says it, at module level: goalLimit uses it too (#139 review: it called scoreView's
// own num, so a goal with a number threw "num is not defined" and blanked the inspector)
function scoreNum(v, u, need) {
  if (v == null) return '—';
  if (typeof v === 'number' && (u === '×' || u === 'x')) return `${safetyNum(v, need)}${u ? ' ' + esc(u) : ''}`;   // (#208 review)
  const n = typeof v === 'number' ? (Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : `${+v.toFixed(2)}`) : esc(String(v));
  return u === '$' ? `$${n}` : `${n}${u ? ' ' + esc(u) : ''}`;
}
const goalLimit = (c) => (typeof c.limit === 'number' ? ` (${c.op === '<=' || c.op === '<' ? 'cap' : 'needs'} ${scoreNum(c.limit, c.unit)})` : '');
function scoreView(d) {
  const card = (d.scorecards || [])[0];
  const stale = card && (card.outdated     // scored the old way (CALI-111): its numbers aren't today's
    || d.parts.some((p) => card.versions && card.versions[p.id] !== undefined && card.versions[p.id] !== p.version));
  const num = scoreNum;
  const tag = (t) => t ? `<span class="badge" title="how far to trust it">${esc(TRUST[t] || t)}</span>` : '';
  // where a check came from (CALI-55): the person's words, an assumption, kept, or only proposed so far
  const from = (c) => c.source === 'stated' ? `<span class="badge ok" title="${esc(c.quote || '')}">you said</span>`
    : c.source === 'assumed' ? '<span class="badge">assumed</span>'
    : c.source === 'confirmed' ? '<span class="badge ok">kept</span>'
    : c.source === 'proposed' ? `<span class="badge" title="${esc(c.why || '')}">proposed</span>
        <button class="ghost" data-goal="${esc(c.id)}" data-keep="1">Keep</button><button class="ghost" data-goal="${esc(c.id)}" data-keep="0">Drop</button>`
    : '';
  const held = (d.goals && d.goals.checks) || [];
  const goals = !d.has_goals
    ? '<div class="muted small">Nothing to hold it to yet but its own rules. Tell me what it must do (“it has to hold me, 200 lb”, “under $50”) and I\'ll write it down.</div>'
    : d.goals && !d.goals.ours ? '<div class="muted small">Held to its <code>scorecard.yaml</code>, as written by hand.</div>' : '';
  if (!card) {
    return `${held.length ? `<ul class="list small">${held.map((c) => `<li>${c.source === 'proposed' ? '◇' : '·'} ${esc(c.label || c.id)} ${from(c)}
        ${c.why && c.source === 'proposed' ? `<div class="muted">${esc(c.why)}</div>` : ''}</li>`).join('')}</ul>` : ''}
      ${goals}<div class="actions"><button id="scGo">Score it</button></div><div id="scProgress"></div>`;
  }
  const delta = (o) => {
    if (o.change == null || Math.abs(o.change) < 1e-9) return '';
    const better = o.direction === 'max' ? o.change > 0 : o.change < 0;
    return ` <span class="small" style="color:var(${better ? '--ok' : '--bad'})">${o.change > 0 ? '+' : ''}${num(o.change)}</span>`;
  };
  const when = stale ? asOf(card) : '';
  const old = when ? ` <span class="muted">(${esc(when)})</span>` : '';
  return `<div class="small">${when ? `<b style="color:var(--amber)">Scored ${esc(when)}:</b> ` : ''}${card.summary.pass} pass · <b style="color:var(--bad)">${card.summary.fail} fail</b>${card.summary.unknown ? ` · ${card.summary.unknown} unknown` : ''}${card.summary.unresolved ? ` (${card.summary.unresolved} not resolved)` : ''}${card.summary.proposed ? ` · ${card.summary.proposed} proposed` : ''}
      <span class="muted">· scored ${new Date(card.created * 1000).toLocaleString()}</span>
      ${stale ? '<span class="badge bad">a part has changed since</span>' : ''}</div>
    <ul class="list small" style="margin-top:6px">${card.checks.map((c) => { const now = held.find((x) => x.id === c.id) || c;
      return `<li>${scoreMark(c, stale, when)}
      ${esc(c.label || c.id)} ${c.value != null ? `— ${num(c.value, c.unit, typeof c.limit === 'number' && (c.op || '>=').startsWith('>') ? c.limit : null)}${goalLimit(c)}${old}` : ''}${c.assumed ? ' <span class="badge">assumed</span>' : ''} ${from(now)} ${tag(c.trust)}
      ${now.source === 'proposed' && now.why ? `<div class="muted">${esc(now.why)}</div>` : ''}
      ${c.loads ? `<div class="muted">${esc(c.loads)}</div>` : ''}</li>`; }).join('')}
      ${held.filter((x) => !card.checks.some((c) => c.id === x.id)).map((c) => `<li>· ${esc(c.label || c.id)} ${from(c)}
        <span class="muted">— new since this card</span></li>`).join('')}</ul>
    <table class="st" style="margin-top:6px">${card.objectives.map((o) => `<tr><td style="text-align:left">${esc(o.label)}</td>
      <td>${num(o.value, o.unit)}${delta(o)}${old}</td><td>${tag(o.trust)}</td></tr>`).join('')}</table>
    ${card.cost ? `<details class="small" style="margin-top:6px"><summary>Stock: $${Math.round(card.cost.usd)} · offcut $${Math.round(card.cost.waste_usd)}${old}</summary>
      <table class="st">${card.cost.lines.map((l) => `<tr><td style="text-align:left">${esc(l.part)}</td><td style="text-align:left">${esc(l.item)}</td>
        <td>$${l.usd.toFixed(0)}</td><td class="muted">${l.waste_usd ? `$${l.waste_usd.toFixed(0)} offcut` : ''}</td></tr>`).join('')}</table>
      <div class="muted">${esc(card.cost.basis)}</div></details>` : ''}
    ${(card.warnings || []).map((n) => `<div class="small" style="margin-top:4px;color:var(--amber)">! ${esc(n)}</div>`).join('')}
    ${(card.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    ${goals}<div class="actions"><button id="scGo">${stale ? 'Score it again' : 'Score it'}</button></div><div id="scProgress"></div>`;
}

function wireScore() {
  document.querySelectorAll('#scoreBox [data-goal]').forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      try {
        S.design = await api('POST', `/api/designs/${S.slug}/goals/${encodeURIComponent(b.dataset.goal)}`, { keep: b.dataset.keep === '1' });
        render();
      } catch (e) { showErr(e.message); b.disabled = false; }
    };
  });
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

// ------------------------------------------------------------- the build package (CALI-51)
// A released, versioned bundle for the shop: the build book (printable, with the assembly order), cut files
// by machine, cut lists, shopping list and the scorecard as released.
function releaseView(d) {
  if (d.parts.some((p) => p.not_accounted)) return `<div class="small muted">No build package yet: a part's pieces don't account for its solid.</div>`;
  const rel = (d.releases || [])[0];
  const go = `<div class="actions"><button id="relGo">${rel ? 'Make a new build package' : 'Make the build package'}</button></div><div id="relProgress"></div>`;
  if (!rel) {
    return `<div class="muted small">One printable bundle for this exact version: every sheet and plate as DXF and PDF,
      the cut lists with their end cuts, what to buy, and the assembly order step by step.</div>${go}`;
  }
  const base = `/api/designs/${S.slug}/releases/${rel.id}/files`;
  const stale = d.parts.some((p) => rel.versions[p.id] !== undefined && rel.versions[p.id] !== p.version);
  const vers = Object.entries(rel.versions).map(([k, v]) => `${esc(k)} v${v}`).join(', ');
  return `<div class="small"><b>Release ${esc(rel.id)}</b>
      ${rel.verdict && rel.verdict.kind === 'holds' ? '<span class="badge ok">ready to cut</span>'
        : rel.verdict && rel.verdict.kind === 'stale' ? '<span class="badge warn">ready as it was made: a part has changed since</span>'
        : `<span class="badge ${verdictTone(rel.verdict)}">not ready — ${esc((rel.verdict && rel.verdict.why) || 'a check isn\'t settled')}</span>`}
      ${stale ? '<span class="badge bad">a part has changed since</span>' : ''}
      <div class="muted">${new Date(rel.created * 1000).toLocaleString()} · ${vers}</div>
      <div>${rel.steps.length} assembly steps · ${rel.sheets} sheets · ~$${Math.round(rel.shopping_usd)} to buy</div></div>
    <a href="${base}/index.html" target="_blank" rel="noopener"><img src="${base}/assembly/finished.png" alt="the finished build"
      style="width:100%;margin-top:6px;border:1px solid var(--line);border-radius:6px;background:#fff"></a>
    <div class="actions" style="flex-wrap:wrap">
      <a class="btn" href="${base}/index.html" target="_blank" rel="noopener">Open the build book</a>
      ${rel.pdf ? `<a class="btn" href="${base}/build-book.pdf" target="_blank" rel="noopener">PDF</a>` : ''}
      <a class="btn" href="${base}/${esc(rel.zip)}">Download all (.zip)</a></div>
    ${rel.pdf_note ? `<div class="muted small">${esc(rel.pdf_note)}</div>` : ''}
    <details class="small"><summary>Assembly order</summary><ol style="margin:4px 0 0 18px;padding:0">
      ${rel.steps.map((s) => `<li><a href="${base}/${esc(s.img)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join('')}</ol></details>
    ${go}`;
}

function wireRelease() {
  const go = $('relGo');
  if (!go) return;
  go.onclick = async () => {
    const prog = $('relProgress');
    go.disabled = true;
    prog.innerHTML = '<div class="small muted" id="relMsg">bringing the cut plans and scorecard up to date…</div>';
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/release`);
      await trackJob(job_id, { kind: 'release', part: null, text: 'bringing the cut plans and scorecard up to date…' }).done;
      await refresh();
    } catch (e) { prog.innerHTML = jobEnded(e); go.disabled = false; }
  };
}

function historyItem(h, now) {
  if (h.kind === 'revision') {
    const what = h.action === 'frame' ? `tubes sized — design ${h.station} (${h.mass_lb} lb, ${h.safety}x)`
      : h.action === 'aero' ? `shaped for drag — station ${h.station}`
      : h.action === 'whittle' ? `from whittle${h.station != null ? ' — station ' + h.station : ''}`
      : h.action === 'build' ? 'construction changed'
      : h.action === 'lighten' ? `lightened — step ${h.station}`
      : h.action === 'restore' ? `rolled back to v${h.restored_from}` : h.action;
    const older = now != null && h.version != null && h.version !== now;   // an older version: see it, or go back to it (#299)
    return `<li class="hist"><span class="v">v${h.version}</span>${esc(what)}
      ${older ? `<span class="hist-acts"><button class="ghost small" data-preview-v="${h.version}">Preview</button>
        <button class="ghost small" data-goback-v="${h.version}">Go back to this</button></span>` : ''}
      ${h.feedback && h.action !== 'author' ? `<div>“${esc(h.feedback)}”</div>` : ''}
      ${h.verdict ? `<span class="badge ${verdictTone(h.verdict)}">${esc(h.verdict.kind === 'holds' ? 'passed' : h.verdict.kind === 'fails' ? 'failing' : h.verdict.word)}</span>` : ''}</li>`;
  }
  if (h.kind === 'assertion') {
    return `<li class="hist">${h.action === 'promoted' ? '🔒 locked in' : 'declined'} <code>${esc(h.expr || h.id)}</code></li>`;
  }
  if (h.kind === 'whittle') return `<li class="hist">studied in whittle (${esc(h.study)}, ${h.stations} stations)</li>`;
  if (h.kind === 'frame' && h.action === 'studied') return `<li class="hist">frame study (${h.stations} designs)</li>`;
  if (h.kind === 'lighten' && h.action === 'studied') return `<li class="hist">lightening study (${h.stations} steps)</li>`;
  // a number only where the check gave one: a check that couldn't run says why, never "0x" (#138 item 3)
  if (h.kind === 'load' && h.action === 'studied') return `<li class="hist">strength check: ${esc(h.verdict ? h.verdict.word : 'not checked yet')}${h.verdict && h.verdict.kind === 'unchecked' && h.verdict.why ? `: ${esc(h.verdict.why)}` : h.safety != null && h.verdict && ['holds', 'fails'].includes(h.verdict.kind) ? `, ${+h.safety.toFixed(1)}x` : ''}</li>`;
  if (h.kind === 'patterns' && h.action === 'made') return `<li class="hist">patterns for hand tools (${h.pieces} pieces)</li>`;
  if (h.kind === 'cutplan' && h.action === 'made') return `<li class="hist">cut plan (${h.sheets} sheet${h.sheets === 1 ? '' : 's'})</li>`;
  if (h.kind === 'aero' && h.action === 'studied') return `<li class="hist">shape search: ${esc((h.searched || []).join(', '))}</li>`;
  if (h.kind === 'setting') return `<li class="hist">marked ${h.role === 'fixed' ? 'as a reference' : 'as a design part'}</li>`;
  return '';
}

// the part's actions, small, top right, in the chain's order (#325): each greyed until it can run, with the right-click
// menu's own ready/why (design.studies.menu), so the two never disagree; a running job shows on its button (jobOff). The
// ids are the panels' own, so their wiring and progress go as before: each action has one place.
function partActions(p) {
  const menu = {};
  ((((S.design.studies || {}).menu) || {})[p.id] || []).forEach((m) => { menu[m.kind] = m; });
  const air = !p.framed && !!((S.design.in_air && S.design.in_air.yes) || aeroRuns(p.id).length || runsFor(p.id).length);
  const cut = cutplanRun(p);
  const acts = [
    p.role !== 'fixed' && !p.framed && ['load', 'lGo', loadRuns(p.id).length ? 'Check it again' : 'Check it holds', ''],
    p.study === 'lighten' && ['lighten', 'lightGo', lightenRuns(p.id).length ? 'Lighten it again' : 'Lighten it', lightenRuns(p.id).length ? ' data-again="1"' : ''],
    p.study === 'carve' && ['carve', 'carveGo', carveRuns(p.id).length ? 'Carve it again' : 'Carve it', carveRuns(p.id).length ? ' data-again="1"' : ''],
    air && ['aero', 'aGo', 'Shape for drag', ''],
    p.built && ['cutplan', 'cpGo', cut ? 'Make the cut plan again' : 'Make the cut plan', ''],
  ].filter(Boolean);
  const buttons = acts.map(([kind, id, label, again]) => {
    const m = menu[kind] || { ready: true, why: '' };
    // a job of this part's running says so on its button (#331 review: Theo asked for "Lightening…")
    const running = kind === 'carve' ? S.carveJob[carveKey(p.id)]
      : ((S.design.running || []).find((r) => r.part === p.id && r.kind === kind));
    const off = !m.ready ? ` aria-disabled="true" data-why="${esc(m.why)}" title="${esc(`Not yet: ${m.why}`)}"` : '';
    return `<button class="small${m.ready ? '' : ' off'}" id="${id}"${again}${off}${running ? ' disabled' : ''}>${running ? runningLabel(kind) || label : label}</button>`;
  }).join('');
  return `<div class="pacts" role="toolbar" aria-label="What to do with it" id="pacts">${buttons}${fixAct(p.id)}</div>
    <div class="small muted pacts-why" id="pactsWhy" aria-live="polite"></div>`;
}
function wirePartActions() {                    // a greyed one says why, on a click or a tap, and never runs
  const bar = $('pacts'), why = $('pactsWhy');
  if (!bar || bar.dataset.wired) return;
  bar.dataset.wired = '1';
  bar.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b || b.getAttribute('aria-disabled') !== 'true') {
      if (why) why.textContent = '';
      if (b && GO_OPENS[b.id]) showSection(...GO_OPENS[b.id]);        // its section open first: its progress shows there
      return;
    }
    e.stopPropagation(); e.preventDefault();
    if (why) why.textContent = b.dataset.why;
  }, true);
}
function cutplanRun(p) { return (S.design.cutplans || []).find((r) => r.part === p.id) || null; }
function partView(p) {
  const d = S.design;
  const mine = (r) => new RegExp(`\\b${p.id}\\b`).test(r.expr);
  const designRules = d.rules.filter(mine);
  const origin = p.origin === 'whittled' ? '<span class="badge whittled">whittled mesh</span>'
    : p.scripted ? '<span class="badge">parametric</span>' : '<span class="badge">imported</span>';
  const rules = [...p.rules, ...designRules], failing = rules.filter((r) => r.verdict && r.verdict.kind === 'fails');
  const revisions = p.history.filter((h) => h.kind === 'revision').length;
  const what = `<label class="small muted" style="display:block;margin-top:2px">
      <input type="checkbox" id="roleRef" ${p.role === 'fixed' ? 'checked' : ''}> treat as a reference (context, e.g. the car)</label>
    ${ssecs('what', [
      { k: 'size', title: 'Size', tone: p.bbox ? 'info' : 'bad', answer: p.bbox ? sizeText(p.bbox.size) : 'it won\'t build',
        body: p.bbox ? `<div class="kv">
      <span class="k">width</span><span>${len(p.bbox.size[1])}</span>
      <span class="k">depth</span><span>${len(p.bbox.size[0])}</span>
      <span class="k">height</span><span>${len(p.bbox.size[2])}</span>
      <span class="k">bottom at</span><span>${len(p.bbox.min[2])}</span></div>` : '<div class="empty">won\'t build</div>' },
      { k: 'rules', title: 'Rules on this part', tone: failing.length ? 'bad' : rules.length ? 'ok' : 'info',
        answer: !rules.length ? 'none yet' : failing.length ? `${failing.length} of ${rules.length} broken` : `${rules.length}, all kept`,
        body: rules.length ? `<ul class="list">${rules.map(ruleItem).join('')}</ul>`
          : '<div class="empty">None yet. Say something like “it must clear the car by 2 in” and I\'ll offer to lock it in.</div>' },
      { k: 'history', title: 'History', tone: 'info', answer: `${revisions} version${revisions === 1 ? '' : 's'}, now v${p.version}`,
        attrs: ' id="partHistory"', body: `<ul class="list">${p.history.slice().reverse().map((h) => historyItem(h, p.version)).join('')}</ul>` },
      { k: 'adv', title: 'Advanced', tone: 'info', answer: `script &amp; spec <span class="muted">${esc(p.id)}</span> ${origin}`,
        attrs: ' id="adv"', body: '<div id="advBody" class="small muted">loading…</div>' }])}`;
  const runs = loadRuns(p.id), run = runs[0];
  const checked = !run ? { tone: 'info', answer: p.loads ? 'not checked yet' : 'it doesn\'t say what it must carry yet' }
    : run.version !== p.version ? { tone: 'warn', answer: `${runWord(run)}, of v${run.version}: the part has changed since` }
      : { tone: run.verdict ? (verdictTone(run.verdict) === 'ok' ? 'ok' : verdictTone(run.verdict) === 'bad' ? 'bad' : 'warn') : 'info',
        answer: run.verdict && run.verdict.short ? run.verdict.short : runWord(run) };
  const light = lightenRuns(p.id)[0], carve = carveRuns(p.id)[0];
  const later = (r, none) => (!r ? { tone: 'info', answer: none } : r.version != null && r.version !== p.version
    ? { tone: 'warn', answer: `of v${r.version}: the part has changed since` } : { tone: 'info', answer: `its steps, of v${r.version != null ? r.version : p.version}` });
  const air = !p.framed && (S.design.in_air.yes || aeroRuns(p.id).length || runsFor(p.id).length);
  const work = ssecs('work', [
    !p.framed && (p.built || p.loads) && p.role !== 'fixed' && { k: 'result', title: 'Will it hold? <span class="badge">strength</span>', ...checked,
      body: `<div id="loadBox">${loadView(p)}</div>` },
    shownPart() && p.role !== 'fixed' && fixesSection(p.id),
    p.study === 'lighten' && lightenShown(p, runs) && { k: 'lighten', title: 'Make it lighter', ...later(light, 'not lightened yet'),
      body: lightenView(p) },
    p.study === 'carve' && (runs.length || carveRuns(p.id).length) && { k: 'carve', title: 'Carve it <span class="badge">printed, any shape</span>',
      ...later(carve, 'not carved yet'), body: carveView(p) },
    p.loads && p.role !== 'fixed' && { k: 'trial', title: 'Test it <span class="badge">the real one</span>', tone: 'info',
      answer: 'what to measure, and what it did', body: `<div id="trialBox">${trialView(p)}</div>` },
    p.framed && { k: 'frame', title: 'Size the frame <span class="badge">tubes back</span>', tone: 'info', answer: '',
      body: `<div id="frameBox">${frameView(p)}</div>` },
    air && { k: 'aero', title: 'Shape it for drag <span class="badge">numbers back</span>', tone: 'info',
      answer: `${aeroRuns(p.id).length} search${aeroRuns(p.id).length === 1 ? '' : 'es'}`, body: `<div id="aeroBox">${aeroView(p)}</div>` },
    air && { k: 'whittle', title: 'whittle carving <span class="badge">mesh back</span>', tone: 'info', answer: '',
      body: `<div id="whittleBox">${whittleView(p)}</div>` }]);
  const buy = p.built ? ssecs('buy', [{ k: 'stock', title: 'Built from <span class="badge">weight &amp; shopping list</span>', tone: 'info',
    answer: 'the stock and what to buy', body: `<div id="buildBox">${buildView(p)}</div>` }]) : '';
  const cut = cutplanRun(p);
  const make = p.built ? ssecs('make', [
    makingSection(p),
    { k: 'patterns', title: 'Patterns for hand tools', tone: 'info', answer: 'every flat piece, full size',
      body: `<div id="patternBox">${patternView(p)}</div>` },
    { k: 'cutplan', title: 'Cut plan', tone: cut && cut.version != null && cut.version !== p.version ? 'warn' : 'info',
      answer: !cut ? (S.design.cutplan_unavailable ? 'not here' : 'not made yet') : cut.version != null && cut.version !== p.version ? `of v${cut.version}: the part has changed since`
        : 'the sheets laid out flat', body: `<div id="cutplanBox">${cutplanView(p)}</div>` }]) : '';
  // the heading is the part's own name; its id and how it was made are one click down, under Advanced (#70 item 21);
  // its actions beside it, its numbers under it, then the four questions (#325)
  const whole = !S.scope ? '<button class="linkish small" data-whole="1">The whole design ▸</button>' : '';   // its one part, unpicked (#364)
  return `<div class="parthead"><div><h2>${esc(p.name || p.id)}</h2>
    <div class="muted small">v${p.version} ${whole}</div></div>${partActions(p)}</div>
    <div id="paramBox">${paramView(p)}</div>
    ${cardsView({ what, work, buy, make })}`;
}

function wireInspector(p) {
  document.querySelectorAll('#inspector [data-part]').forEach((a) => { a.onclick = () => setScope(a.dataset.part); });
  document.querySelectorAll('#inspector [data-whole]').forEach((b) => {   // a one-part design: its part's view, or the whole design's (#364)
    b.onclick = () => { S.whole = b.dataset.whole === '1'; renderInspector(); };
  });
  showMarks();
  wireCards();
  // keep a check the planner assumed: it's enforced from then on (CALI-115)
  // an answer about the shop goes to the shop, on a yes (CALI-124)
  document.querySelectorAll('#inspector [data-shopoffer]').forEach((b) => {
    b.onclick = async () => {
      try {
        S.design = await api('POST', `/api/designs/${S.slug}/shop-offer`, { index: +b.dataset.shopoffer, add: b.dataset.add === '1' });
        renderInspector();
      } catch (e) { showErr(e.message); }
    };
  });
  document.querySelectorAll('#inspector [data-plankeep]').forEach((b) => {
    b.onclick = async () => {
      try {
        S.design = await api('POST', `/api/designs/${S.slug}/plan/checks/${encodeURIComponent(b.dataset.plankeep)}/keep`);
        renderInspector();
      } catch (e) { showErr(e.message); }
    };
  });
  if (!p) { wireBalance(); wireScore(); wireRelease(); return; }
  wirePartActions();                                // the actions top right: a greyed one says why (#325)
  wireBuilt(p);
  wireCutplan(p);
  wireTrial(p);
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
  wireLoad(p);
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

// how its pieces join (CALI-156, #222 slice A): each joint, its kind and what holds it, an assumed one said so
function jointsHtml(r) {
  const js = (r && r.joints) || [];
  if (!js.length) return '';
  const unread = (js.find((j) => typeof j.unread === 'string') || {}).unread;   // said, never "none was said" (#275 review)
  return `<h5 style="margin:12px 0 4px">How it joins</h5><ul class="list small">${js.map((j) => `<li>${esc(j.pieces.join(' and '))}:
    ${esc(j.kind)}${j.assumed ? ` <span class="muted">(assumed: ${j.unread ? "its JOINTS couldn't be read" : 'none was said'})</span>` : ''}, ${esc((j.fix || []).join(' and '))}</li>`).join('')}</ul>
    <div class="muted small">The strength check takes these joints as solid wood: they aren't checked.</div>
    ${unread ? `<div class="muted small">The joints couldn't be read: ${esc(unread)}.</div>` : ''}`;
}

function buildView(p) {
  if (p.not_accounted) return `<div class="small muted">No cut plan yet: its pieces don't account for its solid.</div>`;
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
  if (box && shownPart() === p.id) { box.innerHTML = buildView(p); wireBuilt(p); showMarks(); }
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

// the table, the pieces and the balance go by the model's solid; the part's weight above by its filament figure: said
// where the two differ, so neither reads as the other (#237 review)
function solidSaid(r) {
  const more = r.filament_more_kg || 0;
  if (Math.abs(more) < 0.005 || r.mass_lb == null) return '';
  const solid = r.mass_lb - more * 2.20462;
  return `<div class="small muted">The table below, the pieces' weights and the balance are the model's solid
    (${lbs(solid)}); its weight above, ${lbs(r.mass_lb)}, goes by its filament figure.</div>`;
}
function builtResults(p, c) {
  const r = c.report, b = c.balance, changed = Object.keys(r.changed || {}).length;
  const mine = b && (b.parts || []).find((x) => x.part === p.id);
  const bom = r.bom;
  return `<div class="card">
      <button class="ghost" id="b3d" style="float:right">${built3d.has(p.id) ? 'Back to the solid' : 'Show how it\'s built'}</button>
      <b style="font-size:1.3em">${lbs(r.mass_lb)}</b> ${changed ? '<span class="badge">trying — not saved</span>' : ''}
      ${r.unweighed ? `<div class="small" style="color:var(--amber)">Its weight isn't known: ${esc(r.unweighed)}.</div>`   // never the rest's (#125)
        : `<div class="small">centre of gravity ${cogText(p, r.cog)} <span class="muted">(the red dot)</span></div>`}
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
    ${solidSaid(r)}
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
      ${bom.fasteners ? `<li><b>${bom.fasteners.screws} × ${esc(bom.fasteners.screw)}</b> and <b>${esc(bom.fasteners.glue)}</b>
        <div class="muted small">${esc(bom.fasteners.basis)}</div></li>` : ''}
      ${(bom.printed || []).map((g) => `<li><b>${esc(g.label)}</b>: ${esc(g.name)} <span class="muted">${Math.round(g.filament_g)} g of filament${g.filament_from ? `, ${esc(g.filament_from)}` : ''}
        (the model: ${g.volume_cm3} cm³ at ${Math.round(g.infill * 100)}% infill)</span></li>`).join('')}
    </ul>
    ${jointsHtml(r)}
    ${(r.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    <div class="muted small" style="margin-top:4px">Counts are a shopping estimate (panels packed on whole sheets, cuts on
      whole sticks); the cut plan below nests the real shapes. Densities: <code>materials.py</code>.</div>
`;
}

// made in your shop (CALI-48): what cuts each piece, printed parts fitted to the printer, and what's missing
// its plan's key (#331 review): this design's, this version's, this shop's. Without the design, another design's plan
// for a part of the same name and version stood in for this one's
function makingKey(p) {
  return `${S.slug}:${p.id}:${p.version}:${S.shopKey || 0}`;
}
// its header: only this plan's answer. The route answers a part that doesn't build with a 422, never a plan (#331
// review: the broken-build copy read "planning…" over its error); any other failed read says so, never ✓ or ✗
function makingSection(p) {
  const m = S.making[p.id], mine = m && m.key === makingKey(p) ? m : null, shop = mine && mine.data;
  const failed = !!mine && !shop && mine.error != null;
  return { k: 'shop', title: 'Made in your shop', tone: shop ? (shop.ok ? 'ok' : 'bad') : 'info',
    answer: shop ? (shop.ok ? 'all of it' : 'not all of it') : !failed ? 'planning…'
      : mine.status === 422 ? "can't plan it: it doesn't build" : "couldn't plan it",
    body: `<div id="makingBox">${makingView(p)}</div>` };
}
function makingView(p) {
  const key = makingKey(p);
  const m = S.making[p.id];
  const planning = '<h5 style="margin:14px 0 4px">Made in your shop</h5><div class="small muted">planning…</div>';
  if (!m || m.key !== key) { loadMaking(p, key); return planning; }
  if (m.loading) return planning;                  // still out: a redraw meanwhile read m.data and threw (CALI-101)
  if (m.error) return `<h5 style="margin:14px 0 4px">Made in your shop</h5><div class="small" style="color:var(--bad)">⚠ ${esc(m.error)}</div>`;
  const d = m.data;
  const notes = (how) => d.pieces.filter((x) => x.how === how && x.why).map((x) => esc(x.why));
  return `<h5 style="margin:14px 0 4px">Made in your shop ${d.ok ? '<span class="badge ok">all of it</span>' : '<span class="badge bad">not all of it</span>'}</h5>
    ${d.shop_default ? '<div class="muted small">Planned for hand tools: a jigsaw, a drill, a circular saw. <a href="#" class="openShop">Say what\'s in your shop</a>.</div>' : ''}
    <ul class="list small">${Object.entries(d.by_how).map(([how, names]) => `<li><b>${esc(how)}</b>: ${names.map(esc).join(', ')}
      ${[...new Set(notes(how))].map((n) => `<div class="muted">${n}</div>`).join('')}</li>`).join('')}
      ${d.printed.map((x) => `<li><b>printer</b>: ${esc(x.name)} in ${esc(x.material.toUpperCase())}, ${x.pieces} piece${x.pieces === 1 ? '' : 's'}${x.pinned
        ? ' pinned together' : ''} · about <b>${x.hours} h</b>, ${x.filament_g.toLocaleString()} g, $${x.usd.toFixed(2)}
        <div class="muted">${esc(x.rough_said || x.from)}</div></li>`).join('')}
      ${d.missing.map((x) => `<li style="color:var(--bad)">✗ <b>${esc(x.name)}</b>: ${esc(x.why)}</li>`).join('')}</ul>`;
}
async function loadMaking(p, key) {
  S.making[p.id] = { key, loading: true };
  try { S.making[p.id] = { key, data: await api('GET', `/api/designs/${S.slug}/parts/${p.id}/making`) }; }
  catch (e) { S.making[p.id] = { key, error: e.message, status: e.status }; }
  const box = $('makingBox');
  if (!box || shownPart() !== p.id || key !== makingKey(p)) return;    // another part or design on screen by now
  box.innerHTML = makingView(p); wireMaking();
  const sec = box.closest('details'), head = sec && sec.querySelector('summary'), x = makingSection(p);
  if (head) head.innerHTML = subHead(x);           // its header, drawn before its plan came back (#331 review)
  if (sec) { sec.className = sec.className.replace(/\bt-\w+/, `t-${x.tone}`); sec.classList.toggle('attn', ATTN(x.tone)); }
}
function wireMaking() {
  document.querySelectorAll('#inspector .openShop').forEach((a) => { a.onclick = (e) => { e.preventDefault(); openShop(); }; });
}

// your shop (CALI-48): what you have to make things with — every design plans its making with it
async function openShop() {
  S.shopOpen = true;
  try { S.shop = await api('GET', '/api/shop'); } catch (e) { showErr(e.message); return; }
  renderShop();
}
function renderShop() {
  const el = $('shopPage');
  el.hidden = !S.shopOpen;
  $('shopBtn').classList.toggle('on', !!S.shopOpen);
  if (!S.shopOpen || !S.shop) return;
  const sh = S.shop.shop, have = new Set(sh.hand || []);
  const mach = (k) => (sh.machines || []).find((m) => m.kind === k) || null;
  const r = mach('router'), pl = mach('plasma'), pr = mach('printer');
  const num = (id, v, step) => `<input type="number" id="${id}" value="${v}" min="0" step="${step || 1}">`;
  el.innerHTML = `<div class="studies-head"><h2>Your shop <span class="muted small">what Caliper plans the making with, for every design</span></h2>
      <button class="x" id="shopClose" title="close (Esc)">×</button></div>
    <h4>Hand tools</h4>
    <div class="shop-tools">${Object.entries(S.shop.hand).map(([k, what]) => `<label><input type="checkbox" class="shopHand" value="${esc(k)}"
      ${have.has(k) ? 'checked' : ''}><span><b>${esc(k)}</b><br><span class="muted">${esc(what)}</span></span></label>`).join('')}</div>
    <h4>Machines</h4>
    <div class="shop-machine"><label><input type="checkbox" id="mRouter" ${r ? 'checked' : ''}> <b>CNC router</b></label>
      <span class="small muted"> bed ${num('mRouterW', r ? r.bed_in[0] : 48)} × ${num('mRouterH', r ? r.bed_in[1] : 96)} in · cuts plywood and foam</span></div>
    <div class="shop-machine"><label><input type="checkbox" id="mPlasma" ${pl ? 'checked' : ''}> <b>Plasma table</b></label>
      <span class="small muted"> bed ${num('mPlasmaW', pl ? pl.bed_in[0] : 48)} × ${num('mPlasmaH', pl ? pl.bed_in[1] : 48)} in ·
        plate up to ${num('mPlasmaT', pl ? pl.plate_max_in : 0.375, 0.0625)} in</span></div>
    <div class="shop-machine"><label><input type="checkbox" id="mPrinter" ${pr ? 'checked' : ''}> <b>3D printer</b></label>
      <span class="small muted"> build volume ${num('mPrX', pr ? pr.volume_mm[0] : 256)} × ${num('mPrY', pr ? pr.volume_mm[1] : 256)} ×
        ${num('mPrZ', pr ? pr.volume_mm[2] : 256)} mm ·
        <label><input type="checkbox" class="mPrMat" value="pla" ${!pr || (pr.materials || []).includes('pla') ? 'checked' : ''}> PLA</label>
        <label><input type="checkbox" class="mPrMat" value="petg" ${!pr || (pr.materials || []).includes('petg') ? 'checked' : ''}> PETG</label></span></div>
    <div class="actions"><button class="primary" id="shopSave">Save</button> <span class="small muted" id="shopMsg">${sh.default
      ? 'Nothing saved yet: Caliper assumes a jigsaw, a drill and a circular saw.' : ''}</span></div>`;
  $('shopClose').onclick = () => { S.shopOpen = false; renderShop(); };
  $('shopSave').onclick = saveShop;
}
async function saveShop() {
  const n = (id) => +$(id).value || 0;
  const machines = [];
  if ($('mRouter').checked) machines.push({ kind: 'router', bed_in: [n('mRouterW'), n('mRouterH')], materials: ['plywood', 'xps', 'eps'] });
  if ($('mPlasma').checked) machines.push({ kind: 'plasma', bed_in: [n('mPlasmaW'), n('mPlasmaH')], plate_max_in: n('mPlasmaT'), materials: ['steel'] });
  if ($('mPrinter').checked) machines.push({ kind: 'printer', volume_mm: [n('mPrX'), n('mPrY'), n('mPrZ')],
    materials: [...document.querySelectorAll('.mPrMat:checked')].map((c) => c.value) });
  const hand = [...document.querySelectorAll('.shopHand:checked')].map((c) => c.value);
  try {
    S.shop = await api('PUT', '/api/shop', { hand, machines });
    S.shopKey = (S.shopKey || 0) + 1;            // every part's making plan is re-read with the new shop
    S.shopOpen = false; renderShop(); renderInspector();
  } catch (e) { $('shopMsg').textContent = '⚠ ' + e.message; }
}
$('shopBtn').onclick = () => (S.shopOpen ? (S.shopOpen = false, renderShop()) : openShop());
addEventListener('keydown', (e) => { if (e.key === 'Escape' && S.shopOpen) { S.shopOpen = false; renderShop(); } });

// patterns for hand tools (CALI-48): most people have a jigsaw, not a CNC router — so every flat piece, holes and
// all, to measure and mark, to print full size and tape, or to project and trace
// a lightening step on screen isn't the part until it's cut in (CALI-83: patterns made while previewing one had no
// holes, and that read as a bug)
// a picked Lighten step: these are the part's as it is, and the step's own can be previewed without cutting it in (#297)
function previewNote(p, what) {
  const run = S.station && S.station.part === p.id ? (S.design.lighten_runs || []).find((r) => r.id === S.station.run) : null;
  if (!run) return '';
  const st = (run.stations || []).find((x) => x.index === S.station.index);
  const can = what && st && st.index > 0 && !st.estimate && !run.not_trusted;
  return `<div class="note-warn small">These are of the ${esc(p.name || p.id)} as it is, without the step you're previewing.
      <b>Cut these holes</b> (in the bar under the 3D view) to make it part of it, then make them again.
      ${can ? `<div class="actions" style="margin-top:6px"><button data-preview="${what}">Preview step ${st.index}'s ${what === 'cutplan' ? 'cut plan' : 'patterns'}</button></div>
        <div data-preview-out="${what}"></div>` : ''}</div>`;
}
// the step's patterns or cut plan, made in a scratch copy of the design: no version, every file named preview (#297)
async function previewStep(b) {
  const st = S.station, what = b.dataset.preview;
  const out = document.querySelector(`[data-preview-out="${what}"]`);
  const said = what === 'cutplan' ? 'cut plan' : 'patterns';
  b.disabled = true;
  if (out) out.innerHTML = `<div class="small muted">making step ${st.index}'s ${said} in a scratch copy…</div>`;
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/lighten/${st.run}/stations/${st.index}/preview`, { what });
    const got = await follow(job_id, (ev) => { if (out && ev.text && ev.kind !== 'started') out.innerHTML = `<div class="small muted">${esc(ev.text)}</div>`; });
    if (out) out.innerHTML = `<div class="small" style="margin-top:4px"><a href="${esc(got.url)}" target="_blank" rel="noopener"><b>Open step ${st.index}'s ${said} ↗</b></a>
      <span class="muted">a preview: not the part's until its holes are cut in</span></div>`;
  } catch (e) {
    if (out) out.innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`;
  }
  b.disabled = false;
}
function patternView(p) {
  if (p.not_accounted) return `<div class="small muted">No patterns yet: its pieces don't account for its solid.</div>`;
  const run = (S.design.pattern_runs || []).find((r) => r.part === p.id);
  const url = (name) => `/api/designs/${S.slug}/patterns/${run.id}/${name}`;
  const stale = run && run.version !== p.version;
  return `<h5 style="margin:14px 0 4px">Patterns for hand tools <span class="badge">jigsaw, saw, drill</span></h5>${previewNote(p, 'patterns')}
    ${run ? `<div class="small">${stale ? '<span class="badge bad">the part has changed since</span> ' : ''}
        <a href="${url('measure-and-mark.pdf')}" target="_blank" rel="noopener"><b>Measure and mark</b></a>: each piece
        dimensioned from its square edges, on a 1 in grid ·
        <a href="${url('print-full-size.pdf')}" target="_blank" rel="noopener"><b>Print full size</b></a> (${run.pages} letter pages:
        print at 100% and tape) · <b>Project and trace</b>: ${run.pieces.map((x) => `<a href="${url(x.project)}" target="_blank"
          rel="noopener">${esc(x.name)}</a>`).join(', ')}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px">${run.pieces.map((x) => `<a href="${url('index.html')}"
        target="_blank" rel="noopener" title="${esc(x.name)}"><img src="${url(x.thumb)}" alt="${esc(x.name)}"
        style="width:100%;background:#fff;border-radius:4px;display:block"></a>`).join('')}</div>` : `<div class="muted small">For a
      jigsaw and a tape measure: each piece dimensioned to mark out, at full size to print and tape, or to project
      and trace. Holes included.</div>`}
    <div class="actions"><button id="patGo">${run ? 'Make them again' : 'Make the patterns'}</button></div>
    <div id="patProgress"></div>`;
}

function wirePatterns(p) {
  const go = $('patGo');
  if (!go) return;
  go.onclick = async () => {
    go.disabled = true;
    $('patProgress').innerHTML = '<div class="small muted">drawing every piece…</div>';
    try {
      const got = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/patterns`);
      S.design = got.design;
      render();
    } catch (e) {
      $('patProgress').innerHTML = `<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`;
      go.disabled = false;
    }
  };
}

// --------------------------------------------------------------------- cut plan (CALI-45)
// Every panel flattened and nested onto the sheets it's cut from by Theo's unfold-to-sheets — score lines
// where a panel bends — and every stick cut-listed. Sheets as SVG (click for full size) and DXF for CAM.
// each panel whose grain the person said, as the maker reads it, and whether the layout below follows it (CALI-126,
// #151 review): never a "cut it front to back" line beside a layout that turned it
function cutGrain(p, run) {
  return Object.entries(p.grain || {}).map(([piece, g]) => {
    const got = run && run.version === p.version ? (run.grain || []).find((x) => x.piece === piece) : null;
    const tail = !run ? ''
      : !got ? ' <span style="color:var(--warn)">Make the cut plan again so its layout follows it.</span>'
        : got.follows ? ' <span class="muted">The layout below lays it that way.</span>'
          : ` <span style="color:var(--bad)">The layout below doesn't (${esc(got.why)}): lay it out by hand.</span>`;
    return `<div class="small" style="margin-top:4px">↔ ${esc(g.line)}${tail}</div>`;
  }).join('');
}
function cutplanView(p) {
  if (S.design.cutplan_unavailable) return `<h5 style="margin:14px 0 4px">Cut plan</h5>
    <div class="muted small">Not here: ${esc(S.design.cutplan_unavailable)}.</div>`;
  const run = (S.design.cutplans || []).find((r) => r.part === p.id);
  const url = (path) => `/api/designs/${S.slug}/cutplans/${run.id}/files/${path}`;
  const note = previewNote(p, 'cutplan');
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
  return `<h5 style="margin:14px 0 4px">Cut plan</h5>${note}
    ${cutGrain(p, run)}
    ${run ? `${stale}${sheets}${plates}${tubes}${sticks}<div class="small"><a href="${url('cutlist.txt')}" target="_blank">cut list as text</a></div>
      ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`
      : `<div class="muted small">Flatten every panel onto the sheets it's cut from — score lines where it bends — and list every
         stick to cut. Uses unfold-to-sheets.</div>`}
    <div id="cpProgress"></div>`;
}

function wireCutplan(p) {
  wirePatterns(p);
  wireMaking();
  document.querySelectorAll('[data-preview]').forEach((b) => { b.onclick = () => previewStep(b); });
  const go = $('cpGo');
  if (!go) return;
  // where its section has no progress line (cut plans can't be made here), what it says goes under the buttons: a
  // click never throws and leaves the button dead (#331 review)
  const say = (html, text) => { const pr = $('cpProgress'), w = $('pactsWhy'); if (pr) pr.innerHTML = html; else if (w) w.textContent = text; };
  go.onclick = async () => {
    go.disabled = true;
    say('<div class="small muted" id="cpMsg">unfolding…</div>', 'unfolding…');
    try {
      const { job_id } = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/cutplan`);
      trackJob(job_id, { kind: 'cutplan', part: p.id, text: 'unfolding…' }).done.catch(() => {});   // the overlay (#363)
      await follow(job_id, (ev) => { const m = $('cpMsg'); if (m && ev.text && ev.kind !== 'started') m.textContent = ev.text; });
      await refresh();
    } catch (e) {
      say(`<div class="small" style="color:var(--bad)">⚠ ${esc(e.message)}</div>`, `⚠ ${e.message}`);
      go.disabled = false;
    }
  };
}

function wireBuilt(p) {
  const c = S.built[p.id];
  if (!c || !c.report) return;
  wireCutplan(p);
  const b3 = $('b3d');
  if (b3) b3.onclick = async () => {
    b3.disabled = true;
    try { await showBuilt3d(p.id, !built3d.has(p.id)); } catch (e) { showErr(e.message); }
    b3.disabled = false; b3.textContent = built3d.has(p.id) ? 'Back to the solid' : "Show how it's built";
  };
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
  const hitch = b.moment_lbin != null;           // only when a part declares where it's held (a hitch)
  const part = (x) => (x.part === 'payload' ? 'payload' : `<span class="partlink" data-part="${esc(x.part)}">${esc(x.part)}</span>`);
  return `<div class="card"><b style="font-size:1.3em">${lbs(b.mass_lb)}</b> ${tried ? '<span class="badge">with what-ifs</span>' : ''}
      ${b.unweighed ? `<div class="small" style="color:var(--amber)">The total isn't known: ${esc(b.unweighed.join('; '))}.</div>` : ''}
      ${hitch ? `<div class="small">The hitch carries <b>${lbs(b.force_lb)}</b> with its centre of gravity
        ${len(b.arm_in * IN, 1)} behind it: <b>${lbin(b.moment_lbin)}</b> standing still.</div>
      <div class="muted small" style="margin-top:4px">${HITCH_NOTE}</div>` : ''}</div>
    ${hitch ? `<div class="form" style="margin-top:8px"><span>payload</span>
      <span><input type="number" id="payload" value="${S.payload}" min="0" step="10"> lb on the floor</span></div>` : ''}
    ${b.parts.length > 1 || hitch ? `<table class="st"><tr><th style="text-align:left">part</th><th>lb</th>${hitch ? '<th>behind hitch</th><th>lb·in</th>' : ''}</tr>
      ${b.parts.map((x) => `<tr><td style="text-align:left">${part(x)}</td><td>${x.mass_lb}</td>${hitch
        ? `<td>${x.arm_in != null ? len(x.arm_in * IN, 1) : '—'}</td><td>${x.moment_lbin != null ? Number(x.moment_lbin).toLocaleString() : '—'}</td>` : ''}</tr>`).join('')}</table>` : ''}
    ${(b.notes || []).map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}
    <div class="muted small" style="margin-top:4px">Red dot: the centre of gravity.${hitch ? ' Green: the hitch point.' : ''}</div>`;
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
  if (S.station && S.station.kind === 'load') return;     // the stress picture has the floor to itself
  const shown = shownPart(), c = shown && S.built[shown];       // the part whose view is on screen, picked or not (#364)
  const b = shown ? (c && c.balance) : (S.balance && S.balance.data);
  const cog = shown ? (c && c.report && c.report.cog) : (b && b.mass_kg ? b.cog : null);
  const across = contentBox().getSize(new THREE.Vector3()).length();
  const size = Math.max(across / 160, Math.min(8, across / 25));    // 8 mm would cover most of a small part
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
  if (b && b.hitch && (!shown || cog)) dot(b.hitch, 0x3fb950);
  // what the part has to hold (keeps(): the mattress) — a pale slab if it fits, red if the outside cuts in
  for (const k of (shown && c && c.report && c.report.keeps) || []) {
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
// ------------------------------------------------------------- will it hold? (CALI-54)
// The part's own loads() — an adult stepping up, a shelf of books — through whittle's voxel FEA and, for a
// panel pushed on face-on, a plate check; the verdict is the worse of the two. Each load has a stress picture.
function loadRuns(pid) { return (S.design.load_runs || []).filter((r) => r.part === pid); }

function loadView(p) {
  if (!S.design.aero_available) return '<div class="empty">whittle isn\'t installed in Caliper\'s environment.</div>';
  if (!p.loads) {                               // the designer's way, or the person's own in the editor (#327)
    return `<div class="empty">It doesn't say what it must hold yet: add a scenario below, or tell me, like “it has to
      hold me, 200 lb, stepping onto the top”, and I'll add its <code>loads()</code>.</div>
      <div class="actions"><button id="lAsk">Say what it must hold</button></div>
      ${scenariosBox(p)}`;
  }
  const runs = loadRuns(p.id);
  const pick = Math.min(S.loadRun[p.id] || 0, Math.max(runs.length - 1, 0));
  return `<div class="form">
      <span>least safety</span><span><input type="number" id="lSafety" value="${(runs[0] && runs[0].min_safety) || 2}" min="1" max="10" step="0.5">
        × at each load times its factor</span></div>
    <div class="actions">${runs[0] && runs[0].finer && runs[0].version === p.version ? `<button id="lFiner" title="voxels of ${wallLen(runs[0].finer.spacing_mm)}, enough
        to see its ${wallLen(runs[0].thinnest_mm)} walls">Check it again finer${runs[0].finer.minutes ? ` (about ${runs[0].finer.minutes} min)` : ' (how long: unknown)'}</button>` : ''}</div>
    ${scenariosBox(p)}
    <div id="lProgress"></div>
    ${runs.length ? loadResults(p, runs[pick], runs) : ''}`;
}

// --------------------------------------------------------------------- scenarios and supports (CALI-185, #296 slice A)
// What it must hold and what holds it, as rows the person edits: kept in design.yaml in place of the script's loads() and
// HELD. Saving writes a new version of the part (the same script), so its checks read "older version" (Rule 6).
const SCEN_DIRS = { down: [0, 0, -1], front: [0, -1, 0], back: [0, 1, 0], left: [-1, 0, 0], right: [1, 0, 0] };
const SCEN_SAID = { down: 'down', front: 'toward the front', back: 'toward the back', left: 'toward the left',
  right: 'toward the right', angle: 'at an angle…' };
// a direction from the picker: one of SCEN_DIRS, or an angle from straight down and a heading (0 toward the front,
// 90 toward the right), the front at -y as the rest of Caliper has it
function dirFromPick(kind, deg, heading) {
  if (SCEN_DIRS[kind]) return SCEN_DIRS[kind].slice();
  const t = (Number(deg) || 0) * Math.PI / 180, h = (Number(heading) || 0) * Math.PI / 180;
  const r = (v) => Math.round(v * 1e6) / 1e6;
  return [r(Math.sin(t) * Math.sin(h)), r(-Math.sin(t) * Math.cos(h)), r(-Math.cos(t))];
}
function pickFromDir(d) {
  const n = Math.hypot(...d) || 1, u = d.map((v) => v / n);
  for (const [k, v] of Object.entries(SCEN_DIRS)) if (v.every((x, i) => Math.abs(x - u[i]) < 1e-6)) return { kind: k };
  const deg = Math.acos(Math.max(-1, Math.min(1, -u[2]))) * 180 / Math.PI;
  const heading = ((Math.atan2(u[0], -u[1]) * 180 / Math.PI) + 360) % 360;
  return { kind: 'angle', deg: Math.round(deg * 10) / 10, heading: Math.round(heading * 10) / 10 };
}
const xyz = (v) => (v || []).map((x) => Math.round(Number(x) * 1000) / 1000).join(', ');
// a field left as it was shown keeps its exact value, never the shown rounding (a standard's case put back read edited)
function keptXyz(was, text) {
  if (was && text.trim() === xyz(was)) return was;
  return String(text).split(',').map((v) => Number(v.trim()));
}
function keptDir(was, kind, deg, heading) {
  const shown = pickFromDir(was || [0, 0, -1]);
  if (was && kind === shown.kind && (kind !== 'angle' || (Number(deg) === shown.deg && Number(heading) === shown.heading))) return was;
  return dirFromPick(kind, deg, heading);
}
function scenarioRow(sc, i) {
  const d = pickFromDir(sc.direction || [0, 0, -1]);
  const std = sc.standard ? `<div class="small muted">a standard's case: ${esc(sc.standard.name)}
      ${sc.standard.amount !== sc.amount || sc.standard.unit !== sc.unit ? `; the standard is ${sc.standard.amount} ${esc(sc.standard.unit)}` : ''}
      <button class="ghost" data-scen-std="${i}">Back to the standard</button></div>` : '';
  // the design changed a case under an edit of yours, or dropped it: asked, never settled for you (#312 re-check)
  // until they choose, what's checked is said; a Save settles only the rows chosen on (#312 third round)
  const asked = sc.conflict ? `<div class="small" style="color:var(--amber)">${esc(sc.conflict)}${sc.checked ? `: ${esc(sc.checked)}` : ''}.
      ${sc.keep ? '<span class="muted">yours, kept when you save.</span>'
        : `${sc.design ? `<button class="ghost" data-scen-take="${i}">Take the design's</button>` : ''}<button class="ghost" data-scen-keep="${i}">Keep mine</button>`}</div>`
    : sc.new ? '<div class="small muted">the design added this case since you edited them: it\'s checked as the script has it.</div>' : '';
  const whose = sc.source === 'edited' ? 'yours' : sc.source === 'added' ? 'yours, added' : sc.source === 'script' ? 'its script\'s' : '';
  return `<div class="card scen" data-scen="${i}" style="margin-top:6px">${asked}${whose ? `<div class="small muted">${whose}</div>` : ''}
      <div class="form"><span>what</span><span><input data-f="name" value="${esc(sc.said || sc.name)}"${sc.standard ? ' readonly title="a standard\'s case is named for what it is: edit its numbers"' : ''} style="width:100%"></span>
      <span>how much</span><span><input data-f="amount" type="number" step="any" min="0" value="${sc.amount}" style="width:7em">
        <select data-f="unit">${['lb', 'kg', 'N'].map((u) => `<option${u === sc.unit ? ' selected' : ''}>${u}</option>`).join('')}</select></span>
      <span>which way</span><span><select data-f="dir">${Object.entries(SCEN_SAID).map(([k, w]) =>
        `<option value="${k}"${k === d.kind ? ' selected' : ''}>${w}</option>`).join('')}</select>
        <span data-angle ${d.kind === 'angle' ? '' : 'hidden'}><input data-f="deg" type="number" step="any" value="${d.deg ?? 0}" style="width:5em">°
          from straight down, heading <input data-f="heading" type="number" step="any" value="${d.heading ?? 0}" style="width:5em">°</span></span>
      <span>margin</span><span>× <input data-f="factor" type="number" step="any" min="0" value="${sc.factor}" style="width:5em"></span>
      <span>where</span><span><input data-f="lo" value="${xyz(sc.lo)}" title="one corner of the box it pushes on, x, y, z mm" style="width:12em"> to
        <input data-f="hi" value="${xyz(sc.hi)}" title="the opposite corner" style="width:12em"> mm</span>
      <span>checked</span><span><label><input data-f="on" type="checkbox"${sc.on === false ? '' : ' checked'}> on</label>
        <button class="ghost" data-scen-del="${i}">Remove</button></span></div>${std}</div>`;
}
function supportRow(s, i) {
  if (s.floor) return `<div class="small" data-sup="${i}" data-floor="1" style="margin-top:4px">• the floor at its underside
      <button class="ghost" data-sup-del="${i}">Remove</button></div>`;
  return `<div class="small" data-sup="${i}" style="margin-top:4px">• <input data-f="name" value="${esc(s.name)}">
      <input data-f="lo" value="${xyz(s.lo)}" style="width:12em"> to <input data-f="hi" value="${xyz(s.hi)}" style="width:12em"> mm
      <button class="ghost" data-sup-del="${i}">Remove</button></div>`;
}
// the first case added to a part whose script says none: across the whole top of its box, 2 mm deep, so it rests on whatever
// is highest (a roof, or an open box's wall tops) and the first save works; the person narrows it from there (#337 review: a
// 10 mm box at the origin pushed on thin air, 453.6 mm from the cargo box)
function newLoadBox(p) {
  const b = p && p.bbox;
  if (!b || !b.min || !b.max) return { lo: [0, 0, 0], hi: [10, 10, 10] };
  const r = (v) => Math.round(v * 10) / 10;
  return { lo: [r(b.min[0]), r(b.min[1]), r(b.max[2] - 2)], hi: [r(b.max[0]), r(b.max[1]), r(b.max[2])] };
}
function scenariosView(p, got) {
  if (!got) return '<div class="small muted">reading them…</div>';
  // none of them its script's: none, or added here (#327), saved or not (#337 review: saved, it read "…the rest as its
  // script says them" where its script says none)
  const none = !got.scenarios.some((s) => s.source === 'script');
  return `${none ? `<div class="small">Its script doesn't say what it must hold: ${!got.scenarios.length ? 'add a scenario'
        : got.overridden ? 'these are yours, and what it\'s checked against' : 'save yours to keep them'}.</div>`
      : got.overridden ? '<div class="small">Yours where you edited them; the rest as its script says them, now and as it changes.</div>'
      : '<div class="small muted">As its script says them. Edit and save to keep yours instead.</div>'}
    ${got.scenarios.map(scenarioRow).join('')}
    <div class="actions"><button class="ghost" id="scenAdd">Add a scenario</button></div>
    <div style="margin-top:8px"><b class="small">What holds it</b>${got.supports.map(supportRow).join('')}</div>
    <div class="actions"><button class="ghost" id="supAdd">Add a support</button><button class="ghost" id="supFloor">The floor</button></div>
    <div class="actions"><button class="primary" id="scenSave">Save them</button>
      ${got.overridden ? '<button class="ghost" id="scenBack">Back to its script\'s</button>' : ''}</div>
    <div class="small muted">Saving makes a new version of ${esc(p.id)}, the same script: its checks, Lighten and carves are out
      of date until it's checked again.</div><div id="scenSaid"></div>`;
}
function scenariosBox(p) {
  const open = S.scenOpen === p.id;
  return `<details id="scenBox"${open ? ' open' : ''} style="margin-top:6px"><summary>Scenarios and supports
      <span class="muted small">what it must hold, and what holds it</span></summary>
      <div id="scenBody">${open ? scenariosView(p, (S.scen || {})[p.id]) : ''}</div></details>`;
}
// the rows as they stand in the page, back into scenarios and supports
function readScenarios(got) {
  const scen = [...document.querySelectorAll('#scenBody .scen')].map((el) => {
    const f = (k) => el.querySelector(`[data-f="${k}"]`);
    const i = +el.dataset.scen, was = got.scenarios[i] || {};
    return { ...was, name: was.standard ? was.name : f('name').value.trim(), amount: Number(f('amount').value), unit: f('unit').value,
      direction: keptDir(was.direction, f('dir').value, f('deg').value, f('heading').value), factor: Number(f('factor').value),
      lo: keptXyz(was.lo, f('lo').value), hi: keptXyz(was.hi, f('hi').value), on: f('on').checked };
  });
  const sup = [...document.querySelectorAll('#scenBody [data-sup]')].map((el) => {
    const was = got.supports[+el.dataset.sup] || {};
    return el.dataset.floor ? { name: 'the floor', floor: true }
      : { name: el.querySelector('[data-f="name"]').value.trim(), lo: keptXyz(was.lo, el.querySelector('[data-f="lo"]').value),
          hi: keptXyz(was.hi, el.querySelector('[data-f="hi"]').value) };
  });
  return { scenarios: scen, supports: sup };
}
function wireScenarios(p) {
  const box = $('scenBox');
  if (!box) return;
  const paint = () => { $('scenBody').innerHTML = scenariosView(p, (S.scen || {})[p.id]); wireScenarioRows(p); };
  box.ontoggle = async () => {
    S.scenOpen = box.open ? p.id : null;
    if (!box.open || $('scenSave')) return;      // painted already (a render with it open): keep what it says
    S.scen = S.scen || {};
    if (!S.scen[p.id]) { paint(); S.scen[p.id] = await api('GET', `/api/designs/${S.slug}/parts/${p.id}/scenarios`); }
    paint();
  };
  if (box.open) wireScenarioRows(p);
}
function wireScenarioRows(p) {
  const got = (S.scen || {})[p.id];
  if (!got) return;
  const keep = () => { S.scen[p.id] = { ...got, ...readScenarios(got) }; };
  const repaint = () => { $('scenBody').innerHTML = scenariosView(p, S.scen[p.id]); wireScenarioRows(p); };
  document.querySelectorAll('#scenBody [data-f="dir"]').forEach((sel) => {
    sel.onchange = () => { sel.parentElement.querySelector('[data-angle]').hidden = sel.value !== 'angle'; };
  });
  document.querySelectorAll('#scenBody [data-scen-del]').forEach((b) => {
    b.onclick = () => { keep(); S.scen[p.id].scenarios.splice(+b.dataset.scenDel, 1); repaint(); };
  });
  document.querySelectorAll('#scenBody [data-scen-std]').forEach((b) => {
    b.onclick = () => { keep(); const sc = S.scen[p.id].scenarios[+b.dataset.scenStd];
      S.scen[p.id].scenarios[+b.dataset.scenStd] = { ...sc.standard, standard: sc.standard, on: sc.on !== false }; repaint(); };
  });
  document.querySelectorAll('#scenBody [data-scen-take]').forEach((b) => {
    b.onclick = () => { keep(); const i = +b.dataset.scenTake, sc = S.scen[p.id].scenarios[i];
      S.scen[p.id].scenarios[i] = { ...sc.design, of: sc.of, source: 'script' }; repaint(); };
  });
  document.querySelectorAll('#scenBody [data-scen-keep]').forEach((b) => {
    b.onclick = () => { keep(); S.scen[p.id].scenarios[+b.dataset.scenKeep].keep = true; repaint(); };
  });
  document.querySelectorAll('#scenBody [data-sup-del]').forEach((b) => {
    b.onclick = () => { keep(); S.scen[p.id].supports.splice(+b.dataset.supDel, 1); repaint(); };
  });
  const add = $('scenAdd');
  if (add) add.onclick = () => { keep(); const last = S.scen[p.id].scenarios.slice(-1)[0] || {};
    const box = last.lo ? { lo: last.lo, hi: last.hi } : newLoadBox(p);
    S.scen[p.id].scenarios.push({ name: 'a new load', amount: 50, unit: 'lb', direction: [0, 0, -1], factor: 1, on: true,
      lo: box.lo, hi: box.hi }); repaint(); };
  const sAdd = $('supAdd');
  if (sAdd) sAdd.onclick = () => { keep(); S.scen[p.id].supports.push({ name: 'held here', lo: [0, 0, 0], hi: [10, 10, 10] }); repaint(); };
  const floor = $('supFloor');
  if (floor) floor.onclick = () => { keep(); if (!S.scen[p.id].supports.some((s) => s.floor)) S.scen[p.id].supports.push({ name: 'the floor', floor: true }); repaint(); };
  const said = (t, bad) => { $('scenSaid').innerHTML = `<div class="small" style="color:var(--${bad ? 'bad' : 'ok'})">${esc(t)}</div>`; };
  const save = $('scenSave');
  if (save) save.onclick = async () => {
    save.disabled = true;
    try {
      const got2 = await api('PUT', `/api/designs/${S.slug}/parts/${p.id}/scenarios`, readScenarios(got));
      S.scen[p.id] = got2.scenarios; S.design = got2.design; render();       // the tree's version too
      const open = (got2.open || []).length ? ` Still open, until you choose: ${got2.open.join('; ')}.` : '';
      said(`Saved as v${got2.version}.${open} Its checks are of the loads before: check it again.`);
    } catch (e) { save.disabled = false; said(plainly(e.message), true); }
  };
  const back = $('scenBack');
  if (back) back.onclick = async () => {
    back.disabled = true;
    try {
      const got2 = await api('DELETE', `/api/designs/${S.slug}/parts/${p.id}/scenarios`);
      S.scen[p.id] = got2.scenarios; S.design = got2.design; render();
      said(`Back to its script's, as v${got2.version}: check it again.`);
    } catch (e) { back.disabled = false; said(plainly(e.message), true); }
  };
}

// carve it (CALI-82): a printed part, carved free-form where it isn't working; each step checked
function carveRuns(pid) { return (S.design.carve_runs || []).filter((r) => r.part === pid); }
// what a carve's "removed" is a share of: a run from before CALI-86 counted the whole solid, and says so
function carveShare(run) {
  return run && run.share === 'printed' ? 'of the printed part'
    : 'of the whole solid (carved before CALI-86: carve again for the printed share)';
}
function carveView(p) {
  const run = carveRuns(p.id)[0];
  const head = `<h5 style="margin:14px 0 4px">Carve it <span class="badge">printed, any shape</span></h5>
    <div class="muted small">A printer makes any shape, so the printed part can be carved wherever it isn't working: in steps,
      each one checked. ${p.carved ? 'It\'s carved now; carving again starts from its shape as drawn.' : ''}</div>
    <div class="muted small">${esc(carveTime(p))}</div><div id="carveProgress">${carveProgress(p.id)}</div>`;
  if (!run) return head;
  if (run.status === 'cancelled' || run.status === 'timed_out') {   // stopped: the steps it finished (CALI-101)
    // past its limit isn't a cancel nobody made (#211 review)
    const stopped = run.status === 'timed_out' ? `Stopped at its ${run.limit_s ? run.limit_s / 3600 : 6}-hour limit` : 'Cancelled';
    return `${head}<div class="small"><b>${stopped}</b> after ${run.stations.length} of ${run.steps} steps${run.stations.length
      ? ': what it finished is below.' : ', before its first step.'}</div>${run.stations.length ? carveChart(p, run) : ''}`;
  }
  if (run.status === 'failed') {                   // it stopped on an error, and says which (CALI-103)
    return `${head}<div class="small"><b class="bad">The carve failed</b> after ${run.stations.length} of ${run.steps} steps: ${esc(run.error || '')}</div>`;
  }
  if (run.status === 'running' && S.carveJob[carveKey(p.id)]) return head;   // the live panel says where it is (CALI-101)
  if (run.status === 'running') {                  // on disk as it goes: still running, or it stopped (CALI-103)
    return `${head}<div class="small">Not finished: ${run.stations.length} of ${run.steps} steps checked.</div>`;
  }
  return head + carveChart(p, run);
}
function carveChart(p, run) {
  const stale = run.version !== p.version;
  const W = 300, H = 110, top = Math.max(...run.stations.map((x) => x.safety || 0), run.min_safety * 1.5);
  const x = (r) => 24 + (W - 34) * r / Math.max(...run.stations.map((s) => s.removed), 0.01);
  const y = (sf) => H - 16 - (H - 26) * Math.min(sf, top) / top;
  const dots = run.stations.map((st) => `<circle cx="${x(st.removed)}" cy="${y(st.safety || 0)}" r="5" data-carve="${st.index}"
    class="${verdictTone(st.verdict)}${S.station && S.station.run === run.id && S.station.index === st.index ? ' on' : ''}"><title>step ${st.index}: ${esc(st.verdict ? st.verdict.word : '')}</title></circle>`).join('');
  const line = run.stations.map((st, i) => `${i ? 'L' : 'M'}${x(st.removed)},${y(st.safety || 0)}`).join(' ');
  const best = run.stations.find((st) => st.index === run.best);
  return `${run.weak ? `<div class="note-warn small">${esc(run.weak)}</div>` : ''}
    <svg class="trial-chart" viewBox="0 0 ${W} ${H}"><line x1="24" x2="${W - 10}" y1="${y(run.min_safety)}" y2="${y(run.min_safety)}" class="brk"/>
      <text x="${W - 10}" y="${y(run.min_safety) - 3}" text-anchor="end">needs ${run.min_safety}x</text>
      <path d="${line}" fill="none" stroke="var(--accent)" stroke-width="1.5"/>${dots}
      <text x="24" y="${H - 3}">as drawn</text><text x="${W - 10}" y="${H - 3}" text-anchor="end">${carveShare(run)} carved away →</text></svg>
    <div class="small">${best && best.saved_g ? `The step to use: step <b>${best.index}</b>, ${Math.round(best.removed * 100)}% ${carveShare(run)}
      carved away, <b>${best.saved_g} g</b> less filament, the printed part ${best.safety}x;
      ${holdsHere(best) ? `the whole part ${best.at_most ? 'no higher than ' : ''}${best.whole}x`
        : best.verdict && best.verdict.kind === 'span' ? `<b style="color:var(--amber)">not settled: ${esc(best.verdict.why)}</b>`    // CALI-153
        : best.verdict && (best.verdict.kind === 'unresolved' || best.verdict.kind === 'unchecked')    // #101
          ? `<b style="color:var(--amber)">${esc(best.verdict.word)}: the voxels were too coarse to see its walls, so no step can be said to hold yet</b>`
        : `<b class="bad">${best.verdict && best.verdict.kind === 'untrusted' ? 'not trusted: a solid with more in it than its pieces' : `the whole part ${best.whole != null ? (best.at_most ? 'no higher than ' : '') + best.whole + 'x' : 'unchecked'}, so it doesn't hold`}</b>`}.`
      : run.offer ? '' : 'Nothing could come off and still hold.'}
      ${run.offer ? `<div class="${run.offer.kind === 'room' ? 'muted' : 'note-warn'} small" style="margin-top:4px">${esc(run.offer.said)}</div>` : ''}
      ${stale ? '<span class="badge">older version</span>' : ''}</div>
    <div class="muted small">Click a step to see it; <b>Carve it like this</b> makes it the part's shape and checks it again.</div>`;
}
// a refusal as a person reads it: the server's reason without the exception's name ("ValueError: …", #136 review)
const plainly = (msg) => String(msg ?? '').replace(/^[A-Za-z_.]*(Error|Exception):\s*/, '');
// a long job's ending that isn't a result: a person's own Cancel isn't an error, and a server that's away is said in words
function jobEnded(e) {
  if (e.status === 'cancelled') return '<div class="small muted" style="margin-top:6px">Cancelled.</div>';
  const said = /Failed to fetch|NetworkError|Load failed/.test(e.message) ? 'The server isn\'t answering. Its work may have stopped: this will read again when it\'s back.' : plainly(e.message);
  return `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(said)}</div>`;
}
const carveKey = (pid) => `${S.slug}/${pid}`;
// CALI-101: one click, one carve. The job is kept in S.carveJob[part] from the click until it ends, so the button
// stays disabled, a redraw draws the panel again (steps, bar, time left, Cancel), and a reload finds it by
// design.carving. The server refuses a second carve of the design (409) whatever the page does.
async function runCarve(p, again) {
  const key = carveKey(p.id);                      // held across the wait: the person can move to another design
  if (S.carveJob[key]) return;                     // already asked: a second click, or a second handler, does nothing
  S.carveJob[key] = { text: 'starting…', progress: 0, t0: Date.now() };
  paintCarve(p.id);
  const slug = S.slug;
  try {
    const runs = loadRuns(p.id);
    const { job_id } = await api('POST', `/api/designs/${slug}/carve`, { part: p.id, min_safety: runs[0] ? runs[0].min_safety : 2, again: !!again });
    await followCarve(p, job_id, false, key);
  } catch (e) {
    delete S.carveJob[key];
    if (S.slug !== slug) return;
    await refresh();                              // a 409: the carve that's running is in design.carving; it's followed
    const prog = $('carveProgress');
    if (prog && !S.carveJob[key]) prog.innerHTML = `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(plainly(e.message))}</div>`;
  }
}
async function followCarve(p, jobId, stopping, keyed) {
  const key = keyed || carveKey(p.id), slug = S.slug;
  const cj = S.carveJob[key] = { ...(S.carveJob[key] || { text: 'carving…', progress: 0, t0: Date.now() }), job: jobId };
  trackJob(jobId, { kind: 'carve', part: p.id, text: 'carving…', t0: cj.t0 }).done.catch(() => {});   // the overlay (#363)
  if (stopping) cj.stopping = true;                // asked to stop before this page loaded (#102 review)
  paintCarve(p.id);
  try {
    await follow(jobId, (ev) => {
      if (ev.kind === 'stopping') cj.stopping = true;
      if (ev.kind === 'started' && ev.limit_s) cj.limit = ev.limit_s;
      if (ev.text && ev.kind !== 'started') cj.text = ev.text;
      const m = /^step (\d+):/.exec(ev.text || ''), n = / in (\d+) steps/.exec(ev.text || '');
      if (m) cj.step = +m[1];
      if (n) cj.steps = +n[1];
      if (typeof ev.progress === 'number') {
        if (!cj.p0t && ev.progress > 0) { cj.p0t = Date.now(); cj.p0 = ev.progress; }
        cj.progress = ev.progress;
      }
      if (S.slug === slug) paintCarve(p.id);
    });
    delete S.carveJob[key];
    if (S.slug !== slug) return;                  // it finished while another design was open: that design's page shows it
    clearStation();
    await refresh();
    const run = carveRuns(p.id)[0];
    if (run && run.best) showStation(p.id, run, run.best);
  } catch (e) {
    delete S.carveJob[key];
    if (S.slug !== slug) return;
    await refresh();                              // a cancelled or failed carve: its record says how far it got
    if (e.status !== 'cancelled') {
      const prog = $('carveProgress');
      if (prog) prog.innerHTML = `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(e.message)}</div>`;
    }
  }
}
// the panel while a carve runs: the step it's on, the bar, about how long is left (from its pace so far), and Cancel
// how long a carve has run, from its start, always shown: 9.5 min of a sweep said nothing (#137 item 4)
// and where it will stop: a study has a limit, said beside it (#66 item 2)
const ran = (cj) => (cj && cj.t0 && !cj.stopping ? ` · running for ${minutesText((Date.now() - cj.t0) / 60000)}${cj.limit ? ` (it stops at a step after ${cj.limit >= 3600 ? `${cj.limit / 3600} hours` : `${Math.round(cj.limit / 60)} min`})` : ''}` : '');
// the panel's time moves while nothing else does: the sweep before step 1 reports little
setInterval(() => {
  const mine = `${S.slug}/`;
  for (const key of Object.keys(S.carveJob || {})) if (key.startsWith(mine)) paintCarve(key.slice(mine.length));
}, 30000);
function carveProgress(pid) {
  const cj = S.carveJob[carveKey(pid)];
  if (!cj) return '';
  const pct = Math.round((cj.progress || 0) * 100);
  let left = '';
  if (!cj.stopping && cj.p0t && cj.progress > cj.p0 + 0.01 && Date.now() - cj.p0t > 15000) {
    const min = (Date.now() - cj.p0t) / (cj.progress - cj.p0) * (1 - cj.progress) / 60000;
    left = ` · about ${min < 1.5 ? '1 min' : min < 90 ? `${Math.round(min)} min` : `${(min / 60).toFixed(1)} h`} left`;
  }
  const where = cj.step != null && cj.steps ? `step ${cj.step + 1} of ${cj.steps}: ` : '';   // one count (#102)
  return `<div class="bar"><i style="width:${pct}%"></i></div>
    <div class="small muted" id="carveMsg">${esc(cj.stopping ? 'stopping at the next step…'
      : where + (where ? (cj.text || '').replace(/^step \d+: /, '') : cj.text || ''))}${left}${ran(cj)}</div>
    ${cj.job ? `<div class="actions"><button id="carveStop" ${cj.stopping ? 'disabled' : ''}>Cancel</button></div>` : ''}`;
}
function paintCarve(pid) {
  const prog = $('carveProgress'), go = $('carveGo');
  if (shownPart() !== pid) return;
  const part = ((S.design && S.design.parts) || []).find((x) => x.id === pid);
  // a carve its check blocks stays off after a job ends (#136 review: Cancel re-enabled "Carve it again")
  if (go) go.disabled = !!S.carveJob[carveKey(pid)] || !!(part && carveBlocked(part));
  if (!prog) return;
  prog.innerHTML = carveProgress(pid);
  const stop = $('carveStop');
  if (stop) stop.onclick = async () => {
    const cj = S.carveJob[carveKey(pid)];
    if (!cj || !cj.job) return;
    cj.stopping = true;
    paintCarve(pid);
    try { await api('POST', `/api/jobs/${cj.job}/cancel`); } catch (e) { showErr(e.message); }
  };
}
// what the button says before it's pressed: from the last carve of this part, or its strength check (a carve is
// one sweep and a check per step), never "a few minutes" for an hour's work
// A carve's time over its strength check's isn't a constant: 47 on the printed box, 67 on the mixed stool, about 65 on
// the bar stool's sweep, about 190 on the reviewer's tube (#102 review). So until a carve of the part has finished,
// the label is a floor, "at least about N min", from the low end; after one, that carve's own time.
const minutesText = (min) => (min < 1.5 ? '1 min' : min < 75 ? `${Math.round(min)} min` : min < 100 ? 'an hour'
  : `${(min / 60).toFixed(1)} hours`);
// what stops a carve (or a lightening) before it starts, in words, or '' (CALI-106, #101; #102's note): it already
// fails (#137 item 3), its walls are too thin (#136), its voxels don't connect. The server's one test
// (load_study.blocked), which the card's carve offer reads too, so the two can't disagree (#144 review)
function carveBlocked(p) {
  return (p && p.blocked && p.blocked.carve) || '';
}
function carveTime(p) {
  if (carveBlocked(p)) return carveBlocked(p);
  const done = carveRuns(p.id).find((r) => r.status === 'done' && r.seconds);
  if (done) return `about ${minutesText(done.seconds / 60)} at this size, as its last carve took`;
  return p.carve_takes || 'check it holds first: how long it takes comes from that';   // the server's words, as the card's
}
function wireCarve(p) {
  if ($('carveGo')) $('carveGo').onclick = (e) => runCarve(p, e.target.dataset.again === '1');   // only "Carve it again" says so
  const on = S.design && S.design.carving;           // a carve running since before this page: follow it (CALI-101)
  if (on && on.part === p.id && !S.carveJob[carveKey(p.id)]) followCarve(p, on.job, on.stopping);
  paintCarve(p.id);
  document.querySelectorAll('#inspector [data-carve]').forEach((c) => {
    c.onclick = () => showStation(p.id, carveRuns(p.id)[0], +c.dataset.carve);
  });
}

// make it lighter (CALI-71): holes where the wood isn't working, through the thickness, each step re-checked
// what stops a lightening before it starts, in words, or '': a part that already fails as drawn (#137 item 3), or
// walls too thin for any check a study may make (#101, #136)
function lightenBlocked(p) {
  return (p && p.blocked && p.blocked.lighten) || '';
}
// where a run's worst stress is: a piece by name only from a run that recorded the wall there (#137: an older run's
// "seat top" was the nearest wood to a hot spot in the printed cone), else how high up it is
function peakWhere(f) {
  if (f && f.in && f.wall_mm != null) return `in ${f.in}`;
  return f && f.at ? `around ${len(f.at[2])} up` : 'in the part';
}
function lightenRuns(pid) { return (S.design.lighten_runs || []).filter((r) => r.part === pid); }
// a Lightening's step, led by what's known (#252, #254): under the floor "too little"; one its re-check couldn't settle (unseen,
// unknown) "Not settled"; "The step to use" only where there's a button, or an older run with no offer
const lightenLead = (run) => (!run.offer ? 'The step to use' : run.offer.kind === 'small' ? 'Too little to use' : ['unseen', 'unknown'].includes(run.offer.kind) ? 'Not settled' : 'The step to use');
// with no step to use, what's known (#255): "Nothing lighter still holds" only where the steps were checked and failed; a step
// the check couldn't settle (too coarse, a span, untrusted) says so instead. A thinner sheet's estimate isn't a check
function lightenNone(run) {
  const deeper = run.stations.filter((x) => x.index && !x.estimate);
  const unsure = deeper.find((x) => x.verdict && ['unresolved', 'unchecked', 'span'].includes(x.verdict.kind));
  if (unsure) {
    return unsure.verdict.kind === 'span' ? `Not settled: ${unsure.verdict.why}, so no step can be said to hold.`
      : unsure.verdict.kind === 'unchecked' ? 'Not checked: its walls are too thin for the voxels, so no step can be said to hold.'
        : 'Not resolved yet: the check was too coarse to see its walls, so no step can be said to hold. Check it again finer.';
  }
  if (deeper.some((x) => !x.verdict || !['holds', 'close', 'fails'].includes(x.verdict.kind))) {
    return 'Not settled: none of its steps could be checked, so no step can be said to hold.';
  }
  return 'Nothing lighter still holds.';
}
// the Lighten panel: on a part of sheets with a strength check, and on any part with a Lighten run, though it's changed since
// (#268: v4 put printed strips in Theo's stool, the part read as printed, and its v3 run wasn't drawn at all)
function lightenShown(p, runs) {     // the rule the card and blocked() read: Lighten or Carve, never both (#272)
  return p.study === 'lighten' && (lightenRuns(p.id).length > 0 || runs.length > 0);
}
// a run of an older version: which, and what to do; its steps stay to look at, never to cut in (stationAction)
function lightenChanged(run, p) {
  if (!run || run.version == null || run.version === p.version) return '';
  return `Lightened v${run.version}, and you've changed it since (v${p.version}). ${lightenBlocked(p) ? `${esc(lightenBlocked(p))}.`
    : 'Lighten it again.'} Or look at v${run.version}'s steps below: they can't be cut into v${p.version}.`;   // (#272 re-check)
}
// what the Lighten panel leads with where the check couldn't see (or size) only the printed pieces Lighten leaves out (#276)
function lightenLeadLine(p) {
  const lead = p && p.blocked && p.blocked.lead;
  return lead ? `<div class="small" style="color:var(--amber);margin:2px 0 4px">${esc(lead)}</div>` : '';
}
function lightenView(p) {
  const run = lightenRuns(p.id)[0];
  const on = S.station && run && S.station.run === run.id ? S.station.index : -1;
  const best = run && run.offer ? run.stations.find((x) => x.index === run.offer.index)     // the step the card offers (#167)
    : run && run.stations.filter(holdsHere).reduce((a, x) => (!a || x.saved_lb > a.saved_lb ? x : a), null);
  const out = run && run.stations.find((x) => x.verdict && x.verdict.kind === 'fails');
  // steps the check was too coarse to call: their verdict's word, never "nothing lighter holds" (#136 review)
  const what = (x) => x.phase === 'thinner' ? `in ${esc(x.label)} sheet <span class="badge">estimate</span>`
    : x.phase === 'top' ? `${pct(x.removed)} of the walls + ${x.top_holes} hole${x.top_holes === 1 ? '' : 's'} in the top`
    : x.index ? `${pct(x.removed)} of the walls` : 'as it is';
  return `<h5 style="margin:14px 0 4px">Make it lighter</h5>
    ${lightenLeadLine(p)}
    <div class="muted small">Down until the safety runs out: holes in the walls where the wood isn't working (a jigsaw cuts
      them, a solid rim where it's glued and screwed), then hole-saw holes in the panel you stand on, one at a time,
      then thinner sheet. Every step is checked again.</div>
    ${lightenBlocked(p) ? `<div class="muted small">${esc(lightenBlocked(p))}</div>` : ''}
    <div id="lightProgress"></div>
    ${run ? `<div class="small" style="margin-top:6px">${best && best.saved_lb
      ? (run.not_trusted ? esc(run.not_trusted) : p.untrusted ? 'Not trusted: its strength check ran on a solid with more in it than its pieces, so no step can be said to hold.'
        : `${run.version != null && run.version !== p.version ? `v${run.version}'s lightest step that holds` : lightenLead(run)}: <b>${lbs(best.saved_lb)} lighter</b>, ${what(best)}, ${sx(best.safety, run.min_safety)}.${run.offer && (run.version == null || run.version === p.version) ? ` <span class="${run.offer.kind === 'room' ? 'muted' : ''}">${esc(run.offer.said)}</span>` : ''}`)
      : lightenNone(run)}${out ? ` It runs out at step ${out.index} (${sx(out.safety, run.min_safety)}).` : ''}
      ${lightenChanged(run, p) ? `<div class="small" style="color:var(--amber);margin-top:4px">${lightenChanged(run, p)}</div>` : ''}</div>
    <div class="tw"><table class="st"><tr><th>#</th><th style="text-align:left">what comes out</th><th>lighter</th><th>safety</th><th></th></tr>
      ${run.stations.map((x) => `<tr class="${x.estimate ? '' : 'pick'} ${x.index === on ? 'on' : ''}" ${x.estimate ? '' : `data-lst="${x.index}"`}>
        <td>${x.index}</td><td style="text-align:left">${what(x)}</td><td>${lbs(x.saved_lb)}</td>
        <td style="color:var(--${verdictTone(x.verdict)})">${sx(x.safety, run.min_safety)}</td>
        <td>${x.verdict && x.verdict.kind === 'estimate' ? sheetUse(run, x.label, x.thickness_mm, undefined, undefined,
          { text: `Ask for ${x.label} sheet (redesigns it; checked again after)`,
            off: askWait(on) }) : ''}</td></tr>`).join('')}</table></div>
    ${offWhy(run.stations.some((x) => x.verdict && x.verdict.kind === 'estimate') ? askWait(on) : '')}
    ${stepAction(p, run, on)}
    <div class="muted small" style="margin-top:4px">Click a step to see it, then cut its holes in with the button under the table.
      An estimate's <b>Ask for</b> redesigns it in that sheet, and it's checked again after.</div>
    ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}` : ''}`;
}

// a safety factor's number, as every reader says it, server and page (#208 review: answers.safety_num is the same
// rule, op for op): within 10% of what it needs either way, two places, cut; a fail further under, one place, cut;
// else one place, half up, never up to 10. So 1.995 against 2 is 1.99, never "2x" under a "doesn't hold" badge.
function safetyNum(x, need) {
  x = Number(x);
  if (x < 0.1) return 'under 0.1';        // never "0x" (#235 review)
  let n;
  if (need != null && x > need / 1.1 && x < need * 1.1) n = Math.floor(x * 100 + 1e-9) / 100;
  else if (need != null && x < need) n = Math.floor(x * 10 + 1e-9) / 10;
  else {
    n = Math.floor(x * 10 + 0.5) / 10;
    if (n >= 10 && x < 10) n = Math.floor(x * 10) / 10;
  }
  return String(n);
}
const sx = (v, need) => (v == null ? '—' : `${safetyNum(v, need)}x`);
// a part whose strength check ran on a filled-in solid has no "holds" anywhere (CALI-96)
// why: a filled-in shape, or a shape that couldn't be checked against its pieces at all (it fails closed)
const notTrusted = (why) => (String(why || '').startsWith("couldn't") ? "not trusted: its shape couldn't be checked"
  : 'not trusted: a solid with more in it than its pieces');
const untrustedBadge = (p) => `<span class="badge bad">${notTrusted(p.untrusted)}</span>`;
const partOf = (pid) => (S.design && S.design.parts.find((x) => x.id === pid)) || {};
// CALI-97: a ✓ on an FEA too coarse to see its walls is no ✓. The server marks such a case (c.unresolved:
// 'unresolved' when a finer run can see them, 'unchecked' when none a study may make can); its badge says so, and
// no green "holds" sits under the card's warn. A ✗ stays a ✗.
const coarseWord = (c) => (c.unresolved === 'unchecked' ? 'not checked' : 'not resolved');
// CALI-112: one verdict, the server's (verdicts.py), on every run, case and history line. The page never works one
// out: its badge, word and colour are the verdict's, so a new kind can't be missed here.
const verdictTone = (v) => (v && v.status === 'ok' ? 'ok' : v && v.status === 'bad' ? 'bad' : 'warn');
const verdictBadge = (v) => `<span class="badge ${verdictTone(v)}">${esc(v ? v.word : 'not checked yet')}</span>`;
// a verdict with a number a person may build on: it holds, or it fails
// close: a pass near its limit (CALI-88), still a number to build on
const settled = (v) => !!v && (v.kind === 'holds' || v.kind === 'close' || v.kind === 'fails');
const caseBadge = (c) => verdictBadge(c.verdict);
// a carve or lightening step, or a thickness the plate check tried: the server's verdict says if it holds (#132 review)
const holdsHere = (x) => !!(x && x.verdict && x.verdict.counts_as_pass);
const runBadge = (run) => verdictBadge(run.verdict);
const runWord = (run) => (run.verdict ? run.verdict.word : 'not checked yet');
// which grain the Beam check used (CALI-126): the one the person said, or the weaker way; never a hard-coded "unknown"
// the cut's own words are in the check's why once ("With its face grain running …, as you said"): said once (#151)
function beamGrain(pl) {
  return pl.grain ? 'with the grain as you said' : 'the grain unknown: the weaker way';
}
// keep the advice: the grain the person keeps is the only one that moves the verdict, and it goes on the cut list
function grainKeep(p, pl, need) {
  const said = (p.grain || {})[pl.piece];
  if (said) return pl.grain === said.grain ? '' : ` · <span class="muted">you said: ${esc(said.line || '')} Check it holds again to use it.</span>`;
  if (!(pl.safety > pl.safety_across)) return '';
  return ` <button class="ghost" data-grain="${esc(pl.piece)}">Keep: cut it with its ${esc(pl.advice_phrase || 'face grain running from one support to the other')} (${sx(pl.safety, need)})</button>`;
}
function loadCase(p, run, c, i) {
  const on = S.station && S.station.run === run.id && S.station.index === i;
  const pl = c.plate, f = c.fea || {};
  const holds = p.untrusted ? untrustedBadge(p) : caseBadge(c);     // a filled-in shape wins (CALI-96, then 97)
  // the plate or beam check's number its verdict rests on (the worse grain's), in the verdict's colour and, where it
  // isn't settled, its word: never green on a not-trusted, unresolved or older case (#122, #132)
  const plNum = (n) => `<b style="color:var(--${verdictTone(pl.verdict)})">${sx(n, run.min_safety)}${pl.verdict && !settled(pl.verdict) ? ` (${esc(pl.verdict.word)})` : ''}</b>`;
  const plate = !pl ? '' : !pl.done
    ? `<div class="muted small" style="margin-top:4px">No plate check for ${esc(pl.piece)}: ${esc(pl.why)}.</div>`
    : pl.as === 'beam'      // a top on two sides: a beam, not a plate held all round (CALI-116)
      ? `<div class="small" style="margin-top:4px"><b>Beam check</b> — ${esc(pl.piece)}: ${esc(pl.why)} ·
        ${plNum(pl.safety_across)} ${beamGrain(pl)} · sags ${len(pl.deflection_mm, 3)}${grainKeep(p, pl, run.min_safety)}</div>`
    : pl.support === 'ring'  // a disc on a ring (#137 item 7)
      ? `<div class="small" style="margin-top:4px"><b>Plate check</b> — ${esc(pl.piece)}, a round plate held at its ring's outer edge (${len(pl.ring_mm)} across),
        edges free to turn: ${fixed(pl.stress_mpa, 1)} MPa → ${plNum(pl.safety_across)} across the grain, ${sx(pl.safety, run.min_safety)} along it
        · sags ${len(pl.deflection_mm, 3)} <span class="muted">(Roark; needs an engineer's check)</span></div>`
      : `<div class="small" style="margin-top:4px"><b>Plate check</b> — ${esc(pl.piece)}, ${len(pl.a_mm)} × ${len(pl.b_mm)} held all round,
        edges free to turn: ${fixed(pl.stress_mpa, 1)} MPa → <b>${sx(pl.safety, run.min_safety)}</b> with its face grain across the ${len(pl.b_mm)} span,
        ${plNum(pl.safety_across)} the other way · sags ${len(pl.deflection_mm, 3)}</div>`;
  const fea = f.supported === false ? `<div class="small" style="color:var(--bad)">${esc(c.why)}</div>`
    : `<div class="small" style="margin-top:4px"><b>whittle FEA</b> — works hardest ${esc(peakWhere(f))}
        (${fixed(f.peak_mpa, 1)} MPa${c.verdict && c.verdict.kind === 'span' ? '' : ` → ${sx(f.safety, run.min_safety)}`}) · gives ${len(f.deflection_mm, 3)}</div>`;
  const by = pl && pl.done && pl.by_thickness ? (() => {
    const ok = pl.by_thickness.filter(holdsHere);
    const thin = ok.length ? ok[0] : null;
    return `<details class="small" style="margin-top:4px"><summary>Other thicknesses (plate check)${thin
      ? ` — the thinnest the plate check passes: <b>${esc(thin.label)}</b>` : ''}</summary>
      <table class="st"><tr><th style="text-align:left">${esc((run.plate_material || run.material).name)}</th><th>grain wrong way</th><th>grain right</th><th>sags</th><th></th></tr>
      ${pl.by_thickness.map((b) => { const now = Math.abs(b.thickness_mm - pl.thickness_mm) < 0.01;
        const nowLabel = (pl.by_thickness.find((x) => Math.abs(x.thickness_mm - pl.thickness_mm) < 0.01) || {}).label;
        return `<tr${now ? ' class="on"' : ''}>
        <td style="text-align:left">${esc(b.label)}</td>
        <td style="color:var(--${verdictTone(b.verdict)})">${sx(b.safety_across, run.min_safety)}</td>
        <td>${sx(b.safety, run.min_safety)}</td><td>${len(b.deflection_mm, 3)}</td>
        <td>${now ? '<span class="muted">now</span>' : holdsHere(b)
          ? sheetUse(run, b.label, b.thickness_mm, nowLabel, pl.piece,
            { text: `Ask for ${b.label} sheet (redesigns it; checked again after)`, off: askWait(pickedStep(p)) }) : ''}</td></tr>`; }).join('')}</table>
      ${offWhy(pl.by_thickness.some((b) => holdsHere(b) && Math.abs(b.thickness_mm - pl.thickness_mm) >= 0.01) ? askWait(pickedStep(p)) : '')}</details>`;
  })() : '';
  return `<div class="card loadcase ${on ? 'on' : ''}" style="margin-top:8px">
      <div><b>${esc(c.name)}</b> <span class="muted small">${lbs(c.lb)} × ${c.factor}</span> ${holds}</div>
      ${c.blind ? `<div class="small" style="margin-top:2px">${c.rests ? `Not resolved: ${esc(c.rests.said)}.` : 'The check couldn\'t see any stress here: the piece under the load may be too thin for its voxels, the load\'s patch may be smaller than the voxels, or the load may go straight into what holds it.'}</div>`
      : c.unresolved && c.verdict && c.verdict.kind !== 'fails' && (c.verdict.why || (c.governs && c.governs !== 'fea'))
        ? `<div class="small" style="margin-top:2px">${caseWhy(c, run, false)} <span class="muted">(it needs ${run.min_safety}x)</span></div>`
      : c.unresolved ? `<div class="small" style="margin-top:2px">The FEA read ${sx(c.safety, run.min_safety)}
        <span class="muted">at voxels of ${wallLen(run.spacing_mm)}, too coarse to see its ${wallLen(run.thinnest_mm)} walls:
        ${c.verdict && c.verdict.kind === 'fails' ? 'the fail may be the model\'s' : 'no verdict'} (it needs ${run.min_safety}x)</span></div>`
      : c.verdict && c.verdict.kind === 'span' ? `<div class="small" style="margin-top:2px"><b>Not settled:</b> ${esc(c.verdict.why)}.
        <span class="muted">It needs ${run.min_safety}x.</span></div>`
      : `<div class="small" style="margin-top:2px">Safety <b>${sx(c.safety, run.min_safety)}</b>
        <span class="muted">(by ${c.governs === 'joint' ? `the joint between ${esc(c.joints.governing.between)}: ${esc(c.joints.governing.said)}` : c.governs === 'buckling' ? foldedBy(c) : c.governs === 'plate' ? (pl && pl.grain ? `the plate check, ${beamGrain(pl)}` : 'the plate check, with the grain the wrong way') : 'the FEA'}; it needs ${run.min_safety}x)</span>
        ${c.breaks_lb ? ` · breaks at about <b>${Number(c.breaks_lb).toLocaleString()} lb</b> there` : ''}</div>`}
      ${jointsLine(c, run)}
      ${jointsTable(c, run)}
      ${plate}${fea}${by}
      ${c.heat ? `<div class="actions"><button data-heat="${i}" class="${on ? 'primary' : ''}">${on ? 'Showing the stress' : 'Show the stress'}</button></div>` : ''}
    </div>`;
}

// the hand buckling check that governs a case (CALI-159, #229): which wall, and what it was taken as
// a pass that rests on a wall held square by a joint nothing checks: amber at most, and why, as answers.joint_said says it (#265)
// each joint of a case by hand (#301): the one that governs first, then the rest, with what it carries and what it takes
function jointsTable(c, run) {
  const J = c.joints;
  if (!J || !(J.rows || []).length) return '';
  const g = J.governing;
  const rows = [...J.rows].sort((a, b) => (a.safety == null) - (b.safety == null) || (a.safety || 0) - (b.safety || 0));
  const lb = (o) => Object.entries(o || {}).map(([m, v]) => `${Math.round(v)} lb`).join(', ');
  const fea = J.fea && !J.fea.unread;                // the FEA's side beside the hand rule's (#316 slice 2)
  return `<details class="small" style="margin-top:4px"><summary>Joints, by hand${fea ? ' and from the FEA' : ''}${g ? ` — the weakest: <b>${esc(g.between)}</b>,
      ${sx(g.safety, run.min_safety)}` : ''}</summary>
    <table class="st"><tr><th style="text-align:left">joint</th><th style="text-align:left">how it gives</th><th>carries</th><th>takes</th><th></th></tr>
    ${rows.map((r) => `<tr><td style="text-align:left">${esc(r.between)}</td><td style="text-align:left">${esc(r.said)}${
      r.disagree ? ` <span style="color:var(--amber)">(${esc(r.disagree)})</span>` : ''}${
      r.fix ? `<div class="muted">${esc(r.fix)}</div>` : ''}</td>
      <td>${lb(r.demand_lb)}</td><td>${lb(r.capacity_lb)}</td>
      <td style="color:var(--${r.safety == null ? 'muted' : verdictTone(r.verdict)})">${r.safety == null ? '—' : sx(r.safety, run.min_safety)}</td></tr>`).join('')}</table>
    ${(J.unchecked || []).length ? `<div class="muted">Not checked: ${J.unchecked.map(esc).join('; ')}.</div>` : ''}
    ${J.fea && J.fea.unread ? `<div class="muted">The FEA's side isn't read here: ${esc(J.fea.unread)}.</div>` : ''}
    <div class="muted">Mean breaking loads, by hand, against what the wood needs (${run.min_safety}x): screws by the thread in the edge
      (APA E830), glue to an edge none, bearing at 360 psi: Theo's values (#301). How a long joint's load is shared is interim (#316).
      ${fea ? 'Beside it, each joint\'s force and moment from the FEA, which holds the pieces as one: the lower number governs.' : ''}</div></details>`;
}
function jointsLine(c, run) {
  const b = c.verdict && c.verdict.joints ? c.verdict.brace : null;
  if (!b) return '';
  const said = [];
  if (b.trim) {                                     // a sheet part's glued trim, left out of the check (#272)
    const many = b.trim.length > 1 || /s\s*$/.test(b.trim[0]);
    said.push(`<b>Not checked:</b> the ${esc(b.trim.join(' and the '))} ${many ? 'are' : 'is'}
      glued trim, left out of the check.`);
  }
  if (b.unchained) {                                // a path the hand check couldn't follow: why, once (#311 review)
    said.push(`<b>Joints not checked by hand:</b> ${esc(b.unchained)}.`);
  } else if (b.names && b.names.length) {           // the hand check couldn't place these: named (#301)
    said.push(`<b>Joints not checked by hand:</b> ${b.names.map(esc).join('; ')}.`);
  } else if (b.wood || (b.joints_n != null && !b.piece)) { // a part's joints taken as solid wood, counted or not (#222, #275)
    const n = b.joints_n;
    said.push(`<b>Joints not checked:</b> the check takes its ${n != null ? `${n} joint${n === 1 ? '' : 's'}` : 'joints'} as solid wood.`);
  }
  if (said.length) {
    return said.map((t) => `<div class="small" style="margin-top:2px">${t}</div>`).join('');
  }
  return `<div class="small" style="margin-top:2px"><b>Joints not checked:</b> the ${esc(b.piece)} is held square at its top by its
    joint to the ${esc(b.braced_by)}, which isn't checked${b.sway_safety != null ? `; if that joint gives, it racks (leans over with
    the walls beside it) and folds at ${safetyNum(b.sway_safety, run.min_safety)}x` : ''}.</div>`;
}

function foldedBy(c) {
  const done = (c.buckling || []).filter((r) => r.done);
  const w = done.length ? done.reduce((a, b) => (b.safety < a.safety ? b : a)) : null;
  if (!w) return 'the buckling check';
  const sides = w.edges_held === 2 ? 'held along both sides' : w.edges_held === 1 ? 'held along one side'
    : `free along its sides, ${w.braced_by ? `its top held square by its joint to the ${esc(w.braced_by)}, which isn't checked`
      + (w.sway_safety != null ? ` (it racks and folds at ${safetyNum(w.sway_safety)}x if that joint gives)` : '') : 'its top free to sway'}`;   // (#264, #265)
  const share = w.share != null && w.share !== 1 ? `${Math.round(w.share * 100)}% of the load on it, by the lever rule` : 'its whole load on it';
  if (w.down === false) return `the buckling check on the ${esc(w.piece)}: a push that doesn't run down it, taken as a squeeze, the safe side for the sheet; racking (the frame leaning over at its joints) isn't checked: the FEA takes the joints as solid`;   // (#235, #250 review)
  return `the buckling check on the ${esc(w.piece)}: a plate ${sides}, ${share}`;
}

function loadResults(p, run, runs) {
  const stale = run.version !== p.version;
  return `<div class="small" style="margin-top:12px">${runs.length > 1 ? `<select id="lRun">${runs.map((r, k) =>
      `<option value="${k}" ${r.id === run.id ? 'selected' : ''}>${esc(new Date(r.created * 1000).toLocaleString())} · v${r.version}
        · ${runWord(r)}</option>`).join('')}</select>`       // each run's own verdict: a fail stays a fail (#89)
      : `<b>Last check</b> · v${run.version} · ${new Date(run.created * 1000).toLocaleString()}`}
      ${p.untrusted ? untrustedBadge(p) : runBadge(run)}
      ${stale ? '<span class="badge bad">the part has changed since</span>' : ''}</div>
    ${runReason(run)}
    ${run.cases.map((c, i) => loadCase(p, run, c, i)).join('')}
    <div class="muted small" style="margin-top:6px">In ${esc(run.headline || run.material.name)}, voxels of ${len(run.spacing_mm, 1)}
      (${run.voxels.toLocaleString()} of them), held at ${run.held.map((h) => esc(h.name)).join(', ')} · ${run.seconds}s</div>
    ${run.notes.map((n) => `<div class="muted small" style="margin-top:4px">• ${esc(n)}</div>`).join('')}`;
}

function wireLoad(p) {
  const ask = $('lAsk');
  if (ask) ask.onclick = () => { $('msg').value = 'It has to hold '; $('msg').focus(); };
  const go = $('lGo');
  if (go) go.onclick = () => runLoad(p);
  wireScenarios(p);                                // its scenarios and supports, as data (#296)
  const finer = $('lFiner');                       // a run too coarse to see its walls: again, finer (CALI-97)
  if (finer) finer.onclick = () => runLoad(p, loadRuns(p.id)[0].finer.spacing_mm);
  const sel = $('lRun');
  if (sel) sel.onchange = () => { S.loadRun[p.id] = +sel.value; clearStation(); renderInspector(); };
  const lg = $('lightGo');
  if (lg) lg.onclick = (e) => runLighten(p, e.target.dataset.again === '1');   // only "Lighten it again" says so
  wireCarve(p);
  document.querySelectorAll('#loadBox tr[data-lst]').forEach((tr) => {
    tr.onclick = () => showStation(p.id, lightenRuns(p.id)[0], +tr.dataset.lst);
  });
  document.querySelectorAll('#loadBox [data-step-adopt]').forEach((b) => {   // a picked step, by its table (#297)
    b.onclick = () => adoptStation(p.id, lightenRuns(p.id)[0].id, +b.dataset.stepAdopt, 'lighten');
  });
  document.querySelectorAll('#loadBox [data-use-param]').forEach((b) => {   // a thinner sheet: its number set (#295)
    b.onclick = () => useParam(p, b.dataset.useParam, Number(b.dataset.useMm));
  });
  document.querySelectorAll('#loadBox [data-use-t]').forEach((b) => {
    b.onclick = () => send(b.dataset.useT, p.id);
  });
  document.querySelectorAll('#loadBox [data-grain]').forEach((b) => {   // the person keeps the grain (CALI-126)
    b.onclick = async () => {
      b.disabled = true;
      try {
        const got = await api('POST', `/api/designs/${S.slug}/parts/${p.id}/grain`, { piece: b.dataset.grain, grain: 'along' });
        S.design = got.design; renderInspector();
      } catch (e) { b.disabled = false; showErr(plainly(e.message)); }
    };
  });
  document.querySelectorAll('#loadBox [data-heat]').forEach((b) => {
    b.onclick = () => {
      const runs = loadRuns(p.id), run = runs[Math.min(S.loadRun[p.id] || 0, runs.length - 1)];
      showHeat(p.id, run, +b.dataset.heat);
    };
  });
}

async function runLighten(p, again) {
  const key = `lighten:${S.slug}/${p.id}`;         // by design and part (#175)
  if (S.running[key]) return;                      // already asked: a second click does nothing
  S.running[key] = true;
  try { await startLighten(p, again); } finally { delete S.running[key]; }
}
async function startLighten(p, again) {
  const prog = $('lightProgress'), go = $('lightGo'), slug = S.slug;
  go.disabled = true;
  prog.innerHTML = '<div class="bar"><i></i></div><div class="small muted" id="lightMsg">starting…</div>';
  try {
    const runs = loadRuns(p.id);
    const { job_id } = await api('POST', `/api/designs/${S.slug}/lighten`, { part: p.id, min_safety: runs[0] ? runs[0].min_safety : 2, again: !!again });
    await trackJob(job_id, { kind: 'lighten', part: p.id, version: p.version, text: 'starting…' }).done;
    if (S.slug !== slug) return;                  // finished with another design open: that design's view stays
    clearStation();
    await refresh();
    const run = lightenRuns(p.id)[0];
    if (run && run.offer) showStation(p.id, run, run.offer.index);        // the step the card offers (#167)
  } catch (e) {
    if (S.slug !== slug) return;
    await refresh().catch(() => {});              // a 409: the card as it now is, and the reason beside it
    const said = $('lightProgress');
    if (said) said.innerHTML = jobEnded(e);
    if ($('lightGo') && !trackedFor('lighten', p.id)) $('lightGo').disabled = false;
  }
}

// ------------------------------------------------------------- what's running for this design (#178)
// The design's record says what's running, as `carving` does for a carve. Drawn from that on load and on every redraw:
// a study isn't lost to a switch of design, a reload, or another job finishing.
const JOB_NAME = { load: 'Strength check', lighten: 'Lighten', release: 'Build package' };
const JOB_BOX = { load: 'lProgress', lighten: 'lightProgress', release: 'relProgress' };
const JOB_GO = { load: 'lGo', lighten: 'lightGo', release: 'relGo' };
const jobsHere = () => Object.values(S.tracked).filter((t) => t.slug === S.slug);
const trackedFor = (kind, part) => jobsHere().find((t) => t.kind === kind && (t.part || null) === (part || null));
function trackJob(id, info) {
  if (S.tracked[id]) return S.tracked[id];
  const t = S.tracked[id] = { job: id, slug: S.slug, text: '', progress: null, waiting: false, t0: Date.now(),
    stoppable: STOPS.has(info.kind), ...info };
  paintJobs();
  t.done = follow(id, (ev) => {
    if (ev.kind === 'stopping') t.stopping = true;
    if (ev.text && ev.kind !== 'started') t.text = ev.text;
    if (typeof ev.progress === 'number') t.progress = ev.progress;
    t.waiting = ev.kind === 'waiting';
    paintJobs();
  }).finally(() => jobOver(id));
  return t;
}
// a job's gone, however it went: finished, cancelled, dead, or the server restarted. The page re-reads on its own; if the server
// isn't back yet it tries again, and paintJobs has already given the buttons back
function jobOver(id) {
  const t = S.tracked[id];
  if (!t) return;
  delete S.tracked[id];
  if (S.design && t.slug === S.slug) S.design.running = (S.design.running || []).filter((r) => r.job !== id);
  paintJobs();
  rereadWhenBack(t.slug, 20);
}
function rereadWhenBack(slug, tries) {
  if (S.slug !== slug) return;
  refresh().catch(() => { if (tries > 1) setTimeout(() => rereadWhenBack(slug, tries - 1), 3000); });
}
// ask the record: another tab's job appears, and one the server no longer has can't hold the page.
// Gone twice running before it's dropped: a job's last event can still be on its way
async function pollRunning() {
  if (!S.slug || !S.design || document.hidden) return;         // nothing followed yet still looks: another tab's job shows here
  const slug = S.slug;
  let got;
  try { got = await api('GET', `/api/designs/${slug}/running`); } catch (e) { return; }     // following it says when it's gone
  if (S.slug !== slug || !S.design) return;
  S.design.running = got.running;
  syncRunning();
  const build = got.running.find((r) => r.kind === 'firstrun');   // started from another tab
  if (build && S.following !== build.job) { followBuild(build.job, build.elapsed_s); refresh().catch(() => {}); }   // its cards too
  else if (build) buildRanFor(build.elapsed_s);               // keep to the server's time
  for (const t of jobsHere()) {
    if (got.running.some((r) => r.job === t.job)) t.gone = 0;
    else if ((t.gone = (t.gone || 0) + 1) > 1) jobOver(t.job);
  }
}
// what's on the record and this page isn't following yet: after a reload, or coming back to the design
function syncRunning() {
  for (const r of (S.design && S.design.running) || []) {
    if (r.kind === 'firstrun' || S.tracked[r.job]) continue;     // the first build has its own bubble in the thread
    trackJob(r.job, { kind: r.kind, part: r.part, version: r.version, text: r.text, waiting: r.waiting, stopping: !!r.stopping,
      t0: Date.now() - (r.elapsed_s || 0) * 1000 }).done.catch(() => {});   // jobOver re-reads; its clock from when it began
  }
}
function jobPart(id) { return (((S.design && S.design.parts) || []).find((p) => p.id === id) || {}).name || id; }
// what a job turned off, and only that, it turns back on: what was off for its own reasons stays off
// a job's button while it runs: off, and its words say so where it has some ("Lightening…"), in the tab that started it
// too (#331 review: "Lighten it" stayed, disabled, through 16 s of steps); jobOn gives both back
function jobOff(b, label) {
  if (!b.disabled) b.dataset.jobOff = '1';
  b.disabled = true;
  b.title = 'It\'s running now';
  if (label && b.dataset.jobLabel == null && b.dataset.jobOff) { b.dataset.jobLabel = b.textContent; b.textContent = label; }
}
function jobOn(b) {
  b.disabled = false;
  b.title = '';
  delete b.dataset.jobOff;
  if (b.dataset.jobLabel != null) { b.textContent = b.dataset.jobLabel; delete b.dataset.jobLabel; }
}
function runningLabel(kind) {
  return ({ load: 'Checking…', lighten: 'Lightening…', carve: 'Carving…', fix: 'Fixing…' })[kind] || '';
}
function jobHtml(t, named) {
  const pct = typeof t.progress === 'number' ? Math.round(t.progress * 100) : null;
  return `<div class="job-line">${pct != null ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ''}
    <div class="small muted">${named ? `${esc(JOB_NAME[t.kind])}${t.part ? ` of ${esc(jobPart(t.part))}` : ''}: ` : ''}${esc(t.text || 'running…')}
    ${t.waiting ? `<button class="ghost wait-cancel" data-job-cancel="${esc(t.job)}">Cancel</button>` : ''}</div>${changedUnder(t)}</div>`;
}
// a run whose part changed while it ran: said as soon as the change lands, not when it finishes (#268: Theo's v3 Lighten
// finished on v4 and he couldn't find it)
function changedUnder(t) {
  const now = t.part && S.design ? ((S.design.parts || []).find((p) => p.id === t.part) || {}).version : null;
  if (t.version == null || now == null || now === t.version || !['lighten', 'load'].includes(t.kind)) return '';
  return `<div class="small" style="color:var(--amber)">You've changed ${esc(jobPart(t.part))} since this started (it was
    v${t.version}, it's v${now} now): ${t.kind === 'lighten' ? 'its steps will be of' : 'what it finds will be'} v${t.version}.
    It's kept, under ${t.kind === 'lighten' ? 'Make it lighter' : 'its strength check'}.</div>`;
}
function paintJobs() {
  const note = $('jobNote');
  if (!note) return;
  const lines = [];
  document.querySelectorAll('#inspector [data-job-off]').forEach(jobOn);
  for (const t of jobsHere()) {
    const here = t.kind === 'release' || shownPart() === t.part, panel = here ? $(JOB_BOX[t.kind]) : null;
    const box = panel && panel.closest && panel.closest('details:not([open]), [hidden]') ? null : panel;   // folded away isn't on screen
    // its panel's own line, where it has one (hidden while the overlay greys that panel); the line at the top only for the
    // build package: every part's job is the overlay's now (#363), and the kinds the panels never had stay off them
    if (box) { box.innerHTML = jobHtml(t, false); box.dataset.job = t.job; } else if (t.kind === 'release') lines.push(jobHtml(t, true));
    const go = here && $(JOB_GO[t.kind]);
    if (go) jobOff(go, runningLabel(t.kind));
    if (t.kind === 'load' && here && $('lFiner')) jobOff($('lFiner'));
    document.querySelectorAll(`#inspector [data-better-action="${t.kind}"][data-better-part="${t.part}"]`).forEach(jobOff);
  }
  note.innerHTML = lines.join('');
  for (const box of document.querySelectorAll('#inspector [data-job]')) {     // it's over: nothing left over from it
    if (!S.tracked[box.dataset.job]) { box.innerHTML = ''; delete box.dataset.job; }
  }
  paintBusy();
}

// ------------------------------------------------------------- a running job, plain to see (#363)
// Theo, after Fix these on step-stool-5: "the indicator is really pretty small and hard to see ... making the main part
// screen grey and not working with some circle/timer indicator in the upper right corner ... some text below it to say
// what it's currently doing". One overlay for every job, drawn from what the page follows (S.tracked): top right of the
// view, a large spinner, how long it's run, what's running on which part, its step in words and its bar where it knows
// its count; the view greys, and the part's panel greys over and can't be acted on. The chat and other designs stay usable.
const STOPS = new Set(['load', 'lighten', 'carve', 'fix', 'release', 'preview']);   // stop at their next step (design_api.STOPPABLE)
const BUSY_DOING = { load: 'Checking', lighten: 'Lightening', carve: 'Carving', fix: 'Fixing', cutplan: 'Making the cut plan for',
  aero: 'Shaping {} for drag', chat: 'Working on', whittle: 'Whittling', frame: 'Sizing the frame of', gussets: 'Adding gussets to',
  picture: 'Drawing', preview: 'Previewing a step of', release: 'Making the build package', clarify: 'Thinking about your design',
  goals: 'Working out its goals', scorecard: 'Scoring the design' };
function busyJobs(jobs, scope) {               // the one shown big, and the rest: the part on screen's first, then the oldest
  const shown = jobs.filter((t) => t.kind !== 'firstrun');    // the first build has its own bubble in the thread
  const mine = shown.filter((t) => scope && t.part === scope);
  const order = [...mine, ...shown.filter((t) => !mine.includes(t))];
  return { main: order[0] || null, more: order.slice(1) };
}
function busyTitle(t, name) {
  const doing = BUSY_DOING[t.kind] || 'Working on';
  if (!t.part) return t.kind === 'chat' ? 'Working on your message' : doing.replace(' {}', '').replace(/ (of|for|to)$/, '');
  return doing.includes('{}') ? doing.replace('{}', name) : `${doing} ${name}`;
}
function clock(s) {                            // 0:07, 12:30, 1:02:05
  const n = Math.max(0, Math.floor(s)), h = Math.floor(n / 3600), m = Math.floor(n / 60) % 60, sec = String(n % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
}
function busyStep(t) {
  return t.stopping ? 'stopping at the next step…' : t.text || (t.waiting ? 'waiting for another job on this design' : 'starting…');
}
function busyHtml(main, more, now, name) {
  const pct = typeof main.progress === 'number' ? Math.round(main.progress * 100) : null;
  const stop = main.stopping ? '' : main.waiting ? 'Cancel' : main.stoppable ? 'Stop it' : '';
  return `<div class="busy-spin" aria-hidden="true"></div>
    <div class="busy-time" data-t0="${main.t0}" title="how long it's run">${clock((now - main.t0) / 1000)}</div>
    <div class="busy-what">${esc(busyTitle(main, name(main.part)))}…</div>
    <div class="busy-step">${esc(busyStep(main))}</div>
    ${pct != null ? `<div class="bar busy-bar" role="progressbar" aria-label="How far it's got" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>` : ''}
    ${stop ? `<button class="ghost busy-stop" data-job-cancel="${esc(main.job)}">${stop}</button>` : ''}
    ${more.map((t) => `<div class="busy-more">and ${esc(busyTitle(t, name(t.part)).replace(/^./, (c) => c.toLowerCase()))}: ${esc(busyStep(t))}</div>`).join('')}
    <div class="busy-note">${main.part ? `${esc(name(main.part))} waits till it's done. ` : ''}The chat and your other designs still work.</div>`;
}
function paintBusy() {
  const box = $('busy');
  if (!box) return;
  const here = S.design ? jobsHere() : [], { main, more } = busyJobs(here, S.scope), insp = $('inspector');
  // its panel greys when the part on screen is the one being worked on (a design-wide job leaves the design view be)
  const grey = !!main && !!S.scope && here.some((t) => t.kind !== 'firstrun' && t.part === S.scope);
  insp.classList.toggle('is-busy', grey);   // not .busy: that's the overlay's box
  insp.inert = grey;
  if (grey) insp.setAttribute('aria-busy', 'true'); else insp.removeAttribute('aria-busy');
  $('busyShade').hidden = box.hidden = !main;
  // drawn once per shape, then its words and bar changed in place: a box redrawn on every event replaced Stop it under the
  // pointer, so a press and its release landed on two buttons and the click was lost (found on the walk)
  const shape = main ? [main.job, !!main.stopping, !!main.waiting, !!main.stoppable, typeof main.progress === 'number',
    more.map((t) => t.job).join()].join('|') : '';
  const html = main ? busyHtml(main, more, Date.now(), jobPart) : '';
  if (box.dataset.shape !== shape) { box.innerHTML = html; box.dataset.shape = shape; }
  else if (main) busyUpdate(box, html);
  const said = main ? `${busyTitle(main, jobPart(main.part))}: ${busyStep(main)}` : '';
  if ($('busyLive').textContent !== said) $('busyLive').textContent = said;   // said when it changes, not every tick
}
function busyUpdate(box, html) {               // the same box, its words and bar as they are now
  const fresh = document.createElement('div');
  fresh.innerHTML = html;
  for (const sel of ['.busy-what', '.busy-step', '.busy-note']) box.querySelector(sel).textContent = fresh.querySelector(sel).textContent;
  box.querySelectorAll('.busy-more').forEach((m, i) => { m.textContent = fresh.querySelectorAll('.busy-more')[i].textContent; });
  const bar = box.querySelector('.busy-bar'), now = fresh.querySelector('.busy-bar');
  if (bar && now) { bar.setAttribute('aria-valuenow', now.getAttribute('aria-valuenow')); bar.firstElementChild.style.width = now.firstElementChild.style.width; }
}
setInterval(() => {                            // the clock moves while nothing else does
  const t = document.querySelector('#busy .busy-time');
  if (t) t.textContent = clock((Date.now() - Number(t.dataset.t0)) / 1000);
}, 1000);
function cancelJob(e) {
  const b = e.target.closest('[data-job-cancel]');
  if (!b) return;
  b.disabled = true;
  api('POST', `/api/jobs/${b.dataset.jobCancel}/cancel`).catch((err) => showErr(err.message));
}
// a phone (#164): one pane at a time. The desktop's three columns don't read any of this
function setPane(pane) {
  document.body.dataset.pane = pane;
  document.body.classList.remove('tree-open');
  document.querySelectorAll('#paneTabs [data-pane]').forEach((b) => b.classList.toggle('on', b.dataset.pane === pane));
}
$('paneTabs').onclick = (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.id === 'treeTab') document.body.classList.toggle('tree-open');
  else setPane(b.dataset.pane);
};
setPane('chat');
$('inspector').addEventListener('click', cancelJob);
$('busy').addEventListener('click', cancelJob);         // the overlay's Stop it / Cancel (#363)
$('inspector').addEventListener('toggle', paintJobs, true);    // folded or unfolded mid-wait: toggle doesn't bubble, so captured
setInterval(pollRunning, 5000);
async function runLoad(p, spacing) {
  const key = `load:${S.slug}/${p.id}`;            // by design and part: part ids repeat across designs (#175)
  if (S.running[key]) return;                      // already asked: the card's button and the panel's are two ways in
  S.running[key] = true;
  try { await startLoad(p, spacing); } finally { delete S.running[key]; }
}
async function startLoad(p, spacing) {
  const prog = $('lProgress'), go = $('lGo'), slug = S.slug;
  go.disabled = true;
  if ($('lFiner')) $('lFiner').disabled = true;
  prog.innerHTML = '<div class="bar"><i></i></div><div class="small muted" id="lMsg">starting…</div>';
  try {
    const { job_id } = await api('POST', `/api/designs/${S.slug}/load-study`,
      { part: p.id, min_safety: +$('lSafety').value || 2, ...(spacing ? { spacing_mm: spacing } : {}) });
    await trackJob(job_id, { kind: 'load', part: p.id, version: p.version, text: 'starting…' }).done;
    if (S.slug !== slug) return;          // finished with another design open: its stress picture isn't this design's, whatever the part's called
    S.loadRun[p.id] = 0;
    S.trial = null;                       // the test is set beside the check that just ran, not the one before (#89)
    clearStation();
    await refresh();
    const run = loadRuns(p.id)[0];
    if (run) {
      const worst = run.cases.reduce((a, c, i) => (c.heat && (a < 0 || (c.safety ?? 1e9) < (run.cases[a].safety ?? 1e9)) ? i : a), -1);
      if (worst >= 0) showHeat(p.id, run, worst);
    }
  } catch (e) {
    if (S.slug !== slug) return;
    await refresh().catch(() => {});      // a 409 from a stale tab: the card as it now is, and it follows the job that's running
    const said = $('lProgress');
    if (said) said.innerHTML = jobEnded(e);
    if ($('lGo') && !trackedFor('load', p.id)) $('lGo').disabled = false;
  }
}

// stress, low to high: blue, cyan, green, yellow, red — bright, so a part that's barely working reads as blue,
// not as fog
const HEAT = [[0, 0x4a7fe0], [0.25, 0x35c4dc], [0.5, 0x5fd35f], [0.75, 0xf2c94c], [1, 0xe5383b]];
function heatColor(t, out) {
  t = Math.max(0, Math.min(1, t));
  let k = 1;
  while (k < HEAT.length - 1 && HEAT[k][0] < t) k++;
  const [t0, c0] = HEAT[k - 1], [t1, c1] = HEAT[k];
  return out.setHex(c0).lerp(new THREE.Color(c1), (t - t0) / ((t1 - t0) || 1));
}
const b64 = (s, T) => { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); };

async function showHeat(pid, run, index) {
  try {
    const c = run.cases[index];
    const h = await api('GET', `/api/designs/${S.slug}/load-study/${run.id}/cases/${index}.json`);
    const pos = b64(h.positions, Float32Array), idx = b64(h.index, Uint32Array), heat = b64(h.heat, Float32Array);
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geom.setIndex(new THREE.BufferAttribute(idx, 1));
    const col = new Float32Array(heat.length * 3), tmp = new THREE.Color(), top = h.max || 1;
    for (let i = 0; i < heat.length; i++) { heatColor(heat[i] / top, tmp); col[3 * i] = tmp.r; col[3 * i + 1] = tmp.g; col[3 * i + 2] = tmp.b; }
    geom.setAttribute('color', new THREE.BufferAttribute(col, 3));
    geom.computeVertexNormals();
    clearStation(true);
    stationMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.7, metalness: 0 }));
    // where it's pushed: the load's box, and an arrow in the direction it pushes
    const lo = new THREE.Vector3(...c.lo), hi = new THREE.Vector3(...c.hi);
    const size = hi.clone().sub(lo), mid = lo.clone().add(hi).multiplyScalar(0.5);
    const reach = Math.max(size.x, size.y, size.z, 40);
    const pad = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(size.x, 2), Math.max(size.y, 2), Math.max(size.z, 2))),
      new THREE.LineBasicMaterial({ color: 0xffffff }));
    pad.position.copy(mid);
    stationMesh.add(pad);
    const dir = new THREE.Vector3(...c.force_n).normalize();
    const len3 = reach * 1.6;
    stationMesh.add(new THREE.ArrowHelper(dir, mid.clone().sub(dir.clone().multiplyScalar(len3)), len3, 0xffffff, len3 * 0.3, len3 * 0.15));
    scene.add(stationMesh);
    S.station = { part: pid, run: run.id, index, kind: 'load' };
    const grad = HEAT.map(([t, hex]) => `#${hex.toString(16).padStart(6, '0')} ${t * 100}%`).join(', ');
    // two numbers are on screen: the picture is the FEA's, the verdict may be the plate check's — say which is which
    const pl = c.plate && c.plate.done ? c.plate : null, f = c.fea || {};
    const decided = c.governs === 'joint' && c.joints && c.joints.governing    // a joint by hand decides it (#311 review)
      ? `the joint between ${esc(c.joints.governing.between)}: ${esc(c.joints.governing.said)}`
      : c.governs === 'buckling'
      ? foldedBy(c)                                                       // the picture is the FEA's; the verdict isn't (#229)
      : c.governs === 'plate' && pl
      ? `the plate check on the ${esc(pl.piece)}: ${fixed(pl.stress_mpa, 1)} MPa, with the grain the wrong way`
      : `the FEA's peak: ${fixed(f.peak_mpa, 1)} MPa ${esc(peakWhere(f))}`;   // never an old run's label (#139 review)
    const bar = $('stationBar');
    bar.hidden = false;
    bar.innerHTML = `<div><div><b>${esc(c.name)}</b> · ${lbs(c.lb)} × ${c.factor} →
        ${partOf(pid).untrusted ? `<b style="color:var(--bad)">${notTrusted(partOf(pid).untrusted)}</b>`
          : c.verdict && (c.verdict.kind === 'unresolved' || c.verdict.kind === 'unchecked')   // no "holds" (CALI-110)
            ? `<b style="color:var(--amber)">${c.blind ? (c.rests ? `not resolved: ${esc(c.rests.said)}` : 'not resolved: the check couldn\'t see any stress here') : `${caseWhy(c, run)}`}</b>`
            : c.verdict && c.verdict.kind === 'edge'     // the middle only (CALI-94): no "holds" where people stand
              ? `<b style="color:var(--amber)">middle only: the middle read ${sx(c.safety, run.min_safety)}; the front edge, where people stand, isn't checked</b>`
            : settled(c.verdict)           // the verdict's word and colour (CALI-112): never green unless it holds
              ? `<b style="color:var(--${verdictTone(c.verdict)})">${esc(c.verdict.word)}, ${sx(c.safety, run.min_safety)}</b>`
              : `<b style="color:var(--amber)">${esc(c.verdict ? c.verdict.word : 'not checked yet')}: the check read ${sx(c.safety, run.min_safety)}</b>`}
        ${c.breaks_lb && settled(c.verdict) ? `· breaks at about ${Number(c.breaks_lb).toLocaleString()} lb` : ''}
        ${run.version !== partOf(pid).version ? `· <b style="color:var(--amber)">from v${run.version}: the part has changed since</b>` : ''}</div>
      <div class="small muted" style="margin-top:2px">Colours: whittle's FEA <span class="heatbar" style="background:linear-gradient(90deg, ${grad})"></span>
        0–${fixed(top, 1)} MPa (${esc(run.material.name)} breaks near ${fixed(run.material.strength, 1)} MPa). Decided by ${decided}.</div></div>
      <button id="stationClose" class="ghost">×</button>`;
    $('stationClose').onclick = () => { clearStation(); renderInspector(); };
    paint(); renderInspector();
  } catch (e) { showErr(e.message); }
}

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
      ${c ? `<div class="small" style="margin-bottom:6px">Carrying <b>${lbs(c.mass_lb)}</b> — ${c.parts.map((x) => `${esc((S.design.parts.find((q) => q.id === x.part) || {}).name || x.part)} ${lbs(x.mass_lb)}`).join(', ')} —
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
    <div class="muted small" style="margin:4px 0 8px">The script's own numbers: lengths in mm, angles in degrees, whatever units
      the rest shows. The current value must sit inside its range.
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
    <div id="aProgress"></div>
    ${runs.length ? aeroResults(p, runs[Math.min(S.aeroRun[p.id] || 0, runs.length - 1)], runs) : ''}`;
}

// what a run varied, in words: comparing "straight panels" with "curve free" is the point of a re-run
function aeroLabel(r) {
  const held = Object.entries(r.start || {}).filter(([k]) => /curve/.test(k) && !r.searched.includes(k));
  const shape = r.searched.some((k) => /curve/.test(k)) ? 'curve free'
    : held.length ? `curve held at ${held.map(([, v]) => +v).join('/')}` : 'searched';
  const effort = r.effort == null ? '' : ` · ${AERO_EFFORT[r.effort] || `effort ${r.effort}`} search`;
  return `${shape} · ${r.searched.length} numbers${effort} · ${r.builds} builds${r.created ? ` · ${aeroWhen(r.created)}` : ''}`;
}
// the search menu's words (#330: two runs read alike but for their build count)
const AERO_EFFORT = { 0.3: 'quick', 0.6: 'normal', 1: 'thorough' };
function aeroWhen(created) {
  const d = new Date(created * 1000);
  return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${String(d.getHours()).padStart(2, '0')}:${
    String(d.getMinutes()).padStart(2, '0')}`;
}
// a number as Use writes it: to its places, or, where it's the part's own with more (15.25 in is 387.35 mm), as it is
function aeroNum(v, places) {
  if (v == null) return '—';
  return Number(Number(v).toFixed(places)) === Number(v) ? Number(v).toFixed(places) : String(Number(Number(v).toFixed(6)));
}
// the same numbers as an earlier design: said, not read as another result (#341 review)
function aeroSame(run, s) {
  const key = (x) => run.searched.map((k) => aeroUses(run, x)[k]).join('|');
  const was = run.stations.find((x) => x.index < s.index && key(x) === key(s));
  return was ? ` <span class="muted small">same as ${was.index}</span>` : '';
}
// a design's numbers, as Use writes them (the server's, to its range's places, #330)
function aeroUses(run, s) {
  return s.uses || s.design;
}
// the design the part has now: each searched number what Use would write for it (#330: after Use, the table still read
// design 0 as 0% and offered design 3 again)
function aeroInUse(p, run, s) {
  const u = aeroUses(run, s) || {}, now = p.params || {}, ks = run.searched || [];
  return ks.length > 0 && ks.every((k) => now[k] != null && u[k] != null && Math.abs(+now[k] - +u[k]) <= 1e-9 * Math.max(1, Math.abs(+u[k])));
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
      ${run.stations.map((s) => `<tr class="pick ${s.index === on ? 'on' : ''}" data-ast="${s.index}"><td>${s.index}${
        aeroInUse(p, run, s) ? ' <span class="badge ok">in use</span>' : ''}${aeroSame(run, s)}</td>
        <td>${pct(-s.removed)}</td><td>${pct(s.metrics.drag)}</td><td>${saved(s)}</td>
        <td>${s.derived ? fixed(s.derived.saved_kwh_per_100mi, 2) : '—'}</td>
        ${run.searched.map((k) => `<td>${aeroNum(aeroUses(run, s)[k], (run.places || {})[k] ?? 1)}</td>`).join('')}</tr>`).join('')}</table></div>
    <div class="muted small" style="margin-top:6px">Click a row to see it in place; “volume” is the change against the part this
      search started from${run.version != null ? ` (v${run.version})` : ''}${run.stations.some((s) => aeroInUse(p, run, s))
        ? '; “in use” is the design the part has now' : ''}.
      Each design's drag was found at its unrounded numbers; Use writes them to the places shown, a hair off.
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
    trackJob(job_id, { kind: 'aero', part: p.id, text: 'starting…' }).done.catch(() => {});   // the overlay (#363)
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
const STUDY_PATH = { parametric: 'aero', frame: 'frame-study', lighten: 'lighten', carve: 'carve' };
async function showStation(pid, run, index) {
  const parametric = run.kind === 'parametric', framed = run.kind === 'frame', lightened = run.kind === 'lighten';
  const carved = run.kind === 'carve';
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
    const what = carved
      ? `<span><b>Preview, not carved yet:</b> step <b>${index}</b> · ${pct(st.removed)} ${carveShare(run)} carved away ·
        ${st.saved_g} g less filament · ${partOf(pid).untrusted ? `<b style="color:var(--bad)">${notTrusted(partOf(pid).untrusted)}</b>` : `<b style="color:var(--${verdictTone(st.verdict)})">${esc(st.verdict ? st.verdict.word : 'not checked yet')}, ${sx(st.safety, run.min_safety)}</b>`}</span>`
      : lightened
      ? `<span><b>Preview, not cut yet:</b> step <b>${index}</b> · ${pct(st.removed)} out of the walls${st.top_holes ? ` and ${st.top_holes} hole${st.top_holes === 1 ? '' : 's'} in the top` : ''} · ${lbs(st.saved_lb)} lighter ·
        ${partOf(pid).untrusted ? `<b style="color:var(--bad)">${notTrusted(partOf(pid).untrusted)}</b>` : `<b style="color:var(--${verdictTone(st.verdict)})">${esc(st.verdict ? st.verdict.word : 'not checked yet')}, ${sx(st.safety, run.min_safety)}</b>`}</span>`
      : framed
      ? `<span>design <b>${index}</b> · ${st.mass_lb} lb of steel · weakest ${st.safety}x · sags ${len(st.deflection_mm, 2)}</span>`
      : `<span>${parametric ? 'design' : 'whittle station'} <b>${index}</b> · gives up ${pct(removed)} of the volume
      ${st.metrics && st.metrics.drag != null ? ` · drag ${pct(st.metrics.drag)}` : ''}</span>`;
    bar.innerHTML = `${what}
      ${carved && st.closed === false ? `<span class="small" style="color:var(--bad)">Can't use this step: ${esc(st.why)}.</span>` : ''}
      ${stationAction(pid, run, index, st)}
      <button id="stationClose" class="ghost">×</button>`;
    $('stationClose').onclick = () => { clearStation(); renderInspector(); };
    if ($('adoptBtn')) $('adoptBtn').onclick = () => adoptStation(pid, run.id, index, run.kind);
    paint(); renderInspector();
  } catch (e) { showErr(e.message); }
}
// the bar's offer for a step: a Lighten or carve of an older version can't be cut in (the server refuses it, CALI-87),
// so it isn't offered: the bar says to run it again (CALI-92, #70 item 24)
function stationAction(pid, run, index, st) {
  const lightened = run.kind === 'lighten', carved = run.kind === 'carve';
  if ((lightened || carved) && !index) return '';
  const now = partOf(pid).version;
  if ((lightened || carved) && run.version != null && now != null && run.version !== now) {
    return `<span class="small" id="staleRun">${lightened ? 'This lightening' : 'This carve'} is of v${run.version}, and the part
      has changed since (it's v${now}): ${lightened ? 'lighten' : 'carve'} it again.</span>`;
  }
  if (run.kind === 'parametric' && aeroInUse(partOf(pid), run, st)) {     // used already: said, not offered again (#330)
    return `<span class="small" id="inUse">In use: ${esc(pid)} v${partOf(pid).version} has these numbers.</span>`;
  }
  const no = (lightened || carved) && !holdsHere(st) ? `It can't be used: ${st.verdict ? st.verdict.word : 'not checked'}` : '';
  return `<button class="primary" id="adoptBtn" ${no ? `disabled title="${esc(no)}"` : ''}>${lightened ? 'Cut these holes in '
    : carved ? 'Carve it like this: ' : run.kind === 'frame' ? 'Use these sizes for ' : run.kind === 'parametric' ? 'Use these numbers for ' : 'Bring this back as '}${esc(pid)}</button>${no
    ? `<span class="small muted" id="adoptWhy" data-off-why="1">${esc(no)}</span>` : ''}`;   // said, not only hovered (#306 review)
}
// a version of a part, shown in the view where the part is: "v3 (preview)", what was asked of it, and Go back to this (#299)
async function showVersion(pid, v) {
  const h = (partOf(pid).history || []).find((x) => x.kind === 'revision' && x.version === v) || {};
  try {
    const r = await fetch(`/api/designs/${S.slug}/parts/${pid}/versions/${v}.stl`);
    if (!r.ok) throw new Error(`v${v}: HTTP ${r.status}`);
    const geom = loader.parse(await r.arrayBuffer());
    geom.computeVertexNormals();
    clearStation(true);
    stationMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: 0xffb454, roughness: 0.55, metalness: 0.05 }));
    scene.add(stationMesh);
    S.station = { part: pid, version: v };
    let vol = 0;                                   // its volume, from the shape shown
    const a = geom.attributes.position;
    for (let i = 0; i < a.count; i += 3) {
      const [x1, y1, z1, x2, y2, z2, x3, y3, z3] = [0, 1, 2].flatMap((k) => [a.getX(i + k), a.getY(i + k), a.getZ(i + k)]);
      vol += (x1 * (y2 * z3 - y3 * z2) - x2 * (y1 * z3 - y3 * z1) + x3 * (y1 * z2 - y2 * z1)) / 6;
    }
    const bar = $('stationBar');
    bar.hidden = false;
    bar.innerHTML = `<span><b>v${v} (preview)</b>${h.feedback ? ` · “${esc(h.feedback)}”` : h.action ? ` · ${esc(h.action)}` : ''}
      · ${fixed(Math.abs(vol) / 1000, 0)} cm³</span>
      <button class="primary" data-goback-v="${v}">Go back to this</button> <button id="stationClose" class="ghost">×</button>`;
    $('stationClose').onclick = () => { clearStation(); renderInspector(); };
    paint();
  } catch (e) { showErr(plainly(e.message)); }
}
async function goBackTo(pid, v) {
  const once = `goback:${S.slug}/${pid}`;        // pressed twice saved two versions (#324): taken once, its buttons off
  if (S.running[once]) return;
  S.running[once] = true;
  document.querySelectorAll('[data-goback-v]').forEach((b) => { b.disabled = true; });
  try {
    const got = await api('POST', `/api/designs/${S.slug}/parts/${pid}/restore`, { version: v });
    clearStation();
    S.design = got.design;
    render();
    await syncParts(S.design, false);
  } catch (e) { showErr(plainly(e.message)); } finally { delete S.running[once];
    document.querySelectorAll('[data-goback-v]').forEach((b) => { b.disabled = false; }); }
}
document.addEventListener('click', (e) => {     // the history's buttons, and the preview bar's
  const pv = e.target.closest('[data-preview-v]'), gb = e.target.closest('[data-goback-v]'), shown = shownPart();   // its view, picked or not (#364)
  if (pv && shown) showVersion(shown, Number(pv.dataset.previewV));
  else if (gb && (shown || (S.station && S.station.part))) goBackTo(shown || S.station.part, Number(gb.dataset.gobackV));
});
function clearStation(keepBar) {
  if (stationMesh) { scene.remove(stationMesh); stationMesh.geometry.dispose(); stationMesh = null; }
  S.station = null;
  if (!keepBar) $('stationBar').hidden = true;
  if (S.design) paint();
}
async function adoptStation(pid, wid, index, kind) {
  const once = `adopt:${S.slug}/${wid}:${index}`;             // a double click takes the step once, and shows no false error (#159)
  if (S.running[once]) return;
  S.running[once] = true;
  try { await takeStation(pid, wid, index, kind); } finally { delete S.running[once]; }
}
async function takeStation(pid, wid, index, kind) {
  const go = $('adoptBtn');                         // none when it's Make it better's Use it (#92)
  if (go) go.disabled = true;
  try {
    await api('POST', `/api/designs/${S.slug}/${STUDY_PATH[kind] || 'whittle'}/${wid}/adopt`, { station: index });
    clearStation();
    await refresh();
    // holes cut in, or carved: check its strength again on the part as rebuilt — that's the number to go by
    if (kind === 'lighten' || kind === 'carve') {
      const p = S.design.parts.find((x) => x.id === pid);
      if (p && $('lGo')) runLoad(p);
    }
  } catch (e) { showErr(e.message); if (go) go.disabled = false; }
}

// ------------------------------------------------------------- the studies page (CALI-70)
// Every study the design has, newest first: the part and the version it ran on, the line it came to, and a
// way to open it where it lives. And per part, every study Caliper has: which can run on it now, and what the
// others are missing (what to say or do to get them).
const STUDY_BOX = { load: 'loadBox', lighten: 'loadBox', carve: 'loadBox', frame: 'frameBox', gussets: 'frameBox', aero: 'aeroBox', whittle: 'whittleBox',
  cutplan: 'buildBox', patterns: 'buildBox', scorecard: 'scoreBox', release: 'relBox' };
const studyFilter = { kind: '', part: '' };

function studiesView(d) {
  const st = d.studies || { runs: [], menu: {}, design: [] };
  const rows = st.runs.filter((r) => (!studyFilter.kind || r.kind === studyFilter.kind)
    && (!studyFilter.part || (studyFilter.part === '*' ? !r.part : r.part === studyFilter.part)));
  const kinds = [...new Map(st.runs.map((r) => [r.kind, r.label])).entries()];
  const parts = d.parts.filter((p) => p.role !== 'fixed');
  const when = (t) => (t ? new Date(t * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—');
  const count = (pid, kind) => st.runs.filter((r) => r.part === pid && r.kind === kind).length;
  const item = (m, pid) => `<button class="menu-item ${m.ready ? '' : 'off'}" data-go-kind="${m.kind}" data-go-part="${esc(pid || '')}"
      title="${esc(m.ready ? m.what : `Not yet: ${m.why}`)}">
      <b>${esc(m.label)}${pid && count(pid, m.kind) ? ` <span class="n">· ${count(pid, m.kind)} run${count(pid, m.kind) === 1 ? '' : 's'}</span>` : ''}</b>
      <span class="small muted">${esc(m.ready ? m.what : `Not yet: ${m.why}`)}</span></button>`;
  return `<div class="studies-head"><h2>Studies <span class="muted small">${esc(d.name)}</span></h2>
      <button class="x" id="studiesClose" title="back to the design (Esc)">×</button></div>
    <h4>Run a study</h4>
    <div class="menu">${parts.map((p) => `<div class="menu-part">
        <div><span class="partlink" data-go-part="${esc(p.id)}">${esc(p.name || p.id)}</span> <span class="muted small">v${p.version} · ${esc(p.intent || '')}</span></div>
        <div class="menu-items">${(st.menu[p.id] || []).map((m) => item(m, p.id)).join('')}</div></div>`).join('')}
      <div class="menu-part"><div><b>The whole design</b></div>
        <div class="menu-items">${(st.design || []).map((m) => item(m, '')).join('')}</div></div></div>
    <h4>Every run <span class="muted">· ${st.runs.length}</span></h4>
    ${st.runs.length ? `<div class="filters"><select id="sfKind"><option value="">every kind</option>
        ${kinds.map(([k, l]) => `<option value="${k}" ${studyFilter.kind === k ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
      <select id="sfPart"><option value="">every part</option>
        ${parts.map((p) => `<option value="${esc(p.id)}" ${studyFilter.part === p.id ? 'selected' : ''}>${esc(p.name || p.id)}</option>`).join('')}
        <option value="*" ${studyFilter.part === '*' ? 'selected' : ''}>the whole design</option></select>
      <span class="muted small">${rows.length} shown</span></div>
    <table class="st studies-table"><tr><th>when</th><th>study</th><th>on</th><th>what it came to</th><th></th></tr>
      ${rows.map((r) => `<tr class="pick" data-go-kind="${r.kind}" data-go-part="${esc(r.part || '')}" data-go-run="${esc(r.id || '')}">
        <td class="when">${when(r.created)}</td><td>${esc(r.label)}</td>
        <td>${r.part ? `${esc((parts.find((x) => x.id === r.part) || {}).name || r.part)} <span class="muted">v${r.version ?? '?'}</span>` : '<span class="muted">the design</span>'}
          ${r.stale ? ' <span class="badge bad" title="it has changed since this ran">changed since</span>' : ''}</td>
        <td style="color:${r.ok === true ? 'var(--ok)' : r.ok === false ? 'var(--bad)' : 'inherit'}">${esc(r.headline)}</td>
        <td><button>Open</button></td></tr>`).join('')}</table>`
    : '<div class="empty">No studies yet. Pick one above.</div>'}`;
}

function renderStudies() {
  const el = $('studies');
  el.hidden = !S.studies || !S.design;
  $('studiesBtn').classList.toggle('on', !!S.studies);
  if (el.hidden) return;
  el.innerHTML = studiesView(S.design);
  $('studiesClose').onclick = () => { S.studies = false; renderStudies(); };
  const kind = $('sfKind'), part = $('sfPart');
  if (kind) kind.onchange = () => { studyFilter.kind = kind.value; renderStudies(); };
  if (part) part.onchange = () => { studyFilter.part = part.value; renderStudies(); };
  el.querySelectorAll('[data-go-kind], [data-go-part]').forEach((n) => {
    n.onclick = (e) => {
      e.stopPropagation();
      openStudy(n.dataset.goKind || '', n.dataset.goPart || '', n.dataset.goRun || '');
    };
  });
}
$('studiesBtn').onclick = () => { S.studies = !S.studies; renderStudies(); };
addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && S.studies) { S.studies = false; renderStudies(); }
});

// open a study where it lives: the part's (or the design's) panel, that run picked, scrolled into view
function openStudy(kind, pid, runId) {
  S.studies = false;
  renderStudies();
  const pick = (list, key) => { const k = list.findIndex((r) => r.id === runId); if (k >= 0) S[key][pid] = k; };
  if (pid && runId) {
    if (kind === 'load') pick(loadRuns(pid), 'loadRun');
    if (kind === 'frame') pick(frameRuns(pid), 'frameRun');
    if (kind === 'aero') pick(aeroRuns(pid), 'aeroRun');
    if (kind === 'whittle') pick(runsFor(pid), 'runIndex');
  }
  clearStation();
  setScope(pid || null);
  goTo(STUDY_BOX[kind]);
  // a strength check opens on the stress picture of its weakest load
  const run = kind === 'load' && runId ? loadRuns(pid).find((r) => r.id === runId) : null;
  if (run) {
    const worst = run.cases.reduce((a, c, i) => (c.heat && (a < 0 || (c.safety ?? 1e9) < (run.cases[a].safety ?? 1e9)) ? i : a), -1);
    if (worst >= 0) showHeat(pid, run, worst);
  }
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
  if (was !== S.whittle.ok && shownPart() && !document.querySelector('#wProgress .bar, #aProgress .bar, #lProgress .bar')) renderInspector();
}
checkWhittle();
setInterval(checkWhittle, 15000);
window.__design = S;            // debug seam (like the classic page's window.__asm)
loadDesigns().catch((e) => showErr(e.message));
