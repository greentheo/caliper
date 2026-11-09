### 2026-11-01 · CALI-87 (#63) · The reviewer's correctness findings on the open stack, fixed
Stacked on #58 (which is on #62). One commit per finding, each with a test seen failing first.
- **1 (#57):** the printed rest was cached per version, not per what-if, so a 3/4 in what-if left the part as
  drawn with the what-if's sides. Now it's keyed on the declarations too. `1a8337a`
- **2 (#57):** every script writer (BUILD what-if, frame, gussets, drag, refine) now drops a carve through
  `carve.uncarve()` and says so. A picture or lightening on a carved part is refused, with the reason. `7c83d87`
- **3 (#57):** a carve of an older version isn't adopted (409). `b829d70`
- **4 (#57):** two test assertions that couldn't fail now can, and each was made to fail on purpose. `e21a9f6`
- **5 (#50):** "the right side" cut the left. A side named outright now wins over "side". `5fe022b`
- **6 (#50):** a NaN pad point is refused (422), and a failed picture job still logs a reply. `3bf812f`
- **7 (#49):** the cut sheet now cuts holes before outlines, in SVG and DXF (Caliper's driver; no
  unfold-to-sheets change). `bbd87b4`
- **8 (#49):** a pinned size (`==`, made a band by measuring allowance) is checked for conflicts again.
  `071a3a9`
- **9 (#52):** joints are keyed by piece, not by name. Two pieces both called "side" were 16 screws in the BOM
  and 22 in the kids' book; both now say 18. `720e5c7`
- **10 (#52):** the build book lists `kids.html` only when one was made. `2d593ee`
- **11 (#56):** a small filled box is caught by the share of solid in no piece (more than 10%), not just by
  the volume ratio. `54c9fe5`
