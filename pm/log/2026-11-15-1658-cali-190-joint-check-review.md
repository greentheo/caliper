### 2026-11-15 · CALI-190 (#301) · #311 review: a push along a member bears where it pushes; the splay thrust into the tie; a bevel's thread; the words, case by case

The reviewer's review of #311, with the foreman's rework list. Theo's five values are unchanged, still `pending: Theo`.

1. **A push along a member bears where it pushes** (`_route`).
   - **The bug:** the first pass split a piece's whole force between its joints by the lever rule. So a push along a rail went half to each end, and one end was pulled out of its edge at 0.0×. On v7, "standing on the top" with 1% sideways read 0.0×.
   - **Now,** each component, axis by axis, goes to the joints the piece bears into in that direction, by the lever rule. Where it bears nowhere, it goes across the joints that can take it in shear. Only where neither can is it withdrawal.
   - **A piece is held up only by pieces no farther from what holds the part than itself.** Otherwise a top read the shelf's other hanger, which hangs from it, as holding it up.
   - **On v7:** down, 1% sideways and 10% sideways all read 5.75×, the reviewer's number; 10% front to back reads 5.73×.
   - **A genuine withdrawal still fails:** a shelf hung from two hangers by screws in their edges is ✗ 0.0×, "two #8 screws pulled out of the …'s edge".
2. **The splay thrust** (#301's "a splayed side adds a thrust at its foot: load × tan(splay)").
   - **Its top:** a side leaning more than 2° off vertical takes its load down its own line. On a 10° stool its top edge bears 250 / cos 10° = 254 lb, all of it in bearing.
   - **Its foot:** the foot pushes out by load × tan(splay), about 44 lb a side, into the tie nearest the foot. A tie is a piece joined to both splayed sides that didn't bring the load down: the step on top holds the tops; it doesn't tie the feet.
   - **A butt stringer** takes it as withdrawal from its edge and fails, named: rule 4's point.
   - **No tie:** "not checked by hand: nothing ties its splayed sides".
   - v7's sides stand upright, so nothing there changes.
3. **A bevel's screw is credited only the thread that stays in the wood.** There's one rule, `marks.thread_in`: the book's "comes out … use shorter ones" and the check both read it. At 30° the 2 in screw keeps 3/4 in in the wood: 135 lb, not 180. Square and at 10°, it's unchanged at 180. Bevels from 17.5° to 48.6° gain the book's "use shorter ones" line with the 2 in screw (the reviewer's table).
4. **The words, case by case** (`verdicts.wood_brace(run, c)`):
   - **The badge counts what that case left unchecked:** "1 joint not checked by hand".
   - **A case whose path can't be followed** counts all its joints ("8 joints not checked by hand") and says why once: "not checked by hand: its load path isn't a simple chain".
   - **A part with no joint the check can place** keeps today's words exactly ("joints not checked"; "the check takes its 8 joints as solid wood").
   - **The record keeps them apart:** a case's reason is `joints_unchained`, never a joint's name.
   - **A Lighten step** reads its own cases' joints.
   - **The station bar** names the joint that decides it, never "the FEA's peak".
5. **`holed_buckling`'s `JC.lower` is pinned:** buckling governed, its holes leave no wall checked, and the joint is lower than what it took over from.

**Sources:** the exact rows behind the constants are quoted on #301 (issuecomment-6903134071), because the reviewer's E830 PDF gave no text: E830 Table 6, Y510 Table 3 and its footnote, NDS Table 12L's 3/4 in #8 row (69 lb at G 0.42), the Commentary's "about 1/5 of maximum tested", NDS §12.2.2.3 and the PDS bearing line.

**CI:** `test_scrub_sweep` failed on `"unchecked": [str(e)]`, raw exception text headed for a person. That was the code's fault: `NotChain` carries its own sentence as `why`, and that's what's said. My around runs had missed it because my list of the tests that scan the source was missing four (`test_scrub_sweep`, `test_closed_everywhere`, `test_cut_before_compare`, `test_verdicts`). The list is now built from the tests that scan `src`: 28.

**Tests:** `tests/test_joint_check.py` has 42 tests now (it had 26):
- a push along a member, and a shelf hung from screws in edges;
- a splayed stool with a stringer, and one without;
- a bevel at 0°, 10° and 30°;
- `holed_buckling`;
- the words, case by case: not a chain, none placed, the count, the bar, the page once;
- a case's verdict and a Lighten step reading their own cases' joints;
- a push that slides on one joint before it pulls another.

**Mutants:** 21 on the rework, all caught; one ("no slide") survived until the push-away pin. The first pass's 22 are re-checked, 3 at their moved lines: all caught.
