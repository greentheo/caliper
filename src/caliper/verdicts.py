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

import math
from typing import Optional

def cut(x: float, places: int = 2) -> float:
    """A safety kept to ``places``, cut toward safe, never rounded up (CALI-152, #213): stored as 2.0, a true 1.995
    against 2 read "holds". Every producer that makes a verdict stores its number with this."""
    k = 10 ** places
    return math.floor(x * k + 1e-9) / k


#: What a run from before CALI-152 says when its number sits exactly on its limit: it may be a 1.995 rounded up.
UNCUT = "made before a rounding fix, and it sits exactly on its limit"     # why it says "check it again" (#214)


def old_on_limit(run: Optional[dict], safety, need) -> bool:
    """A run written before CALI-152 (no ``cut`` marker) whose number is exactly its limit: not settled (#214 review:
    step-stool-2's stored 2.0 is a true 1.99)."""
    return (bool(run) and not run.get("cut") and safety is not None and need is not None
            and abs(float(safety) - float(need)) < 1e-9)


def cut_lb(x: float, step: float = 10.0) -> float:
    """A breaking load kept to ``step`` lb, cut toward safe (#214 review: rounded to the nearest 10, a true 496 lb
    was 500 and met "breaks above 500")."""
    return math.floor(x / step + 1e-9) * step


def goal_on_limit(uncut: bool, metric: str, value, limit, op: str = ">=") -> bool:
    """Whether a goal's number from a run made before the rounding fix may be a rounded fail: a safety exactly on
    the goal's own limit, or a breaking load within the 5 lb it could have been rounded up (#214 review)."""
    if not uncut or not isinstance(value, (int, float)) or not isinstance(limit, (int, float)) or not op.startswith(">"):
        return False
    if metric == "strength.safety":
        return abs(value - limit) < 1e-9
    if metric == "strength.breaks_lb":
        return limit <= value < limit + 5
    return False


def needs_recheck(run: Optional[dict]) -> bool:
    """A stored run a reader mustn't reuse as it is (a build package's scorecard, #198): one of its cases, or
    steps, sits on its limit from before CALI-152."""
    run = run or {}
    need = run.get("min_safety")
    return any(old_on_limit(run, x.get("safety"), need) for x in [*(run.get("cases") or []), *(run.get("stations") or [])])


#: Why a part bending between its holds, with the FEA as its only check, isn't settled (CALI-153, #217).
#: A carve step that carved under a held edge of the plywood (#228): its number is a ceiling, not a reading.
AT_MOST_WHY = ("it carves away what holds up an edge of the plywood, so the whole part reads no higher than it did as drawn, "
               "and how much weaker it is the check can't say")
SPAN_WHY = ("the check holds it fixed where it's held, and a real support may let it turn, so it can read two or three "
            "times too strong")


#: A span's FEA number is only in doubt under this many times what it needs: the worst the check read high against beam theory in the coupon
#: table (pm/bench/theory-vs-whittle.md, 3.17). A part that clears even after dividing by it has earned its ✓. To be revisited when Theo's
#: measured coupons come in (#42).
SPAN_MARGIN = 3.2


#: Every kind, best last: (status, the word a badge says, counts as a pass). A new state goes here and in RANK.
KINDS = {
    "fails": ("bad", "doesn't hold", False),
    "untrusted": ("warn", "not trusted", False),
    "unchecked": ("warn", "not checked", False),
    "unresolved": ("warn", "not resolved", False),
    "span": ("warn", "not settled", False),           # the FEA alone, on a part bending between its holds (CALI-153)
    "edge": ("warn", "middle only", False),
    "stale": ("warn", "older version", False),
    "recheck": ("warn", "check it again", False),     # made before a rounding fix, on its limit (CALI-152, #214)
    "estimate": ("warn", "an estimate", False),
    "waiting": ("unknown", "not checked yet", False),
    "close": ("warn", "holds, close to the line", True),
    "holds": ("ok", "holds", True),
}
#: A pass at or under this many times its limit is amber, ``close``: it holds, but near the line (the four-questions
#: spec's proposal, "within 25% of the limit"; the owner may change the band). CALI-88, #64 item 2.
CLOSE = 1.25
#: The kinds with a number a person may build on (it holds, close to the line or not, or it fails), and the passes.
SETTLED = ("holds", "close", "fails")
PASSES = ("holds", "close")
#: Worst first: a run, or a design, is its worst case.
RANK = list(KINDS)


def _make(kind: str, safety=None, **extra) -> dict:
    status, word, counts = KINDS[kind]
    if safety is not None and kind == "fails":           # a ✗'s number is cut, never rounded up toward its limit:
        safety = math.floor(safety * 10 + 1e-9) / 10     # 1.96 against 2 read "doesn't hold 2.0x" (CALI-88, #64)
    short = f"{word} {safety:.1f}x" if safety is not None and kind in ("holds", "fails", "close") else word
    return {"status": status, "kind": kind, "word": word, "short": short, "counts_as_pass": counts, **extra}


def _unresolved(run: dict, c: dict) -> bool:
    from .load_study import unresolved

    return unresolved(run, c)


def case(run: dict, c: dict, *, filled: Optional[str] = None, edge: bool = False, stale: bool = False) -> dict:
    """One load case's verdict. ``filled``: why the part's shape isn't its pieces (CALI-96), if it isn't; ``edge``:
    a two-sided top whose loads skip its free edge (#106: or the case says ``middle_only``); ``stale``: the run is
    of an older version."""
    safety = c.get("safety")
    from .load_study import BLIND, blind

    if blind(run, c):                                  # it saw no stress to judge by (#202): neither a ✓ nor a number to read
        return _make("unresolved", safety, why=BLIND, blind=True)
    if safety is None:
        return _make("waiting", why=c.get("why") or "")
    if (c.get("fea") or {}).get("supported") is False and c.get("governs", "fea") == "fea":
        # the FEA couldn't connect the load to a support: a check that couldn't run, not a ✗ at 0x (#138 item 3)
        return _make("unchecked", why=c.get("why") or "nothing connects where it's pushed to where it's held")
    held = c.get("holds")  # producer: the study's own number, judged here
    off = _unresolved(run, c)
    if not held:                                       # a ✗ stays a ✗ (CALI-97): its words say if the model may be wrong
        return _make("fails", safety, coarse=off)
    if filled or run.get("filled"):
        return _make("untrusted", safety, why=filled or run.get("filled"))
    if off:
        from .load_study import judged_by, unseen

        gap = unseen(run, c)                          # what couldn't be seen, beside what holds (#244)
        by = judged_by(run, c)
        piece = ((c.get("plate") or {}).get("piece") if by == "plate" else
                 next((r.get("piece") for r in c.get("buckling") or [] if r.get("done")), None) if by == "buckling" else None)
        what = f"the {piece.replace('_', ' ')}" if piece else f"the {by} check"
        why = (f"{what} holds {safety:.2f}x; {gap}" if gap and safety is not None else "")
        return _make("unchecked" if not run.get("finer") else "unresolved", safety, **({"why": why} if why else {}))
    from .load_study import fixed_ends

    if fixed_ends(run, c):
        return _make("span", safety, why=SPAN_WHY)
    if edge or c.get("middle_only"):
        return _make("edge", safety)
    if stale:
        return _make("stale", safety)
    if old_on_limit(run, safety, run.get("min_safety")):            # a pass that may be a rounded fail (#214)
        return _make("recheck", safety, why=UNCUT)
    return _make("close" if near(safety, run.get("min_safety")) else "holds", safety)


def near(safety: Optional[float], need: Optional[float]) -> bool:
    """A pass at or under :data:`CLOSE` times what it needs: close to the line (amber)."""
    return safety is not None and bool(need) and need <= safety <= need * CLOSE


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
CHECK = {"pass": "holds", "fail": "fails", "untrusted": "untrusted", "unresolved": "unresolved", "edge": "edge", "span": "span",
         "unknown": "waiting", "deferred": "waiting", "proposed": "waiting"}


def check(status: str) -> dict:
    return _make(CHECK.get(status, "waiting"))


def summary(s: Optional[dict]) -> dict:
    """A scorecard's summary as one verdict: ``ok`` only when nothing fails, nothing is unsettled and something
    passed. ``why`` says the first thing in the way, in precedence order."""
    if not s:                                   # no card: nothing checked yet, not a fail (#132 review)
        return _make("waiting", why="nothing has been checked yet")
    if s.get("fail"):
        return _make("fails", why="a check fails")
    if s.get("untrusted"):
        return _make("untrusted", why="a check isn't trusted yet")
    if s.get("unresolved"):
        return _make("unresolved", why="a strength check isn't resolved")
    if s.get("span"):
        return _make("span", why=SPAN_WHY)
    if s.get("edge"):
        return _make("edge", why="a strength check skipped the front edge")
    if s.get("unknown") or not (s.get("pass") or s.get("estimate")):
        return _make("waiting", why="a check isn't settled")
    # a guessed print time isn't a ✓, and it doesn't stop a design being ready to cut (#166: with no slicer, nothing could be)
    return _make("holds", why="", guess=bool(s.get("estimate")))


# --- a goal held against a metric (the scorecard and the design card), and a number against what it needs ----------
#: A verdict kind as a scorecard check's status.
STATUS = {"holds": "pass", "fails": "fail", "untrusted": "untrusted", "unresolved": "unresolved",
          "unchecked": "unresolved", "edge": "edge", "stale": "unknown", "waiting": "unknown", "estimate": "estimate",
          "span": "span", "close": "pass", "recheck": "unknown"}   # close passes, in amber; an old number on its limit isn't settled


def goal(met: Optional[bool], *, untrusted: Optional[str] = None, unresolved: Optional[str] = None,
         edge: bool = False, stale: bool = False, incomplete: Optional[str] = None,
         estimate: Optional[str] = None, close: bool = False, recheck: Optional[str] = None,
         span: Optional[str] = None) -> dict:
    """A goal on a metric: ``met`` (None when there's no number). A ✗ stays a ✗ (a fail on a filled-in block is
    certain: the part as built is weaker still); then not trusted, not resolved, middle only, scored before the last
    change, a part left out, a number that's partly a guess (``estimate``, #166: a rough print time runs low, so a ✓
    on it is what rule 6 forbids). ``untrusted``/``unresolved``/``incomplete``/``estimate`` say why, as ``why``:
    a design's verdict never leaves a part out (#132 review: a part unchecked, older or errored is that, so the
    rest can't read as holding for it)."""
    if met is None:                            # no number: not checked, and why where it's known
        return _make("waiting", **({"why": incomplete} if incomplete else {}))
    if not met:
        return _make("fails")
    if untrusted:
        return _make("untrusted", why=untrusted)
    if unresolved:
        return _make("unresolved", why=unresolved)
    if span:
        return _make("span", why=span)
    if edge:
        return _make("edge")
    if stale:
        return _make("stale")
    if recheck:                                # a number from before a rounding fix, on its limit (#214)
        return _make("recheck", why=recheck)
    if incomplete:
        return _make("waiting", why=incomplete)
    if estimate:
        return _make("estimate", why=estimate)
    return _make("close" if close else "holds")


def compare(value: float, op: str, limit: float) -> bool:
    """A goal's number against its limit, as the goal says (``>=``, ``<=``, ``==``): the one place it's compared."""
    return value >= limit if op == ">=" else value <= limit if op == "<=" else abs(value - limit) < 1e-9


def rule(holds_now: Optional[bool]) -> dict:
    """A proposed rule on the part as it is: holds, fails, or not known yet (None: never a ✓, #132 review)."""
    return _make("waiting" if holds_now is None else "holds" if holds_now else "fails")


def meets(safety: Optional[float], need: Optional[float], *, stale: bool = False, close: bool = True,
          recheck: bool = False) -> dict:
    """A number against what it needs (a frame's weakest member, a station): holds or fails, or waiting; an older
    run's holds is ``stale`` (a fail stays a fail). ``close``: whether a pass near its limit is amber (a strength
    margin is; a tipping case's factor is its own judgement, not a strength margin)."""
    if safety is None or need is None:          # nothing to hold it to: not a pass (#132 review)
        return _make("waiting")
    if safety < need:
        return _make("fails", safety)
    if recheck and not stale:                   # an old number on its limit, from before the rounding fix (#214)
        return _make("recheck", safety, why=UNCUT)
    return _make("stale" if stale else "close" if close and near(safety, need) else "holds", safety)


def release(rel: dict, current: dict) -> dict:
    """A build package: ready only as made and for the parts as they are now (#132 review: "ready to cut" on a
    package of older versions). ``current``: ``{part: version}``."""
    if not rel.get("ready"):  # producer: the release's own verdict, made with summary() at release time
        v = summary((rel.get("card") or {}).get("summary"))    # its own reason: a fail, or waiting (#132 review)
        return v if not v["counts_as_pass"] else _make("waiting", why="it wasn't ready when it was made")
    older = any(current.get(k) not in (None, v) for k, v in (rel.get("versions") or {}).items())
    return _make("stale" if older else "holds")


def report(rep: Optional[dict]) -> dict:
    """A measured report (``Report.to_dict()``) as one verdict (#132 review): a fail only with a failure; passes
    with a check still waiting is waiting ("not all checked"); only waiting, or nothing, is "nothing checked yet",
    never red; else holds."""
    results = (rep or {}).get("results") or []
    statuses = [r.get("status") for r in results]
    if any(st in ("fail", "error") for st in statuses):
        return _make("fails", why=(rep or {}).get("said") or "a check fails")
    if "pass" in statuses and any(st not in ("pass",) for st in statuses):
        return {**_make("waiting", why=(rep or {}).get("said") or ""), "word": "not all checked"}
    if "pass" not in statuses:
        return {**_make("waiting", why="nothing checked yet"), "word": "nothing checked yet"}
    return _make("holds", why=(rep or {}).get("said") or "")


def history(h: dict) -> dict:
    """A revision's history line: the verdict it stored (``result``: a verdict kind), or, from before it did, the
    old ``all_pass``/``fail`` (single-part checks, which never waited)."""
    result = h.get("result")
    if result in KINDS:
        return {**_make(result, why=h.get("said") or ""), **({"word": h["word"]} if h.get("word") else {})}
    return _make("holds" if result == "all_pass" else "fails")  # producer: a record from before verdicts


def coarse(run: Optional[dict]) -> Optional[str]:
    """The kind a study's ✓ is when its voxels couldn't see the walls (CALI-106, #101: #100's rule for carve and
    lighten): ``unresolved`` (a finer run can), ``unchecked`` (none a study may make can), or None."""
    if not run or run.get("resolved") is not False:
        return None
    return "unchecked" if run.get("too_thin") else "unresolved"


def carve_step(st: dict, filled: Optional[str] = None, run: Optional[dict] = None) -> dict:
    """A carve step as a person reads it (#132 review): it holds only if the printed part holds there AND the whole
    part does (``whole_holds``), on a shape that isn't a filled-in block, at voxels that can see its walls (#101),
    and whose part closes up (#124). A fail stays a fail."""
    v = station(st)
    if v["kind"] in ("unchecked", "span"):      # its part doesn't close up (#124), or bends between its holds (CALI-153): said, not a fail
        return v
    if not v["counts_as_pass"]:
        return _make("fails", st.get("safety"))
    if st.get("whole_holds") is False:  # producer: the study's own number, judged here
        return _make("fails", st.get("whole"), why="the whole part doesn't hold there")
    if st.get("at_most"):               # Rule 6 (#228): no higher than the plywood as drawn, and how much lower isn't checked
        return _make("span", st.get("whole"), why=AT_MOST_WHY)
    if filled:
        return _make("untrusted", st.get("safety"), why=filled)
    if coarse(run):
        return _make(coarse(run), st.get("safety"))
    need = (run or {}).get("min_safety")        # an old number on its limit, the printed part's or the whole's (#214)
    if old_on_limit(run, st.get("safety"), need) or old_on_limit(run, st.get("whole"), need):
        return _make("recheck", st.get("safety"), why=UNCUT)
    return _make("holds", st.get("safety"))


def lighten_step(st: dict, filled: Optional[str] = None, run: Optional[dict] = None) -> dict:
    """A lightening step as a person reads it (#132 review): a thinner sheet's number is an estimate, never "holds";
    on a filled-in block, not trusted; on voxels that can't see the walls, not resolved (#101)."""
    v = station(st)
    if v["kind"] in ("fails", "span"):
        return v
    if st.get("estimate"):
        return _make("estimate", st.get("safety"))
    if filled:
        return _make("untrusted", st.get("safety"), why=filled)
    if coarse(run):
        return _make(coarse(run), st.get("safety"))
    if old_on_limit(run, st.get("safety"), (run or {}).get("min_safety")):   # an old number on its limit (#214)
        return _make("recheck", st.get("safety"), why=UNCUT)
    return v


def station(st: dict, *, whole: bool = False, run: Optional[dict] = None) -> dict:
    """A lighten or carve step: the carved part (or, ``whole``, the whole part at that step) holds or doesn't; a
    hold on voxels too coarse to see its walls is ``unresolved``/``unchecked`` (#101), and a fail stays a fail."""
    held = st.get("whole_holds" if whole else "holds")  # producer: the study's own number, judged here
    safety = st.get("whole" if whole else "safety")
    if held and st.get("closed") is False:     # a carved step whose part doesn't close up can't be adopted (#124)
        return _make("unchecked", safety, why=st.get("why") or "its shape doesn't close up")
    if held is None:
        return _make("waiting")
    if held and old_on_limit(run, safety, (run or {}).get("min_safety")):   # (#214 review)
        return _make("recheck", safety, why=UNCUT)
    if held and st.get("span"):                # the FEA alone, between its holds (CALI-153)
        return _make("span", safety, why=SPAN_WHY)
    if held and coarse(run):
        return _make(coarse(run), safety)
    return _make("holds" if held else "fails", safety)


def of(got: dict) -> dict:
    """A verdict carried on a result (``got["verdict"]``), or read from its flags: ``holds`` with ``unresolved``,
    ``filled``, ``middle_only`` (a picture's re-check, as #100–#106 wrote them)."""
    if got.get("verdict"):
        return got["verdict"]
    return goal(got.get("holds"), untrusted=got.get("filled") or None, unresolved="coarse" if got.get("unresolved") else None,
                edge=bool(got.get("middle_only")))
