"""CALI-117 (#105) — a carved step whose part doesn't close up is never offered or adopted.

Carving MIXED with its front-edge foot (#106) adopted a step whose part wasn't watertight, and with one BLAS thread
(#121's CI) so did main's carve-down test: summation order picks the step. A part that isn't watertight can't be
voxelized, so the check adopting it runs fails or reads wrong. Now each step is repaired if it can be (small holes
filled) and otherwise marked, with why; the best is the lightest that holds and closes; adopt refuses one that
doesn't, and writes nothing."""

import os

import pytest
import trimesh

from caliper import carve, load_study

from .test_mixed import MIXED
from .test_resolved import TUBE

pytest.importorskip("cadquery")


def _leaky(mesh, keep=0.6):
    """The mesh with a hole too big to fill: the first ``keep`` of its faces only."""
    return trimesh.Trimesh(mesh.vertices, mesh.faces[: int(len(mesh.faces) * keep)], process=False)


def test_a_small_hole_is_filled_and_a_big_one_isn_t():
    box = trimesh.creation.box((10, 10, 10))
    one = trimesh.Trimesh(box.vertices, box.faces[1:], process=False)
    assert not one.is_watertight and carve._closed(one).is_watertight
    assert carve._closed(_leaky(trimesh.creation.icosphere(3))) is None
    assert carve._closed(box) is box


def _carve(tmp_path, monkeypatch, src, pid, stations, **kw):
    pytest.importorskip("whittle")
    from caliper.design import DesignStore

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a part", base=str(tmp_path / pid))
    store.write_part(pid, src, intent="printed")
    return store, carve.study(store, pid, stations=stations, remove_up_to=0.4, **kw)


def test_a_step_that_doesn_t_close_up_isn_t_offered_or_adopted(tmp_path, monkeypatch):
    real, n = carve._station_mesh, []

    def leaks_once_carved(mesh):                         # every carved step leaks; as drawn doesn't
        n.append(1)
        tm = real(mesh)
        return tm if len(n) == 1 else _leaky(tm)
    monkeypatch.setattr(carve, "_station_mesh", leaks_once_carved)
    store, rec = _carve(tmp_path, monkeypatch, TUBE, "tube", 3)
    st = rec["stations"]
    assert len(st) > 1 and "closed" not in st[0]
    for x in st[1:]:
        assert x["closed"] is False and x["why"] == carve.OPEN
    assert rec["best"] == 0                              # the lightest that holds and closes: as drawn
    v = store.design.part("tube").version
    with pytest.raises(carve.NotClosed, match="step 1: its carved shape doesn't close up"):
        carve.adopt(store, rec["id"], 1)
    assert store.design.part("tube").version == v and not os.path.isdir(os.path.join(store.part_dir("tube"), "carved"))


def test_an_open_join_with_the_wood_isn_t_offered_and_is_repaired_or_refused(tmp_path, monkeypatch):
    """The other place it can open: the union of the carved print with the wood as drawn. One carve, then its
    offer and its adopt with the join forced open."""
    import copy

    real = carve._join
    kid = MIXED.replace('"lb": 200', '"lb": 60').replace("an adult", "a kid")
    store, rec = _carve(tmp_path, monkeypatch, kid, "stool", 2)
    assert rec["best"] == 1, rec["stations"]
    folder, spacing = os.path.join(carve.runs_dir(store), rec["id"]), rec["spacing_mm"]
    v = store.design.part("stool").version
    # a join that can't be closed: the study doesn't offer the step, and adopting it is refused, nothing written
    monkeypatch.setattr(carve, "_join", lambda a, b: _leaky(real(a, b)))
    steps = copy.deepcopy(rec["stations"])
    assert carve._offer(store, "stool", steps, folder, spacing) is None
    assert [x.get("closed") for x in steps if x["holds"]] == [False] * sum(x["holds"] for x in steps)
    with pytest.raises(carve.NotClosed, match="step 1: its carved shape doesn't close up"):
        carve.adopt(store, rec["id"], 1)
    assert store.design.part("stool").version == v
    # a gap a fill closes: adopted, and the part is watertight
    monkeypatch.setattr(carve, "_join", lambda a, b: (lambda m: trimesh.Trimesh(m.vertices, m.faces[1:], process=False))(
        real(a, b)))
    got = carve.adopt(store, rec["id"], 1)
    assert got["version"] == v + 1 and store.part_geometry("stool").require_mesh().is_watertight
