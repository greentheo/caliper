# Caliper — the design ⇄ optimize ⇄ make loop (M6)

**Status:** draft, Theo's first redlines in (§5, §7) · 2026-10-28 · follows `caliper-conversational-spec.md` (M4)

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

### 0. The quadfecta
What the loop balances, all at once: **design** (it is what the spec says), **optimization** (strength,
mass, aerodynamics), **manufacturability** (this shop can make it from this stock), and **cost and waste**
(what the stock costs, and how much of it ends up as offcut). The scorecard carries all four.

### 1. The scorecard (first)
Every requirement compiles to something measured, at the design level:

- **checks** — must hold: `mattress fits`, `bumper_clearance >= 2 in`, `frame safety >= 3.3x`,
  `every piece fits a machine`;
- **objectives** — to push on, with a direction and a weight: drag, steel lb, hitch lb·in, **cost** (stock
  bought, at prices the user can correct), **waste** (bought minus used — offcut area and length, and its
  cost);
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

### 5. Gates are constraints — the user's, and the ones Caliper finds
Theo's redline: gates are hard to prespecify. Rather than fixed stopping points, **the user states their
gates as constraints, in their own words** — "don't take more than 15% of the volume", "no wall thinner
than 1/8 in", "it has to hold a twin mattress", "stop and show me before you change the shape much" — and
Caliper compiles each into a check, an optimizer bound, or a pause. whittle's minimum wall is the model:
a constraint the optimizer can't cross, not a meeting.

**Finding the crucial constraints is part of the job.** On the camper the one Theo didn't think of first was
that the base had to take a twin mattress. That kind of constraint is discovered, and then it's iteration.
So before spending compute, Caliper asks what the design must hold, fit, clear, or be made with — from the
domain ("a camper: who sleeps in it? what goes in it?"), and from what a first rough pass reveals. Ideally
that happens before optimization; sometimes it only shows up after, and then it's a new check and a re-run,
recorded as such.

Never silent: relaxing or retiring a requirement is always a proposal (as `hatch_clearance` was), and
release to cut is always the user's.

### 6. Budgets
The loop's unattended time defaults to **10 minutes**, and the user can set it ("I'll check back in an
hour"). Caliper plans back from the limit: a rough first pass spends little (coarse drag, quick sizing);
once the design and constraints are dialed in, longer runs (a 40-minute drag study, a full plate sweep) are
worth it. Every run says what it spent.

### 7. The build package
A released, versioned bundle per revision: per-machine files, cut list with end cuts and bevels, BOM and
shopping list, assembly drawing and order, and the scorecard as released.

## Cards

- **CALI-47 — Scorecard** · P0 · M6 — checks + objectives + trust, one panel; studies report into it.
- **CALI-48 — The shop** · P0 · M6 — machines + stock as input; manufacturability checks; per-machine routing
  of the cut plan (plasma via cnc-plasma-nesting, router DXF, printer STL + slicer).
- **CALI-49 — Moves** · P1 · M6 — one interface over design/optimize/make tools; layouts and BUILD
  what-ifs as options.
- **CALI-50 — The loop runner** · P1 · M6 — propose → run → measure → keep/revert, budgets, journal, gates.
- **CALI-51 — Build package** · P1 · M6 — release a revision to the shop. ✅ v1 2026-10-28 (`release.py`):
  routes by material until CALI-48 knows the machines (steel plate → `plasma/`, sheet goods → `router/`).
- **Housekeeping before CALI-50:** commit/pin whittle's frame-study work; merge `cali-31-design-ui` /
  `cali-39-parametric-aero`; pin unfold-to-sheets by commit.

## Theo's answers (2026-10-28)

- **Gates:** user-specified, in colloquial terms, as constraints on the optimize side; Caliper works to find
  the crucial ones early (§5).
- **Budgets:** default 10 minutes unattended, user-set, planned backwards from the limit (§6).
- **Cost:** yes — and minimizing material waste with it (§0, §1).
- **The large printer:** printed parts in the camper (nose caps, brackets) as the printer path's test case.
- **First job for the loop runner:** the camper's 2x2 skeleton — a "box inside the box" where the front and
  back panels meet the floor and roof (posts only where the shell is flat), cross beams under the roof for a
  mild snow load, 1x1 ribs only if needed — searched over count, size and an inside skin, against weight and
  cost, under snow and driving.
