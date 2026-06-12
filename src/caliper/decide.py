"""CALI-7 — decide: route failures by type (design spec §2/§5 step 6).

The split that keeps the LLM from hallucinating dimensions:
- **continuous** failures (mass, fit, clearance) → a numeric optimizer tunes a continuous parameter.
  The LLM never guesses a number; it sets up a search and a solver finds the value.
- **structural / topological** failures (wrong hole count, multiple bodies) → a discrete/structural
  move (here: bump a discrete parameter; in the full system, an LLM script edit).

For M0 the optimizer is a robust 1-D search (grid + the evaluator's signed margins) over a single
continuous parameter — deterministic and immune to the noise of rebuilding geometry each step. It is
injected an ``eval_fn(spec) -> Report`` so this logic is testable without the geometry kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .evaluate import Report
from .spec import Spec

EvalFn = Callable[[Spec], Report]

# Which continuous parameter to tune for a given failing assertion (M0 bracket family).
DEFAULT_TUNING: dict[str, str] = {
    "mass_budget": "wall",
    "walls_printable": "wall",
    "fits_bed": "wall",
    "cable_fits": "cable_bore",
}


@dataclass
class DecideResult:
    new_spec: Spec
    move: str
    kind: str  # "continuous" | "structural" | "llm" | "none"
    projected_report: Optional[Report] = None


def with_param(spec: Spec, name: str, value) -> Spec:
    """Return a deep copy of ``spec`` with parameter ``name`` set to ``value``."""
    s = spec.model_copy(deep=True)
    prm = s.parameters[name]
    if hasattr(prm, "init"):
        prm.init = value
    else:  # fixed
        prm.value = value
    return s


def _margin_of(report: Report, assertion_id: str) -> float:
    for r in report.results:
        if r.id == assertion_id and r.margin is not None:
            return r.margin
    return float("-inf")


def _pass_count(report: Report) -> int:
    return sum(1 for r in report.results if r.status == "pass")


def tune_continuous(
    spec: Spec, param: str, target_id: str, eval_fn: EvalFn, samples: int = 13
) -> tuple[float, Spec, Report]:
    """1-D search of a continuous parameter to satisfy ``target_id`` while keeping the rest passing.

    Scores each candidate by (all_pass, #passing assertions, target margin) and returns the best.
    Grid over [min, max] then one local refinement around the winner.
    """
    p = spec.parameters[param]
    lo, hi = float(p.min), float(p.max)

    def _best_over(values):
        best = None
        for v in values:
            s = with_param(spec, param, float(v))
            rep = eval_fn(s)
            score = (rep.all_pass, _pass_count(rep), _margin_of(rep, target_id))
            if best is None or score > best[3]:
                best = (float(v), s, rep, score)
        return best

    best = _best_over(np.linspace(lo, hi, samples))
    # local refine around the winner
    step = (hi - lo) / (samples - 1) if samples > 1 else 0.0
    if step:
        v0 = best[0]
        refine = np.linspace(max(lo, v0 - step), min(hi, v0 + step), 5)
        cand = _best_over(refine)
        if cand[3] > best[3]:
            best = cand
    return best[0], best[1], best[2]


def decide(spec: Spec, report: Report, eval_fn: EvalFn, tuning: Optional[dict] = None) -> DecideResult:
    """Pick the next move given a failing report. Continuous first, then structural, then defer to LLM."""
    tuning = tuning or DEFAULT_TUNING

    # 1) continuous route — a tunable continuous parameter governs a failing numeric assertion.
    for r in report.failures:
        param = tuning.get(r.id)
        if param and param in spec.parameters and getattr(spec.parameters[param], "type", None) == "continuous":
            value, new_spec, rep = tune_continuous(spec, param, r.id, eval_fn)
            return DecideResult(
                new_spec=new_spec,
                move=f"optimizer: {param} → {value:.3g} to satisfy {r.id}",
                kind="continuous",
                projected_report=rep,
            )

    # 2) structural route — bump a discrete parameter (M0 stand-in for an LLM structural edit).
    for r in report.failures:
        for name, prm in spec.parameters.items():
            if getattr(prm, "type", None) == "discrete":
                choices = list(prm.choices)
                try:
                    nxt = choices[(choices.index(prm.init) + 1) % len(choices)]
                except ValueError:
                    nxt = choices[0]
                if nxt != prm.init:
                    return DecideResult(
                        new_spec=with_param(spec, name, nxt),
                        move=f"structural: {name} {prm.init} → {nxt} (for {r.id})",
                        kind="structural",
                    )

    # 3) nothing automated applies — the full system hands this to the LLM script editor.
    return DecideResult(spec, move="no automated move (needs LLM script edit)", kind="llm")
