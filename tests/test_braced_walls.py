"""CALI-170 (#264) — a wall braced at its top doesn't sway, and walls in line share the load.

Theo's step-stool-5 v2 read "doesn't hold, 0.69×", governed by the hand buckling check on its two sides: each was taken as a
swaying cantilever (a quarter of Euler) carrying the whole 2,224 N. The step rests across both sides' tops, so their tops can't
move sideways: pinned at both ends, full Euler. And the two sides share the one step's load, by the lever rule from where it's
applied. By hand that's about 5.6×. A synthetic stool with the issue's numbers stands in for Theo's (his script stays his)."""

import math

import pytest

from caliper import buckling, load_study

from .test_buckling import HALVES, PLY, TOPPED, WALL, _part, _pieces

pytest.importorskip("cadquery")

#: Two 3/4 in plywood sides 491.6 mm tall and 330.2 mm wide, 400 mm apart, under a step resting across both their tops.
TWO_SIDES = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 400.0, "d": 330.2, "h": 491.6, "x": 200.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    side = lambda x0: cq.Workplane().box(t, d, h, centered=False).translate((x0, 0, 0))
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side(0).union(side(w - t)).union(step)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)]},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, d, h, x = p["t"], p["d"], p["h"], p["x"]
    return [{"name": "standing on the step", "lb": 250, "factor": 2.0,
             "lo": (x - 50, d / 2 - 50, h + t - 2), "hi": (x + 50, d / 2 + 50, h + t)}]
'''
E = 8000.0 * buckling.PLY_BENDING_ACROSS                      # 800 MPa: the weaker way, #42's to change, not this issue's


@pytest.fixture(scope="module")
def stool(tmp_path_factory):
    s = _part(tmp_path_factory.mktemp("two"), "two sides and a step", TWO_SIDES)
    pcs, tol = _pieces(s, "p")
    return s, pcs, tol


def _rows(stool, x=200.0):
    s, pcs, tol = stool
    load = {**load_study.parse_loads([{"name": "a foot", "lb": 250, "factor": 2.0,
                                       "lo": (x - 50, 115.1, 508.6), "hi": (x + 50, 215.1, 510.65)}])[0]}
    return {r["piece"]: r for r in buckling.check(pcs, load, PLY, tol)}


def test_two_sides_under_one_step_are_braced_at_their_tops_and_share_its_load(stool):
    rows = _rows(stool)
    push = 250 * 2.0 * load_study.LB                                       # 2,224 N, the issue's
    euler = math.pi ** 2 * E * 19.05 ** 2 / (12 * 491.6 ** 2) * 330.2 * 19.05   # pinned at both ends: about 6.2 kN
    for name in ("left side", "right side"):
        r = rows[name]
        assert r["done"] and r["edges_held"] == 0 and r["braced_by"] == "step", r
        assert r["share"] == pytest.approx(0.5) and r["load_n"] == pytest.approx(push / 2, rel=1e-3)
        assert r["p_cr_n"] == pytest.approx(euler, rel=1e-3)
        assert r["safety"] == pytest.approx(5.6, abs=0.05)                  # the issue's by-hand figure; it read 0.69


@pytest.mark.parametrize("x, left", [(100.0, 0.75), (300.0, 0.25), (200.0, 0.5)])
def test_the_load_is_shared_by_the_lever_rule_from_where_it_s_applied(stool, x, left):
    rows = _rows(stool, x)
    span = 400.0 - 19.05                                                   # between the sides' mid-planes, where they bear
    want = (400.0 - 19.05 / 2 - x) / span
    assert rows["left side"]["share"] == pytest.approx(want, abs=1e-3) and rows["right side"]["share"] == pytest.approx(1 - want, abs=1e-3)
    assert want == pytest.approx(left, abs=0.02)


def test_a_load_with_no_place_goes_whole_on_each_wall_as_before(stool):
    s, pcs, tol = stool
    rows = {r["piece"]: r for r in buckling.check(pcs, {"force": (0, 0, -1000.0), "factor": 2.0}, PLY, tol)}
    assert all(rows[n]["share"] == 1.0 and rows[n]["load_n"] == 2000.0 for n in ("left side", "right side"))


def test_a_lone_wall_under_a_top_still_sways(tmp_path):
    """#235's reviewer's case: a top resting on one lone wall moves with it, so it braces nothing: still a quarter of Euler."""
    s = _part(tmp_path, "a topped wall", TOPPED)
    pcs, tol = _pieces(s, "p")
    (wall,) = [r for r in buckling.check(pcs, {"force": (0, 0, -1000.0), "factor": 2.0}, PLY, tol) if r["piece"] == "wall"]
    sway = buckling.SWAY * math.pi ** 2 * E * 6.35 ** 2 / (12 * 600 ** 2) * 300 * 6.35
    assert wall["done"] and wall["braced_by"] is None and wall["p_cr_n"] == pytest.approx(sway, rel=1e-3), wall


@pytest.mark.parametrize("src, names", [(WALL, ["wall"]), (HALVES, ["left half", "right half"])])
def test_the_lone_wall_and_the_wall_cut_in_two_still_fold(tmp_path, src, names):
    s = _part(tmp_path, f"walls {len(names)}", src)
    pcs, tol = _pieces(s, "p")
    rows = buckling.check(pcs, {"force": (0, 0, -1000.0), "factor": 2.0}, PLY, tol)
    assert [r["piece"] for r in rows] == names and all(r["braced_by"] is None and r["edges_held"] == 0 for r in rows)
    assert all(r["safety"] < 1 for r in rows)


def test_the_card_and_the_page_say_what_it_was_taken_as():
    from caliper import answers

    from .test_carve_click import _page, _run

    braced = {"piece": "left side", "done": True, "safety": 1.2, "edges_held": 0, "braced_by": "step", "share": 0.5, "down": True}
    lone = {"piece": "wall", "done": True, "safety": 0.4, "edges_held": 0, "braced_by": None, "share": 1.0, "down": True}
    said = answers.fail_hedge({"min_safety": 2.0}, {"governs": "buckling", "buckling": [braced]}, {"kind": "fails"}, False)
    assert said.startswith(" The left side folds first: it's too slender for the load running down it (a hand buckling check, "
                           "held at its top by the step, its edges and stiffness taken on the safe side, and 50% of the load on it, "
                           "by the lever rule)."), said
    assert answers.fail_hedge({"min_safety": 2.0}, {"governs": "buckling", "buckling": [lone]}, {"kind": "fails"}, False).endswith(
        "and the whole load on it).")
    out = _run(_page(["foldedBy"], consts=["esc"], extra=f"""
out = [foldedBy({{governs: 'buckling', buckling: [{__import__('json').dumps(braced)}]}}),
       foldedBy({{governs: 'buckling', buckling: [{__import__('json').dumps(lone)}]}})];"""))
    assert out == ["the buckling check on the left side: a plate free along its sides, held at its top by the step, 50% of the load on "
                   "it, by the lever rule",
                   "the buckling check on the wall: a plate free along its sides, its top free to sway, its whole load on it"], out
    assert "by the lever rule" in load_study.BUCKLING_CHECKED and "held at its top" in load_study.BUCKLING_CHECKED
