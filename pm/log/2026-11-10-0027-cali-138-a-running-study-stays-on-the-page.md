### 2026-11-10 · CALI-138 (#178) · A running study stays on the page
Found walking the stool: a study running on the server vanished from the page after a switch of design, a reload or another
job finishing, and its button looked live, either silently dead or starting a duplicate.
- **The design's record says what's running** (`running`: strength checks, Lightens and build packages), as `carving` does for
  a carve. The page draws from it on load and on every redraw: the progress line, Cancel while it waits, and the button
  off with why.
- **A second click says it's already running:** the routes refuse a repeat of the same kind and part (409, in words).
  Another design may run the same part.
- With its panel not on screen, a line at the top of the cards says what's running.
- Found checking it: the Parameters panel threw on a timer while a design was loading.
- Tests: tests/test_running.py. Mutants fail for not being on the record, another design's job counted, a second click allowed, a
  redraw not looking, following twice, and Cancel shown when it isn't waiting.
