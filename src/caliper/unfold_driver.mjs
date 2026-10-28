// CALI-45 — run Theo's unfold-to-sheets (game-dev/unfold-to-sheets) on one material's panels.
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

const mesh = buildMesh(parseOBJ(readFileSync(job.obj, 'utf8')), { units: job.units, name: job.name });
const prepared = prepare(mesh, { stock: job.stock, material: job.material, units: job.units,
  rotations: job.rotations ?? 8 });
const result = runScale(prepared, 1, { rotations: job.rotations ?? 8 });
// A thick board takes a gentle bend without being scored: folds under the material's threshold are
// left off the drawings (unfold-to-sheets scores anything over 0.5°, right for card, not for 1 in foam).
const minScore = job.min_score_deg ?? 0;
let scored = 0, bent = 0;
for (const p of result.pieces) {
  const keep = p.flat.folds.filter((f) => Math.abs(f.angleDeg ?? 0) >= minScore);
  scored += keep.length;
  bent += p.flat.folds.length - keep.length;
  p.flat.folds = keep;
}
const view = buildSheets(result);
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
console.log(JSON.stringify({
  segment: prepared.segmentMethod, patches: prepared.patches.length,
  cuts: prepared.seamEdgeCount, folds: prepared.foldEdgeCount, scored, bent_unscored: bent,
  min_score_deg: minScore,
  pieces: pieces.length, splits: result.splits, sheets: result.sheetCount,
  utilisation: result.utilisation, worst_edge_error: result.worstEdgeError, worst_spread: result.worstSpread,
  missing: result.missing.map((m) => ({ label: m.label, why: m.why })),
  tokens_ok: result.tokenCheck.ok,
  files: files.map((f) => ({ name: f.name, kind: f.kind, describe: f.describe })),
  piece_list: pieces,
}));
