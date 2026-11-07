"""CALI-126 (#150) — a sheet's face grain: greener only when the person says it, and the maker is told.

Plywood is about half as strong across its face grain, so a top resting on two sides (a beam across the gap) is
checked both ways and, the grain's way unknown, takes the worse (#118). Which way it's cut is the maker's call, so:

- **Assumed:** a ``"grain"`` the designer writes on a sheet in ``construction()`` is never the verdict's. The check
  takes the worse grain and the card gives the advice ("cut it with the face grain running front to back and it's
  about 3.1 times over"), as the plan's assumed numbers are shown, not enforced (#117).
- **Stated:** a grain the person says (in the chat, "cut the seat with the grain front to back", or by keeping the
  card's advice) is kept here, in the design, never in the script. The next strength check uses it for that panel,
  and the cut list and the build book tell the maker which way to cut it.

``design.grain`` is ``{part: {piece: {"grain": "along" | "across", "runs": "front to back", "said": …}}}``; ``grain``
is relative to the gap the panel spans, ``runs`` is the same in the part's own directions when it's known.
"""

from __future__ import annotations

import re
from typing import Optional

from .design import DesignStore

GRAINS = ("along", "across")

#: the part's own directions, by the axis a run's beam check says it spans (x across, y front to back, z up)
AXIS_WORDS = {"x": "side to side", "y": "front to back", "z": "up and down"}
_WORD_AXIS = {"side to side": "x", "left to right": "x", "right to left": "x", "front to back": "y",
              "back to front": "y", "up and down": "z"}


def stated(store: DesignStore, pid: str) -> dict:
    """The grains the person has said for this part's sheets: ``{piece: {grain, runs, said}}``."""
    return dict((store.design.grain or {}).get(pid) or {})


def runs(span_axis: Optional[str], grain: str) -> str:
    """Which way the face grain runs, in the part's own directions: along a span that runs front to back is "front to
    back"; across it, the other way in the panel's plane (a top's: side to side). "" where that isn't known."""
    if span_axis not in AXIS_WORDS:
        return ""
    if grain == "along":
        return AXIS_WORDS[span_axis]
    other = {"x": "y", "y": "x"}.get(span_axis)          # a top: its plane is x-y; the other way in it
    return AXIS_WORDS[other] if other else ""


def beam_of(store: DesignStore, pid: str, piece: str) -> Optional[dict]:
    """The newest beam check on this panel at this part's version, if one ran: its span's axis says which way is
    which."""
    from . import load_study as L

    entry = store.design.part(pid)
    for run in L.list_runs(store, pid):
        if entry is None or run.get("version") != entry.version:
            continue
        for c in run.get("cases") or []:
            pl = c.get("plate") or {}
            if pl.get("as") == "beam" and pl.get("piece") == piece:
                return pl
    return None


def state(store: DesignStore, pid: str, piece: str, grain: str, said: str = "") -> dict:
    """The person's grain for one panel, kept in the design (never the script). ``grain``: along or across the gap
    it spans. Raises with why for a part or panel that isn't one, or a grain that isn't along or across."""
    from . import construction as C

    if grain not in GRAINS:
        raise ValueError(f"a sheet's grain is along or across the gap it spans, not {grain!r}")
    if store.design.part(pid) is None:
        raise ValueError(f"there's no part {pid!r}")
    sheets = [it.get("name") for it in C.declared(store, pid).get("construction") or []
              if isinstance(it, dict) and it.get("kind") == "sheet"]
    if piece not in sheets:
        raise ValueError(f"the {pid.replace('_', ' ')} has no sheet {piece!r}"
                         + (f" (its sheets: {', '.join(s for s in sheets if s)})" if sheets else ""))
    pl = beam_of(store, pid, piece)
    entry = {"grain": grain, "runs": runs((pl or {}).get("span_axis"), grain), "said": said}
    store.design.grain = {**(store.design.grain or {}), pid: {**stated(store, pid), piece: entry}}
    store.save()
    store.append_history(pid, {"kind": "grain", "action": "stated", "piece": piece, **entry})
    return entry


def phrase(runs: str, grain: str) -> str:
    """The one way a cut's grain is said, everywhere (#151 review: "along the gap" and "across the gap" each read both
    ways): the part's own direction first, then which way that is between the supports. "face grain running front to
    back, from one support to the other" (along the span: the strong way) or "…, parallel to the supports" (across)."""
    between = "from one support to the other" if grain == "along" else "parallel to the supports"
    return f"face grain running {runs}, {between}" if runs else f"face grain running {between}"


def axis(entry: dict) -> Optional[str]:
    """The part's own axis the face grain runs along ("x", "y", "z"), from its direction words; None if not known."""
    return _WORD_AXIS.get(entry.get("runs") or "")


def line(piece: str, entry: dict) -> str:
    """What the maker reads: "Cut the seat top with its face grain running front to back, from one support to the
    other."."""
    return f"Cut the {piece} with its {phrase(entry.get('runs') or '', entry['grain'])}."


def notes(store: DesignStore, pid: str) -> list[str]:
    """The cut list's and the build book's grain lines for this part's panels, as the person said them."""
    return [line(piece, e) for piece, e in sorted(stated(store, pid).items())]


# --- the chat: "cut the seat with the grain front to back" ------------------------------------------------------------

_SAID = re.compile(r"\bgrain\b", re.I)
_WAY = re.compile(r"\b(side to side|left to right|right to left|front to back|back to front|up and down)\b|"
                  r"\b(along|across)\s+the\s+(?:span|gap)\b", re.I)


def from_chat(store: DesignStore, message: str, scope: Optional[str] = None) -> Optional[dict]:
    """A grain the person says in the chat, for a sheet it can name: ``{part, piece, grain, entry}`` once kept, or
    ``{"why": …}`` when it can't be placed (said, never guessed), or None when the message isn't about a grain."""
    from . import construction as C

    if not _SAID.search(message or "") or message.strip().endswith("?"):
        return None                              # a question about the grain is the chat's to answer, never kept
    m = _WAY.search(message)
    text = _WAY.sub(" ", message.lower())        # "front to back" names a direction, not the front or back panel
    found = []
    for p in store.design.parts:
        if scope and p.id != scope:
            continue
        try:
            items = C.declared(store, p.id).get("construction") or []
        except Exception:  # noqa: BLE001 — a part that won't build names no sheet
            continue
        for it in items:
            name = (it.get("name") or "") if isinstance(it, dict) and it.get("kind") == "sheet" else ""
            words = [w for w in re.split(r"[\s_]+", name.lower()) if w]
            if name and (name.lower().replace("_", " ") in text or (words and all(w in text for w in words))):
                found.append((p.id, name))
    if m is None:                                # a grain with no way: asked, never left to the designer (#151)
        return {"why": ("which way: front to back, or side to side?" if found else
                        "which sheet, and which way: front to back, or side to side?")}
    if not found:
        return {"why": "which sheet? Name it as its part does (its sheets are on the part's card)"}
    if len(found) > 1:
        return {"why": "that names " + ", ".join(f"the {n} of the {p.replace('_', ' ')}" for p, n in found)
                       + ": say which one"}
    (pid, piece), = found
    if m.group(2):
        grain = m.group(2).lower()
    else:
        pl = beam_of(store, pid, piece)
        axis = (pl or {}).get("span_axis")
        if axis is None:
            return {"why": f"which way does the {piece} span? Check it holds first, then say it again (or say "
                           f"\"along the span\" or \"across the span\")"}
        grain = "along" if _WORD_AXIS[m.group(1).lower()] == axis else "across"
    return {"part": pid, "piece": piece, "grain": grain, "entry": state(store, pid, piece, grain, said=message)}
