### 2026-11-11 · CALI-92 (#70) · The reviews' robustness and small-words findings

The first of #70's two PRs: items 11, 12, 13, 15, 16, 18, 19 and 22. Items 8 and 9 landed with #211. The strength and measurement items (2, 3, 5, 6, 7, 17) and the rest (10, 14, 20, 21, 23, 24) are still to come.

- **11.** The classic assembly page measures under the OCCT lock.
- **12.** Errors recorded at once are all kept: a lock, and each writer its own temporary file.
- **13.** No "Say it simpler" button without a key, because simpler words need Claude.
- **15.** A panel's glue line comes from its material: foam gets foam-safe adhesive, and anything else unknown gets none named.
- **16.** A report too long for a link keeps the line that failed, cutting the trace from its start as the server does.
- **18.** A job's live error goes through the report's scrub. A failed chat turn's reply is the plain sentence with the error's id. `samples.save`'s two renames stay, with the reason said.
- **19.** A goto line reaches its panel from either view, selecting the part if there's one to select. Otherwise it isn't drawn as a link.
- **22.** Only a body really cut to fit the bed is pinned. Two sides simply apart are two pieces.

The whole suite is CI's.
