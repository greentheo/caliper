### 2026-11-06 · CALI-107 (#107) · A requested feature builds or the script says why not; the reply says what changed
- **`part_scripts.md`: no silent fallbacks.** A requested feature builds or raises with a clear message. No
  `try/except` that passes or hands back the shape without it, no returning the input because a size came out
  small, no clamping a requested size without raising.
- **The round checks it** (`fallbacks.find`, an AST read of the script; it never runs it), and fails naming each line:
  - an `except` (bare, `Exception`, …) around a CadQuery call that passes or returns something unchanged;
  - `min(<a requested size>, <a computed limit>)`, through a local copy too (`r = p["fillet_r"]`; tuple
    unpacking counts);
  - `if <a size test>: return <the input>` (a test against 0, "not asked for", is fine).
  - On copies of the bar stool's v4 to v6 it flags every fallback the issue names: the fillet's clamp and its two
    `except: pass`, the mesh's clamps, its two size-guarded returns and its `except: return cone_solid`. The
    samples and the suite's fixtures are clean.
- **The reply says what was asked for and what changed:** "Asked for: …", "Changed: wall 4 mm → 6 mm" (in inches too:
  "fillet_r 6.35 mm (1/4 in) → 12.7 mm (1/2 in)"), and the volume before → after. If the shape didn't change, it
  says what you asked for may not have happened. It says what isn't measured. "The part's own checks pass" replaces
  "Every check on this part passes", which read as covering the request.
- **From #119's review:**
  - a requested parameter (or its copy) compared with 0 or 1 is "none asked for", not flagged (`if p["holes"] < 1:
    return shape`); a computed size still is;
  - any handler type or tuple around a CAD call counts (`(ValueError, RuntimeError)`, OCP's `Standard_Failure`), and
    so does `return s.translate(...)`, the input moved without the feature;
  - a try/except around anything but CAD isn't flagged;
  - the reply says a parameter's plain name ("foot fillet radius") and every length with its unit, whole numbers too.
- **A failing check's reason now reaches the chat** (`_fail_lines` adds its detail), so the line is named there too.
- Tests: `tests/test_fallbacks.py`.
