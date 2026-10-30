"""CALI-71 (#32) — lighten a sheet part where the wood isn't working, in cuts a sheet can take."""

import numpy as np
import pytest

from caliper import consistency, holes, lighten, load_study, sandbox
from caliper import construction as C
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

#: A 2 x 2 in hole through the box stool's left wall (x = 0..t), on its outline face at x = 0.
HOLE = '''

HOLES = [{"piece": "left", "normal": [1, 0, 0], "depth": 19.05,
          "polygons": [[[0, 100, 80], [0, 150.8, 80], [0, 150.8, 130.8], [0, 100, 130.8]]]}]
'''


def test_holes_are_cut_after_build_and_counted_in_their_piece():
    solid = sandbox.run_script(BOX_STOOL, timeout=120)
    holed = sandbox.run_script(BOX_STOOL + HOLE, timeout=120)
    assert holed.ok and holed.geometry.mesh.is_watertight
    gone = solid.geometry.mesh.volume - holed.geometry.mesh.volume
    assert gone == pytest.approx(50.8 * 50.8 * 19.05, rel=0.01)
    left = next(p for p in holed.declared["construction"] if p["name"] == "left")
    assert len(left["holes"]) == 1
    # the take-off: the left wall weighs its outline less the hole
    rows = {r["name"]: r for r in C.takeoff(holed.declared["construction"])}
    full = {r["name"]: r for r in C.takeoff(solid.declared["construction"])}
    assert rows["left"]["area_mm2"] == pytest.approx(full["left"]["area_mm2"] - 50.8 ** 2, rel=1e-6)
    assert rows["left"]["holes"] == 1
    # and what it says it's built from still matches what was built
    got = {r.id: r for r in consistency.check(holed.declared, holed.geometry)}
    assert got["construction_inside"].passed and got["construction_covers"].passed
    assert got["construction_volume"].actual == pytest.approx(1.0, abs=0.02)


def test_merge_leaves_other_pieces_alone():
    pieces = [{"name": "left", "kind": "sheet"}, {"name": "top", "kind": "sheet"}]
    out = holes.merge(pieces, [{"piece": "left", "polygons": [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]]}])
    assert out[0]["holes"] and "holes" not in out[1] and "holes" not in pieces[0]
    assert holes.area([[0, 0, 0], [2, 0, 0], [2, 3, 0], [0, 3, 0]]) == pytest.approx(6.0)


@pytest.fixture
def stool(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: quick, and the rules still bite
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    return store


def test_the_walls_lighten_and_the_top_stays_solid(stool):
    rec = lighten.study(stool, "stool", steps=(0.5, 1.0))
    assert sorted(p["name"] for p in rec["panels"]) == ["back", "front", "left", "right"]   # not the top
    first, *rest = rec["stations"]
    assert first["removed"] == 0 and first["holes"] == 0
    assert rest and rest[-1]["removed"] > 0.2 and rest[-1]["saved_lb"] > 0
    assert [s["removed"] for s in rec["stations"]] == sorted(s["removed"] for s in rec["stations"])
    # every hole keeps its rim: no corner nearer the panel's edge than the rim
    walls = {p["name"]: p for p in C.declared(stool, "stool")["construction"]}
    for st in rec["stations"]:
        for name, polys in st["panels"].items():
            outline = np.asarray(walls[name]["outline"], float)
            lo, hi = outline.min(axis=0), outline.max(axis=0)
            for poly in polys:
                pts = np.asarray(poly)
                flat = [i for i in range(3) if hi[i] - lo[i] > 1]
                gap = np.minimum(pts[:, flat] - lo[flat], hi[flat] - pts[:, flat]).min()
                assert gap >= lighten.RIM_MM - 1.0
    # the top is still judged by the plate check at every station
    assert all(c["governs"] in ("plate", "fea") for s in rec["stations"] for c in s["cases"])


def test_using_a_station_cuts_its_holes_into_the_part(stool):
    rec = lighten.study(stool, "stool", steps=(1.0,))
    st = rec["stations"][-1]
    assert st["holds"] and st["holes"]
    before = C.report(stool, "stool")["mass_lb"]
    got = lighten.adopt(stool, rec["id"], st["index"])
    assert got["version"] == 2 and "HOLES = [" in stool.read_script("stool")
    assert C.report(stool, "stool")["mass_lb"] < before
    run = sandbox.run_script(stool.read_script("stool"), timeout=120)
    assert run.ok and run.geometry.mesh.is_watertight
    assert all(r.passed for r in consistency.check(run.declared, run.geometry))
    # and lightening it again starts from the holes it has
    again = lighten.study(stool, "stool", steps=(1.0,))
    assert again["stations"][0]["safety"] == pytest.approx(st["safety"], rel=0.15)
