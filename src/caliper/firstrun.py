"""CALI-59 (#8) — first run: one sentence in, four answers out (four-questions spec, step 5).

A new design used to stop after its questions with "Tell me which part to build first". Then it needed a
build, a strength requirement, a strength check and the patterns, each asked for in turn, before its cards
had anything to say: the stool took six messages and a couple of clicks. The first build now does the minimum, and shows it (CALI-157):

1. **Build it:** first the plan (CALI-35, #3a): with Claude, a planner splits the sentence into parts, the numbers they share and the checks
   between them. A plan of several parts stops here for the person's review; the stool plans as one part and goes on.
2. **The part, on screen,** as soon as one script builds: one automatic repair at most, for a script that doesn't build or pieces that don't
   account for the solid. Anything else that fails is told to the person, so corrections can start.

Whether it holds, the patterns and the score are there to click when it looks right. The reply is the four answers, one line each, in words a
kid can read, and the card says "not checked yet" until the check runs.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from . import chat, goals, load_study
from .design import DesignStore
from .errors import scrubbed

#: A reply leads with what fails, then what holds, then what's still to check.
#: Worst first (#132 review): a fail, then a warning, then what holds, so the first reply's two lines never drop a
#: "not trusted" or "not resolved" under two "Holds…".
VERDICT_FIRST = ("bad", "warn", "ok", "info")
#: What the goals are written from, when it's the design's sentence and its answers that say it.


#: A first build's designer tries: the first, and one repair (CALI-157). Only what stops it being shown right is repaired: a script that
#: doesn't build always is, and these checks: pieces that don't account for the solid. Anything else is told to the person.
FIRST_ROUNDS = 2
REPAIRS = frozenset({"construction_covers", "construction_volume"})


def first_part(store: DesignStore) -> tuple[str, str]:
    """What to build first, and as what: the whole thing, as one part named for what it is."""
    prompt = store.design.prompt.strip()
    return chat.part_id_from(prompt, {p.id for p in store.design.parts}), prompt


def _llm(use_llm: bool, client) -> bool:
    return use_llm and (client is not None or bool(os.environ.get("ANTHROPIC_API_KEY")))


def _min_safety(store: DesignStore) -> float:
    """The safety its checks ask for (the strictest), else the strength check's own."""
    asks = [c["limit"] for c in goals.read(store).get("checks") or []
            if c.get("metric") == "strength.safety" and c.get("source") != "proposed" and c.get("limit")]
    return max(asks) if asks else load_study.MIN_SAFETY


def build(store: DesignStore, *, emit: Optional[Callable] = None, use_llm: bool = True, client=None,
          author=None, cards: Optional[Callable] = None) -> dict:
    """Build a design that has no parts yet, and show it: the minimum, so corrections can start (CALI-157). Whether it holds, its patterns and
    its score wait to be asked for. Returns ``{"part", "ok", "steps": {build}, "reply"}``.

    ``emit(kind, text, **data)`` hears each step (a job's emit). ``cards(store, pid)`` gives the part's four cards for the reply.
    """
    emit = emit or (lambda *a, **k: None)
    steps: dict = {}

    def forward(ev):
        emit(ev.kind, ev.text, **ev.data)

    held = _plan(store, steps, emit, use_llm=use_llm, client=client, author=author)
    if held is not None:                       # a plan of several parts: the person reviews it first (CALI-35)
        return held

    pid, intent = first_part(store)
    emit("step", "Building it", step="build", part=pid)
    res = chat.author_part(store, pid, intent, author=author, client=client, use_llm=use_llm,
                           on_event=forward, promote_feedback=False, max_rounds=FIRST_ROUNDS, repair_only=REPAIRS)
    steps["build"] = "built" if res.version else f"failed: {res.error}"
    store.append_log({"kind": "firstrun", "action": "built" if res.version else "failed", "part": pid,
                      "version": res.version})
    if not res.version:
        store.append_log({"kind": "reply", "action": "author", "part": pid, "ok": False, "reply": res.reply,
                          "error": res.error})
        return {"part": pid, "ok": False, "steps": steps, "reply": res.reply}
    entry = store.design.part(pid)                    # a one-part design's part is called what the design is (#94)
    if entry is not None and not entry.label:
        entry.label = store.design.name
        store.save()

    reply = summary(cards(store, pid)) if cards else res.reply
    short = [r for r in (res.part_report.results if res.part_report is not None else []) if r.id in REPAIRS and not r.passed]
    if short:                                   # what the one repair couldn't fix comes first, never "I built it" over it
        reply = ("I built it, but its 3D shape and its pieces still don't match after one repair: the What is it? card says where. "
                 "Say what to change and I'll revise it.\n\n" + reply)
    if steps.get("plan", "").startswith("planning"):
        reply += f"\n\n({steps['plan'][0].upper()}{steps['plan'][1:]}.)"
    store.append_log({"kind": "reply", "action": "author", "part": pid, "version": res.version,
                      "ok": bool(res.ok), "reply": reply, "firstrun": True})
    emit("step", "Done", step="done", part=pid)
    return {"part": pid, "ok": bool(res.ok), "version": res.version, "steps": steps, "reply": reply}


def _plan(store: DesignStore, steps: dict, emit: Callable, *, use_llm: bool, client, author=None) -> Optional[dict]:
    """CALI-35 (#3a): plan before building. Returns the first run's result when it stops for the plan (a plan of
    several parts, to review), or when it builds a reviewed plan's parts in order (#3b); else None and it builds as
    one part."""
    from . import build_plan
    from . import plan as P

    saved = P.load(store)
    if saved is not None and len(P.buildable(saved)) > 1:      # reviewed: Build it builds its parts, in order (#3b)
        return build_plan.build(store, steps, emit, author=author, client=client, use_llm=use_llm)
    if not _llm(use_llm, client):
        steps["plan"] = "planning it in several parts needs Claude: I built it as one"
        return None
    emit("step", "Planning its parts", step="plan")
    try:
        plan = P.propose(store, client=client)
    except Exception as e:  # noqa: BLE001 — a plan that can't be made or used: build it as one part, and say why
        steps["plan"] = f"planning it in several parts didn't work ({scrubbed(e)}): I built it as one"
        emit("error", f"couldn't plan its parts: {scrubbed(e)}")
        return None
    if len(P.buildable(plan)) <= 1:            # what it stands on, or what you have, doesn't stop it for review (#117)
        gone = P.dropped_line(plan)
        steps["plan"] = "one part" + (f" ({gone})" if gone else "")
        return None
    P.save(store, plan, "review")
    gone = P.dropped_line(plan)                # never dropped without a word (#123 review)
    reply = (P.headline(plan, store.design.name) + (f" ({gone[0].upper() + gone[1:]}.)" if gone else "")
             + P.said_aside(plan)
             + "\n\nThat's the plan, before anything's drawn: its numbers and the "
             "checks between the parts are under What is it?. Say what to change (\"make the mast 10 ft\"), or "
             "**Build it** to go on: " + build_plan.cost(plan) + ".")      # the cost, said first (#135 review)
    store.append_log({"kind": "reply", "action": "plan", "ok": True, "reply": reply, "firstrun": True,
                      "parts": plan.ids()})
    steps["plan"] = f"{len(plan.parts)} parts, to review"
    emit("step", "Done", step="done")
    return {"part": None, "ok": True, "steps": steps, "reply": reply, "plan": "review"}


def summary(cards: list[dict]) -> str:
    """The four answers as the reply: each question and its top line or two. Where a card has verdicts
    (will it work, how to make it), a failure comes first, then what holds, then the rest."""
    lines = ["I built it. Here's what I found:", ""]
    for c in cards:
        said = [ln for ln in c["lines"] if ln["text"]]
        if c["key"] in ("work", "make"):
            said = sorted(said, key=lambda ln: VERDICT_FIRST.index(ln["status"]))
        text = [ln["text"] if ln["text"][-1] in ".!?…" else ln["text"] + "." for ln in said[:2]]
        if text:
            lines.append(f"- **{c['q']}** " + " ".join(text))
    if any(c.get("promise") for c in cards):           # a strength verdict says what it promises (CALI-86)
        lines += ["", next(c["promise"] for c in cards if c.get("promise"))]
    lines += ["", "Click a card on the right to see it, or ask me why."]
    return "\n".join(lines)
