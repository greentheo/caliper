"""CALI-159 (#229) — a hand plate-buckling check for a sheet carrying a load in its own plane."""

import math

import numpy as np
import pytest

from caliper import buckling

PLY = {"E": 8000.0, "across": 0.5, "key": "plywood"}            # as load_study.material() gives plywood


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


def test_both_edges_free_sways_a_quarter_of_euler():
    # #235 review: held on neither side, nothing stops its top moving either: fixed at its foot and free at its top, a
    # cantilever of twice its height, so a quarter of Euler's π² E t² / (12 a²)
    E, t, a, b = 8000.0, 19.05, 228.6, 300.0
    assert buckling.SWAY == 0.25
    assert buckling.critical_stress(E, t, a, b, 0) == pytest.approx(0.25 * math.pi ** 2 * E * t ** 2 / (12 * a ** 2), rel=1e-9)


def test_fewer_edges_held_is_never_stronger():
    for a, b in ((100, 300), (300, 300), (900, 300)):
        s = [buckling.critical_stress(8000, 6.35, a, b, h) for h in (0, 1, 2)]
        assert s[0] <= s[1] <= s[2], (a, b, s)


def test_plywood_bends_across_its_grain_at_a_tenth_of_along():
    # #235 review (the foreman's call until Theo's coupons): buckling goes by bending, and a 3-ply sheet across its face grain
    # bends at about 0.09 of along by ply theory, not the 0.5 of its strength
    assert buckling.PLY_BENDING_ACROSS == 0.1
    assert buckling.weak_E(PLY) == buckling.weak_E({"E": 8000.0, "across": 0.5}) == 800.0
    assert buckling.weak_E({"E": 8000.0, "across": 1.0, "E_across": 1600.0}) == 1600.0     # a measured one wins
    assert buckling.weak_E({"E": 2000.0}) == 2000.0                                       # the same both ways


# --- the reasons it gives for not checking a sheet --------------------------------------------------------------------------
def _flat(points, name="wall", t=6.35, holes=None):
    """A sheet as :func:`consistency.shapes` gives one (its side into +y for a wall in the xz plane)."""
    return {"name": name, "kind": "sheet", "thickness": t, "sides": [1], "polys": [np.asarray(points, float)],
            **({"holes": holes} if holes else {})}


WALL_PTS = [(0, 0, 0), (300, 0, 0), (300, 0, 600), (0, 0, 600)]
DOWN = {"force": (0.0, 0.0, -1000.0), "factor": 2.0}


def test_a_sheet_that_isn_t_a_rectangle_isn_t_checked():
    five = [(0, 0, 0), (300, 0, 0), (300, 0, 600), (150, 0, 700), (0, 0, 600)]
    (row,) = buckling.check([_flat(five)], DOWN, PLY, 2.0)
    assert not row["done"] and row["why"] == "it isn't a plain rectangle"


def test_a_load_at_a_slant_to_its_edges_isn_t_checked():
    (row,) = buckling.check([_flat(WALL_PTS)], {"force": (700.0, 0.0, -700.0), "factor": 2.0}, PLY, 2.0)
    assert not row["done"] and row["why"] == "the load runs at a slant to its edges"


def test_a_load_well_off_its_plane_isn_t_one_for_it():
    # half the load across its face is the plate check's, not a wall's: |n·f| = 0.5 |f|, past IN_PLANE (0.3)
    f = np.array([0.0, 0.5, -math.sqrt(0.75)]) * 1000
    assert buckling.check([_flat(WALL_PTS)], {"force": tuple(f), "factor": 1.0}, PLY, 2.0) == []
    f = np.array([0.0, 0.2, -math.sqrt(0.96)]) * 1000                         # a little off its plane: still a wall's
    assert len(buckling.check([_flat(WALL_PTS)], {"force": tuple(f), "factor": 1.0}, PLY, 2.0)) == 1


# --- on real parts ------------------------------------------------------------------------------------------------------------
cq = pytest.importorskip("cadquery")

from caliper import answers, consistency, lighten, load_study, verdicts  # noqa: E402
from caliper import construction as C  # noqa: E402
from caliper import verdicts as V  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

from .test_load_study import BOX_STOOL  # noqa: E402

#: One plywood sheet standing on its edge, nothing beside it, a weight on its top edge: a swaying wide column.
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
PUSH = 200 * 2.0 * load_study.LB                                           # 1779.3 N


def _pieces(store, pid):
    mesh = store.part_geometry(pid).require_mesh()
    pcs = consistency.shapes(C.declared(store, pid))
    consistency._sides(mesh, pcs)
    return pcs, consistency.tolerance(mesh)


def _part(tmp_path, name, src):
    s = DesignStore.create(name, base=str(tmp_path / name.replace(" ", "-")))
    s.write_part("p", src, intent="x")
    return s


def test_the_box_stool_s_walls_are_held_both_sides_and_its_top_isn_t_one(tmp_path):
    s = _part(tmp_path, "a box stool", BOX_STOOL)
    pcs, tol = _pieces(s, "p")
    load = {"force": (0, 0, -200 * load_study.LB), "factor": 2.0}
    rows = {r["piece"]: r for r in buckling.check(pcs, load, PLY, tol)}
    assert set(rows) == {"left", "right", "front", "back"}                 # the top carries it across its face
    assert all(r["done"] and r["edges_held"] == 2 for r in rows.values()), rows
    left = rows["left"]                                                    # 9 in tall, 10 in deep, 3/4 in
    assert (left["height_mm"], left["width_mm"], left["E_mpa"]) == (228.6, 254.0, 800.0)
    assert left["sigma_cr_mpa"] == pytest.approx(buckling.critical_stress(800.0, 19.05, 228.6, 254.0, 2), abs=1e-3)
    assert left["safety"] == pytest.approx(left["sigma_cr_mpa"] * 254.0 * 19.05 / PUSH, rel=1e-3)


def test_a_wall_with_a_hole_isn_t_checked_and_says_why(tmp_path):
    from .test_lighten import HOLE

    s = _part(tmp_path, "a box stool", BOX_STOOL + HOLE)
    pcs, tol = _pieces(s, "p")
    rows = {r["piece"]: r for r in buckling.check(pcs, {"force": (0, 0, -900.0), "factor": 2.0}, PLY, tol)}
    assert not rows["left"]["done"] and "holes" in rows["left"]["why"] and rows["right"]["done"]


#: The lone wall cut in two down the middle, the halves butted in one plane (#235 review).
HALVES = WALL.replace('''    return [{"name": "wall", "kind": "sheet", "material": "plywood", "thickness": p["t"],
             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]}]''',
                      '''    return [{"name": "left half", "kind": "sheet", "material": "plywood", "thickness": p["t"],
             "outline": [(-w / 2, 0, 0), (0, 0, 0), (0, 0, h), (-w / 2, 0, h)]},
            {"name": "right half", "kind": "sheet", "material": "plywood", "thickness": p["t"],
             "outline": [(0, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (0, 0, h)]}]''')


def test_a_butted_half_in_the_same_plane_holds_no_edge(tmp_path):
    # #235 review: each half counted the seam as held (k 0.228 -> 0.487) and read 4.3 times greener than the whole wall.
    # Butted in one plane, they fold together
    assert HALVES != WALL
    s = _part(tmp_path, "a wall in two", HALVES)
    pcs, tol = _pieces(s, "p")
    rows = buckling.check(pcs, DOWN, PLY, tol)
    assert [r["edges_held"] for r in rows] == [0, 0], rows


#: The lone wall with a 3/4 in fin standing across its left edge, on the wall's inner face, ``z`` mm up from the floor.
def _fin(z: float) -> str:
    return WALL.replace('''             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]}]''',
                        f'''             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]}},
            {{"name": "fin", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(-w / 2, p["t"], 0), (-w / 2, p["t"] + 100, 0), (-w / 2, p["t"] + 100, {z}), (-w / 2, p["t"], {z})]}}]''').replace(
        '''    return cq.Workplane().box(p["w"], p["t"], p["h"], centered=(True, False, False))''',
        f'''    fin = cq.Workplane().box(19.05, 100, {z}, centered=False).translate((-p["w"] / 2, p["t"], 0))
    return cq.Workplane().box(p["w"], p["t"], p["h"], centered=(True, False, False)).union(fin)''')


@pytest.mark.parametrize("z, held", [(600.0, 1), (200.0, 0)])
def test_an_edge_met_along_only_part_of_its_length_isn_t_held(tmp_path, z, held):
    # a fin up the whole edge holds it; one from 0 to 200 of its 600 mm meets one of the three quarter points, and held needs
    # all three, or a corner touching would hold a whole edge (#235 review, a surviving mutant)
    src = _fin(z)
    assert "fin" in src and src != WALL
    s = _part(tmp_path, f"a wall and a fin {z:g}", src)
    pcs, tol = _pieces(s, "p")
    (wall,) = [r for r in buckling.check(pcs, DOWN, PLY, tol) if r["piece"] == "wall"]
    assert wall["done"] and wall["edges_held"] == held


def _wall(tmp_path, monkeypatch, src, through):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    s = _part(tmp_path, f"a wall {through} {len(src)}", src)
    return s, load_study.study(s, "p")


def test_a_lone_thin_wall_sways_and_folds_long_before_it_crushes(tmp_path, monkeypatch):
    # a quarter of Euler, at a tenth of 8000 MPa: σ = 0.25 π² 800 6.35² / (12 × 600²) = 0.0184 MPa, × 300 × 6.35 = 35.1 N.
    # Pushed with 200 lb × 2 = 1779 N, it's 0.0197 times over, kept cut toward safe: 0.01 (#214), never rounded up to 0.02
    s, rec = _wall(tmp_path, monkeypatch, WALL, 2)
    (c,) = rec["cases"]
    (row,) = c["buckling"]
    raw = 0.25 * math.pi ** 2 * 800.0 * 6.35 ** 2 / (12 * 600.0 ** 2) * 300 * 6.35 / PUSH
    assert row["done"] and row["edges_held"] == 0 and row["p_cr_n"] == pytest.approx(35.1, abs=0.1)
    assert round(raw, 2) == 0.02 and V.cut(raw) == 0.01
    assert row["safety"] == c["safety"] == 0.01 and c["governs"] == "buckling" and not c["holds"]
    assert c["fea"]["safety"] > 100 * c["safety"]
    assert rec["unseen"] == [{"mm": 6.35, "piece": "wall"}]           # every wall it couldn't see is recorded (#248 review)
    assert verdicts.case(rec, c)["kind"] == "fails"
    # the card names the wall that folds, not where the FEA's stress peaks (#235 review)
    said = answers.fail_hedge(rec, c, verdicts.case(rec, c), False)
    assert said.startswith(" The wall folds first: it's too slender for the load running down it") and "stress" not in said


#: A 3/4 in wall 300 mm tall: it holds, and only by hand (0.25 π² 800 19.05² / (12 × 300²) × 300 × 19.05 = 3791 N, 2.13×).
STOUT = WALL.replace('PARAMS = {"t": 6.35, "w": 300.0, "h": 600.0}', 'PARAMS = {"t": 19.05, "w": 300.0, "h": 300.0}')


def test_a_buckling_check_that_holds_never_settles_an_fea_too_coarse_to_see_the_wall(tmp_path, monkeypatch):
    s, rec = _wall(tmp_path, monkeypatch, STOUT, 1)
    (c,) = rec["cases"]
    assert c["governs"] == "buckling" and c["safety"] == 2.13 and c["holds"]
    assert load_study.unresolved(rec, c)
    assert not verdicts.case(rec, c)["counts_as_pass"]


def _fea_case(**extra):
    return {"name": "a load", "lb": 100, "factor": 1.0, "safety": 5.0, "holds": True, "governs": "buckling", "over": "fea",
            "force_n": [0.0, 0.0, -444.8], "lo": [50.0, 3.0, 10.0], "hi": [60.0, 7.0, 12.0],
            "fea": {"supported": True, "safety": 5.0e7}, **extra}


def test_a_buckling_check_that_holds_never_settles_a_blind_fea():
    # the FEA saw next to no stress (#202): a holding hand number under it doesn't make it one that saw (#235 review, a mutant)
    run = {"material": {"strength": 30.0}, "min_safety": 2.0}
    assert load_study.blind(run, _fea_case())
    assert not load_study.blind(run, _fea_case(safety=1.5))            # its fail is certain: that one isn't the FEA's to see


def test_a_buckling_check_that_holds_never_settles_a_span(monkeypatch):
    # an FEA holding a span's ends fixed (CALI-153): a holding hand number under it doesn't settle it (#235 review, a mutant)
    monkeypatch.setattr(load_study, "_spans", lambda run, c: True)
    run = {"min_safety": 2.0}
    case = _fea_case(fea={"supported": True, "safety": 5.0})
    assert load_study.fixed_ends(run, case)
    assert not load_study.fixed_ends(run, {**case, "governs": "plate"})


def test_judged_through_a_hole_keeps_the_lower_buckling_number():
    # #235 review: a hand hole in the top set the case from the FEA's calibrated number, 7.14, over the wall's 0.39
    case = {"lb": 200, "factor": 2.0, "governs": "buckling", "over": "fea", "safety": 0.39,
            "buckling": [{"piece": "wall", "done": True, "safety": 0.39}, {"piece": "top", "done": False, "why": "x"}]}
    got = lighten.judged(dict(case), 7.14, 2.0)
    assert (got["governs"], got["safety"], got["holds"], got["over"]) == ("buckling", 0.39, False, "fea-calibrated")
    plain = lighten.judged({k: v for k, v in case.items() if k != "buckling"}, 7.14, 2.0)
    assert (plain["governs"], plain["safety"], "over" in plain) == ("fea-calibrated", 7.14, False)


#: The reviewer's case: the lone 1/4 in wall under a 3/4 in top, a 40 × 60 mm hand hole in the top.
TOPPED = WALL.replace('''    return cq.Workplane().box(p["w"], p["t"], p["h"], centered=(True, False, False))''',
                      '''    top = cq.Workplane().box(p["w"], 200, 19.05, centered=(True, False, False)).translate((0, -100, p["h"]))
    return cq.Workplane().box(p["w"], p["t"], p["h"], centered=(True, False, False)).union(top)''').replace(
    '''             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]}]''',
    '''             "outline": [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)]},
            {"name": "top", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(-w / 2, -100, h + 19.05), (w / 2, -100, h + 19.05), (w / 2, 100, h + 19.05), (-w / 2, 100, h + 19.05)]}]''').replace(
    '''"lo": (-w / 2, 0, h - 2), "hi": (w / 2, t, h)}]''', '''"lo": (-50, -50, h + 17), "hi": (50, 50, h + 19.05)}]''') + '''

HOLES = [{"piece": "top", "normal": [0, 0, -1], "depth": 19.05,
          "polygons": [[[100, 20, 619.05], [140, 20, 619.05], [140, 80, 619.05], [100, 80, 619.05]]]}]
'''


def test_a_hand_hole_in_the_top_never_turns_a_folding_wall_into_a_pass(tmp_path, monkeypatch):
    s, rec = _wall(tmp_path, monkeypatch, TOPPED, 2)
    (c,) = rec["cases"]
    assert any(r["piece"] == "wall" and r["done"] for r in c["buckling"])
    assert c["governs"] == "buckling" and not c["holds"] and verdicts.case(rec, c)["kind"] == "fails", (c["governs"], c["safety"])


def test_the_note_says_not_checked_only_where_a_wall_wasn_t(tmp_path):
    from .test_lighten import HOLE

    s = _part(tmp_path, "a box stool", BOX_STOOL)
    pcs, tol = _pieces(s, "p")
    loads = load_study.parse_loads(C.declared(s, "p")["loads"])
    assert load_study.buckling_notes(pcs, loads, PLY, tol) == [load_study.BUCKLING_CHECKED]
    h = _part(tmp_path, "a holed stool", BOX_STOOL + HOLE)
    pcs, tol = _pieces(h, "p")
    (note,) = load_study.buckling_notes(pcs, loads, PLY, tol)
    assert note.startswith(load_study.BUCKLING) and "the left" in note
    assert load_study.buckling_notes(pcs, loads, {"E": 2000.0, "printed": True}, tol) == [load_study.BUCKLING]


def test_the_page_names_the_buckling_check_and_the_wall():
    from .test_carve_click import _page, _run

    out = _run(_page(["foldedBy"], consts=["esc"], extra="""
const c = {governs: 'buckling', buckling: [{piece: 'top', done: false, why: 'x'}, {piece: 'left', done: true, safety: 0.39, edges_held: 0},
                                           {piece: 'right', done: true, safety: 0.5, edges_held: 2}]};
out = [foldedBy(c), foldedBy({...c, buckling: [{piece: 'back', done: true, safety: 3, edges_held: 2}]}), foldedBy({governs: 'buckling'})];"""))
    assert out == ["the buckling check on the left: a plate free along its sides, its top free to sway, its whole load on it",
                   "the buckling check on the back: a plate held along both sides, its whole load on it", "the buckling check"]
