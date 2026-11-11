"""CALI-75 (#42) — coupons: calibrate the strength check against small samples measured by hand.

A coupon is a strip on two supports, loaded in the middle (a three-point bend). Each one gets three numbers:

(a) what beam theory says, from the materials table;
(b) what whittle says, the same way the strength check runs it (:func:`caliper.load_study.check_load`);
(c) what Theo measures at the bench.

(a) against (b) says whether the check is right about the mechanics; (b) against (c) says whether the material
values are right. This module has (a) and (b), and writes the one-page bench sheet and the theory-against-whittle
table. Nothing here changes a verdict: correction factors come later, and using them is Theo's call.

    python -m caliper.coupons --out pm/bench          # the sheet (quick)
    python -m caliper.coupons --out pm/bench --fea    # and whittle's numbers (a few minutes)
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import load_study as L
from . import materials as M

IN = M.IN
LB = L.LB
#: The saddle the load hangs from and each support's bearing, along the span (mm).
PAD = IN
#: Timoshenko's shear factor for a rectangle.
KAPPA = 5 / 6
#: The load steps stay under this share of the predicted break: well inside the straight part of the curve.
MOST_OF_BREAK = 0.4
#: Below this sag (mm) at the top step, a ruler read to half a millimetre can't give a useful number.
RULER_MM = 3.0


@dataclass(frozen=True)
class Coupon:
    id: str
    name: str
    #: what the table calls it: "lumber", "plywood", or a printed plastic
    material: str
    length: float
    #: across the coupon, level, as it sits on the supports
    width: float
    #: up and down, the way the load pushes
    depth: float
    span: float
    #: the three targets for reading sag, lb
    steps: tuple
    how: str
    #: plywood with its face grain across the span
    across: bool = False
    #: whether the sheet asks for a break, and if not what it would take
    breaks: bool = True
    note: str = ""


_2X4 = M.STICKS["lumber"]["sizes"]["2x4"]
_PETG = {"material": "petg", "length": 8 * IN, "width": 1 * IN, "depth": 0.5 * IN, "span": 6 * IN, "steps": (4, 8, 12)}

COUPONS = (
    Coupon("2x4-E", "2x4 on edge", "lumber", 90 * IN, _2X4[0], _2X4[1], 84 * IN, (50, 100, 150),
           "8 ft stud cut to 90 in. Pick a straight one and test it this way first", breaks=False),
    Coupon("2x4-F", "2x4 flat", "lumber", 90 * IN, _2X4[1], _2X4[0], 84 * IN, (20, 40, 60),
           "the same stud, turned flat"),
    Coupon("34-L", "3/4 in ply, along", "plywood", 34 * IN, 3 * IN, 0.75 * IN, 30 * IN, (20, 40, 60),
           "3 x 34 in strip, face grain along its length"),
    Coupon("34-X", "3/4 in ply, across", "plywood", 34 * IN, 3 * IN, 0.75 * IN, 30 * IN, (10, 20, 30),
           "3 x 34 in strip, face grain across it", across=True),
    Coupon("12-L", "1/2 in ply, along", "plywood", 28 * IN, 3 * IN, 0.5 * IN, 24 * IN, (10, 20, 30),
           "3 x 28 in strip, face grain along its length"),
    Coupon("12-X", "1/2 in ply, across", "plywood", 28 * IN, 3 * IN, 0.5 * IN, 24 * IN, (5, 10, 15),
           "3 x 28 in strip, face grain across it", across=True),
    Coupon("PG-F", "PETG, printed flat", how="1 x 1/2 x 8 in bar, the 1 in face on the bed", **_PETG),
    Coupon("PG-E", "PETG, printed on edge", how="same bar, the 1/2 in face on the bed", **_PETG),
    # the only one that pulls the layers apart, which is what LAYERS_ACROSS and #64 item 6 want to know
    Coupon("PG-S", "PETG, printed standing", how="same bar, printed upright with a brim: bending pulls its layers apart",
           **_PETG),
)


def by_id(key: str) -> Coupon:
    return next(c for c in COUPONS if c.id == key)


def _solid(c: Coupon):
    import trimesh

    box = trimesh.creation.box(extents=(c.length, c.width, c.depth))
    box.apply_translation((c.length / 2, c.width / 2, c.depth / 2))
    return box


def material(c: Coupon) -> dict:
    """The E and strength the check gives this coupon, from the check's own functions. Printed: its plastic at the share
    that's plastic and half strength (at Caliper's default walls and infill), the same three ways round."""
    if c.material in M.PRINTS:
        declared = {"construction": [{"kind": "printed", "material": c.material}]}
        got = L.printed_material(declared, _solid(c))
        return {"E": got["E"], "strength": got["strength"], "name": got["name"]}
    got = L.material([{"material": c.material, "volume": 1.0}])
    k = got["across"] if c.across else 1.0
    return {"E": got["E"] * k, "strength": got["strength"] * k, "name": got["name"]}


def theory(c: Coupon, lb: Optional[float] = None) -> dict:
    """Beam theory at ``lb`` (the top step if not given): sag in bending plus shear, the peak stress, and the load
    that takes the stress to the table's strength. Shear at the solver's isotropic G, since (a) is checking (b)."""
    mat, lb = material(c), lb if lb is not None else c.steps[-1]
    force = lb * LB
    moment_of_area = c.width * c.depth ** 3 / 12
    area = c.width * c.depth
    shear = mat["E"] / (2 * (1 + L.POISSON))
    sag = force * c.span ** 3 / (48 * mat["E"] * moment_of_area) + force * c.span / (4 * KAPPA * shear * area)
    stress = 1.5 * force * c.span / (c.width * c.depth ** 2)
    return {"lb": lb, "sag_mm": sag, "stress_mpa": stress, "breaks_lb": lb * mat["strength"] / stress,
            "E": mat["E"], "strength": mat["strength"]}


def check_spacing(c: Coupon) -> float:
    """The voxels the check would use on this coupon, by its own rule: on a long strip, coarser than four across."""
    thin = min(c.width, c.depth)
    return L.spacing_for([{"kind": "sheet", "thickness": thin}], c.length * c.width * c.depth, c.length)[0]


def across(c: Coupon, n: int) -> float:
    """Voxels sized to put exactly ``n`` across the coupon's thinnest side: the size a real panel gets from the check."""
    return min(c.width, c.depth) / n


def fea(c: Coupon, spacing: Optional[float] = None, *, how: str = "check", lb: Optional[float] = None) -> dict:
    """Whittle's sag and stress for this coupon, through the check's own :func:`~caliper.load_study.check_load`.

    ``how="check"``: held the way the check holds a part, a pad under each support with every voxel in it pinned.
    ``how="alone"``: the solver with no supports to get wrong. By symmetry half a three-point beam is a cantilever from
    mid-span, with half the load on its end, and the same sag and root moment."""
    from whittle import LoadStudy, Material, Mesh

    from .consistency import tolerance

    mat, lb = material(c), lb if lb is not None else c.steps[-1]
    spacing = spacing or check_spacing(c)
    run = c if how == "check" else _half(c)
    mesh = _solid(run)
    ls = LoadStudy(Mesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces)),
                   material=Material(name=mat["name"], youngs_modulus=mat["E"], poisson_ratio=L.POISSON,
                                     strength=mat["strength"], density=1.0), spacing=spacing)
    grow = L.reach(tolerance(mesh), spacing) + spacing / 2
    attach = np.zeros(ls.grid.shape, dtype=bool)
    if how == "check":
        for lo, hi in held_boxes(c):
            box = L._grow(lo, hi, grow)
            ls.support(box=box)
            attach |= ls.region(box=box)
        box, force = L._grow(*load_box(c), grow), [0.0, 0.0, -lb * LB]
    else:
        columns = np.flatnonzero(ls.solid.any(axis=(1, 2)))     # the first and last columns of voxels, by their centres
        def column(i):
            x = float(ls.grid.origin[0]) + spacing * int(i)
            return ((x - 0.4 * spacing, -1.0, -1.0), (x + 0.4 * spacing, run.width + 1, run.depth + 1))
        root = column(columns[0])
        ls.support(box=root)
        attach |= ls.region(box=root)
        box, force = column(columns[-1]), [0.0, 0.0, -lb * LB / 2]
    attach |= ls.region(box=box)
    ctx = {"ls": ls, "loads": [{"name": c.id, "lb": lb, "factor": 1.0, "force": force, "lo": list(box[0]),
                                "hi": list(box[1])}],
           "boxes": [box], "mat": mat, "attach": attach, "pieces": [], "tol": tolerance(mesh), "declared": {},
           "spacing": spacing}
    case, result = L.check_load(ctx, 0, L.MIN_SAFETY)
    got = case["fea"]
    return {"how": how, "spacing_mm": round(spacing, 2), "across": round(min(c.width, c.depth) / spacing, 2),
            "voxels": int(ls.solid.sum()), "layers": int(ls.solid.sum(axis=2).max()),  # how deep the voxels make it
            "converged": bool(result.converged), "sag_mm": got["deflection_mm"],
            "peak_mpa": got["peak_mpa"], "breaks_lb": round(lb * mat["strength"] / got["peak_mpa"], 1)}


def _half(c: Coupon) -> Coupon:
    return Coupon(c.id, c.name, c.material, c.span / 2, c.width, c.depth, c.span, c.steps, c.how, c.across)


def held_boxes(c: Coupon) -> list:
    """Where the supports touch it: the underside, a pad wide, at each end of the span."""
    ends = ((c.length - c.span) / 2, (c.length + c.span) / 2)
    return [((x - PAD / 2, 0.0, 0.0), (x + PAD / 2, c.width, 0.0)) for x in ends]


def load_box(c: Coupon) -> tuple:
    """Where the load hangs from: the top, a pad wide, at the middle."""
    return ((c.length / 2 - PAD / 2, 0.0, c.depth), (c.length / 2 + PAD / 2, c.width, c.depth))


def measure() -> list[dict]:
    """(a) and (b) for every coupon. The three printed ones are one model, so one run covers them."""
    done: dict = {}
    rows = []
    for c in COUPONS:
        key = (c.material, c.length, c.width, c.depth, c.span, c.across)
        if key not in done:
            done[key] = {"check": fea(c), "four": fea(c, across(c, 4)), "six": fea(c, across(c, 6)),
                         "alone_four": fea(c, across(c, 4), how="alone"), "alone_six": fea(c, across(c, 6), how="alone")}
        t = theory(c)
        rows.append({"id": c.id, "name": c.name, "lb": c.steps[-1], "theory_sag_mm": round(t["sag_mm"], 2),
                     "theory_breaks_lb": round(t["breaks_lb"], 1), **done[key]})
    return rows


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------
def _mm(v: float) -> str:
    return f"{v:.2f}" if v < 10 else f"{v:.1f}"


def _cell(r: dict, how: str) -> str:
    return f"{r[how]['sag_mm'] / r['theory_sag_mm']:.2f} / {r[how]['breaks_lb'] / r['theory_breaks_lb']:.2f}"


def _span(rows: list, how: str, field: str, theory: str) -> tuple:
    got = [r[how][field] / r[theory] for r in rows]
    return min(got), max(got)


def table_md(rows: list[dict]) -> str:
    head = ("# Coupons: beam theory against whittle (#42)\n\n"
            "Generated by `python -m caliper.coupons --out pm/bench --fea`. Do not edit by hand. The raw numbers are in "
            "`theory-vs-whittle.json`.\n\n"
            "Each row is one coupon in a three-point bend at its top load step, with the material values Caliper uses today. "
            "Each whittle cell is **sag / break load, as multiples of theory**, so 1.00 / 1.00 is a perfect match. A sag "
            "under 1 reads too stiff, and a break load over 1 reads too strong.\n\n"
            "**Held** is the path a real strength check takes: a pad under each support, every voxel in it pinned. **Alone** "
            "takes the supports out: by symmetry, half the beam is a cantilever from mid-span with half the load on its end. "
            "**Check's voxels** is the size the check would pick for this coupon, coarser on a long strip because of its "
            "voxel limits. **4 across** and **6 across** put that many voxels across the thinnest side, the first being what "
            "the check gives a panel whose length doesn't limit it.\n\n"
            "| Coupon | Load lb | Theory sag mm | Theory break lb | Check's voxels mm (across) | Held, check's voxels | "
            "Held, 4 across | Held, 6 across | Alone, 4 across | Alone, 6 across |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")
    lines = [f"| {r['name']} | {r['lb']} | {_mm(r['theory_sag_mm'])} | {r['theory_breaks_lb']:.0f} "
             f"| {r['check']['spacing_mm']:g} ({r['check']['across']:g}) | {_cell(r, 'check')} | {_cell(r, 'four')} "
             f"| {_cell(r, 'six')} | {_cell(r, 'alone_four')} | {_cell(r, 'alone_six')} |" for r in rows]
    fit = [r for r in rows if r["id"] != "2x4-E"]             # depth is the thinnest side, so the voxels fit it exactly
    a, z = _span(fit, "alone_six", "sag_mm", "theory_sag_mm")
    a2, z2 = _span(fit, "alone_six", "breaks_lb", "theory_breaks_lb")
    h, k = _span(rows, "four", "sag_mm", "theory_sag_mm")
    h2, k2 = _span(rows, "four", "breaks_lb", "theory_breaks_lb")
    rounded = [r for r in rows if r["check"]["spacing_mm"] * r["check"]["layers"] > 1.01 * by_id(r["id"]).depth]
    ch, ck = _span(rounded, "check", "sag_mm", "theory_sag_mm")
    bh, bk = _span(rounded, "check", "breaks_lb", "theory_breaks_lb")
    tail = ("\n\n## What it says\n\n"
            f"- **The solver is close when the supports are out of the way and the voxels fit the depth.** At 6 across, alone, "
            f"sag is {a:.2f} to {z:.2f} of theory and the break load {a2:.2f} to {z2:.2f} times theory (leaving out the 2x4 "
            "on edge, whose depth isn't a whole number of voxels). whittle's own notes expect this element to read 5 to 20% "
            "stiff.\n"
            f"- **Held the way the check holds a part, the strip acts clamped at both ends.** At 4 across, sag is {h:.2f} to "
            f"{k:.2f} of theory and the break load {h2:.2f} to {k2:.2f} times theory. A beam truly clamped at both ends is "
            "0.25 and 2.00. Any support a voxel wide or more stops the end from turning. The short PETG bar reads further off, "
            "probably because the pinned pads take up a large share of its span.\n"
            f"- **A depth that isn't a whole number of voxels is rounded up.** The voxels at the check's own size make a strip "
            f"deeper than it is (`layers` in the JSON), and it reads stiffer and stronger again: sag {ch:.2f} to {ck:.2f} of "
            f"theory, break load {bh:.2f} to {bk:.2f} times theory, on the {len(rounded)} coupons long enough that the check "
            "picks that coarser size. A real panel short enough to get 4 across exactly doesn't have this.\n"
            "- **Where that reaches a verdict.** A sheet the check finds resting on other pieces all round, on two opposite "
            "edges or on a ring also gets the plate or beam check, which is this theory, and the lower number governs. Anything "
            "else has the FEA alone (a sheet on `held()` patches, or on one or three edges, an outline that isn't a rectangle "
            f"or disc, sticks, printed parts), and where it bends between its holds it can read {h2:.1f} to {k2:.1f} times too "
            "strong if the real support lets the end turn. #217 tracks that. Nothing here changes a verdict.\n"
            "- **The printed rows are one model.** The check has one set of values for a print, whichever way it was laid "
            "down, at Caliper's default walls and infill.\n"
            "- **Across-grain plywood is run here at half E and half strength**, so theory and whittle compare like with like. "
            "The real check's FEA has one stiffness and uses the along-grain values. Its plate check takes the across-grain "
            "one.\n")
    return head + "\n".join(lines) + tail


# ---------------------------------------------------------------------------
# The bench sheet
# ---------------------------------------------------------------------------
_STYLE = """
/* A test record: one printed page, ruled and dense, the look of a lab form */
:root { --paper:#fbfcfa; --ink:#1b211d; --soft:#56605a; --rule:#aab3ad; --tint:#e7ece8; --mark:#b5481f;
        --body:"IBM Plex Sans Condensed","Arial Narrow",Arial,sans-serif;
        --num:"IBM Plex Mono",Menlo,Consolas,monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --paper:#171c19; --ink:#e7ece8; --soft:#a4aea8;
        --rule:#4d5751; --tint:#262d29; --mark:#ef8a5e; color-scheme:dark } }
:root[data-theme="dark"] { --paper:#171c19; --ink:#e7ece8; --soft:#a4aea8; --rule:#4d5751; --tint:#262d29;
        --mark:#ef8a5e; color-scheme:dark }
@page { size: letter portrait; margin: 0.35in; }
@media print { :root, :root:not([data-theme="light"]), :root[data-theme="dark"] { --paper:#fff; --ink:#000; --soft:#333;
        --rule:#777; --tint:#eee; --mark:#000; color-scheme:light } .sheet { padding:0 !important; max-width:none !important } }
* { box-sizing:border-box }
body { background:var(--paper); color:var(--ink); font:10px/1.24 var(--body); margin:0 }
.sheet { max-width:7.8in; margin:0 auto; padding-block:12px; padding-left:max(16px,env(safe-area-inset-left,0px));
         padding-right:max(16px,env(safe-area-inset-right,0px)); display:grid; gap:7px }
h1 { font-size:19px; line-height:1; margin:0; text-wrap:balance }
header { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; border-bottom:2px solid var(--ink); padding-bottom:4px }
header p { margin:0; color:var(--soft); flex:1 1 300px; min-width:0 }
h2 { font-size:10px; letter-spacing:.07em; text-transform:uppercase; margin:0 0 2px }
.top { display:grid; grid-template-columns:minmax(0,1.04fr) minmax(0,1fr); gap:10px }
.ways { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,2.3in),1fr)); gap:4px 12px }
ol, ul { margin:0; padding-left:14px; display:grid; gap:1px }
svg { width:100%; height:auto; display:block; max-width:100% }
svg text { fill:var(--ink); font:10px var(--body) } svg .s { fill:none; stroke:var(--ink); stroke-width:1.4 }
svg .t { fill:var(--tint); stroke:var(--ink); stroke-width:1.2 } svg .m { fill:none; stroke:var(--mark); stroke-width:1.2 }
svg .mt { fill:var(--mark); font-weight:600 }
.safe { border:1.5px solid var(--mark); padding:3px 6px }
.safe b { color:var(--mark) }
.wrap { overflow-x:auto }
table { border-collapse:collapse; width:100%; font:inherit }
th, td { border:1px solid var(--rule); padding:1px 3px; text-align:left; vertical-align:top }
th { background:var(--tint); font-weight:600; font-size:9.5px; line-height:1.1 }
td.id { white-space:nowrap }
td.n { font-family:var(--num); font-size:9.5px; white-space:nowrap; font-variant-numeric:tabular-nums }
.rec td { height:19px }
.note { color:var(--soft); margin:0 }
"""

_RIG = """<svg viewBox="0 0 330 138" role="img" aria-label="A strip resting on two round supports, a bucket hanging from a strap at the middle, a thread stretched between pins over the supports and a rule at mid-span">
<circle class="t" cx="46" cy="55" r="7"/><circle class="t" cx="284" cy="55" r="7"/>
<path class="s" d="M36 62h20l4 22H32zM274 62h20l4 22h-28z"/>
<rect class="t" x="16" y="38" width="298" height="10"/>
<rect class="s" x="156" y="33" width="18" height="5"/>
<path class="s" d="M157 33v28M173 33v28M165 61v8"/>
<path class="s" d="M151 74h28l-3 34h-22zM151 74c4-11 24-11 28 0"/>
<text x="165" y="96" text-anchor="middle">load</text>
<path class="m" d="M46 22v16M284 22v16M46 24H284"/>
<rect class="t" x="183" y="10" width="7" height="38"/>
<text class="mt" x="195" y="17">rule: read it at the thread</text>
<text class="mt" x="52" y="17">thread on pins</text>
<path class="s" d="M46 118H284M46 113v10M284 113v10"/>
<text x="165" y="131" text-anchor="middle">span: centre of support to centre of support</text>
<text x="150" y="66" text-anchor="end">saddle and strap</text>
<path class="s" d="M6 43h6M9 38v10"/><text x="0" y="33">depth</text>
</svg>"""


def _lb(v: float) -> str:
    return f"{5 * round(v / 5):.0f}"


def _in(mm: float) -> str:
    return f"{mm / IN:g}"


def _read_with(c: Coupon, sag: float) -> str:
    return "rule or dial" if sag >= RULER_MM else "dial, or skip sag"


def floor_gap_in(c: Coupon) -> int:
    """How far above its catch the load hangs, in whole inches: twice the sag at the predicted break (real wood goes
    further), or at the top step where the sheet doesn't ask for a break. Never under two inches."""
    sag = theory(c, theory(c)["breaks_lb"] if c.breaks else c.steps[-1])["sag_mm"]
    return max(2, math.ceil(2 * sag / IN))


def _break(c: Coupon, t: dict) -> str:
    if not c.breaks:
        return f"no, it takes {_lb(t['breaks_lb'])}+ lb"
    return f"yes, at {_lb(t['breaks_lb'])}+ lb"


def sheet_html() -> str:
    rows = []
    for c in COUPONS:
        t = theory(c)
        rows.append(f"<tr><td class=id><b>{html.escape(c.id)}</b></td><td>{html.escape(c.name)}: {html.escape(c.how)}</td>"
                    f"<td class=n>{_in(c.span)} in</td>"
                    f"<td class=n>{' / '.join(str(s) for s in c.steps)}</td>"
                    f"<td class=n>{t['sag_mm']:.1f} mm</td><td>{_read_with(c, t['sag_mm'])}</td>"
                    f"<td class=n>{floor_gap_in(c)} in</td><td>{_break(c, t)}</td></tr>")
    blank = "<tr>" + "<td></td>" * 14 + "</tr>"
    return f"""<title>Coupon Bend Test</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans+Condensed:wght@400;600;700&display=swap">
<style>{_STYLE}</style>
<div class="sheet">
<header><h1>Coupon bend test</h1><p>A strip on two supports, loaded in the middle. Caliper will compare what you read here with what it predicted for the same strip (issue #42).</p></header>
<div class="top">
<div>{_RIG}</div>
<div><h2>Each coupon</h2><ol>
<li>Measure its width and depth at mid-span, and the span. Weigh it if you can.</li>
<li>Tape or screw two round supports, 1 in pipe or dowel, to sawhorses or a bench so they can't roll. Rest the strip loose on them, so its ends can turn and slide.</li>
<li>Hang the load from a strap over a 1 in wood saddle at the middle, the table's floor gap above a block or pad. If the load touches down before the strip breaks, the numbers are bad: redo it with more gap.</li>
<li>Hang the empty hanger, about 5 lb, and zero the sag reading there. The sag steps count what you add above it.</li>
<li>Go to each of the three load steps. Wait 30 seconds and read the sag. The steps are targets: write what you actually hung.</li>
<li>Back off to the empty hanger. The reading should come back near zero. If it doesn't, something slipped or crushed: redo it.</li>
<li>Where the table says to break it, stop reading sag and add load in small steps from the side, at arm's length. Write the most it held, <b>which includes the hanger and strap</b>, and how it broke. If you run out of load, write "held N, didn't break".</li>
</ol></div>
</div>
<div class="safe"><b>Safety.</b> Eye protection, gloves and closed shoes. Brace or weigh the horses so they can't tip when one end kicks. Near the break, no hand or foot under the load, and never lean over the strip. A snapped strip pivots on its supports and the ends whip up: stand beside it, never in line with either end, and keep people and pets out. Every strap, hanger and scale must be rated above the most you'll hang; luggage scales often stop near 110 lb. With a ratchet strap, keep your face out of its line: a stretched strap can throw the scale. Bagged concrete is 60 to 80 lb, so lift it with care. Nobody stands on a coupon.</div>
<div class="ways">
<div><h2>Loading: use what you have</h2><ul>
<li><b>Sand or gravel in buckets</b>, weighed before you hang them. Two part-full buckets are safer than one full one.</li>
<li><b>Bathroom scale:</b> weigh each bucket on it. Holding a bucket and subtracting yourself is too coarse for 4 and 5 lb steps: use a kitchen or luggage scale there. Or put one support on a board on the scale, note the reading with the strip resting, and as you load take twice the rise. It can't be zeroed with the strip on it, and many digital ones won't follow a slowly rising load, so check yours does first.</li>
<li><b>Weights or bagged concrete</b> on a hanger board.</li>
<li><b>Hanging scale and ratchet strap</b> to a floor anchor: the scale reads the load directly.</li>
</ul></div>
<div><h2>Reading the sag: from a reference on the supports</h2><ul>
<li><b>Dial indicator</b> clamped to a straight bar that rests on the strip over the supports, tip on the strip beside the saddle. Not on a stand on the floor: that counts crush and the horses' flex.</li>
<li><b>Rule and thread:</b> stretch a thread tight between two pins in the strip, over the supports. Tape a steel rule upright at mid-span, and read it where the thread crosses, at eye level, to 1/64 in or 0.5 mm.</li>
<li><b>No dial for PETG?</b> A rule can't read 1 mm. Skip the sag and just break it: the most it held is still worth having.</li>
</ul></div>
</div>
<div><h2>Coupons</h2><div class="wrap"><table>
<tr><th>ID</th><th>What to cut or print</th><th>Span</th><th>Load steps, lb</th><th>Sag at top step</th><th>Read with</th><th>Floor gap</th><th>Break it?</th></tr>
{''.join(rows)}
</table></div></div>
<p class="note"><b>2x4 on edge:</b> a loose block each side at each end keeps it upright without gripping it. <b>PETG:</b> test all three bars on their 1 in face, 1/2 in deep, however they printed. For the 6 in span, clamp two 2x4s flat across two sawhorses set 18 in apart, 5 in clear between the 2x4s. Tape a dowel along each inside edge, rest the bar across the dowels, and hang the load down through the gap, between the horses. It has to carry about 100 lb. <b>Sag and break</b> are predictions from the textbook values Caliper uses today, at its default print settings (1.2 mm walls, 20% infill). Real wood often beats them by a lot, and finding out by how much is the point. Most 3/4 ply is 23/32 and most 1/2 ply is 15/32, so expect more sag and a lower break than these; the comparison uses the depth you measure. Three of each kind beats one. PETG may fold instead of snapping. Printed: note layer height, walls, infill and pattern, filament, nozzle temperature. Wood: note knots near the middle, and moisture if you have a meter.</p>
<div><h2>Record: load in lb, sizes and sag in mm or in (say which). Copy this page for more rows</h2><div class="wrap"><table class="rec">
<tr><th>ID</th><th>#</th><th>Width</th><th>Depth</th><th>Span</th><th>Load 1</th><th>Sag 1</th><th>Load 2</th><th>Sag 2</th><th>Load 3</th><th>Sag 3</th><th>Back to</th><th>Most it held</th><th>How it broke, and where</th></tr>
{blank * 5}
</table></div></div>
</div>
"""


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Write the coupon bench sheet and the theory-against-whittle table (#42).")
    ap.add_argument("--out", default="pm/bench")
    ap.add_argument("--fea", action="store_true", help="also run whittle on every coupon: a few minutes")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "coupon-sheet.html"), "w") as f:
        f.write(sheet_html())
    if args.fea:
        rows = measure()
        with open(os.path.join(args.out, "theory-vs-whittle.json"), "w") as f:
            json.dump(rows, f, indent=1)
            f.write("\n")
        with open(os.path.join(args.out, "theory-vs-whittle.md"), "w") as f:
            f.write(table_md(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
