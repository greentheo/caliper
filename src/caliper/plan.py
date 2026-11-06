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

from pydantic import BaseModel, ConfigDict, Field

#: What a rule between parts may call: the assembly's measures (assembly.build_context) and plain arithmetic.
FUNCTIONS = {"interference", "min_clearance", "clearance", "max_interference", "min_clearance_all",
             "hole_misalignment", "holes_aligned", "bbox", "approx", "within", "fits", "abs", "min", "max"}
#: A part id or a skeleton name: lowercase, digits and underscores, starting with a letter (a Python name, so a
#: rule can say it).
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
#: The units a skeleton number may be in. Lengths are stored in mm, as the models are.
UNITS = {"mm", "in", "ft", "m", "cm", "deg", "N", "lb", "kg", "count"}


class PlanError(ValueError):
    """A plan that can't be used, and why, in words the person can read."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanPart(_Base):
    id: str
    what: str                                   # what it is, in plain words: "two printed buckets between plates"
    made: str = ""                              # how it's made: printed, sheet, welded tube, foam…
    role: Literal["fixed", "movable"] = "movable"   # fixed: the person already has it; drawn as a reference
    mounts_on: list[str] = Field(default_factory=list)


class SkeletonValue(_Base):
    name: str
    value: float
    unit: str
    why: str = ""


class PlanMate(_Base):
    between: list[str]
    kind: Literal["no_interference", "clearance", "fit", "touch"] = "no_interference"
    value: Optional[float] = None


class PlanRule(_Base):
    id: str
    expr: str
    why: str = ""


class Plan(_Base):
    parts: list[PlanPart]
    skeleton: list[SkeletonValue] = Field(default_factory=list)
    mates: list[PlanMate] = Field(default_factory=list)
    rules: list[PlanRule] = Field(default_factory=list)

    def ids(self) -> list[str]:
        return [p.id for p in self.parts]

    def value(self, name: str) -> Optional[SkeletonValue]:
        return next((s for s in self.skeleton if s.name == name), None)


def validate(data) -> Plan:
    """A plan from the planner's JSON (or a :class:`Plan`), checked: every name well formed and used once, every
    skeleton number with a unit, every mate and rule over parts and numbers the plan has, the rules in the
    language the assembly measures, and a build order with no cycle. Raises :class:`PlanError` with the reason."""
    try:
        plan = data if isinstance(data, Plan) else Plan.model_validate(data)
    except Exception as e:  # noqa: BLE001 — pydantic's message, said plainly
        raise PlanError(f"the plan isn't in the shape a plan takes: {e}") from e
    if not plan.parts:
        raise PlanError("the plan has no parts")
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
    for r in plan.rules:
        _check_rule(r, set(ids), set(names))
    order(plan)                                  # a cycle is refused here
    return plan


def _check_rule(rule: PlanRule, ids: set, names: set) -> None:
    try:
        tree = ast.parse(rule.expr, mode="eval")
    except SyntaxError as e:
        raise PlanError(f"the check {rule.id!r} isn't an expression Caliper can measure: {rule.expr!r}") from e
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            if id(n) in called:
                if n.id not in FUNCTIONS:
                    raise PlanError(f"the check {rule.id!r} calls {n.id}(), which isn't a measure Caliper has")
            elif n.id not in ids and n.id not in names:
                raise PlanError(f"the check {rule.id!r} names {n.id!r}, which isn't a part or a skeleton number "
                                f"of the plan")
        elif isinstance(n, ast.Call) and not isinstance(n.func, ast.Name):
            raise PlanError(f"the check {rule.id!r} calls something that isn't a measure: {rule.expr!r}")


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
        for m in by[pid].mounts_on:
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
        Assertion(id=r.id, expr=r.expr) for r in plan.rules]
    store.design.skeleton = [s.model_dump() for s in plan.skeleton]
    store.design.plan = {"status": status, "parts": [p.model_dump() for p in plan.parts], "order": order(plan),
                         "rules": [r.model_dump() for r in plan.rules]}
    store.save()


def load(store) -> Optional[Plan]:
    """The design's saved plan, as a :class:`Plan` (its mates read back from assembly.yaml), or None."""
    rec = store.design.plan
    if not rec:
        return None
    mates = [{"between": m.between, "kind": m.kind, "value": m.value} for m in store.assembly.mates
             if m.id.startswith("plan_")]
    return Plan.model_validate({"parts": rec["parts"], "skeleton": store.design.skeleton or [], "mates": mates,
                                "rules": rec.get("rules") or []})


# ---------------------------------------------------------------------------
# Saying it: the review card's line and its numbers
# ---------------------------------------------------------------------------


def headline(plan: Plan, name: str) -> str:
    """The top line of the review: "A wind turbine in 4 parts: the rotor (two printed buckets…), the hub, …"."""
    def one(p: PlanPart) -> str:
        said = p.id.replace("_", " ")
        what = p.what.strip().rstrip(".")
        extra = f" ({what})" if what and what.lower() != said and not what.lower().startswith(f"the {said}") else ""
        return f"the {said}{extra}" + (", which you have" if p.role == "fixed" else "")
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


def numbers(plan: Plan, inches: bool) -> list[str]:
    """One click down: the skeleton's numbers, and the checks between the parts."""
    out = [f"{s.name.replace('_', ' ')}: {number(s, inches)}" + (f" ({s.why})" if s.why else "") for s in plan.skeleton]
    out += [f"{m.kind.replace('_', ' ')}: {m.between[0]} and {m.between[1]}" for m in plan.mates]
    out += [f"check {r.id}: {r.expr}" for r in plan.rules]
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
other. Pieces of one sheet-goods or printed part stay ONE part (a step stool of plywood panels is one part). Things \
the person already has are parts with role "fixed" (drawn from their stated size as a reference, never designed).

Name the numbers the parts share as the skeleton: each with a value, a unit (mm, in, ft, m, cm, deg, N, lb, kg or \
count) and why. Write mates between parts (touch, clearance, fit, no_interference) and rules over part ids and \
skeleton names, so every interface is measured. A rule may call: interference(a, b), min_clearance(a, b), \
hole_misalignment(a, b), holes_aligned(a, b), bbox(part).min/.max/.size (.x .y .z, mm), abs, min, max. Lengths in \
rules are mm; a skeleton name in a rule reads in mm. Each part says what it mounts on (the parts it's built onto).

Ids and names are lowercase with underscores. Answer by calling the plan tool, once."""


def _tool() -> dict:
    return {"name": "plan", "description": "The design's parts, the numbers they share, and the checks between them.",
            "input_schema": Plan.model_json_schema()}


def _ask(client, model: Optional[str], content: str) -> Plan:
    from .chat import DEFAULT_MODEL

    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=4000, system=SYSTEM, tools=[_tool()],
                                 tool_choice={"type": "tool", "name": "plan"},
                                 messages=[{"role": "user", "content": content}])
    got = next((b.input for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
    if got is None:
        raise PlanError("the planner didn't answer with a plan")
    return validate(got)


def propose(store, *, client=None, model: Optional[str] = None) -> Plan:
    """The planner's plan for the design's sentence and its answered questions, validated."""
    asked = "\n".join(f"- {r.question} {r.answer}" for r in store.design.requirements)
    units = "inches and feet" if store.design.display_units == "in" else "mm"
    return _ask(client, model, f"What to make: {store.design.prompt}\n\nWhat was clarified:\n{asked or '- nothing'}\n\n"
                               f"The person talks in {units}.")


def revise(store, said: str, *, client=None, model: Optional[str] = None) -> tuple[Plan, Plan]:
    """The plan as the person's words change it, during review: (before, after), both validated. The chat edits
    the plan, never the geometry: "make the mast 10 ft" changes a skeleton number."""
    import json

    before = load(store)
    if before is None:
        raise PlanError("there's no plan to change")
    after = _ask(client, model, "The plan now:\n" + json.dumps(before.model_dump(), indent=1)
                 + f"\n\nThe person said: {said}\n\nAnswer with the whole plan as it should now be. Change only what "
                   "they asked for; keep every other part, number and check as it is.")
    return before, after
