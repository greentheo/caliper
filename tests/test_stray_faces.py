"""CALI-118 (#126) — a stray face from the CAD's meshing isn't the part, and an open part is said, never thrown.

Theo's bar stool v7 couldn't be scored, weighed or released: its mesh was one closed body of 22,772 faces and one
face of no area, at the cone's apex on the flange. OCCT fans a cone face's triangles from its apex, and one comes out
with two corners on it: any cone that runs to its apex does it (``cq.Solid.makeCone(30, 0, 40)``). With it the mesh
wasn't closed, and every boolean on it threw "Not all meshes are volumes!"."""

import math
import os

import numpy as np
import pytest
import trimesh

from caliper import construction, load_study
from caliper.design import DesignStore
from caliper.measure import STRAY_SHARE, Geometry, clean, open_near

cq = pytest.importorskip("cadquery")


def _raw(wp):
    """The mesh as the tessellation gives it, before :func:`clean`."""
    v, f = wp.val().tessellate(0.05)
    return trimesh.Trimesh(np.array([[p.x, p.y, p.z] for p in v]), np.array(f), process=True)


@pytest.mark.parametrize("name,make", [
    ("a cone to its apex", lambda: cq.Workplane().add(cq.Solid.makeCone(30, 0, 40))),
    ("a cone on a plate", lambda: cq.Workplane().box(100, 100, 14).translate((0, 0, 7)).union(
        cq.Workplane().add(cq.Solid.makeCone(30, 0, 40, pnt=cq.Vector(0, 0, 14))))),
    ("a cone standing on its apex", lambda: cq.Workplane().box(100, 100, 14).translate((0, 0, 7)).union(
        cq.Workplane().add(cq.Solid.makeCone(0, 30, 40, pnt=cq.Vector(0, 0, 14))))),
])
def test_a_cone_s_apex_sliver_is_left_out_and_said(name, make):
    wp = make()
    raw = _raw(wp)
    assert not raw.is_watertight                                 # the mesher's sliver, as on the bar stool
    m = Geometry.from_cadquery(wp).require_mesh()
    assert m.is_watertight and m.is_volume, name
    assert m.metadata["strays"].startswith("left out 1 stray face from the CAD's meshing (at z "), m.metadata
    assert abs(m.volume) == pytest.approx(abs(wp.val().Volume()), rel=2e-3)     # it weighed nothing


def test_the_cone_alone_keeps_its_volume():
    m = Geometry.from_cadquery(cq.Workplane().add(cq.Solid.makeCone(30, 0, 40))).require_mesh()
    assert abs(m.volume) == pytest.approx(math.pi * 30 ** 2 * 40 / 3, rel=5e-3)
    assert m.metadata["strays"] == "left out 1 stray face from the CAD's meshing (at z 34.3–40.0 mm)"   # along its seam


def test_a_closed_mesh_and_one_stray_triangle_drops_the_triangle_and_keeps_its_weight():
    box = trimesh.creation.box((100, 100, 100))
    tri = trimesh.Trimesh([[200, 0, 0], [200.01, 0, 0], [200, 0.01, 0]], [[0, 1, 2]], process=False)
    assert tri.area < STRAY_SHARE * box.area
    m = clean(trimesh.util.concatenate([box, tri]))
    assert m.is_watertight and abs(m.volume) == pytest.approx(1e6)
    assert m.metadata["strays"] == "left out 1 stray face from the CAD's meshing (at z 0.0 mm)"


def test_a_real_opening_is_kept_and_said_where():
    box = trimesh.creation.box((100, 100, 100))
    top = box.face_normals[:, 2] > 0.9
    holed = trimesh.Trimesh(box.vertices, box.faces[~top], process=False)       # the lid off: a real opening
    m = clean(holed)
    assert not m.is_watertight and "strays" not in m.metadata                   # not dropped: it's the part's
    assert open_near(m) == "near z 50 mm"
    # a bigger loose open shell beside a closed body isn't the mesher's either: kept
    big = trimesh.Trimesh([[300, 0, 0], [400, 0, 0], [300, 100, 0]], [[0, 1, 2]], process=False)
    m = clean(trimesh.util.concatenate([box, big]))
    assert not m.is_watertight and "strays" not in m.metadata


# --- in a design: the weight with the apex sliver gone, and an open part said, not thrown --------------------------
CONE = '''import cadquery as cq

PARAMS = {"r": 30.0, "h": 40.0}
BUILD = {"material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().add(cq.Solid.makeCone(p["r"], 0, p["h"]))


def construction(params, build=None):
    b = {**BUILD, **(build or {})}
    return [{"name": "cone", "kind": "printed", "material": b["material"], "infill": b["infill"]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "a hand", "lb": 5, "factor": 2.0, "lo": (-3, -3, p["h"] - 2), "hi": (3, 3, p["h"])}]
'''


def _store(tmp_path, name="cone"):
    store = DesignStore.create("a printed cone", base=str(tmp_path / name))
    store.write_part("cone", CONE, intent="a printed cone")
    return store


def test_a_cone_part_is_weighed_whole_and_the_card_says_what_was_left_out(tmp_path):
    from caliper import answers, design_api

    store = _store(tmp_path)
    rep = construction.report(store, "cone")
    assert rep["mass_lb"] is not None and "unweighed" not in rep
    assert construction.balance(store)["mass_lb"] == rep["mass_lb"]
    what = answers.answers(store, design_api.design_state(store), "cone")[0]["lines"]
    assert any(ln["text"].startswith("I left out 1 stray face from the CAD's meshing") for ln in what), what


def _open(monkeypatch, store):
    box = trimesh.creation.box((60, 60, 40))
    box.apply_translation((0, 0, 20))
    lid = box.face_normals[:, 2] > 0.9
    open_box = Geometry.from_mesh(trimesh.Trimesh(box.vertices, box.faces[~lid], process=False))
    monkeypatch.setattr(type(store), "part_geometry", lambda self, pid: open_box)


def test_a_part_that_isn_t_closed_is_not_checked_said_where_never_thrown(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import scorecard
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = _store(tmp_path, "designs")
    _open(monkeypatch, store)
    rep = construction.report(store, "cone")
    assert rep["mass_lb"] is None and rep["unweighed"] == "not checked: its shape isn't closed near z 40 mm"
    with pytest.raises(ValueError, match="not checked: its shape isn't closed near z 40 mm, so it can't be voxelized"):
        load_study.prepare(store, "cone")
    card = scorecard.compute(store)                               # scored: the weight unknown, the strength said
    assert card["metrics"]["weight.total_lb"]["value"] is None
    assert "its shape isn't closed" in card["metrics"]["strength.cone.error"]["value"]
    app = TestClient(create_app())
    got = app.post(f"/api/designs/{store.design.slug}/balance", json={})
    assert got.status_code == 200 and got.json()["mass_lb"] is None
    assert app.get(f"/api/designs/{store.design.slug}").status_code == 200


def test_the_designer_is_told_why_a_cone_can_leave_a_sliver():
    import caliper

    text = open(os.path.join(os.path.dirname(caliper.__file__), "part_scripts.md")).read()
    assert "A cone that runs to its apex" in text


def test_closed_is_judged_as_it_reads_back():
    """#124 review: two cubes touching along an edge are watertight in memory (the pinch: each cube's own vertices
    at one point) and not once merged, as any STL round trip merges them: four faces on one edge. Every reader
    judges the merged form."""
    from caliper.measure import closed

    a = trimesh.creation.box((10, 10, 10))
    b = trimesh.creation.box((10, 10, 10))
    b.apply_translation((10, 10, 0))
    pinch = trimesh.util.concatenate([a, b])
    assert pinch.is_watertight and not closed(pinch)
    assert open_near(pinch) is not None
    assert closed(a)


def test_the_card_s_stray_face_line_is_in_the_design_s_units(tmp_path):
    """#144 review: the card went through ``answers._strays`` only by luck; ``meta["strays"]`` (mm) passed the suite.
    Through ``answers.part``: an inch design reads its height in inches, an mm one in mm."""
    import re

    from caliper import answers, design_api

    store = _store(tmp_path)
    got = {}
    for units in ("in", "mm"):
        store.design.display_units = units
        store.save()
        what = answers.answers(store, design_api.design_state(store), "cone")[0]["lines"]
        (got[units],) = [ln["text"] for ln in what if ln["text"].startswith("I left out 1 stray face")]
    assert re.search(r"\(at z [\d.]+ in(–[\d.]+ in)?\)", got["in"]) and " mm" not in got["in"], got["in"]
    assert re.search(r"\(at z [\d.]+ mm(–[\d.]+ mm)?\)", got["mm"]), got["mm"]
