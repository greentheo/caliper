"""CALI-29 — the chat turn handler: a message (optionally scoped to a clicked part) becomes a move.

This is the loop behind the conversation (``specs/caliper-conversational-spec.md`` §4). It adds no new
geometry machinery — every action it takes dispatches to the engine that already exists
(:func:`caliper.authoring.improve`, :func:`caliper.authoring.refine_authored`). What it adds is the
three things a conversation needs and the engine never had:

**1. Scope is the selection.** An unscoped message is about the design; a message scoped to a clicked
part is about *that part*. That single rule replaces most of the old control panel — no mode toggles,
no "pick 1 / pick 2" ceremony before a button un-greys.

**2. Refining a part that lives inside an assembly.** This did not exist. ``refine_authored`` operated
on a single-part run, and assembly members were static ``.py`` files with no revision path — so the
core interaction ("click the roller wheel, say what's wrong, watch it change") had no code path at all.
:func:`refine_part` closes it: read the part's script and spec out of the Design, revise it with the
**design context** in hand (siblings, mates, enforced assertions, prior feedback), write a new
snapshotted revision, and re-measure.

**3. Re-measuring the whole design, every time.** The discipline that separates this from a chat
wrapper around a CAD kernel: widening the carriage may break a clearance three parts away, so every
geometry change is measured against *every* mate and assembly assertion, and the turn reports what it
**broke** (and what it fixed) — in the same reply, by id, with the number.

Classification mirrors intake (CALI-5): Claude when a key is available, a deterministic offline parser
otherwise, and the classifier is injectable so tests never need a network.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .design import DesignStore
from .spec import Assertion, Spec

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")

#: What a brand-new part must clear before anything else is asked of it. A spec with no assertions can
#: never pass (:attr:`Report.all_pass` requires at least one considered check), so the author loop would
#: spin its full round budget for nothing.
BASELINE_ASSERTIONS = (
    Assertion(id="one_body", expr="body_count == 1"),
    Assertion(id="watertight", expr="is_watertight"),
)

_QUESTION_LEAD = {"what", "how", "why", "where", "which", "who", "when", "is", "are", "does", "do",
                  "can", "could", "show", "list", "tell", "status"}
_LEAD_FILLER = {"add", "also", "now", "please", "build", "create", "make", "generate", "give", "me",
                "a", "an", "the", "some", "another", "new", "insert", "put", "design", "model"}
_BREAK_WORDS = {"it", "its", "that", "this", "for", "to", "with", "on", "in", "into", "which", "and",
                "so", "at", "of", "from", "under", "over", "between", "next", "then"}
_ADD_VERBS = re.compile(r"\b(add|create|build|make|generate|model|design|insert|need)\b")
_REVERT = re.compile(r"\b(roll(\s+\w+)?\s*back|revert|undo|go\s+back|put\s+it\s+back)\b")


# ---------------------------------------------------------------------------
# Turn vocabulary
# ---------------------------------------------------------------------------
@dataclass
class Intent:
    """What the turn decided the message was asking for."""

    action: str                       # "refine" | "author" | "revert" | "answer"
    part: Optional[str] = None        # the part to revise, or the id for a new one
    intent: str = ""                  # for `author`: what the new part is
    source: str = "offline"           # "offline" | "llm" | "injected"
    note: str = ""                    # why we routed this way (surfaced when we're unsure)


@dataclass
class Event:
    """One step of progress, for narration. CALI-31 will stream these; today they're collected."""

    kind: str                         # classified | authoring | built | measured | wrote | done | error
    text: str
    data: dict = field(default_factory=dict)


@dataclass
class TurnResult:
    """Everything the chat needs to say back, plus the measured truth behind it."""

    action: str
    reply: str
    ok: bool = True
    part: Optional[str] = None
    version: Optional[int] = None
    part_report: Any = None           # the part's own spec, measured
    report: Any = None                # the WHOLE design, measured after the change
    broke: list[str] = field(default_factory=list)   # passed before, failing now
    fixed: list[str] = field(default_factory=list)   # failing before, passing now
    part_errors: dict = field(default_factory=dict)  # parts that wouldn't build
    events: list[Event] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Classification — offline first, Claude when available, injectable for tests
# ---------------------------------------------------------------------------
def _words(message: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", (message or "").lower())


def _is_question(message: str) -> bool:
    msg = (message or "").strip()
    if msg.endswith("?"):
        return True
    w = _words(msg)
    return bool(w) and w[0] in _QUESTION_LEAD


def part_id_from(message: str, existing: set[str]) -> str:
    """Derive a readable, unique, identifier-safe part id from "add a corner bracket" → ``corner_bracket``."""
    words = [w for w in _words(message) if not w[0].isdigit()]
    i = 0
    while i < len(words) and words[i] in _LEAD_FILLER:
        i += 1
    core: list[str] = []
    for w in words[i:]:
        if w in _BREAK_WORDS or w in _LEAD_FILLER:
            break
        core.append(w)
        if len(core) == 2:
            break
    base = "_".join(core) or "part"
    if base[0].isdigit():
        base = f"p_{base}"
    out, n = base, 1
    while out in existing:
        n += 1
        out = f"{base}_{n}"
    return out


def named_part(message: str, parts: list[str]) -> Optional[str]:
    """Which existing part does this message name? Longest match wins ('bar_v' beats 'bar')."""
    words = set(_words(message))
    hits = []
    for pid in parts:
        tokens = set(_words(pid))
        if tokens and tokens <= words:
            hits.append((len(tokens), pid))
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def last_touched(store: DesignStore) -> Optional[str]:
    """The part an unscoped "undo" most likely means — the one most recently revised."""
    if not store.design.parts:
        return None
    return max(store.design.parts, key=lambda p: p.updated).id


def offline_classify(store: DesignStore, message: str, scope: Optional[str] = None) -> Intent:
    """Deterministic routing — no network. Ask-don't-assume when genuinely ambiguous.

    The rules, in order: a scoped message is about that part unless it's a question; an unscoped
    message that names an existing part is about it; an "add/build a ..." is a new part; the first part
    of an empty design needs no naming ceremony. Anything else routes to ``answer`` with a nudge rather
    than guessing which part the user meant — a wrong guess spends an authoring run.
    """
    ids = [p.id for p in store.design.parts]
    question = _is_question(message)

    if _REVERT.search((message or "").lower()) and not question:
        target = scope or named_part(message, ids) or last_touched(store)
        if target:
            return Intent(action="revert", part=target, note="asks to undo the last change")

    if scope:
        if question:
            return Intent(action="answer", part=scope, note="a question about this part")
        return Intent(action="refine", part=scope, note="scoped to the clicked part")

    hit = named_part(message, ids)
    if hit and not question:
        return Intent(action="refine", part=hit, note=f"names the part {hit!r}")
    if question:
        return Intent(action="answer", part=hit, note="reads as a question")

    wants_new = bool(_ADD_VERBS.search((message or "").lower()))
    if wants_new or not ids:
        new_id = part_id_from(message, set(ids))
        return Intent(action="author", part=new_id, intent=(message or "").strip(),
                      note="the first part of the design" if not ids else "asks for a new part")

    return Intent(action="answer", note="ambiguous — no part named and no request to add one")


_CLASSIFY_SYSTEM = """You route a message in a CAD design conversation. Reply with ONLY a JSON object:

{"action": "refine" | "author" | "revert" | "answer", "part": "<existing part id, a new snake_case id, or null>",
 "intent": "<for author: a one-line description of the part to build; else empty>"}

- "refine": change an EXISTING part. `part` must be one of the design's part ids.
- "author": build a NEW part. `part` is a new snake_case identifier; `intent` describes it.
- "revert": undo the last change to a part ("roll it back", "undo that"). `part` is that part.
- "answer": the user asked a question or said something that changes no geometry.
If the message is ambiguous about WHICH part, use "answer" — do not guess."""


def llm_classify(store: DesignStore, message: str, scope: Optional[str] = None,
                 client=None, model: Optional[str] = None) -> Intent:
    """Route with Claude, given the design's parts as context. Raises on any failure (caller falls back)."""
    model = model or DEFAULT_MODEL
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()

    parts = "\n".join(f"  - {p.id}: {p.intent or '(no stated intent)'}" for p in store.design.parts)
    ask = (
        f"design goal: {store.design.prompt}\n\n"
        f"existing parts:\n{parts or '  (none yet)'}\n\n"
        + (f"the user has SELECTED the part '{scope}' — a request to change something almost certainly "
           f"means that part\n\n" if scope else "")
        + f"message: {message}"
    )
    msg = client.messages.create(model=model, max_tokens=300, system=_CLASSIFY_SYSTEM,
                                 messages=[{"role": "user", "content": ask}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)
    action = str(data.get("action", "")).strip()
    if action not in ("refine", "author", "revert", "answer"):
        raise ValueError(f"unusable action {action!r}")
    part = data.get("part") or None
    ids = {p.id for p in store.design.parts}
    if action in ("refine", "revert") and part not in ids:
        raise ValueError(f"{action} targets unknown part {part!r}")
    if action == "author":
        part = part if part and part not in ids else part_id_from(message, ids)
    return Intent(action=action, part=part, intent=str(data.get("intent") or message).strip(),
                  source="llm", note="routed by Claude")


Classifier = Callable[[DesignStore, str, Optional[str]], Intent]


def classify(store: DesignStore, message: str, scope: Optional[str] = None, *,
             use_llm: bool = True, client=None, classifier: Optional[Classifier] = None) -> Intent:
    """Claude when it's available, the deterministic parser otherwise — routing never hard-fails."""
    if classifier is not None:
        out = classifier(store, message, scope)
        out.source = out.source or "injected"
        return out
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            return llm_classify(store, message, scope, client=client)
        except Exception as e:  # noqa: BLE001 — routing must degrade, not crash the turn
            print(f"[chat] LLM routing failed → offline: {type(e).__name__}: {e}", file=sys.stderr)
    return offline_classify(store, message, scope)


# ---------------------------------------------------------------------------
# Measuring the whole design, and naming what a change broke
# ---------------------------------------------------------------------------
def _statuses(report) -> dict[str, str]:
    return {} if report is None else {r.id: r.status for r in report.results}


def _delta(before, after) -> tuple[list[str], list[str]]:
    """Which checks a change broke, and which it fixed — the point of re-measuring everything."""
    b, a = _statuses(before), _statuses(after)
    broke = [i for i, st in a.items() if st != "pass" and b.get(i) == "pass"]
    fixed = [i for i, st in a.items() if st == "pass" and b.get(i) not in (None, "pass")]
    return sorted(broke), sorted(fixed)


def _measure_design(store: DesignStore):
    """Measure the whole design, tolerantly. ``(None, {})`` when there's nothing to measure yet."""
    from .assembly import derived_assertions

    if not store.assembly.parts or not derived_assertions(store.assembly):
        return None, {}
    try:
        return store.evaluate(tolerant=True)
    except Exception as e:  # noqa: BLE001 — a measurement failure must not swallow the user's change
        return None, {"<design>": f"{type(e).__name__}: {e}"}


def _fail_lines(report, only: Optional[list[str]] = None, limit: int = 6) -> list[str]:
    if report is None:
        return []
    out = []
    for r in report.results:
        if r.status == "pass":
            continue
        if only is not None and r.id not in only:
            continue
        margin = "" if r.margin is None else f" (margin {r.margin:+.3g})"
        out.append(f"  • {r.id}: {r.expr} → actual={r.actual}{margin}")
    return out[:limit]


# ---------------------------------------------------------------------------
# The actions — each one dispatches to the EXISTING engine
# ---------------------------------------------------------------------------
def _working_spec(store: DesignStore, part_id: str, intent: str) -> Spec:
    """A throwaway spec carrying the design context, so a revision sees what it must not break.

    Deliberately a copy: :func:`~caliper.authoring.refine_authored` folds the instruction into
    ``spec.intent`` to keep it alive across rounds, and that must not leak into the part's stored spec.
    """
    spec = store.read_spec(part_id)
    if spec is None:
        spec = Spec(part=part_id, intent=intent, assertions=list(BASELINE_ASSERTIONS))
    else:
        spec = spec.model_copy(deep=True)
        if not spec.assertions:
            spec.assertions = list(BASELINE_ASSERTIONS)
    context = store.prompt_context(part_id)
    frame = ("\n\nBuild this part in the DESIGN'S WORLD COORDINATES (the other parts are already placed "
             "there); the assembly applies no extra transform." if len(store.design.parts) > 1 else "")
    spec.intent = f"{spec.intent or intent}\n\n--- design context ---\n{context}{frame}"
    return spec


def _emit(events: list[Event], on_event, kind: str, text: str, **data) -> None:
    ev = Event(kind=kind, text=text, data=data)
    events.append(ev)
    if on_event is not None:
        on_event(ev)


def refine_part(store: DesignStore, part_id: str, message: str, *, author=None, client=None,
                max_rounds: int = 4, events: Optional[list[Event]] = None, on_event=None) -> TurnResult:
    """Revise a part **that lives inside a design** and re-measure the whole thing.

    The gap CALI-29 exists to close. Everything here is plumbing around one existing call —
    :func:`~caliper.authoring.refine_authored` — except the two things that make it safe: the revision
    sees the design context (what else exists, what must keep holding), and the result is measured
    against the whole design rather than the part alone.
    """
    from . import authoring

    events = events if events is not None else []
    entry = store.design.part(part_id)
    if entry is None:
        return TurnResult(action="error", ok=False, part=part_id, events=events,
                          error=f"unknown part {part_id!r}",
                          reply=f"There's no part called '{part_id}' in this design.")
    if entry.origin == "imported" or not os.path.exists(store.script_path(part_id)):
        return TurnResult(action="error", ok=False, part=part_id, events=events,
                          error=f"{part_id} has no script to revise",
                          reply=(f"'{part_id}' is imported geometry — there's no script behind it to "
                                 f"revise. Re-author it as a new part if you want it to change."))

    before, _ = _measure_design(store)
    spec = _working_spec(store, part_id, entry.intent)
    script = store.read_script(part_id)

    _emit(events, on_event, "authoring", f"revising {part_id}…", part=part_id)
    res = authoring.refine_authored(spec, script, message, max_rounds=max_rounds,
                                    ref_base=store.root, author=author, client=client)

    if res.geometry is None:                      # never built — don't write a broken part
        _emit(events, on_event, "error", f"{part_id} would not build", part=part_id)
        return TurnResult(action="refine", ok=False, part=part_id, events=events,
                          error=res.error or "the revision never built",
                          reply=(f"I couldn't get '{part_id}' to build with that change after "
                                 f"{res.rounds} attempt(s). Last error:\n  {res.error}\n"
                                 f"The part is unchanged."))

    _emit(events, on_event, "built", f"{part_id} built in {res.rounds} round(s)", part=part_id)
    report_dict = res.report.to_dict() if res.report is not None else None
    version = store.write_part(part_id, res.script, feedback=message, action="refine",
                               report=report_dict)
    _emit(events, on_event, "wrote", f"{part_id} → v{version}", part=part_id, version=version)

    after, part_errors = _measure_design(store)
    _emit(events, on_event, "measured", "measured the whole design", part=part_id)
    broke, fixed = _delta(before, after)

    return TurnResult(action="refine", ok=bool(res.ok) and not broke, part=part_id, version=version,
                      part_report=res.report, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, events=events,
                      reply=_compose(store, part_id, version, res, after, broke, fixed, part_errors,
                                     verb="revised"))


def author_part(store: DesignStore, part_id: str, intent: str, *, author=None, client=None,
                max_rounds: int = 4, events: Optional[list[Event]] = None, on_event=None) -> TurnResult:
    """Author a brand-new part into the design, then measure the design with it in place."""
    from . import authoring

    events = events if events is not None else []
    before, _ = _measure_design(store)
    spec = _working_spec(store, part_id, intent)

    _emit(events, on_event, "authoring", f"authoring {part_id}…", part=part_id)
    res = authoring.improve(spec, author=author, max_rounds=max_rounds, client=client,
                            ref_base=store.root)

    if res.geometry is None:
        _emit(events, on_event, "error", f"{part_id} would not build", part=part_id)
        return TurnResult(action="author", ok=False, part=part_id, events=events,
                          error=res.error or "the part never built",
                          reply=(f"I couldn't build '{part_id}' after {res.rounds} attempt(s). Last "
                                 f"error:\n  {res.error}\nNothing was added to the design."))

    _emit(events, on_event, "built", f"{part_id} built in {res.rounds} round(s)", part=part_id)
    stored = Spec(part=part_id, intent=intent, parameters=spec.parameters,
                  assertions=[a.model_copy() for a in spec.assertions])
    report_dict = res.report.to_dict() if res.report is not None else None
    version = store.write_part(part_id, res.script, intent=intent, spec=stored, action="author",
                               feedback=intent, report=report_dict)
    _emit(events, on_event, "wrote", f"{part_id} → v{version}", part=part_id, version=version)

    after, part_errors = _measure_design(store)
    _emit(events, on_event, "measured", "measured the whole design", part=part_id)
    broke, fixed = _delta(before, after)

    return TurnResult(action="author", ok=bool(res.ok) and not broke, part=part_id, version=version,
                      part_report=res.report, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, events=events,
                      reply=_compose(store, part_id, version, res, after, broke, fixed, part_errors,
                                     verb="built"))


def revert_part(store: DesignStore, part_id: str, *, events=None, on_event=None) -> TurnResult:
    """Roll a part back one revision and re-measure — so the rollback the reply offers is real.

    :meth:`DesignStore.restore` writes it as a *new* revision, so undoing is itself part of the
    history rather than a hole in it.
    """
    events = events if events is not None else []
    entry = store.design.part(part_id)
    if entry is None:
        return TurnResult(action="error", ok=False, part=part_id, events=events,
                          error=f"unknown part {part_id!r}",
                          reply=f"There's no part called '{part_id}' in this design.")
    versions = store.versions(part_id)
    if len(versions) < 2:
        return TurnResult(action="error", ok=False, part=part_id, events=events,
                          error=f"{part_id} has only one version",
                          reply=f"'{part_id}' has only one version — there's nothing to roll back to.")

    before, _ = _measure_design(store)
    target = versions[-2]
    version = store.restore(part_id, target)
    _emit(events, on_event, "wrote", f"{part_id} rolled back to v{target} (saved as v{version})",
          part=part_id, version=version, restored_from=target)

    after, part_errors = _measure_design(store)
    _emit(events, on_event, "measured", "measured the whole design", part=part_id)
    broke, fixed = _delta(before, after)

    lines = [f"\u21a9 rolled **{part_id}** back to v{target} (saved as v{version})"]
    if fixed:
        lines.append(f"\u2713 That fixed: {', '.join(fixed)}")
    if broke:
        lines.append(f"\u26a0 But it broke: {', '.join(broke)}")
        lines.extend(_fail_lines(after, only=broke))
    if after is not None and after.all_pass:
        lines.append("The whole design measures green.")
    return TurnResult(action="revert", ok=(after is None or after.all_pass), part=part_id,
                      version=version, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, events=events, reply="\n".join(lines))


def answer(store: DesignStore, message: str, scope: Optional[str] = None,
           note: str = "", events: Optional[list[Event]] = None) -> TurnResult:
    """Report the measured state. No geometry moves — so the answer is facts, not an opinion."""
    events = events if events is not None else []
    d = store.design
    lines = [f"**{d.name}** — {d.prompt}" if d.prompt else f"**{d.name}**"]
    if d.requirements:
        lines.append("")
        lines.append("Clarified so far:")
        for r in d.requirements:
            mark = "" if r.source == "answered" else "  _(assumed)_"
            lines.append(f"  • {r.question} → {r.answer}{mark}")
    lines.append("")
    if d.parts:
        lines.append(f"{len(d.parts)} part(s):")
        for p in d.parts:
            mark = "  ← selected" if p.id == scope else ""
            lines.append(f"  • {p.id} (v{p.version}) — {p.intent or 'no stated intent'}{mark}")
    else:
        lines.append("No parts yet — tell me what to build first.")

    report, part_errors = _measure_design(store)
    for pid, err in part_errors.items():
        lines.append(f"  ⚠ {pid} won't build: {err}")
    if report is not None:
        failing = _fail_lines(report)
        lines.append("")
        lines.append("All design checks pass." if report.all_pass
                     else f"{len(failing)} design check(s) failing:")
        lines.extend(failing)
    if note.startswith("ambiguous"):
        lines.append("")
        lines.append("_If you meant to change a part, click it in the viewer or name it "
                     "(e.g. \"make the carriage 5mm wider\")._")
    return TurnResult(action="answer", ok=True, part=scope, report=report,
                      part_errors=part_errors, events=events, reply="\n".join(lines))


def _compose(store, part_id, version, res, after, broke, fixed, part_errors, verb: str) -> str:
    """The chat reply: what happened, what it measures, and — critically — what it broke."""
    head = "✓" if (res.ok and not broke) else "✗"
    lines = [f"{head} {verb} **{part_id}** → v{version} ({res.rounds} round(s))"]

    if res.report is not None:
        part_fails = _fail_lines(res.report)
        if part_fails:
            lines.append(f"{len(part_fails)} check(s) on this part still failing:")
            lines.extend(part_fails)
        else:
            lines.append("Every check on this part passes.")

    if broke:
        lines.append("")
        lines.append(f"⚠ This change **broke {len(broke)} design check(s)** that passed before:")
        lines.extend(_fail_lines(after, only=broke))
        lines.append("_Tell me how to fix it, or say **roll it back** to undo this revision._")
    if fixed:
        lines.append(f"✓ It also fixed: {', '.join(fixed)}")
    if not broke and after is not None and after.all_pass:
        lines.append("The whole design still measures green.")
    for pid, err in part_errors.items():
        if pid != part_id:
            lines.append(f"⚠ {pid} won't build: {err}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------
def turn(store: DesignStore, message: str, scope: Optional[str] = None, *, author=None, client=None,
         use_llm: bool = True, classifier: Optional[Classifier] = None, max_rounds: int = 4,
         on_event=None) -> TurnResult:
    """One conversational turn: route the message, make the move, measure the whole design, reply.

    ``scope`` is the part the user clicked (``None`` = the design). ``author``/``classifier`` are
    injectable so the whole turn is testable without a key; ``on_event`` receives progress as it
    happens (CALI-31 will stream these to the chat).
    """
    events: list[Event] = []
    intent = classify(store, message, scope, use_llm=use_llm, client=client, classifier=classifier)
    _emit(events, on_event, "classified", f"{intent.action}"
          + (f" → {intent.part}" if intent.part else ""),
          action=intent.action, part=intent.part, source=intent.source, note=intent.note)

    store.append_log({"kind": "message", "text": message, "scope": scope,
                      "action": intent.action, "part": intent.part, "routed_by": intent.source})

    if intent.action == "refine" and intent.part:
        result = refine_part(store, intent.part, message, author=author, client=client,
                             max_rounds=max_rounds, events=events, on_event=on_event)
    elif intent.action == "revert" and intent.part:
        result = revert_part(store, intent.part, events=events, on_event=on_event)
    elif intent.action == "author" and intent.part:
        result = author_part(store, intent.part, intent.intent or message, author=author,
                             client=client, max_rounds=max_rounds, events=events, on_event=on_event)
    else:
        result = answer(store, message, scope=scope or intent.part, note=intent.note, events=events)

    _emit(events, on_event, "done", result.action, ok=result.ok, part=result.part)
    store.append_log({"kind": "reply", "action": result.action, "part": result.part,
                      "version": result.version, "ok": result.ok,
                      "broke": result.broke, "fixed": result.fixed,
                      **({"error": result.error} if result.error else {})})
    return result
