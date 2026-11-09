### 2026-11-01 · CALI-86 (#62), #71 rework · The reviewer's review of findings 8–13, worked
The foreman's ten items. New commits only; the reviewed ones keep their hashes.
- **2 (rule 6):** a live test that broke below what the part must hold, or sagged well out of the predicted
  band, outranks the prediction. The part card loses its ✓ lines, and the design's strength checks read the
  test: "It broke at 150 lb in your test. We predicted it would hold 400." `57e9568`
- **3, 4, 7:** every step is judged and the worst governs (closes #70 #1). Each edge is pinned by a test. A
  break within 10% of the prediction matches it; short of that is "our check was too hopeful"; a low sag is
  "stiffer than our check said". `c88a047`
- **1:** the promise follows only strength and frame verdicts (`rests_on_model`), and goes in the first-run
  reply and `chat._facts`. `56e7eeb`
- **5, 6:** "about" follows the printed model where it governs (`load_study.rough`); a plywood-governed verdict
  keeps plywood's words. The top line is "Holds a foot, about 2.6 times over.", with the caveat by the promise.
  "About" is also on the carve reply and the release table. `2f59997`
- **8:** an old carve run says "of the whole solid (carved before CALI-86 …)", never relabelled. `a59f9f4`
- **9, 10:** the chat turn isn't ok when the check couldn't run; each sample guard is tested alone; an unknown
  sample is a 404 with no path.
