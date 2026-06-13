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

import ast
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

# Fit assertions (CALI-10) reference these probes; a failing one routes to a size parameter so the
# optimizer can shrink/grow the part until it clears the reference — no per-spec id wiring needed.
FIT_PREDICATES: tuple[str, ...] = ("interference", "min_clearance", "clearance")
# Preferred continuous parameter to vary for a fit failure (largest extent first).
FIT_PARAM_PREFERENCE: tuple[str, ...] = ("bolt_circle", "leg", "width", "wall")


def _is_band(expr: str) -> bool:
    """True if ``expr`` is a two-sided band like ``lo <= x <= hi`` (a fit target, not a one-sided bound)."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(n, ast.Compare) and len(n.ops) >= 2 for n in ast.walk(tree))


def _fit_param(spec: Spec) -> Optional[str]:
    """Pick the continuous parameter that most changes the part's footprint, for fit tuning."""
    for name in FIT_PARAM_PREFERENCE:
        prm = spec.parameters.get(name)
        if prm is not None and getattr(prm, "type", None) == "continuous":
            return name
    for name, prm in spec.parameters.items():  # any continuous param as a last resort
        if getattr(prm, "type", None) == "continuous":
            return name
    return None


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
    spec: Spec, param: str, target_id: str, eval_fn: EvalFn, samples: int = 13,
    prefer: Optional[float] = None,
) -> tuple[float, Spec, Report]:
    """1-D search of a continuous parameter to satisfy ``target_id`` while keeping the rest passing.

    Scores each candidate by (all_pass, #passing assertions, target margin) and returns the best.
    Grid over [min, max] then one local refinement around the winner.

    ``prefer`` requests a *minimal-change* (snug) solution: among feasible candidates, pick the one
    closest to ``prefer`` rather than the one with the largest margin. This is what makes a fit shrink
    *just enough* to clear a reference instead of collapsing to the smallest possible part.
    """
    p = spec.parameters[param]
    lo, hi = float(p.min), float(p.max)

    def _score(v: float, rep: Report):
        feasible = rep.all_pass
        if prefer is not None:
            # feasible → minimise distance to the preferred (original) value; infeasible → make
            # progress by maximising passing assertions and the target margin.
            proximity = -abs(v - prefer) if feasible else float("-inf")
            return (feasible, proximity, _pass_count(rep), _margin_of(rep, target_id))
        return (feasible, _pass_count(rep), _margin_of(rep, target_id))

    def _best_over(values):
        best = None
        for v in values:
            s = with_param(spec, param, float(v))
            rep = eval_fn(s)
            score = _score(float(v), rep)
            if best is None or score > best[3]:
                best = (float(v), s, rep, score)
        return best

    best = _best_over(np.linspace(lo, hi, samples))
    # progressive local refinement around the winner — each round shrinks the window, so the search
    # converges onto tight targets (a 0.2 mm fit band, CALI-19) the coarse grid alone would skip over.
    step = (hi - lo) / (samples - 1) if samples > 1 else 0.0
    for _ in range(4):
        if step <= 1e-6:
            break
        v0 = best[0]
        cand = _best_over(np.linspace(max(lo, v0 - step), min(hi, v0 + step), 5))
        if cand[3] > best[3]:
            best = cand
        step /= 4.0
    return best[0], best[1], best[2]


# ---------------------------------------------------------------------------
# CALI-19b — multi-parameter optimizer: joint tuning of N coupled continuous params
# ---------------------------------------------------------------------------
# `tune_continuous` moves one knob for one target. Assembly fits couple: one clearance depends on two
# dimensions, or two mates fight over the same wall. Tuning them one-at-a-time can stall or oscillate.
# `tune_multi` searches the joint space against a *global* objective (every assertion at once):
#   maximize (all_pass, #passing, worst signed margin, −total normalized change-from-init).
# The default engine is **coordinate descent** — deterministic and eval-frugal (geometry rebuilds are
# the expensive thing here), sweeping each param against the global score until no sweep improves. An
# optional `engine="scipy"` runs `differential_evolution` (seeded) for cheap eval_fns / offline tuning.

def _continuous_params(spec: Spec) -> list[str]:
    return [n for n, p in spec.parameters.items() if getattr(p, "type", None) == "continuous"]


def _global_score(spec: Spec, rep: Report, params: list[str], inits: dict, spans: dict):
    """Comparable tuple (bigger = better): feasibility, #passing, worst margin, then minimal change."""
    margins = [r.margin for r in rep.results if r.margin is not None]
    worst = min(margins) if margins else 0.0
    change = sum(abs(float(spec.parameters[p].init) - inits[p]) / spans[p] for p in params)
    return (rep.all_pass, _pass_count(rep), round(float(worst), 6), -round(change, 6))


def tune_multi(
    spec: Spec, params: list[str], eval_fn: EvalFn, samples: int = 7, sweeps: int = 4,
    engine: str = "coord",
) -> tuple[Spec, Report]:
    """Jointly tune ``params`` (continuous) to drive every assertion to pass, snugly. Returns (spec, report).

    Coordinate descent (default): each sweep, scan every param over a coarse grid + a window refined
    around its current value, keeping any candidate that improves the global score; stop when a whole
    sweep yields no improvement. ``engine="scipy"`` swaps in a global ``differential_evolution`` search
    (deterministic via a fixed seed) where eval is cheap.
    """
    params = [p for p in params if getattr(spec.parameters.get(p), "type", None) == "continuous"]
    if not params:
        return spec, eval_fn(spec)
    inits = {p: float(spec.parameters[p].init) for p in params}
    spans = {p: max(float(spec.parameters[p].max) - float(spec.parameters[p].min), 1e-9) for p in params}

    def score(s: Spec, rep: Report):
        return _global_score(s, rep, params, inits, spans)

    current = spec
    cur_rep = eval_fn(current)
    cur_score = score(current, cur_rep)

    if engine == "scipy":
        polished = _scipy_tune_multi(spec, params, eval_fn, inits, spans, score)
        if polished is not None and polished[2] > cur_score:
            return polished[0], polished[1]
        return current, cur_rep

    for _ in range(sweeps):
        improved = False
        for p in params:
            lo, hi = float(spec.parameters[p].min), float(spec.parameters[p].max)
            v0 = float(current.parameters[p].init)
            candidates = list(np.linspace(lo, hi, samples))
            step = (hi - lo) / (samples - 1) if samples > 1 else 0.0
            for _r in range(3):  # progressive local refinement around the current value (tight bands)
                if step <= 1e-7:
                    break
                candidates += list(np.linspace(max(lo, v0 - step), min(hi, v0 + step), 5))
                step /= 4.0
            best = (cur_score, current, cur_rep)
            for v in candidates:
                s = with_param(current, p, float(v))
                rep = eval_fn(s)
                sc = score(s, rep)
                if sc > best[0]:
                    best = (sc, s, rep)
            if best[0] > cur_score:
                cur_score, current, cur_rep = best
                improved = True
        if not improved:
            break

    # Escalate to a global search only if coordinate descent couldn't reach feasibility — coupled
    # objectives (a target that needs two knobs moved together) trap coordinate descent at a saddle the
    # per-axis sweeps can't leave. Cheap-first keeps the common (separable) case frugal on geometry builds.
    if not cur_rep.all_pass:
        polished = _scipy_tune_multi(spec, params, eval_fn, inits, spans, score)
        if polished is not None and polished[2] > cur_score:
            return polished[0], polished[1]
    return current, cur_rep


def _scipy_tune_multi(spec, params, eval_fn, inits, spans, score):
    """Global joint search via scipy ``differential_evolution`` (seeded). None if scipy is absent."""
    try:
        from scipy.optimize import differential_evolution
    except Exception:
        return None
    bounds = [(float(spec.parameters[p].min), float(spec.parameters[p].max)) for p in params]

    def _apply(x):
        s = spec
        for p, v in zip(params, x):
            s = with_param(s, p, float(v))
        return s

    def loss(x):
        s = _apply(x)
        rep = eval_fn(s)
        margins = [r.margin for r in rep.results if r.margin is not None]
        worst = float(np.clip(min(margins) if margins else 0.0, -1e3, 1e3))
        base = -(_pass_count(rep) * 1000.0 + worst)
        if rep.all_pass:  # among feasible, prefer minimal change (snug)
            base += 1e-2 * sum(abs(float(v) - inits[p]) / spans[p] for p, v in zip(params, x))
        return base

    res = differential_evolution(loss, bounds, seed=0, maxiter=20, popsize=8, tol=1e-3, polish=True)
    s = _apply(res.x)
    rep = eval_fn(s)
    return s, rep, score(s, rep)


def decide(spec: Spec, report: Report, eval_fn: EvalFn, tuning: Optional[dict] = None) -> DecideResult:
    """Pick the next move given a failing report. Continuous first, then structural, then defer to LLM."""
    tuning = tuning or DEFAULT_TUNING

    # 0) coupled-fit route (CALI-19b) — with ≥2 continuous knobs and a failing numeric check, the fits
    # may be coupled (one target needs two knobs moved together), which the 1-D path can't escape. Tune
    # the whole vector jointly. Only taken if it actually improves (more passing / all pass), else fall
    # through to the 1-D path. Single-knob specs skip this entirely (the common case stays 1-D + snug).
    continuous = _continuous_params(spec)
    numeric_fails = [r for r in report.failures if r.margin is not None]
    if len(continuous) >= 2 and len(numeric_fails) >= 1:
        new_spec, rep = tune_multi(spec, continuous, eval_fn)
        if rep.all_pass or _pass_count(rep) > _pass_count(report):
            return DecideResult(
                new_spec=new_spec,
                move=f"optimizer(multi): jointly tuned {', '.join(continuous)}",
                kind="continuous",
                projected_report=rep,
            )

    # 1) continuous route — a tunable continuous parameter governs a failing numeric assertion.
    for r in report.failures:
        param = tuning.get(r.id)
        # fit failures (interference/clearance) auto-route to a size parameter — no id wiring needed.
        is_fit = not param and any(p in r.expr for p in FIT_PREDICATES)
        if is_fit:
            param = _fit_param(spec)
        if param and param in spec.parameters and getattr(spec.parameters[param], "type", None) == "continuous":
            # a one-sided fit (min_clearance >= X) resizes minimally (snug) — stay close to the current
            # size. A two-sided fit BAND (lo <= clearance <= hi, CALI-19) instead maximises the chained
            # margin, which centres the part in the band; no `prefer` so it doesn't fight that.
            prefer = float(spec.parameters[param].init) if (is_fit and not _is_band(r.expr)) else None
            value, new_spec, rep = tune_continuous(spec, param, r.id, eval_fn, prefer=prefer)
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
