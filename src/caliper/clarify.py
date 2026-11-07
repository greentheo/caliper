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
    about: str = ""        # "shop:printer" etc. for a question about the shop: its answer goes there (CALI-124)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(id=str(d.get("id") or ""), question=str(d.get("question") or ""),
                   why=str(d.get("why") or ""), default=str(d.get("default") or ""),
                   about=str(d.get("about") or ""))


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


# ---------------------------------------------------------------------------
# The shop (CALI-124, #145): a question about it is answered by it, and an answer about it goes to it
# ---------------------------------------------------------------------------
#: What a question about the shop asks, by what in the shop answers it.
_SHOP_Q = [("printer", re.compile(r"\b(?:bed|build (?:volume|plate|area|size)|print (?:volume|area|bed)|nozzle)\b"
                                  r"|\bprinter(?:'s)? (?:size|bed|volume)\b|\bhow big (?:a|is your) print", re.I)),
           ("router", re.compile(r"\b(?:cnc|router)\b", re.I)),
           ("plasma", re.compile(r"\bplasma\b", re.I)),
           ("hand", re.compile(r"\bwhat (?:hand )?tools\b|\btools (?:do )?you (?:have|own)\b", re.I))]
_PLASTICS = ("pla", "petg", "abs", "asa", "tpu", "nylon")


def shop_topic(q: Question) -> str:
    """What in the shop a question asks about ("printer", "router", "plasma", "hand"), or ""."""
    if q.about.startswith("shop:"):
        return q.about[5:]
    text = f"{q.question} {q.why}"
    return next((kind for kind, rx in _SHOP_Q if rx.search(text)), "")


def shop_says(shop: dict, kind: str, known: bool = True) -> str:
    """What the shop already says about it, in words, or "" where it doesn't know ("your printer: 256 × 256 × 256 mm
    build volume, PLA and PETG"). ``known``: the person has said what's in their shop (a shop.yaml), so its hand tools
    are theirs, not the default's."""
    from . import shop as S

    if kind == "hand":
        tools = (shop or {}).get("hand") or []
        return f"your hand tools: {', '.join(tools)}" if known and tools else ""
    m = S.machine(shop or {}, kind)
    if not m:
        return ""
    mats = ", ".join(x.upper() if x in _PLASTICS else x for x in m.get("materials") or [])
    if kind == "printer" and m.get("volume_mm"):
        size = " × ".join(f"{float(v):g}" for v in m["volume_mm"]) + " mm build volume"
    elif m.get("bed_in"):
        size = " × ".join(f"{float(v):g}" for v in m["bed_in"]) + " in bed"
    else:
        size = ""
    return f"your {kind}: " + ", ".join(x for x in (size, mats) if x)


def shop_words(shop: dict, known: bool) -> str:
    """The shop as the question-writer is told it: what not to ask about."""
    said = [shop_says(shop, k, known) for k in ("printer", "router", "plasma", "hand")]
    return "; ".join(x for x in said if x)


def with_shop(questions: list[Question], shop: Optional[dict], known: bool = True) -> list[Question]:
    """Each question about the shop is tagged so its answer goes to the shop, and one the shop already answers
    says what the shop has instead of asking it (#145: Theo was asked his printer's bed size)."""
    out = []
    for q in questions:
        kind = shop_topic(q)
        if kind:
            said = shop_says(shop or {}, kind, known)
            q = Question(q.id, q.question, q.why, q.default, about=f"shop:{kind}")
            if said:
                q.question = f"{said[0].upper() + said[1:]}. If this one's to be made on something else, say what."
                q.why, q.default = "how it's made: from your shop", "as your shop has it"
        out.append(q)
    return out


def _numbers(text: str) -> tuple[list[float], bool]:
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text or "")]
    inches = bool(re.search(r"\d\s*(?:\"|in\b|inch)", text or "", re.I))
    return nums, inches


def shop_offer(kind: str, answer: str) -> Optional[dict]:
    """What an answer about the shop offers to add to it: ``{text, kind, machine | hand}``, or None where it says
    nothing the shop can take (it's about the shop either way: never a design requirement)."""
    from . import shop as S

    a = (answer or "").strip()
    if not a or a.lower() in ("as your shop has it", "same", "yes", "no"):
        return None
    if kind == "hand":
        tools = [t for t in S.HAND if re.search(rf"\b{re.escape(t)}s?\b", a, re.I)]
        return {"kind": "hand", "hand": tools, "text": f"Add {', '.join(tools)} to your shop's tools?"} if tools else None
    nums, inches = _numbers(a)
    mats = [p for p in _PLASTICS if re.search(rf"\b{p}\b", a, re.I)]
    if kind == "printer" and nums:
        mm = [v * 25.4 if inches else v for v in nums[:3]]
        vol = (mm * 3)[:3] if len(mm) == 1 else (mm + mm[:1])[:3] if len(mm) == 2 else mm
        machine = {"kind": "printer", "volume_mm": [round(v, 1) for v in vol], "materials": mats or ["pla", "petg"]}
        size = " × ".join(f"{v:g}" for v in machine["volume_mm"])
        return {"kind": "printer", "machine": machine,
                "text": f"Add a {size} mm printer ({', '.join(m.upper() for m in machine['materials'])}) to your shop?"}
    if kind in ("router", "plasma") and len(nums) >= 2:
        feet = bool(re.search(r"\d\s*(?:'|ft\b|feet|foot)", a, re.I))      # "4 x 8 ft": a sheet's size, in feet
        bed = [v * 12 if feet else v if inches or v < 200 else v / 25.4 for v in nums[:2]]   # inches, as shops say
        machine = {"kind": kind, "bed_in": [round(v, 2) for v in bed]}
        return {"kind": kind, "machine": machine,
                "text": f"Add a {bed[0]:g} × {bed[1]:g} in {kind} to your shop?"}
    return None


def _offers_path(store: DesignStore) -> str:
    return os.path.join(store.root, "shop_offers.json")


def offers(store: DesignStore) -> list[dict]:
    """What the answers offered to add to the shop, not yet taken or turned down."""
    try:
        with open(_offers_path(store)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def take_offer(store: DesignStore, index: int, add: bool) -> dict:
    """Add an offered machine or tools to the shop (``shop.write``, the shop's own path), or turn it down. Either
    way it's gone from the offers. Returns the shop."""
    from . import shop as S

    got = offers(store)
    if not 0 <= index < len(got):
        raise ValueError("no such offer")
    offer = got.pop(index)
    with open(_offers_path(store), "w") as f:
        json.dump(got, f, indent=2)
    have = S.read()
    if not add:
        return have
    if offer.get("machine"):
        kind = offer["machine"]["kind"]
        have = {**have, "machines": [m for m in have.get("machines") or [] if m.get("kind") != kind]
                + [offer["machine"]]}
    if offer.get("hand"):
        have = {**have, "hand": list(dict.fromkeys([*(have.get("hand") or []), *offer["hand"]]))}
    store.append_log({"kind": "shop", "action": "added", "what": offer["text"]})
    return S.write(have)


Asker = Callable[[str], list[Question]]


def draft_questions(prompt: str, *, use_llm: bool = True, client=None,
                    asker: Optional[Asker] = None, shop: Optional[dict] = None,
                    shop_known: bool = True) -> tuple[list[Question], str]:
    """Claude when available, the deterministic floor otherwise. Returns ``(questions, source)``. ``shop``: the
    person's shop, read first (CALI-124): never asked for what it says, and a question about it is tagged."""
    if asker is not None:
        return with_shop(asker(prompt)[:MAX_QUESTIONS], shop, shop_known), "injected"
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            told = shop_words(shop, shop_known) if shop else ""
            said = prompt + (f"\n\nTheir shop (what they make things with; never ask about it): {told}." if told else "")
            return with_shop(llm_questions(said, client=client), shop, shop_known), "llm"
        except Exception as e:  # noqa: BLE001 — a design must still start without the LLM
            print(f"[clarify] LLM questions failed → offline: {type(e).__name__}: {e}",
                  file=sys.stderr)
    return with_shop(offline_questions(prompt), shop, shop_known), "offline"


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
    recorded, offered = [], offers(store)
    for q in qs:
        given = "" if skip else str(answers.get(q.id, "") or "").strip()
        kind = shop_topic(q)
        if kind:                                   # about the shop: offered to it, never a design fact (CALI-124)
            offer = shop_offer(kind, given)
            if offer:
                offered.append(offer)
            continue
        if given:
            recorded.append(store.add_requirement(q.question, given, source="answered"))
        elif q.default:
            recorded.append(store.add_requirement(q.question, q.default, source="assumed"))
    if offered:
        with open(_offers_path(store), "w") as f:
            json.dump(offered, f, indent=2)
    if os.path.exists(_path(store)):
        os.remove(_path(store))
    store.append_log({"kind": "clarify", "action": "skipped" if skip else "answered",
                      "answered": sum(1 for r in recorded if r.source == "answered"),
                      "assumed": sum(1 for r in recorded if r.source == "assumed")})
    return recorded
