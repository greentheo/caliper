"""CALI-45 — a cut plan: panels unfolded and nested by unfold-to-sheets, sticks cut-listed."""

import os

import pytest

from caliper import cutplan
from caliper.design import DesignStore

from .test_construction import BOX


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a crate", base=str(tmp_path / "designs"))
    s.write_part("crate", BOX, intent="an open crate")
    return s


def test_panels_go_to_the_unfolder_one_group_each():
    items = [{"name": "floor", "outline": [(0, 0, 0), (10, 0, 0), (10, 5, 0), (0, 5, 0)]},
             {"name": "bent", "facets": [[(0, 0, 0), (10, 0, 0), (10, 0, 5)], [(0, 0, 0), (10, 0, 5), (0, 2, 5)]]}]
    text = cutplan.panels_obj(items, "test")
    assert [ln for ln in text.splitlines() if ln.startswith("g ")] == ["g floor", "g bent"]
    assert sum(ln.startswith("v ") for ln in text.splitlines()) == 10
    assert [ln for ln in text.splitlines() if ln.startswith("f ")] == ["f 1 2 3 4", "f 5 6 7", "f 8 9 10"]


needs_unfolder = pytest.mark.skipif(cutplan.available() is not None,
                                    reason=f"no cut plans here: {cutplan.available()}")


@needs_unfolder
def test_a_cut_plan_nests_each_material_and_lists_the_sticks(store):
    rec = cutplan.run(store, "crate")
    by = {g["material"]: g for g in rec["sheets"]}
    assert set(by) == {"plywood", "xps"}
    assert by["plywood"]["sheets"] == 1 and by["plywood"]["pieces"] == 1
    # 48x24, 48x24, 24x24, 24x24 of foam: a real nester gets them onto one 4x8 (the BOM's shelf count said 2)
    assert by["xps"]["pieces"] == 4 and by["xps"]["sheets"] >= 1 and not by["xps"]["missing"]
    assert by["xps"]["worst_edge_error"] < 1e-6                 # flat panels flatten exactly
    root = os.path.join(cutplan.runs_dir(store), rec["id"])
    for g in rec["sheets"]:
        names = {f["name"] for f in g["files"]}
        assert {"sheets/sheet-01.svg", "sheets/sheet-01.dxf", "pattern.pdf", "assembly.txt"} <= names
        assert os.path.exists(os.path.join(root, g["key"], "sheets", "sheet-01.dxf"))
    (posts,) = rec["sticks"]
    assert posts["label"] == "2x2 SPF lumber" and [round(c["length_mm"]) for c in posts["cuts"]] == [610, 610]
    assert "24.0 in" in open(os.path.join(root, "cutlist.txt")).read()
    assert cutplan.list_runs(store, "crate")[0]["id"] == rec["id"]
    assert store.history("crate")[-1]["kind"] == "cutplan"


@needs_unfolder
def test_cut_plan_files_stay_inside_the_plan(store):
    rec = cutplan.run(store, "crate")
    assert cutplan.file_path(store, rec["id"], "cutlist.txt").endswith("cutlist.txt")
    for bad in ("../../design.yaml", "/etc/passwd", "nope.txt"):
        with pytest.raises(FileNotFoundError):
            cutplan.file_path(store, rec["id"], bad)
    assert cutplan.load_run(store, "../x") is None


def test_a_part_with_nothing_to_cut_is_refused(tmp_path):
    s = DesignStore.create("plain", base=str(tmp_path / "designs"))
    s.write_part("box", "PARAMS = {'w': 1.0}\n\ndef build(params):\n    import cadquery as cq\n"
                        "    return cq.Workplane().box(1, 1, 1)\n")
    if cutplan.available() is None:
        with pytest.raises(ValueError, match="nothing to cut"):
            cutplan.run(s, "box")


def test_tubes_are_cut_to_the_faces_they_butt_and_mitred_to_lie_flat():
    import math
    two = {"outer": 50.8, "wall": 3.175}
    one = {"outer": 25.4, "wall": 1.5875}
    big = {"outer": 63.5, "wall": 3.175}
    arm_end = (-600 + 500 * math.cos(math.radians(60)), 500 * math.sin(math.radians(60)), 0)
    members = [
        {"name": "riser", "group": "riser", "a": (0, 0, -200), "b": (0, 0, 0), **big},
        {"name": "spine_0", "group": "spine", "a": (0, 0, 0), "b": (-600, 0, 0), **two},
        {"name": "spine_1", "group": "spine", "a": (-600, 0, 0), "b": (-1000, 0, 0), **two},
        {"name": "stub", "group": "spine", "a": (-600, 0, 0), "b": (-600, 0, 12.7), **two},
        {"name": "arm", "group": "x", "a": (-600, 0, 12.7), "b": (arm_end[0], arm_end[1], 12.7), **one},
    ]
    cuts = {t["name"]: t for t in cutplan.tube_cuts(members)}
    assert set(cuts) == {"riser", "spine", "arm"}                   # the stub is inside the joint, not a cut
    spine = cuts["spine"]
    assert spine["centreline_mm"] == pytest.approx(1000)
    assert spine["length_mm"] == pytest.approx(1000 - 63.5 / 2, abs=0.1)     # set back to the riser's face
    arm = cuts["arm"]
    (inner,) = [e for e in arm["ends"] if e.get("butts")]
    assert inner["butts"] == "spine" and inner["angle_deg"] == pytest.approx(60, abs=0.5)
    assert inner["miter_deg"] == pytest.approx(30, abs=0.5)
    assert arm["length_mm"] == pytest.approx(500 - 25.4 / math.sin(math.radians(60)), abs=0.5)
    # the riser is the biggest tube at its top: it carries on to close the corner over the spine
    top = next(e for e in cuts["riser"]["ends"] if e.get("carries"))
    assert top["extend_mm"] == pytest.approx(25.4) and cuts["riser"]["length_mm"] == pytest.approx(200 + 25.4, abs=0.1)


def test_every_face_is_written_facing_out():
    # a mirrored pair: the right panel is the left one with y flipped, so it comes wound the other way
    left = [(0, 100, 0), (100, 100, 0), (100, 100, 50), (0, 100, 50)]
    right = [(x, -y, z) for x, y, z in left]
    text = cutplan.panels_obj([{"name": "left", "outline": left}, {"name": "right", "outline": right}], "t",
                              centre=(50, 0, 25))
    vs = [tuple(map(float, ln.split()[1:])) for ln in text.splitlines() if ln.startswith("v ")]

    def normal(p):
        n = [0.0, 0.0, 0.0]
        for i, a in enumerate(p):
            b = p[(i + 1) % len(p)]
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        return n

    assert normal(vs[:4])[1] > 0 and normal(vs[4:])[1] < 0       # each facing away from the middle
