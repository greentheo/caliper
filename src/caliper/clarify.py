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
#: A question about the person's own machine (#146 review: "your printer", "your bed", "what tools do you have"), not a
#: design question that names a machine ("How tall is the plasma cutter the cart carries?", "Which router bit profile?").
_YOURS = re.compile(r"\b(?:your|you(?:'ve| have| own)|do you have an?|what (?:hand )?tools do you)\b", re.I)
#: The machine a question names comes first ("your router's bed size" is the router's); then a printer's own words.
_SHOP_Q = [("router", re.compile(r"\b(?:cnc|router)\b(?! bit)", re.I)),
           ("plasma", re.compile(r"\bplasma\b", re.I)),
           ("printer", re.compile(r"\b(?:3d )?printer|\bbed size\b|\bbuild (?:volume|plate|area)\b|\bprint (?:bed|area|volume)\b",
                                  re.I)),
           ("hand", re.compile(r"\btools\b", re.I))]
_PLASTICS = ("pla", "petg", "abs", "asa", "tpu", "nylon")


def shop_topic(q: Question) -> str:
    """What of the person's own shop a question asks about ("printer", "router", "plasma", "hand"), or "" for a
    design question. The question-writer's own tag wins; otherwise only a question about *your* machine is the shop's
    (#146 review: "What nozzle diameter should the hose fitting take?" is the design's, and its answer is kept)."""
    if q.about.startswith("shop:"):
        return q.about[5:]
    if not _YOURS.search(q.question):
        return ""
    return next((kind for kind, rx in _SHOP_Q if rx.search(q.question)), "")


def shop_says(shop: dict, kind: str, known: bool = True) -> str:
    """What the shop already says about it, in words, or "" where it doesn't know ("your printer: 256 × 256 × 256 mm
    build volume, PLA and PETG"). ``known``: the person has said what's in their shop (a shop.yaml), so its hand tools
    are theirs, not the default's."""
    from . import shop as S

    if kind == "hand":
        tools = (shop or {}).get("hand") or []
        return f"your hand tools: {', '.join(tools)}" if known and tools and not (shop or {}).get("hand_default") else ""
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
    """Each question about the person's own shop is tagged so its answer goes to the shop, and one the shop already
    answers says what the shop has instead of asking it (#145: Theo was asked his printer's bed size)."""
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


#: A size said with its unit: "256 x 256 x 256 mm", "10 in", "4 x 8 ft", '48" x 96"'. Only these make an offer (#146:
#: "X1C" was a 1 x 1 x 1 printer, "0.4 nozzle, 256 bed" 0.4 x 256 x 0.4, and "150 x 150 mm" read as inches).
_UNIT = r"(mm|cm|in(?:ch(?:es)?)?\b|\"|ft\b|feet|foot|')"
_SIZE = re.compile(rf"(\d+(?:\.\d+)?)\s*{_UNIT}?\s*(?:(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*{_UNIT}?\s*)?"
                   rf"(?:(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*{_UNIT}?)?", re.I)
_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, '"': 25.4, "ft": 304.8, "'": 304.8}
#: A table's size said as a sheet's, with no unit: "4x8", "5 x 10" (feet, as plywood is sold).
_SHEET = re.compile(r"^\s*(4|5|6)\s*(?:x|×|by)\s*(4|5|8|10|12)\s*$", re.I)


def _sizes(text: str) -> list[tuple[list[float], str]]:
    """Each size said with a unit, in mm: ``[([256, 256, 256], "256 × 256 × 256 mm"), …]``."""
    out = []
    for m in _SIZE.finditer(text or ""):
        nums = [float(x) for x in (m.group(1), m.group(3), m.group(5)) if x]
        unit = next((u for u in (m.group(6), m.group(4), m.group(2)) if u), None)
        if not unit:
            continue                               # a number with no unit isn't a size (#146)
        u = unit.lower()
        key = "in" if u.startswith("in") or u == '"' else "ft" if u in ("ft", "feet", "foot", "'") else u
        out.append(([v * _TO_MM[key] for v in nums],
                    " × ".join(f"{v:g}" for v in nums) + f" {key}"))
    return out


def shop_offer(kind: str, answer: str) -> Optional[dict]:
    """What an answer about the shop offers to add to it: ``{text, kind, machine | hand}``, its size said with its
    numbers and units so a yes is informed; or a note, ``{kind: "note", text}``, where it says nothing the shop can take
    ("I couldn't read a printer from 'Bambu X1C': …"); None for a blank answer, or one that keeps the shop as it is."""
    from . import shop as S

    a = (answer or "").strip()
    if not a or a.lower() in ("as your shop has it", "same", "yes", "no", "none"):
        return None
    cant = {"kind": "note", "about": kind,
            "text": f"I couldn't read {'your tools' if kind == 'hand' else 'a ' + kind} from {a!r}: add "
                    f"{'them' if kind == 'hand' else 'it'} to your shop by hand"
                    + ("." if kind == "hand" else ", or give its " + ("build volume" if kind == "printer" else "bed")
                       + " with its units (" + ('"256 x 256 x 256 mm"' if kind == "printer" else '"4 x 8 ft"') + ").")}
    if kind == "hand":
        tools = [t for t in S.HAND if re.search(rf"\b{re.escape(t)}s?\b", a, re.I)]
        return {"kind": "hand", "hand": tools, "text": f"Add {', '.join(tools)} to your shop's tools?"} if tools else cant
    mats = [p for p in _PLASTICS if re.search(rf"\b{p}\b", a, re.I)]
    if kind == "printer":
        beds = [(mm, said) for mm, said in _sizes(a) if min(mm) >= 50]          # a nozzle's 0.4 mm isn't a bed
        if not beds:
            return cant
        mm, said = max(beds, key=lambda b: (len(b[0]), max(b[0])))
        vol = (mm * 3)[:3] if len(mm) == 1 else (mm + mm[:1])[:3] if len(mm) == 2 else mm
        machine = {"kind": "printer", "volume_mm": [round(v, 1) for v in vol], **({"materials": mats} if mats else {})}
        size = " × ".join(f"{v:g}" for v in machine["volume_mm"]) + " mm"
        return {"kind": "printer", "machine": machine,
                "text": f"Add a printer with a {size} build volume" + (f" (you said {said})" if not said.endswith(" mm") or
                                                                         len(mm) < 3 else "")
                        + (f", {', '.join(m.upper() for m in mats)}" if mats else ", materials not said") + ", to your shop?"}
    if kind in ("router", "plasma"):
        sheet = _SHEET.match(a)
        if sheet:                                  # a bare "4x8" is a sheet's size: feet, as plywood is sold (#146)
            mm, said = [float(sheet.group(1)) * 304.8, float(sheet.group(2)) * 304.8], f"{sheet.group(1)} × {sheet.group(2)} ft"
        else:
            beds = [(m, s) for m, s in _sizes(a) if len(m) >= 2]
            if not beds:
                return cant
            mm, said = max(beds, key=lambda b: max(b[0]))
        bed = [round(v / 25.4, 2) for v in mm[:2]]
        return {"kind": kind, "machine": {"kind": kind, "bed_in": bed},
                "text": f"Add a {kind} with a {bed[0]:g} × {bed[1]:g} in bed ({said}) to your shop?"}
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
    if not add or offer.get("kind") == "note":    # a note is only seen, never written
        return have
    if have.get("default"):                       # no shop.yaml yet: only what was offered, never the default saws
        have = {"machines": [], "hand_default": True}
    if offer.get("machine"):
        kind = offer["machine"]["kind"]
        have = {**have, "machines": [m for m in have.get("machines") or [] if m.get("kind") != kind]
                + [offer["machine"]]}
    if offer.get("hand"):
        mine = [] if have.get("hand_default") else (have.get("hand") or [])
        have = {**{k: v for k, v in have.items() if k != "hand_default"},
                "hand": list(dict.fromkeys([*mine, *offer["hand"]]))}
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
        if kind:                                   # about your shop: offered to it (CALI-124)
            offer = shop_offer(kind, given)
            if offer and offer["kind"] != "note":
                offered.append(offer)              # it goes to the shop, on a yes: not a design fact
                continue
            if offer:                              # nothing the shop can take: said, and the answer kept (#146 review)
                offered.append(offer)
            if not given:
                continue                           # a shop question left blank: the shop's, nothing to keep
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
