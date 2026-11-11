"""CALI-159 (#229) — a hand plate-buckling check for a sheet carrying a load in its own plane."""

import math

import numpy as np
import pytest

from caliper import buckling

STEEL = {"E": 200_000.0}


def test_a_square_plate_held_all_round_is_the_textbook_s_k_4():
    # Timoshenko & Gere §9.2: k = 4 for a square plate simply supported all round; σ_cr = 3.615 E (t/b)² at ν = 0.3
    assert buckling.k_factor(500, 500, 2) == pytest.approx(4.0)
    assert buckling.critical_stress(200_000, 10, 500, 500, 2) == pytest.approx(3.615 * 200_000 * (10 / 500) ** 2, rel=1e-3)
    assert buckling.critical_stress(200_000, 10, 500, 500, 2) == pytest.approx(289.2, abs=0.1)


@pytest.mark.parametrize("ratio, k", [(0.5, 6.25), (1.0, 4.0), (1.5, 4.34), (2.0, 4.0), (2.5, 4.13), (3.0, 4.0)])
def test_k_held_all_round_follows_the_textbook_s_curve(ratio, k):
    # Timoshenko & Gere eq. 9-7 and Fig. 9-3: the least over the half-waves m of (m b/a + a/(m b))²
    assert buckling.k_factor(ratio * 100, 100, 2) == pytest.approx(k, abs=0.01)


def test_one_edge_free_is_0_425_plus_b_over_a_squared():
    # Timoshenko §9.4 (loaded edges simply supported, one unloaded edge free): 0.425 + (b/a)²; a long plate tends to 0.425
    assert buckling.k_factor(200, 100, 1) == pytest.approx(0.425 + 0.25)
    assert buckling.k_factor(10_000, 100, 1) == pytest.approx(0.425, abs=1e-3)


def test_both_edges_free_is_euler_s_column():
    # nothing holds its sides: a wide column pinned at its ends, π² E I / a² over its section, so σ_cr = π² E t² / (12 a²)
    E, t, a, b = 8000.0, 19.05, 228.6, 300.0
    assert buckling.critical_stress(E, t, a, b, 0) == pytest.approx(math.pi ** 2 * E * t ** 2 / (12 * a ** 2), rel=1e-9)


def test_fewer_edges_held_is_never_stronger():
    for a, b in ((100, 300), (300, 300), (900, 300)):
        s = [buckling.critical_stress(8000, 6.35, a, b, h) for h in (0, 1, 2)]
        assert s[0] <= s[1] <= s[2], (a, b, s)


def test_plywood_is_taken_its_weaker_way():
    assert buckling.weak_E({"E": 8000.0, "across": 0.5}) == 4000.0
    assert buckling.weak_E({"E": 8000.0, "across": 1.0, "E_across": 1600.0}) == 1600.0
    assert buckling.weak_E({"E": 2000.0}) == 2000.0


# --- on real parts ------------------------------------------------------------------------------------------------------------
cq = pytest.importorskip("cadquery")

from caliper import consistency, load_study, verdicts  # noqa: E402
from caliper import construction as C  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

from .test_load_study import BOX_STOOL  # noqa: E402

#: One plywood sheet standing on its edge, nothing beside it, a weight on its top edge: a wide column.
WALL = '''import cadquery as cq

PARAMS = {"t": 6.35, "w": 300.0, "h": 600.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["w"], p["t"], p["h"], centered=(True, False, False))


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, h = p["w"], p["h"]
    return [{"name": "wall", "kind": "sheet", "material": "plywood", "thickness": p["t"],
             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, h, t = p["w"], p["h"], p["t"]
    return [{"name": "a weight on its top edge", "lb": 200, "factor": 2.0, "lo": (-w / 2, 0, h - 2), "hi": (w / 2, t, h)}]
'''


def _pieces(store, pid):
    mesh = store.part_geometry(pid).require_mesh()
    pcs = consistency.shapes(C.declared(store, pid))
    consistency._sides(mesh, pcs)
    return pcs, consistency.tolerance(mesh)


def test_the_box_stool_s_walls_are_held_both_sides_and_its_top_isn_t_one(tmp_path):
    s = DesignStore.create("a box stool", base=str(tmp_path / "d"))
    s.write_part("stool", BOX_STOOL, intent="x")
    pcs, tol = _pieces(s, "stool")
    load = {"force": (0, 0, -200 * load_study.LB), "factor": 2.0}
    rows = {r["piece"]: r for r in buckling.check(pcs, load, {"E": 8000.0, "across": 0.5}, tol)}
    assert set(rows) == {"left", "right", "front", "back"}                 # the top carries it across its face
    assert all(r["done"] and r["edges_held"] == 2 for r in rows.values()), rows
    left = rows["left"]                                                    # 9 in tall, 10 in deep, 3/4 in
    assert (left["height_mm"], left["width_mm"]) == (228.6, 254.0)
    assert left["sigma_cr_mpa"] == pytest.approx(buckling.critical_stress(4000.0, 19.05, 228.6, 254.0, 2), abs=1e-3)
    assert left["safety"] == pytest.approx(left["sigma_cr_mpa"] * 254.0 * 19.05 / (400 * load_study.LB), rel=1e-3)


def test_a_wall_with_a_hole_isn_t_checked_and_says_why(tmp_path):
    from .test_lighten import HOLE

    s = DesignStore.create("a box stool", base=str(tmp_path / "d"))
    s.write_part("stool", BOX_STOOL + HOLE, intent="x")
    pcs, tol = _pieces(s, "stool")
    rows = {r["piece"]: r for r in buckling.check(pcs, {"force": (0, 0, -900.0), "factor": 2.0}, {"E": 8000.0}, tol)}
    assert not rows["left"]["done"] and "holes" in rows["left"]["why"] and rows["right"]["done"]


def _wall(tmp_path, monkeypatch, t, through):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    s = DesignStore.create("a wall", base=str(tmp_path / f"w{t}"))
    s.write_part("wall", WALL.replace('"t": 6.35', f'"t": {t}'), intent="a sheet on its edge")
    return s, load_study.study(s, "wall")


def test_a_lone_thin_wall_folds_long_before_it_crushes(tmp_path, monkeypatch):
    # Euler for the wide column: σ = π² (8000 × 0.5) 6.35² / (12 × 600²) = 0.368 MPa, × 300 × 6.35 = 702 N; it's pushed
    # with 200 lb × 2 = 1779 N: 0.39 times over. The FEA reads it many times over, crushing.
    s, rec = _wall(tmp_path, monkeypatch, 6.35, 2)
    (c,) = rec["cases"]
    (row,) = c["buckling"]
    assert row["done"] and row["edges_held"] == 0 and row["p_cr_n"] == pytest.approx(702, abs=2)
    assert c["governs"] == "buckling" and c["safety"] == pytest.approx(0.39, abs=0.01) and not c["holds"]
    assert c["fea"]["safety"] > 10 * c["safety"]
    assert verdicts.case(rec, c)["kind"] == "fails"


def test_a_buckling_check_that_holds_never_settles_an_fea_too_coarse_to_see_the_wall(tmp_path, monkeypatch):
    # a 1/2 in wall: 4 x the 1/4 in one's stress, twice its section: 3.16 times over, under the FEA's number, which is read at
    # one voxel through: not resolved. The lower number is the case's, and its verdict stays not resolved (no ✓)
    s, rec = _wall(tmp_path, monkeypatch, 12.7, 1)
    (c,) = rec["cases"]
    assert c["governs"] == "buckling" and c["safety"] == pytest.approx(3.15, abs=0.02) and c["holds"]
    assert load_study.unresolved(rec, c)
    assert not verdicts.case(rec, c)["counts_as_pass"]


def test_the_note_says_not_checked_only_where_a_wall_wasn_t(tmp_path):
    from .test_lighten import HOLE

    s = DesignStore.create("a box stool", base=str(tmp_path / "d"))
    s.write_part("stool", BOX_STOOL, intent="x")
    pcs, tol = _pieces(s, "stool")
    loads = load_study.parse_loads(C.declared(s, "stool")["loads"])
    ply = {"E": 8000.0, "across": 0.5}
    assert load_study.buckling_notes(pcs, loads, ply, tol) == [load_study.BUCKLING_CHECKED]
    h = DesignStore.create("a box stool", base=str(tmp_path / "h"))
    h.write_part("stool", BOX_STOOL + HOLE, intent="x")
    pcs, tol = _pieces(h, "stool")
    (note,) = load_study.buckling_notes(pcs, loads, ply, tol)
    assert note.startswith(load_study.BUCKLING) and "the left" in note
    assert load_study.buckling_notes(pcs, loads, {"E": 2000.0, "printed": True}, tol) == [load_study.BUCKLING]


def test_the_page_names_the_buckling_check_and_the_wall():
    from .test_carve_click import _page, _run

    out = _run(_page(["foldedBy"], consts=["esc"], extra="""
const c = {governs: 'buckling', buckling: [{piece: 'top', done: false, why: 'x'}, {piece: 'left', done: true, safety: 0.39, edges_held: 0},
                                           {piece: 'right', done: true, safety: 0.5, edges_held: 2}]};
out = [foldedBy(c), foldedBy({...c, buckling: [{piece: 'back', done: true, safety: 3, edges_held: 2}]}), foldedBy({governs: 'buckling'})];"""))
    assert out == ["the buckling check on the left: a plate free along its sides, its whole load on it",
                   "the buckling check on the back: a plate held along both sides, its whole load on it", "the buckling check"]
