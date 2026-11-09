### 2026-11-01 · CALI-86 (#62), findings 1–7 · The reviewer's findings on the open stack, fixed
The reviewer's pass over #43–#57, checked by the foreman. One commit each, each with a test seen failing first.
- **1 (#57, rule 6):** a panel on two edges spread a foot over its whole width, so a 900 mm × 1/2 in panel over
  300 mm read 2.72× when a plate solution says 1.11×. Now it uses BS 8110's effective width (the load's width +
  0.6 of the span), which reads 31% high on 900 × 300 and 23% high on 450 × 300 against a Lévy plate series. That's
  the safe side, the owner's call. Every stool fixture's verdict is unchanged. `136a5ef`
- **2 (#57, rule 6):** the carve's headline was green ("still 8.4x") while the whole part was 0.66×. It now leads with
  "doesn't hold as it is" and isn't ok. `8c70418`
- **3 (#43):** a failed chat job was kept with the person's message, and a design's folder named it in tracebacks.
  Jobs are now kept by kind, and a design's name is written `designs/<design>`. `report()` looped forever on a long
  error; now it always stops. The dialog now says what the report really holds, and a job is marked failed only
  after its error is kept. `cccc696`
- **4 (#43):** `caliper sample save` with no name deleted every sample. A name must now be a plain slug. `6b998a2`
- **5 (#51):** one NaN test step broke the design's page. Steps must be real numbers more than nothing, and a bad
  line on file is skipped (the panel says so). `4f51df6`
- **6 (#52, rule 6):** the kids' book had a kid holding the work while the jigsaw ran. Now the grown-up clamps,
  cuts and drives the screws, and the kid stands back in safety glasses. `b3def7e`
- **7 (#50):** the left side's pattern was mirrored. Patterns are now drawn from the outside face, turned rather
  than flipped, and each page names the face. `06092c7`
