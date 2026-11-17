"""A shape's tessellation as arrays, read straight off OCC's triangulation (#298).

CadQuery's ``Shape.tessellate`` meshes with OCC (BRepMesh, milliseconds), then copies each face's triangles out in a
Python list comprehension over ``poly.Triangles()``. That copy is the slow part: on the camper's cargo box (98 faces,
728 triangles) it took 0.265 s of a 0.278 s tessellate, 95% of every drag-study candidate. Reading the same
triangulation by index gives the same vertices and triangles, in the same order, in 0.014 s.
"""

from __future__ import annotations

import numpy as np


def triangles(shape, tolerance: float, angular: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    """``(vertices (N,3) float64, triangles (M,3) int64)``: what ``shape.tessellate(tolerance, angular)`` gives, as
    arrays, element for element. ``shape`` is a CadQuery Shape (a Workplane's value, a Solid, a Compound)."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_Orientation
    from OCP.TopLoc import TopLoc_Location

    shape.mesh(tolerance, angular)                           # OCC's mesher, as tessellate() calls it
    verts, tris, offset = [], [], 0
    for face in shape.Faces():
        loc = TopLoc_Location()
        poly = BRep_Tool.Triangulation_s(face.wrapped, loc)
        if poly is None:                                     # a face the mesher left bare: tessellate() skips it
            continue
        trsf = loc.Transformation()
        n = poly.NbNodes()
        verts.append(np.array([poly.Node(i).Transformed(trsf).Coord() for i in range(1, n + 1)],
                              dtype=np.float64).reshape(-1, 3))
        t = np.array([poly.Triangle(i).Get() for i in range(1, poly.NbTriangles() + 1)],
                     dtype=np.int64).reshape(-1, 3) - 1 + offset
        if face.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED:
            t = t[:, [0, 2, 1]]                              # wound the other way, as tessellate() does
        tris.append(t)
        offset += n
    if not verts:
        return np.zeros((0, 3), np.float64), np.zeros((0, 3), np.int64)
    return np.concatenate(verts), np.concatenate(tris)
