### 2026-10-30 · CALI-78 (#46) · A picture on it: a T-rex cut out of the side, and it still holds Dad
- Showcase 1 (#10): "a stool to reach the sink, with a T-rex on it". The kid's ask is the hook; the engineering
  question it raises is the story: can you cut a T-rex out of the side and still hold Dad?
- **`pictures.py`:** the picture comes from words or from the pad.
  - **Words:** a hand-drawn T-rex is built in (also "dinosaur"). Anything else, Claude puts together from simple
    shapes (ellipses, thick strokes, polygons), joined and smoothed into one silhouette. Asked to trace an outline
    point by point, its T-rexes came out unrecognisable and one crossed itself; built from shapes, its cat and its
    rocket came out right (its T-rex still didn't, hence the built-in one).
  - **The pad:** a drawing, screen y down.
  - **Where it goes:** a panel nobody stands on (the front, or the one named; "side" means left or right), upright
    and facing the way it was drawn as you look at it from outside, centred at the room's pole of inaccessibility,
    90% of as big as fits inside the 1.5 in rim and a web clear of any holes.
  - **Cuttable:** closed and opened at 1/8 in radius (nothing narrower than a 1/4 in blade turns round, no gap
    narrower), exterior only (no eye to fall out).
  - **Checked:** the strength check is tried with its cells taken out of the voxels (as the lightening study does);
    too weak, it shrinks by 0.8 up to five times, or says it can't and changes nothing.
  - **Cut:** written into `HOLES` with `"picture": "T-rex"`, so the patterns, the CNC sheet (CALI-77) and the
    rebuilt part's strength check see it. That check is the number the reply gives.
- **Lightening leaves it alone:** `holes.merge` marks picture polygons and `lighten.panels` keeps a web of wood round
  them, so a later study doesn't read the T-rex as a hole and redraw it as a blob; `lighten.adopt` keeps picture
  entries and replaces only the lightening holes (`holes.read`/`holes.write`, shared now).
- **From the chat:** a new route, `picture` ("put a T-rex on the side"). Claude routes it with the subject and the
  panel; offline it's taken only for a shape it can draw or one called a picture, so "add a foot on the bottom" is
  still a part. **From the page:** **🦖 Put a picture on it** under *What is it?* (a part, or a one-part design):
  say it (or 🎤), or draw it on the pad, pick the panel, **Cut it out**.
  `GET/POST /api/designs/{slug}/parts/{pid}/picture`.
- **Live (the sample stool, Claude routing):** "put a T-rex on the side" → "✓ I cut a T-rex 5.2 × 5 in out of the left
  side panel. It still holds, 3.11 times over (it needs 2)." in about 40 s. The side's pattern shows it with "drill a
  3/8 in hole inside the line to start the jigsaw"; *How do I make it?* reads "5 pieces, 1 hole".
- Tests: `test_pictures.py` (the built-in T-rex and Claude's shapes joined; what a jigsaw can't follow smoothed
  out and the eye dropped; panels nobody stands on, upright as seen from outside; a T-rex on the side cut and still
  holding, on the rebuilt part; lightening leaves it alone and adopting keeps it; too weak shrinks it, hopeless
  changes nothing; the chat routes it and leaves parts alone; a drawing from the pad cut through the API).
- Commit: `c2ecdc0`. PR #50. **Full suite: 523 passed.**
