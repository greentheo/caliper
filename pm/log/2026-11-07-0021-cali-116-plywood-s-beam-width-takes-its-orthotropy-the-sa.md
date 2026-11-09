### 2026-11-07 · CALI-116 (#118) · Plywood's beam width takes its orthotropy, the safe side
- **`load_study.beam()`** scales the effective width under a foot by `orthotropic(mat)` = (D_across / D_along)^¼ (the
  material's `E_across` if given, else its strength ratio across; 0.841 for ply) when the face grain runs along the
  span, the edge's share too, never past the panel's width (BS 8110 cl. 3.5.2.2(b)). `width_along_mm` and
  `orthotropic` are on the record. The grain's way unknown, `safety_across` (the verdict) is the worse of the two.
- **The `why` says so,** and the page's Load panel shows a two-sided top as a **Beam check** with its `why`, not "held all
  round, edges free to turn" (design.js v=53).
- **Before → after** (the plate numbers; the FEA and every verdict unchanged, since the verdict already took the grain
  across the gap at half strength):

  | fixture · case | width (mm) | grain along the span | verdict |
  |---|---|---|---|
  | test stool · front edge | 206.7 → 173.8 | 2.37 → 1.99 | 1.19 ✗ → 1.19 ✗ |
  | test stool · middle | 254.0 → 238.5 | 2.91 → 2.74 | 1.46 ✗ → 1.46 ✗ |
  | MIXED · front edge | 190.0 → 159.8 | 1.15 → 0.97 | 0.57 ✗ → 0.57 ✗ |
  | MIXED · middle | 220.0 → 210.2 | 1.33 → 1.27 | 0.66 ✗ → 0.66 ✗ |

  The greener number was the advice: "cut with its face grain running across the gap and it's about 2.4 times over"
  for the test stool's front edge is now 2.0.
- **NEEDS ENGINEER CHECK:** the factor (#42: or b_ef = M_beam / m_plate, or let the plate check govern).
- `tests/test_orthotropic.py` (7; six fail on main).
- **Merged forward onto main's one verdict (#132):** the plate or beam check gets its own verdict on the server
  (`verdicts.meets` of its worse-grain number against the run's need, only where the case is settled: never green on
  a not-trusted, unresolved or older case), and the Beam check panel takes its colour and word from it. Before, the
  panel's number was plain bold. No number moves. Both guards pass.
- **#122 review:** pinned that no plate or beam number reads green on a case that isn't settled (too coarse, or an
  older version): it reads as its case does, and dropping the guard fails the test. Merged main (#139): the panel's
  plate line is one expression with the beam, the ring and the rectangle, each with its number in its verdict's colour
  (`plNum`). The sag beside "grain unknown" is the worse grain's (`beam`'s `sag_worse`: along the span its own E on
  the narrower width, across it its stiffness across on the whole width): for ply, half as stiff across, so twice
  the isotropic sag where that governs. `test_beam_width`'s sag reads the same.
- **The worse-grain sag moves the real test's verdict** (`trials.predict` takes the plate or beam sag as the top of
  the predicted range, at read time, so a recorded test re-judges). Before → after, for ply on two sides (the centred
  foot, top of range 2.62 → 5.24 mm at the check's load):

  | a test's sag at that load | before | after |
  |---|---|---|
  | 6 mm (2.3× the old top) | "it sagged more than we predicted" (warn) | within the prediction (ok) |
  | 12 mm (4.6× the old top) | "it sagged more than we predicted" | "it sagged more than we predicted" |

  Honest while the grain is unknown: the prediction spans both grains. **Where a plate says its grain** (`"grain":
  "along"` or `"across"`), the prediction takes that grain's sag (`deflection_along_mm` / `deflection_across_mm`, now
  on the beam's record), pinned. Nothing declares a grain yet: a piece's `construction()` has no grain key, so today
  it's always the worse grain's. Theo has no recorded tests.
- **#122 review, round 3:** `plNum`'s "(word)" pinned: an unsettled plate or beam number says its verdict's word ("3x (not resolved)"), a settled one never does.
