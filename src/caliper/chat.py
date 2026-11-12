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

from . import llm
from .design import DesignStore
from .errors import scrubbed
from .spec import Assertion, Spec


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
#: (#258) the request itself, as a phrase at the very start, never the part's name: "I need a bench" is a bench, not `i_need`.
#: Only there: a "can" inside a name ("a trash can enclosure", "a can crusher") is the name's (#262 review)
_REQUEST = re.compile(r"^\s*(?:please\s+)?(?:i\s+(?:really\s+)?(?:need|want|would\s+(?:like|love)|'?d\s+(?:like|love))"
                      r"|i'd\s+(?:like|love)|we\s+(?:need|want|would\s+like|'?d\s+like)|(?:can|could|would|will)\s+you(?:\s+please)?"
                      r"|let'?s)\b", re.I)
_BREAK_WORDS = {"it", "its", "that", "this", "for", "to", "with", "on", "in", "into", "which", "and",
                "so", "at", "of", "from", "under", "over", "between", "next", "then"}
_ADD_VERBS = re.compile(r"\b(add|create|build|make|generate|model|design|insert|need)\b")
_REVERT = re.compile(r"\b(roll(\s+\w+)?\s*back|revert|undo|go\s+back|put\s+it\s+back)\b")
#: Feedback phrased as an obligation is a *rule*, not a one-off tweak — worth saying so even
#: when Caliper can't turn it into a number (CALI-30).
_OBLIGATION = re.compile(r"\b(must|always|never|needs? to|has to|should (?:never|always|not)?)\b")
#: CALI-55: a number with a unit is usually a requirement ("under 10 lb", "16 in wide", "$50").
_MEASURE = re.compile(r"\d\s*(?:lb|lbs|kg|in|inch|inches|mm|cm|ft|feet|mph|%)\b|\$\s*\d", re.I)
#: CALI-59: asking for it again in plain words is a question, never a change, even with a part selected.
_EXPLAIN = re.compile(r"\b(explain|plain (?:words|english)|more simply|what does .{0,40}\bmean"
                      r"|say (?:that|it)(?: again)?(?: in)? (?:simpler|plainer)|(?:simpler|plainer) (?:words|terms|english)"
                      r"|(?:simpler|plainer),? please|say (?:that|it) again|i don'?t (?:get|understand)"
                      r"|like i'?m (?:five|5|six|6|a kid)|eli5)\b|^\s*(?:simpler|plainer)[.!]?\s*$", re.I)
#: (#212 review) "simpler legs" is a change: simpler or plainer is about the words only when it says so ("say it
#: simpler", "simpler please", "simpler words", or the word on its own).
_CHANGE_VERBS = (r"(?:make|change|add|remove|move|use|set|put|cut|build|turn|swap|replace|widen|lengthen|shorten"
                 r"|thicken|raise|lower|give)")
#: Where a request's verb starts a clause: after a stop, a colon, a dash, "and", "then", "so", or "can you" (#70, reviewer-2:
#: "I don't get it - make it 2 inches taller" and "…, can you make it…" were dropped).
_LEAD = (r"(?:(?:^|[,;:.!]|\s[-–—]|[–—])\s*(?:(?:and|then|but|so)\s+)?(?:(?:can|could|would|will)\s+you\s+)?"
         r"|\b(?:and|then|also|just|now|so)\s+)")
#: CALI-89 (#65 item 1, #212 review): a change asked for, as a request: its verb starts a clause ("…, make it 2
#: inches taller", "and make the legs thicker"). Inside a question it's a word ("explain the build order", "how to cut
#: the carriage"), and a question stays a question.
_CHANGE = re.compile(_LEAD + r"(?:please\s+)?" + _CHANGE_VERBS + r"\b", re.I)
#: (#212, round 2) a request for other words, whatever verb starts it: "put it in plain English", "use plain words",
#: "turn that into plain English". A question, unless it also asks for a size or a direction.
_WORDS = re.compile(r"\b(?:plain (?:english|words|language)|(?:simpler|plainer) (?:words|terms|language)|eli5)\b", re.I)
#: (#212, round 2) a size added to what's there is a revision: "add 2 inches to the height", "I need it 2 in wider".
_ADD_SIZE = re.compile(r"\badd\s+(?:another\s+)?\d[\d./ ]*\s*(?:in|inch|inches|mm|cm|ft|feet|foot|\")(?=\W|$)"
                       r"|\bneed\s+(?:it|this|that|them)\s+(?:to\s+be\s+)?(?=\d|\S+er\b)", re.I)   # a size after it
#: (#212, round 3) a clause asking why, what or how: a question, whatever words are in it.
_Q_CLAUSE = re.compile(r"^\s*(?:why|what|how|which|where|when|who|is|are|does|do|did|can|could|would|should|will)\b",
                       re.I)
#: (#212, round 3) a statement with no change in it: "I need it by Friday" isn't a revision.
_STATEMENT = re.compile(r"^\s*i\s+need\s+(?:it|this|that|them)\s*(?:(?:by|before|for|on|soon|today|tomorrow|tonight|asap"
                        r"|now|this|next)\b.*)?[.!]?\s*$", re.I)    # not "I need them painted", a change (#70, reviewer-2)
#: (#250 review, #262 re-check) "I need them painted", "I want it taller": what's left of a request ("I want", "can you", …) when it asks about something already there: "it taller",
#: "make them smaller". With nothing built, that has nothing to change, so it answers. The request is _REQUEST's, one for both rules
_OF_IT = re.compile(r"^\s*(?:\w+\s+)?(?:it|this|that|them)\b", re.I)


def _asks_of_it(message: str) -> bool:
    m = _REQUEST.match(message or "")
    return bool(m) and bool(_OF_IT.match(message[m.end():]))
#: (#70, reviewer-2) a clause that tells, not asks: "it's heavier than I thought"; its direction word is no request.
_SAYS = re.compile(r"^\s*(?:it|this|that|they|these|those|i)(?:'s|'re|'m|\s+(?:is|are|was|were|am|seems?|looks?|feels?"
                   r"|thought|think|was))\b", re.I)
#: (#212) a change to what's there: "make it wider", "use 1/2 in plywood"; not "make a bench", nor "add …".
_MODIFY = re.compile(_LEAD + r"(?:please\s+)?"
                     r"(?:make(?!\s+(?:me\s+)?(?:a|an|another|some|new|second|one more)\b)|change|remove|move|use|set"
                     r"|turn|swap|replace|widen|lengthen|shorten|thicken|raise|lower)\b|" + _ADD_SIZE.pattern, re.I)
#: (#65 item 3) "make it look like X": a question, answered with the picture offered; nothing changes.
_LOOKS_LIKE = re.compile(r"\bmake\s+(?:it|this|that|them|the\s+\w+)\s+look\s+like\s+(?:a\s+|an\s+|the\s+)?"
                         r"(?P<subject>[\w\-' ]{2,40}?)\s*[.!]?$", re.I)
#: (#65 item 3) what's a part, not a picture: "add a dino skid on the bottom" is a skid.
_STRUCTURE = {"skid", "skids", "foot", "feet", "leg", "legs", "shelf", "shelves", "bracket", "brackets", "rail",
              "rails", "handle", "handles", "wheel", "wheels", "base", "step", "steps", "brace", "braces", "support",
              "supports", "block", "blocks", "drawer", "drawers", "lid", "hinge", "hinges", "hook", "hooks", "tray",
              "panel", "panels", "post", "posts", "bar", "bars", "strut", "struts", "pad", "pads"}
#: (#65) a new thing: "add a shelf", "make me a bench"; "make it wider" changes what's there.
_NEW_THING = re.compile(r"\b(?:add|create|build|generate|model|design|insert)\b"
                        r"|\bneed\s+(?:me\s+)?(?:a|an|another|some|new|second|one more)\b"
                        r"|\bmake\s+(?:me\s+)?(?:a|an|another|some|new|second|one more)\b", re.I)   # with or without
#                                                         an article: "add shelves", "add the lid" (#212 review)
#: CALI-78: a picture cut out of a panel, for looks ("put a T-rex on the side", "cut a dinosaur into the front").
_PICTURE = re.compile(r"\b(?:put|draw|cut|carve|add|stick)\s+(?:a|an|the|some|my)?\s*(?P<subject>[\w\-' ]{2,40}?)"
                      r"\s+(?:on|onto|into|in|out of)\s+(?:the\s+|its\s+)?(?P<where>[\w ]{0,30})", re.I)
#: CALI-82: carving a printed part where it isn't working ("carve the sides", "whittle them down").
_CARVE = re.compile(r"\b(carve|whittle)\b", re.I)
#: CALI-54: feedback about what a part carries — a strength requirement, which goes into its loads().
_CARRIES = re.compile(r"\b(hold|holds|carry|carries|support|supports|bear|weight|load|loads|lb|lbs|kg|pounds)\b")


# ---------------------------------------------------------------------------
# Turn vocabulary
# ---------------------------------------------------------------------------
@dataclass
class Intent:
    """What the turn decided the message was asking for."""

    action: str                       # refine | author | revert | accept | decline | answer
    part: Optional[str] = None        # the part to revise, or the id for a new one
    intent: str = ""                  # for `author`: what the new part is; for `picture`: what to draw
    where: str = ""                   # for `picture`: which panel, in the person's words ("on the side")
    source: str = "offline"           # "offline" | "llm" | "injected"
    note: str = ""                    # why we routed this way (surfaced when we're unsure)
    parts: list = field(default_factory=list)   # every part a change names, in plan order (#241); [part] for one

    def __post_init__(self):
        if not self.parts and self.part and self.action == "refine":
            self.parts = [self.part]


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
    proposal: Any = None              # CALI-30: an assertion offered for confirmation
    events: list[Event] = field(default_factory=list)
    error: str = ""
    #: for a revision of several parts (#242): whether a number, the volume, the size or the centre of mass moved;
    #: None where it wasn't asked
    moved: Optional[bool] = None


# ---------------------------------------------------------------------------
# Classification — offline first, Claude when available, injectable for tests
# ---------------------------------------------------------------------------
def _words(message: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", (message or "").lower())


def _changes_outside_questions(msg: str) -> bool:
    """A size or a direction asked for in a clause that isn't itself a question (#212, round 3: "use plain words: why
    is it so much heavier" asks why; "…and make it wider" asks for a change)."""
    out = []
    for clause in re.split(r"[,:;.!?]|\s[-–—]\s|[–—]", msg):       # a dash ends a clause (#70, reviewer-2)
        parts = re.split(r"\b(?:and|then)\b(?=\s+(?:please\s+)?" + _CHANGE_VERBS + r"\b)", clause) if _Q_CLAUSE.match(clause) \
            else re.split(r"\band\b|\bthen\b", clause)            # "why is it wider and heavier" is one question
        out += [p for p in parts if not _Q_CLAUSE.match(p) and not _SAYS.match(p)]   # nor is a statement a request
    return any((_MEASURE.search(c) or _DIRECTION.search(c)) for c in out)


def _is_question(message: str) -> bool:
    msg = (message or "").strip()
    if msg.endswith("?"):
        return True
    w = _words(msg)
    if _EXPLAIN.search(msg) and not _CHANGE.search(msg):
        return True                                  # a question stays a question, whatever words are in it (#212)
    if _WORDS.search(msg) and not _changes_outside_questions(msg):
        return True                                  # other words, whatever verb asks for them (#212, round 2)
    if _STATEMENT.search(msg) and not _changes_outside_questions(msg) and not _ADD_SIZE.search(msg):
        return True                                  # "I need it by Friday": nothing to change (#212, round 3)
    return bool(w) and w[0] in _QUESTION_LEAD


def part_id_from(message: str, existing: set[str]) -> str:
    """Derive a readable, unique, identifier-safe part id from "add a corner bracket" → ``corner_bracket``."""
    words = [w for w in _words(_REQUEST.sub("", message or "", count=1)) if not w[0].isdigit()]
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


def named_part(message: str, parts: list[str], labels: Optional[dict] = None) -> Optional[str]:
    """Which existing part does this message name? Longest match wins ('bar_v' beats 'bar'). ``labels``: the names given
    in the tree ("Bathroom stool"), which the cards say (#70, reviewer-2: a renamed part's fix words authored a new part)."""
    words = set(_words(message))
    hits = []
    for pid in parts:
        # its id as written ("step_stool"), or as a person says it ("the step stool": #209 review, a card's words)
        for tokens in (set(_words(pid)), set(pid.lower().split("_")) - {""}, set(_words((labels or {}).get(pid) or ""))):
            if tokens and tokens <= words:
                hits.append((len(tokens), pid))
                break
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


#: "both sides", "neither slot", "each leg", "all the legs": a word that makes several parts the target (#241)
#: Words that say where a part is, not what it is: the ids of true siblings differ only by these, or by a number.
POSITION = {"left", "right", "front", "back", "rear", "top", "bottom", "upper", "lower", "inner", "outer", "middle",
            "centre", "center", "near", "far", "side", "l", "r", "fl", "fr", "bl", "br", "rl", "rr", "lh", "rh"}
#: Position words that mean the same: "the rear legs" are leg_back_left and leg_back_right (#242 re-check)
_SAME_PLACE = {"rear": "back", "centre": "center"}
_GROUP = re.compile(r"\b(?:both|neither|either|each|every|all)\s+(?:of\s+)?(?:the\s+)?((?:(?:"
                    + "|".join(sorted(POSITION, key=len, reverse=True)) + r")\s+)*[a-z]+)\b", re.I)


def _said_as(pid: str) -> str:
    """A part's id as a person says it, as a pattern: "side_left", "side left" or "left side"."""
    tokens = [t for t in pid.lower().split("_") if t]
    orders = [tokens] + ([tokens[::-1]] if len(tokens) == 2 else [])
    return "(?:" + "|".join([re.escape(pid.lower())] + [r"\s+".join(map(re.escape, o)) for o in orders]) + ")"


def _singular(word: str) -> list[str]:
    """A plural's singulars to try: shelves → shelf, bodies → body, boxes → box, legs → leg."""
    w = word.lower()
    out = []
    if w.endswith("ves"):
        out += [w[:-3] + "f", w[:-3] + "fe"]
    if w.endswith("ies"):
        out.append(w[:-3] + "y")
    if w.endswith("es"):
        out.append(w[:-2])
    if w.endswith("s") and not w.endswith("ss"):
        out.append(w[:-1])
    return out


def _siblings(stem: str, where: set, parts: list[str]) -> list[str]:
    """The parts a plural of ``stem`` means: those whose id, with the stem taken out, leaves only position words or
    numbers (side_left, leg_front_left, shelf_2: not corner_bracket_left, not lid_hinge), narrowed to ``where`` ("front
    legs" → the two front legs). The part named just ``stem`` counts too."""
    out = []
    where = {_SAME_PLACE.get(w, w) for w in where}
    for pid in parts:
        tokens = [_SAME_PLACE.get(t, t) for t in pid.lower().split("_") if t]
        if stem not in tokens:
            continue
        rest = set(tokens) - {stem}
        if all(t in POSITION or t.isdigit() for t in rest) and where <= set(tokens):
            out.append(pid)
    # one part is a plural's only when it's named just that ("lids": lid), never by elimination ("panels": not
    # back_panel alone, because side_panel's "side" was read as something else) (#242 re-check)
    return out if len(out) > 1 or (out and out[0].lower() == stem) else []


def _group(text: str, parts: list[str], strong: bool) -> list[str]:
    """Every part a group word names (``strong``: "both sides", "each leg", "all the shelves"), else every part a bare
    plural names ("the front legs"), siblings only, narrowed by the position words before it."""
    found: list[str] = []
    if strong:
        for m in _GROUP.finditer(text):
            words = m.group(1).lower().split()
            for k in range(len(words) - 1, -1, -1):          # the noun from the end: "neither side is" → "side"
                noun, where = words[k], {w for w in words[:k] if w in POSITION}
                got = next((g for g in (_siblings(stem, where, parts) for stem in [noun] + _singular(noun)) if g), [])
                if got:
                    found += got
                    break
        return found
    return [pid for _, got in _plurals(text, parts) for pid in got]


def _plurals(text: str, parts: list[str]) -> list[tuple[int, list]]:
    """Each bare plural that names siblings, with where it is in the text: ``[(index, [pids])]``."""
    found = []
    tokens = list(re.finditer(r"[a-z0-9_]+", text.lower()))
    for i, t in enumerate(tokens):
        w = t.group(0)
        stems = _singular(w) if len(w) > 3 else []
        if not stems:
            continue
        where, j = set(), i - 1
        while j >= 0 and tokens[j].group(0) in POSITION:
            where.add(tokens[j].group(0))
            j -= 1
        for stem in stems:
            got = _siblings(stem, where, parts)
            if got:
                found.append((t.start(), got))
                break
    return found


def named_parts(message: str, parts: list[str]) -> list[str]:
    """Every part a change is asked of (CALI-163, #241), in the order of ``parts``: :func:`targets` without its
    question (an unclear one gives none)."""
    return targets(message, parts)[0]


#: A request's verb and its article: the part right after it is what the request acts on ("make the top …")
_VERB_OBJECT = re.compile(r"\b(?:make|set|change|move|thicken|lengthen|widen|raise|lower|shorten|round|trim|extend|give|"
                          r"cut|drill|fillet|chamfer|resize|scale|stretch|shrink|narrow|deepen)\s+(?:the\s+|both\s+|all\s+)?")
#: A change asked for in a few words: "the top thicker", "2 in longer"
_MORE = re.compile(r"\b(?:thicker|thinner|longer|shorter|taller|wider|narrower|deeper|shallower|bigger|smaller|higher|"
                   r"lower|stronger|stiffer|lighter|heavier|larger|flatter|rounder|closer|further|farther|more|less)\b", re.I)
#: Where a request's own clause ends and what it's about begins: "make the legs longer; the top wobbles"
_CLAUSE = re.compile(r";|\bso\b|\bbecause\b|\bsince\b|\bwhile\b|\bas\b")


def targets(message: str, parts: list[str]) -> tuple[list[str], str]:
    """``(parts, question)``: every part a change is asked of, in the order of ``parts``, or a question when it can't
    tell which (#242 re-check: never the wrong part with a ✓).

    - A group word makes a group the target: "both sides", "neither slot", "each leg", "all the shelves".
    - Names joined by "and" or a comma are each the target ("the stretcher and the left side").
    - A bare plural beside a named part: the one the verb acts on, in the request's first clause (before "so",
      "because", "since" or ";") wins: "make the legs longer; the top wobbles" is the legs, "make the top thicker so
      the legs don't wobble" the top; both in it, joined by "and", are both ("the legs 2 in longer and the top
      thicker"). Otherwise it asks: "the legs, or the top?".
    - Any other part named is a reference, not changed ("…; the stretcher doesn't fit snug": not the stretcher).
    Several only when the message says several; otherwise the one part :func:`named_part` finds."""
    text = (message or "").lower()
    direct = [pid for pid in parts if re.search(rf"\b{_said_as(pid)}\b", text)]
    direct = [p for p in direct if not any(o != p and set(p.split("_")) < set(o.split("_")) for o in direct)]
    joined = set()
    for a in direct:
        for b in direct:
            if a != b and re.search(rf"{_said_as(a)}\s*(?:,|\band\b|&)\s*(?:the\s+)?{_said_as(b)}", text):
                joined |= {a, b}
    order = lambda got: [pid for pid in parts if pid in got]  # noqa: E731
    strong = set(_group(text, parts, strong=True))
    if strong:
        return order(strong | joined), ""
    if len(joined) >= 2:
        return order(joined), ""
    plurals = _plurals(text, parts)
    weak = {pid for _, got in plurals for pid in got}
    if weak and not direct:
        return order(weak), ""
    if weak:
        cut = _CLAUSE.search(text)
        end = cut.start() if cut else len(text)
        first_weak = {pid for at, got in plurals if at < end for pid in got}
        first_direct = [p for p in direct if (m := re.search(rf"\b{_said_as(p)}\b", text)) and m.start() < end]
        if first_weak and first_direct:
            if re.search(r"\band\b", text[:end]):
                # "and" joins two requests, not a request and a complaint ("the top is too thin and the legs wobble")
                asked: set = set()
                at = 0
                for piece in re.split(r"\band\b", text[:end]):
                    if _VERB_OBJECT.search(piece) or _MORE.search(piece):
                        asked |= {pid for a, got in plurals if at <= a < at + len(piece) for pid in got}
                        asked |= {p for p in first_direct if re.search(rf"\b{_said_as(p)}\b", piece)}
                    at += len(piece) + 3
                if asked:
                    return order(asked), ""
            led = _VERB_OBJECT.search(text[:end])    # "make the top overhang the sides": the verb's object is the top
            if led:
                after = led.end()
                at_weak = min((at for at, _ in plurals if at >= after), default=None)
                at_direct = min((m.start() for p in first_direct for m in [re.search(rf"\b{_said_as(p)}\b", text[after:])]
                                 if m), default=None)
                at_direct = at_direct + after if at_direct is not None else None
                if at_weak == after:
                    return order(first_weak), ""
                if at_direct == after:
                    return [named_part(text[after:end], first_direct) or first_direct[0]], ""
        elif first_weak:
            return order(first_weak), ""
        elif first_direct:
            return [named_part(text[:end], first_direct) or first_direct[0]], ""
        group = " or ".join(dict.fromkeys(f"the {text[at:].split()[0].strip('.,;:!?')}" for at, _ in plurals))
        named = " or ".join(f"the {p.replace('_', ' ')}" for p in direct)
        return [], f"Which do you want changed: {group}, or {named}? Say which (or both), and I'll change it."
    one = named_part(message, parts)
    return ([one] if one else []), ""


def last_touched(store: DesignStore) -> Optional[str]:
    """The part an unscoped "undo" most likely means — the one most recently revised."""
    if not store.design.parts:
        return None
    return max(store.design.parts, key=lambda p: p.updated).id


def _printed(store: DesignStore, part_id: str) -> bool:
    return store.is_scripted(part_id) and bool(re.search(r"""["']kind["']\s*:\s*["']printed["']""",
                                                         store.read_script(part_id)))


def _drawable(store: DesignStore, subject: str, part: Optional[str]) -> bool:
    """Whether "make it look like <subject>" is a picture to offer (#212 review): one thing, not a compound ("a
    dinosaur and 2 in taller" is a change), one Caliper can draw offline (not "oak" or "wood", a finish), on a part
    with a panel a picture can go on."""
    from .pictures import BUILT_IN, panels

    s = subject.lower()
    if not part or re.search(r"\d|,|\band\b|\bwith\b", s) or not any(k in s for k in BUILT_IN):
        return False
    try:
        return bool(panels(store, part))
    except Exception:  # noqa: BLE001 — a part that can't say: no offer, and the message routes as it would
        return False


def _offer(subject: str) -> str:
    """The picture offered for "make it look like <subject>", nothing changed (#65, #212: "an" before a vowel)."""
    a = "an" if subject[:1].lower() in "aeiou" else "a"
    return (f"I can cut {a} {subject} out of a panel nobody stands on, and check it still holds. Say \"put {a} "
            f"{subject} on the side\" (or the front) to do it. Nothing's changed.")


def offline_classify(store: DesignStore, message: str, scope: Optional[str] = None) -> Intent:
    """Deterministic routing — no network. Ask-don't-assume when genuinely ambiguous.

    The rules, in order: a scoped message is about that part unless it's a question; an unscoped
    message that names an existing part is about it; an "add/build a ..." is a new part; the first part
    of an empty design needs no naming ceremony. Anything else routes to ``answer`` with a nudge rather
    than guessing which part the user meant — a wrong guess spends an authoring run.
    """
    ids = [p.id for p in store.design.parts]
    labels = {p.id: p.label for p in store.design.parts if p.label}
    question = _is_question(message)

    # "make it look like a dinosaur": the picture offered, nothing changed (#65 item 3)
    looks = _LOOKS_LIKE.search((message or "").strip())
    if looks and ids and _drawable(store, looks.group("subject").strip(), scope or (ids[0] if len(ids) == 1 else None)):
        return Intent(action="answer", part=scope, note=f"offer a picture: {looks.group('subject').strip()}")

    # carve a printed part (CALI-82)
    if _CARVE.search(message or "") and not question and ids:
        target = scope or named_part(message, ids, labels) or (ids[0] if len(ids) == 1 else None)
        if target and _printed(store, target):
            return Intent(action="carve", part=target, note="carve the printed part where it isn't working")

    # a picture: offline, only one it can draw, or one that says it's a picture (Claude routes the rest)
    pic = _PICTURE.search(message or "")
    if pic and not question and ids:
        from .pictures import BUILT_IN

        subject = pic.group("subject").strip()
        target = scope or named_part(message, ids, labels) or (ids[0] if len(ids) == 1 else None)
        thing = (subject.lower().split() or [""])[-1]
        if target and thing not in _STRUCTURE and (any(k in subject.lower() for k in BUILT_IN)
                       or re.search(r"\b(picture|drawing|silhouette|cut-?out|shape)\b", subject, re.I)):
            return Intent(action="picture", part=target, intent=subject, where=pic.group("where").strip(),
                          note="a picture to cut out of a panel")

    if _REVERT.search((message or "").lower()) and not question:
        target = scope or named_part(message, ids, labels) or last_touched(store)
        if target:
            return Intent(action="revert", part=target, note="asks to undo the last change")

    several, which = targets(message, ids)
    if which and not question:                     # it can't tell which: asked, never the wrong part (#242 re-check)
        return Intent(action="answer", note=f"ask which: {which}")
    if len(several) > 1 and not question:          # by the request, not the selection (#241)
        return Intent(action="refine", part=several[0], parts=several, note=f"names {len(several)} parts")

    if scope:
        if question:
            return Intent(action="answer", part=scope, note="a question about this part")
        return Intent(action="refine", part=scope, note="scoped to the clicked part")

    hit = named_part(message, ids, labels)
    if hit and not question:
        return Intent(action="refine", part=hit, note=f"names the part {hit!r}")
    if question:
        return Intent(action="answer", part=hit, note="reads as a question")

    wants_new = bool(_NEW_THING.search(message or "")) and not _ADD_SIZE.search(message or "")   # a size added: a revision
    if not ids and not wants_new and (_EXPLAIN.search(message or "") or _asks_of_it(message)):
        # "I don't get it, make it 2 inches taller" with nothing built: nothing to change, no part named `i_don` (#70)
        return Intent(action="answer", note="asks to explain, and there's nothing to change yet")
    if not wants_new and len(ids) == 1 and _MODIFY.search(message or ""):
        # "make it 2 in wider" on a one-part design is that part, not a new one named "part" (#65)
        return Intent(action="refine", part=ids[0], note="a change, and the design has one part")
    if wants_new or not ids:
        new_id = part_id_from(message, set(ids))
        return Intent(action="author", part=new_id, intent=(message or "").strip(),
                      note="the first part of the design" if not ids else "asks for a new part")

    return Intent(action="answer", note="ambiguous — no part named and no request to add one")


_CLASSIFY_SYSTEM = """You route a message in a CAD design conversation. Reply with ONLY a JSON object:

{"action": "refine" | "author" | "revert" | "answer" | "picture" | "carve",
 "part": "<existing part id, a new snake_case id, or null>",
 "intent": "<for author: a one-line description of the part to build; for picture: just the thing to draw, in
            a word or two (\"T-rex\", \"heart\"); else empty>",
 "where": "<for picture: which panel, in their words (\"the side\", \"the front\"), or empty>",
 "parts": ["<for refine: EVERY existing part id the request changes, the first being `part`>"]}

- "refine": change an EXISTING part: its shape, or what its script says about it (what it's built
  from, what it must hold or carry, what it must keep clear). `part` must be one of the design's part
  ids. A new requirement on a part ("it has to hold me, 200 lb", "make it from 1/2 in ply") is a refine.
- A request that names or implies several parts changes each of them: "both sides", "neither slot", "all the legs",
  "the stretcher and the left side". List every one in `parts`, whichever part is selected. A part named only as a
  reference ("make the carriage clear the rail") isn't in `parts`.
- "author": build a NEW part. `part` is a new snake_case identifier; `intent` describes it, as the
  design's requirements have it: never a choice they don't make or one that contradicts them.
- "revert": undo the last change to a part ("roll it back", "undo that"). `part` is that part.
- "picture": cut a picture or shape out of a panel for looks ("put a T-rex on the side", "cut a heart
  into the back"), not a new working part. `part` is the existing part it goes on.
- "carve": carve or whittle a 3D-printed part down where it isn't working ("carve the sides", "whittle
  the legs down"). `part` is that part.
- "answer": the user asked a question, asked for something to be explained or said more simply, or said
  something that changes nothing about any part.
- A message that asks for an explanation AND a change ("I don't get it, make it 2 inches taller", "explain why,
  and make the legs thicker") is the change: "refine". Asking for simpler or plainer words with no change in it
  ("say it simpler", "simpler please", "in plain English", "explain like I'm five") is "answer".
- "make it look like a dinosaur" is "answer" (offer to cut the picture; change nothing). A picture is "put/draw/
  cut <subject> on/into <a panel>". "a … skid / foot / leg / shelf on the bottom" is a working part, not a
  picture: "author" (or "refine" when that part is selected).
- "make it …" (wider, taller, thicker) on a design with one part changes that part: "refine", never a new part.
- A question stays a question, whatever words are in it: "explain the build order", "how do I cut the carriage",
  "I don't understand which way to turn the panel" are "answer", never a change or a new part. Only a request
  that starts a clause ("…, make it taller", "and make the legs thicker") is a change.
- "simpler" or "plainer" is about the words only when it says so ("say it simpler", "simpler please"); "simpler
  legs", "a plainer finish" change the part. "make it look like a dinosaur and 2 in taller" is a change.
- "add …" is a new part with or without an article ("add shelves", "add the lid").
If the message is ambiguous about WHICH part, use "answer" — do not guess."""


def llm_classify(store: DesignStore, message: str, scope: Optional[str] = None,
                 client=None, model: Optional[str] = None) -> Intent:
    """Route with Claude, given the design's parts as context. Raises on any failure (caller falls back)."""
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()

    parts = "\n".join(f"  - {p.id}: {p.intent or '(no stated intent)'}" for p in store.design.parts)
    # CALI-54: the router writes a new part's intent, and the author follows the intent — so without the
    # requirements here it made up a "two-step stool" after the user had settled on a single platform.
    reqs = "\n".join(f"  - {r.question} -> {r.answer}" + ("" if r.source == "answered" else " [assumed]")
                     for r in store.design.requirements)
    ask = (
        f"design goal: {store.design.prompt}\n\n"
        + (f"requirements (settled; a new part's intent follows them):\n{reqs}\n\n" if reqs else "")
        + f"existing parts:\n{parts or '  (none yet)'}\n\n"
        + (f"the user has SELECTED the part '{scope}' — a request to change something almost certainly "
           f"means that part\n\n" if scope else "")
        + f"message: {message}"
    )
    msg = llm.ask(client, "classify", model=model, system=_CLASSIFY_SYSTEM,
                  messages=[{"role": "user", "content": ask}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)
    action = str(data.get("action", "")).strip()
    if action not in ("refine", "author", "revert", "answer", "picture", "carve"):
        raise ValueError(f"unusable action {action!r}")
    part = data.get("part") or None
    ids = {p.id for p in store.design.parts}
    if action in ("picture", "carve") and part not in ids:
        part = scope if scope in ids else (next(iter(ids)) if len(ids) == 1 else None)
        if part is None:
            raise ValueError("a picture on which part?")
    if action in ("refine", "revert") and part not in ids:
        raise ValueError(f"{action} targets unknown part {part!r}")
    if action == "author":
        part = part if part and part not in ids else part_id_from(message, ids)
    several: list = []
    if action == "refine":
        named = [str(x) for x in (data.get("parts") or []) if x]
        unknown = [x for x in named if x not in ids]
        if unknown:
            raise ValueError(f"refine names unknown part(s) {unknown!r}")
        order = [p.id for p in store.design.parts]
        several = [p for p in order if p in set(named) | {part}]
    return Intent(action=action, part=several[0] if several else part, intent=str(data.get("intent") or message).strip(),
                  where=str(data.get("where") or "").strip(), source="llm", note="routed by Claude", parts=several)


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
            print(f"[chat] LLM routing failed → offline: {type(e).__name__}: {scrubbed(e)}", file=sys.stderr)
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


#: A path on the machine the server runs on, as a traceback or an error names it: never shown to the person.
_SERVER_PATH = re.compile(r"(?:/Users|/home|/private|/tmp|/var|/opt|[A-Za-z]:\\)[^\s\"',)]*")


def shown(reply: str) -> str:
    """A reply as the chat shows it again (#89, #137 P2 item 12: an old reply from before the stop said its reason
    plainly kept a raw traceback naming `/Users/…/_sandbox_runner.py`): a traceback down to its last line, and a server
    path down to its file's name. The log keeps every word; this is what's shown."""
    if not reply:
        return reply
    out, base = [], None
    for line in reply.splitlines():
        indent = len(line) - len(line.lstrip())
        if line.lstrip().startswith("Traceback (most recent call last)"):
            base = indent                              # the frames are indented past it; its last line isn't
            continue
        if base is not None and (indent > base or not line.strip()):
            continue                                   # a frame: dropped
        base = None
        out.append(line)
    return _SERVER_PATH.sub(lambda m: m.group(0).replace("\\", "/").rsplit("/", 1)[-1], "\n".join(out))


def _measure_design(store: DesignStore):
    """Measure the whole design, tolerantly. ``(None, {})`` when there's nothing to measure yet."""
    from .assembly import derived_assertions

    if not store.assembly.parts or not derived_assertions(store.assembly):
        return None, {}
    try:
        return store.evaluate(tolerant=True)
    except Exception as e:  # noqa: BLE001 — a measurement failure must not swallow the user's change
        return None, {"<design>": f"{type(e).__name__}: {scrubbed(e)}"}


def _design_line(report) -> str:
    """What the whole design measures, in a line (#103 review, for #3b): green only when every check ran and
    passed (:meth:`Report.said`); a check that waits for an unbuilt part is said, never counted."""
    if report is None or report.failures:
        return ""
    if report.all_pass and not report.waiting:
        # what was measured, not "green" (#241): its plan rules pass; whether a part fits its pocket isn't one of them
        return (f"The design's checks pass ({', '.join(_kinds(report))}); whether a part fits snug in its pocket "
                f"isn't measured.")
    return f"The whole design: {report.said()}."


def _kinds(report) -> list[str]:
    """What the design's checks measure, by kind, in a person's words: "touch", "no overlap", "fit", "clearance"."""
    out: list[str] = []
    for r in report.results:
        e = r.expr or ""
        kind = ("no overlap" if "interference(" in e
                else "touch" if re.match(r"^\s*-[\d.]+\s*<=\s*min_clearance\(", e)
                else "fit" if re.search(r"<=\s*min_clearance\(.*\)\s*<=", e)
                else "clearance" if "min_clearance(" in e else "the design's rules")
        if kind not in out:
            out.append(kind)
    return out


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
        # the reason, where the check gives one: the line a fallback hides a feature on (CALI-107)
        out.append(f"  • {r.id}: {r.expr} → actual={r.actual}{margin}" + (f". {r.detail}" if r.detail else ""))
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
    spec.intent = f"{spec.intent or intent}\n\n--- design context ---\n{context}{frame}{TUNABLE}"
    return spec


#: CALI-39 / CALI-54: the script's shape and its declarations are in the part-script reference, which the
#: generator's system prompt carries (:func:`caliper.authoring.system_prompt`); a revision is reminded to
#: keep both, because a change to build() that leaves construction() behind fails the round.
TUNABLE = """

Keep the script in the shape the part-script reference gives (PARAMS first, build() merging overrides).
If it declares what it's built from (BUILD and construction(), members() and supports()), what it must
hold (loads()) or keeps(), RANGES, LAYOUTS and HOLES, keep every one of them, describing the same part as
build(): move a panel or a tube in one and move it in the others. A part made from sheet goods, lumber
or tube that doesn't declare construction() yet should get one, and one whose requirements say what it
must carry should get loads()."""


def _emit(events: list[Event], on_event, kind: str, text: str, **data) -> None:
    ev = Event(kind=kind, text=text, data=data)
    events.append(ev)
    if on_event is not None:
        on_event(ev)


def _features_of(store: DesignStore, part_id: str) -> Optional[dict]:
    """A part's faces and edges, or None if they can't be worked out: then what landed where can't be said."""
    from . import features

    try:
        return features.for_part(store, part_id)
    except Exception:  # noqa: BLE001 — the change stands; only the check of it is lost
        return None


def refine_part(store: DesignStore, part_id: str, message: str, *, author=None, client=None,
                max_rounds: int = 4, events: Optional[list[Event]] = None, on_event=None,
                use_llm: bool = True, drafter=None, promote_feedback: bool = True, measured: str = "",
                pick: Optional[dict] = None, focus: str = "", keep_same: bool = True, of: str = "") -> TurnResult:
    """Revise a part **that lives inside a design** and re-measure the whole thing.

    ``focus`` is said to the designer only, after the request (#241: which of the parts it names this revision is
    for). ``keep_same=False``: a revision whose code is the same (comments and layout don't count) writes no version,
    and says so; any other is written, and ``moved`` says whether a number, the volume, the size or the centre of mass
    moved (#242 re-check: a move written as literals keeps the numbers and the volume). ``of`` follows the part's name
    as it's said ("2 of 2").

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
    if not store.is_scripted(part_id):
        # Revising the part.py underneath a whittled mesh would silently throw the carving away —
        # so say what the part currently is, and how to get back to something revisable.
        if entry.origin == "whittled":
            reply = (f"'{part_id}' is currently whittle's carved shape (v{entry.version}) — a mesh, "
                     f"with no script behind it to revise. Say **roll it back** to return to the "
                     f"parametric version, then ask for the change there.")
        else:
            reply = (f"'{part_id}' is imported geometry — there's no script behind it to revise. "
                     f"Re-author it as a new part if you want it to change.")
        return TurnResult(action="error", ok=False, part=part_id, events=events,
                          error=f"{part_id} has no script to revise", reply=reply)

    from . import mirror

    source = mirror.source_of(store, part_id)
    if source:                                     # a mirror has no script of its own: the edit is its source's (#239)
        res = refine_part(store, source, message, author=author, client=client, max_rounds=max_rounds, events=events,
                          on_event=on_event, use_llm=use_llm, drafter=drafter, promote_feedback=promote_feedback,
                          measured=measured)
        followed = store.design.part(part_id).version
        res.reply = (f"{part_id} mirrors {source}: I changed {source}"
                     + (f", and {part_id} follows it (v{followed})" if res.version else "") + ".\n\n" + res.reply)
        return res

    picked_from = _features_of(store, part_id) if pick else None    # the part as it was picked on (#109)
    before, _ = _measure_design(store)
    spec = _working_spec(store, part_id, entry.intent)
    script = store.read_script(part_id)
    prior = script                                 # what the request changes, as it was (CALI-107)
    was = _volume(store, part_id)
    before_shape = None if keep_same else _shape(store, part_id)

    _emit(events, on_event, "authoring", f"revising {part_id}{f' ({of})' if of else ''}…", part=part_id)
    # ``measured`` is true of this version: to the designer's first round only, never into the part's record (#158)
    tries: list = []
    res = None
    try:
        res = authoring.refine_authored(spec, script, f"{message}\n\n{focus}" if focus else message,
                                        max_rounds=max_rounds, measured=measured,
                                        ref_base=store.root, author=author, client=client, tries=tries)
    finally:
        # every revision's tries, each with its round, built or not: the ones that fail are the ones to see (#232 review)
        if tries:
            store.append_log({"kind": "revise", "part": part_id, "rounds": res.rounds if res else max(t["round"] for t in tries),
                              "built": bool(res and res.geometry is not None), "tries": tries})

    if res.geometry is None:                      # never built — don't write a broken part
        _emit(events, on_event, "error", f"{part_id} would not build", part=part_id)
        return TurnResult(action="refine", ok=False, part=part_id, events=events,
                          error=res.error or "the revision never built",
                          reply=(f"I couldn't get '{part_id}' to build with that change after "
                                 f"{res.rounds} attempt(s). Last error:\n  {res.error}\n"
                                 f"The part is unchanged."))

    _emit(events, on_event, "built", f"{part_id} built in {res.rounds} round(s)", part=part_id)
    report_dict = res.report.to_dict() if res.report is not None else None
    described = redescribe(entry.intent, message, res.script, use_llm=use_llm, client=client)
    from . import carve

    uncarved = carve.carved(store.read_script(part_id))   # a carve fits the shape it was carved from (CALI-82)
    script = carve.uncarve(res.script)[0]
    if not keep_same and _same_code(prior, script):   # the same code: nothing to write, said (#241)
        return TurnResult(action="refine", ok=False, part=part_id, events=events, error="unchanged",
                          reply=f"The revision left **{part_id}**'s code as it was.")
    moved = None if keep_same else _moved(prior, script, before_shape, res.geometry)
    from .authoring import params_from_spec

    version = store.write_part(part_id, script, feedback=message, action="refine",
                               report=report_dict, intent=described,
                               built=(res.script, params_from_spec(spec), res.geometry))
    _emit(events, on_event, "wrote", f"{part_id} → v{version}", part=part_id, version=version)

    after, part_errors = _measure_design(store)
    _emit(events, on_event, "measured", "measured the whole design", part=part_id)
    broke, fixed = _delta(before, after)

    reply = _compose(store, part_id, version, res, after, broke, fixed, part_errors, verb="revised",
                     asked=message, prior=prior, new=script,
                     volumes=(was, _volume(store, part_id)))
    if uncarved:
        reply += "\n\n" + carve.DROPPED
    on_pick = None
    if pick:                                        # did it land on what was picked? Only what can be measured is said
        from . import features

        check = features.landed(picked_from, _features_of(store, part_id), pick, message, store.design.display_units == "in")
        on_pick = check["landed"]
        short = on_pick is False or on_pick == features.PARTIAL      # what was asked for didn't happen
        if short:                                   # the same words next time are a retry, not "v2 already did that" (#177)
            store.append_history(part_id, {"kind": "pick_missed", "version": version})
        # a miss comes first and the turn isn't a success: never a tick above "it isn't on what you picked" (rule 6)
        reply = (f"{'!' if on_pick == features.PARTIAL else chr(0x2717)} {check['said']}\n\n{reply.replace(chr(0x2713) + ' ', '', 1)}"
                 if short else f"{reply}\n\n{check['said']}")
    proposal, offer = _offer_promotion(store, part_id, message, use_llm=use_llm, client=client,
                                       drafter=drafter, enabled=promote_feedback,
                                       events=events, on_event=on_event)
    if offer:
        reply += "\n\n" + offer

    return TurnResult(action="refine", ok=bool(res.ok) and not broke and on_pick not in (False, "partial"), part=part_id, version=version, moved=moved,
                      part_report=res.report, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, proposal=proposal, events=events, reply=reply)


def _same_code(prior: str, new: str) -> bool:
    """Whether a revision's code is the same as before, comments and layout aside (#242 re-check): by its parsed tree."""
    import ast

    from . import carve

    try:
        return ast.dump(ast.parse(carve.uncarve(prior or "")[0])) == ast.dump(ast.parse(new or ""))
    except SyntaxError:
        return (prior or "").strip() == (new or "").strip()


def _shape(store: DesignStore, part_id: str):
    """``(volume, bounds, centre of mass)`` of the part as it is, or None."""
    try:
        return _measures(store.part_geometry(part_id))
    except Exception:  # noqa: BLE001 — not measurable: nothing to compare against
        return None


def _measures(geometry):
    m = geometry.require_mesh()
    return float(abs(m.volume)), [[float(v) for v in row] for row in m.bounds], [float(v) for v in m.center_mass]


def _moved(prior: str, new: str, before, geometry, tol: float = 0.01) -> bool:
    """Whether a revision moved something measured (#242 re-check): a PARAMS number, the volume, the bounding box or the
    centre of mass (a move written as literals keeps the numbers and the volume, not the box)."""
    from . import carve, fallbacks

    if fallbacks.changed(carve.uncarve(prior or "")[0], new or ""):
        return True
    try:
        after = _measures(geometry)
    except Exception:  # noqa: BLE001 — nothing measured can't show a move; the code changed, said as that
        return False
    if before is None:
        return True
    (v0, b0, c0), (v1, b1, c1) = before, after
    return (abs(v1 - v0) > 1e-6 * max(v0, 1.0)
            or any(abs(a - b) > tol for r0, r1 in zip(b0, b1) for a, b in zip(r0, r1))
            or any(abs(a - b) > tol for a, b in zip(c0, c1)))


def _offer_promotion(store: DesignStore, part_id: str, feedback: str, *, use_llm: bool,
                     client, drafter, enabled: bool, events: list[Event], on_event):
    """Turn the feedback into a proposed test — or say honestly why it can't be one (CALI-30).

    Silence is the default for vague tweaks: offering to enshrine "a bit wider" as a rule is noise.
    But feedback phrased as an **obligation** ("it must clear the rail", "never thicker than 6mm") is a
    rule the user is stating out loud, so when that can't be measured we say so rather than letting
    them assume it stuck.
    """
    from . import promote

    if not enabled:
        return None, ""
    promote.clear(store)                     # a new change supersedes any stale offer
    try:
        got = promote.draft(store, part_id, feedback, use_llm=use_llm, client=client, drafter=drafter)
    except Exception as e:  # noqa: BLE001 — the user's edit already landed; an offer is a bonus
        _emit(events, on_event, "error", f"could not draft an assertion: {scrubbed(e)}", part=part_id)
        return None, ""

    if got.proposal is not None:
        promote.park(store, got.proposal)
        _emit(events, on_event, "proposed", f"{got.proposal.id}: {got.proposal.expr}",
              part=part_id, assertion=got.proposal.id, holds_now=got.proposal.holds_now)  # producer: carried
        return got.proposal, got.proposal.describe()

    fb = (feedback or "").lower()
    if _OBLIGATION.search(fb) and _CARRIES.search(fb) and store.is_scripted(part_id) \
            and "def loads(" in store.read_script(part_id):
        return None, ("_That's a strength requirement, which a rule on the shape can't measure, so it's in "
                      "the part's `loads()` now: **Check it holds** (under *Will it hold?*) puts it through "
                      "whittle's FEA and a plate check._")
    if _OBLIGATION.search(fb):
        why = got.reason or "it isn't something Caliper can measure"
        return None, (f"_You phrased that as a rule, but I can't make it one: {why}. "
                      f"It's applied as a one-off change — a later revision could undo it._")
    return None, ""


#: CALI-69: a part's description is what the router and every later revision read as what the part *is*,
#: so a revision that changes that (two steps -> one platform) must change the description too.
_DESCRIBE_SYSTEM = """You keep the one-line description of a part in a CAD design. The people working on it read
it, and so does the next revision, as what the part is. You get the description as it was, the change just
made, and the part's script as it is now. Reply with the description of the part as the script now builds
it: one sentence, what it is, its main pieces and what it's made of, and what it's for. If the old
description is still true, reply with it unchanged. Never keep anything the script no longer builds.
Reply with the sentence only."""
_REVISED = re.compile(r"\s*\(revised: .*\)$", re.S)


def redescribe(old: Optional[str], change: str, script: str, *, use_llm: bool = True, client=None,
               model: Optional[str] = None) -> str:
    """The part's description after a revision: re-described from the new script by Claude, or offline, the
    old one with the latest change said after it (never silently out of date)."""
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            if client is None:
                from anthropic import Anthropic  # lazy; may be absent

                client = Anthropic()
            msg = llm.ask(
                client, "describe", model=model, system=_DESCRIBE_SYSTEM,
                messages=[{"role": "user", "content": f"description as it was: {old or '(none)'}\n\n"
                                                      f"the change just made: {change}\n\nthe script now:\n{script}"}])
            text = " ".join("".join(b.text for b in msg.content if getattr(b, "type", None) == "text").split())
            if text:
                return text.strip().strip('"')
        except Exception:  # noqa: BLE001 — the revision landed; a stale-marked description beats none
            pass
    return f"{_REVISED.sub('', old or '').strip()} (revised: {change.strip()})".strip()


def author_part(store: DesignStore, part_id: str, intent: str, *, author=None, client=None,
                max_rounds: int = 4, events: Optional[list[Event]] = None, on_event=None,
                use_llm: bool = True, drafter=None, promote_feedback: bool = True,
                interfaces=None, repair_only=None, pick: Optional[dict] = None, on: Optional[str] = None) -> TurnResult:
    """Author a brand-new part into the design, then measure the design with it in place. ``pick``, an edge picked on the
    part ``on``: the new part must touch it, measured each round (CALI-171, #266)."""
    from . import authoring

    events = events if events is not None else []
    before, _ = _measure_design(store)
    seat = _picked_edge(store, on, pick)
    if seat is not None:                         # the pick is a requirement, told and measured (#266)
        interfaces = _also(interfaces, lambda g, script: [_on_the_pick(g, seat)])
    spec = _working_spec(store, part_id, intent + (_seat_words(seat) if seat else ""))

    _emit(events, on_event, "authoring", f"authoring {part_id}…", part=part_id)


    def said_round(n: int, most: int) -> None:          # the first is the line above; a later one says which (CALI-154)
        if n > 1:
            word = {2: "second", 3: "third", 4: "fourth"}.get(n)
            _emit(events, on_event, "authoring", f"authoring {part_id}: {word + ' try' if word else f'try {n}'}",
                  part=part_id, round=n, rounds=most)

    res = authoring.improve(spec, author=author, max_rounds=max_rounds, client=client,
                            ref_base=store.root, interfaces=interfaces, on_round=said_round, repair_only=repair_only)

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
    from .authoring import params_from_spec

    version = store.write_part(part_id, res.script, intent=intent, spec=stored, action="author",
                               feedback=intent, report=report_dict,
                               built=(res.script, params_from_spec(spec), res.geometry))
    _emit(events, on_event, "wrote", f"{part_id} → v{version}", part=part_id, version=version)

    after, part_errors = _measure_design(store)
    _emit(events, on_event, "measured", "measured the whole design", part=part_id)
    broke, fixed = _delta(before, after)

    reply = _compose(store, part_id, version, res, after, broke, fixed, part_errors, verb="built")
    proposal, offer = _offer_promotion(store, part_id, intent, use_llm=use_llm, client=client,
                                       drafter=drafter, enabled=promote_feedback,
                                       events=events, on_event=on_event)
    if offer:
        reply += "\n\n" + offer
    # where it sits, before anything else is said: never a ✓ over a measured miss (#266, rule 6)
    miss = _seat_miss(res.geometry, seat, part_id) if seat is not None else _drafted_miss(proposal, part_id)
    if seat is not None and miss is None:
        reply = reply.replace("\n", f"\nIt sits on the edge you picked on {seat['part']}.\n", 1)
    if miss is not None:
        reply = f"\u2717 {miss}\n\n" + reply.replace("\u2713 ", "", 1).replace("Every check on this part passes.\n", "")
        return TurnResult(action="author", ok=False, part=part_id, version=version,
                          part_report=res.report, report=after, broke=broke, fixed=fixed,
                          part_errors=part_errors, proposal=proposal, events=events, reply=reply)

    return TurnResult(action="author", ok=bool(res.ok) and not broke, part=part_id, version=version,
                      part_report=res.report, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, proposal=proposal, events=events, reply=reply)


#: How close a part added on a picked edge must come to it, everywhere along it (#266).
SEAT_MM = 0.5


def _picked_edge(store: DesignStore, on: Optional[str], pick: Optional[dict]) -> Optional[dict]:
    """The edge picked on part ``on``, in the design's coordinates: ``{"part", "points", "said"}``; None for no edge pick, or
    one whose part changed since (its ids were that version's)."""
    if not pick or pick.get("kind") != "edge" or not on:
        return None
    feats = _features_of(store, on)
    if not feats or pick.get("version") not in (None, feats.get("version")):
        return None
    edge = next((e for e in feats.get("edges") or [] if e["id"] == pick.get("id")), None)
    if edge is None or len(edge.get("points") or []) < 2:
        return None
    return {"part": on, "points": [[float(c) for c in p] for p in edge["points"]], "said": pick.get("said") or "the edge"}


def _pt(p) -> str:
    return "(" + ", ".join(f"{round(c, 2):g}" for c in p) + ")"


def _seat_words(seat: dict) -> str:
    """The requirement as the designer reads it: where the picked edge is, in its coordinates (#266: they were ignored)."""
    pts = seat["points"]
    return (f"\n\nIt goes on the edge picked on {seat['part']} ({seat['said']}): the line from {_pt(pts[0])} to {_pt(pts[-1])}"
            + (f" through {len(pts) - 2} more points" if len(pts) > 2 else "")
            + f", in mm in the design's coordinates, which are this new part's. Its surface must touch that edge along its "
            f"whole length, within {SEAT_MM:g} mm: measured, not assumed.")


def _seat_gap(geometry, seat: dict) -> float:
    """How far the part is from the picked edge at its worst, in mm: the edge sampled along its length, each point's distance to
    the part's surface."""
    import numpy as np

    from . import spatial

    pts = np.asarray(seat["points"], float)
    samples = np.concatenate([a + np.linspace(0.0, 1.0, 9)[:, None] * (b - a) for a, b in zip(pts[:-1], pts[1:])])
    _, dist, _ = spatial.on_surface(geometry.require_mesh(), samples)
    return float(np.max(dist))


def _on_the_pick(geometry, seat: dict):
    """The pick as a round's check: fails, and is repaired, until the part touches the picked edge (#266)."""
    from .evaluate import AssertionResult

    gap = _seat_gap(geometry, seat)
    ok = gap <= SEAT_MM
    return AssertionResult(id="on_the_pick", expr=f"touches the edge picked on {seat['part']}", status="pass" if ok else "fail",
                           passed=ok, actual=round(gap, 2), margin=round(SEAT_MM - gap, 2),
                           detail="" if ok else (f"it sits {round(gap, 2):g} mm off the edge picked on {seat['part']}, the line "
                                                 f"from {_pt(seat['points'][0])} to {_pt(seat['points'][-1])}: move it onto "
                                                 f"that edge"))


def _also(interfaces, more):
    """``interfaces`` with another check added each round."""
    if interfaces is None:
        return more
    return lambda g, script: list(interfaces(g, script)) + list(more(g, script))


def _seat_miss(geometry, seat: dict, part_id: str) -> Optional[str]:
    """The reply's first line when the built part doesn't sit on the pick (#266), else None."""
    if geometry is None:
        return None
    gap = _seat_gap(geometry, seat)
    if gap <= SEAT_MM:
        return None
    return f"Built {part_id}, but it sits {round(gap, 2):g} mm off the edge you picked on {seat['part']}: not where you asked."


def _drafted_miss(proposal, part_id: str) -> Optional[str]:
    """The drafted fit test, measured off now (``min_clearance(new, other) <= x`` at 76.75): the reply's first line (#266)."""
    if proposal is None or proposal.holds_now is not False:
        return None
    m = re.match(r"\s*(?:min_clearance|clearance)\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*<=", proposal.expr or "")
    if not m or part_id not in m.groups() or not isinstance(proposal.actual, (int, float)):
        return None
    other = m.group(2) if m.group(1) == part_id else m.group(1)
    return f"Built {part_id}, but it sits {round(float(proposal.actual), 2):g} mm off {other}: not where you asked."


def _accept(store: DesignStore, proposal, events: list[Event], on_event) -> TurnResult:
    """Lock the proposed assertion in. From here the engine enforces it, not the conversation."""
    from . import promote

    where = promote.accept(store, proposal)
    _emit(events, on_event, "wrote", f"promoted {proposal.id}", part=proposal.part,
          assertion=proposal.id, level=proposal.level)
    lines = [f"\u2713 Locked in on {where}: **{proposal.id}** — `{proposal.expr}`",
             "Every future revision is measured against it; if something breaks it, I'll say so."]
    for _, cid, cexpr in proposal.conflicts:
        lines.append(f"\u21ba Retired **{cid}** (`{cexpr}`) — it couldn't hold alongside this one.")
    from . import verdicts

    now = verdicts.rule(proposal.holds_now)
    if now["kind"] == "fails":
        lines.append("\u26a0 Note: it does **not** hold right now — so the design reads as failing until "
                     "we fix it. Tell me to have a go.")
        if store.design.part(proposal.part or "") is not None:     # "have a go" means: fix that part (#98)
            from . import awaiting

            awaiting.park(store, "fix_rule", part=proposal.part, rule=proposal.id, expr=proposal.expr)
    report, part_errors = _measure_design(store)
    return TurnResult(action="accept", ok=now["counts_as_pass"], part=proposal.part,
                      report=report, part_errors=part_errors, proposal=proposal,
                      events=events, reply="\n".join(lines))


def _decline(store: DesignStore, proposal, events: list[Event], on_event) -> TurnResult:
    """Leave it as a one-off edit — and record that the choice was deliberate."""
    from . import promote

    promote.decline(store, proposal)
    _emit(events, on_event, "wrote", f"declined {proposal.id}", part=proposal.part)
    return TurnResult(action="decline", ok=True, part=proposal.part, proposal=proposal,
                      events=events,
                      reply=(f"Fine — left as a one-off change. `{proposal.expr}` is **not** enforced, "
                             f"so a later revision may undo it."))


def carve_part(store: DesignStore, part_id: str, *, events=None, on_event=None) -> TurnResult:
    """CALI-82: carve a printed part in steps (``carve.study``); the reply says the lightest that holds."""
    from . import carve, mirror

    events = events if events is not None else []
    try:                                           # never on a mirror on its own: it'd be undone (#246 review)
        mirror.refuse_if_mirror(store, part_id, "carve")
    except ValueError as e:
        return TurnResult(action="carve", ok=False, part=part_id, events=events, reply=f"{scrubbed(e)}.")
    try:
        rec = carve.study(store, part_id, emit=lambda k, t="", **d: _emit(events, on_event, k, t, part=part_id, **d))
    except (ValueError, ImportError) as e:
        return TurnResult(action="carve", ok=False, part=part_id, events=events, error=scrubbed(e),
                          reply=f"I couldn't carve it: {scrubbed(e)}.")
    from . import answers, consistency, verdicts

    best = next((x for x in rec["stations"] if x["index"] == rec["best"]), None)  # search: the printed part's lightest
    v = verdicts.carve_step(best, consistency.filled(store, part_id), rec) if best else None   # #132 review, #101
    said = []
    if rec.get("weak"):
        said.append(f"⚠ {rec['weak']}")
    if rec.get("offer") and not rec["offer"]["offers"]:      # nothing to use: why, and the steps are in the study (#167)
        said.append(f"I carved the printed part in {len(rec['stations']) - 1} steps. {rec['offer']['said']}")
    elif best and best["saved_g"] and not v["counts_as_pass"]:
        said.append(f"I carved the printed part in {len(rec['stations']) - 1} steps. It could come off down to step "
                    f"{best['index']} ({best['saved_g']} g less filament), but that isn't a part known to hold: "
                    + (f"the whole part is then {'no higher than ' if best.get('at_most') else ''}{answers._times(best['whole'], need=rec.get('min_safety'))}." if v["kind"] == "fails" and best.get("whole") is not None else
                       f"the voxels were too coarse to see its walls (not resolved): check it again finer first." if v["kind"] in ("unresolved", "unchecked") else f"{v['word']}: {v['why']}." if v.get("why") else f"{v['word']}.")
                    + " Fix that first.")
    elif best and best["saved_g"]:
        said.append(f"I carved the printed part in {len(rec['stations']) - 1} steps. The step to use is step "
                    f"{best['index']}: {best['removed']:.0%} {carve.share(rec)} carved away, {best['saved_g']} g less filament, "
                    f"{answers._times(rec['offer']['quote'] if rec.get('offer') else best['safety'], about=True, need=rec.get('min_safety'))} "
                    f"(printed parts are a rough model). {rec['offer']['said'] + ' ' if rec.get('offer') else ''}It's on the 3D view: **Carve it like this** to make it the "
                    f"part's shape (under *Will it work? → the numbers*, with every step). {answers.PROMISE_POINTER}")
    else:
        said.append("Nothing could come off it and still hold.")
    return TurnResult(action="carve", ok=bool(v and v["counts_as_pass"]), part=part_id, events=events,
                      reply="\n\n".join(said))


def picture_part(store: DesignStore, part_id: str, subject: str, where: str = "", *, points=None, events=None,
                 on_event=None, use_llm: bool = True, client=None, strength: bool = True) -> TurnResult:
    """CALI-78: a picture cut out of one of the part's panels, checked it still holds (``pictures.put``)."""
    from . import mirror, pictures

    events = events if events is not None else []
    try:                                           # never on a mirror on its own: it'd be undone (#246 review)
        mirror.refuse_if_mirror(store, part_id, "cut a picture into")
    except ValueError as e:
        return TurnResult(action="picture", ok=False, part=part_id, events=events, reply=f"{scrubbed(e)}.")
    subject = re.sub(r"^(?:a|an|the|some)\s+", "", (subject or "picture").strip(), flags=re.I) or "picture"
    # just the thing: "T-rex silhouette cut into the side panel" -> "T-rex"
    subject = re.split(r"\s+(?:silhouette|cut|cutout|cut-out|shape|picture|drawing|on|onto|into|out of|in)\b",
                       subject, maxsplit=1, flags=re.I)[0].strip() or "picture"
    try:
        if points:
            shape = pictures.from_drawing(points)
        else:
            _emit(events, on_event, "step", f"Drawing a {subject}", step="draw", part=part_id)
            shape = pictures.draw(subject, use_llm=use_llm, client=client)
        got = pictures.put(store, part_id, shape, subject=subject, where=where, strength=strength,
                           emit=lambda k, t="", **d: _emit(events, on_event, k, t, part=part_id, **d))
    except (ValueError, ImportError) as e:
        return TurnResult(action="picture", ok=False, part=part_id, events=events, error=scrubbed(e),
                          reply=f"I couldn't put a {subject} on it: {scrubbed(e)}.")
    from . import verdicts

    checked = got.get("safety") is not None            # one verdict (CALI-112): only a ✓ with nothing over it is ok
    return TurnResult(action="picture", ok=got["ok"] and (not checked or verdicts.of(got)["counts_as_pass"]), part=part_id,
                      version=got.get("version"), events=events, reply=got["reply"])


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

    from . import promote

    promote.clear(store)                      # the change the offer referred to is being undone
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
    if _design_line(after):
        lines.append(_design_line(after))
    return TurnResult(action="revert", ok=(after is None or after.all_pass), part=part_id,
                      version=version, report=after, broke=broke, fixed=fixed,
                      part_errors=part_errors, events=events, reply="\n".join(lines))


#: CALI-59: a question answered in plain words, from what's measured. A kid and an engineer ask the same
#: question; the kid gets the everyday words, and the engineer asks for the numbers.
_EXPLAIN_SYSTEM = """You answer a question about a design in Caliper, a tool for designing things to build
and make. The person asking may be a child or an engineer. Answer in plain words: short sentences and
everyday words, so a curious 6-year-old could follow it read aloud. If they ask for the numbers, the method
or the detail, give those exactly, still plainly.

- Use only the facts given. If they don't answer the question, say so, and say what to click or tell Caliper
  to find out.
- Never use the tool's own words: voxels, stations, construction(), PARAMS, loads(), scripts. Say "the 3D
  model", "the strength check", "the list of pieces".
- A safety of 3.1 times means "it could hold about three times that before it breaks".
- Use the design's units. No headings. At most 120 words."""


def _facts(store: DesignStore, scope: Optional[str]) -> str:
    """What's known, for a plain answer: the four questions' answers (the design's and the selected part's),
    the strength check behind them, and the last of the conversation."""
    from . import answers, load_study
    from .design_api import design_state

    state = design_state(store)
    out = [f"design: {store.design.name}: {store.design.prompt}", f"units: {store.design.display_units}"]
    for r in store.design.requirements:
        out.append(f"requirement: {r.question} -> {r.answer}" + ("" if r.source == "answered" else " (assumed)"))
    promised = False
    for pid in [None] + [p.id for p in store.design.parts if p.id == scope or len(store.design.parts) == 1]:
        for c in answers.answers(store, state, pid):
            for ln in c["lines"]:
                out.append(f"{pid or 'the design'} · {c['q']} {ln['text']}")
            promised = promised or bool(c.get("promise"))
    if promised:                                       # so a plain answer about strength can say it (CALI-86)
        out.append("what a strength verdict promises: "
                   + answers.promise(store, [scope] if scope else [p.id for p in store.design.parts]))   # (#64 item 14)
    from . import consistency, verdicts

    for run in load_study.list_runs(store)[:2]:
        filled = consistency.filled(store, run["part"])
        middle = bool(consistency.bare_edge(store, run["part"]))     # loaded in the middle only (CALI-94)
        part = store.design.part(run["part"])
        older = part is None or run.get("version") != part.version      # an older run says so (#132 review)
        for c in run.get("cases") or []:
            v = verdicts.case(run, c, filled=filled, stale=older, edge=middle)   # one verdict (CALI-112)
            out.append(f"strength check of {run['part']} v{run['version']}: {c.get('name')} {c.get('lb')} lb x "
                       f"{c.get('factor')}: verdict {v['word'].upper()}; safety {c.get('safety')} ({c.get('governs')}), "
                       f"breaks near {c.get('breaks_lb')} lb; needs {run.get('min_safety')}"
                       # never a verdict to repeat: the FEA couldn't see the wall (CALI-110), or the middle only (CALI-94)
                       + ("; NOT RESOLVED: the voxels were too coarse to see its walls, so this number is no verdict"
                          if v["kind"] in ("unresolved", "unchecked") or v.get("coarse") else "")
                       + ("; CHECKED IN THE MIDDLE ONLY: the front edge, where people stand, isn't, so this is no "
                          "verdict" if v["kind"] == "edge" else "")
                       + ("; NOT TRUSTED: it ran on a solid with more in it than its pieces" if v["kind"] == "untrusted" else "")
                       + (f"; NOT SETTLED: {v.get('why')}, so this number is no verdict" if v["kind"] == "span" else ""))
        out += [f"strength note: {n}" for n in (run.get("notes") or [])[:4]]
    said = [e for e in store.log() if e.get("kind") in ("message", "reply")][-6:]
    out += [f"{'they said' if e['kind'] == 'message' else 'Caliper said'}: {(e.get('text') or e.get('reply') or '')[:600]}"
            for e in said]
    return "\n".join(out)


def explain(store: DesignStore, message: str, scope: Optional[str] = None, client=None,
            model: Optional[str] = None) -> str:
    """The question answered in plain words by Claude, from the facts. Raises on any failure (the caller
    falls back to the facts as they are)."""
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    msg = llm.ask(
        client, "explain", model=model, system=_EXPLAIN_SYSTEM,
        messages=[{"role": "user", "content": f"facts:\n{_facts(store, scope)}\n\nquestion: {message}"}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    if not text:
        raise ValueError("an empty answer")
    return text


def answer(store: DesignStore, message: str, scope: Optional[str] = None,
           note: str = "", events: Optional[list[Event]] = None, *, use_llm: bool = False,
           client=None) -> TurnResult:
    """Report the measured state. No geometry moves — so the answer is facts, not an opinion. With Claude
    (CALI-59), the question itself is answered from those facts, in plain words."""
    events = events if events is not None else []
    stopped = None
    if note.startswith("ask which: "):                  # the parts or the part beside them: asked (#242 re-check)
        return TurnResult(action="answer", ok=True, part=scope, events=events, reply=note.split(": ", 1)[1])
    if note.startswith("offer a picture: "):           # "make it look like a dinosaur": offered, not done (#65)
        return TurnResult(action="answer", ok=True, part=scope, events=events, reply=_offer(note.split(": ", 1)[1]))
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            return TurnResult(action="answer", ok=True, part=scope, events=events,
                              reply=explain(store, message, scope, client=client))
        except llm.Stopped as e:                 # said, then the facts as they are
            stopped = llm.said(e)
        except Exception:  # noqa: BLE001 — the facts as they are, then
            pass
    d = store.design
    lines = ([f"{stopped}. Here's what's measured:", ""] if stopped else []) + [f"**{d.name}** — {d.prompt}" if d.prompt else f"**{d.name}**"]
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
        lines.append(f"  ⚠ {pid} won't build: {scrubbed(err)}")
    if report is not None:
        failing = _fail_lines(report)
        lines.append("")
        said = report.said()                    # never "all pass" with a check that hasn't run (#103 review)
        lines.append(said[0].upper() + said[1:] + (":" if failing else "."))
        lines.extend(failing)
    if note.startswith("ambiguous"):
        lines.append("")
        lines.append("_If you meant to change a part, click it in the viewer or name it "
                     "(e.g. \"make the carriage 5mm wider\")._")
    return TurnResult(action="answer", ok=True, part=scope, report=report,
                      part_errors=part_errors, events=events, reply="\n".join(lines))


def _volume(store: DesignStore, part_id: str):
    """The part's volume now, in mm³, or None (CALI-107: whether a request changed the shape at all)."""
    try:
        return float(abs(store.part_geometry(part_id).require_mesh().volume))
    except Exception:  # noqa: BLE001 — not measurable is said, not hidden
        return None


#: The ends of a PARAMS name, in words: foot_fillet_r is the foot fillet radius (#119 review).
_ENDS = {"r": "radius", "t": "thickness", "w": "width", "h": "height", "d": "depth", "dia": "diameter",
         "l": "length", "len": "length", "x": "x", "y": "y", "z": "z"}
#: Names that count things, said without a unit.
_COUNT = ("n", "num", "count", "rows", "cols", "columns", "holes", "slats", "steps", "sides", "segments", "teeth",
          "legs", "panels", "spokes", "stations", "openings", "pieces")


def _plain(key: str) -> str:
    """A PARAMS name as words: ``foot_fillet_r`` → "foot fillet radius"."""
    bits = key.split("_")
    return " ".join(_ENDS.get(b, b) if i == len(bits) - 1 else b for i, b in enumerate(bits))


def _counts(key: str) -> bool:
    bits = key.lower().split("_")
    return bits[0] in _COUNT or bits[-1] in _COUNT


def _asked(store: DesignStore, asked: str, prior: str, new: str, volumes) -> list[str]:
    """What was asked for, what changed, what the build shows, and what nothing measures (CALI-107, rule 6): a
    reply never lets "the checks pass" stand for "what you asked for happened"."""
    from . import answers, fallbacks

    inches = store.design.display_units == "in"

    def said(key, v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return repr(v) if v is not None else "none"
        if _counts(key):                             # a count: rows, holes, slats…
            return f"{v:g}"
        return f"{v:g} mm" + (f" ({answers._small_len(v, True)})" if inches and v > 0 else "")   # a length, always its unit

    out = [f"Asked for: {asked.strip()}"]
    moved = fallbacks.changed(prior or "", new or "")
    out.append("Changed: " + (", ".join(f"{_plain(k)} {said(k, a)} → {said(k, b)}" for k, a, b in moved) if moved
                              else "no number in its PARAMS; the change is in how it's built"))
    was, now = volumes or (None, None)
    if was is not None and now is not None:
        out.append(f"Its shape didn't change (the same volume, {was / 1000:,.0f} cm³): what you asked for may not have "
                   f"happened. Look at it, and say so if it didn't." if abs(now - was) <= 1e-6 * max(was, 1.0) else
                   f"Measured: its volume went from {was / 1000:,.0f} to {now / 1000:,.0f} cm³.")
    out.append("Not measured: whether that's what you meant. The checks below are the part's own rules, not your "
               "request; look at it to see it's right.")
    return out


def _not_closed(res) -> str:
    """The build's own line when :func:`measure.clean` couldn't close the part (CALI-121), else ""."""
    from .measure import closed, open_near

    try:
        mesh = res.geometry.require_mesh() if res.geometry is not None else None
    except Exception:  # noqa: BLE001 — no mesh to judge: the build says what it can
        return ""
    if mesh is None or closed(mesh):
        return ""
    return (f"⚠ Its shape isn't closed {open_near(mesh)}: strength, weight and carving can't be checked until it "
            f"is.")


def _overclaimed(store: DesignStore) -> list[str]:
    """A locked check whose name says a part mirrors another but whose expression doesn't measure it, said with what
    ``mirrors()`` measures (CALI-161, #239: step-stool-4's ``side_left_mirrors_side_right``, Theo's, kept as he took
    it, compares the two bounding boxes' sides)."""
    from . import measure, promote
    from .assembly import _names

    out = []
    ids = {p.id for p in store.design.parts}
    for a in store.assembly.assertions:
        if not promote.overclaims(a.id, a.expr, sorted(ids)):
            continue
        pair = [n for n in sorted(_names(a.expr)) if n in ids]
        named = [p for p in ids if p in a.id]
        pair = sorted(named, key=a.id.index)[:2] if len(named) >= 2 else pair[:2]
        what = "only overall size" if "bbox(" in a.expr else "something else"
        try:
            off = measure.mirror_off(store.part_geometry(pair[0]), store.part_geometry(pair[1]))
            said = f"mirrors() says their surfaces are up to {off:g} mm apart"
        except Exception as e:  # noqa: BLE001 — what couldn't be measured is said
            said = f"mirrors() couldn't measure them ({scrubbed(e)})"
        out.append(f"⚠ {a.id} compares {what}; {said}.")
    return out


def _compose(store, part_id, version, res, after, broke, fixed, part_errors, verb: str, *, asked: str = "",
             prior: str = "", new: str = "", volumes=None) -> str:
    """The chat reply: what happened, what it measures, and — critically — what it broke. For a request, what was
    asked for and what changed come first, and nothing below stands for it (CALI-107)."""
    head = "✓" if (res.ok and not broke) else "✗"
    lines = [f"{head} {verb} **{part_id}** → v{version} ({res.rounds} round(s))"]
    if asked:
        lines += _asked(store, asked, prior, new, volumes)

    shut = _not_closed(res)
    if shut:                                    # said once, by the build itself (CALI-121)
        lines.append(shut)
    if res.report is not None:
        part_fails = _fail_lines(res.report)
        if part_fails:
            lines.append(f"{len(part_fails)} check(s) on this part still failing:")
            lines.extend(part_fails)
        else:
            lines.append("The part's own checks pass." if asked else "Every check on this part passes.")

    if broke:
        lines.append("")
        lines.append(f"⚠ This change **broke {len(broke)} design check(s)** that passed before:")
        lines.extend(_fail_lines(after, only=broke))
        lines.append("_Tell me how to fix it, or say **roll it back** to undo this revision._")
    if fixed:
        lines.append(f"✓ It also fixed: {', '.join(fixed)}")
    if not broke and _design_line(after):
        lines.append(_design_line(after).replace("checks pass", "checks still pass"))
    lines += _overclaimed(store) if store is not None else []     # a reply composed with no design has no locked checks
    for pid, err in part_errors.items():
        if pid != part_id:
            lines.append(f"⚠ {pid} won't build: {scrubbed(err)}")
    if getattr(res, "error", None) and res.geometry is not None:     # a round that built is kept, and why it stopped there is said
        lines.append(f"{res.error}.")
    return "\n".join(lines)


#: Asking for one part to be another's mirror or copy, in Theo's words too: "make both sides the right side" (#242 review)
_MIRROR = re.compile(r"\bmirror(?:s|ed|ing)?\b|\bsymmetric|\blike\s+(?:the\s+|each\s+)?other\b|\bidentical\b|"
                     r"\bcop(?:y|ies|ied)\b|\blike\s+the\s+(?:left|right|front|back|rear|other)\s+(?:one|side)\b|"
                     r"\bthe\s+same\b(?!\s+(?:as|thickness|width|height|length|depth|size|diameter|radius|spacing|"
                     r"thick|wide|tall|long|deep)\b)|"
                     r"\buse\s+(?:the\s+)?(?:\w+\s+){1,2}for\s+(?:both|all|each)\b|"
                     r"\b(?:both|all|each)\s+(?:of\s+)?(?:the\s+)?\w+\s+the\s+(?:left|right|front|back|rear|other|first|second)\b",
                     re.I)
#: "match" and "the same as" are a mirror only before one of the parts asked of, "the other" or "each other" (#242
#: re-check: "taller to match the top" and "match the stretcher's thickness" aren't)
_MATCH = re.compile(r"\b(?:match(?:es|ing)?|(?:the\s+)?same\s+as)\s+(?:the\s+)?(?P<what>[a-z_ ]+)", re.I)


def _mirror_asked(message: str, parts: list[str]) -> bool:
    """Whether a request over ``parts`` asks for one to be another's mirror or copy, in any of the words for it."""
    text = (message or "").lower()
    if _MIRROR.search(text):
        return True
    for m in _MATCH.finditer(text):
        what = m.group("what").strip()
        if re.match(r"(?:each\s+)?other\b", what) or any(re.match(rf"{_said_as(p)}\b", what) for p in parts):
            return True
    return False


def _listed(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def refine_several(store: DesignStore, parts: list[str], message: str, *, scope: Optional[str] = None,
                   pick: Optional[dict] = None, **kw) -> TurnResult:
    """An edit that names several parts changes each (CALI-163, #241), in plan order, each built and checked before the
    next, and the reply says first what changed and what didn't: a tick only when every part named changed (rule 6:
    "✓ revised side_left" over a request that named both sides read greener than it was).

    Each designer is told which part its revision is for, and what the parts before it became (#242 review: a size
    they share can follow). The count is said up front, and "2 of 3" as each starts. A pick goes with the part it was
    made on, the selected one."""
    from . import fallbacks

    events = kw.pop("events", None)
    events = events if events is not None else []
    on_event = kw.get("on_event")
    _emit(events, on_event, "authoring", f"revising {len(parts)} parts: {', '.join(parts)}", parts=list(parts))
    done, left, still, results, became = [], [], [], [], []
    for n, pid in enumerate(parts, 1):
        others = [p for p in parts if p != pid]
        focus = (f"This request names {_listed(parts)}. This revision is to {pid} only: {_listed(others)} "
                 f"{'is' if len(others) == 1 else 'are'} revised on {'its' if len(others) == 1 else 'their'} own.")
        if became:
            focus += " Already revised for it: " + "; ".join(became) + "."
        prior = store.read_script(pid) if store.is_scripted(pid) else ""
        r = refine_part(store, pid, message, events=events, focus=focus, keep_same=False, of=f"{n} of {len(parts)}",
                        pick=pick if pid == scope else None, **kw)
        results.append(r)
        if r.version is not None and r.moved is False:   # written, but nothing measured moved: kept, said, no ✓ (#242)
            still.append(pid)
        elif r.version is not None:                # a number, its volume, its size or its place moved
            done.append(pid)
            moved = fallbacks.changed(prior, store.read_script(pid))
            became.append(f"{pid} " + (", ".join(f"{k} {a:g} → {b:g}" if isinstance(a, (int, float)) and
                                                 isinstance(b, (int, float)) else f"{k} {a!r} → {b!r}"
                                                 for k, a, b in moved) if moved else "changed in how it's built"))
        else:
            why = ("its code came back as it was" if r.error == "unchanged"
                   else f"it wouldn't build ({scrubbed(r.error)})" if r.error else "it wasn't revised")
            left.append((pid, why))
    mirror = _mirror_asked(message, parts)
    notes = ([f"{pid} not changed: {why}" for pid, why in left]
             + [f"{pid}: the code changed, but no number, size or position I measure moved" for pid in still])
    if done:
        tick = not notes and not mirror and all(r.ok for r in results)       # never over a break, a gap or a hedge
        first = f"{'✓' if tick else '!'} Changed {_listed(done)}" + (f"; {'; '.join(notes)}" if notes else "") + "."
    elif still:
        first = "! " + "; ".join(notes) + "."
    else:
        first = f"✗ Nothing changed: {_listed([p for p, _ in left])} ({'; '.join(notes)})."
    lines = [first]
    if pick and scope and scope not in parts:      # said, not dropped (#242 re-check)
        lines.append(f"What you picked is on {scope}, which this doesn't change: the pick wasn't used.")
    if mirror:
        lines.append("Each was revised on its own, not mirrored: to make one the other's mirror, say \"use the right "
                     "side for both\" (or name the one to keep), and the other becomes its mirror (#239).")
    lines.append("")
    lines += ["\n\n".join(r.reply for r in results if r.reply)]
    broke = sorted({b for r in results for b in r.broke})
    last = next((r for r in reversed(results) if r.version is not None), results[-1])
    return TurnResult(action="refine", ok=not left and not still and not mirror and all(r.ok for r in results), part=parts[0],
                      version=last.version, part_report=last.part_report, report=last.report, broke=broke,
                      fixed=sorted({f for r in results for f in r.fixed} - set(broke)),
                      part_errors={k: v for r in results for k, v in r.part_errors.items()},
                      events=events, reply="\n".join(lines))


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------
def _reviewing(store: DesignStore) -> bool:
    """A plan of several parts saved and none of them built: what the chat changes is the plan (CALI-35)."""
    plan = store.design.plan or {}
    ids = [p["id"] for p in plan.get("parts") or []]
    made = [p["id"] for p in plan.get("parts") or [] if p.get("role") != "fixed"]
    return len(made) > 1 and not any(store.design.part(i) and store.design.part(i).version for i in ids)


def _built_plan(store: DesignStore) -> bool:
    """A plan of several parts with a skeleton, and a part of it built: its numbers now drive the parts (CALI-35c)."""
    plan = store.design.plan or {}
    ids = [p["id"] for p in plan.get("parts") or []]
    return (len(ids) > 1 and bool(store.design.skeleton)
            and any(store.design.part(i) and store.design.part(i).version for i in ids))


def skeleton_edit(store: DesignStore, message: str, *, client=None, use_llm: bool = True, events=None,
                  on_event=None) -> Optional[TurnResult]:
    """After the build, a message that changes only shared numbers ("make the mast 10 ft"): the skeleton takes them
    and every part that reads one rebuilds, with no new design, and the whole design is measured again (CALI-35c).
    None when it names no number, or changes more than the numbers (a part, a check): the chat takes it as ever."""
    from . import plan as P
    from . import skeleton as S
    from . import verdicts

    events = events if events is not None else []
    if not P._said_numbers(message) or not (use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY"))):
        return None
    try:
        before, after = P.revise(store, message, client=client)
    except Exception:  # noqa: BLE001 — not a change to the plan's numbers: the chat takes it as ever
        return None
    same = lambda p: {**p.model_dump(), "skeleton": None}   # noqa: E731 — the plan but its numbers
    if same(before) != same(after) or before.skeleton == after.skeleton:
        return None                                   # more than a shared number, or none: not a drive
    _emit(events, on_event, "step", "Changing a shared number and rebuilding what reads it")
    got = S.drive(store, [s.model_dump() for s in after.skeleton], said=message)
    rep = got.get("report")
    # it worked if nothing it rebuilt or measured fails: a check still waiting on an unbuilt part is said, not a fail
    ok = (not got.get("failed") and not got.get("refused") and not got.get("unmoved")
          and (rep is None or verdicts.report(rep.to_dict())["kind"] != "fails"))
    return TurnResult("skeleton", S.said(got), ok=ok, events=events)


def plan_edit(store: DesignStore, message: str, *, client=None, use_llm: bool = True, events=None,
              on_event=None) -> TurnResult:
    """Change the plan as the person said ("make the mast 10 ft"), check it, save it, and say what changed."""
    from . import plan as P

    events = events if events is not None else []
    if not (use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY"))):
        return TurnResult("plan", "Changing the plan needs Claude, and it isn't set up here. Press Build it to "
                                  "go on with the plan as it is.", ok=False, events=events)
    _emit(events, on_event, "step", "Changing the plan")
    try:
        before, after = P.revise(store, message, client=client)
    except Exception as e:  # noqa: BLE001 — a change that can't be made or used leaves the plan as it was
        return TurnResult("plan", f"I couldn't change the plan that way: {scrubbed(e)}. It's as it was.", ok=False,
                          events=events, error=scrubbed(e))
    inches = store.design.display_units == "in"
    said = P.changes(before, after, inches)
    if not said:
        return TurnResult("plan", "That didn't change the plan. Say which part or number to change.", ok=False,
                          events=events)
    P.save(store, after, "review")
    gone = P.dropped_line(after)
    return TurnResult("plan", "Changed the plan: " + "; ".join(said) + ".\n\n" + P.headline(after, store.design.name)
                      + (f" ({gone[0].upper() + gone[1:]}.)" if gone else "") + P.said_aside(after), events=events)


_REMOVE = re.compile(r"^\s*(?:please\s+)?(?:remove|delete|get\s+rid\s+of|take\s+out)\s+(?:the\s+)?(.+?)\s*[.!]*\s*$", re.I)
_RESTORE = re.compile(r"^\s*(?:please\s+)?(?:put\s+back|restore|bring\s+back|undelete)\s+(?:the\s+)?(.+?)\s*[.!]*\s*$"
                      r"|^\s*(?:please\s+)?put\s+(?:the\s+)?(.+?)\s+back\s*[.!]*\s*$", re.I)


def _named_part(store: DesignStore, words: str, scope: Optional[str], ids: Optional[list] = None) -> Optional[str]:
    """The part a short phrase names: its id, or its id with spaces ("conical skirt"); "it"/"this" is the clicked one."""
    w = re.sub(r"\s+(part|piece)$", "", words.strip().lower())
    if w in ("it", "this", "that", "this part", "that part") and scope:
        return scope
    for pid in ids if ids is not None else [p.id for p in store.design.parts]:
        if w in (pid.lower(), pid.lower().replace("_", " ")):
            return pid
    return None


def _remove_or_restore(store: DesignStore, message: str, scope: Optional[str], *, events, on_event):
    """ "remove conical_skirt" asks once (its files go to the trash); "put back conical_skirt" restores it (#98)."""
    from . import awaiting, trash

    m = _RESTORE.match(message or "")
    if m:
        pid = _named_part(store, m.group(1) or m.group(2), None, ids=[t["part"] for t in trash.listing(store)])
        if pid is None:
            return None
        try:
            got = trash.restore(store, pid=pid)
        except ValueError as e:
            return TurnResult(action="restore", ok=False, part=pid, events=events, reply=f"I couldn't put it back: {scrubbed(e)}.")
        report, part_errors = _measure_design(store)
        return TurnResult(action="restore", ok=True, part=pid, events=events, report=report, part_errors=part_errors,
                          reply=f"Put back the {pid.replace('_', ' ')} ({pid}), as it was."
                                + (f" {got['waiting'][0][0].upper()}{'; '.join(got['waiting'])[1:]}."
                                   if got["waiting"] else "")
                                + (f"\n\nThe design checks: {report.said()}." if report is not None else ""))
    m = _REMOVE.match(message or "")
    if m:
        pid = _named_part(store, m.group(1), scope)
        if pid is None:
            return None
        awaiting.park(store, "remove", part=pid)
        return TurnResult(action="ask", ok=True, part=pid, events=events,
                          reply=f"Remove {pid}? Its files go to the design's trash, so it can be put back.")
    return None


def _awaited(store: DesignStore, message: str, scope: Optional[str], **kw) -> Optional[TurnResult]:
    """Caliper's own last question, answered (#98): a fix for a rule it just locked in that doesn't hold, a removal
    to confirm, a repeat to confirm. Anything else lets it lapse (None: the turn goes on as ever)."""
    from . import awaiting, trash

    aw = awaiting.pending(store)
    if aw is None:
        return None
    if aw["kind"] == "grain_way":                      # "which way?": a bare direction answers it, for that piece
        from . import grain

        awaiting.clear(store)
        try:
            got = grain.answer(store, aw["part"], aw["piece"], message)
        except ValueError as e:                        # the part or sheet has gone since it asked
            return TurnResult(action="grain", ok=False, part=aw["part"], events=kw["events"],
                              reply=f"I couldn't keep that grain: {scrubbed(e)}.")
        return None if got is None else _grain_reply(got)
    yes = awaiting.reads(message)
    awaiting.clear(store)
    if yes is None:
        return None
    pid, events, on_event = aw.get("part"), kw["events"], kw["on_event"]
    if store.design.part(pid or "") is None and aw["kind"] != "remove":
        return None
    if not yes:
        return TurnResult(action="ask", ok=True, part=pid, events=events,
                          reply={"remove": f"Kept {pid}.", "repeat": "Left it as it is.",
                                 "fix_rule": f"Left it: {aw.get('rule')} still doesn't hold."}.get(aw["kind"], "Left it."))
    if aw["kind"] == "mirrors":                       # "make these 3 panels mirrors of the top panel?" yes (#246)
        return _mirror_these(store, pid, [t for t in aw.get("targets") or [] if store.design.part(t)], aw.get("message") or "")
    if aw["kind"] == "remove":
        if store.design.part(pid or "") is None:
            return TurnResult(action="remove", ok=False, part=pid, events=events, reply=f"There's no {pid} to remove.")
        got = trash.remove(store, pid)
        report, part_errors = _measure_design(store)
        went = [f"rule {r}" for r in got["rules"]] + [f"mate {m}" for m in got["mates"]]
        with_it = (f", and its {', '.join(went[:-1]) + ' and ' + went[-1] if len(went) > 1 else went[0]} went with it"
                   if went else "")
        return TurnResult(action="remove", ok=True, part=pid, events=events, report=report, part_errors=part_errors,
                          reply=f"Removed {pid}: its files are in the design's trash{with_it} (say \"put back {pid}\" "
                                f"to restore {'them all' if went else 'it'})."
                                + (f"\n\nThe design checks: {report.said()}." if report is not None else ""))
    message = (f"Change it so it meets its rule {aw['rule']}: {aw['expr']}. Change only what that needs."
               if aw["kind"] == "fix_rule" else aw["message"])
    from . import part_rules

    return refine_part(store, pid, message, author=kw["author"], client=kw["client"], max_rounds=kw["max_rounds"],
                       events=events, on_event=on_event, use_llm=kw["use_llm"], drafter=kw["drafter"],
                       measured=part_rules.to_fix(store, pid, aw["rule"]) if aw["kind"] == "fix_rule" else "",
                       pick=aw.get("pick"),                  # a parked repeat keeps its pick: "yes" runs the same check (#177)
                       # fixing a rule it already has: never an offer to lock a looser copy of it (#153)
                       promote_feedback=kw["promote_feedback"] and aw["kind"] != "fix_rule")


_DIRECTION = re.compile(r"\b(wider|narrower|taller|shorter|thicker|thinner|longer|deeper|shallower|bigger|smaller|"
                        r"higher|lower|heavier|lighter|rounder)\b")


def _repeats(store: DesignStore, pid: str, message: str) -> Optional[str]:
    """The question to ask when a refine's request matches what the part's last revision just did (#98: the foot
    flange widened 1 in twice): the same words, or the same numbers and the same directions. None otherwise."""
    entry = store.design.part(pid)
    last = next((h for h in reversed(store.history(pid)) if h.get("kind") == "revision"), None) if entry else None
    if entry and any(h.get("kind") == "pick_missed" and h.get("version") == entry.version for h in store.history(pid)):
        return None                                 # it didn't do that: it missed (#177)
    if not last or last.get("action") != "refine" or last.get("version") != entry.version or not last.get("feedback"):
        return None
    norm = lambda s: re.sub(r"[^a-z0-9.]+", " ", s.lower()).strip()                   # noqa: E731
    gist = lambda s: (sorted(re.findall(r"\d+(?:\.\d+)?", s)), sorted(_DIRECTION.findall(s.lower())))   # noqa: E731
    a, b = last["feedback"], message
    if norm(a) != norm(b) and not (gist(a)[0] and gist(a)[1] and gist(a) == gist(b)):
        return None
    return (f"v{entry.version} already did that (\"{a}\"). Do it again, on top of v{entry.version}? Say yes to do "
            f"it again, or no to leave it.")


#: "use the right side for both", "choose the right side … to use for both sides", "make the left side a mirror of the
#: right side", "mirror the right side onto the left": one part made its sibling's mirror (CALI-161, #239)
_SWAP = [re.compile(r"\buse (?:the )?(?P<src>[a-z_ ]+?) for (?:both|all|each)\b", re.I),
         re.compile(r"\b(?:choose|take|pick) (?:the )?(?P<src>[a-z_ ]+?)\b[^.;]*?\bfor (?:both|all|each)\b", re.I),
         re.compile(r"\bmake (?:the )?(?P<dst>[a-z_ ]+?) (?:a )?mirror(?: image)? of (?:the )?(?P<src>[a-z_ ]+?)\s*(?:[.,;!]|$)", re.I),
         re.compile(r"\bmirror (?:the )?(?P<src>[a-z_ ]+?) (?:onto|to|for) (?:the )?(?P<dst>[a-z_ ]+?)\s*(?:[.,;!]|$)", re.I)]
#: "make the left one different", "stop mirroring the left side", "unmirror side_left": the mirror broken
_BREAK = re.compile(r"\bmake (?:the )?(?P<a>[a-z_ ]+?) (?:different|its own(?: part)?|separate)\b|"
                    r"\b(?:stop|don'?t) mirror(?:ing)? (?:the )?(?P<b>[a-z_ ]+?)\s*(?:[.,;!]|$)|\bunmirror (?:the )?(?P<c>[a-z_ ]+)", re.I)
#: Words that say where a part is: "the left one" is the part with "left" in its id.
_WHERE = {"left", "right", "front", "back", "rear", "top", "bottom", "upper", "lower", "inner", "outer"}


def _part_said(words: str, ids: list[str], among: Optional[list] = None) -> Optional[str]:
    """A part from a few words: its name, or "the left one" (the one with that position in its id)."""
    hit = named_part(words, ids)
    if hit:
        return hit
    where = set(_words(words)) & _WHERE
    pool = [i for i in (among if among is not None else ids) if where and where <= set(i.lower().split("_"))]
    return pool[0] if len(pool) == 1 else None


def _mirror_siblings(pid: str, ids: list[str]) -> list[str]:
    """The parts whose id differs from ``pid``'s only by where it is (side_left, side_right)."""
    mine = [t for t in pid.lower().split("_") if t not in _WHERE]
    return [i for i in ids if i != pid and [t for t in i.lower().split("_") if t not in _WHERE] == mine]


def _mirror_said(store: DesignStore, message: str, scope: Optional[str]) -> Optional[TurnResult]:
    """One part made its sibling's mirror, or a mirror broken, in the person's words (CALI-161, #239). Deterministic, no
    Claude call, one round; None when the message isn't about mirroring."""
    from . import mirror

    ids = [p.id for p in store.design.parts]
    text = (message or "").strip()
    brk = _BREAK.search(text)
    mirrors = [i for i in ids if mirror.source_of(store, i)]
    if brk and mirrors:
        pid = _part_said(next(g for g in brk.groups() if g), ids, among=mirrors)
        if pid in mirrors:
            source = mirror.source_of(store, pid)
            v = mirror.unmirror(store, pid)
            return TurnResult(action="mirror", ok=True, part=pid, version=v,
                              reply=(f"**{pid}** is its own part now (v{v}): it keeps the mirrored shape, and no longer "
                                     f"follows {source}. Ask for the change you want on it."))
    if _SIZE_ASKED.search(text):                   # "pick the top panel thickness for all panels": a size, not a mirror
        return None
    for pattern in _SWAP:
        m = pattern.search(text)
        if m is None:
            continue
        source = _part_said(m.group("src"), ids)
        if source is None:
            continue
        dst = _part_said(m.group("dst"), ids) if "dst" in pattern.groupindex and m.group("dst") else None
        built = lambda i: bool(store.design.part(i) and store.design.part(i).version and store.is_scripted(i))  # noqa: E731
        if dst:
            targets = [dst] if dst != source else []
        else:                                      # only a like-for-like twin, and only one without asking (#246 review)
            if not built(source) or not all(built(t) for t in _mirror_siblings(source, ids)):
                continue                           # a plan under review mirrors in the plan, not here
            targets = [t for t in _mirror_siblings(source, ids) if _twin(store, source, t)]
            if not targets and built(source):
                return TurnResult(action="mirror", ok=False, part=source,
                                  reply=f"Nothing here is the {source.replace('_', ' ')}'s shape, so nothing can be its "
                                        f"mirror. Say which part to mirror it as: \"make <part> a mirror of {source}\".")
            if _WIDE.search(text) or len(targets) > 1:
                from . import awaiting

                awaiting.park(store, "mirrors", part=source, targets=targets, message=text)
                return TurnResult(action="ask", ok=True, part=source,
                                  reply=f"Make {_listed_ids(targets)} {'mirrors' if len(targets) > 1 else 'a mirror'} of "
                                        f"{source}? {'They' if len(targets) > 1 else 'It'}'d lose "
                                        f"{'their' if len(targets) > 1 else 'its'} own script (kept in the versions). "
                                        f"Say yes, or name the one: \"make {targets[0]} a mirror of {source}\".")
        if not targets or not built(source) or not all(built(t) for t in targets):
            continue                               # a plan under review mirrors in the plan, not here
        return _mirror_these(store, source, targets, text)
    return None


#: A mirror request about a size is about the size: "pick the top panel thickness for all panels" (#246 review)
_SIZE_ASKED = re.compile(r"\b(?:thickness|thick|width|wide|height|tall|length|long|depth|deep|size|diameter|radius)\b", re.I)
#: More than a pair: asked first, never done in one go (#246 review: "for all of them" made four panels mirrors)
_WIDE = re.compile(r"\b(?:all|every|each)\b", re.I)


def _twin(store: DesignStore, a: str, b: str, share: float = 0.2) -> bool:
    """Whether two parts are the same shape give or take: each axis's extent within ``share`` of the other's (a top
    panel and a side panel aren't, though their sorted sizes are the same)."""
    try:
        ea = store.part_geometry(a).require_mesh().extents
        eb = store.part_geometry(b).require_mesh().extents
    except Exception:  # noqa: BLE001 — a part that won't build isn't known to be a twin
        return False
    return all(abs(x - y) <= share * max(x, y, 1e-9) for x, y in zip(ea, eb))


def _mirror_these(store: DesignStore, source: str, targets: list[str], text: str) -> TurnResult:
    """Make each of ``targets`` a mirror of ``source``, and say so: what's already one, what was made, what couldn't be."""
    from . import mirror

    said = []
    try:
        for t in targets:
            if mirror.source_of(store, t) == source:     # asked again: already so, nothing written (#246 review)
                said.append(f"**{t}** already mirrors {source}: nothing to change.")
                continue
            was = store.design.part(t).version
            v = mirror.make(store, t, source, feedback=text)
            got = mirror.of(store.read_script(t))
            said.append(f"**{t}** is now a mirror of {source} (v{v}), flipped in the {got['plane']} plane "
                        f"{'xyz'[mirror.PLANES[got['plane']]]} = {got['at'][mirror.PLANES[got['plane']]]:g} mm. "
                        f"Its own script is kept as v{was} in its versions.")
    except ValueError as e:
        return TurnResult(action="mirror", ok=False, part=source, reply="\n".join(said + [f"I couldn't mirror it: {scrubbed(e)}."]))
    report, errors = _measure_design(store)
    line = _design_line(report)
    made = any("is now a mirror" in x for x in said)
    more = (_MORE.search(text) or _DIRECTION.search(text)) if text else None   # "…for both sides, taller": not done
    if more:
        said.insert(0, f"! Only the mirror is done: the rest of what you asked (\"{more.group(0)}\") isn't yet. Ask for it "
                       f"on {source} now, and {_listed_ids(targets)} follow{'s' if len(targets) == 1 else ''}.")
    return TurnResult(action="mirror", ok=not more and not errors and (report is None or not report.failures),
                      part=targets[0], version=store.design.part(targets[0]).version, report=report, part_errors=errors,
                      reply="\n".join(said) + (f"\n\nOne script for {_listed_ids([source, *targets])}: a change to "
                                               f"either changes both, and it cost no designer time." if made else "")
                      + (f"\n{line}" if line and made else ""))


def _listed_ids(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _grain_said(store: DesignStore, message: str, scope: Optional[str]) -> Optional[TurnResult]:
    """A sheet's face grain the person states (CALI-126): kept in the design, said back as the maker will read it.
    Deterministic, no Claude call; None when the message isn't about a grain."""
    from . import grain

    try:
        got = grain.from_chat(store, message, scope)
    except ValueError as e:
        return TurnResult(action="grain", reply=f"I couldn't keep that grain: {scrubbed(e)}.", ok=False)
    if got is None:
        return None
    if got.get("ask"):                                 # "which way?": the reply answers for this piece (#153)
        from . import awaiting

        awaiting.park(store, "grain_way", **got["ask"])
    return _grain_reply(got)


def _grain_reply(got: dict) -> TurnResult:
    from . import grain

    if "why" in got:
        return TurnResult(action="grain", reply=f"I couldn't keep that grain: {got['why']}.", ok=False)
    return TurnResult(action="grain", part=got["part"], ok=True,
                      reply=f"Kept: {grain.line(got['piece'], got['entry'])[0].lower()}"
                            f"{grain.line(got['piece'], got['entry'])[1:]} It's on the cut list and in the build book; "
                            f"check it holds again and the Beam check uses it.")


def turn(store: DesignStore, message: str, scope: Optional[str] = None, *, author=None, client=None,
         use_llm: bool = True, classifier: Optional[Classifier] = None, max_rounds: int = 4,
         on_event=None, drafter=None, promote_feedback: bool = True, logged: bool = False,
         pick: Optional[dict] = None) -> TurnResult:
    """One conversational turn: route the message, make the move, measure the whole design, reply.

    ``scope`` is the part the user clicked (``None`` = the design). ``author``/``classifier``/
    ``drafter`` are injectable so the whole turn is testable without a key; ``on_event`` receives
    progress as it happens (CALI-31 will stream these to the chat).

    A **parked assertion proposal** (CALI-30) owns the next turn if the message answers it — so "yes"
    confirms the test rather than being misread as a request to change geometry. Set
    ``promote_feedback=False`` to suppress the offers entirely.
    """
    from . import promote

    events: list[Event] = []

    # A parked proposal owns the next turn if the message answers it — deterministic, no LLM round
    # trip, and it keeps "yes" from being read as a request to change geometry.
    parked = promote.pending(store)
    if parked is not None:
        verdict = promote.reads_as_yes(message)
        if verdict is not None:
            result = (_accept(store, parked, events, on_event) if verdict
                      else _decline(store, parked, events, on_event))
            if not logged:                       # the page logs it when it arrives (CALI-103)
                store.append_log({"kind": "message", "text": message, "scope": scope,
                                  "action": result.action, "part": result.part, "routed_by": "pending"})
            store.append_log({"kind": "reply", "action": result.action, "part": result.part,
                              "ok": result.ok, "reply": result.reply})
            _emit(events, on_event, "done", result.action, ok=result.ok, part=result.part)
            return result

    # what Caliper's own last question waits for (#98): a short go-ahead or no answers it, with no LLM
    said = _awaited(store, message, scope, author=author, client=client, max_rounds=max_rounds, events=events,
                    on_event=on_event, use_llm=use_llm, drafter=drafter, promote_feedback=promote_feedback)
    if said is None:
        said = _remove_or_restore(store, message, scope, events=events, on_event=on_event)
    if said is not None:
        if not logged:
            store.append_log({"kind": "message", "text": message, "scope": scope, "action": said.action,
                              "part": said.part, "routed_by": "pending"})
        store.append_log({"kind": "reply", "action": said.action, "part": said.part, "version": said.version,
                          "ok": said.ok, "reply": said.reply})
        _emit(events, on_event, "done", said.action, ok=said.ok, part=said.part)
        return said

    said = _mirror_said(store, message, scope) if not message.strip().endswith("?") else None   # (#239)
    if said is not None:
        if not logged:
            store.append_log({"kind": "message", "text": message, "scope": scope, "action": "mirror",
                              "part": said.part, "routed_by": "mirror"})
        store.append_log({"kind": "reply", "action": "mirror", "part": said.part, "version": said.version,
                          "ok": said.ok, "reply": said.reply})
        _emit(events, on_event, "done", "mirror", ok=said.ok, part=said.part)
        return said

    if scope is None and _reviewing(store) and not message.strip().endswith("?"):
        # a plan of several parts under review (CALI-35, #3a): the chat edits the plan, never the geometry
        result = plan_edit(store, message, client=client, use_llm=use_llm, events=events, on_event=on_event)
        if not logged:
            store.append_log({"kind": "message", "text": message, "scope": scope, "action": "plan",
                              "routed_by": "review"})
        store.append_log({"kind": "reply", "action": "plan", "ok": result.ok, "reply": result.reply})
        _emit(events, on_event, "done", "plan", ok=result.ok)
        return result

    if scope is None and _built_plan(store) and not message.strip().endswith("?"):
        # a planned design, built: a shared number changed drives every part that reads it (CALI-35c, #3c)
        result = skeleton_edit(store, message, client=client, use_llm=use_llm, events=events, on_event=on_event)
        if result is not None:
            if not logged:
                store.append_log({"kind": "message", "text": message, "scope": scope, "action": "skeleton",
                                  "routed_by": "skeleton"})
            store.append_log({"kind": "reply", "action": "skeleton", "ok": result.ok, "reply": result.reply})
            _emit(events, on_event, "done", "skeleton", ok=result.ok)
            return result

    said = _grain_said(store, message, scope)          # "cut the seat with the grain front to back" (CALI-126)
    if said is not None:
        if not logged:
            store.append_log({"kind": "message", "text": message, "scope": scope, "action": "grain",
                              "part": said.part, "routed_by": "grain"})
        store.append_log({"kind": "reply", "action": "grain", "part": said.part, "ok": said.ok, "reply": said.reply})
        _emit(events, on_event, "done", "grain", ok=said.ok, part=said.part)
        return said

    intent = classify(store, message, scope, use_llm=use_llm, client=client, classifier=classifier)
    _emit(events, on_event, "classified", f"{intent.action}"
          + (f" → {intent.part}" if intent.part else ""),
          action=intent.action, part=intent.part, source=intent.source, note=intent.note)

    if not logged:
        store.append_log({"kind": "message", "text": message, "scope": scope,
                          "action": intent.action, "part": intent.part, "routed_by": intent.source})

    several = intent.action == "refine" and len(intent.parts) > 1
    again = _repeats(store, intent.part, message) if intent.action == "refine" and intent.part and not several else None
    if again is not None:                          # the last revision already did this: asked first (#98)
        from . import awaiting

        awaiting.park(store, "repeat", part=intent.part, message=message, pick=pick)
        result = TurnResult(action="ask", ok=True, part=intent.part, events=events, reply=again)
    elif several:                                  # each part the request names (#241)
        result = refine_several(store, intent.parts, message, scope=scope, pick=pick, author=author, client=client,
                                max_rounds=max_rounds, events=events, on_event=on_event, use_llm=use_llm,
                                drafter=drafter, promote_feedback=promote_feedback)
    elif intent.action == "refine" and intent.part:
        result = refine_part(store, intent.part, message, author=author, client=client, pick=pick,
                             max_rounds=max_rounds, events=events, on_event=on_event,
                             use_llm=use_llm, drafter=drafter, promote_feedback=promote_feedback)
    elif intent.action == "revert" and intent.part:
        result = revert_part(store, intent.part, events=events, on_event=on_event)
    elif intent.action == "carve" and intent.part:
        result = carve_part(store, intent.part, events=events, on_event=on_event)
    elif intent.action == "picture" and intent.part:
        result = picture_part(store, intent.part, intent.intent, intent.where, events=events,
                              on_event=on_event, use_llm=use_llm, client=client)
    elif intent.action == "author" and intent.part:
        result = author_part(store, intent.part, intent.intent or message, author=author,
                             client=client, max_rounds=max_rounds, events=events, on_event=on_event,
                             use_llm=use_llm, drafter=drafter, promote_feedback=promote_feedback,
                             pick=pick, on=(pick or {}).get("part") or scope)   # the pick is a requirement (#266)
    else:
        result = answer(store, message, scope=scope or intent.part, note=intent.note, events=events,
                        use_llm=use_llm, client=client)

    # what it's held to (CALI-55): a turn that says what the design must do updates its scorecard's checks
    if result.ok is not False and (_OBLIGATION.search(message.lower()) or _CARRIES.search(message.lower())
                                   or _MEASURE.search(message)):
        from . import goals

        try:
            said = goals.reply(goals.update(store, message, use_llm=use_llm, client=client))
        except Exception as e:  # noqa: BLE001 — the change landed; the checks catch up next turn
            said = ""
            _emit(events, on_event, "error", f"couldn't update the scorecard's checks: {scrubbed(e)}")
        if said:
            result.reply = f"{result.reply}\n\n{said}" if result.reply else said
    _emit(events, on_event, "done", result.action, ok=result.ok, part=result.part)
    # the reply TEXT is logged too, so a reloaded page can redraw the conversation as it was
    store.append_log({"kind": "reply", "action": result.action, "part": result.part,
                      "version": result.version, "ok": result.ok,
                      "broke": result.broke, "fixed": result.fixed, "reply": result.reply,
                      **({"proposal": result.proposal.to_dict()} if result.proposal else {}),
                      **({"error": result.error} if result.error else {})})
    return result
