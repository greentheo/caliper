"""CALI-20 — the assembly model: N parts + named mates + assembly-level assertions.

This is where Caliper stops being about *one* part and becomes about *a collection of parts that
fit together* — the heart of the north star ("a 3D printer that's 10 feet tall", "insert a support
between the wheel and the XYZ assembly"). It generalizes CALI-10's two-body fit substrate
(``interference`` / ``min_clearance``) to **N posed bodies with named relationships**.

Three pieces, mirroring the single-part spec:
- :class:`Part` — a named instance, its geometry source (an STL or a prior run dir), and its
  **placement** (position + rotation) in the assembly frame.
- :class:`Mate` — a **named relationship between two parts** (no-interference / clearance / fit /
  touch). Each mate expands to one measured assertion, so "wheel and support mate at a slip fit"
  becomes ``0.12 <= min_clearance(wheel, support) <= 0.30`` — measured, not asserted by eye.
- :class:`Assembly` — the parts, the mates, and any free-form **assembly-level assertions** (e.g.
  ``max_interference() <= 0`` — no pair collides anywhere).

Evaluation reuses the single-part evaluator wholesale: the same safe AST interpreter, the same
signed-margin extraction (so a fit *band* between two parts is tunable too), the same ``Report``.
The only difference is the namespace — part ids bind to loaded :class:`~caliper.measure.Geometry`
and the fit probes take *two* parts.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

import numpy as np
import yaml
from pydantic import Field, model_validator

from . import measure, tolerance
from .measure import Geometry
from .spec import Assertion, _Base


class Part(_Base):
    """A named part instance in the assembly.

    ``source`` points at the geometry: an STL file, or a prior run directory (we load its
    ``part.stl``). ``position`` (mm) + ``rotation`` (deg, three.js ``XYZ`` intrinsic euler) place the
    part in the assembly frame — exactly the pose convention used for references (CALI-10), so the
    viewer gizmo and the measured pose agree. ``role: fixed`` marks a datum you mate *to* (an existing
    part you won't move); ``movable`` parts are the ones a future optimizer/author may adjust.
    """

    id: str
    source: str
    role: Literal["fixed", "movable"] = "movable"
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class Mate(_Base):
    """A named relationship between two parts — the assembly's edges.

    ``between`` is exactly two part ids. ``kind`` drives the measured assertion it expands to:
    - ``no_interference`` → ``interference(a, b) <= 0`` (they must not overlap).
    - ``clearance`` (``value`` mm) → ``min_clearance(a, b) >= value`` (keep at least this gap).
    - ``fit`` (``fit`` class, e.g. ``slip``) → a tunable clearance **band** (CALI-19) between them.
    - ``touch`` (``value`` = tolerance, default 0.1) → ``-tol <= min_clearance(a, b) <= tol``
      (surfaces meet, flush within tolerance — a seated/mating face).
    """

    id: str
    between: list[str]
    kind: Literal["no_interference", "clearance", "fit", "touch"] = "no_interference"
    value: Optional[float] = None
    fit: Optional[str] = None
    nominal: Optional[float] = None

    @model_validator(mode="after")
    def _check(self) -> "Mate":
        if len(self.between) != 2:
            raise ValueError(f"mate {self.id!r}: `between` needs exactly two part ids, got {self.between!r}")
        if self.between[0] == self.between[1]:
            raise ValueError(f"mate {self.id!r}: a part can't mate with itself ({self.between[0]!r})")
        return self


class Assembly(_Base):
    """N parts + named mates + assembly-level assertions — the human-confirmed multi-part contract."""

    name: str
    intent: str = ""
    parts: list[Part] = Field(default_factory=list)
    mates: list[Mate] = Field(default_factory=list)
    # YAML/JSON use ``assert`` (a reserved word); expose it as ``assertions`` (mirrors Spec).
    assertions: list[Assertion] = Field(default_factory=list, alias="assert")

    @model_validator(mode="after")
    def _check_refs(self) -> "Assembly":
        ids = {p.id for p in self.parts}
        if len(ids) != len(self.parts):
            raise ValueError("duplicate part id in assembly")
        for m in self.mates:
            for pid in m.between:
                if pid not in ids:
                    raise ValueError(f"mate {m.id!r} references unknown part {pid!r}")
        return self

    # --- (de)serialization (mirrors Spec) ----------------------------------
    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "Assembly":
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, text: str) -> "Assembly":
        return cls.from_dict(yaml.safe_load(text))

    @classmethod
    def from_json(cls, text: str) -> "Assembly":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str) -> "Assembly":
        with open(path) as f:
            text = f.read()
        if path.endswith((".yaml", ".yml")):
            return cls.from_yaml(text)
        return cls.from_json(text)


# ---------------------------------------------------------------------------
# Mates → measured assertions
# ---------------------------------------------------------------------------
def mate_assertion(mate: Mate) -> Assertion:
    """Expand one mate into the measured assertion that checks it (the same vocabulary specs use)."""
    a, b = mate.between
    if mate.kind == "no_interference":
        return Assertion(id=mate.id, expr=f"interference({a}, {b}) <= 0")
    if mate.kind == "clearance":
        v = 0.0 if mate.value is None else mate.value
        return Assertion(id=mate.id, expr=f"min_clearance({a}, {b}) >= {v}")
    if mate.kind == "fit":
        lo, hi = tolerance.fit_band(mate.fit or tolerance.DEFAULT_FIT, mate.nominal)
        return Assertion(id=mate.id, expr=f"{lo} <= min_clearance({a}, {b}) <= {hi}")
    if mate.kind == "touch":
        t = 0.1 if mate.value is None else abs(mate.value)
        return Assertion(id=mate.id, expr=f"{-t} <= min_clearance({a}, {b}) <= {t}")
    raise ValueError(f"unknown mate kind {mate.kind!r}")


def derived_assertions(asm: Assembly) -> list[Assertion]:
    """Every assertion the assembly checks: one per mate, then the free-form assembly-level ones."""
    return [mate_assertion(m) for m in asm.mates] + list(asm.assertions)


# ---------------------------------------------------------------------------
# Geometry loading
# ---------------------------------------------------------------------------
def _resolve_source(source: str, base_dir: str) -> str:
    """An STL path, a CadQuery ``build(params)`` script (``.py``), or a run dir whose ``part.stl`` we load."""
    path = source if os.path.isabs(source) else os.path.join(base_dir, source)
    if os.path.isdir(path):
        path = os.path.join(path, "part.stl")
    return path


_PART_CACHE: dict = {}   # (abspath, mtime) -> built Geometry in LOCAL frame (B-rep kept)


def _build_py_local(path: str) -> Geometry:
    """Build a CadQuery ``build(params)`` script in its LOCAL frame (cached by path + mtime).

    Runs in the sandbox (same path as the LLM author), so the part keeps its **B-rep** — exact hole/
    face probes work, which is what hole-alignment needs. Cached so a re-`assemble` (or the webapp
    fetching the same part for measurement *and* rendering) doesn't rebuild it.
    """
    from . import sandbox

    key = (os.path.abspath(path), os.path.getmtime(path))
    cached = _PART_CACHE.get(key)
    if cached is not None:
        return cached
    with open(path) as f:
        script = f.read()
    res = sandbox.run_script(script, {})
    if not res.ok:
        raise ValueError(f"failed to build part script {path}:\n{res.feedback[:400]}")
    _PART_CACHE[key] = res.geometry
    return res.geometry


def _build_py_part(path: str, position, rotation) -> Geometry:
    """Build a ``.py`` part (CALI-23) and pose it into the assembly frame.

    The pose is baked into the mesh; the solid stays in its local frame with the pose recorded on the
    Geometry, so feature probes (holes) transform their results to the assembly frame.
    """
    base = _build_py_local(path)
    T = measure.pose_matrix(position, rotation)
    if np.allclose(T, np.eye(4)):
        return Geometry(mesh=base.mesh, solid=base.solid, pose=T)
    m = base.require_mesh().copy()
    m.apply_transform(T)
    return Geometry(mesh=m, solid=base.solid, pose=T)


def load_parts(asm: Assembly, base_dir: str = ".") -> dict[str, Geometry]:
    """Load and pose every part's geometry → ``{part_id: Geometry}``.

    Each part's ``position``/``rotation`` is baked into its mesh at load, so the fit probes measure the
    parts *where they sit* in the assembly. A ``.py`` source is **built** (CALI-23, keeps the B-rep so
    hole probes work); anything else is loaded as a posed STL (run-dir → ``part.stl``).
    """
    parts: dict[str, Geometry] = {}
    for p in asm.parts:
        path = _resolve_source(p.source, base_dir)
        if path.endswith(".py"):
            parts[p.id] = _build_py_part(path, p.position, p.rotation)
        else:
            parts[p.id] = Geometry.from_stl_posed(path, p.position, p.rotation)
    return parts


# ---------------------------------------------------------------------------
# Evaluation — reuses the single-part evaluator (CALI-3)
# ---------------------------------------------------------------------------
def build_context(asm: Assembly, parts: dict[str, Geometry]) -> dict:
    """Bind the assembly namespace: each part id → its Geometry, plus N-body fit probes & helpers.

    The fit probes here take **two parts** (``interference(a, b)``, ``min_clearance(a, b)``), unlike
    the single-part context where they took one part + one reference. ``max_interference()`` /
    ``min_clearance_all()`` reduce over *every* pair so an assembly-level assertion can say "no pair
    collides" or "nothing is tighter than X" in one line.
    """
    ctx: dict[str, Any] = {
        # pairwise fit probes (the assembly edges)
        "interference": lambda a, b: measure.interference(a, b),
        "min_clearance": lambda a, b: measure.min_clearance(a, b),
        "clearance": lambda a, b: measure.min_clearance(a, b),
        # whole-assembly reductions
        "max_interference": lambda: measure.max_interference(parts),
        "min_clearance_all": lambda: measure.min_pair_clearance(parts),
        # hole alignment across parts (CALI-25) — does a screw pass through both?
        "hole_misalignment": lambda a, b: measure.min_hole_misalignment(a, b),
        "holes_aligned": lambda a, b, tol=0.5: measure.min_hole_misalignment(a, b) <= tol,
        # per-part dimensional query
        "bbox": lambda part: measure.bounding_box(part),
        # tolerant comparisons (CALI-19)
        "approx": tolerance.approx,
        "within": tolerance.within,
        "fits": tolerance.fits,
    }
    for pid, geom in parts.items():
        ctx[pid] = geom
    return ctx


def evaluate_assembly(
    asm: Assembly, base_dir: str = ".", parts: Optional[dict[str, Geometry]] = None
):
    """Build (or accept) the part geometries, then evaluate every mate + assembly assertion → Report.

    Reuses the single-part evaluator's :func:`~caliper.evaluate.evaluate_assertion` so margins,
    deferred/error handling, and the ``Report`` shape are identical to the per-part loop.
    """
    from .evaluate import Report, evaluate_assertion

    parts = parts if parts is not None else load_parts(asm, base_dir)
    ctx = build_context(asm, parts)
    return Report([evaluate_assertion(a, ctx) for a in derived_assertions(asm)])
