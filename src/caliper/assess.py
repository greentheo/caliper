"""CALI-160 (#238), slice B — Review it: Claude reads every part against the request, and says what it reads wrong.

Slice A (:mod:`review`) lists what's **measured** wrong after a build, with no model call. Some of what's wrong no check
measures ("the legs look thin for 300 lb", "the flange bolt holes don't line up with the top's"). Here, on the person's
press and never by itself, one Claude call (the ``assess`` job) reads the request, the plan, the skeleton and every
part's script and size, with slice A's findings as already found, and lists what it reads wrong: each reading names its
parts, says what's wrong in the person's words, and proposes the change.

**Rule 6, kept apart.** A reading is never a measurement:

- each one goes under Things to fix badged **Claude's reading** (``fixes._reading_rows``), and after Fix these it's
  **done, not measured**, never fixed (``fixing.apply``);
- an empty reading says "found nothing more; that's a reading, not a check: look at it", never that it's right.

**Kept, not re-asked.** Each reading is saved in the design (``reviews/assess-<n>.json``) with the part versions it read.
When a part moves on, its readings say "read on v3; it's changed since", and Review it is offered again. No cap: each
reading is the person's own press, and from the fourth on the offer says how many there have been (:func:`offer`).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Optional

from . import llm
from .design import DesignStore
from .errors import scrubbed

JOB = "assess"
#: The most readings one call may list.
MOST = 8
#: How long a reading's words may be.
LONGEST = 400
#: From this reading on, the offer says how many there have been.
SAY_COUNT_FROM = 4
#: What one reading costs, as the offer says it.
COST = "one Claude call, about 30–60 s"

_SYSTEM = """You review a design that Caliper has built, part by part, before anyone checks its strength. You get what
the person asked for, what was settled with them, the plan (its parts, the numbers they share, the rules between them),
and every part: its intent, its version, its script and its measured size. You also get what Caliper has already
MEASURED wrong, each with an id (m1, m2, …): never repeat one of those. If a point you'd make IS one of them, leave it out;
if you can't tell, make it and put the measured one's id in "same_as".

List what you read wrong that would stop it going together or doing what was asked: parts that don't meet, holes that
don't line up, a part sized for something else, a side that should mirror another and doesn't, a number the person gave
that a part ignores, a piece that looks too thin for what it carries. Only what you can point to in the scripts or the
sizes; no style advice, no "consider".

Name each part by its id, or a piece of one by the name its script declares ("front_rail").

Reply with ONLY a JSON object:
{"readings": [{"parts": ["<part id or piece name>", ...], "said": "<what's wrong, one sentence, in the person's words>",
               "fix": "<the change you propose, one sentence, a thing the designer can do>",
               "same_as": "<a measured id, only where it may be the same thing; else leave it out>"}]}
At most 8, the worst first. Part ids exactly as given. An empty list when you find nothing more."""


def _dir(store: DesignStore) -> str:
    return os.path.join(store.root, "reviews")


def _files(store: DesignStore) -> list[tuple[int, str]]:
    try:
        names = os.listdir(_dir(store))
    except OSError:
        return []
    out = []
    for name in names:
        m = re.fullmatch(r"assess-(\d+)\.json", name)
        if m:
            out.append((int(m.group(1)), os.path.join(_dir(store), name)))
    return sorted(out)


def count(store: DesignStore) -> int:
    """How many readings this design has had."""
    return len(_files(store))


def latest(store: DesignStore) -> Optional[dict]:
    """The design's last reading, or None. One that can't be read (a crash between taking its number and writing it) is
    passed over for the one before (#368 re-check: the earlier readings' rows vanished)."""
    for _, path in reversed(_files(store)):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return None


def _versions(store: DesignStore) -> dict[str, int]:
    return {p.id: p.version for p in store.design.parts if p.version and store.is_scripted(p.id)}


def unread(store: DesignStore, rec: Optional[dict]) -> list[str]:
    """The parts built now that a reading never read: added since (#368 review: the offer couldn't say "frame wasn't
    read")."""
    if not rec:
        return []
    return [pid for pid in _versions(store) if pid not in (rec.get("versions") or {})]


def stale(store: DesignStore, rec: Optional[dict]) -> dict[str, int]:
    """The parts a reading read that have changed since, each with the version it read (gone parts too)."""
    if not rec:
        return {}
    now = _versions(store)
    return {pid: v for pid, v in (rec.get("versions") or {}).items() if now.get(pid) != v}


def _box(store: DesignStore, pid: str) -> str:
    """A part's measured size, as the reading is shown it; said where it can't be measured, never guessed."""
    from . import measure

    try:
        b = measure.bounding_box(store.part_geometry(pid))
        return (f"{b.dx:.1f} x {b.dy:.1f} x {b.dz:.1f} mm, from ({b.min_x:.1f}, {b.min_y:.1f}, {b.min_z:.1f}) "
                f"to ({b.max_x:.1f}, {b.max_y:.1f}, {b.max_z:.1f})")
    except Exception as e:  # noqa: BLE001 — the reading goes on without it, and is told so
        return f"not measured ({type(e).__name__})"


def context(store: DesignStore, found: dict) -> str:
    """What the reading is given: the request, what was settled, the plan, every built part (script and size), and what's
    already measured wrong."""
    d = store.design
    reqs = "\n".join(f"  - {r.question} -> {r.answer}" + ("" if r.source == "answered" else " [assumed]")
                     for r in d.requirements) or "  (none)"
    plan = d.plan or {}
    planned = "\n".join(f"  - {p.get('id')}: {p.get('what', '')}" + (f" (made: {p['made']})" if p.get("made") else "")
                        + (f", mounts on {', '.join(p['mounts_on'])}" if p.get("mounts_on") else "")
                        + (f", the mirror of {p['mirror_of']}" if p.get("mirror_of") else "")
                        for p in plan.get("parts") or []) or "  (no plan: the parts as built)"
    skel = "\n".join(f"  - {s.get('name')} = {s.get('value')} {s.get('unit', '')}" + (f" ({s['why']})" if s.get("why") else "")
                     for s in d.skeleton or []) or "  (none)"
    rules = "\n".join(f"  - {a.id}: {a.expr}" for a in store.assembly.assertions) or "  (none)"
    parts = []
    for p in d.parts:
        if not (p.version and store.is_scripted(p.id)):
            continue
        parts.append(f"### {p.id} (v{p.version}): {p.intent or '(no stated intent)'}\nmeasured size: {_box(store, p.id)}\n"
                     f"```python\n{store.read_script(p.id)}\n```")
    measured = "\n".join(f"  - {mid}: [{f.get('kind')}] {f['said']} ({', '.join(f.get('parts') or [])})"
                         for mid, f in _measured(found).items()) or "  (nothing)"
    return (f"WHAT THEY ASKED FOR: {d.prompt}\n\nSETTLED WITH THEM:\n{reqs}\n\nTHE PLAN'S PARTS:\n{planned}\n\n"
            f"NUMBERS THE PARTS SHARE:\n{skel}\n\nRULES BETWEEN PARTS:\n{rules}\n\nTHE PARTS AS BUILT:\n\n"
            + ("\n\n".join(parts) or "(none built)")
            + f"\n\nALREADY MEASURED WRONG (don't repeat these):\n{measured}")


def _measured(found: dict) -> dict[str, dict]:
    """The measured findings by the id the reading is shown them by: ``{"m1": finding, …}``."""
    return {f"m{i + 1}": f for i, f in enumerate(f for f in found.get("findings") or [] if f.get("measured"))}


def _repeats(r: dict, same_as, found: dict) -> Optional[dict]:
    """The measured finding a reading is set aside as repeating: only where Claude says so (``same_as``) and it names that
    finding's parts (#368 review: a list of kind words dropped different problems, strength among them). None otherwise."""
    f = _measured(found).get(str(same_as or "").strip())
    return f if f is not None and set(f.get("parts") or []) == set(r["parts"]) else None


def _may_repeat(same_as, found: dict) -> Optional[str]:
    """The measured finding a kept reading may say again: only where Claude's own ``same_as`` names one (on other parts,
    or it would be set aside). Never from words (#368 re-check: a thin stringer was badged with an unrelated height)."""
    f = _measured(found).get(str(same_as or "").strip())
    return f["said"] if f is not None else None


def _norm(name: str) -> str:
    return re.sub(r"^the ", "", re.sub(r"[\s_-]+", " ", str(name).strip().lower()))


def _part_of(store: DesignStore, name, built: list[str], loose: bool = True) -> Optional[str]:
    """The part a reading names, by its id, as it's said ("step stool") or by its label ("Step stool"), normalised; or by
    words only one part's name has ("stool"). None where it names none (#368 review: every label was dropped)."""
    if not isinstance(name, str) or not name.strip():
        return None
    want = _norm(name)
    labels = {pid: (store.design.part(pid).label or "") if store.design.part(pid) else "" for pid in built}
    for pid in built:                           # an id first: ids are unique, a label is only what it's shown as
        if want == _norm(pid):
            return pid
    for pid in built:
        if labels[pid] and want == _norm(labels[pid]):
            return pid
    if not loose:
        return None
    words = set(want.split())
    hits = [pid for pid in built if words and words <= set(_norm(pid).split()) | set(_norm(labels[pid]).split())]
    return hits[0] if len(hits) == 1 else None


#: Why a point of Claude's was set aside, as the reply says it.
NO_PART, NOTHING, REPEAT, OVER = "named no part here", "said nothing to change", "repeated a measured finding", "past the 8"


def _piece_of(store: DesignStore, name, built: list[str], seen: dict, loose: bool = True) -> Optional[dict]:
    """The piece a reading names, as its part's script declares it or the tree labels it ("front rail", "left side"), with
    the part that declares it: ``{part, piece, name}``; None where it names none, or two (#368 re-check: on a one-part
    stool every piece-named point was set aside). ``seen`` keeps each part's pieces for the reply."""
    from . import tree

    if not isinstance(name, str) or not name.strip():
        return None
    for pid in built:
        if pid not in seen:
            try:
                seen[pid] = tree.pieces(store, pid)
            except Exception:  # noqa: BLE001 — a part that won't declare names no piece
                seen[pid] = []
    every = [(pid, pc) for pid in built for pc in seen[pid]]
    want = _norm(name)
    words = set(want.split())
    tests = [lambda k: want in k,                                      # its key or its label, as written
             lambda k: any(words == set(x.split()) for x in k)]        # the same words in another order ("left side")
    if loose:
        tests.append(lambda k: words and any(words <= set(x.split()) for x in k))   # words only one piece has
    for test in tests:
        hits = [(pid, pc) for pid, pc in every if test({_norm(pc["key"]), _norm(pc.get("name") or "")} - {""})]
        if len(hits) == 1:
            pid, pc = hits[0]
            return {"part": pid, "piece": pc["key"], "name": (pc.get("name") or pc["key"]).replace("_", " ")}
        if hits:
            return None
    return None


def parse(text: str, store: DesignStore, found: dict) -> dict:
    """The reply's readings: ``{"readings", "set_aside", "dropped", "repeats"}``. Each kept one names parts this design
    has built (by id or label), says something and proposes something. Every point set aside keeps its words and why
    (#368 review: "found nothing more" over three readings thrown away). Raises ``ValueError`` where the reply isn't a
    list of readings at all."""
    start = (text or "").find("{")
    try:                                        # the first object only: a brace after it is prose (#368 review)
        got = json.JSONDecoder().raw_decode(text[start:])[0] if start >= 0 else None
    except (TypeError, ValueError):
        got = None
    items = got.get("readings") if isinstance(got, dict) else None
    if not isinstance(items, list):
        raise ValueError("the reading didn't come back in a form I can use")
    built = list(_versions(store))
    out, aside, seen = [], [], {}
    for it in items:
        if not isinstance(it, dict):              # a bare sentence: its words kept, said as naming no part
            aside.append({"said": str(it).strip()[:LONGEST], "fix": "", "named": [], "why": NO_PART})
            continue
        named = [str(p) for p in (it.get("parts") or []) if isinstance(p, str)]
        parts, pieces = [], []
        for n in named:                             # a part by id or label; else a piece, and its part (#368 re-check)
            pid = _part_of(store, n, built, loose=False)               # exact names first: a part's, then a piece's,
            pc = None if pid else _piece_of(store, n, built, seen, loose=False)   # then words only one of either has
            pid = pid or (None if pc else _part_of(store, n, built))
            pc = pc or (None if pid else _piece_of(store, n, built, seen))
            if pc:
                pieces.append(pc)
            if pid or pc:
                parts.append(pid or pc["part"])
        parts = list(dict.fromkeys(parts))
        said = str(it.get("said") or "").strip()[:LONGEST]
        fix = str(it.get("fix") or "").strip()[:LONGEST]
        if not (said and fix):
            aside.append({"said": said, "fix": fix, "named": named, "why": NOTHING})
            continue
        if not parts:
            aside.append({"said": said, "fix": fix, "named": named, "why": NO_PART})
            continue
        r = {"parts": parts, **({"pieces": pieces} if pieces else {}), "said": said, "fix": fix}
        same = _repeats(r, it.get("same_as"), found)
        if same is not None:
            aside.append({**r, "named": named, "why": REPEAT, "repeats": same["said"]})
            continue
        maybe = _may_repeat(it.get("same_as"), found)
        out.append({**r, **({"may_repeat": maybe} if maybe else {})})
    aside += [{**r, "named": r["parts"], "why": OVER} for r in out[MOST:]]
    return {"readings": [{**r, "id": f"r{i + 1}"} for i, r in enumerate(out[:MOST])], "set_aside": aside,
            "dropped": sum(1 for a in aside if a["why"] != REPEAT), "repeats": sum(1 for a in aside if a["why"] == REPEAT)}


def _save(store: DesignStore, rec: dict) -> dict:
    """The reading as the next ``assess-<n>.json``, its number taken by creating the file, so two never share one (#368
    review: two presses could both write the same n)."""
    os.makedirs(_dir(store), exist_ok=True)
    n = (_files(store)[-1][0] if _files(store) else 0) + 1
    while True:
        path = os.path.join(_dir(store), f"assess-{n}.json")
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            n += 1
    rec = {"n": n, **rec}
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=1)
    os.replace(tmp, path)
    return rec


_RUNNING: dict = {}
_RUNNING_MU = threading.Lock()


def _one_at_a_time(store: DesignStore) -> threading.Lock:
    with _RUNNING_MU:
        return _RUNNING.setdefault(os.path.realpath(store.root), threading.Lock())


#: What a second press says while a reading of the design is running (#368 review).
BUSY = "A reading of this design is already running: its answer comes first."


def run(store: DesignStore, *, client=None, model: Optional[str] = None, found: Optional[dict] = None) -> dict:
    """Review it: one reading of the whole design, saved, and said (the route's body). Returns
    ``{"n", "at", "versions", "readings", "set_aside", "dropped", "repeats", "said", "ok"}``; ``ok`` False (and nothing
    saved) where Claude gave no usable reading, its reason in ``said``, or where a reading of the design is already
    running (``busy``: one at a time, #368 review)."""
    lock = _one_at_a_time(store)
    if not lock.acquire(blocking=False):
        return {"ok": False, "busy": True, "readings": [], "said": BUSY}
    try:
        return _run(store, client=client, model=model, found=found)
    finally:
        lock.release()


def _run(store: DesignStore, *, client=None, model: Optional[str] = None, found: Optional[dict] = None) -> dict:
    from . import review

    if found is None:
        try:
            found = review.findings(store)
        except Exception:  # noqa: BLE001 — the reading goes on; it's told nothing's measured
            found = {"findings": []}
    try:
        if client is None:
            from .llm import client as _claude  # CALI-217 (#366): no key is said in the reply, never a crash

            client = _claude()
        msg = llm.ask(client, JOB, model=model, system=_SYSTEM,
                      messages=[{"role": "user", "content": context(store, found)}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        got = parse(text, store, found)
    except llm.Stopped as e:
        return {"ok": False, "readings": [], "said": f"No reading: {llm.said(e)}"}
    except ValueError as e:
        return {"ok": False, "readings": [], "said": f"No reading: {scrubbed(e)}."}
    rec = _save(store, {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "versions": _versions(store), **got})
    return {**rec, "ok": True, "said": said(rec)}


def _aside_said(aside: list[dict], total: int) -> str:
    """"2 of Claude's 5 points were left out: 1 named no part here, 1 repeated a measured finding"."""
    whys: dict = {}
    for a in aside:
        whys[a["why"]] = whys.get(a["why"], 0) + 1
    n = len(aside)
    return (f"{n} of Claude's {total} point{'s' if total != 1 else ''} {'was' if n == 1 else 'were'} left out: "
            + ", ".join(f"{c} {w}" for w, c in whys.items()) + ".")


def _where(r: dict) -> str:
    """What a reading names: its pieces with their part ("front rail on step_stool"), and any part named as a whole."""
    whole = [p for p in r["parts"] if not any(pc["part"] == p for pc in r.get("pieces") or [])]
    return ", ".join([f"{pc['name']} on {pc['part']}" for pc in r.get("pieces") or []] + whole)


def said(rec: dict) -> str:
    """A reading, as the reply says it: each one marked as Claude's reading, never as measured; what was set aside counted,
    with why. "Found nothing more" only where Claude said nothing more and nothing was set aside (#368 review)."""
    n = len(rec.get("versions") or {})
    of = f"{n} part{'s' if n != 1 else ''}"
    readings, aside = rec.get("readings") or [], rec.get("set_aside") or []
    left = _aside_said(aside, len(readings) + len(aside)) if aside else ""
    if not readings and not aside:
        return f"Claude read {of} and found nothing more. That's a reading, not a check: look at it."
    if not readings:
        return f"Claude read {of}, and none of what it said could be kept: {left[:1].lower()}{left[1:]} Look at it yourself."
    lines = [f"Claude's reading of {of} ({len(readings)} thing{'s' if len(readings) != 1 else ''}; read, not measured):"]
    lines += [f"- {r['said'][:1].upper()}{r['said'][1:]} ({_where(r)}). {r['fix']}"
              + (f" (May repeat what's measured: {r['may_repeat']}.)" if r.get("may_repeat") else "") for r in readings]
    return "\n".join(lines + ([left] if left else []))


def _nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def offer(store: DesignStore) -> dict:
    """What the Review it button says (the page's contract): ``{"label", "cost", "note", "stale", "unread", "count"}``.
    ``stale``: the parts the last reading read that have changed since (or gone), each with the version it read;
    ``unread``: the parts built since that it never read."""
    rec, n = latest(store), count(store)
    moved = stale(store, rec)
    label = "Review again" if rec else "Review it"
    note = f"{_nth(n + 1)} reading on this design" if n + 1 >= SAY_COUNT_FROM else ""
    return {"label": label, "cost": COST, "note": note, "stale": moved, "unread": unread(store, rec), "count": n}
