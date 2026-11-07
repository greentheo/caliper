"""CALI-112 (#114; rule 6) — one verdict, asked by every reader.

Four states were added one PR at a time in two days (not trusted, #96; not resolved, #100/#110; waiting for parts,
#103; checked in the middle only, #106), and each time a reader that re-derived the verdict from ``holds`` or
``safety >= min_safety`` still said "holds", or showed green. Every reader now asks here, and a new state is one
place: a kind in :data:`KINDS`, and where it ranks.

A verdict is ``{"status": ok | warn | bad | unknown, "kind": …, "short": "holds 3.1x", "word": "holds",
"counts_as_pass": bool}``. Precedence, as the PRs settled it: a ✗ stays a ✗; then not trusted (the check ran on a
block); then not resolved / not checked (an FEA too coarse to see the wall); then middle only (no foot on the free
edge); then an older version; then waiting; only then holds.
"""

from __future__ import annotations

from typing import Optional

#: Every kind, best last: (status, the word a badge says, counts as a pass). A new state goes here and in RANK.
KINDS = {
    "fails": ("bad", "doesn't hold", False),
    "untrusted": ("warn", "not trusted", False),
    "unchecked": ("warn", "not checked", False),
    "unresolved": ("warn", "not resolved", False),
    "edge": ("warn", "middle only", False),
    "stale": ("warn", "older version", False),
    "waiting": ("unknown", "not checked yet", False),
    "holds": ("ok", "holds", True),
}
#: Worst first: a run, or a design, is its worst case.
RANK = list(KINDS)


def _make(kind: str, safety=None, **extra) -> dict:
    status, word, counts = KINDS[kind]
    short = f"{word} {safety:.1f}x" if safety is not None and kind in ("holds", "fails") else word
    return {"status": status, "kind": kind, "word": word, "short": short, "counts_as_pass": counts, **extra}


def _unresolved(run: dict, c: dict) -> bool:
    from .load_study import unresolved

    return unresolved(run, c)


def case(run: dict, c: dict, *, filled: Optional[str] = None, edge: bool = False, stale: bool = False) -> dict:
    """One load case's verdict. ``filled``: why the part's shape isn't its pieces (CALI-96), if it isn't; ``edge``:
    a two-sided top whose loads skip its free edge (#106: or the case says ``middle_only``); ``stale``: the run is
    of an older version."""
    safety = c.get("safety")
    if safety is None:
        return _make("waiting", why=c.get("why") or "")
    held = c.get("holds")  # producer: the study's own number, judged here
    off = _unresolved(run, c)
    if not held:                                       # a ✗ stays a ✗ (CALI-97): its words say if the model may be wrong
        return _make("fails", safety, coarse=off)
    if filled or run.get("filled"):
        return _make("untrusted", safety, why=filled or run.get("filled"))
    if off:
        return _make("unchecked" if not run.get("finer") else "unresolved", safety)
    if edge or c.get("middle_only"):
        return _make("edge", safety)
    if stale:
        return _make("stale", safety)
    return _make("holds", safety)


def worst(verdicts: list[dict]) -> Optional[dict]:
    """The worst of several (a run's cases, a design's parts)."""
    return min(verdicts, key=lambda v: RANK.index(v["kind"]), default=None)


def run(rec: dict, *, filled: Optional[str] = None, edge: bool = False, stale: bool = False) -> dict:
    """A strength run's verdict: its worst case, carrying that case's safety (the run's own number)."""
    got = [case(rec, c, filled=filled, edge=edge, stale=stale) for c in rec.get("cases") or []]
    w = worst(got)
    if w is None:
        return _make("waiting")
    return {**w, "short": _make(w["kind"], rec.get("safety"))["short"], "cases": got}


def holds(rec: dict, c: Optional[dict] = None, **kw) -> bool:
    """Whether a person may read it as holding: only a ✓ with nothing over it."""
    return (case(rec, c, **kw) if c is not None else run(rec, **kw))["counts_as_pass"]


def fails(rec: dict, c: Optional[dict] = None) -> bool:
    """A ✗ (and only a ✗): a fail stays a fail, whatever else is true."""
    return (case(rec, c) if c is not None else run(rec))["kind"] == "fails"


# --- a scorecard: its checks' statuses and its summary --------------------------------------------------------------
#: A scorecard check's status, as a verdict kind.
CHECK = {"pass": "holds", "fail": "fails", "untrusted": "untrusted", "unresolved": "unresolved", "edge": "edge",
         "unknown": "waiting", "deferred": "waiting", "proposed": "waiting"}


def check(status: str) -> dict:
    return _make(CHECK.get(status, "waiting"))


def summary(s: Optional[dict]) -> dict:
    """A scorecard's summary as one verdict: ``ok`` only when nothing fails, nothing is unsettled and something
    passed. ``why`` says the first thing in the way, in precedence order."""
    s = s or {}
    if not s or s.get("fail"):
        return _make("fails", why="a check fails")
    if s.get("untrusted"):
        return _make("untrusted", why="a check isn't trusted yet")
    if s.get("unresolved"):
        return _make("unresolved", why="a strength check isn't resolved")
    if s.get("edge"):
        return _make("edge", why="a strength check skipped the front edge")
    if s.get("unknown") or not s.get("pass"):
        return _make("waiting", why="a check isn't settled")
    return _make("holds", why="")


# --- a goal held against a metric (the scorecard and the design card), and a number against what it needs ----------
#: A verdict kind as a scorecard check's status.
STATUS = {"holds": "pass", "fails": "fail", "untrusted": "untrusted", "unresolved": "unresolved",
          "unchecked": "unresolved", "edge": "edge", "stale": "unknown", "waiting": "unknown"}


def goal(met: Optional[bool], *, untrusted: Optional[str] = None, unresolved: Optional[str] = None,
         edge: bool = False, stale: bool = False) -> dict:
    """A goal on a metric: ``met`` (None when there's no number). A ✗ stays a ✗ (a fail on a filled-in block is
    certain: the part as built is weaker still); then not trusted, not resolved, middle only, scored before the last
    change. ``untrusted``/``unresolved`` are the words that say why, carried as ``why``."""
    if met is None:
        return _make("waiting")
    if not met:
        return _make("fails")
    if untrusted:
        return _make("untrusted", why=untrusted)
    if unresolved:
        return _make("unresolved", why=unresolved)
    if edge:
        return _make("edge")
    if stale:
        return _make("stale")
    return _make("holds")


def meets(safety: Optional[float], need: Optional[float]) -> dict:
    """A number against what it needs (a frame's weakest member, a station): holds or fails, or waiting."""
    if safety is None:
        return _make("waiting")
    return _make("holds" if safety >= (need or 0) else "fails", safety)


def station(st: dict, *, whole: bool = False) -> dict:
    """A lighten or carve step: the carved part (or, ``whole``, the whole part at that step) holds or doesn't.
    #101 adds its own kinds here (a step on voxels too coarse to see the wall)."""
    held = st.get("whole_holds" if whole else "holds")  # producer: the study's own number, judged here
    safety = st.get("whole" if whole else "safety")
    if held is None:
        return _make("waiting")
    return _make("holds" if held else "fails", safety)


def of(got: dict) -> dict:
    """A verdict carried on a result (``got["verdict"]``), or read from its flags: ``holds`` with ``unresolved``,
    ``filled``, ``middle_only`` (a picture's re-check, as #100–#106 wrote them)."""
    if got.get("verdict"):
        return got["verdict"]
    return goal(got.get("holds"), untrusted=got.get("filled") or None, unresolved="coarse" if got.get("unresolved") else None,
                edge=bool(got.get("middle_only")))
