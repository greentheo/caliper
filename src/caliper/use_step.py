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
#: the least saving of material worth a button, in dollars. A judgment call, not a measurement: a carve costs a re-check, up to a third or so of
#: the margin, and it comes off the next time the chat changes the part. Under this, the card says what it would save and leaves it in the study
USE_MIN_USD = 1.0
ROOM = ("It's the deepest step whose walls the re-check can see and that clears what it must hold by at least half again, which is a "
        "rule of thumb, not a prediction.")
NO_ROOM = ("No step whose walls the re-check can see clears what it must hold by half again (a rule of thumb), so this one may not hold "
           "once it's re-checked.")
UNSEEN = "The re-check can't see the walls of any step at this size, so it couldn't settle whether one holds. The steps are in the study."
UNKNOWN = ("This study didn't record how thin each step's walls are, so it can't say which step a re-check could settle: run the study again "
           "to know. The steps are in the study.")
SAID = {"room": ROOM, "no_room": NO_ROOM, "unseen": UNSEEN, "unknown": UNKNOWN}
#: the least a Lightening must save to get a button (#207). A labour threshold, not a safety one: every hole is a cut in the shop and a
#: re-check, so a few ounces is the same waste as a 7¢ carve, paid in labour. A quarter pound or 5% of the part, whichever is larger,
#: but never more than a pound: the labour doesn't grow with the part, and a pound saved is a pound carried (#252 review). The foreman's
#: call for now; Theo can move it. It decides only whether there's a button: a deeper step over it is still named
LIGHTEN_MIN = {"lb": 0.25, "share": 0.05, "most_lb": 1.0}


def lighten_floor(part_lb: Optional[float]) -> float:
    """:data:`LIGHTEN_MIN` for a part of this weight: ``min(1 lb, max(0.25 lb, 5%))``; a quarter pound where its weight isn't known."""
    if not part_lb:
        return LIGHTEN_MIN["lb"]
    return min(LIGHTEN_MIN["most_lb"], max(LIGHTEN_MIN["lb"], LIGHTEN_MIN["share"] * part_lb))


#: a deeper step only counts as given up if it saves this much more: "3.37 lb against 3.35" isn't worth a sentence
GAVE_UP_BY = 1.05


def own(st: dict) -> float:
    """A step's number: the weaker of its own and the whole part's, where it has both."""
    return min(x for x in (st.get("safety"), st.get("whole")) if x is not None)


def _money(usd: float) -> str:
    return f"${usd:,.2f}" if usd >= 1 else f"{max(1, round(usd * 100))}¢"


def _strength(as_drawn: Optional[float], quote: float) -> str:
    """What the step costs in strength, in words: "" where the part as drawn wasn't checked."""
    if as_drawn is None:
        return ""
    if quote >= 0.95 * as_drawn:
        return "at almost no cost in strength"
    return f"taking it from about {round(as_drawn, 1):g} to {round(quote, 1):g} times over"


def choose(steps: list[dict], need: float, saved: str, further: Callable[[dict], str], *, as_drawn: Optional[float] = None,
           worth: Optional[Callable[[dict], Optional[float]]] = None, least: Optional[float] = None) -> Optional[dict]:
    """The step to offer from those that pass, and what to say about it: ``{index, kind, quote, said, deepest, offers}``. ``saved`` is what
    a step saves; ``further`` says how far a step got, for what's given up; ``as_drawn`` is the part's number before any of it; ``worth``
    is what a step saves in dollars, where that's known. ``offers`` False: nothing to click. The re-check couldn't settle any step, or the
    saving is too small to be worth it, and the card says which. ``least``: the least ``saved`` worth a button (a Lightening's, #207)."""
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
    deepest = max(seen or steps, key=lambda st: st[saved])          # one the re-check can see: that's one to choose (#207)
    furthest = max(steps, key=lambda st: st[saved])
    out = {"index": pick["index"], "kind": kind, "quote": own(pick), "deepest": None, "offers": False, "said": SAID[kind]}
    if kind in ("unseen", "unknown"):
        return out
    cost = _strength(as_drawn, own(pick))
    usd = worth(pick) if worth else None
    if usd is not None and usd < USE_MIN_USD:
        return {**out, "kind": "small", "said": f"It would save about {_money(usd)} of material{', ' + cost if cost else ''}: too little to be worth "
                                                f"a re-check, so it's left in the study."}
    gave_up = deepest[saved] > GAVE_UP_BY * pick[saved]
    if least is not None and pick[saved] < least:   # the floor decides the button only: a deeper step over it is still named (#252)
        named = gave_up and deepest[saved] >= least
        return {**out, "kind": "small", "deepest": deepest["index"] if named else None,
                "said": f"It would make it {further(pick)}{', ' + cost if cost else ''}: too little to be worth the cuts and a re-check, "
                        f"so it's left in the study."
                        + (f" The study got as far as {further(deepest)}, and that step is there to choose." if named else "")}
    unseen = furthest.get("seen") is not True and furthest[saved] > GAVE_UP_BY * (deepest if gave_up else pick)[saved]
    return {**out, "offers": True, "deepest": deepest["index"] if gave_up else None,
            "said": SAID[kind] + (f" That takes it{cost[9:]}." if cost.startswith("taking it") else f" It comes {cost}." if cost else "")
                    + (f" The study got as far as {further(deepest)}, and that step is there to choose." if gave_up else "")
                    + (f" The study got as far as {further(furthest)}, but the re-check can't see that step's walls, so it couldn't be "
                       f"settled." if unseen else "")}
