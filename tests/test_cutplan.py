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
