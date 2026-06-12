"""CALI-10 — fit helpers shared by the CLI (`caliper fit`) and the webapp (`/api/fit`).

A *fit* attaches an imported STL as a `role: fixed` reference (posed in the part's frame), adds
the fit assertions (`interference` / `min_clearance`), and frees a size parameter so the optimizer
can resize the part to clear the reference. Keeping this in one place means the CLI and the webapp
build identical specs.
"""

from __future__ import annotations

from typing import Optional

from .spec import Assertion, ContinuousParam, Reference, Spec

# Preferred continuous parameter to vary for a fit (largest footprint first); mirrors decide's.
FIT_PARAM_PREFERENCE: tuple[str, ...] = ("bolt_circle", "leg", "width", "wall")


def pick_free_param(spec: Spec) -> Optional[str]:
    """Pick the parameter the optimizer should resize to fit (a size dimension if there is one)."""
    for name in FIT_PARAM_PREFERENCE:
        if name in spec.parameters:
            return name
    return next(iter(spec.parameters), None)


def ensure_tunable(spec: Spec, name: Optional[str]) -> Optional[str]:
    """Make ``name`` continuous so the optimizer can resize the part to fit.

    A fit needs a free dimension; intake often locks the bracket size as ``fixed``. Promote it to a
    continuous range around its current value (shrink to clear, room to grow). No-op if already
    continuous or absent.
    """
    if not name or name not in spec.parameters:
        return name if name in spec.parameters else None
    prm = spec.parameters[name]
    if getattr(prm, "type", None) == "continuous":
        return name
    v = float(getattr(prm, "init", getattr(prm, "value", 60.0)) or 60.0)
    spec.parameters[name] = ContinuousParam(
        min=max(8.0, round(v * 0.3, 1)), max=round(v * 1.5, 1), init=v,
        unit=getattr(prm, "unit", None) or "mm",
    )
    return name


def attach_reference(
    spec: Spec,
    ref_id: str,
    file: str,
    position=None,
    rotation=None,
    min_clearance: Optional[float] = None,
    no_overlap: bool = True,
    fit: Optional[str] = None,
    nominal: Optional[float] = None,
) -> None:
    """Add (or replace) a posed reference and its fit assertion(s) on ``spec`` in place.

    Constraint precedence: ``fit`` (a class like ``slip``/``press`` → a tunable clearance **band**,
    CALI-19) wins; else ``min_clearance`` adds ``min_clearance(ref) >= MM``; else/also ``no_overlap``
    adds ``interference(ref) <= 0``. Re-fitting the same id replaces its prior reference + assertions.
    """
    spec.references = [r for r in spec.references if r.id != ref_id]
    spec.references.append(Reference(
        id=ref_id, file=file,
        position=[float(x) for x in (position or [0.0, 0.0, 0.0])],
        rotation=[float(x) for x in (rotation or [0.0, 0.0, 0.0])],
    ))
    spec.assertions = [a for a in spec.assertions if not a.id.startswith(f"{ref_id}_")]
    if fit:
        from .tolerance import fit_band

        lo, hi = fit_band(fit, nominal)
        spec.assertions.append(Assertion(
            id=f"{ref_id}_fit", expr=f"{lo} <= min_clearance({ref_id}) <= {hi}"))
        return
    if no_overlap:
        spec.assertions.append(Assertion(id=f"{ref_id}_no_interference", expr=f"interference({ref_id}) <= 0"))
    if min_clearance is not None:
        spec.assertions.append(
            Assertion(id=f"{ref_id}_clearance", expr=f"min_clearance({ref_id}) >= {min_clearance}")
        )
