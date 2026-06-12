"""CALI-1.M1 — the refinement step (design spec §8, the M1 'one iteration cycle').

After a part is built and measured, the human says something loose — "make the holes 8 mm", "bigger
spacing", "thicker walls", "add a rib" — and Caliper re-derives the spec, regenerates, and re-measures.
This module turns a natural-language refinement into a mutated :class:`~caliper.spec.Spec`; the loop
controller (CALI-6) then runs it, and the optimizer (CALI-7) handles any continuous tuning. Together
that's the full one-iteration cycle.

Two paths, mirroring intake (CALI-5):
- ``offline`` — a deterministic parser for the common bracket refinements (hole size/count, bolt
  spacing, wall, cable bore, ribs). Used by ``--no-llm`` and tests, so it's reproducible.
- ``llm`` — Claude edits the spec given the instruction; falls back to offline on any failure.

Crucially, refinements change *parameters the generator reads* and re-sync the dependent assertions,
so the change flows all the way to the mesh — not just to the acceptance text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .intake import _M_CLEARANCE
from .spec import Assertion, Spec


@dataclass
class RefineResult:
    spec: Spec
    changes: list[str] = field(default_factory=list)
    source: str = "offline"

    @property
    def changed(self) -> bool:
        return bool(self.changes)


# ---------------------------------------------------------------------------
# small spec helpers
# ---------------------------------------------------------------------------
def _get(spec: Spec, name: str):
    p = spec.parameters.get(name)
    if p is None:
        return None
    return getattr(p, "init", getattr(p, "value", None))


def _set(spec: Spec, name: str, value, template: Optional[dict] = None) -> None:
    """Set parameter ``name`` to ``value``, adding it from ``template`` if missing."""
    p = spec.parameters.get(name)
    if p is None:
        if template is None:
            return
        from .spec import ContinuousParam, DiscreteParam, FixedParam

        kind = template["type"]
        data = dict(template)
        if kind == "continuous":
            data["init"] = value
            spec.parameters[name] = ContinuousParam(**data)
        elif kind == "discrete":
            data["init"] = value
            spec.parameters[name] = DiscreteParam(**data)
        else:
            data["value"] = value
            spec.parameters[name] = FixedParam(**data)
        return
    if hasattr(p, "init"):
        # clamp continuous to its declared range
        if hasattr(p, "min") and hasattr(p, "max"):
            value = max(p.min, min(p.max, value))
        p.init = value
    else:
        p.value = value


def _num(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _resync_assertions(spec: Spec) -> None:
    """Keep assertions consistent with the (possibly mutated) parameters."""
    hole_d = _get(spec, "hole_d")
    hole_count = _get(spec, "hole_count")
    for a in spec.assertions:
        if a.id == "bolt_pattern" and hole_d is not None and hole_count is not None:
            on = ""
            m = re.search(r"on=circle\([^)]*\)", a.expr)
            if m:
                on = f", {m.group(0)}"
            a.expr = f"holes_matching(diameter={hole_d}{on}, count={int(hole_count)})"
    # a cable bore implies a cable_fits assertion
    if _get(spec, "cable_bore") is not None and not any(a.id == "cable_fits" for a in spec.assertions):
        spec.assertions.append(Assertion(id="cable_fits", expr="largest_through_bore >= 8"))


# ---------------------------------------------------------------------------
# offline (deterministic) refinement
# ---------------------------------------------------------------------------
def offline_refine(spec: Spec, instruction: str) -> RefineResult:
    s = spec.model_copy(deep=True)
    text = instruction.lower()
    changes: list[str] = []

    def _record(name, before, after, unit=""):
        if before != after:
            changes.append(f"{name} {before} → {after}{unit}")

    # --- bolt spacing / overall size (authoritative when 'spacing'/'size' is named) ---
    if re.search(r"spacing|bolt ?circle|further apart|wider apart|\bsize\b|make it bigger", text):
        before = _get(s, "bolt_circle")
        n = _num(text)
        if re.search(r"bigger|larger|wider|more|increase|further", text) and n is not None:
            after = before + n
        elif n is not None:
            after = n
        elif re.search(r"bigger|larger|wider|more|increase|further", text):
            after = before + 8
        elif re.search(r"smaller|tighter|closer|less|decrease", text):
            after = before - (n or 8)
        else:
            after = before
        _set(s, "bolt_circle", after)
        _record("spacing", before, _get(s, "bolt_circle"), " mm")

    # --- hole diameter (only when 'hole' is mentioned with size, not 'spacing') ---
    elif re.search(r"\bholes?\b", text) and not re.search(r"\bholes?\b\s*(?:count|number)", text):
        before = _get(s, "hole_d") or 5.2
        mm = re.search(r"m(\d+(?:\.\d+)?)\b", text)
        n = _num(text)
        if mm:
            after = _M_CLEARANCE.get(float(mm.group(1)), float(mm.group(1)) + 0.2)
        elif n is not None and re.search(r"\bmm\b|wider|bigger|larger|diameter", text):
            after = before + n if re.search(r"bigger|larger|wider|increase", text) and n < before else n
        elif re.search(r"bigger|larger|wider", text):
            after = before + 1.5
        elif re.search(r"smaller|tighter", text):
            after = before - 1.0
        else:
            after = before
        _set(s, "hole_d", after, template={"type": "fixed", "unit": "mm"})
        _record("hole Ø", before, _get(s, "hole_d"), " mm")

    # --- hole count --- (\b avoids matching the '6' in 'M6 holes')
    cnt = re.search(r"\b(\d+)\s+holes\b", text)
    if cnt:
        before = _get(s, "hole_count")
        after = int(cnt.group(1))
        _set(s, "hole_count", after, template={"type": "fixed"})
        _record("hole count", before, after)

    # --- wall thickness / sturdiness ---
    if re.search(r"\bwall|thick|thin|sturd|strong|stiff|rigid", text):
        before = _get(s, "wall")
        if before is not None:
            n = _num(text)
            if re.search(r"\bwall", text) and n is not None and re.search(r"\bmm\b", text):
                after = n
            elif re.search(r"thicker|sturd|strong|stiff|rigid|beef", text):
                after = before + 1.0
            elif re.search(r"thinner|lighter|less", text):
                after = before - 0.6
            else:
                after = before
            _set(s, "wall", after)
            _record("wall", before, _get(s, "wall"), " mm")

    # --- cable bore ---
    if re.search(r"cable|bore|pass.?through|wire", text):
        before = _get(s, "cable_bore")
        n = _num(text)
        if n is not None:
            after = n
        elif before is None:
            after = 10.0
        elif re.search(r"bigger|larger|wider", text):
            after = before + 2.0
        elif re.search(r"smaller|tighter", text):
            after = before - 2.0
        else:
            after = before
        _set(s, "cable_bore", after,
             template={"type": "continuous", "min": 6, "max": 20, "unit": "mm"})
        _record("cable bore", before, _get(s, "cable_bore"), " mm")

    # --- ribs / stiffening ---
    if re.search(r"\brib|gusset", text):
        before = _get(s, "rib_count") or 0
        if re.search(r"remove|no rib|without|delete", text):
            after = 0
        else:
            after = min(2, int(before) + 1)
        _set(s, "rib_count", after)
        _record("rib_count", before, _get(s, "rib_count"))

    _resync_assertions(s)
    return RefineResult(spec=s, changes=changes, source="offline")


# ---------------------------------------------------------------------------
# LLM refinement (best-effort, falls back to offline)
# ---------------------------------------------------------------------------
_SYSTEM = """You are Caliper's refinement step. Given a current part spec (JSON) and a natural-language
change, return the edited spec. Only change what the instruction asks. Keep parameters and assertions
consistent (a hole-size change must update both the `hole_d` parameter and the `bolt_pattern` assertion).
Respond with JSON: {"spec": <edited-spec-with-`assert`-key>, "changes": [<short string>, ...]}."""


def llm_refine(spec: Spec, instruction: str, client=None, model: str = "claude-opus-4-8") -> RefineResult:
    import json

    if client is None:
        from anthropic import Anthropic

        client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"current spec:\n{spec.to_json()}\n\nchange: {instruction}"}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = json.loads(text)
    return RefineResult(spec=Spec.from_dict(data["spec"]), changes=list(data.get("changes", [])), source="llm")


def apply_refinement(spec: Spec, instruction: str, use_llm: bool = True, client=None) -> RefineResult:
    """Apply a natural-language refinement. Uses Claude when available, else the offline parser."""
    if use_llm:
        try:
            return llm_refine(spec, instruction, client=client)
        except Exception:
            pass
    return offline_refine(spec, instruction)
