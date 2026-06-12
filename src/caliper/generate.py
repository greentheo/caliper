"""CALI-4 — the generator (bracket family).

Turns a spec into geometry (design spec §2/§5). The MVP primary strategy is an LLM-authored
parametric script; for M0 we hardcode one part family — the **corner bracket** — as a parametric
CadQuery template driven by the spec's parameters. Build errors are first-class feedback (the
"stack trace") captured in :class:`BuildResult.error` and routed back to the decide step (CALI-7).

The corner bracket is an L-shaped angle: two flanges meeting at 90°, each with bolt holes, plus
optional stiffening ribs and an optional cable bore. Geometry is built watertight from a clean
profile extrusion so the measurement layer (CALI-2) has a valid B-rep + mesh.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .measure import Geometry
from .spec import Spec


@dataclass
class BracketParams:
    """Resolved, concrete parameters for one bracket build (all in mm)."""

    leg: float = 60.0          # length of each flange from the corner
    width: float = 20.0        # depth across the bracket (2020 extrusion = 20)
    thickness: float = 4.0     # wall / flange thickness  (spec param: wall)
    hole_d: float = 5.2        # bolt hole Ø (M5 clearance)
    holes_per_leg: int = 2     # → 2 per leg = 4 holes total
    rib_count: int = 0         # 0/1/2 stiffening gussets
    cable_bore: float = 0.0    # optional pass-through Ø through the horizontal flange (0 = none)

    @classmethod
    def from_spec(cls, spec: Spec) -> "BracketParams":
        """Read known bracket parameters off a spec, falling back to defaults.

        For M0 this maps the corner-bracket family's parameter names. Unknown specs still build
        with sensible defaults so the loop always has geometry to measure.
        """
        p = cls()

        def _val(name: str):
            param = spec.parameters.get(name)
            if param is None:
                return None
            # continuous/discrete carry `init`; fixed carries `value`
            return getattr(param, "init", getattr(param, "value", None))

        if (wall := _val("wall")) is not None:
            p.thickness = float(wall)
        if (bc := _val("bolt_circle")) is not None:
            p.leg = float(bc)
        if (cb := _val("cable_bore")) is not None:
            p.cable_bore = float(cb)
        if (rc := _val("rib_count")) is not None:
            p.rib_count = int(rc)
        if (hd := _val("hole_d")) is not None:
            p.hole_d = float(hd)
        if (hc := _val("hole_count")) is not None:
            # symmetric L-bracket: split the total bolt count evenly across the two flanges
            p.holes_per_leg = max(1, round(int(hc) / 2))
        return p


@dataclass
class BuildResult:
    """Outcome of a build. ``solid``/``mesh`` are None on failure; ``error`` is the captured trace."""

    build_ok: bool
    geometry: Optional[Geometry] = None
    error: str = ""
    params: Optional[BracketParams] = None


def make_bracket(p: BracketParams) -> Any:
    """Construct the corner bracket as a CadQuery Workplane. CadQuery imported lazily."""
    import cadquery as cq

    leg, w, t = p.leg, p.width, p.thickness
    # L-shaped profile in the XZ plane, extruded along Y by the width.
    # Corner at origin; horizontal flange runs +X, vertical flange runs +Z.
    profile_pts = [
        (0, 0), (leg, 0), (leg, t), (t, t), (t, leg), (0, leg),
    ]
    body = cq.Workplane("XZ").polyline(profile_pts).close().extrude(w)
    # The "XZ" plane normal is (0,-1,0), so extrude direction/sign is kernel-defined. Recentre on Y
    # from the actual bounds so the bracket is symmetric about y=0 and centred bolt holes land true.
    bb = body.val().BoundingBox()
    body = body.translate((0, -(bb.ymin + bb.ymax) / 2.0, 0))

    # --- bolt holes -------------------------------------------------------
    # Evenly distribute holes along the usable length of each flange (from the corner to the end).
    def _positions(n: int) -> list[float]:
        return [t + (leg - t) * (i + 0.5) / n for i in range(n)]

    r = p.hole_d / 2.0
    over = t  # cut length margin to guarantee a clean through-hole

    # Horizontal flange: flat slab z∈[0,t], drilled along Z at x positions, centred in Y.
    for x in _positions(p.holes_per_leg):
        cutter = (
            cq.Workplane("XY")
            .workplane(offset=-over)
            .center(x, 0)
            .circle(r)
            .extrude(t + 2 * over)
        )
        body = body.cut(cutter)

    # Vertical flange: slab x∈[0,t], drilled along X at z positions, centred in Y.
    for z in _positions(p.holes_per_leg):
        cutter = (
            cq.Workplane("YZ")
            .workplane(offset=-over)
            .center(0, z)               # YZ workplane: local (y, z)
            .circle(r)
            .extrude(t + 2 * over)
        )
        body = body.cut(cutter)

    # --- optional cable bore through the horizontal flange near the corner ---
    if p.cable_bore and p.cable_bore > 0:
        cb_r = p.cable_bore / 2.0
        x_bore = t + max(cb_r + 1.0, (leg - t) * 0.5)
        cutter = (
            cq.Workplane("XY").workplane(offset=-over)
            .center(x_bore, 0).circle(cb_r).extrude(t + 2 * over)
        )
        body = body.cut(cutter)

    # --- optional stiffening ribs in the inner corner ---------------------
    if p.rib_count and p.rib_count > 0:
        rib_size = min(leg - t, 3 * t)
        rib_th = t
        ys = _rib_y_positions(p.rib_count, w, rib_th)
        for y0 in ys:
            rib = (
                cq.Workplane("XZ")
                .polyline([(t, t), (t + rib_size, t), (t, t + rib_size)]).close()
                .extrude(rib_th)
                .translate((0, y0, 0))
            )
            body = body.union(rib)

    return body


def _rib_y_positions(n: int, width: float, rib_th: float) -> list[float]:
    if n == 1:
        return [-rib_th / 2.0]
    # spread ribs across the width, inset from the edges
    inset = width * 0.2
    span = width - 2 * inset
    return [(-width / 2 + inset + span * i / (n - 1)) - rib_th / 2 for i in range(n)]


def build(spec: Spec) -> BuildResult:
    """Spec → geometry. Captures kernel build errors as structured feedback."""
    params = BracketParams.from_spec(spec)
    try:
        wp = make_bracket(params)
        geom = Geometry.from_cadquery(wp)
        # touch the mesh so tessellation errors surface here, not later in sensing.
        geom.require_mesh()
        return BuildResult(build_ok=True, geometry=geom, params=params)
    except Exception as e:  # noqa: BLE001 — build errors are first-class feedback
        import traceback

        return BuildResult(
            build_ok=False,
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            params=params,
        )


def export_stl(geom: Geometry, path: str) -> str:
    """Write the geometry to an STL file and return the path."""
    geom.require_mesh().export(path)
    return path
