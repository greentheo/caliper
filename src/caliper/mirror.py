"""CALI-161 (#239) — mirrored parts: one script, flipped.

Theo's step-stool-4 (2026-11-11): the left and right sides weren't mirrors of each other. The plan's intent said "mirror
of side_left", but nothing made it one: the designer wrote side_right from scratch (walls 15 against 12 mm, another
pocket depth, a boss against a pad), and spent a full try on a part that is a flip.

A mirrored part's script is **generated**, never written by a designer: its source's script, whole, with a wrapper
that flips what it builds in a plane (``YZ``, ``XZ`` or ``XY``, through ``MIRROR_AT``) and flips the points and
directions it declares (its construction's outlines, holes and stick ends, ``HOLES``, its loads). So every reader of a
part's script (the cut list, the holes, the joints, the strength study) reads the mirror as its own part with no change
to them, and it costs no designer time. It's written again whenever its source is (:meth:`DesignStore.write_part`),
and an edit asked of it goes to its source.
"""

from __future__ import annotations

import re
from typing import Optional

#: The planes a part can be mirrored in, and the axis each one flips.
PLANES = {"YZ": 0, "XZ": 1, "XY": 2}
HEAD = "# --- Caliper: a mirror of {source} (generated) ---"
_OF = re.compile(r"^MIRROR_OF\s*=\s*['\"](\w+)['\"]", re.M)
_PLANE = re.compile(r"^MIRROR_PLANE\s*=\s*['\"](\w+)['\"]", re.M)
_AT = re.compile(r"^MIRROR_AT\s*=\s*\(([^)]*)\)", re.M)
_BODY = re.compile(r"\n# --- Caliper: the source's script ---\n(.*)\n# --- Caliper: the mirror, applied ---\n", re.S)

#: What the wrapper does to the source's script. It flips only what's under keys that hold points or directions; a
#: size (``size``, ``thickness``) is never flipped.
WRAPPER = '''
# --- Caliper: the mirror, applied ---
import functools as _caliper_ft

_CALIPER_POINTS = ("outline", "facets", "holes", "polygons", "a", "b", "at", "lo", "hi", "points", "from", "to",
                   "center", "centre", "origin", "start", "end")
_CALIPER_VECTORS = ("normal", "direction", "dir", "axis")
_CALIPER_I = {"YZ": 0, "XZ": 1, "XY": 2}[MIRROR_PLANE]
#: the position words a flip in this plane swaps, in a piece's or a hole's name ("right side" is "left side" mirrored)
_CALIPER_SWAP = [("left", "right"), ("front", "back"), ("top", "bottom")][_CALIPER_I]


def _caliper_triple(v):
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(
        isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)


def _caliper_map(x, point):
    if _caliper_triple(x):
        out = [float(c) for c in x]
        out[_CALIPER_I] = 2 * MIRROR_AT[_CALIPER_I] - out[_CALIPER_I] if point else -out[_CALIPER_I]
        return tuple(out) if isinstance(x, tuple) else out
    if isinstance(x, (list, tuple)):
        got = [_caliper_map(c, point) for c in x]
        return tuple(got) if isinstance(x, tuple) else got
    return x


def _caliper_rename(s):
    import re as _re

    a, b = _CALIPER_SWAP
    def swap(m):
        w = m.group(0)
        to = b if w.lower() == a else a
        return to.capitalize() if w[:1].isupper() else to
    return _re.sub(rf"\\b(?:{a}|{b})\\b", swap, s, flags=_re.I)


def _caliper_tree(x):
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in ("name", "piece") and isinstance(v, str):
                out[k] = _caliper_rename(v)
                continue
            out[k] = (_caliper_map(v, True) if k in _CALIPER_POINTS else _caliper_map(v, False) if k in _CALIPER_VECTORS
                      else _caliper_tree(v))
        if _caliper_triple(out.get("lo")) and _caliper_triple(out.get("hi")):    # a box's corners, low and high again
            lo, hi = list(out["lo"]), list(out["hi"])
            out["lo"], out["hi"] = [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]
        return out
    if isinstance(x, (list, tuple)):
        return [_caliper_tree(c) for c in x]
    return x


def _caliper_flip(f):
    @_caliper_ft.wraps(f)
    def flipped(*args, **kwargs):
        return _caliper_tree(f(*args, **kwargs))
    return flipped


_caliper_source_build = build


def build(params):
    got = _caliper_source_build(params)
    if hasattr(got, "mirror"):
        return got.mirror(MIRROR_PLANE, MIRROR_AT)
    raise TypeError("a mirrored part can only flip a CadQuery solid, and its source built a " + type(got).__name__)


for _caliper_name in ("construction", "loads", "held", "keeps", "shell", "roof", "supports", "members"):
    if callable(globals().get(_caliper_name)):
        globals()[_caliper_name] = _caliper_flip(globals()[_caliper_name])
if isinstance(globals().get("HOLES"), list):
    HOLES = _caliper_tree(HOLES)
'''


def script(source: str, source_script: str, plane: str, at) -> str:
    """Part ``source``'s script, flipped in ``plane`` through ``at``: a mirrored part's whole script."""
    plane = plane.upper()
    if plane not in PLANES:
        raise ValueError(f"a mirror's plane is YZ, XZ or XY, not {plane!r}")
    if of(source_script):
        raise ValueError(f"{source} is itself a mirror: mirror its source instead")
    at = tuple(round(float(v), 4) for v in at)
    return (HEAD.format(source=source) + "\n"
            f"# This part is {source}, mirrored in the {plane} plane through {at}. Change {source}, not this: it's\n"
            f"# written again whenever {source} is.\n"
            f"MIRROR_OF = {source!r}\nMIRROR_PLANE = {plane!r}\nMIRROR_AT = {at!r}\n"
            "\n# --- Caliper: the source's script ---\n" + source_script.rstrip() + "\n" + WRAPPER)


def of(script_text: str) -> Optional[dict]:
    """``{"source", "plane", "at"}`` if this script is a mirror, else None."""
    m = _OF.search(script_text or "")
    if m is None:
        return None
    at = _AT.search(script_text)
    return {"source": m.group(1), "plane": (_PLANE.search(script_text) or [None, "YZ"])[1],
            "at": tuple(float(v) for v in at.group(1).split(",") if v.strip()) if at else (0.0, 0.0, 0.0)}


def source_of(store, part_id: str) -> Optional[str]:
    """The part this one mirrors, or None."""
    if not store.is_scripted(part_id):
        return None
    got = of(store.read_script(part_id))
    return got["source"] if got else None


def mirrors_of(store, source: str) -> list[str]:
    """The parts that mirror ``source``."""
    return [p.id for p in store.design.parts if p.id != source and source_of(store, p.id) == source]


def body(script_text: str) -> str:
    """The source's script inside a mirror's (what's flipped)."""
    m = _BODY.search(script_text or "")
    return m.group(1).rstrip() + "\n" if m else script_text


def between(store, part_id: str, source: str) -> tuple[str, tuple]:
    """The plane and point to flip ``source`` in so it lands where ``part_id`` is: across the axis their middles are
    furthest apart on, half way between them (two sides of a stool, at either end of it)."""
    a = store.part_geometry(source).require_mesh().bounds
    b = store.part_geometry(part_id).require_mesh().bounds
    ca, cb = [(a[0][k] + a[1][k]) / 2 for k in range(3)], [(b[0][k] + b[1][k]) / 2 for k in range(3)]
    k = max(range(3), key=lambda i: abs(ca[i] - cb[i]))
    at = [0.0, 0.0, 0.0]
    at[k] = (ca[k] + cb[k]) / 2
    return {0: "YZ", 1: "XZ", 2: "XY"}[k], tuple(at)


def make(store, part_id: str, source: str, plane: Optional[str] = None, at=None, *, feedback: str = "") -> int:
    """Make ``part_id`` a mirror of ``source``: its script becomes the generated one, and its own script stays in its
    versions. The plane and point, where not given, are half way between where the two parts are now. The new
    version."""
    if part_id == source:
        raise ValueError("a part can't mirror itself")
    if source_of(store, part_id) == source:          # asked again: already so, nothing written (#246 review)
        return store.design.part(part_id).version
    if source_of(store, source) == part_id:
        raise ValueError(f"{part_id} and {source} are already one script: {source} mirrors {part_id}")
    if source_of(store, source):
        raise ValueError(f"{source} is itself a mirror of {source_of(store, source)}: make {part_id} a mirror of "
                         f"{source_of(store, source)} instead")
    followers = mirrors_of(store, part_id)
    if followers:                                     # no mirror of a mirror, from either end (#246 review)
        raise ValueError(f"{part_id} has a mirror, {_listed(followers)}: break that first, or make "
                         f"{followers[0]} a mirror of {source} too")
    if plane is None or at is None:
        got_plane, got_at = between(store, part_id, source) if store.design.part(part_id) else ("YZ", (0.0, 0.0, 0.0))
        plane, at = plane or got_plane, at if at is not None else got_at
    text = script(source, store.read_script(source), plane, at)
    entry = store.design.part(source)
    return store.write_part(part_id, text, action="mirror", intent=f"a mirror of {source}",
                            feedback=feedback or f"made a mirror of {source}",
                            extra={"mirror_of": source, "source_version": entry.version if entry else None})


def rebuild(store, source: str) -> list[str]:
    """Write every mirror of ``source`` again from its script as it is now: the mirrors rebuilt."""
    done = []
    for pid in mirrors_of(store, source):
        got = of(store.read_script(pid))
        text = script(source, store.read_script(source), got["plane"], got["at"])
        if text != store.read_script(pid):
            entry = store.design.part(source)
            store.write_part(pid, text, action="mirror", feedback=f"rebuilt from {source} v{entry.version}",
                             extra={"mirror_of": source, "source_version": entry.version})
            done.append(pid)
    return done


def unmirror(store, part_id: str) -> int:
    """Break the mirror ("make the left one different"): ``part_id`` keeps the flipped shape, as a script of its own that
    no longer follows its source. The new version."""
    text = store.read_script(part_id)
    got = of(text)
    if got is None:
        raise ValueError(f"{part_id} isn't a mirror")
    own = _OF.sub(f"MIRROR_OF = None  # was a mirror of {got['source']}: its own script now", text, count=1)
    own = own.replace(HEAD.format(source=got["source"]), f"# --- a copy of {got['source']}, mirrored: its own now ---", 1)
    return store.write_part(part_id, own, action="unmirror", feedback=f"no longer a mirror of {got['source']}",
                            extra={"unmirrored_from": got["source"]})


def _listed(xs: list) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def said(part_id: str, source: str) -> str:
    """Where a change asked of a mirror goes, in words."""
    return (f"{part_id} mirrors {source}: change {source} and {part_id} follows it, or break the mirror first (say "
            f"\"make {part_id} its own part\")")


def refuse_if_mirror(store, part_id: str, what: str = "") -> None:
    """Refuse a change asked of a mirror that can't go to its source, saying where to make it (#246 review: a carve or a
    Lighten on the mirror would be undone the next time its source changed, with nothing said). ValueError."""
    source = source_of(store, part_id)
    if source:
        raise ValueError((f"I can't {what} {part_id} on its own: " if what else "") + said(part_id, source))
