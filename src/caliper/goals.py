"""CALI-55 (#2) — what a design is held to, written from the conversation.

The scorecard (CALI-47) judges a design against ``scorecard.yaml``: checks with limits, and objectives.
Until now someone wrote that file by hand. Here the conversation writes it. After the clarify round, and
after any turn that says what the design must do, Claude reads what was said and keeps the checks up to
date. Every check says where it came from:

- ``stated``: the person said it ("it has to hold me too (200 lb)"), and the check keeps their words.
- ``assumed``: it rests on an answer Caliper assumed, or on a number the person didn't give (the
  safety factor behind "hold me"). It binds, and it's shown so it's easy to confirm or change.
- ``proposed``: nobody said it, but the design needs it (what it holds, what holds it up, whether a kid
  can carry it). It doesn't bind until the person keeps it, like feedback promoted to a rule (CALI-30).
  A proposal they drop isn't offered again.

A goals file somebody wrote by hand (no ``written_by: caliper``) is theirs: Caliper reads it and never
rewrites it.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from .design import DesignStore

SOURCES = ("stated", "assumed", "proposed", "confirmed")
MARK = "caliper"

#: What a check can be written against: the scorecard's metrics a conversation is likely to name. Each is
#: (what it measures, unit, the usual direction).
METRICS = {
    "strength.safety": ("the worst safety factor of every load the parts must carry (their loads())", "×", ">="),
    "strength.breaks_lb": ("the smallest predicted breaking load; only when the person names a breaking load "
                           "(\"it must take 500 lb before it breaks\"), never beside strength.safety", "lb", ">="),
    "weight.total_lb": ("what the whole design weighs", "lb", "<="),
    "cost.usd": ("the stock to buy, at Caliper's rough prices", "$", "<="),
    "make.sheets": ("how many sheets the cut plans use", "sheets", "<="),
    "make.missing": ("pieces that fit no sheet (should be 0)", "pieces", "<="),
    "waste.pct": ("offcut, by cost", "%", "<="),
    "hitch.tongue_lb": ("what a trailer hitch carries on its tongue (only for something on a hitch)", "lb", "<="),
    "frame.yield_x": ("how many times its standing load a welded frame survives", "×", ">="),
    "snow.safety": ("the roof's safety under the design's snow load", "×", ">="),
    "drag.lbf": ("drag at the design's speed (an objective, for something that moves through air)", "lbf", "<="),
}

_SYSTEM = """You keep the list of what a design must do, for its scorecard. You get the design (its goal, its
requirements with whether each was answered or assumed, its parts), the checks it has now, the metrics a
check can use, and the latest thing the person said. Reply with ONLY a JSON object:

{"checks": [{"id": "<short_snake_id>", "label": "<what it means, in the person's words where you can>",
             "metric": "<one of the metrics>", "op": ">=" | "<=", "limit": <number>,
             "source": "stated" | "assumed" | "proposed", "quote": "<the person's words, for stated>",
             "why": "<for proposed: why the design needs it, one short sentence>"}],
 "objectives": [{"id": "...", "label": "...", "metric": "...", "direction": "min" | "max"}]}

Rules:
- Return the whole list as it should now be: keep every existing check unless the person changed or
  withdrew it, and keep its id.
- One check per thing the person needs. Never write the same requirement twice with two metrics.
- Only what a listed metric measures. A requirement none of them measures (a height, a fit, a look) is
  left out: the design's own rules cover those. Never put a requirement on a metric that measures
  something else.
- "stated": the person said it AND gave the limit. Quote their words.
- "assumed": it rests on an assumed requirement, or on any number you chose (the safety factor behind
  "it has to hold me" is yours, so that check is assumed). Still quote their words when they said the
  rest of it.
- The label is what someone reads at a glance, in their words, short: "holds Dad (200 lb), 2 times over",
  "under $50", "fits through a 30 in door". No metric names.
- "proposed": at most two, only what this design plainly needs that nobody said: what it must hold, what
  holds it up, whether someone can carry or lift it. Never propose an id in the declined list.
- Use only the metrics listed. A strength check needs a part that declares loads(); if the person names a
  load and no part declares one, still write the check (it shows as not checked yet).
- For a person standing or stepping on something, the usual limit is strength.safety >= 2."""


def path(store: DesignStore) -> str:
    from .scorecard import goals_path

    return goals_path(store)


def read(store: DesignStore) -> dict:
    """The goals file as data (empty if there isn't one)."""
    import yaml

    p = path(store)
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def ours(data: dict) -> bool:
    """Caliper may rewrite it: there isn't one yet, or Caliper wrote it."""
    return not data or data.get("written_by") == MARK


def write(store: DesignStore, data: dict) -> None:
    import yaml

    data = {"written_by": MARK, **{k: v for k, v in data.items() if k != "written_by"}}
    head = ("# What this design is held to, written from the conversation (CALI-55). Each check says where it\n"
            "# came from: stated (the person said it), assumed, proposed (not binding until kept), confirmed.\n")
    with open(path(store), "w") as f:
        f.write(head + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110))


def _context(store: DesignStore, data: dict, said: str) -> str:
    d = store.design
    reqs = "\n".join(f"  - {r.question} -> {r.answer} [{r.source}]" for r in d.requirements) or "  (none)"
    parts = []
    for p in d.parts:
        script = store.read_script(p.id) if store.is_scripted(p.id) else ""
        decl = [n for n in ("loads", "construction", "members", "roof") if f"def {n}(" in script]
        parts.append(f"  - {p.id}: {p.intent or ''} (declares: {', '.join(decl) or 'nothing'})")
    metrics = "\n".join(f"  - {k}: {what} [{unit}]" for k, (what, unit, _) in METRICS.items())
    now = json.dumps({"checks": data.get("checks") or [], "objectives": data.get("objectives") or []}, indent=1)
    return (f"design goal: {d.prompt}\n\nrequirements:\n{reqs}\n\nparts:\n" + ("\n".join(parts) or "  (none yet)")
            + f"\n\nmetrics:\n{metrics}\n\nchecks now:\n{now}\n\ndeclined (never propose again): "
            f"{', '.join(data.get('declined') or []) or 'none'}\n\nthe latest thing the person said: {said}")


def _valid(c: dict, kind: str) -> Optional[dict]:
    if not isinstance(c, dict) or not c.get("id") or c.get("metric") not in METRICS:
        return None
    cid = re.sub(r"[^a-z0-9_]+", "_", str(c["id"]).lower()).strip("_")
    if kind == "objectives":
        return {"id": cid, "label": str(c.get("label") or cid), "metric": c["metric"],
                "direction": "max" if c.get("direction") == "max" else "min"}
    try:
        limit = float(c["limit"])
    except (KeyError, TypeError, ValueError):
        return None
    out = {"id": cid, "label": str(c.get("label") or cid), "metric": c["metric"],
           "op": "<=" if c.get("op") == "<=" else ">=", "limit": limit,
           "source": c.get("source") if c.get("source") in SOURCES else "assumed"}
    for k in ("quote", "why"):
        if c.get(k):
            out[k] = str(c[k])
    return out


def draft(store: DesignStore, said: str, data: dict, *, client=None, model: Optional[str] = None) -> dict:
    """Claude's list of checks and objectives as they should now be."""
    from .chat import DEFAULT_MODEL

    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=1500, system=_SYSTEM,
                                 messages=[{"role": "user", "content": _context(store, data, said)}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    m = re.search(r"\{.*\}", text, re.S)
    got = json.loads(m.group(0) if m else text)
    return {k: [x for x in (_valid(c, k) for c in got.get(k) or []) if x] for k in ("checks", "objectives")}


_HOLD = re.compile(r"\b(?:hold|carry|support)s?\b[^.]{0,40}?\b(\d{2,4})\s*(?:lb|lbs|pounds)\b", re.I)


def offline(store: DesignStore, said: str, data: dict) -> dict:
    """Without Claude: "it has to hold me (200 lb)" becomes a strength check; everything else stays."""
    checks = list(data.get("checks") or [])
    text = " ".join([store.design.prompt or "", said or ""])
    m = _HOLD.search(text)
    if m and not any(c.get("metric") == "strength.safety" for c in checks):
        checks.append({"id": "holds", "label": f"holds {m.group(1)} lb, at 2x (the 2x is assumed)",
                       "metric": "strength.safety", "op": ">=", "limit": 2.0, "source": "assumed",
                       "quote": m.group(0)})
    return {"checks": checks, "objectives": list(data.get("objectives") or [])}


def update(store: DesignStore, said: str, *, use_llm: bool = True, client=None) -> Optional[dict]:
    """Bring the design's checks up to date with what was just said. Returns what changed
    (``{"added": [...], "changed": [...], "proposed": [...]}``), or None when the file is somebody's own."""
    data = read(store)
    if not ours(data):
        return None
    before = {c["id"]: c for c in data.get("checks") or []}
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            got = draft(store, said, data, client=client)
        except Exception:  # noqa: BLE001 — the turn landed; the checks wait for the next one
            got = offline(store, said, data)
    else:
        got = offline(store, said, data)
    declined = set(data.get("declined") or [])
    checks, metrics = [], set()
    strength = any(c["metric"] == "strength.safety" for c in got["checks"])
    for c in got["checks"]:
        # one check per metric, and a breaking load beside the safety factor only if the person said it
        if c["metric"] in metrics or (c["metric"] == "strength.breaks_lb" and strength
                                      and c.get("source") != "stated"):
            continue
        metrics.add(c["metric"])
        old = before.get(c["id"])
        if c["id"] in declined and c.get("source") == "proposed":
            continue
        # what the person kept stays kept, unless they've now said otherwise
        if old and old.get("source") == "confirmed" and c.get("source") != "stated":
            c = {**c, "source": "confirmed"}
        checks.append(c)
    if checks == list(before.values()) and got["objectives"] == (data.get("objectives") or []):
        return {"added": [], "changed": [], "proposed": []}
    data.update({"checks": checks, "objectives": got["objectives"]})
    write(store, data)
    added = [c for c in checks if c["id"] not in before]
    changed = [c for c in checks if c["id"] in before and c != before[c["id"]]]
    store.append_log({"kind": "goals", "action": "updated", "added": [c["id"] for c in added],
                      "changed": [c["id"] for c in changed]})
    return {"added": [c for c in added if c["source"] != "proposed"], "changed": changed,
            "proposed": [c for c in added if c["source"] == "proposed"]}


def decide(store: DesignStore, check_id: str, keep: bool) -> dict:
    """The person keeps a proposed (or assumed) check, or drops it; a dropped proposal isn't offered again."""
    data = read(store)
    if not ours(data):
        raise ValueError("this design's goals were written by hand; edit scorecard.yaml")
    checks = data.get("checks") or []
    c = next((x for x in checks if x["id"] == check_id), None)
    if c is None:
        raise KeyError(f"no check {check_id!r}")
    if keep:
        c["source"] = "confirmed"
    else:
        checks.remove(c)
        data["declined"] = sorted(set(data.get("declined") or []) | {check_id})
    write(store, data)
    store.append_log({"kind": "goals", "action": "kept" if keep else "dropped", "id": check_id})
    return c


def reply(changes: Optional[dict]) -> str:
    """What the chat says about it, if anything."""
    if not changes or not (changes["added"] or changes["changed"] or changes["proposed"]):
        return ""
    lines = []
    for c in changes["added"] + changes["changed"]:
        lines.append(f"**{c['label']}**" + (" _(assumed)_" if c["source"] == "assumed" else ""))
    out = ("_Now on the scorecard: " + "; ".join(lines) + "._") if lines else ""
    if changes["proposed"]:
        out += ("\n\n" if out else "") + "_I'd also check: " + "; ".join(
            f"**{c['label']}** ({c.get('why') or 'the design needs it'})" for c in changes["proposed"]) \
            + ". Keep or drop them under Scorecard._"
    return out
