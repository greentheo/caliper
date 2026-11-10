"""CALI-109 (#177 review) — what a part script uses to act on a picked edge.

``NearestToPointSelector`` measures to an edge's centre of mass, and a ring's is on its axis, so concentric rings tie: on
the bar stool 138 of 371 edges were tied or returned another edge, and the outer rim returned the concave ring, #107's bug
again. :func:`edge_at` measures true distance to the edge from a point on it. It's in every script's namespace.
"""

from __future__ import annotations

#: how far from the point an edge may be and still be the one meant, mm: a point on it, to the rounding it's written to
ON_THE_EDGE = 0.5


def edge_at(solid, point):
    """The one edge of ``solid`` (a Workplane or a Shape) that ``point`` lies on, by true distance. A Workplane comes back
    with that edge selected, so ``edge_at(result, (x, y, z)).fillet(r)`` works. Raises if no edge is there."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex  # type: ignore
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape  # type: ignore
    from OCP.gp import gp_Pnt  # type: ignore

    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*(float(c) for c in point))).Vertex()
    is_workplane = hasattr(solid, "newObject")
    shapes = solid.vals() if is_workplane else [solid]
    edges = [e for shape in shapes for e in shape.Edges()]
    best = min(edges, key=lambda e: BRepExtrema_DistShapeShape(e.wrapped, vertex).Value(), default=None)
    gap = BRepExtrema_DistShapeShape(best.wrapped, vertex).Value() if best is not None else None
    if gap is None or gap > ON_THE_EDGE:
        raise ValueError(f"no edge at {tuple(point)}: the nearest is {gap if gap is None else round(gap, 2)} mm away")
    return solid.newObject([best]) if is_workplane else best
