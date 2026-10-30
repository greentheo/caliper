"""CALI-16 — the LLM author: spec → CadQuery script, self-healing build errors.

This is the design spec's **primary generation strategy** (§2): instead of a hardcoded part family,
the LLM writes a parametric ``build(params)`` script, we run it sandboxed (:mod:`caliper.sandbox`),
and on a build error we feed the **traceback back** to the LLM to revise — the "stack trace as
feedback" channel, now closing on geometry. The authored script is the human-editable source of truth
and is stored per run.

The LLM call is **injectable** (an ``author(spec, feedback, prior) -> str`` callable), mirroring how
the loop injects ``eval_fn`` — so the author/heal mechanism is fully testable without a key.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import consistency, sandbox
from .spec import Spec

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")
#: Long enough for a multi-member part plus helper functions; the old 2000 cut a tube frame off mid-line,
#: and a part now writes its construction() beside build() (CALI-54).
AUTHOR_MAX_TOKENS = 12000

# author(spec, feedback, prior_script) -> python source for `build(params)`
Author = Callable[[Spec, Optional[str], Optional[str]], str]


def params_from_spec(spec: Spec) -> dict:
    """Resolve the concrete ``{name: value}`` dict the authored ``build(params)`` receives."""
    out: dict[str, Any] = {}
    for name, prm in spec.parameters.items():
        out[name] = getattr(prm, "init", getattr(prm, "value", None))
    return out


def extract_code(text: str) -> str:
    """Pull Python source out of an LLM reply that may be fenced or prefixed with prose."""
    t = text.strip()
    fence = re.search(r"```(?:python|py)?\s*(.*?)```", t, re.S)
    if fence:
        return fence.group(1).strip()
    return t


#: The part-script reference, shared with contributors: what the prompt says is what the docs say (CALI-54).
REFERENCE = os.path.join(os.path.dirname(__file__), "part_scripts.md")

_SYSTEM = """You are Caliper's generator. You write a part script: a Python file whose build(params)
makes the part as ONE watertight cadquery solid, plus whatever it declares about how it's built.

Rules:
- `cq` (the cadquery module) is already available; you may also `import cadquery as cq` inside build.
- Use the values in `params` for dimensions; never hardcode a dimension that's a parameter.
- Model the part the intent describes. Use only the Python standard library and cadquery. No file I/O,
  no network.
- If the part is made from sheet goods, lumber or steel tube, declare what it's built from (BUILD and
  construction(), or members() and supports() for a welded tube frame), using only the materials listed
  below. Caliper checks the declarations against the solid every time it builds the part.
- Output ONLY the Python code of the script — no markdown fences, no prose, no example calls.

The reference for part scripts follows. It is the same document contributors read.

"""


def system_prompt() -> str:
    """The generator's instructions: the rules, the part-script reference, and the materials table."""
    from . import materials

    with open(REFERENCE) as f:
        reference = f.read()
    return f"{_SYSTEM}{reference}\n\n## The materials table\n\n{materials.table()}\n"


def author_script(
    spec: Spec,
    feedback: Optional[str] = None,
    prior: Optional[str] = None,
    client=None,
    model: Optional[str] = None,
) -> str:
    """Ask Claude to write (or revise) the ``build(params)`` script for ``spec``."""
    model = model or DEFAULT_MODEL
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()

    goals = "\n".join(f"  - {a.id}: {a.expr}" for a in spec.assertions)
    params = "\n".join(
        f"  - {n}: {getattr(p, 'type', '?')} = {getattr(p, 'init', getattr(p, 'value', None))}"
        f"{(' ' + p.unit) if getattr(p, 'unit', None) else ''}"
        for n, p in spec.parameters.items()
    )
    ask = (
        f"part: {spec.part}\nintent: {spec.intent}\n\n"
        f"parameters (your build(params) receives these by name):\n{params or '  (none)'}\n\n"
        f"it should aim to satisfy these measured assertions:\n{goals or '  (none)'}"
    )
    if prior and feedback:
        ask += (
            "\n\nYour previous attempt did not satisfy the spec. Revise the script to fix it; keep the "
            "checks that already pass passing.\n"
            f"--- previous build(params) ---\n{prior}\n"
            f"--- problem ---\n{feedback}"
        )

    msg = client.messages.create(
        model=model, max_tokens=AUTHOR_MAX_TOKENS, system=system_prompt(),
        messages=[{"role": "user", "content": ask}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    code = extract_code(text)
    if getattr(msg, "stop_reason", None) == "max_tokens":
        # A reply cut off mid-script would otherwise come back as a baffling SyntaxError (seen live: a
        # seven-tube frame plus members() overran the old 2000-token cap on every attempt). Fail the build
        # with the real reason, so the next round's feedback says what to fix.
        code += ("\n\nraise RuntimeError('this script was cut off: the reply hit the length limit "
                 "before it finished. Write it more compactly: loops and small helpers instead of "
                 "repeating near-identical blocks.')\n")
    return code


@dataclass
class AuthorResult:
    ok: bool
    geometry: Any = None
    script: str = ""
    attempts: int = 0
    error: str = ""
    history: list[str] = field(default_factory=list)  # one feedback string per failed attempt


def generate_part(
    spec: Spec,
    author: Optional[Author] = None,
    max_attempts: int = 3,
    timeout: float = 25.0,
    client=None,
) -> AuthorResult:
    """Author a script and build it, retrying with the build error until it builds or we give up.

    ``author`` defaults to the real Claude call; tests inject a deterministic stub. Returns the built
    :class:`~caliper.measure.Geometry` plus the winning script, or the last error after ``max_attempts``.
    """
    if author is None:
        def author(s: Spec, feedback: Optional[str], prior: Optional[str]) -> str:
            return author_script(s, feedback=feedback, prior=prior, client=client)

    params = params_from_spec(spec)
    feedback: Optional[str] = None
    prior: Optional[str] = None
    history: list[str] = []
    script = ""

    for attempt in range(1, max_attempts + 1):
        script = author(spec, feedback, prior)
        run = sandbox.run_script(script, params, timeout=timeout)
        if run.ok:
            return AuthorResult(ok=True, geometry=run.geometry, script=script,
                                attempts=attempt, history=history)
        prior = script
        feedback = run.feedback
        history.append(feedback)

    return AuthorResult(ok=False, script=script, attempts=max_attempts,
                        error=feedback or "author failed", history=history)


# ---------------------------------------------------------------------------
# CALI-17 — the structural-edit loop: revise the script to fix failing MEASUREMENTS
# ---------------------------------------------------------------------------
def _failing_summary(report) -> str:
    """A compact, actionable list of the assertions that didn't pass — the feedback for a revision."""
    lines = []
    for r in report.results:
        if r.status in ("fail", "error"):
            margin = "" if r.margin is None else f" (margin {r.margin:+.3g})"
            detail = f"\n      {r.detail}" if r.detail else ""
            lines.append(f"  - {r.id}: {r.expr}  → actual={r.actual}{margin}  [{r.status}]{detail}")
    return "\n".join(lines)


def _report_signature(report) -> tuple:
    """Coarse fingerprint of the failing checks — a repeat ⇒ the LLM is going in circles."""
    return tuple(
        (r.id, r.status, None if r.margin is None else round(float(r.margin), 3))
        for r in report.results if r.status in ("fail", "error")
    )


@dataclass
class ImproveResult:
    ok: bool
    geometry: Any = None
    script: str = ""
    report: Any = None              # caliper.evaluate.Report (None if nothing ever built)
    rounds: int = 0
    error: str = ""
    history: list[tuple] = field(default_factory=list)  # (kind, detail) per round


def improve(
    spec: Spec,
    author: Optional[Author] = None,
    max_rounds: int = 4,
    timeout: float = 25.0,
    client=None,
    machine=None,
    seed_script: Optional[str] = None,
    seed_feedback: Optional[str] = None,
    ref_base: str = ".",
) -> ImproveResult:
    """Author a part and drive it to green: build errors AND failing measurements both feed back.

    The design spec's two-actor loop, for LLM-authored geometry (§2/§5): each round the LLM writes (or
    revises) the script; we build it sandboxed and measure it, its declarations against its solid too
    (:mod:`caliper.consistency`); a build error or a failing assertion becomes the feedback for the next
    revision. Stops on success, an unchanged failure signature
    (oscillation), or the round cap — mirroring the bracket loop's safety rails (CALI-6).

    ``seed_script`` + ``seed_feedback`` **prime round 1 with an existing part** so the LLM *edits the
    real part* instead of starting over — the basis for author-loop fit & refine (CALI-22): pass a
    prior run's ``part.py`` as the seed and the new constraint (clear this reference / apply this edit)
    as the feedback. ``ref_base`` resolves relative reference paths (the run dir, for a re-fit).

    ``author`` is injectable (tests pass a deterministic stub); it defaults to the real Claude call.
    """
    from .evaluate import DEFAULT_MACHINE, evaluate, load_references

    if author is None:
        def author(s: Spec, feedback: Optional[str], prior: Optional[str]) -> str:
            return author_script(s, feedback=feedback, prior=prior, client=client)

    params = params_from_spec(spec)
    references = load_references(spec, ref_base) if spec.references else None
    machine = machine or DEFAULT_MACHINE

    feedback: Optional[str] = seed_feedback
    prior: Optional[str] = seed_script
    history: list[tuple] = []
    seen: set = set()
    best: Optional[tuple] = None  # (geometry, script, report)

    for rnd in range(1, max_rounds + 1):
        script = author(spec, feedback, prior)
        run = sandbox.run_script(script, params, timeout=timeout)
        prior = script

        if not run.ok:  # build error → "stack trace" feedback (CALI-16 heal, folded into the loop)
            feedback = f"Your script raised an error when built:\n{run.feedback}"
            history.append(("build_error", run.feedback))
            continue

        report = evaluate(spec, run.geometry, machine, references=references)
        # CALI-54: what the script says it's built from is measured against what it built
        report.results.extend(consistency.check(run.declared, run.geometry))
        best = (run.geometry, script, report)
        if report.all_pass:
            history.append(("passed", ""))
            return ImproveResult(ok=True, geometry=run.geometry, script=script, report=report,
                                 rounds=rnd, history=history)

        summary = _failing_summary(report)
        history.append(("measurement_fail", summary))
        sig = _report_signature(report)
        if sig in seen:  # same failures again → the LLM is stuck; stop rather than spin
            break
        seen.add(sig)
        feedback = ("Your part built but failed these measured checks. Revise the script so they pass "
                    "(keep the passing ones passing):\n" + summary)

    if best is not None:
        geom, script, report = best
        return ImproveResult(ok=report.all_pass, geometry=geom, script=script, report=report,
                             rounds=max_rounds, history=history)
    return ImproveResult(ok=False, script=prior or "", rounds=max_rounds,
                         error=feedback or "author failed", history=history)


# ---------------------------------------------------------------------------
# CALI-22 — author-loop fit & refine: edit the REAL part, not a bracket
# ---------------------------------------------------------------------------
# Fit/refine used to rebuild via the bracket generator, so they ignored an authored part.py (CALI-19
# guarded them to fail honestly). These route through ``improve`` **seeded with the existing script**:
# the LLM edits the real part to satisfy a new fit constraint or apply a plain-language change, with
# the same build-error + failing-measurement healing as ``gen``.

def refit_authored(
    spec: Spec,
    script: str,
    max_rounds: int = 4,
    ref_base: str = ".",
    author: Optional[Author] = None,
    client=None,
) -> ImproveResult:
    """Re-fit an authored part: the LLM revises ``part.py`` to satisfy the fit assertions now on ``spec``.

    ``spec`` must already carry the reference(s) + fit assertion(s) (via ``fit.attach_reference``). The
    existing ``script`` seeds round 1 so the model edits dimensions/placement rather than starting over.
    """
    constraints = "\n".join(
        f"  - {a.id}: {a.expr}" for a in spec.assertions
        if any(a.id.endswith(s) for s in ("_no_interference", "_clearance", "_fit"))
    )
    feedback = (
        "The part below already builds. It now must also FIT imported reference geometry. Revise the "
        "script — change dimensions or placement as needed, keep it ONE watertight solid and keep the "
        "other checks passing — so these measured checks pass:\n" + (constraints or "  (fit checks)")
    )
    return improve(spec, author=author, max_rounds=max_rounds, client=client,
                   seed_script=script, seed_feedback=feedback, ref_base=ref_base)


def refine_authored(
    spec: Spec,
    script: str,
    instruction: str,
    max_rounds: int = 4,
    ref_base: str = ".",
    author: Optional[Author] = None,
    client=None,
) -> ImproveResult:
    """Apply a natural-language change to an authored part by revising its script (CALI-22).

    The instruction is folded into ``spec.intent`` so it persists across revision rounds (otherwise a
    later round, fed only the failing-measurement summary, could quietly undo the requested edit).
    """
    spec.intent = (spec.intent + "  " if spec.intent else "") + instruction
    feedback = (
        "Apply this change to the part below, keeping the existing measured checks passing (change as "
        "little else as possible):\n  " + instruction
    )
    return improve(spec, author=author, max_rounds=max_rounds, client=client,
                   seed_script=script, seed_feedback=feedback, ref_base=ref_base)
