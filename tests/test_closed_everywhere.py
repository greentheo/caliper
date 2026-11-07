"""CALI-121 (#133) — every judgment of "closed" is made as the mesh reads back (``measure.closed``).

#124 and #129 settled it: a pinch (two vertices at one point) is watertight in memory and open after any STL round
trip. ``measure.closed`` judges a merged copy; ``whittle_bridge`` and ``measure.is_watertight`` still asked trimesh
in memory. And when ``clean()`` couldn't close a built part, the build itself said nothing."""

import glob
import os
import re

import numpy as np
import pytest
import trimesh

from caliper import measure

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "caliper")
#: A raw read of trimesh's own watertight/volume, not a call of measure's helpers (``is_watertight(g)``).
RAW = re.compile(r"\.is_watertight\b(?!\()|\.is_volume\b")


def _pinch():
    """Two boxes meeting along an edge: watertight in memory, four faces on one edge once merged."""
    a = trimesh.creation.box((10, 10, 10))
    b = a.copy()
    b.apply_translation((10, 10, 0))
    return trimesh.util.concatenate([a, b])


def test_every_closed_judgment_goes_through_closed():
    """A raw read is closed() itself, or says why it isn't (``# raw:``)."""
    bad = []
    for path in glob.glob(os.path.join(SRC, "*.py")):
        for n, line in enumerate(open(path), 1):
            if RAW.search(line) and "# raw:" not in line:
                bad.append(f"{os.path.basename(path)}:{n}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_the_helpers_judge_a_pinch_open():
    pinch = _pinch()
    assert pinch.is_watertight                              # trimesh, in memory
    g = measure.Geometry.from_mesh(pinch)
    assert not measure.is_watertight(g) and not measure.is_manifold(g)
    assert measure.is_watertight(measure.Geometry.from_mesh(trimesh.creation.box((10, 10, 10))))


def test_the_whittle_bridge_refuses_a_pinch(tmp_path, monkeypatch):
    from caliper import whittle_bridge
    from caliper.design import DesignStore

    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    store.write_part("box", "import cadquery as cq\n\ndef build(params):\n    return cq.Workplane().box(10, 10, 10)\n",
                     intent="a box")
    monkeypatch.setattr(whittle_bridge, "_mesh_of", lambda stl: _pinch())
    with pytest.raises(ValueError, match="'box' isn't closed \\(near z .*\\): whittle can't voxelize or carve it"):
        whittle_bridge.plan(store, "box")


def test_the_build_says_once_when_its_part_isn_t_closed():
    from types import SimpleNamespace

    from caliper import chat

    box = trimesh.creation.box((10, 10, 10))
    lid = box.face_normals[:, 2] > 0.9
    holed = trimesh.Trimesh(box.vertices, box.faces[~lid], process=False)
    said = chat._not_closed(SimpleNamespace(geometry=measure.Geometry.from_mesh(holed)))
    assert said == ("⚠ Its shape isn't closed near z 5 mm: strength, weight and carving can't be checked until it "
                    "is.")
    assert chat._not_closed(SimpleNamespace(geometry=measure.Geometry.from_mesh(box))) == ""
    assert chat._not_closed(SimpleNamespace(geometry=None)) == ""


def test_a_face_of_no_area_goes_even_where_the_part_is_open_elsewhere():
    """#129's surviving mutant: on a closed part the stray step would drop a zero-area face anyway (it's a loose shell
    of its own). Only on a part open elsewhere is there no closed body for the stray step to keep, so only the
    zero-area step takes the sliver out, and says so, while the real opening stays, said where."""
    box = trimesh.creation.box((10, 10, 10))
    lid = box.face_normals[:, 2] > 0.9
    a, b = box.edges_unique[0]
    m = trimesh.Trimesh(box.vertices, np.vstack([box.faces[~lid], [[a, a, b]]]), process=False)
    got = measure.clean(m)
    assert len(got.faces) == len(box.faces) - lid.sum()                  # the sliver gone, the opening kept
    assert got.metadata["strays"].startswith("left out 1 stray face from the CAD's meshing")
    assert not measure.closed(got) and measure.open_near(got) == "near z 5 mm"


def _pinch_across():
    """Two boxes meeting along a level edge (at z 5 mm): a pinch with a place in z, unlike ``_pinch``'s upright one."""
    a = trimesh.creation.box((10, 10, 10))
    b = a.copy()
    b.apply_translation((10, 0, 10))
    return trimesh.util.concatenate([a, b])


def test_open_near_places_a_pinch_at_its_edge():
    """#134 review: a pinch's edge has four faces, not one, so open_near found no lone edge and named the whole part
    (z -5–15 mm). It takes every edge with other than two faces."""
    assert measure.open_near(_pinch_across()) == "near z 5 mm"


def test_the_build_reply_says_when_its_part_isn_t_closed():
    """#134 review's survivor: the reply itself carries the ⚠ line (``_compose``), not only ``_not_closed``."""
    from types import SimpleNamespace

    from caliper import chat

    res = SimpleNamespace(ok=True, rounds=1, report=None,
                          geometry=measure.Geometry.from_mesh(_pinch_across()))
    reply = chat._compose(None, "box", 2, res, None, [], [], {}, "Built")
    assert "⚠ Its shape isn't closed near z 5 mm: strength, weight and carving can't be checked until it is." in reply
    shut = SimpleNamespace(ok=True, rounds=1, report=None,
                           geometry=measure.Geometry.from_mesh(trimesh.creation.box((10, 10, 10))))
    assert "isn't closed" not in chat._compose(None, "box", 2, shut, None, [], [], {}, "Built")


def test_a_pinched_printed_part_isn_t_weighed(monkeypatch):
    """#134 review's other survivor: a pinch's is_volume is True in memory, so without closed() it was weighed."""
    from caliper import construction as C

    monkeypatch.setattr(C, "printed_solid", lambda store, pid, d=None: _pinch_across())
    (got,) = C.with_printed(None, "cone", [{"kind": "printed", "name": "cone"}], d={})
    assert got["unweighed"] == "not checked: its shape isn't closed near z 5 mm" and "volume_mm3" not in got
    monkeypatch.setattr(C, "printed_solid", lambda store, pid, d=None: trimesh.creation.box((10, 10, 10)))
    (got,) = C.with_printed(None, "cone", [{"kind": "printed", "name": "cone"}], d={})
    assert got["volume_mm3"] == pytest.approx(1000) and "unweighed" not in got
