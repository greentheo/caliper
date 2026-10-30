"""CALI-30 — feedback becomes a test.

The idea that makes a design's history worth keeping (``specs/caliper-conversational-spec.md`` §2).
A conversational CAD tool that only ever *edits* accumulates drift: you say "make the mount clear the
rail", it happens, and nothing stops revision #14 from quietly undoing it. Caliper has a better option
than any chat-with-CAD toy, because measurement is already its source of truth — **feedback that can be
measured is promoted into an assertion**::

    "the carriage needs to clear the rail"  ->  min_clearance(carriage, rail) >= 1.0

Now it's a test, checked on every later revision by machinery that already exists.

Three rules this module exists to enforce:

- **Validate before offering.** A proposal is built, then *actually evaluated* against the current
  geometry. An expression that won't parse, names a probe that doesn't exist, or throws is never shown
  to the user. Offering a broken test is worse than offering none.
- **Propose, never promote silently.** An over-constrained spec fails in confusing ways, and the human
  has to know which rules exist. The proposal is parked (``pending.json``) and the next turn accepts or
  declines it.
- **Be honest about what can't be measured.** "Make it look less chunky" is not a number. It stays a
  plain edit, labelled unenforceable, rather than being faked into a threshold nobody asked for.

Two levels, because Caliper has two namespaces: a **part** assertion goes in that part's ``spec.assert``
and sees one geometry (``bbox``, ``min_wall``, ``body_count``…); a **design** assertion goes in
``assembly.assertions`` and sees every part by id plus the pairwise probes (``min_clearance(a, b)``,
``hole_misalignment(a, b)``…). Drafting picks the level; validation uses the matching namespace.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

from .design import DesignStore
from .spec import Assertion, Spec

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")

#: The measurement vocabulary an assertion may use, by level. Kept here (rather than inferred) so the
#: drafting prompt and the offline patterns can't drift from what the evaluator actually binds.
PART_VOCABULARY = """  bbox.dx / bbox.dy / bbox.dz      overall size in mm
  bbox.min / bbox.max              corner coordinates [x, y, z]
  min_wall                         thinnest wall, mm
  body_count                       number of separate solids
  is_watertight / is_manifold      booleans
  volume                           mm^3
  mass(density)                    grams, density in g/cm^3
  largest_through_bore             diameter of the largest through hole, mm
  holes_matching(diameter, on=circle(d), count=n, tol=0.3)
  machine.nozzle / machine.bed_x / machine.bed_y / machine.bed_z"""

DESIGN_VOCABULARY = """  min_clearance(a, b)              smallest gap between two parts, mm
  interference(a, b)               overlap volume, mm^3 (0 = no collision)
  max_interference()               worst overlap across every pair
  min_clearance_all()              tightest gap across every pair
  hole_misalignment(a, b)          how far the nearest hole axes miss, mm
  holes_aligned(a, b, tol=0.5)     boolean
  bbox(part).dx / .dy / .dz        one part's size in mm
  <part_id>                        every part in the design is bound by id"""

#: CALI-68 (#28): how far a measurement can be off, on a part that's right. Parts are measured on a mesh
#: tessellated to 0.05 mm, so a size can read up to 0.05 short at each side; a wall is ray-cast across that
#: mesh from just inside its surface (19.05 mm ply reads 18.98). A rule that pins one of them allows for it.
MEASURING = {"min_wall": 0.15, "bbox.dx": 0.1, "bbox.dy": 0.1, "bbox.dz": 0.1}

_ID_OK = re.compile(r"^[a-z][a-z0-9_]*$")
_YES = re.compile(r"\b(yes|yep|yeah|sure|ok|okay|do it|lock it in|lock that in|enforce|keep it|accept|"
                  r"please do|go ahead|sounds good)\b")
_NO = re.compile(r"\b(no|nope|don'?t|do not|skip|decline|leave it|not now|nah|forget it)\b")


# ---------------------------------------------------------------------------
# The proposal
# ---------------------------------------------------------------------------
@dataclass
class Proposal:
    """A candidate assertion, already proven to evaluate. Never constructed without validation."""

    id: str
    expr: str
    level: str                     # "part" | "design"
    part: Optional[str] = None     # the part it constrains (and where a part-level one is stored)
    why: str = ""                  # the feedback it came from, in the user's words
    holds_now: bool = True         # does the current geometry satisfy it?
    actual: object = None          # what it measured when validated
    source: str = "offline"        # "offline" | "llm"
    #: Enforced rules this proposal cannot co-exist with — accepting it replaces them (CALI-30).
    conflicts: list = field(default_factory=list)   # [(level, id, expr)]

    def to_dict(self) -> dict:
        return {"id": self.id, "expr": self.expr, "level": self.level, "part": self.part,
                "why": self.why, "holds_now": self.holds_now, "actual": _plain(self.actual),
                "source": self.source, "conflicts": [list(c) for c in self.conflicts]}

    @classmethod
    def from_dict(cls, d: dict) -> "Proposal":
        return cls(id=d["id"], expr=d["expr"], level=d.get("level", "part"), part=d.get("part"),
                   why=d.get("why", ""), holds_now=bool(d.get("holds_now", True)),
                   actual=d.get("actual"), source=d.get("source", "offline"),
                   conflicts=[tuple(c) for c in d.get("conflicts", [])])

    def describe(self) -> str:
        """The line the chat shows. Says what it means, and whether it's true right now."""
        scope = "the design" if self.level == "design" else f"'{self.part}'"
        actual = "" if self.actual is None else f" (measured {_fmt(self.actual)})"
        lines = [f"💡 I can lock that in as a test on {scope}:", f"    {self.id}: {self.expr}"]
        allowed = re.search(r" [-+] (\d+(?:\.\d+)?)\b", self.expr)
        if allowed and any(k.split(".")[-1] in self.expr for k in MEASURING):
            lines.append(f"    (the {allowed.group(1)} mm is what measuring it can be off by, on a part that's right)")
        if self.holds_now:
            lines.append(f"    ✓ it holds now{actual}. Every future revision would be checked "
                         f"against it.")
        else:
            # The honest reading: we just made a change on this feedback and the check it implies is
            # still failing — so the edit did not achieve what was asked.
            lines.append(f"    ⚠ it does **not** hold right now{actual} — so the change didn't "
                         f"actually achieve what you asked for.")
            lines.append("    Accept it and I'll have to make the part satisfy it.")
        for level, cid, cexpr in self.conflicts:
            where = "the design" if level == "design" else f"'{self.part}'"
            lines.append(f"    ⚠ It contradicts a rule you already locked in on {where} — "
                         f"**{cid}**: `{cexpr}`. Both can't hold.")
        if self.conflicts:
            lines.append("    Saying **yes** replaces that older rule with this one.")
        lines.append("    Say **yes** to enforce it, or **no** to leave it as a one-off change.")
        return "\n".join(lines)


@dataclass
class Draft:
    """What drafting produced: a proposal, or an honest reason there isn't one."""

    proposal: Optional[Proposal] = None
    measurable: bool = True
    reason: str = ""
    rejected: list[str] = field(default_factory=list)   # candidates that failed validation, with why


def _plain(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        return str(v)


def _fmt(v) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)


# ---------------------------------------------------------------------------
# Validation — a proposal is never offered until it has actually been measured
# ---------------------------------------------------------------------------
@dataclass
class Validation:
    ok: bool
    holds: bool = False
    actual: object = None
    error: str = ""


def validate(store: DesignStore, expr: str, level: str, part: Optional[str] = None) -> Validation:
    """Evaluate ``expr`` against the design's *current* geometry in the matching namespace.

    ``ok`` means the expression is usable — it parsed, every name resolved, and measuring it didn't
    throw. ``holds`` is whether it currently passes, which is a different question: a proposal that
    doesn't hold yet is still worth offering (the user may be stating a goal), but the chat must say so
    rather than implying the part already complies.
    """
    from .evaluate import evaluate_assertion

    try:
        ctx = _context(store, level, part)
    except Exception as e:  # noqa: BLE001 — a design that won't build can't validate anything
        return Validation(ok=False, error=f"{type(e).__name__}: {e}")

    res = evaluate_assertion(Assertion(id="_candidate", expr=expr), ctx)
    if res.status in ("error", "deferred"):
        return Validation(ok=False, error=res.detail or res.status)
    return Validation(ok=True, holds=(res.status == "pass"), actual=res.actual)


def _context(store: DesignStore, level: str, part: Optional[str]) -> dict:
    from . import evaluate as ev
    from .assembly import build_context, load_parts

    from .occt import OCCT

    with OCCT:
        parts = load_parts(store.assembly, base_dir=store.root)
    if level == "design":
        return build_context(store.assembly, parts)
    if not part or part not in parts:
        raise ValueError(f"unknown part {part!r}")
    spec = store.read_spec(part) or Spec(part=part)
    refs = ev.load_references(spec, store.root) if spec.references else None
    return ev.build_context(spec, parts[part], ev.DEFAULT_MACHINE, references=refs)


# ---------------------------------------------------------------------------
# Drafting — offline patterns first, Claude when it's there
# ---------------------------------------------------------------------------
_NUM = r"(\d+(?:\.\d+)?)"
#: Deterministic patterns for the phrasings that come up constantly. Not an attempt at NLP — a
#: reliable floor under the LLM path so the offline route proposes *something* correct rather than
#: guessing, and so the tests don't need a key.
_PATTERNS: list[tuple[str, str]] = [
    # "clear the rail by at least 1mm" / "must clear rail by 1 mm"
    (rf"clear(?:s|ance)?\s+(?:the\s+|of\s+)?(?P<other>\w+)\s+(?:by\s+)?(?:at\s+least\s+)?{_NUM}\s*mm",
     "clearance"),
    # "must not touch the rail" / "never collide with rail"
    (r"(?:not|never|don'?t|doesn'?t|must\s+not)\s+(?:touch|collide\s+with|hit|overlap)\s+"
     r"(?:the\s+)?(?P<other>\w+)", "no_interference"),
    # "no taller than 40mm" / "must be under 40 mm tall"
    (rf"(?:no\s+(?:taller|higher)\s+than|under|below|at\s+most|max(?:imum)?)\s+{_NUM}\s*mm\s*(?:tall|high)?",
     "max_height"),
    # "walls at least 2mm" / "minimum wall 2.4mm"
    (rf"(?:wall|thickness)\w*\s+(?:of\s+)?(?:at\s+least\s+|min(?:imum)?\s+)?{_NUM}\s*mm", "min_wall"),
    (rf"min(?:imum)?\s+wall\s+{_NUM}\s*mm", "min_wall"),
    # "must stay one piece" / "one watertight body"
    (r"\b(?:one|single)\s+(?:piece|body|solid)\b", "one_body"),
]


def offline_draft(store: DesignStore, part: str, feedback: str) -> Draft:
    """Pattern-match the common, unambiguous phrasings. Silent (no proposal) when unsure."""
    text = (feedback or "").lower()
    ids = {p.id for p in store.design.parts}

    for pattern, kind in _PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        groups = m.groupdict()
        other = groups.get("other")
        value = next((g for g in m.groups() if g and re.fullmatch(_NUM, g)), None)

        if kind in ("clearance", "no_interference"):
            if not other or other not in ids or other == part:
                continue  # names something that isn't a part in this design — don't invent a probe
            if kind == "clearance":
                return _candidate(store, f"{part}_clears_{other}",
                                  f"min_clearance({part}, {other}) >= {float(value)}",
                                  "design", part, feedback)
            return _candidate(store, f"{part}_misses_{other}",
                              f"interference({part}, {other}) <= 0", "design", part, feedback)
        if kind == "max_height" and value:
            return _candidate(store, f"{part}_height", f"bbox.dz <= {float(value)}",
                              "part", part, feedback)
        if kind == "min_wall" and value:
            return _candidate(store, f"{part}_wall", f"min_wall >= {float(value)}",
                              "part", part, feedback)
        if kind == "one_body":
            return _candidate(store, f"{part}_one_body", "body_count == 1", "part", part, feedback)

    return Draft(measurable=False,
                 reason="nothing in that maps onto something Caliper can measure")


_OPS = {ast.GtE: "ge", ast.Gt: "ge", ast.LtE: "le", ast.Lt: "le", ast.Eq: "eq"}


def _bounds(expr: str):
    """``left OP number`` → ``(left_source, lo, hi)``, or ``None`` if it isn't that simple shape.

    Only single comparisons against a literal are handled. Anything else (chained bands, booleans,
    calls returning non-numbers) returns ``None`` and is treated as "can't reason about it" — which is
    the right default: a false conflict claim is worse than no claim.
    """
    try:
        tree = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(tree, ast.Compare) or len(tree.ops) != 1 or len(tree.comparators) != 1:
        return None
    kind = _OPS.get(type(tree.ops[0]))
    if kind is None:
        return None
    value = _number(tree.comparators[0])
    if value is None:
        return None
    left = ast.unparse(tree.left).replace(" ", "")
    if kind == "ge":
        return left, value, math.inf
    if kind == "le":
        return left, -math.inf, value
    return left, value, value


def _number(node) -> Optional[float]:
    """A literal number, or literal numbers added and taken away (``19.05 - 0.15``, CALI-68)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _number(node.operand)
        return None if v is None else -v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        a, b = _number(node.left), _number(node.right)
        if a is None or b is None:
            return None
        return a + b if isinstance(node.op, ast.Add) else a - b
    return None


def _incompatible(a, b) -> bool:
    """Do two bounds over the same measurement have an empty intersection?"""
    return max(a[1], b[1]) > min(a[2], b[2])


def conflicts(store: DesignStore, expr: str, level: str, part: Optional[str]) -> list:
    """Enforced rules that measure the same thing and cannot hold at the same time as ``expr``."""
    mine = _bounds(expr)
    if mine is None:
        return []
    out = []
    enforced = [("design", a) for a in store.assembly.assertions]
    if part:
        spec = store.read_spec(part)
        if spec is not None:
            enforced += [("part", a) for a in spec.assertions]
    for lvl, a in enforced:
        if lvl != level:
            continue                      # different namespaces measure different things
        theirs = _bounds(a.expr)
        if theirs is None or theirs[0] != mine[0]:
            continue
        if _incompatible(mine, theirs):
            out.append((lvl, a.id, a.expr))
    return out


def _unique_id(store: DesignStore, aid: str, level: str) -> str:
    """Keep a design-level id from shadowing a **mate**.

    Mates expand to assertions under their own id (``derived_assertions``), and a promoted assertion
    with the same id would produce two rows sharing one name — which makes "what did this change
    break?" ambiguous, since that comparison is keyed by id. Re-promoting the same id at the same level
    is fine (``accept`` replaces it); colliding with a mate is not, so we step aside.
    """
    if level != "design":
        return aid
    taken = {m.id for m in store.assembly.mates}
    out, n = aid, 1
    while out in taken:
        n += 1
        out = f"{aid}_{n}"
    return out


def _measured_as(node) -> Optional[str]:
    """The measurement a comparison's left side is, in :data:`MEASURING`'s terms (``bbox(lid).dz`` counts as
    ``bbox.dz``), or None."""
    if isinstance(node, ast.Name):
        return node.id if node.id in MEASURING else None
    if isinstance(node, ast.Attribute) and node.attr in ("dx", "dy", "dz"):
        base = node.value
        if (isinstance(base, ast.Name) and base.id == "bbox") or (
                isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "bbox"):
            return f"bbox.{node.attr}"
    return None


def allow_for_measuring(expr: str) -> str:
    """``min_wall >= 19.05`` -> ``min_wall >= 19.05 - 0.15``: a rule pinning a measured size, with what measuring
    it can be off by written into it, so a part that's right reads as holding. Anything else unchanged."""
    try:
        tree = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return expr
    if not isinstance(tree, ast.Compare) or len(tree.ops) != 1:
        return expr
    rhs = tree.comparators[0]
    what = _measured_as(tree.left)
    if what is None or not isinstance(rhs, ast.Constant) or not isinstance(rhs.value, (int, float)) \
            or isinstance(rhs.value, bool):
        return expr
    tol, left, v = MEASURING[what], ast.unparse(tree.left), ast.unparse(rhs)      # their number, as written
    op = type(tree.ops[0])
    if op in (ast.GtE, ast.Gt):
        return f"{left} {'>=' if op is ast.GtE else '>'} {v} - {tol:g}"
    if op in (ast.LtE, ast.Lt):
        return f"{left} {'<=' if op is ast.LtE else '<'} {v} + {tol:g}"
    if op is ast.Eq:
        return f"{v} - {tol:g} <= {left} <= {v} + {tol:g}"
    return expr


def _candidate(store: DesignStore, aid: str, expr: str, level: str, part: str, why: str,
               source: str = "offline") -> Draft:
    """Build and **validate** a candidate. A proposal that won't evaluate is never returned. A rule that pins a
    measured size allows for what measuring it can be off by (CALI-68)."""
    if not _ID_OK.match(aid):
        return Draft(measurable=True, reason=f"bad assertion id {aid!r}", rejected=[aid])
    expr = allow_for_measuring(expr)
    aid = _unique_id(store, aid, level)
    v = validate(store, expr, level, part)
    if not v.ok:
        return Draft(measurable=True, reason=f"that check doesn't measure cleanly: {v.error}",
                     rejected=[f"{expr} → {v.error}"])
    return Draft(proposal=Proposal(id=aid, expr=expr, level=level, part=part, why=why,
                                   holds_now=v.holds, actual=v.actual, source=source,
                                   conflicts=conflicts(store, expr, level, part)))


_DRAFT_SYSTEM = """You turn a piece of design feedback into ONE measurable Caliper assertion, or say it
isn't measurable. Reply with ONLY a JSON object:

{"measurable": true|false, "level": "part"|"design", "id": "<snake_case>", "expr": "<expression>",
 "reason": "<if not measurable, why>"}

- "part" level sees ONE part's geometry:
%s

- "design" level sees EVERY part by id, and the probes between them:
%s

Rules:
- Use ONLY the names listed above. Never invent a probe.
- Anything relating two parts is "design" level. Anything about one part alone is "part" level.
- The expression must be a single Python comparison (>=, <=, ==, or a chained a <= x <= b).
- Prefer the threshold the user actually stated. If they gave no number and none can be inferred from
  the design, set measurable=false rather than inventing one.
- Aesthetic or vague feedback ("looks chunky", "cleaner", "nicer") is NOT measurable.""" % (
    PART_VOCABULARY, DESIGN_VOCABULARY)


def llm_draft(store: DesignStore, part: str, feedback: str, client=None,
              model: Optional[str] = None) -> Draft:
    """Draft with Claude, then validate the result exactly as strictly as the offline path."""
    model = model or DEFAULT_MODEL
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()

    ask = (f"{store.prompt_context(part)}\n\n"
           f"the user said this about '{part}': {feedback}\n\n"
           f"What single assertion would lock that in permanently?")
    msg = client.messages.create(model=model, max_tokens=400, system=_DRAFT_SYSTEM,
                                 messages=[{"role": "user", "content": ask}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)

    if not data.get("measurable"):
        return Draft(measurable=False, reason=str(data.get("reason") or "not measurable"))
    level = "design" if str(data.get("level")) == "design" else "part"
    aid = str(data.get("id") or f"{part}_check").strip()
    expr = str(data.get("expr") or "").strip()
    if not expr:
        return Draft(measurable=False, reason="the draft had no expression")
    return _candidate(store, aid, expr, level, part, feedback, source="llm")


def draft(store: DesignStore, part: str, feedback: str, *, use_llm: bool = True, client=None,
          drafter=None) -> Draft:
    """Claude when available, patterns otherwise — and drafting never crashes a turn."""
    if drafter is not None:
        return drafter(store, part, feedback)
    if use_llm and (client is not None or os.environ.get("ANTHROPIC_API_KEY")):
        try:
            got = llm_draft(store, part, feedback, client=client)
            if got.proposal is not None or not got.measurable:
                return got
        except Exception as e:  # noqa: BLE001 — a failed draft must not sink the user's edit
            print(f"[promote] LLM drafting failed → offline: {type(e).__name__}: {e}", file=sys.stderr)
    return offline_draft(store, part, feedback)


# ---------------------------------------------------------------------------
# Pending proposals — parked between turns, because acceptance is a separate turn
# ---------------------------------------------------------------------------
def pending_path(store: DesignStore) -> str:
    return os.path.join(store.root, "pending.json")


def park(store: DesignStore, proposal: Proposal) -> Proposal:
    with open(pending_path(store), "w") as f:
        json.dump(proposal.to_dict(), f, indent=2)
    return proposal


def pending(store: DesignStore) -> Optional[Proposal]:
    path = pending_path(store)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return Proposal.from_dict(json.load(f))
    except Exception:  # noqa: BLE001 — a corrupt parking slot must not break the conversation
        return None


def clear(store: DesignStore) -> None:
    path = pending_path(store)
    if os.path.exists(path):
        os.remove(path)


def reads_as_yes(message: str) -> Optional[bool]:
    """Is this message an answer to a pending proposal? ``True``/``False``/``None`` for "not an answer"."""
    text = (message or "").strip().lower()
    if not text:
        return None
    no, yes = _NO.search(text), _YES.search(text)
    if no and not yes:
        return False
    if yes and not no:
        return True
    return None


# ---------------------------------------------------------------------------
# Acceptance — where the assertion actually lands
# ---------------------------------------------------------------------------
def accept(store: DesignStore, proposal: Proposal) -> str:
    """Append the assertion where it will be enforced, and record it in the part's history.

    A **part** assertion joins that part's ``spec.assert``, so every later revision of the part is
    measured against it by the author loop. A **design** assertion joins ``assembly.assertions``, so it
    is checked whenever *anything* in the design changes — which is what a cross-part constraint needs.
    """
    retired = {cid for _, cid, _ in proposal.conflicts}
    if proposal.level == "design":
        existing = [a for a in store.assembly.assertions
                    if a.id == proposal.id or a.id in retired]
        for a in existing:
            store.assembly.assertions.remove(a)
        store.assembly.assertions.append(Assertion(id=proposal.id, expr=proposal.expr))
        store.save()
        where = "the design"
    else:
        part = proposal.part
        spec = store.read_spec(part) or Spec(part=part,
                                             intent=(store.design.part(part).intent
                                                     if store.design.part(part) else ""))
        spec.assertions = [a for a in spec.assertions
                           if a.id != proposal.id and a.id not in retired]
        spec.assertions.append(Assertion(id=proposal.id, expr=proposal.expr))
        store.write_spec(part, spec)
        where = f"'{part}'"

    if proposal.part:
        store.append_history(proposal.part, {
            "kind": "assertion", "action": "promoted", "id": proposal.id, "expr": proposal.expr,
            "level": proposal.level, "from_feedback": proposal.why, "holds_now": proposal.holds_now,
            **({"replaced": sorted(retired)} if retired else {}),
        })
    store.append_log({"kind": "assertion", "action": "promoted", "id": proposal.id,
                      "expr": proposal.expr, "level": proposal.level})
    clear(store)
    return where


def decline(store: DesignStore, proposal: Proposal) -> None:
    """Log the refusal so the history records that the change was a one-off, deliberately."""
    if proposal.part:
        store.append_history(proposal.part, {
            "kind": "assertion", "action": "declined", "id": proposal.id, "expr": proposal.expr,
            "from_feedback": proposal.why,
        })
    store.append_log({"kind": "assertion", "action": "declined", "id": proposal.id})
    clear(store)
