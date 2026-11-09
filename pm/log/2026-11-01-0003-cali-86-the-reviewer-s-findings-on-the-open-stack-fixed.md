### 2026-11-01 · CALI-86 (#62), findings 8–13 · The reviewer's findings on the open stack, fixed (part 2)
Stacked on findings 1–7. One commit each, each with a test seen failing first.
- **8 (#57):** "% carved away" counted the plywood the carve keeps: 30% was 46% of the print. Now it's the
  printed part's share, and labelled so. `663f332`
- **9 (#57, rule 6):** a printed part's verdict now says "about … (printed parts are a rough model)". `9aacd52`
- **10 (#50, rule 6):** with no strength check installed, a picture on a part with loads() got a ✓. Now it
  says it couldn't check, and isn't ok. `622c402`
- **11 (#51, rule 6):** breaking below what the part must hold is bad, breaking short of the prediction is warn,
  and a sag more than 2× outside the predicted range is warn, with words. `2c041c2`
- **12 (#43):** `open_sample("..")` copied the package folder. Now it takes only a listed sample's slug.
  `258fe5e`
- **13 (#43):** scorecard verdicts (the camper's "safe to tow" lines) now carry the promise. `0b21850`
