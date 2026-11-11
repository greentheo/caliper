"""CALI-35 (#3a) — the plan: a sentence becomes parts, the numbers they share, and the checks between them.

An LLM's part list is a plan, and plans get trusted when they shouldn't be (the conversational spec's risk section).
So the plan comes out as something measurable: an assembly skeleton.
- **Parts:** what each is and how it's made; ``role: fixed`` for what the person already has.
- **The skeleton:** the numbers the parts share, each named, with a unit and a reason (the interfaces).
- **Mates and rules** between the parts, over part ids and skeleton names, so every interface is measured.
- **A build order:** each part says what it mounts on; mounted-on first; a cycle is refused.

This module is the plan's shape, its validation and its order. It's pure: no geometry, no Claude. The planner that
proposes one, the review and saving are built on it.
"""

from __future__ import annotations

import ast
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

#: What a rule between parts may call: the assembly's measures (assembly.build_context) and plain arithmetic.
FUNCTIONS = {"interference", "min_clearance", "clearance", "max_interference", "min_clearance_all",
             "hole_misalignment", "holes_aligned", "bbox", "approx", "within", "fits", "abs", "min", "max"}
#: What a rule may read off a measure: a bounding box's sizes and corners (measure.bounding_box). Nothing else, and
#: nothing private: a dunder chain is refused (#103 review).
ATTRIBUTES = {"dx", "dy", "dz", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z"}
#: The measures that answer yes or no, so a rule may be one of them alone.
YES_NO = {"holes_aligned", "approx", "within", "fits"}
#: The expression a rule may be: arithmetic, comparisons, and/or/not, calls to the measures, names and numbers.
#: No powers, no strings, no lists, no subscripts (#103 review: "9 ** 9 ** 9 > 0" and "'a' * 10 ** 10" froze the
#: app).
_NODES = (ast.Expression, ast.Compare, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
          ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Call, ast.Name, ast.Attribute, ast.Constant, ast.Load,
          ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
#: The longest a rule may be.
MAX_RULE = 300
#: A part id or a skeleton name: lowercase, digits and underscores, starting with a letter (a Python name, so a
#: rule can say it).
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
#: The units a skeleton number may be in. Lengths are stored in mm, as the models are.
UNITS = {"mm", "in", "ft", "m", "cm", "deg", "N", "lb", "kg", "count", "m/s", "km/h", "mph"}
#: The measures that read a part. A rule that calls none of them, and names no part, reads only the plan's own numbers:
#: it always says the same thing (CALI-115, #117: "generator_shaft_dia == 25.4").
MEASURES = FUNCTIONS - {"abs", "min", "max", "approx", "within"}
#: Words in a part's ``made`` that say it's to be made, so it can't be one the person has (#117: a "welded 7 ft mast"
#: came back fixed, "which you have"). Never read from ``what``: an existing thing was once built or cut (#123 review).
MAKING = re.compile(r"(?i)\b(weld(ed|ing)?|print(ed|ing)?|3d[- ]print\w*|(plasma|laser|water ?jet|cnc)[- ]?cut\w*|cut|"
                    r"routed|milled|machined|turned|bent|glued|sewn|to (build|make)|built|fabricated|assembled)\b")
#: Possession, near the part's own noun in what the person said (#123 review: "my kid's science fair" isn't having a
#: generator): before it ("my", "our", "the existing", "I've got a"), or after it ("I have", "I pulled", "from my").
HAVE = re.compile(r"(?i)\b(i|we)\s*('ve got|'ve| have| already have| own| already own| got| pulled| salvaged| "
                  r"bought| kept)\b")
HAVE_BEFORE = re.compile(r"(?i)\b(my|our|existing|spare)\b")
HAVE_AFTER = re.compile(r"(?i)\bfrom (my|our)\b")
#: What a design stands on or is in: never a part (#117: "the bathroom floor" made the stool a plan of two). Supports
#: are held(), the floor the default.
GROUND = {"floor", "ground", "room", "wall", "walls", "earth", "soil", "ceiling", "terrain", "yard", "lawn"}
_WORD = re.compile(r"[a-z0-9']+")
#: Where a skeleton number or a rule came from (CALI-115, as goals' are): ``stated`` (the person's number),
#: ``assumed`` (the planner's: shown, not enforced) or ``kept`` (assumed, then kept by the person).
SOURCES = ("stated", "assumed", "kept")


class PlanError(ValueError):
    """A plan that can't be used, and why, in words the person can read. ``rule``: the check it's about, when the
    fault is one rule's (CALI-119: after the retry that rule is dropped and said, never the plan)."""

    def __init__(self, message: str, rule: Optional[str] = None, hint: Optional[str] = None):
        super().__init__(message)
        self.rule = rule
        #: a word for the planner's retry, never in what the person reads (#130 review)
        self.hint = hint


class _NumbersOnly(PlanError):
    """A rule over the plan's own numbers: decided when it's planned (CALI-119), not measured."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanPart(_Base):
    id: str
    what: str                                   # what it is, in plain words: "two printed buckets between plates"
    made: str = ""                              # how it's made: printed, sheet, welded tube, foam…
    role: Literal["fixed", "movable"] = "movable"   # fixed: the person already has it; drawn as a reference
    mounts_on: list[str] = Field(default_factory=list)
    #: for a fixed part: "stated" when the person's words say they have it, else "assumed" ("you have it? say if not")
    source: Literal["stated", "assumed"] = "stated"
    #: CALI-161 (#239): this part is another's mirror, flipped in a plane (YZ, XZ or XY); built by flipping, not designed
    mirror_of: Optional[str] = None
    mirror_plane: Optional[Literal["YZ", "XZ", "XY"]] = None
    #: the point the plane passes through, in mm: the assembly origin unless given
    mirror_at: Optional[list[float]] = None


class SkeletonValue(_Base):
    name: str
    value: float
    unit: str
    why: str = ""
    source: Literal["stated", "assumed", "kept", "measured"] = "assumed"   # measured: off a part as built (#240)


class PlanMate(_Base):
    between: list[str]
    kind: Literal["no_interference", "clearance", "fit", "touch", "fits_in"] = "no_interference"
    value: Optional[float] = None


class PlanRule(_Base):
    id: str
    expr: str
    why: str = ""
    source: Literal["stated", "assumed", "kept"] = "assumed"


class Plan(_Base):
    parts: list[PlanPart]
    skeleton: list[SkeletonValue] = Field(default_factory=list)
    mates: list[PlanMate] = Field(default_factory=list)
    rules: list[PlanRule] = Field(default_factory=list)
    #: checks left out, each with why (CALI-119): plan data, so the review says them and a revision sees them
    left_out: list[str] = Field(default_factory=list)
    #: parts validation dropped: the floor, the ground, the room (#117)
    _dropped: list = PrivateAttr(default_factory=list)

    @property
    def dropped(self) -> list[str]:
        return list(self._dropped)

    @property
    def dropped_rules(self) -> list[str]:
        return list(self.left_out)

    @property
    def notes(self) -> list[str]:
        """The rules over the plan's own numbers, as notes (CALI-119): they stay in ``rules`` (#130 review: plan data,
        so a revision sees them and they're decided again), and they're never checks."""
        return [f"{r.why or r.id.replace('_', ' ')} ({r.expr})" for r in self.rules if numbers_only(r, self)]

    def _carry(self, other: "Plan") -> "Plan":
        """This plan with ``other``'s dropped parts (a copy doesn't keep them)."""
        self._dropped = other.dropped
        return self

    def ids(self) -> list[str]:
        return [p.id for p in self.parts]

    def value(self, name: str) -> Optional[SkeletonValue]:
        return next((s for s in self.skeleton if s.name == name), None)


def validate(data, drop_bad_rules: bool = False) -> Plan:
    """A plan from the planner's JSON (or a :class:`Plan`), checked: every name well formed and used once, every
    skeleton number with a unit, every mate and rule over parts and numbers the plan has, the rules in the
    language the assembly measures and each measuring a part, a part you have that isn't one to be made, and a build
    order with no cycle. What it stands on (the bathroom floor, the garage wall) is dropped, with what names it, and
    said (:func:`dropped_line`). Raises :class:`PlanError` with the reason."""
    try:
        plan = data if isinstance(data, Plan) else Plan.model_validate(data)
    except Exception as e:  # noqa: BLE001 — pydantic's first complaint, in words (never its raw text or its URL)
        raise PlanError(f"the plan isn't in the shape a plan takes: {_plainly(e)}") from e
    plan = _drop_ground(plan)
    if not plan.parts:
        raise PlanError("the plan has no parts")
    for p in plan.parts:
        made = MAKING.search(p.made) if p.role == "fixed" else None
        if made:
            raise PlanError(f"{p.id!r} is marked as something you have, but it's to be made ({made.group(0).lower()}): "
                            f"only what the person said they have is fixed")
    ids = plan.ids()
    names = [s.name for s in plan.skeleton]
    for kind, seen in (("part", ids), ("skeleton number", names)):
        for n in seen:
            if not NAME.match(n):
                raise PlanError(f"the {kind} name {n!r} isn't a plain name (lowercase letters, digits, underscores)")
        dup = next((n for n in seen if seen.count(n) > 1), None)
        if dup:
            raise PlanError(f"two {kind}s are both called {dup!r}")
    clash = set(ids) & set(names) or (set(ids) | set(names)) & FUNCTIONS
    if clash:
        raise PlanError(f"{sorted(clash)[0]!r} names two things (a part, a skeleton number or a measure)")
    for s in plan.skeleton:
        if not s.unit or s.unit not in UNITS:
            raise PlanError(f"the skeleton number {s.name!r} has no unit" if not s.unit else
                            f"the skeleton number {s.name!r} is in {s.unit!r}, not a unit Caliper measures in")
    for p in plan.parts:
        for m in p.mounts_on:
            if m not in ids:
                raise PlanError(f"{p.id!r} mounts on {m!r}, which isn't a part of the plan")
            if m == p.id:
                raise PlanError(f"{p.id!r} mounts on itself")
        if p.mirror_of is not None:                 # a mirror of a part of the plan, never of itself or of a mirror (#239)
            src = next((q for q in plan.parts if q.id == p.mirror_of), None)
            if src is None or src.id == p.id:
                raise PlanError(f"{p.id!r} is a mirror of {p.mirror_of!r}, which isn't another part of the plan")
            if src.mirror_of is not None:
                raise PlanError(f"{p.id!r} mirrors {src.id!r}, which is itself a mirror: mirror {src.mirror_of!r} instead")
    for m in plan.mates:
        if len(m.between) != 2 or m.between[0] == m.between[1]:
            raise PlanError(f"a mate is between two different parts, not {m.between!r}")
        for pid in m.between:
            if pid not in ids:
                raise PlanError(f"a mate names {pid!r}, which isn't a part of the plan")
    rule_ids = [r.id for r in plan.rules]
    dup = next((r for r in rule_ids if rule_ids.count(r) > 1), None)
    if dup:
        raise PlanError(f"two checks are both called {dup!r}")
    kept, left = [], []
    for r in plan.rules:
        try:
            try:
                _check_rule(r, set(ids), set(names))
            except _NumbersOnly:                 # decided now, every validate (CALI-119): a note, a contradiction
                if not _by_the_numbers(r, plan):
                    left.append(f"the check {r.id!r} ({r.expr}): it reads only numbers")
                    continue
            kept.append(r)
        except PlanError as e:
            if not drop_bad_rules:
                raise PlanError(str(e), rule=r.id, hint=getattr(e, "hint", None)) from e
            said = str(e).removeprefix(f"the check {r.id!r} ")          # the check named once (#130 review)
            left.append(f"the check {r.id!r} ({r.expr}): {said}")       # one rule never sinks the plan (CALI-119)
    # validate's own left-out checks only: never what a planner's answer claims was left out (#130 review); a
    # revision adds the prior plan's (revise)
    out = plan.model_copy(update={"rules": kept, "left_out": list(dict.fromkeys(left))})
    order(out)                                   # a cycle is refused here: the plan's, not a rule's
    return out._carry(plan)


def numbers_only(rule: "PlanRule", plan: "Plan") -> bool:
    """A rule that reads only the plan's own numbers: a note, decided when it's planned, never a check."""
    try:
        tree = ast.parse(rule.expr, mode="eval")
    except SyntaxError:
        return False
    ids = set(plan.ids())
    return not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MEASURES
                   for n in ast.walk(tree)) and not any(isinstance(n, ast.Name) and n.id in ids for n in ast.walk(tree))


def _by_the_numbers(rule: "PlanRule", plan: "Plan") -> Optional[str]:
    """A rule over the plan's own numbers, decided now (CALI-119): true, its note; false, the plan is refused with
    the contradiction; over literals alone, None (it says nothing about this plan)."""
    from .evaluate import safe_eval

    from . import tolerance

    tree = ast.parse(rule.expr, mode="eval")
    names = {s.name for s in plan.skeleton}
    read = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in names]
    if not read:
        return None
    values = skeleton_values(plan.skeleton)
    try:                                         # the checks' own functions; any error is this rule's (#130 review)
        holds = safe_eval(rule.expr, {**values, "abs": abs, "min": min, "max": max,
                                      "approx": tolerance.approx, "within": tolerance.within})
    except Exception as e:  # noqa: BLE001 — a rule that can't be decided is its fault, never the plan's
        raise PlanError(f"the check {rule.id!r} can't be decided by the numbers ({rule.expr}): {e}", rule=rule.id) from e
    if holds:
        return f"{rule.why or rule.id.replace('_', ' ')} ({rule.expr})"
    said = ", ".join(f"{n} {values[n]:g} " + ("mm" if mm(plan.value(n)) is not None else plan.value(n).unit)
                     for n in dict.fromkeys(read))
    lengths = any(mm(plan.value(n)) is not None for n in read)
    what = rule.why or rule.id.replace("_", " ")
    raise PlanError(f"the check {rule.id!r} contradicts the plan's own numbers: {what}, but {rule.expr} is false "
                    f"({said})", rule=rule.id, hint="lengths in a check read in mm" if lengths else None)


def _ground(p: PlanPart) -> bool:
    """What it stands on, not a part: the id's LAST word is a ground word and it isn't made (#123 review:
    "floor_lamp", "wall_shelf" and "ground_stake" are parts; "bathroom_floor" and "garage_wall" aren't; a
    "retaining_wall" that's built is)."""
    return p.id.split("_")[-1] in GROUND and not p.made.strip()


def said_aside(plan: Plan) -> str:
    """What the review says besides the parts (CALI-119): checks left out, each with why, and the notes that hold
    by the numbers. Never a silent drop."""
    out = "".join(f"\n\nI left out {d}." for d in plan.dropped_rules)
    if plan.notes:
        out += "\n\nBy the numbers: " + "; ".join(plan.notes) + "."
    return out


def dropped_line(plan: Plan) -> str:
    """"the bathroom floor is what it stands on, not a part", or "" (never dropped without a word)."""
    gone = [f"the {d.replace('_', ' ')}" for d in plan.dropped]
    if not gone:
        return ""
    return (" and ".join(gone) + (" is what it stands on, not a part" if len(gone) == 1
                                  else " are what it stands on, not parts"))


def _have(said: str, p: PlanPart) -> bool:
    """The person's words say they have this part: a possession phrase within a few words of its noun."""
    words = _WORD.findall((said or "").lower())
    nouns = {w for w in p.id.lower().split("_") if len(w) > 2}
    for i, w in enumerate(words):
        if w.rstrip("s") not in {n.rstrip("s") for n in nouns}:
            continue
        before, after = " ".join(words[max(0, i - 4):i]), " ".join(words[i + 1:i + 8])
        if HAVE.search(before) or HAVE_BEFORE.search(before) or HAVE.search(after) or HAVE_AFTER.search(after):
            return True
    return False


def _drop_ground(plan: Plan) -> Plan:
    """The plan without the floor, the ground or the room, and without the mates and rules that name them (#117)."""
    gone = [p.id for p in plan.parts if _ground(p)]
    if not gone:
        return plan

    def names(expr: str) -> set:
        try:
            return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)}
        except SyntaxError:
            return set()
    out = plan.model_copy(update={
        "parts": [p.model_copy(update={"mounts_on": [m for m in p.mounts_on if m not in gone]})
                  for p in plan.parts if p.id not in gone],
        "mates": [m for m in plan.mates if not set(m.between) & set(gone)],
        "rules": [r for r in plan.rules if not names(r.expr) & set(gone)]}, deep=True)
    out._dropped = gone
    return out


def buildable(plan: Plan) -> list[str]:
    """The parts to be made: not the ones the person has. One of them is a design of one part, built at once."""
    return [p.id for p in plan.parts if p.role != "fixed"]


def _plainly(e: Exception) -> str:
    """A validation error as a person reads it: "parts 1: what is missing" (#103 review: the reason leaked pydantic's
    whole message, with its documentation URL)."""
    errs = getattr(e, "errors", lambda: [])()
    if not errs:
        return "it isn't a plan"
    first = errs[0]
    where = " ".join(str(x) for x in first.get("loc") or ()) or "the plan"
    msg = {"missing": "is missing", "extra_forbidden": "isn't part of a plan"}.get(first.get("type"),
                                                                                 str(first.get("msg", "")).lower())
    more = f" (and {len(errs) - 1} more)" if len(errs) > 1 else ""
    return f"{where} {msg}{more}"


def _check_rule(rule: PlanRule, ids: set, names: set) -> None:
    if len(rule.expr) > MAX_RULE:
        raise PlanError(f"the check {rule.id!r} is longer than a check should be ({len(rule.expr)} characters)")
    try:
        tree = ast.parse(rule.expr, mode="eval")
    except SyntaxError as e:
        hint = ": `=` isn't a comparison; use `==`" if re.search(r"(?<![=!<>])=(?!=)", rule.expr) else ""
        raise PlanError(f"the check {rule.id!r} isn't an expression Caliper can measure: {rule.expr!r}{hint}") from e
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            raise PlanError(f"the check {rule.id!r} raises to a power, which a check never needs: {rule.expr!r}")
        if isinstance(n, ast.Constant) and not (isinstance(n.value, (int, float)) and not isinstance(n.value, bool)):
            raise PlanError(f"the check {rule.id!r} has {n.value!r} in it: a check is numbers and measures")
        if not isinstance(n, _NODES):
            raise PlanError(f"the check {rule.id!r} uses something a check can't ({type(n).__name__}): {rule.expr!r}")
        if isinstance(n, ast.Attribute) and n.attr not in ATTRIBUTES:
            raise PlanError(f"the check {rule.id!r} reads .{n.attr}, which isn't a size or corner of a box "
                            f"({', '.join(sorted(ATTRIBUTES))})")
        if isinstance(n, ast.Call) and n.keywords:
            raise PlanError(f"the check {rule.id!r} names an argument; a check passes them in order")
        if isinstance(n, ast.Name):
            if id(n) in called:
                if n.id not in FUNCTIONS:
                    raise PlanError(f"the check {rule.id!r} calls {n.id}(), which isn't a measure Caliper has")
            elif n.id not in ids and n.id not in names:
                raise PlanError(f"the check {rule.id!r} names {n.id!r}, which isn't a part or a skeleton number "
                                f"of the plan")
        elif isinstance(n, ast.Call) and not isinstance(n.func, ast.Name):
            raise PlanError(f"the check {rule.id!r} calls something that isn't a measure: {rule.expr!r}")
    if not _yes_no(tree.body):
        raise PlanError(f"the check {rule.id!r} doesn't say yes or no: compare a measure with a number "
                        f"({rule.expr!r})")
    if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MEASURES
               for n in ast.walk(tree)) and not any(isinstance(n, ast.Name) and n.id in ids for n in ast.walk(tree)):
        raise _NumbersOnly(f"the check {rule.id!r} reads only the plan's own numbers ({rule.expr!r})", rule=rule.id)


def _yes_no(n: ast.AST) -> bool:
    """A comparison, and/or/not of them, or a measure that answers yes or no: never a bare number, which would
    read as a pass (#103 review: "rotor_d" and "1" passed)."""
    if isinstance(n, ast.Compare):
        return True
    if isinstance(n, ast.BoolOp):
        return all(_yes_no(v) for v in n.values)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
        return _yes_no(n.operand)
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in YES_NO


def order(plan: Plan) -> list[str]:
    """The build order: every part after what it mounts on, the plan's own order otherwise. A cycle is refused."""
    by = {p.id: p for p in plan.parts}
    done: list[str] = []
    doing: list[str] = []

    def visit(pid: str) -> None:
        if pid in done:
            return
        if pid in doing:
            loop = doing[doing.index(pid):] + [pid]
            raise PlanError("the parts mount on each other in a circle: " + " → ".join(loop))
        doing.append(pid)
        for m in by[pid].mounts_on + ([by[pid].mirror_of] if by[pid].mirror_of in by else []):   # a mirror after its source
            visit(m)
        doing.pop()
        done.append(pid)

    for p in plan.parts:
        visit(p.id)
    return done


#: A length in the person's units, as a skeleton number says it, to mm.
TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}


def mm(s: SkeletonValue) -> Optional[float]:
    """A skeleton number as a length in mm (the models' unit), or None if it isn't a length."""
    return s.value * TO_MM[s.unit] if s.unit in TO_MM else None


def skeleton_values(skeleton: list) -> dict:
    """``{name: value}`` for a rule to read: lengths in mm (the models' unit), anything else as it's given."""
    out = {}
    for s in skeleton or []:
        sv = s if isinstance(s, SkeletonValue) else SkeletonValue.model_validate(s)
        out[sv.name] = mm(sv) if mm(sv) is not None else sv.value
    return out


# ---------------------------------------------------------------------------
# Where its numbers came from (CALI-115, #117): what the person said is enforced; the rest is shown, assumed
# ---------------------------------------------------------------------------
#: A number with its unit in what the person said: "7 ft", "1 in", "3/4 in", "40 lb", "600 mm", '2"'.
_SAID = re.compile(r"(\d+(?:\.\d+)?(?:\s*/\s*\d+)?|\d+\s+\d+/\d+)\s*(mph|km/h|kmh|kph|m/s|mm|cm|m|in|inch|inches|\"|"
                   r"ft|feet|foot|'|deg|degrees|°|lb|lbs|pounds?|kg|n)(?![a-z])", re.I)
#: Speeds and masses to one unit each, so "60 mph" is the planner's 26.82 m/s (CALI-119).
SAME = {"mph": ("m/s", 0.44704), "km/h": ("m/s", 1 / 3.6), "m/s": ("m/s", 1.0), "lb": ("kg", 0.45359237),
        "kg": ("kg", 1.0)}
_SAID_UNIT = {"inch": "in", "inches": "in", '"': "in", "feet": "ft", "foot": "ft", "'": "ft", "degrees": "deg",
              "°": "deg", "lbs": "lb", "pound": "lb", "pounds": "lb", "n": "N", "kmh": "km/h", "kph": "km/h"}


def _amount(num: str) -> float:
    """"7", "0.75", "3/4", "1 1/2"."""
    return sum(float(a) / float(b) if "/" in x else float(x) for x in num.split()
               for a, b in [x.split("/") if "/" in x else (x, "1")])


def _said_numbers(said: str) -> list[tuple[float, str]]:
    """Each number the person gave with a unit: (value, unit), lengths as mm with unit "mm"."""
    out = []
    for num, unit in _SAID.findall(said or ""):
        unit = _SAID_UNIT.get(unit.lower(), unit.lower())
        try:
            v = _amount(num.replace(" / ", "/"))
        except (ValueError, ZeroDivisionError):
            continue
        out.append((v * TO_MM[unit], "mm") if unit in TO_MM else
                   (v * SAME[unit][1], SAME[unit][0]) if unit in SAME else (v, unit))
    return out


def _was_said(s: SkeletonValue, said: list[tuple[float, str]]) -> bool:
    unit = s.unit                              # by the unit, never the name (#130 review: "rotor_d" read as a speed)
    v = mm(s)
    want = ((v, "mm") if v is not None else (s.value * SAME[unit][1], SAME[unit][0]) if unit in SAME
            else (s.value, unit))
    return any(u == want[1] and abs(x - want[0]) <= max(0.005 * abs(want[0]), 1e-9) for x, u in said)


def classify(plan: Plan, said: str, prior: Optional[Plan] = None) -> Plan:
    """Each skeleton number and rule marked by where it came from, whatever the planner wrote: a number is stated
    when the person gave it ("7 ft", "1 in"), a rule when it reads only stated numbers and at least one; anything
    the person kept stays kept (a revision doesn't undo it); the rest is assumed: shown, not enforced (#117)."""
    nums = _said_numbers(said)
    kept_n = {(k.name, k.value, k.unit) for k in (prior.skeleton if prior else []) if k.source == "kept"}
    kept_r = {(r.id, r.expr) for r in (prior.rules if prior else []) if r.source == "kept"}
    skel = [s.model_copy(update={"source": "kept" if (s.name, s.value, s.unit) in kept_n
                                 else "stated" if _was_said(s, nums) else "assumed"}) for s in plan.skeleton]
    given = {s.name for s in skel if s.source != "assumed"}
    names = {s.name for s in skel}
    rules = []
    for r in plan.rules:
        read = {n.id for n in ast.walk(ast.parse(r.expr, mode="eval")) if isinstance(n, ast.Name)} & names
        src = "kept" if (r.id, r.expr) in kept_r else "stated" if read and read <= given else "assumed"
        rules.append(r.model_copy(update={"source": src}))
    # a part you have: "stated" when your words say so, else assumed and asked, never the whole plan refused (#123)
    kept_p = {p.id for p in (prior.parts if prior else []) if p.role == "fixed" and p.source == "stated"}
    parts = [p.model_copy(update={"source": "stated" if p.role != "fixed" or p.id in kept_p or _have(said, p)
                                  else "assumed"}) for p in plan.parts]
    return plan.model_copy(update={"skeleton": skel, "rules": rules, "parts": parts})._carry(plan)


def binding(plan: Plan) -> list[PlanRule]:
    """The rules that are enforced: stated or kept, reading no number that's only assumed."""
    assumed = {s.name for s in plan.skeleton if s.source == "assumed"}
    return [r for r in plan.rules if r.source != "assumed" and not numbers_only(r, plan)      # a note isn't a check
            and not ({n.id for n in ast.walk(ast.parse(r.expr, mode="eval")) if isinstance(n, ast.Name)} & assumed)]


def keep(store, rule_id: str) -> Plan:
    """The person keeps an assumed check: it's enforced from now on, and so are the numbers it reads."""
    plan = load(store)
    rule = next((r for r in (plan.rules if plan else []) if r.id == rule_id), None)
    if rule is None:
        raise KeyError(f"the plan has no check {rule_id!r}")
    read = {n.id for n in ast.walk(ast.parse(rule.expr, mode="eval")) if isinstance(n, ast.Name)}
    plan = plan.model_copy(update={
        "rules": [r.model_copy(update={"source": "kept"}) if r.id == rule_id else r for r in plan.rules],
        "skeleton": [s.model_copy(update={"source": "kept"}) if s.name in read and s.source == "assumed" else s
                     for s in plan.skeleton]})._carry(plan)
    save(store, plan, (store.design.plan or {}).get("status", "review"))
    return plan


def words(store) -> str:
    """What the person said: the sentence and their answers (an assumed answer isn't theirs)."""
    answers = [r.answer for r in store.design.requirements if getattr(r, "source", "") != "assumed"]
    return "\n".join([store.design.prompt or "", *answers])


# ---------------------------------------------------------------------------
# Saving it: assembly.yaml (parts, mates, rules) and design.yaml (the skeleton, the plan)
# ---------------------------------------------------------------------------
def save(store, plan: Plan, status: str = "review") -> None:
    """Write the plan into the design's records. A planned part goes into assembly.yaml where its script will be
    (it isn't built yet: evaluation skips it, and a rule naming it waits); the mates and rules go in as the plan's;
    the skeleton and the plan itself into design.yaml. Saving again replaces what the last plan wrote."""
    from .assembly import Mate, Part
    from .spec import Assertion

    old = {p["id"] for p in (store.design.plan or {}).get("parts") or []}
    built = {p.id for p in store.design.parts if p.version}
    asm = store.assembly
    keep = [p for p in asm.parts if p.id not in old or p.id in built]
    have = {p.id for p in keep}
    for p in plan.parts:
        if p.id not in have:
            keep.append(Part(id=p.id, source=store._script_source(p.id), role=p.role))
    asm.parts = keep
    asm.mates = [m for m in asm.mates if not m.id.startswith("plan_")] + [
        Mate(id=f"plan_{m.between[0]}_{m.between[1]}_{m.kind}", between=m.between, kind=m.kind, value=m.value)
        for m in plan.mates]
    prior = {r["id"] for r in (store.design.plan or {}).get("rules") or []}
    asm.assertions = [a for a in asm.assertions if a.id not in prior] + [
        Assertion(id=r.id, expr=r.expr) for r in binding(plan)]          # an assumed rule is shown, not enforced
    store.design.skeleton = [s.model_dump() for s in plan.skeleton]
    store.design.plan = {"status": status, "parts": [p.model_dump() for p in plan.parts], "order": order(plan),
                         "rules": [r.model_dump() for r in plan.rules],
                         **({"dropped": plan.dropped} if plan.dropped else {}),
                         **({"left_out": plan.left_out} if plan.left_out else {})}
    store.save()


def load(store) -> Optional[Plan]:
    """The design's saved plan, as a :class:`Plan` (its mates read back from assembly.yaml), or None."""
    rec = store.design.plan
    if not rec:
        return None
    mates = [{"between": m.between, "kind": m.kind, "value": m.value} for m in store.assembly.mates
             if m.id.startswith("plan_")]
    plan = Plan.model_validate({"parts": rec["parts"], "skeleton": store.design.skeleton or [], "mates": mates,
                                "rules": rec.get("rules") or [], "left_out": rec.get("left_out") or []})
    plan._dropped = list(rec.get("dropped") or [])
    return plan


# ---------------------------------------------------------------------------
# Saying it: the review card's line and its numbers
# ---------------------------------------------------------------------------


def headline(plan: Plan, name: str) -> str:
    """The top line of the review: "A wind turbine in 4 parts: the rotor (two printed buckets…), the hub, …"."""
    def one(p: PlanPart) -> str:
        said = p.id.replace("_", " ")
        what = p.what.strip().rstrip(".")
        extra = f" ({what})" if what and what.lower() != said and not what.lower().startswith(f"the {said}") else ""
        have = "" if p.role != "fixed" else (", which you have" if p.source == "stated"
                                              else " (you have it? say if not)")
        return f"the {said}{extra}{have}"
    names = [one(p) for p in plan.parts]
    listed = ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else names[0]
    a = name.strip().rstrip(".")
    if not re.match(r"(?i)(a|an|the|my|our)\b", a):
        a = ("an " if a[:1].lower() in "aeiou" else "a ") + a[:1].lower() + a[1:]
    return f"{a[0].upper() + a[1:]} in {len(plan.parts)} parts: {listed}."


def number(s: SkeletonValue, inches: bool) -> str:
    """A skeleton number in the person's units: lengths in inches or mm, anything else as given."""
    v = mm(s)
    if v is None:
        return f"{s.value:g} {s.unit}"
    if inches:
        ft, inch = divmod(v / 25.4, 12)
        return f"{v / 25.4:.3g} in" if v < 25.4 * 24 else (f"{ft:g} ft {inch:.2g} in" if round(inch, 1) else f"{ft:g} ft")
    return f"{v:.4g} mm"


def said_number(s: SkeletonValue, inches: bool) -> str:
    """"mast h: 7 ft (the mast you asked for)", and " · assumed" on one the person didn't give."""
    return (f"{s.name.replace('_', ' ')}: {number(s, inches)}" + (f" ({s.why})" if s.why else "")
            + (" · assumed" if s.source == "assumed" else " · measured off the part" if s.source == "measured" else ""))


def numbers(plan: Plan, inches: bool) -> list[str]:
    """One click down: the skeleton's numbers, and the checks between the parts."""
    out = [said_number(s, inches) for s in plan.skeleton]
    out += [f"{m.kind.replace('_', ' ')}: {m.between[0]} and {m.between[1]}" for m in plan.mates]
    out += [f"check {r.id}: {r.expr}" + (" · assumed" if r.source == "assumed" else "") for r in plan.rules]
    return out


def changes(before: Plan, after: Plan, inches: bool) -> list[str]:
    """What an edit changed, in words: the reply to "make the mast 10 ft"."""
    out = []
    was = {s.name: s for s in before.skeleton}
    now = {s.name: s for s in after.skeleton}
    for n in now:
        if n not in was:
            out.append(f"added {n.replace('_', ' ')}: {number(now[n], inches)}")
        elif mm(now[n]) != mm(was[n]) or now[n].value != was[n].value:
            out.append(f"{n.replace('_', ' ')}: {number(was[n], inches)} → {number(now[n], inches)}")
    out += [f"dropped {n.replace('_', ' ')}" for n in was if n not in now]
    pb, pa = set(before.ids()), set(after.ids())
    out += [f"added the {p.replace('_', ' ')}" for p in after.ids() if p not in pb]
    out += [f"dropped the {p.replace('_', ' ')}" for p in before.ids() if p not in pa]
    rb, ra = {r.id: r.expr for r in before.rules}, {r.id: r.expr for r in after.rules}
    out += [f"check {r}: {ra[r]}" for r in ra if rb.get(r) != ra[r]]
    out += [f"dropped the check {r}" for r in rb if r not in ra]
    return out


# ---------------------------------------------------------------------------
# The planner: one Claude call, with the plan's schema as its only tool
# ---------------------------------------------------------------------------
SYSTEM = """You plan a physical design for Caliper before any part of it is drawn. Split it into parts only where \
things are made separately and then joined (a different material or process), or where they move against each \
other. Pieces of one sheet-goods or printed part stay ONE part (a step stool of plywood panels is one part). Use \
role "fixed" only for what the person said they already have ("my generator", "a pump I have"): drawn from their \
stated size as a reference, never designed. Anything welded, printed, cut or otherwise made is never fixed. A part \
is never the ground, the floor, a wall or the room: what it stands on is held, the floor by default.

Name the numbers the parts share as the skeleton: each with a value, a unit (mm, in, ft, m, cm, deg, N, lb, kg, \
count, or a speed in m/s, km/h or mph) and why. A number two parts must agree on lives in the skeleton, never in \
either part: where one part sits in, on or through another (a pocket, slot, hole, flange, a top on sides), name the \
joining sizes in the skeleton (the inserted part's thickness and height, the pocket's clearance a side, a bolt's \
diameter and spacing), and write a fits_in mate between them, the inserted part first, its value the clearance a \
side in mm. Write mates between parts (touch, clearance, fit, fits_in, no_interference) and rules over part ids and \
skeleton names, so every interface is measured. A rule may call: interference(a, b), min_clearance(a, b), \
hole_misalignment(a, b), holes_aligned(a, b), bbox(part).dx/.dy/.dz (sizes) and .min_x/.min_y/.min_z/.max_x/\
.max_y/.max_z (corners), abs, min, max. Every rule compares a measure of a part with a number (`==`, never `=`), \
with + - * / and no powers or text. A rule over skeleton numbers alone measures nothing: it's decided when it's \
planned (true, it's a note; false, the plan contradicts itself and is refused). Lengths in rules are mm; a skeleton name in a rule reads in mm. Each part says what it mounts on (the parts it's built onto).

Give a number or a rule source "stated" only when the person gave it; anything you chose (a size, a margin, a rule \
of thumb) is "assumed": shown to them, and not enforced until they keep it. Don't add rules nobody asked for beyond \
what makes the parts fit.

A part that is another's mirror (a pair, matching sides, "the other side", "mirror") is mirror_of that part, with \
mirror_plane the plane it flips in (YZ for a left and right, XZ for a front and back, XY for a top and bottom) and \
mirror_at a point on that plane in mm (half way between the two; the origin if left out): it's \
built by flipping its source, never designed on its own.

Ids and names are lowercase with underscores. Answer by calling the plan tool, once."""


def _tool() -> dict:
    return {"name": "plan", "description": "The design's parts, the numbers they share, and the checks between them.",
            "input_schema": Plan.model_json_schema()}


def _ask(client, model: Optional[str], content: str, said: str, prior: Optional[Plan] = None,
         drop: bool = True) -> Plan:
    """One plan from the planner, validated and classified. A refused plan is asked for once more, with the reason
    (#117: one "=" for "==" threw the camper's whole plan away); refused again, the reason is raised."""
    from . import llm

    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    # Opus 5.5 refuses a forced tool: it's asked to, and a reply without one is sent back round below
    content = f"{content}\n\nAnswer by calling the plan tool."
    ask = content
    for attempt in (1, 2):
        msg = llm.ask(client, "plan", model=model, system=SYSTEM, tools=[_tool()],
                      messages=[{"role": "user", "content": ask}])
        got = next((b.input for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
        try:
            if got is None:
                raise PlanError("the planner didn't answer with a plan")
            return classify(validate(got, drop_bad_rules=drop and attempt == 2), said, prior)
        except PlanError as e:
            if attempt == 2:
                raise
            ask = (f"{content}\n\nYour last plan was refused: {e}" + (f" ({e.hint})" if getattr(e, "hint", None) else "")
                   + ". Answer with the whole plan again, with that fixed and everything else as it was.")
    raise AssertionError("unreachable")


def propose(store, *, client=None, model: Optional[str] = None) -> Plan:
    """The planner's plan for the design's sentence and its answered questions, validated."""
    asked = "\n".join(f"- {r.question} {r.answer}" for r in store.design.requirements)
    units = "inches and feet" if store.design.display_units == "in" else "mm"
    return _ask(client, model, f"What to make: {store.design.prompt}\n\nWhat was clarified:\n{asked or '- nothing'}\n\n"
                               f"The person talks in {units}.", words(store))


def revise(store, said: str, *, client=None, model: Optional[str] = None) -> tuple[Plan, Plan]:
    """The plan as the person's words change it, during review: (before, after), both validated. The chat edits
    the plan, never the geometry: "make the mast 10 ft" changes a skeleton number."""
    import json

    before = load(store)
    if before is None:
        raise PlanError("there's no plan to change")
    after = _ask(client, model, "The plan now:\n" + json.dumps(before.model_dump(), indent=1)
                 + f"\n\nThe person said: {said}\n\nAnswer with the whole plan as it should now be. Change only what "
                   "they asked for; keep every other part, number and check as it is.",
                 words(store) + "\n" + said, prior=before, drop=False)   # an edit that contradicts a note is refused
    if before.left_out:                          # what was left out stays said through an edit (#130 review)
        after = after.model_copy(update={"left_out": list(dict.fromkeys([*before.left_out, *after.left_out]))})._carry(after)
    return before, after
