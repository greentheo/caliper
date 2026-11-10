"""CALI-103 (#95) — a mesh's R-tree is queried by one thread at a time.

libspatialindex isn't safe from two threads on one index. Before the fix, the race below, run raw, died with
SIGSEGV or SIGABRT in 3 runs of 3 (exit 139, 139, 134: the owner's app went down the same way mid-carve)."""

import os
import re
import subprocess
import sys

import pytest

import caliper

pytest.importorskip("rtree")

RACE = r'''
import sys, threading
import numpy as np
import trimesh
from caliper import spatial

mesh = trimesh.creation.icosphere(subdivisions=5)          # ~20k faces: about a carve part's size


def work(k):
    r = np.random.default_rng(k)
    for _ in range(int(sys.argv[1])):
        pts = r.uniform(-1.2, 1.2, (400, 3))
        raw = sys.argv[2] == "raw"
        if k % 2:                                             # the page's consistency check, say
            mesh.contains(pts) if raw else spatial.contains(mesh, pts)
        else:                                                 # and a study's loads check, at once
            trimesh.proximity.closest_point(mesh, pts) if raw else spatial.closest_point(mesh, pts)


ts = [threading.Thread(target=work, args=(k,)) for k in range(4)]
[t.start() for t in ts]
[t.join() for t in ts]
print("survived")
'''


def _race(tmp_path, how):
    script = tmp_path / "race.py"
    script.write_text(RACE)
    env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(caliper.__file__))}
    return subprocess.run([sys.executable, str(script), "40", how], capture_output=True, text=True, env=env, timeout=300)


def test_two_threads_on_one_mesh_dont_take_the_app_down(tmp_path):
    for run in range(2):                                      # through the lock it never crashes
        got = _race(tmp_path, "locked")
        assert got.returncode == 0 and "survived" in got.stdout, (run, got.returncode, got.stderr[-500:])


@pytest.mark.skipif(not os.environ.get("CALIPER_RACE"), reason="crashes a Python on purpose: set CALIPER_RACE=1")
def test_the_same_race_raw_does(tmp_path):
    """The check can see a crash: raw, the race dies (7 runs in 7 here, SIGSEGV or SIGABRT). Out of the default suite
    (#99 review): it leaves a crash report each time, and wouldn't fire everywhere."""
    assert any(_race(tmp_path, "raw").returncode != 0 for _ in range(3)), "the raw race survived 3 runs"


#: A mesh's spatial queries, which go through caliper.spatial and nowhere else: any access to them, so an alias
#: (q = mesh.nearest) counts, and a getattr by name.
RAW = re.compile(r"\.(nearest|ray|contains)\b|trimesh\.proximity|ProximityQuery|triangles_tree"
                 r"|getattr\([^)]*['\"](nearest|ray|contains|triangles_tree)['\"]")
#: The five .contains( calls that are shapely's (a polygon's), not a mesh's: exempt line by line, not file by file.
SHAPELY = {
    "if room.buffer(0.5).contains(Point(x, y)):",                                     # lighten
    "if box.buffer(s / 2).contains(type(box.centroid)(x, y)):",                       # lighten
    "if region.contains(cand) and all(cand.distance(p) > 4 * PIN_D_MM for p in pts):",  # printing
    "lo, hi = (mid, hi) if room.contains(placed(mid)) else (lo, mid)",                # pictures
    "if got is None or not room.contains(got):",                                      # pictures
    # a hole inside its panel's outline, both shapely polygons in the panel's plane (#66 item 4), not a mesh
    "if hole.is_empty or room.is_empty or not room.contains(hole):",                  # consistency
    "past = not Polygon(flat).buffer(HOLE_RIM_TOL_MM).contains(hole)",                # consistency
}


def offending(name: str, text: str) -> list:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        code = line.split("#")[0]
        if line.strip() in SHAPELY or re.search(r"spatial\.(contains|on_surface)\(", code):
            continue
        if RAW.search(code):
            out.append(f"{name}:{n}: {line.strip()}")
    return out


def test_no_module_queries_a_mesh_any_other_way():
    here = os.path.dirname(caliper.__file__)
    found = []
    for name in sorted(os.listdir(here)):
        if name.endswith(".py") and name != "spatial.py":
            found += offending(name, open(os.path.join(here, name)).read())
    assert not found, "\n".join(found)


@pytest.mark.parametrize("line", ["q = mesh.nearest", "d = mesh.nearest.on_surface(p)", "inside = mesh.contains(p)",
                                  "hit = mesh.ray.intersects_any(o, d)", "t = mesh.triangles_tree",
                                  "f = getattr(mesh, 'contains')", "trimesh.proximity.signed_distance(m, p)"])
def test_the_guard_sees_every_way_in(line):
    """CALI-103 (#99 review, item 2): an alias got past the old guard, and whole files were exempt."""
    assert offending("x.py", line)


def test_the_guard_lets_shapely_through_and_only_those_lines():
    assert not offending("lighten.py", "            if room.buffer(0.5).contains(Point(x, y)):")
    assert offending("construction.py", "    if mesh.contains(pts).any():")     # construction.py isn't exempt now
