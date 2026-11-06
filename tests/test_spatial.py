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


def test_two_threads_on_one_mesh_dont_take_the_app_down(tmp_path):
    script = tmp_path / "race.py"
    script.write_text(RACE)
    env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(caliper.__file__))}

    def race(how):
        return subprocess.run([sys.executable, str(script), "40", how], capture_output=True, text=True, env=env,
                              timeout=300)

    # the check can see a crash: raw, the same race dies (it did 4 runs in 4 at this size, SIGSEGV or SIGABRT)
    assert any(race("raw").returncode != 0 for _ in range(3)), "the raw race survived 3 runs: the test can't see it"
    for run in range(2):                                      # and through the lock it never does
        got = race("locked")
        assert got.returncode == 0 and "survived" in got.stdout, (run, got.returncode, got.stderr[-500:])


#: A mesh's spatial queries, which go through caliper.spatial and nowhere else.
RAW = re.compile(r"\.nearest\.|\.ray\.|trimesh\.proximity\.|ProximityQuery|triangles_tree")


def test_no_module_queries_a_mesh_any_other_way():
    here = os.path.dirname(caliper.__file__)
    found = []
    for name in sorted(os.listdir(here)):
        if not name.endswith(".py") or name == "spatial.py":
            continue
        text = open(os.path.join(here, name)).read()
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("#")[0]
            if RAW.search(code):
                found.append(f"{name}:{n}: {line.strip()}")
            # .contains( is shapely's too (pictures, lightening, printing): only there, where shapely is in use
            if ".contains(" in code and "spatial.contains(" not in code and "shapely" not in text:
                found.append(f"{name}:{n}: {line.strip()}")
    assert not found, "\n".join(found)
