"""CALI-92 (#70, items 2 to 7 and 17; rule 6) — what a strength or a measurement says has to be what it knows."""

import os
from types import SimpleNamespace

import numpy as np
import pytest

from caliper import carve, load_study, pictures, promote, samples, trials
from caliper.design import DesignStore
from caliper.measure import min_wall_thickness

from .test_carve_click import JS, _fn, _run
from .test_load_study import BOX_STOOL
from .test_mixed import MIXED

pytest.importorskip("cadquery")


# ---------------------------------------------------------------------------
# Item 4: never a picture outside its room
# ---------------------------------------------------------------------------
def _panel(size=100.0):
    from shapely.geometry import box

    return {"room": box(0, 0, size, size), "right": np.array([1.0, 0.0]), "up": np.array([0.0, 1.0])}


def test_a_picture_the_95_percent_shrink_doesnt_bring_inside_is_shrunk_until_it_fits(monkeypatch):
    from shapely.geometry import box

    monkeypatch.setattr(pictures, "cuttable", lambda poly: poly.buffer(8))       # grows it past the room
    panel = _panel()
    got = pictures.fit(box(-10, -10, 10, 10), panel)
    assert got is not None and panel["room"].contains(got)


def test_a_picture_that_never_fits_is_refused(monkeypatch):
    from shapely.geometry import box

    monkeypatch.setattr(pictures, "cuttable", lambda poly: poly.buffer(200))     # nothing fits
    assert pictures.fit(box(-10, -10, 10, 10), _panel()) is None


# ---------------------------------------------------------------------------
# Item 3: a picture that fails on its panel names a quieter one, and asks
# ---------------------------------------------------------------------------
@pytest.fixture
def stool(tmp_path):
    pytest.importorskip("whittle")
    s = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL, intent="a box step stool")
    return s


def _by_panel(front, other):
    return lambda ctx, panel, poly, need: front if "front" in panel["name"] else other


def test_a_picture_too_weak_on_its_panel_names_where_it_would_hold_and_doesnt_move_it(stool, monkeypatch):
    monkeypatch.setattr(pictures, "_try", _by_panel(1.2, 3.1))
    rex = pictures.draw("T-rex", use_llm=False)
    before = stool.design.part("stool").version
    got = pictures.put(stool, "stool", rex, subject="T-rex", where="on the front")
    assert not got["ok"] and stool.design.part("stool").version == before        # never moved unasked
    assert "front" in got["panel"]
    other = got["holds_on"]
    assert "front" not in other
    assert f"It would hold on the {other}" in got["reply"] and "Want it there?" in got["reply"]
    assert "Try another panel" not in got["reply"]


def test_a_picture_too_weak_everywhere_doesnt_promise_another_panel(stool, monkeypatch):
    monkeypatch.setattr(pictures, "_try", _by_panel(1.2, 1.3))
    got = pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="on the front")
    assert not got["ok"] and got["holds_on"] is None
    assert "would hold on" not in got["reply"] and "No other panel" in got["reply"]


# ---------------------------------------------------------------------------
# Item 17: the measuring allowance doesn't swallow a thin wall
# ---------------------------------------------------------------------------
def test_the_allowance_is_capped_at_a_share_of_a_thin_wall():
    assert promote.allow_for_measuring("min_wall >= 1.2") == "min_wall >= 1.2 - 0.06"
    assert promote.allow_for_measuring("min_wall >= 19.05") == "min_wall >= 19.05 - 0.15"
    assert promote.allow_for_measuring("min_wall >= 3") == "min_wall >= 3 - 0.15"
    assert promote.allow_for_measuring("bbox(a).dz >= 1") == "bbox(a).dz >= 1 - 0.1"       # a size isn't a wall


def test_a_rule_written_either_way_is_still_read_as_its_allowance():
    assert promote.added_allowance("min_wall >= 1.2 - 0.06") == pytest.approx(0.06)
    assert promote.added_allowance("min_wall >= 1.2 - 0.15") == pytest.approx(0.15)       # a rule already locked
    assert promote.added_allowance("min_wall >= 1.2 - 0.05") is None                       # their own number


BOX = '''import cadquery as cq


def build(params):
    o = cq.Workplane().box(100, 100, 100, centered=(True, True, False))
    return o.cut(cq.Workplane().box(100 - 2 * {t}, 100 - 2 * {t}, 100 - {t}, centered=(True, True, False)))
'''


@pytest.mark.parametrize("wall", [1.2, 19.05])
def test_a_wall_built_right_reads_inside_its_allowance_and_one_12_percent_under_doesnt(tmp_path, wall):
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX.format(t=wall), intent="a box")
    lower = promote._bounds(promote.allow_for_measuring(f"min_wall >= {wall}"))[1]
    assert min_wall_thickness(s.part_geometry("box")) >= lower
    if wall == 1.2:
        assert 1.06 < lower                                       # what the fixed 0.15 let through


# ---------------------------------------------------------------------------
# Item 2: the measuring advice suits the part
# ---------------------------------------------------------------------------
def test_a_sag_no_hand_tool_can_read_says_the_test_is_the_load_held():
    said = trials.measure_with(0.01)
    assert "load held" in said and "feeler" not in said and "tape" not in said


def test_feeler_gauges_are_only_named_where_they_can_read_it():
    assert "feeler" not in trials.measure_with(0.05)              # the thinnest is about 0.04 mm: nothing to spare
    assert "feeler" in trials.measure_with(0.2)


def test_a_closed_underside_is_measured_from_above_beside_the_foot():
    said = trials.measure_with(0.1, closed=True)
    assert "under the middle" not in said and "beside the foot" in said and "held edges" in said


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return samples.open_sample("step-stool", base=str(tmp_path_factory.mktemp("designs")))


def test_the_sample_stools_advice_suits_its_closed_box(sample):
    pid = sample.design.parts[0].id
    pr = trials.predict(sample, pid)
    assert pr["closed_under"] is True
    assert "beside the foot" in pr["measure_with"] and "under the middle" not in pr["measure_with"]
    # held all round: which way the straightedge goes, and what the other way reads (#228 review)
    assert "long edges" in pr["measure_with"] and "long edges" in pr["measured_at"]
    assert "half an inch past the foot" in pr["measured_at"]
    # the sag is given for that spot, from the plate series: 0.78 of the middle's along the long side
    assert pr["spot"] == pytest.approx(0.776, abs=0.002)
    assert "77%" in pr["other_way"]                                # 0.594 / 0.776
    assert "where the foot is" in pr["basis"]


def test_the_plate_series_reads_the_reviews_numbers_beside_the_foot():
    # #228 review: a Navier series for the sample top, 368 x 216 mm under a 100 mm foot, half an inch past it
    top = {"a_mm": 368.0, "b_mm": 216.0, "footprint_mm": [100.0, 100.0]}
    assert trials.beside_the_foot(top) == pytest.approx(0.776, abs=0.002)
    assert trials.beside_the_foot(top, "short") == pytest.approx(0.594, abs=0.002)
    assert trials.beside_the_foot({"as": "beam"}) == 1.0           # the straightedge moves with the foot


def test_the_sag_on_the_card_is_the_sag_beside_the_foot(sample, monkeypatch):
    pid = sample.design.parts[0].id
    there = trials.predict(sample, pid)
    monkeypatch.setattr(trials, "closed_under", lambda *a: False)
    middle = trials.predict(sample, pid)
    assert there["per_lb_mm"] == pytest.approx([x * there["spot"] for x in middle["per_lb_mm"]], rel=1e-3)
    assert middle["other_way"] is None and middle["measured_at"] == "at the middle"


def test_the_trial_card_says_what_the_other_way_reads(sample):
    import json

    pid = sample.design.parts[0].id
    pr = trials.predict(sample, pid)
    t = {"prediction": pr, "rows": []}
    got = _run("const esc = (s) => String(s); const inches = () => true; const trialChart = () => '';\n"
               "const sagRange = () => ''; const sagText = () => '';\n"
               f"const S = {{trial: {{part: 'p', key: 1, data: {json.dumps(t)}}}}};\n"
               f"{_fn(open(JS).read(), 'trialView')}\nconsole.log(JSON.stringify(trialView({{id: 'p', version: 1}})));")
    assert pr["other_way"] in got and "long edges" in got


def test_a_stool_open_underneath_keeps_the_middle(sample, tmp_path):
    assert trials.closed_under(None, "x", {}, {}) is False        # no plate check: nothing to say it's closed


def _page_range(a, b, inches=True):
    return _run(f"const IN = 25.4; const inches = () => {'true' if inches else 'false'};\n{_fn(open(JS).read(), 'sagRange')}\n"
                f"console.log(JSON.stringify(sagRange({a}, {b})));")


def test_the_sample_stools_50_lb_row_has_two_ends_that_differ(sample):
    pid = sample.design.parts[0].id
    row = next(s for s in trials.predict(sample, pid)["steps"] if s["lb"] == 50)["sag_mm"]
    lo, hi = _page_range(*row).replace(" in", "").split("–")
    assert lo != hi


@pytest.mark.parametrize("a, b, inches", [(0.0191, 0.0204, True), (0.02, 0.9, True), (0.0012, 0.0013, False),
                                          (1.0, 1.0, True)])
def test_the_page_and_the_summary_say_a_sag_range_the_same_way(a, b, inches):
    assert _page_range(a, b, inches) == trials.sag_range(a, b, inches)


def test_equal_ends_are_said_once():
    assert trials.sag_range(25.4, 25.4, True) == "1.000 in"


# ---------------------------------------------------------------------------
# Item 5: buckling, said where it isn't checked
# ---------------------------------------------------------------------------
def test_a_wall_carrying_the_load_lists_buckling_as_not_checked(stool, monkeypatch):
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    rec = load_study.study(stool, "stool")
    assert load_study.BUCKLING in rec["notes"]


def _sheet(normal):
    n = np.asarray(normal, float)
    u = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.5 else np.array([1.0, 0.0, 0.0])
    v = np.cross(n, u)
    return {"kind": "sheet", "polys": [np.array([[0.0, 0.0, 0.0], 100 * u, 100 * u + 100 * v, 100 * v])]}


def test_a_flat_panel_alone_has_no_wall_to_buckle():
    down = [{"force": [0.0, 0.0, -100.0]}]
    assert load_study.buckling_notes([_sheet((0, 0, 1))], down, {}) == []
    assert load_study.buckling_notes([_sheet((1, 0, 0))], down, {}) == [load_study.BUCKLING]


def test_a_printed_part_has_walls_to_buckle():
    assert load_study.buckling_notes([], [{"force": [0.0, 0.0, -100.0]}], {"printed": True}) == [load_study.BUCKLING]


# ---------------------------------------------------------------------------
# Item 6: a station's plywood is held by what that station kept
# ---------------------------------------------------------------------------
def test_a_stations_support_is_only_where_its_print_still_is():
    grid = SimpleNamespace(origin=(0.0, 0.0, 0.0), spacing=1.0)
    printed = np.zeros((6, 6, 6), dtype=bool)
    printed[:2] = True
    under = carve.station_under(lambda pts, tol=0.5: np.ones(len(pts), dtype=bool), grid, printed)
    got = under(np.array([[0.0, 2.0, 2.0], [5.0, 2.0, 2.0], [50.0, 2.0, 2.0]]))
    assert got.tolist() == [True, False, False]


class _Stop(Exception):
    pass


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    s = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    s.write_part("stool", MIXED, intent="a plywood top on printed sides")
    return s


def _carve_with(mixed, monkeypatch, cut):
    """The real carve up to the first station's strength check, the station's shape being ``cut`` of the solid."""
    from whittle import LoadStudy

    seen = {}
    real = load_study.check_load

    def sweep(self, **kw):
        return SimpleNamespace(stations=[SimpleNamespace(design=cut(self))])

    def check(ctx, i, need, solid=None):
        seen["case"] = real(ctx, i, need, solid=solid)[0]
        raise _Stop

    monkeypatch.setattr(LoadStudy, "sweep", sweep)
    monkeypatch.setattr(load_study, "check_load", check)
    with pytest.raises(_Stop):
        carve.study(mixed, "stool", stations=2)
    return seen["case"]


def test_carving_away_what_holds_an_edge_changes_the_plywoods_check(mixed, monkeypatch):
    whole = _carve_with(mixed, monkeypatch, lambda ls: ls.solid)
    assert whole["plate"]["done"] and whole["plate"]["edges_held"] == 2

    def no_left_side(ls):
        centres = np.asarray(ls.grid.origin)[0] + ls.grid.spacing * np.arange(ls.solid.shape[0])
        out = ls.solid.copy()
        out[centres < 30.0] = False
        return out

    monkeypatch.undo()
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    carved = _carve_with(mixed, monkeypatch, no_left_side)
    assert carved["plate"]["edges_held"] == 1 and not carved["plate"].get("done")


def _carve_steps(mixed, monkeypatch, cut):
    """The real carve's checks of two steps, as drawn and ``cut``: every load's case at each, then stopped."""
    import trimesh
    from whittle import LoadStudy

    seen, real = [], load_study.check_load

    def sweep(self, **kw):
        return SimpleNamespace(stations=[SimpleNamespace(design=d, build=lambda: None)
                                         for d in (self.solid.copy(), cut(self))])

    def check(ctx, i, need, solid=None):
        seen.append(real(ctx, i, need, solid=solid)[0])
        if len(seen) == 2 * len(ctx["loads"]):
            raise _Stop
        return seen[-1], SimpleNamespace(supported=False)

    monkeypatch.setattr(LoadStudy, "sweep", sweep)
    monkeypatch.setattr(load_study, "check_load", check)
    monkeypatch.setattr(carve, "_station_mesh", lambda mesh: trimesh.creation.box())
    with pytest.raises(_Stop):
        carve.study(mixed, "stool", stations=2)
    n = len(seen) // 2
    return seen[:n], seen[n:]


def _centres(ls, axis):
    return np.asarray(ls.grid.origin)[axis] + ls.grid.spacing * np.arange(ls.solid.shape[axis])


def _notch_under_one_held_edge(ls):
    """The review's notch: the printed side cut away under the middle of the left edge, just below the plywood."""
    x, y, z = (_centres(ls, a) for a in range(3))
    out = ls.solid.copy()
    cut = (x < 30.0)[:, None, None] & (abs(y - 110.0) < 20.0)[None, :, None] & ((z > 160.0) & (z < 207.0))[None, None, :]
    out[cut] = False
    return out


def test_a_step_carved_under_a_held_edge_reads_no_stronger_than_the_part_as_drawn(mixed, monkeypatch):
    # Rule 6 (#228 review): the notch unholds the edge, the plate check stops and the FEA reads a plywood top far
    # higher (0.57 -> 1.66 on the review's run). Taking support away can't make it stronger
    drawn, notched = _carve_steps(mixed, monkeypatch, _notch_under_one_held_edge)
    assert all(c["governs"] == "plate" and c["plate"]["done"] for c in drawn)
    for was, now in zip(drawn, notched):
        assert now["plate"]["as_drawn"] and now["plate"]["edges_held"] == 2
        assert now["fea"]["safety"] > was["safety"]                  # what it would have read
        assert now["safety"] == was["safety"] and now["governs"] == "plate"
        assert now["breaks_lb"] == was["breaks_lb"]


def test_a_step_with_a_whole_side_cut_away_reads_no_stronger_than_the_part_as_drawn(mixed, monkeypatch):
    def no_left_side(ls):
        out = ls.solid.copy()
        out[_centres(ls, 0) < 30.0] = False
        return out

    drawn, carved = _carve_steps(mixed, monkeypatch, no_left_side)
    for was, now in zip(drawn, carved):
        assert now["safety"] is not None and now["safety"] <= was["safety"]


def test_the_ceiling_is_the_plywoods_number_across_the_grain():
    # the plate is judged across the grain; a ceiling on the along-grain number would let an FEA between the two through
    drawn = {"done": True, "safety": 1.2, "safety_across": 0.57, "piece": "top"}
    governs, safety, pl = load_study.as_drawn_ceiling(drawn, "fea", 0.9, None)
    assert (governs, safety, pl["as_drawn"]) == ("plate", 0.57, True)
    assert load_study.as_drawn_ceiling(drawn, "fea", 0.5, None) == ("fea", 0.5, None)       # under it: its own number
    assert load_study.as_drawn_ceiling(None, "fea", 1.66, None) == ("fea", 1.66, None)      # as drawn: nothing to cap it


def test_a_capped_step_reads_no_higher_than_as_drawn_and_isnt_a_pass(mixed, monkeypatch):
    import trimesh
    from whittle import LoadStudy

    from caliper import verdicts

    monkeypatch.setattr(LoadStudy, "sweep", lambda self, **kw: SimpleNamespace(
        stations=[SimpleNamespace(design=d, build=lambda: None) for d in (self.solid.copy(), _notch_under_one_held_edge(self))]))
    monkeypatch.setattr(carve, "_station_mesh", lambda mesh: trimesh.creation.box())
    monkeypatch.setattr(carve, "_judge", lambda *a, **k: None)
    rec = carve.study(mixed, "stool", stations=2, min_safety=0.5)       # under the as-drawn 0.57: the step would pass on its number
    drawn, notched = rec["stations"]
    assert not drawn["at_most"] and notched["at_most"] and notched["whole"] == drawn["whole"]
    assert carve.CAPPED in rec["notes"] and "no higher than" in carve.CAPPED
    v = verdicts.carve_step(notched, None, rec)
    assert not v["counts_as_pass"] and v["why"] == verdicts.AT_MOST_WHY


def test_a_carves_notes_list_buckling_as_not_checked(mixed, monkeypatch):
    import trimesh
    from whittle import LoadStudy

    monkeypatch.setattr(LoadStudy, "sweep", lambda self, **kw: SimpleNamespace(
        stations=[SimpleNamespace(design=self.solid.copy(), build=lambda: None)]))
    monkeypatch.setattr(carve, "_station_mesh", lambda mesh: trimesh.creation.box())
    monkeypatch.setattr(carve, "_judge", lambda *a, **k: None)
    rec = carve.study(mixed, "stool", stations=1)
    assert load_study.BUCKLING in rec["notes"]                     # printed sides carry the top in compression
    assert carve.CAPPED not in rec["notes"]                        # nothing carved, nothing capped


def test_a_step_that_keeps_its_held_edges_is_read_by_its_own_plate_check(mixed, monkeypatch):
    drawn, same = _carve_steps(mixed, monkeypatch, lambda ls: ls.solid.copy())
    assert not any(c["plate"].get("as_drawn") for c in same)
    assert [c["safety"] for c in same] == [c["safety"] for c in drawn]


# ---------------------------------------------------------------------------
# Item 7: the adopted plywood and carved sides are one body
# ---------------------------------------------------------------------------
def test_adopting_a_step_joins_the_plywood_and_the_print_into_one_body(mixed, tmp_path):
    pytest.importorskip("manifold3d")
    # a carve's step keeps the wood's voxels, so its mesh runs up into the plywood: the whole part, uncarved, does too
    path = os.path.join(tmp_path, "station.stl")
    mixed.part_geometry("stool").require_mesh().export(path)
    shape = carve._adopted(mixed, "stool", path, 4.0)
    assert len(shape.split(only_watertight=False)) == 1
