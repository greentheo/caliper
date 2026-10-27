"""CALI-33 — the clarify round: ask once, never re-ask.

A new design starts with a short, **bounded** round of questions whose answers actually change the
geometry — how high the receiver sits, what the part is screwed to, how much interior it must keep.
Answers become the design's **requirements**, which :meth:`DesignStore.prompt_context` hands to every
later revision as fixed context. That's the point: the question is asked once, at the start, and
never again — rather than rediscovered (or silently guessed differently) on revision #9.

Two rules carried over from intake (CALI-5):

- **Ask, don't assume — but don't interrogate.** At most :data:`MAX_QUESTIONS`, each with the default
  Caliper will use if it's left blank, and the human can skip the lot ("just build it").
- **An assumption is labelled as one.** A skipped question is recorded with ``source="assumed"``, so
  it reads differently in the context and can be re-surfaced later — unlike something the human said.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from .design import DesignStore

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")
MAX_QUESTIONS = 5

_INCHES = re.compile(r"\d\s*(?:\"|”|''|in\b|inch|inches)", re.I)


@dataclass
class Question:
    id: str
    question: str
    why: str = ""          # what the answer changes about the geometry
    default: str = ""      # what Caliper assumes if it's left blank

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(id=str(d.get("id") or ""), question=str(d.get("question") or ""),
                   why=str(d.get("why") or ""), default=str(d.get("default") or ""))


def speaks_inches(prompt: str) -> bool:
    """Does the human give dimensions in inches? Then the UI shows inches (geometry stays mm)."""
    return bool(_INCHES.search(prompt or ""))


# ---------------------------------------------------------------------------
# Drafting the questions
# ---------------------------------------------------------------------------
def offline_questions(prompt: str) -> list[Question]:
    """A deterministic floor: the questions almost every physical part needs answered."""
    qs = []
    if not re.search(r"\d", prompt or ""):
        qs.append(Question("size", "What are the overall dimensions?",
                           "everything else is sized from the envelope", "about 100 mm on a side"))
    qs.append(Question("mounting", "What does it attach to, and how?",
                       "decides where the holes and mating faces go", "free-standing"))
    qs.append(Question("loads", "What does it carry, and roughly how heavy?",
                       "decides wall thickness and where to add material", "light handling only"))
    qs.append(Question("process", "How will it be made (printed, cut from sheet, foam, machined)?",
                       "decides minimum walls, radii and what shapes are buildable at all",
                       "FDM printed in PLA"))
    return qs[:MAX_QUESTIONS]


_SYSTEM = f"""You are the clarify step of a CAD tool. Given what someone wants to build, ask the few
questions whose answers would CHANGE THE GEOMETRY — dimensions, mounting, clearances, loads, how it's
made. Never ask what the request already states. Never ask about cost, colour, or preferences that
don't change the shape. At most {MAX_QUESTIONS} questions; fewer is better.

Reply with ONLY a JSON array:
[{{"id": "<snake_case>", "question": "<one sentence>", "why": "<what it changes, briefly>",
   "default": "<the specific value you'd assume if they skip it, in the units they used>"}}]"""


def llm_questions(prompt: str, client=None, model: Optional[str] = None) -> list[Question]:
    model = model or DEFAULT_MODEL
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    msg = client.messages.create(model=model, max_tokens=900, system=_SYSTEM,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    m = re.search(r"\[.*\]", text, re.S)
    data = json.loads(m.group(0) if m else text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of questions")
    out, seen = [], set()
    for item in data:
        q = Question.from_dict(item if isinstance(item, dict) else {})
        if not q.question.strip():
            continue
        q.id = re.sub(r"[^a-z0-9_]+", "_", (q.id or q.question).lower()).strip("_")[:40] or "q"
        while q.id in seen:
            q.id += "_"
        seen.add(q.id)
        out.append(q)
    if not out:
        raise ValueError("no usable questions")
    return out[:MAX_QUESTIONS]


Asker = Callable[[str], list[Question]]


def draft_questions(prompt: str, *, use_llm: bool = True, client=None,
                    asker: Optional[Asker] = None) -> tuple[list[Question], str]:
    """Claude when available, the deterministic floor otherwise. Returns ``(questions, source)``."""
    if asker is not None:
        return asker(prompt)[:MAX_QUESTIONS], "injected"
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            return llm_questions(prompt, client=client), "llm"
        except Exception as e:  # noqa: BLE001 — a design must still start without the LLM
            print(f"[clarify] LLM questions failed → offline: {type(e).__name__}: {e}",
                  file=sys.stderr)
    return offline_questions(prompt), "offline"


# ---------------------------------------------------------------------------
# Parking the questions, and recording the answers
# ---------------------------------------------------------------------------
def _path(store: DesignStore) -> str:
    return os.path.join(store.root, "clarify.json")


def open_round(store: DesignStore, questions: list[Question], source: str = "") -> list[Question]:
    """Park the questions so the page can show them (and show them again after a reload)."""
    with open(_path(store), "w") as f:
        json.dump({"source": source, "questions": [q.to_dict() for q in questions]}, f, indent=2)
    store.append_log({"kind": "clarify", "action": "asked", "count": len(questions),
                      "routed_by": source})
    return questions


def pending(store: DesignStore) -> list[Question]:
    path = _path(store)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return [Question.from_dict(q) for q in json.load(f).get("questions", [])]
    except Exception:  # noqa: BLE001 — a corrupt file must not wedge the design
        return []


def answer_round(store: DesignStore, answers: dict[str, str], skip: bool = False) -> list:
    """Record every question as a requirement: answered ones as said, blank ones as **assumed**.

    ``skip=True`` is "just build it": every question takes its default, each labelled as an
    assumption so it's distinguishable later from something the human actually told us.
    """
    qs = pending(store)
    recorded = []
    for q in qs:
        given = "" if skip else str(answers.get(q.id, "") or "").strip()
        if given:
            recorded.append(store.add_requirement(q.question, given, source="answered"))
        elif q.default:
            recorded.append(store.add_requirement(q.question, q.default, source="assumed"))
    if os.path.exists(_path(store)):
        os.remove(_path(store))
    store.append_log({"kind": "clarify", "action": "skipped" if skip else "answered",
                      "answered": sum(1 for r in recorded if r.source == "answered"),
                      "assumed": sum(1 for r in recorded if r.source == "assumed")})
    return recorded
