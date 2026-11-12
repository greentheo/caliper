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

    braced = {"piece": "left side", "done": True, "safety": 1.2, "sway_safety": 1.4, "edges_held": 0, "braced_by": "step", "share": 0.5,
              "down": True}
    lone = {"piece": "wall", "done": True, "safety": 0.4, "edges_held": 0, "braced_by": None, "share": 1.0, "down": True}
    said = answers.fail_hedge({"min_safety": 2.0}, {"governs": "buckling", "buckling": [braced]}, {"kind": "fails"}, False)
    assert said.startswith(" The left side folds first: it's too slender for the load running down it (a hand buckling check, "
                           "its sides and stiffness taken on the safe side, its top held square by its joint to the step, which "
                           "isn't checked, and 50% of the load on it, by the lever rule)."), said
    assert answers.fail_hedge({"min_safety": 2.0}, {"governs": "buckling", "buckling": [lone]}, {"kind": "fails"}, False).endswith(
        "and the whole load on it).")
    out = _run(_page(["foldedBy", "safetyNum"], consts=["esc"], extra=f"""
out = [foldedBy({{governs: 'buckling', buckling: [{__import__('json').dumps(braced)}]}}),
       foldedBy({{governs: 'buckling', buckling: [{__import__('json').dumps(lone)}]}})];"""))
    assert out == ["the buckling check on the left side: a plate free along its sides, its top held square by its joint to the step, "
                   "which isn't checked (it racks and folds at 1.4x if that joint gives), 50% of the load on it, by the lever rule",
                   "the buckling check on the wall: a plate free along its sides, its top free to sway, its whole load on it"], out
    assert "by the lever rule" in load_study.BUCKLING_CHECKED and "held square at its top by its joint" in load_study.BUCKLING_CHECKED
    assert "rack" in load_study.BUCKLING_CHECKED


# --- #265 review -----------------------------------------------------------------------------------------------------------
#: The reviewer's divider: a 3/8 in right side, a 3/4 in left, and a 3/4 in divider between them stopping 100 mm under the step.
def _stool(right_t=19.05, divider=False, overhang=0.0):
    src = TWO_SIDES.replace('"x": 200.0}', f'"x": 200.0, "rt": {right_t}, "oh": {overhang}}}')
    src = src.replace('''    side = lambda x0: cq.Workplane().box(t, d, h, centered=False).translate((x0, 0, 0))
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side(0).union(side(w - t)).union(step)''', '''    rt, oh = p["rt"], p["oh"]
    side = lambda x0, th, hh=h: cq.Workplane().box(th, d, hh, centered=False).translate((x0, 0, 0))
    step = cq.Workplane().box(w + oh, d, t, centered=False).translate((0, 0, h))
    out = side(0, t).union(side(w - rt, rt)).union(step)''' + ('''
    out = out.union(side(w / 2 - t / 2, t, h - 100))''' if divider else '') + '''
    return out''')
    src = src.replace('''            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]}]''', '''            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": p["rt"],
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w + p["oh"], 0, h + t), (w + p["oh"], d, h + t), (0, d, h + t)]}]''' + (''' + [
            {"name": "divider", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w / 2 - t / 2, 0, 0), (w / 2 - t / 2, d, 0), (w / 2 - t / 2, d, h - 100), (w / 2 - t / 2, 0, h - 100)]}]''' if divider else ''))
    return src


def _rows_of(tmp_path, src, x, name):
    s = _part(tmp_path, name, src)
    pcs, tol = _pieces(s, "p")
    load = load_study.parse_loads([{"name": "a foot", "lb": 250, "factor": 2.0, "lo": (x - 50, 115.1, 508.6), "hi": (x + 50, 215.1, 510.65)}])[0]
    return {r["piece"]: r for r in buckling.check(pcs, load, PLY, tol)}


def test_a_divider_the_step_doesn_t_rest_on_takes_none_of_the_share(tmp_path):
    """reviewer on #265: a divider stopping 100 mm under the step took 0.956 of the load and the thin side read 7.86, where
    without it the thin side folds. The load is shared only between walls the loaded piece rests on."""
    plain = _rows_of(tmp_path, _stool(9.525), 200.0, "thin right")
    split = _rows_of(tmp_path, _stool(9.525, divider=True), 200.0, "thin right divided")
    assert split["right side"]["share"] == pytest.approx(plain["right side"]["share"]) and split["right side"]["safety"] < 1.0
    assert split["right side"]["safety"] == pytest.approx(plain["right side"]["safety"])
    assert split["divider"]["share"] == 1.0 and split["divider"]["braced_by"] is None       # not under the step: the whole load
    off = _rows_of(tmp_path, _stool(9.525, divider=True), 100.0, "thin right divided, load left")   # off the divider too
    assert off["divider"]["share"] == 1.0 and off["right side"]["done"] and off["left side"]["done"], off


def test_a_load_beyond_both_walls_puts_more_than_all_of_it_on_the_near_one(tmp_path):
    """reviewer on #265: a step overhanging the right side by 150 mm, the load at its end: the right side takes the lever share,
    over 1; the left is lifted, not pushed, so this load can't fold it."""
    rows = _rows_of(tmp_path, _stool(overhang=150.0), 500.0, "overhung")
    near = 400.0 - 19.05 / 2
    want = (500.0 - 19.05 / 2) / (near - 19.05 / 2)
    assert rows["right side"]["share"] == pytest.approx(want, abs=1e-3) and want == pytest.approx(1.29, abs=0.01)
    assert not rows["left side"]["done"] and "lifts" in rows["left side"]["why"], rows["left side"]


def test_a_braced_wall_says_what_it_reads_if_its_joint_gives(stool):
    rows = _rows(stool)
    r = rows["left side"]
    sway = buckling.SWAY * math.pi ** 2 * E * 19.05 ** 2 / (12 * 491.6 ** 2) * 330.2 * 19.05
    assert r["sway_safety"] == pytest.approx(sway / r["load_n"], rel=1e-3) and r["sway_safety"] == pytest.approx(1.40, abs=0.01)


def _case(rows, safety, governs="buckling"):
    return {"name": "standing on the step", "lb": 250, "factor": 2.0, "safety": safety, "holds": safety >= 2.0, "governs": governs,
            "buckling": rows, "fea": {"supported": True, "safety": 4.0}}


def test_a_pass_that_rests_on_a_brace_is_amber_at_most_and_says_joints_not_checked():
    """The foreman's ruling on #265 (#222's question 1 until Theo answers): two walls under one step can rack; full Euler holds only
    if the joint to the step holds their tops square, and it isn't checked."""
    from caliper import answers, verdicts

    from .test_carve_click import _page, _run

    braced = {"piece": "left side", "done": True, "safety": 5.58, "sway_safety": 1.4, "edges_held": 0, "braced_by": "step",
              "share": 0.5, "down": True}
    run = {"min_safety": 2.0, "cut": True}
    v = verdicts.case(run, _case([braced], 5.58))
    assert verdicts.JOINT_CAP == "close" and v["kind"] == "close" and v["joints"] is True and "joints not checked" in v["why"]
    text = answers._case_line("p", {**run, "cases": []}, _case([braced], 5.58), None, False, False)["text"]
    assert ("the left side is held square at its top by its joint to the step, which isn't checked; if that joint gives, it "
            "racks (leans over with the walls beside it) and folds at 1.4 times over") in text, text
    assert v["word"] == "holds, joints not checked" and v["short"] == "holds 5.6x, joints not checked", v
    whole = verdicts.run({**run, "safety": 5.58, "cases": [_case([braced], 5.58)]})
    assert whole["kind"] == "close" and whole["short"] == "holds 5.6x, joints not checked", whole
    line = _run(_page(["jointsLine", "safetyNum"], consts=["esc"], extra=f"""
out = jointsLine({{verdict: {__import__('json').dumps({"joints": True, "brace": braced})}}}, {{min_safety: 2}});"""))
    assert " ".join(line.split()) == ('<div class="small" style="margin-top:2px"><b>Joints not checked:</b> the left side is held '
                                      "square at its top by its joint to the step, which isn't checked; if that joint gives, it racks "
                                      "(leans over with the walls beside it) and folds at 1.4x.</div>"), line
    assert _run(_page(["jointsLine"], extra="out = jointsLine({verdict: {kind: 'holds'}}, {min_safety: 2});")) == ""
    # the brace lets it pass under another check too: still amber
    v = verdicts.case(run, _case([braced], 3.5, governs="fea"))
    assert v["kind"] == "close" and v["joints"] is True
    # a brace the governing check is on caps the pass even where it would hold swaying: the number itself rests on the joint
    assert verdicts.case(run, _case([{**braced, "sway_safety": 2.5}], 5.58))["kind"] == "close"
    # a brace it doesn't rest on (it would hold swaying too) leaves the pass alone
    firm = {**braced, "sway_safety": 2.5}
    assert verdicts.case(run, _case([firm], 3.5, governs="fea"))["kind"] == "holds"


def test_the_cap_is_one_constant(monkeypatch):
    from caliper import verdicts

    monkeypatch.setattr(verdicts, "JOINT_CAP", "holds")
    braced = {"piece": "left side", "done": True, "safety": 5.58, "sway_safety": 1.4, "edges_held": 0, "braced_by": "step", "share": 0.5}
    v = verdicts.case({"min_safety": 2.0, "cut": True}, _case([braced], 5.58))
    assert v["kind"] == "holds" and v["joints"] is True and "joints not checked" in v["why"]
    from caliper import answers
    text = answers._case_line("p", {"min_safety": 2.0, "cut": True, "cases": []}, _case([braced], 5.58), None, False, False)["text"]
    assert "Its joints aren't checked: the left side is held square at its top by its joint to the step" in text, text
