"""CALI-21 — insert-into-assembly: author a new part that mates to two named interfaces.

The headline interaction of the north star: *"insert a support between the wheel and the XYZ
assembly."* Everything the assembly spine built converges here:

- **CALI-20 (assembly)** gives the existing parts, posed in world coordinates, and their geometry.
- **CALI-19 (fits)** turns "mate it snugly" into a measured clearance **band** against each interface.
- **CALI-16/17/22 (author loop)** writes a CadQuery part — *in assembly coordinates* — and revises it
  until those bands (and no-collision with the rest) are **measured** to pass.

The flow: pick two interface parts + a fit class → build a spec whose **references are the posed
existing parts** and whose assertions are the two fit bands + no-interference with everything else →
hand the author loop a richly-described intent (the interface bounding boxes, the gap, the facing
faces, in world coords) → it authors and self-corrects the bridging part → on success the new part is
added back to the assembly (as a new run-dir source + two `fit` mates) and the assembly is re-measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import assembly as _asm
from . import measure, tolerance
from .assembly import Assembly, Mate, Part
from .spec import Assertion, Reference, Spec


@dataclass
class Interface:
    """One existing part the new part must mate to: its id and posed bounding box."""

    id: str
    bbox: Any  # SimpleNamespace from measure.bounding_box (.dx/.dy/.dz/.min/.max)


@dataclass
class Bridge:
    """How two interfaces face each other: the separation axis, the gap, and the two facing faces."""

    axis: int                 # 0/1/2 → x/y/z
    gap: float                # mm between the nearest faces (negative if the bboxes already overlap)
    face_a: float             # coordinate of interface-a's face toward b (along `axis`)
    face_b: float             # coordinate of interface-b's face toward a (along `axis`)

    @property
    def axis_name(self) -> str:
        return "xyz"[self.axis]


def _bridge(a_bb, b_bb) -> Bridge:
    """Pick the axis along which the two parts are most separated — the direction to bridge."""
    best: Optional[Bridge] = None
    for ax in range(3):
        gap_pos = b_bb.min[ax] - a_bb.max[ax]   # b sits on the + side of a
        gap_neg = a_bb.min[ax] - b_bb.max[ax]   # a sits on the + side of b
        if gap_pos >= gap_neg:
            cand = Bridge(ax, float(gap_pos), float(a_bb.max[ax]), float(b_bb.min[ax]))
        else:
            cand = Bridge(ax, float(gap_neg), float(a_bb.min[ax]), float(b_bb.max[ax]))
        if best is None or cand.gap > best.gap:
            best = cand
    return best  # type: ignore[return-value]


def _fmt3(v) -> str:
    return "[" + ", ".join(f"{float(x):.2f}" for x in v) + "]"


def _interface_line(iface: Interface) -> str:
    bb = iface.bbox
    return (f"  - {iface.id}: bbox min={_fmt3(bb.min)} max={_fmt3(bb.max)} "
            f"(size {bb.dx:.1f}×{bb.dy:.1f}×{bb.dz:.1f} mm)")


def build_insert_intent(
    new_intent: str, between: list[str], ifaces: dict[str, Interface], bridge: Bridge,
    fit: str, others: list[Interface],
) -> str:
    """The enriched intent handed to the author loop: where to build, what to mate, in world coords."""
    a, b = between
    lo, hi = tolerance.fit_band(fit)
    target = (lo + hi) / 2.0
    lines = [
        f"Insert {new_intent} into an existing assembly, modeled in ASSEMBLY / WORLD coordinates (mm). "
        f"It must bridge and mate to these two existing parts at a {fit} fit "
        f"(a small clearance of about {target:.2f} mm — close but NOT overlapping):",
        _interface_line(ifaces[a]),
        _interface_line(ifaces[b]),
        "",
        f"Their facing surfaces are {bridge.gap:.1f} mm apart along the {bridge.axis_name}-axis: "
        f"{a}'s face is at {bridge.axis_name}={bridge.face_a:.2f} and {b}'s at "
        f"{bridge.axis_name}={bridge.face_b:.2f}. Build the new part positioned in WORLD coordinates so "
        f"it spans that gap and its two ends come within ~{target:.2f} mm of those facing surfaces "
        f"(leave the clearance — do not intersect either part). Overlap the interfaces in the other two "
        f"axes so the parts actually meet.",
    ]
    if others:
        lines += ["", "Do not collide with the other parts in the assembly:"]
        lines += [_interface_line(o) for o in others]
    lines += [
        "",
        "Return ONE watertight solid placed at its TRUE world position (use .translate(...) or workplane "
        "offsets — do NOT center it at the origin). Keep it simple (a bar/plate/block is fine).",
    ]
    return "\n".join(lines)


def insert_spec(
    asm: Assembly, between: list[str], fit: str = "slip", new_intent: str = "a connecting part",
    new_id: str = "insert", parts: Optional[dict] = None, base_dir: str = ".",
) -> tuple[Spec, Bridge]:
    """Build the spec the author loop drives: posed references + fit bands + no-collision + watertight.

    References are the **existing parts, posed** (so ``min_clearance(part_id)`` is measured against the
    real geometry where it sits). The two ``between`` parts get a fit **band**; every other part gets a
    no-interference guard. Returns the spec and the computed :class:`Bridge` (for display).
    """
    if len(between) != 2:
        raise ValueError(f"insert needs exactly two interface parts, got {between!r}")
    ids = {p.id for p in asm.parts}
    for pid in between:
        if pid not in ids:
            raise ValueError(f"insert interface {pid!r} is not a part of assembly {asm.name!r}")
    if new_id in ids:
        raise ValueError(f"insert id {new_id!r} collides with an existing part")

    parts = parts if parts is not None else _asm.load_parts(asm, base_dir)
    ifaces = {p.id: Interface(p.id, measure.bounding_box(parts[p.id])) for p in asm.parts}
    a, b = between
    bridge = _bridge(ifaces[a].bbox, ifaces[b].bbox)
    others = [ifaces[p.id] for p in asm.parts if p.id not in between]

    lo, hi = tolerance.fit_band(fit)
    references = [
        Reference(id=p.id, file=_asm._resolve_source(p.source, base_dir),
                  position=list(p.position), rotation=list(p.rotation))
        for p in asm.parts
    ]
    assertions = [
        Assertion(id=f"mate_{a}", expr=f"{lo} <= min_clearance({a}) <= {hi}"),
        Assertion(id=f"mate_{b}", expr=f"{lo} <= min_clearance({b}) <= {hi}"),
    ]
    assertions += [Assertion(id=f"clear_{o.id}", expr=f"interference({o.id}) <= 0") for o in others]
    assertions.append(Assertion(id="one_body", expr="body_count == 1 and is_watertight"))

    spec = Spec(
        part=new_id,
        intent=build_insert_intent(new_intent, between, ifaces, bridge, fit, others),
        references=references,
        assertions=assertions,
    )
    return spec, bridge


def add_part_to_assembly(
    asm: Assembly, new_id: str, source: str, between: list[str], fit: str = "slip",
) -> Assembly:
    """Return a copy of ``asm`` with the authored part added (identity placement) + a fit mate to each side.

    The authored part is already built in world coordinates, so its placement is the origin; ``source``
    points at its run dir / STL. Two ``fit`` mates record the relationships the author satisfied.
    """
    data = asm.to_dict()
    new = Assembly.from_dict(data)
    new.parts.append(Part(id=new_id, source=source, position=[0.0, 0.0, 0.0]))
    for iid in between:
        new.mates.append(Mate(id=f"{new_id}_{iid}", between=[new_id, iid], kind="fit", fit=fit))
    # re-validate (part-ref + dup-id checks) by round-tripping through the model
    return Assembly.from_dict(new.to_dict())


@dataclass
class InsertResult:
    ok: bool
    new_id: str
    spec: Optional[Spec] = None           # the insert spec (references + fit bands) — for persistence
    geometry: Any = None
    script: str = ""
    report: Any = None
    bridge: Optional[Bridge] = None
    rounds: int = 0
    assembly: Optional[Assembly] = None   # the assembly with the new part added (on success)
    error: str = ""
    history: list = field(default_factory=list)


def insert_part(
    asm: Assembly, between: list[str], fit: str = "slip", new_intent: str = "a connecting part",
    new_id: str = "insert", author=None, max_rounds: int = 6, base_dir: str = ".",
) -> InsertResult:
    """Author a part that mates to the two named interfaces at ``fit``, verified by measurement.

    Runs the author loop (:func:`caliper.authoring.improve`) on the insert spec; ``author`` is
    injectable for tests. On success the new part is added back to ``asm`` (placement at origin, two
    fit mates) and returned in :attr:`InsertResult.assembly` — ready to ``assemble`` or ``insert`` again.
    """
    from .authoring import improve

    spec, bridge = insert_spec(asm, between, fit=fit, new_intent=new_intent, new_id=new_id,
                               base_dir=base_dir)
    res = improve(spec, author=author, max_rounds=max_rounds, ref_base=base_dir)
    return InsertResult(ok=bool(res.ok), new_id=new_id, spec=spec, geometry=res.geometry,
                        script=res.script, report=res.report, bridge=bridge, rounds=res.rounds,
                        error=res.error, history=res.history)
