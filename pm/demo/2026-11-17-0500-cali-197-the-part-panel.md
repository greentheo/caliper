### 2026-11-17 · CALI-197 (#331) · the part panel: Parameters on top, the four questions one at a time, the actions top right

**Pick a part.**
- **Its numbers:** Parameters sits right under its name, always in view.
- **The four questions,** What is it?, Will it work?, What do I buy? and How do I make it?, are an accordion: one open
  at a time, the first ✗ open first.
- **Every closed card keeps its mark and its answer line** under its header. Inside each card, blocks keep their own
  mark and answer, closed until opened.

**The actions are small buttons top right:** Check it holds, Lighten it (or Carve it), Shape for drag, and Make the cut
plan, in the chain's order.
- **A greyed one says why** on a click or a tap, under the buttons, and nothing runs: "it doesn't build yet", "check it
  holds first", "it doesn't pass its loads yet: 1.0 where it needs 2", or "not here: unfold-to-sheets isn't at …".
- **A running check or Lighten says so** on its button: "Checking…", "Lightening…".
- **Each one opens what it feeds,** where its progress shows.

**The marks say only what's measured:**
- With no check of this version, Things to fix reads "· not checked yet", never ✓. Check it holds, and it reads the
  list again.
- Made in your shop is this design's plan, its header set when the plan comes back. A part that doesn't build reads
  "can't plan it: it doesn't build".

**Offline:** `python -m pytest tests/test_part_panel.py tests/test_part_panel_marks.py`.
