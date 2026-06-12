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

from . import sandbox
from .spec import Spec

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")

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


_SYSTEM = """You are Caliper's generator. Write a SINGLE Python function:

    def build(params):
        # params is a dict of the spec's parameters (mm unless noted)
        ...
        return solid   # a cadquery Workplane or Solid

Rules:
- `cq` (the cadquery module) is already available; you may also `import cadquery as cq` inside build.
- Use the values in `params` for dimensions; never hardcode a dimension that's a parameter.
- Return ONE watertight solid (a Workplane is fine). Model the part the intent describes.
- Use only the Python standard library and cadquery. No file I/O, no network.
- Output ONLY the Python code for build(params) — no markdown fences, no prose, no example calls."""


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
        model=model, max_tokens=2000, system=_SYSTEM,
        messages=[{"role": "user", "content": ask}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return extract_code(text)


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
            lines.append(f"  - {r.id}: {r.expr}  → actual={r.actual}{margin}  [{r.status}]")
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
) -> ImproveResult:
    """Author a part and drive it to green: build errors AND failing measurements both feed back.

    The design spec's two-actor loop, for LLM-authored geometry (§2/§5): each round the LLM writes (or
    revises) the script; we build it sandboxed and measure it; a build error or a failing assertion
    becomes the feedback for the next revision. Stops on success, an unchanged failure signature
    (oscillation), or the round cap — mirroring the bracket loop's safety rails (CALI-6).

    ``author`` is injectable (tests pass a deterministic stub); it defaults to the real Claude call.
    """
    from .evaluate import DEFAULT_MACHINE, evaluate, load_references

    if author is None:
        def author(s: Spec, feedback: Optional[str], prior: Optional[str]) -> str:
            return author_script(s, feedback=feedback, prior=prior, client=client)

    params = params_from_spec(spec)
    references = load_references(spec) if spec.references else None
    machine = machine or DEFAULT_MACHINE

    feedback: Optional[str] = None
    prior: Optional[str] = None
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
