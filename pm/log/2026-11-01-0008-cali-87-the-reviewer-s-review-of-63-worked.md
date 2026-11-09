### 2026-11-01 · CALI-87 (#63), #75 rework · The reviewer's review of #63, worked
New commits only, on `cali-87-correctness`.
1. A regression from finding 9: the kids' book crashed when certain pieces shared a name (8 of 26 ways), and
   the package shipped without it. The chosen piece is now taken out by identity, and all 26 make a book with
   18 screws. `edc63e0`
2. A kids' book that fails is said in the package's notes and kept for a report. `cb45cae`
3. Pages tell same-named pieces apart: drawings by key, "the first side" / "the other side", "touches both
   sides". `23e9025`
4. A filled box caught by its core reports the core share against 10%. `21cf8f3`
5. A lightening study is adopted only onto its own version (409). `64d1b6b`
6. A chat turn that fails still answers in the log. `d492d90`
7. The carve refusal names "roll it back". Lightening a carved part is refused before the study runs.
   `5314c0f`
