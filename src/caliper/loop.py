"""CALI-6 — the loop controller (design spec §5).

Wires the magic loop: generate → build → sense → evaluate → decide, until the spec is green or we
give up. Two safety rails (§5, §10): an **iteration cap** and **oscillation detection** (a repeated
measurement signature means we're going in circles — stop rather than flail).

The controller is injected an ``eval_fn(spec) -> Report`` (build + sense + evaluate) so it's testable
without the geometry kernel. The production wiring is :func:`make_eval_fn`, which builds the geometry
(CALI-4), measures it (CALI-2), and evaluates the assertions (CALI-3).

Each run is persisted under ``runs/<id>/`` (spec + report + STL) so iterations are diffable — "git
for parts" (§6).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from .decide import EvalFn, decide
from .evaluate import DEFAULT_MACHINE, AssertionResult, Report, evaluate
from .spec import Spec

LoopStatus = str  # "passed" | "capped" | "oscillation" | "stuck" | "build_failed"


@dataclass
class IterationRecord:
    index: int
    report: Report
    move: str = ""


@dataclass
class LoopResult:
    status: LoopStatus
    spec: Spec
    report: Report
    iterations: int
    history: list[IterationRecord] = field(default_factory=list)


def _signature(report: Report) -> tuple:
    """A coarse fingerprint of a report — repeated signature ⇒ oscillation."""
    return tuple(
        (r.id, r.status, None if r.margin is None else round(r.margin, 4)) for r in report.results
    )


def run_loop(spec: Spec, eval_fn: EvalFn, max_iter: int = 6) -> LoopResult:
    """Drive the spec to green (or give up). Returns the final spec, report, and the path taken."""
    current = spec
    seen: list[tuple] = []
    history: list[IterationRecord] = []

    for i in range(max_iter):
        report = eval_fn(current)

        # build failure surfaces as a synthetic "error" assertion (see make_eval_fn).
        if any(r.status == "error" and r.id == "build" for r in report.results):
            history.append(IterationRecord(i, report, move="build failed"))
            return LoopResult("build_failed", current, report, i + 1, history)

        if report.all_pass:
            history.append(IterationRecord(i, report, move="all pass"))
            return LoopResult("passed", current, report, i + 1, history)

        sig = _signature(report)
        if sig in seen:
            history.append(IterationRecord(i, report, move="oscillation detected"))
            return LoopResult("oscillation", current, report, i + 1, history)
        seen.append(sig)

        dec = decide(current, report, eval_fn)
        history.append(IterationRecord(i, report, move=dec.move))
        if dec.kind == "llm":  # no automated move available in M0
            return LoopResult("stuck", current, report, i + 1, history)
        current = dec.new_spec

    # cap reached — report on the final spec
    final = eval_fn(current)
    history.append(IterationRecord(max_iter, final, move="iteration cap reached"))
    status = "passed" if final.all_pass else "capped"
    return LoopResult(status, current, final, max_iter, history)


def make_eval_fn(machine=DEFAULT_MACHINE) -> EvalFn:
    """Production eval_fn: build geometry (CALI-4), then measure+evaluate (CALI-2/3).

    A build error becomes a single ``error`` assertion with id ``build`` carrying the captured
    trace, so the controller can route it (the "stack trace" feedback channel).
    """
    from . import generate  # lazy: pulls CadQuery

    def _eval(spec: Spec) -> Report:
        res = generate.build(spec)
        if not res.build_ok:
            return Report([AssertionResult("build", "kernel build", "error", None, detail=res.error)])
        return evaluate(spec, res.geometry, machine)

    return _eval


def persist_run(out_dir: str, spec: Spec, report: Report, geometry=None) -> str:
    """Write spec + report (+ STL) for one run so iterations are diffable. Returns the directory."""
    import json

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "spec.yaml"), "w") as f:
        f.write(spec.to_yaml())
    with open(os.path.join(out_dir, "report.txt"), "w") as f:
        f.write(report.to_text())
    with open(os.path.join(out_dir, "report.json"), "w") as f:  # structured, for fast reload (CALI-15)
        json.dump(report.to_dict(), f)
    if geometry is not None:
        from . import generate

        generate.export_stl(geometry, os.path.join(out_dir, "part.stl"))
    return out_dir
