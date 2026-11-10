"""CALI-134 (#167) — which step of a carve or a Lighten to offer, one answer for the card, the panel, the chat and the 3D view.

The deepest step that passes its own check has no room: the re-check on the rebuilt part reads lower, and often leaves a part that doesn't
hold. How much lower follows the walls, not the number. A lighter load scales the number and leaves the shape alone, so a thin step can
clear any margin: the bridge at 15 lb read 3.06 and re-checked at 0.94. So a step counts as having room only if the re-check can see
its walls at all, and then the 1.5 times is a floor, a rule of thumb and not a prediction.
"""

from __future__ import annotations

from typing import Callable, Optional

#: how far a step's own number must clear what the part must hold: a rule of thumb, from the re-checks in #167
USE_FLOOR = 1.5
ROOM = ("It's the deepest step whose walls the re-check can see and that clears what it must hold by at least half again, which is a "
        "rule of thumb, not a prediction.")
NO_ROOM = ("No step whose walls the re-check can see clears what it must hold by half again (a rule of thumb), so this one may not hold "
           "once it's re-checked.")
UNSEEN = "The re-check can't see this step's walls at this size, so it may not settle whether it holds."
UNKNOWN = "This study didn't record how thin each step's walls are, so the re-check may not settle it: run the study again to know."
SAID = {"room": ROOM, "no_room": NO_ROOM, "unseen": UNSEEN, "unknown": UNKNOWN}


def own(st: dict) -> float:
    """A step's number: the weaker of its own and the whole part's, where it has both."""
    return min(x for x in (st.get("safety"), st.get("whole")) if x is not None)


def choose(steps: list[dict], need: float, saved: str, further: Callable[[dict], str]) -> Optional[dict]:
    """The step to offer from those that pass, and what to say about it: ``{index, kind, quote, said, deepest}``. ``saved`` is what a step
    saves; ``further`` says how far a step got, for what's given up."""
    if not steps:
        return None
    seen = [st for st in steps if st.get("seen") is True]
    room = [st for st in seen if own(st) >= USE_FLOOR * need]
    if room:
        pick, kind = max(room, key=lambda st: st[saved]), "room"
    elif seen:
        pick, kind = max(seen, key=own), "no_room"
    else:
        pick, kind = max(steps, key=own), "unknown" if any(st.get("seen") is None for st in steps) else "unseen"
    deepest = max(steps, key=lambda st: st[saved])
    gave_up = deepest[saved] > pick[saved]
    return {"index": pick["index"], "kind": kind, "quote": own(pick), "deepest": deepest["index"] if gave_up else None,
            "said": SAID[kind] + (f" The study got as far as {further(deepest)}, and that step is there to choose." if gave_up else "")}
