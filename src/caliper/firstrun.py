"""CALI-59 (#8) — first run: one sentence in, four answers out (four-questions spec, step 5).

A new design used to stop after its questions with "Tell me which part to build first". Then it needed a
build, a strength requirement, a strength check and the patterns, each asked for in turn, before its cards
had anything to say: the stool took six messages and a couple of clicks. The first build does them in a
row, saying each as it goes:

1. **What it's held to:** the checks, from the sentence and the answers (CALI-55).
2. **Build it:** first the plan (CALI-35, #3a): with Claude, a planner splits the sentence into parts, the numbers
   they share and the checks between them. A plan of several parts stops here for the person's review; the stool
   plans as one part and goes on. Then the whole thing as one part, from the sentence and the answers. Its
   description is then rewritten from what was built (CALI-69).
3. **Will it work?** Its strength check, when it says what it must hold, at the safety its checks ask for.
4. **How do I make it?** The patterns, when it has flat sheet pieces.
5. **Scored:** what it's held to, judged (the cut plans' sheets and offcut too), so no check it was given
   reads "not checked yet".

A step that can't run says why, and the rest go on: the cards then say what's still missing. The reply
is the four answers, one line each, in words a kid can read.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from . import chat, goals, load_study, patterns
from .design import DesignStore
from .errors import scrubbed

#: A reply leads with what fails, then what holds, then what's still to check.
#: Worst first (#132 review): a fail, then a warning, then what holds, so the first reply's two lines never drop a
#: "not trusted" or "not resolved" under two "Holds…".
VERDICT_FIRST = ("bad", "warn", "ok", "info")
#: What the goals are written from, when it's the design's sentence and its answers that say it.
SAID = "(the design's goal and the answers to its questions)"


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
          author=None, strength: bool = True, cards: Optional[Callable] = None) -> dict:
    """Build a design that has no parts yet, check it and plan its making. Returns what each step did:
    ``{"part", "ok", "steps": {goals, build, strength, patterns}, "reply"}``.

    ``emit(kind, text, **data)`` hears each step (a job's emit). ``strength=False`` skips the strength check
    (whittle isn't installed). ``cards(store, pid)`` gives the part's four cards for the reply.
    """
    emit = emit or (lambda *a, **k: None)
    steps: dict = {}

    def forward(ev):
        emit(ev.kind, ev.text, **ev.data)

    emit("step", "Writing down what it has to do", step="goals")
    try:
        steps["goals"] = goals.reply(goals.update(store, SAID, use_llm=use_llm, client=client)) or "unchanged"
    except Exception as e:  # noqa: BLE001 — it builds without them; the cards say nothing's checked
        steps["goals"] = f"failed: {scrubbed(e)}"
        emit("error", f"couldn't write down what it has to do: {scrubbed(e)}")

    held = _plan(store, steps, emit, use_llm=use_llm, client=client, author=author)
    if held is not None:                       # a plan of several parts: the person reviews it first (CALI-35)
        return held

    pid, intent = first_part(store)
    emit("step", "Building it", step="build", part=pid)
    res = chat.author_part(store, pid, intent, author=author, client=client, use_llm=use_llm,
                           on_event=forward, promote_feedback=False)
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

    if _llm(use_llm, client):
        # what it is, as built: the sentence said what it's for, the script says what it is
        entry = store.design.part(pid)
        entry.intent = chat.redescribe(intent, "built from the design's goal and the answers to its questions",
                                       store.read_script(pid), use_llm=use_llm, client=client)
        store.save()

    script = store.read_script(pid) if store.is_scripted(pid) else ""
    if "def loads(" not in script:
        steps["strength"] = "it doesn't say what it must hold"
    elif not strength:
        steps["strength"] = "the strength check isn't installed"
    else:
        emit("step", "Checking it holds what it must", step="strength", part=pid)
        try:
            run = load_study.study(store, pid, min_safety=_min_safety(store),
                                   emit=lambda k, t="", **d: emit("strength", t, **d) if t else None)
            from .answers import ran_safety

            ran = ran_safety(run)                    # never 0x for a load that never reached a support (#140)
            steps["strength"] = f"{ran}x" if ran is not None else next(
                (f"not checked: {c['why']}" for c in run.get("cases") or []
                 if (c.get("fea") or {}).get("supported") is False and c.get("why")), "no verdict")
        except Exception as e:  # noqa: BLE001 — the card says it's not checked yet, with the button
            steps["strength"] = f"failed: {scrubbed(e)}"
            emit("error", f"couldn't check it holds: {scrubbed(e)}")

    try:
        flat = bool(patterns.pieces(store, pid))
    except Exception:  # noqa: BLE001 — no construction() it can read
        flat = False
    if flat:
        emit("step", "Drawing the patterns to cut it out", step="patterns", part=pid)
        try:
            rec = patterns.make(store, pid)
            steps["patterns"] = f"{rec['pages']} pages"
        except Exception as e:  # noqa: BLE001
            steps["patterns"] = f"failed: {scrubbed(e)}"
            emit("error", f"couldn't draw the patterns: {scrubbed(e)}")
    else:
        steps["patterns"] = "no flat pieces"

    if goals.read(store).get("checks"):
        emit("step", "Scoring it against what it has to do", step="score", part=pid)
        try:
            from . import scorecard

            card = scorecard.compute(store, emit=lambda k, t="", **d: emit("score", t, **d) if t else None)
            s_ = card["summary"]
            steps["score"] = f"{s_['pass']} pass, {s_['fail']} fail"
        except Exception as e:  # noqa: BLE001 — the card offers Score it
            steps["score"] = f"failed: {scrubbed(e)}"
            emit("error", f"couldn't score it: {scrubbed(e)}")
    else:
        steps["score"] = "nothing to hold it to"

    reply = summary(cards(store, pid)) if cards else res.reply
    if steps.get("plan", "").startswith("planning"):
        reply += f"\n\n({steps['plan'][0].upper()}{steps['plan'][1:]}.)"
    if steps.get("strength", "").startswith("failed: "):
        # said, not hidden behind a "Check it holds" that would fail the same way (CALI-81)
        reply += f"\n\n⚠ I couldn't check it holds: {steps['strength'][len('failed: '):]}."
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
