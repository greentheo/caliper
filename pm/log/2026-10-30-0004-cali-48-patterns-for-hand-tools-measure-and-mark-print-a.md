### 2026-10-30 · CALI-48 (#4), first slice · Patterns for hand tools: measure and mark, print and tape, project and trace
- **Theo:** "a cut plan with a jig saw is important. CNC is great, but most people operate with hand tools.
  We need plans that can be laid out by ruler and pencil, or maybe projected with a projector and traced or
  printed or something like that."
- **`patterns.py`:** every flat sheet piece of a part (holes and all), in its own plane with its longest edge
  along the bottom and its corner at (0, 0), three ways:
  - **Measure and mark** (`measure-and-mark.pdf`): a landscape page per piece on a 1 in grid, numbered from
    the bottom-left corner, overall dimension lines, the corners of anything that isn't a plain rectangle,
    and each hole's position and size from the two square edges ("H1: 1 1/2 in from the left, 1 1/2 in up;
    11 7/16 in wide, 6 in tall… drill a 3/8 in hole inside the line to start the jigsaw").
  - **Print and tape** (`print-full-size.pdf`): full size on letter pages, portrait or landscape (whichever is
    fewer), 1/2 in overlaps shaded grey, the 1 in grid to line pages up, a label on each ("page A2 (2 of 2) ·
    overlaps …"), a 3 in ruler in every top margin to check it printed at 100%, and a map page per piece.
  - **Project and trace** (`project-<piece>.svg`): full size in real inches, white on black, with a 4 in
    calibration square to zoom the projector to.
  Pages are Pillow rasters at 150 dpi saved as PDF with their resolution, so they print at true size with no
  PDF library (every page is 612 × 792 pt). A 1/4 in border pushed a 14 1/2 in panel onto a third, nearly
  empty page; it's 1/10 in now: the stool is 10 printed pages, two a piece.
- **In the app:** *Patterns for hand tools* comes before the CNC cut plan under *Built from*, with links and
  thumbnails; it's on the Studies page. **The build package** gets `hand/<part>/` with all three.
- Live on the stool (v3): 5 pieces, 15 pages with the maps.
- **Not yet in #4:** the shop itself (machines and stock as a design input), the printer, routing by machine.
- Tests: `test_patterns.py` (3: pieces lie flat, long edge down, holes in place; every printed page is
  8.5 × 11 in and the PDFs, SVG and history are right; nothing flat, no patterns) and `hand/` in the release.
  **Full suite (over #2 and #4): 486 passed.**
- Commit: `92248f0`, PR #37 (stacked on #36).
