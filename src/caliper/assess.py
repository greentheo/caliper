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
import time
from typing import Optional

from . import llm
from .design import DesignStore

JOB = "assess"
#: The most readings one call may list.
MOST = 8
#: How long a reading's words may be.
LONGEST = 400
#: From this reading on, the offer says how many there have been.
SAY_COUNT_FROM = 4
#: What one reading costs, as the offer says it.
COST = "one Claude call, about 30–60 s"

#: A finding's kind (slice A) and the words a reading of the same thing uses: a reading over the same parts that says one
#: of these repeats the measured finding, and is dropped.
_SAME = {"fit": r"\b(?:fit|fits|pocket|slot|play|clearance|loose|tight)\b",
         "mirror": r"\bmirror",
         "rule": r"\b(?:touch|touches|miss|misses|gap|overlap|overlaps|interfere\w*)\b",
         "shadow": r"\b(?:cop(?:y|ies)|shared?|skeleton|own (?:copy|number))\b",
         "stated": r"\b(?:tall|long|height|length)\b"}

_SYSTEM = """You review a design that Caliper has built, part by part, before anyone checks its strength. You get what
the person asked for, what was settled with them, the plan (its parts, the numbers they share, the rules between them),
and every part: its intent, its version, its script and its measured size. You also get what Caliper has already
MEASURED wrong: never repeat one of those.

List what you read wrong that would stop it going together or doing what was asked: parts that don't meet, holes that
don't line up, a part sized for something else, a side that should mirror another and doesn't, a number the person gave
that a part ignores, a piece that looks too thin for what it carries. Only what you can point to in the scripts or the
sizes; no style advice, no "consider".

Reply with ONLY a JSON object:
{"readings": [{"parts": ["<part id>", ...], "said": "<what's wrong, one sentence, in the person's words>",
               "fix": "<the change you propose, one sentence, a thing the designer can do>"}]}
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
    """The design's last reading, or None."""
    files = _files(store)
    if not files:
        return None
    try:
        with open(files[-1][1]) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _versions(store: DesignStore) -> dict[str, int]:
    return {p.id: p.version for p in store.design.parts if p.version and store.is_scripted(p.id)}


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
    measured = "\n".join(f"  - [{f.get('kind')}] {f['said']} ({', '.join(f.get('parts') or [])})"
                         for f in found.get("findings") or [] if f.get("measured")) or "  (nothing)"
    return (f"WHAT THEY ASKED FOR: {d.prompt}\n\nSETTLED WITH THEM:\n{reqs}\n\nTHE PLAN'S PARTS:\n{planned}\n\n"
            f"NUMBERS THE PARTS SHARE:\n{skel}\n\nRULES BETWEEN PARTS:\n{rules}\n\nTHE PARTS AS BUILT:\n\n"
            + ("\n\n".join(parts) or "(none built)")
            + f"\n\nALREADY MEASURED WRONG (don't repeat these):\n{measured}")


def _repeats(r: dict, found: dict) -> bool:
    """Whether a reading says a measured finding again: the same parts, and the finding's kind in its words."""
    for f in found.get("findings") or []:
        if not f.get("measured") or set(f.get("parts") or []) != set(r["parts"]):
            continue
        words = _SAME.get(str(f.get("kind")))
        if words and re.search(words, f"{r['said']} {r['fix']}", re.I):
            return True
    return False


def parse(text: str, store: DesignStore, found: dict) -> dict:
    """The reply's readings, kept only where they name parts this design has built, say something and propose
    something, and don't repeat a measured finding: ``{"readings", "dropped", "repeats"}``. Raises ``ValueError`` where
    the reply isn't a list of readings at all."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        got = json.loads(m.group(0) if m else text)
    except (TypeError, ValueError):
        raise ValueError("the reading didn't come back in a form I can use") from None
    items = got.get("readings") if isinstance(got, dict) else None
    if not isinstance(items, list):
        raise ValueError("the reading didn't come back in a form I can use")
    built = set(_versions(store))
    out, dropped, repeats = [], 0, 0
    for it in items:
        parts = [p for p in (it.get("parts") or []) if isinstance(p, str) and p in built] if isinstance(it, dict) else []
        said = str(it.get("said") or "").strip()[:LONGEST] if isinstance(it, dict) else ""
        fix = str(it.get("fix") or "").strip()[:LONGEST] if isinstance(it, dict) else ""
        if not (parts and said and fix):
            dropped += 1
            continue
        r = {"parts": list(dict.fromkeys(parts)), "said": said, "fix": fix}
        if _repeats(r, found):
            repeats += 1
            continue
        out.append(r)
    dropped += max(0, len(out) - MOST)
    return {"readings": [{**r, "id": f"r{i + 1}"} for i, r in enumerate(out[:MOST])], "dropped": dropped,
            "repeats": repeats}


def _save(store: DesignStore, rec: dict) -> dict:
    os.makedirs(_dir(store), exist_ok=True)
    n = (_files(store)[-1][0] if _files(store) else 0) + 1
    rec = {"n": n, **rec}
    path = os.path.join(_dir(store), f"assess-{n}.json")
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=1)
    os.replace(tmp, path)
    return rec


def run(store: DesignStore, *, client=None, model: Optional[str] = None, found: Optional[dict] = None) -> dict:
    """Review it: one reading of the whole design, saved, and said (the route's body). Returns
    ``{"n", "at", "versions", "readings", "dropped", "repeats", "said", "ok"}``; ``ok`` False (and nothing saved) where
    Claude gave no usable reading, its reason in ``said``."""
    from . import review

    if found is None:
        try:
            found = review.findings(store)
        except Exception:  # noqa: BLE001 — the reading goes on; it's told nothing's measured
            found = {"findings": []}
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    try:
        msg = llm.ask(client, JOB, model=model, system=_SYSTEM,
                      messages=[{"role": "user", "content": context(store, found)}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        got = parse(text, store, found)
    except llm.Stopped as e:
        return {"ok": False, "readings": [], "said": f"No reading: {llm.said(e)}"}
    except ValueError as e:
        return {"ok": False, "readings": [], "said": f"No reading: {e}."}
    rec = _save(store, {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "versions": _versions(store), **got})
    return {**rec, "ok": True, "said": said(rec)}


def said(rec: dict) -> str:
    """A reading, as the reply says it: each one marked as Claude's reading, never as measured; an empty one says it's a
    reading, not a check."""
    n = len(rec.get("versions") or {})
    of = f"{n} part{'s' if n != 1 else ''}"
    readings = rec.get("readings") or []
    if not readings:
        return f"Claude read {of} and found nothing more. That's a reading, not a check: look at it."
    lines = [f"Claude's reading of {of} ({len(readings)} thing{'s' if len(readings) != 1 else ''}; read, not measured):"]
    lines += [f"- {r['said'][:1].upper()}{r['said'][1:]} ({', '.join(r['parts'])}). {r['fix']}" for r in readings]
    return "\n".join(lines)


def _nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def offer(store: DesignStore) -> dict:
    """What the Review it button says (the page's contract): ``{"label", "cost", "note", "stale", "count"}``. ``stale``:
    the parts the last reading read that have changed since, each with the version it read."""
    rec, n = latest(store), count(store)
    moved = stale(store, rec)
    label = "Review again" if rec else "Review it"
    note = f"{_nth(n + 1)} reading on this design" if n + 1 >= SAY_COUNT_FROM else ""
    return {"label": label, "cost": COST, "note": note, "stale": moved, "count": n}
