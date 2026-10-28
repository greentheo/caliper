# Caliper — the design ⇄ optimize ⇄ make loop (M6)

**Status:** draft for Theo to redline · 2026-10-28 · follows `caliper-conversational-spec.md` (M4)

## Why

Caliper's promise is: *you give it the specification and the constraints; it does the rest and shows you
the measurements.* On the hitch camper that turned out to mean three activities that today are separate
trades with people in the loop at every hand-off:

| activity | tools today | what it answers |
|---|---|---|
| **design** | Caliper (LLM-authored CadQuery, measured) | is it the shape and size the spec says? |
| **optimize** | whittle (drag, frame + walls, soon plates); Caliper's weight & balance | is it the best shape for drag, steel, hitch load? |
| **make** | unfold-to-sheets (cut plans); cnc-plasma-nesting; (soon) a slicer | can *this shop* make it, from what stock, in what order? |

In the CALI-39…45 run those three were joined by hand: a Claude session ran scripts between the panels —
layout comparisons, an exhaustive tube search, fixing experiments, the strip-built bands — and the PM log is
the only record of why. M6 makes that loop Caliper's own job, with Theo in it at a few deliberate gates.

## The pieces

### 1. The scorecard (first)
Every requirement compiles to something measured, at the design level:

- **checks** — must hold: `mattress fits`, `bumper_clearance >= 2 in`, `frame safety >= 3.3x`,
  `every piece fits a machine`;
- **objectives** — to push on, with a direction and a weight: drag, steel lb, hitch lb·in, sheets, cost;
- **trust** — each number says how good its model is (whittle drag ±30%; PMF stiffness a guess; FEA as
  conservative). A number is never shown without it.

One panel on the design page: every check ✓/✗ with its margin, every objective with its value and trend
across revisions. Assertions (CALI-30) are the checks that already exist; the scorecard is them plus the
studies' outputs plus the shop's.

### 2. The shop
A design input beside the requirements, saved per user (reused across designs):

```yaml
machines:
  - {id: plasma, kind: plasma, bed: [48, 48] in, plate_max: 3/8 in, kerf: 0.06 in, materials: [steel]}
  - {id: router, kind: router, bed: [48, 96] in, bits: [1/4 in], materials: [plywood, xps]}
  - {id: printer, kind: fdm, volume: [256, 256, 256] mm, materials: [PETG, PLA]}
hand: [hot wire, knife, rasp, spray foam, welder (MIG)]
stock: {plywood: [4x8 ft 3/8, 1/2], xps: [4x8 ft 1 in], steel_tube: [20 ft], plate: [2x4 ft 3/16]}
```

It turns manufacturability into checks (a piece fits the bed; plate within the table's thickness; foam
folds within its limit; a printed part fits the volume) and routes the cut plan: each piece goes to the
machine that makes it — plasma DXF (or G-code via cnc-plasma-nesting), router DXF, printer STL + slicer
estimate, hand-work list.

### 3. Moves
Every tool behind one interface, so the loop can pick any of them:

```
move.run(design, inputs) -> record   # numbers + files, scored against the scorecard
move.adopt(record)       -> revision # a new, still-parametric revision, measured like any other
```

Already shaped like this: drag study, frame study, construction what-ifs, cut plan. To add: plate mode
(whittle), nesting (cnc-plasma-nesting), slicing, layout variants as first-class options, and the
"author/revise a part" turn itself.

### 4. The loop runner
Given the scorecard, Claude proposes the next move, runs it, measures, keeps or reverts — within a budget
(time, builds, tokens) — and journals each step with its scorecard delta and the reason ("riser under the
front wall: −17 lb steel, safety 3.3 → 3.57"). The journal *is* the design's history; the PM log stops
being the only record.

### 5. Gates — where Theo is in the loop
1. **Requirements + shop** — confirmed up front (the clarify round, extended).
2. **Trade-offs** — when the scorecard has a real choice (layout, skin, how much volume to give for drag),
   a small frontier with a recommendation; Theo picks.
3. **Release to cut** — nothing goes to a machine until the build package for that exact revision is
   reviewed: sheets per machine, cut list, shopping list, assembly order, the scorecard at release.

Never silent: relaxing or retiring a requirement is always a proposal (as `hatch_clearance` was).
Everything between gates runs without asking.

### 6. The build package
A released, versioned bundle per revision: per-machine files, cut list with end cuts and bevels, BOM and
shopping list, assembly drawing and order, and the scorecard as released.

## Cards

- **CALI-47 — Scorecard** · P0 · M6 — checks + objectives + trust, one panel; studies report into it.
- **CALI-48 — The shop** · P0 · M6 — machines + stock as input; manufacturability checks; per-machine routing
  of the cut plan (plasma via cnc-plasma-nesting, router DXF, printer STL + slicer).
- **CALI-49 — Moves** · P1 · M6 — one interface over design/optimize/make tools; layouts and BUILD
  what-ifs as options.
- **CALI-50 — The loop runner** · P1 · M6 — propose → run → measure → keep/revert, budgets, journal, gates.
- **CALI-51 — Build package** · P1 · M6 — release a revision to the shop.
- **Housekeeping before CALI-50:** commit/pin whittle's frame-study work; merge `cali-31-design-ui` /
  `cali-39-parametric-aero`; pin unfold-to-sheets by commit.

## Open questions for Theo

- Which gates, exactly — are three right? (e.g. a gate before any shape change bigger than X%?)
- Budgets: how long may the loop run unattended (a drag study is ~40 min)?
- Cost as an objective — worth adding stock prices?
- The large printer: printed parts in the camper (nose caps? brackets?) as a test case for the printer path.
