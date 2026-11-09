### 2026-10-30 · CALI-79 (#47) · A build book a kid can follow: pictures first, one step a page
- Showcase 1 (#10) asks for a build book a kid can read, pictures first. The shop's book had two steps for the
  stool ("End and side panels", "Finish"), and its panel step said to "glue them to the floor's edge and the
  skeleton with foam-safe adhesive": the camper's words, for a plywood stool.
- **`kidbook.py`:** `kids.html` in the build package, for a build that's all wood (sheets or sticks, glued and
  screwed; a welded frame stays in the shop's book):
  - **Get your things:** the shopping list in a kid's words, plus the tools, as boxes to tick.
  - **Draw the pieces:** each pattern's thumbnail and its name, and the full-size PDF.
  - **Cut them out**, with a grown-up: for a picture or a hole, "drill a hole just inside the line first".
  - **Sand the edges.**
  - **One page a piece**, in the order they go together: the lowest standing piece first, then each one that
    meets what's there (the joints the shopping list counts screws for), lowest and biggest first. Every page has
    the same view, what's on in pale and the new piece in colour, and "Put glue on the edges where the left side
    panel touches the front panel… put in 2 screws." The pages' screws add up to the shopping list's.
  - **Paint it**, if it's painted.
  - **Test it:** gently, with a grown-up holding it; how many times over it should hold; what that promises.
  - The view looks at the side with the picture (and the front with it); the cover is the stool with its T-rex.
- **Drawings show holes:** `release.pieces` gives a flat panel its holes, so the shop's book draws the T-rex and the
  lightening windows too. *How do I make it?* links **The kids' build book** beside the build book.
- Tests: `test_kidbook.py` (a wooden build gets one and a welded frame doesn't; the pages in order with the top
  last, a kid's words, the start-hole line, the promise, a drawing per piece, the screws adding up; the drawings
  show a panel's holes and look at the picture).
- Commits: `14d939d`, `96584bf` (the shop book's wood panels). PR #52. **Full suite on this branch, the stack's top: 530 passed.**
