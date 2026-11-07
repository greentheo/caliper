// CALI-45 — run unfold-to-sheets (github.com/greentheo/unfold-to-sheets) on one material's panels.
//
// Caliper writes the panels of a part as an OBJ with one group per panel — the seams are authored, so
// unfold-to-sheets segments by group rather than guessing — and hands this driver the stock and the
// material as plain objects (its resolveStock takes objects as well as ids, so 1 in XPS needs no change
// to that repo). It unfolds each panel (folds inside a panel become score lines), nests the pieces onto
// the stock, writes its package (sheets as SVG + DXF, assembly drawing, seam list, PDF) and prints a JSON
// summary on its last line.
//
//   node unfold_driver.mjs < job.json      job = {obj, out, name, units, stock, material, rotations}

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const job = JSON.parse(readFileSync(0, 'utf8'));
const root = job.unfold_dir;
const lib = async (m) => import(pathToFileURL(join(root, 'js', m)).href);

const { parseOBJ, buildMesh } = await lib('mesh.js');
const { prepare, runScale } = await lib('pipeline.js');
const { buildSheets } = await lib('sheetview.js');
const { buildAssembly } = await lib('assembly.js');
const { buildPackage } = await lib('package.js');
const { nestPieces } = await lib('nesting.js');

const mesh = buildMesh(parseOBJ(readFileSync(job.obj, 'utf8')), { units: job.units, name: job.name });
const prepared = prepare(mesh, { stock: job.stock, material: job.material, units: job.units,
  rotations: job.rotations ?? 8 });
const result = runScale(prepared, 1, { rotations: job.rotations ?? 8 });

// CALI-126 (#151 review): a panel whose face grain the person said is laid with that grain along the sheet's length
// (the sheet's own grain), never turned across it. unfold-to-sheets flattens each piece in its own frame and its
// grain lock is for a whole nest, so: find each such piece's grain on its flat (the plane's map from three of its
// corners), turn its outline so the grain runs along the sheet, nest the lot turning end for end only, and put the
// turn back into the placement (rotate by angle, then shift: R(a) R(-t) = R(a - t)). Said per piece: it fits that
// way, or not. A piece split in two (top -> topa, topb) keeps its panel's grain.
const want = job.grain || {};
const grainOut = [];
let grainFree = null;
if (Object.keys(want).length) {
  const P = result.mesh.positions;
  const at = (i) => [P[i * 3], P[i * 3 + 1], P[i * 3 + 2]];
  const sub3 = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot3 = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  // the panel a piece is cut from, by its faces' OBJ group: its label is the group's only when there are several
  // (one panel alone is "P1"), and a split one is "topa", "topb"
  const M = prepared.mesh;
  const of = (p) => {
    const f = (p.patch && p.patch.faces || [])[0];
    const name = f != null && M.groupNames ? M.groupNames[M.groups[f] ?? 0] : p.label;
    return Object.prototype.hasOwnProperty.call(want, name) ? name : null;
  };
  const turn = new Map();
  result.pieces.forEach((p, i) => {
    const name = of(p);
    if (!name) return;
    const ids = [...p.flat.xy.keys()];
    const a = ids[0];
    const b = ids.reduce((m, k) => (dot3(sub3(at(k), at(a)), sub3(at(k), at(a))) > dot3(sub3(at(m), at(a)), sub3(at(m), at(a))) ? k : m), a);
    const e1 = sub3(at(b), at(a)), L1 = dot3(e1, e1) || 1;
    const off = (k) => { const e = sub3(at(k), at(a)), s = dot3(e, e1) / L1; return sub3(e, [e1[0] * s, e1[1] * s, e1[2] * s]); };
    const c = ids.reduce((m, k) => (dot3(off(k), off(k)) > dot3(off(m), off(m)) ? k : m), a);
    const e2 = sub3(at(c), at(a));
    const g = want[name];
    const g11 = dot3(e1, e1), g12 = dot3(e1, e2), g22 = dot3(e2, e2), det = g11 * g22 - g12 * g12;
    const ua = p.flat.xy.get(a), ub = p.flat.xy.get(b), uc = p.flat.xy.get(c);
    if (!(Math.abs(det) > 1e-9) || !ua || !ub || !uc) { grainOut.push({ label: p.label, name, fits: false, why: "its outline is too thin to tell which way it lies" }); return; }
    const al = (dot3(g, e1) * g22 - dot3(g, e2) * g12) / det, be = (dot3(g, e2) * g11 - dot3(g, e1) * g12) / det;
    const gu = al * (ub.u - ua.u) + be * (uc.u - ua.u), gv = al * (ub.v - ua.v) + be * (uc.v - ua.v);
    if (Math.hypot(gu, gv) < 0.2) { grainOut.push({ label: p.label, name, fits: false, why: "its grain runs through its thickness, not along its face" }); return; }
    const t = (Math.atan2(gv, gu) * 180) / Math.PI;
    turn.set(i, t);
    grainOut.push({ label: p.label, name, turned_deg: Math.round(t * 10) / 10 });
  });
  const rot = (q, deg) => { const r = (deg * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r); return { u: q.u * c - q.v * s, v: q.u * s + q.v * c }; };
  const s = result.stock;
  const free = result.sheetCount;              // what it took turning freely: the lock's cost, said (#151 review)
  const nest = nestPieces(result.pieces.map((p, i) => ({ id: i, label: p.label,
    outline: turn.has(i) ? p.flat.cutOutline.map((q) => rot(q, -turn.get(i))) : p.flat.cutOutline })),
  { sheetLength: s.sheetLength, sheetWidth: s.sheetWidth, margin: s.margin, kerf: s.kerf, grain: true,
    rotations: job.rotations ?? 8, openSheets: 0 });
  for (const sheet of nest.sheets) for (const pl of sheet.placed) if (turn.has(pl.index)) pl.angle -= turn.get(pl.index);
  grainFree = free;
  const sheetArea = s.sheetLength * s.sheetWidth;
  result.nest = nest; result.sheets = nest.sheets; result.sheetCount = nest.sheets.length;
  result.stockArea = nest.sheets.length * sheetArea;
  result.utilisation = result.stockArea > 0 ? result.partArea / result.stockArea : 0;
  result.wasteSheets = result.stockArea > 0 ? (result.stockArea - result.partArea) / sheetArea : 0;
  result.missing = [...result.missing.filter((m) => m.stage !== 'nest'), ...nest.oversize.map((o) => ({
    key: o.piece.label, label: o.piece.label, stage: 'nest', width: o.width, height: o.height,
    why: 'no way fits the sheet turning it end for end only, its grain along the sheet' }))];
  for (const g of grainOut) {
    if (g.fits === false) continue;
    g.fits = !nest.oversize.some((o) => o.piece.label === g.label);
    if (!g.fits) g.why = "it doesn't fit the sheet with its grain along the sheet's length";
  }
}
// A thick board takes a gentle bend without being scored: folds under the material's threshold are
// left off the drawings (unfold-to-sheets scores anything over 0.5°, right for card, not for 1 in foam).
const minScore = job.min_score_deg ?? 0;
let scored = 0, bent = 0;
for (const p of result.pieces) {
  const keep = p.flat.folds.filter((f) => Math.abs(f.angleDeg ?? 0) >= minScore);
  scored += keep.filter((f) => Math.abs(f.angleDeg ?? 0) >= 0.5).length;   // what gets drawn
  bent += p.flat.folds.length - keep.length;
  p.flat.folds = keep;
}
const view = buildSheets(result);
// Holes before outlines (CALI-87, as #45 says): a panel cut free first has nothing holding it while its holes are
// cut. Only the cut lines change places, among themselves; everything else stays where unfold-to-sheets put it.
for (const sheet of view.sheets ?? []) {
  const at = sheet.items.map((it, i) => (it.layer === 'cut' ? i : -1)).filter((i) => i >= 0);
  const cuts = at.map((i) => sheet.items[i]);
  const ordered = [...cuts.filter((it) => it.kind === 'hole'), ...cuts.filter((it) => it.kind !== 'hole')];
  at.forEach((i, k) => { sheet.items[i] = ordered[k]; });
}
const assembly = buildAssembly(result);
const files = buildPackage(result, view, assembly);
for (const f of files) {
  const p = join(job.out, f.name);
  mkdirSync(dirname(p), { recursive: true });
  if (f.latin1) {
    const bytes = Buffer.alloc(f.text.length);
    for (let i = 0; i < f.text.length; i++) bytes[i] = f.text.charCodeAt(i) & 0xff;
    writeFileSync(p, bytes);
  } else writeFileSync(p, f.text);
}

const pieces = result.pieces.map((p) => {
  const xs = p.flat.cutOutline.map((q) => q.u), ys = p.flat.cutOutline.map((q) => q.v);
  return {
    label: p.label, edge_error: p.flat.maxEdgeError, spread: p.flat.spread,
    overlaps: p.flat.overlaps.length,
    size: [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)],
  };
});
// Joints between pieces: every seam between the same two pieces together — its length and the angle the
// pieces meet at, for bevelling a thick board's edges (half the angle on each).
const pairs = new Map();
for (const seam of result.seams.seams.values()) {
  const [i, j] = [...seam.pieces].sort((a, b) => a - b);
  const key = `${i}:${j}`;
  const g = pairs.get(key) || { a: result.pieces[i].label, b: result.pieces[j].label, length: 0, sum: 0, max: 0, min: 180 };
  const ang = Math.abs(seam.foldDeg ?? 0);
  g.length += seam.length; g.sum += ang * seam.length; g.max = Math.max(g.max, ang); g.min = Math.min(g.min, ang);
  pairs.set(key, g);
}
const joints = [...pairs.values()].map((g) => ({
  a: g.a, b: g.b, length: g.length, angle_mean: g.length ? g.sum / g.length : 0, angle_max: g.max, angle_min: g.min,
}));
console.log(JSON.stringify({ joints,
  segment: prepared.segmentMethod, patches: prepared.patches.length,
  cuts: prepared.seamEdgeCount, folds: prepared.foldEdgeCount, scored, bent_unscored: bent,
  min_score_deg: minScore,
  pieces: pieces.length, splits: result.splits, sheets: result.sheetCount,
  utilisation: result.utilisation, worst_edge_error: result.worstEdgeError, worst_spread: result.worstSpread,
  missing: result.missing.map((m) => ({ label: m.label, why: m.why })),
  tokens_ok: result.tokenCheck.ok,
  files: files.map((f) => ({ name: f.name, kind: f.kind, describe: f.describe })),
  piece_list: pieces,
  grain: grainOut,
  grain_sheets: grainOut.length ? { free: grainFree, kept: result.sheetCount } : null,
}));
