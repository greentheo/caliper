"""CALI-103 (#95) — every spatial query on a mesh, one at a time.

trimesh answers ``contains``, ``nearest``, ``ray`` and proximity queries with an R-tree (libspatialindex, through
``rtree``), built once per mesh and kept on it. libspatialindex isn't safe to use from two threads on one index:
Caliper keeps meshes in caches (a part's geometry, a printed rest) and a study thread and a page request can query
the same one at once, which corrupted the heap and took the owner's app down (exit 134, mid-carve). So every such
query in Caliper goes through here, under one lock, held for that query only: milliseconds, never a whole study.
``tests/test_spatial.py`` fails if a module queries a mesh any other way.
"""

from __future__ import annotations

import threading

import numpy as np

#: Held for one query at a time (re-entrant, so a query that asks another inside it can't deadlock).
LOCK = threading.RLock()


def contains(mesh, points) -> np.ndarray:
    with LOCK:
        return mesh.contains(np.asarray(points, float))


def closest_point(mesh, points):
    import trimesh

    with LOCK:
        return trimesh.proximity.closest_point(mesh, np.asarray(points, float))


def signed_distance(mesh, points) -> np.ndarray:
    import trimesh

    with LOCK:
        return trimesh.proximity.signed_distance(mesh, np.asarray(points, float))


def on_surface(mesh, points):
    """The nearest point on the surface to each point: (points, distances, triangle ids)."""
    with LOCK:
        return mesh.nearest.on_surface(np.asarray(points, float))


def intersects_location(mesh, origins, directions, **kw):
    with LOCK:
        return mesh.ray.intersects_location(ray_origins=origins, ray_directions=directions, **kw)


class Proximity:
    """trimesh's ProximityQuery on one mesh, each query under the lock."""

    def __init__(self, mesh):
        import trimesh

        with LOCK:
            self._q = trimesh.proximity.ProximityQuery(mesh)

    def signed_distance(self, points) -> np.ndarray:
        with LOCK:
            return self._q.signed_distance(np.asarray(points, float))
