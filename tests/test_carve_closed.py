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

from .test_mixed import CENTRED, MIXED
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
    kept = carve._closed(box)                                 # judged merged, as it reads back: a closed copy
    assert kept.is_watertight and abs(kept.volume) == pytest.approx(abs(box.volume))


def _carve(tmp_path, monkeypatch, src, pid, stations, remove_up_to=0.4, **kw):
    pytest.importorskip("whittle")
    from caliper.design import DesignStore

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a part", base=str(tmp_path / pid))
    store.write_part(pid, src, intent="printed")
    return store, carve.study(store, pid, stations=stations, remove_up_to=remove_up_to, **kw)


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
    # the middle foot only, as main's MIXED was: with #106's front-edge foot the two-load carve's step 1 doesn't close
    # (#105's kind of step, rightly refused) and the whole part fails at the edge, so there's no step 1 to force open
    kid = CENTRED.replace('"lb": 200', '"lb": 60').replace("an adult", "a kid")
    store, rec = _carve(tmp_path, monkeypatch, kid, "stool", 2)
    assert rec["best"] == 1, rec["stations"]
    folder, spacing = os.path.join(carve.runs_dir(store), rec["id"]), rec["spacing_mm"]
    v = store.design.part("stool").version
    # a join that can't be closed: the study doesn't offer the step, and adopting it is refused, nothing written
    monkeypatch.setattr(carve, "_join", lambda a, b: _leaky(real(a, b)))
    steps = copy.deepcopy(rec["stations"])
    carve._judge(store, "stool", steps, folder, spacing)
    assert [x.get("closed") for x in steps if x["holds"]] == [False] * sum(x["holds"] for x in steps)
    with pytest.raises(carve.NotClosed, match="step 1: its carved shape doesn't close up"):
        carve.adopt(store, rec["id"], 1)
    assert store.design.part("stool").version == v
    # a gap a fill closes: adopted, and the part is watertight
    monkeypatch.setattr(carve, "_join", lambda a, b: (lambda m: trimesh.Trimesh(m.vertices, m.faces[1:], process=False))(
        real(a, b)))
    got = carve.adopt(store, rec["id"], 1)
    assert got["version"] == v + 1 and store.part_geometry("stool").require_mesh().is_watertight


# --- #124 review: #105's cause, a pinch -----------------------------------------------------------------------------
def test_a_pinch_reads_closed_in_memory_and_isn_t_once_read_back():
    """Two pieces meeting along an edge, each with its own vertices there: watertight in memory; merged, as any STL
    round trip does, four faces share one edge and it isn't. A fill can't mend that: refused. (Meeting at a corner
    only, every edge still has two faces: it reads back closed.)"""
    a = trimesh.creation.box((10, 10, 10))
    edge = a.copy()
    edge.apply_translation((10, 10, 0))
    pinch = trimesh.util.concatenate([a, edge])
    assert pinch.is_watertight                                # in memory
    assert carve._closed(pinch) is None                       # as it reads back
    corner = a.copy()
    corner.apply_translation((10, 10, 10))
    assert carve._closed(trimesh.util.concatenate([a, corner])) is not None


#: #105's repro: MIXED with its front-edge foot first (#106's), a kid's 40 lb.
EDGE_MIXED = MIXED.replace('''    return [{"name": "an adult stepping up"''', '''    return [{"name": "stepping on the front edge", "lb": 200, "factor": 2.0,
             "lo": (cx - 50, 0, h - 2), "hi": (cx + 50, 100, h)},
            {"name": "an adult stepping up"''').replace('"lb": 200', '"lb": 40').replace("an adult", "a kid")


@pytest.mark.slow       # a two-load carve in four steps: several minutes (#124 review: mark it)
def test_105_s_repro_the_step_offered_is_one_that_adopts(tmp_path, monkeypatch):
    assert EDGE_MIXED != MIXED and "front edge" in EDGE_MIXED
    store, rec = _carve(tmp_path, monkeypatch, EDGE_MIXED, "stool", 4, remove_up_to=0.6)
    assert all(x.get("why") == carve.OPEN for x in rec["stations"] if x.get("closed") is False)
    if rec["best"] is None:                                   # every step that held leaked: none offered, said
        assert any(x.get("closed") is False for x in rec["stations"] if x["holds"])
        return
    got = carve.adopt(store, rec["id"], rec["best"])          # offered, so it adopts: offer and adopt agree
    mesh = store.part_geometry("stool").require_mesh()
    assert got["version"] == 2 and mesh.is_watertight
