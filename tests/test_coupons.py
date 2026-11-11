"""CALI-75 (#42) — the coupons: what beam theory and whittle say about a strip in a three-point bend, and the bench sheet."""

import json
import os

import pytest

from caliper import coupons as K
from caliper import load_study as L
from caliper.design import DesignStore

pytest.importorskip("whittle")

BENCH = os.path.join(os.path.dirname(__file__), "..", "pm", "bench")


def _read(name):
    with open(os.path.join(BENCH, name)) as f:
        return f.read()


def _rows():
    return json.loads(_read("theory-vs-whittle.json"))


def test_the_theory_is_the_hand_sum():
    # a flat 2x4 (3.5 x 1.5 in), 84 in span, 60 lb, E 9000 and 20 MPa:
    # 266.9 N * 2133.6^3 / (48 * 9000 * 409,700) = 14.57 mm in bending, 0.09 in shear at G = E/2.6
    got = K.theory(K.by_id("2x4-F"))
    assert got["sag_mm"] == pytest.approx(14.66, abs=0.01)
    assert got["stress_mpa"] == pytest.approx(6.62, abs=0.01)
    assert got["breaks_lb"] == pytest.approx(181.3, abs=0.1)


def test_a_coupon_across_the_grain_is_half_as_stiff_and_half_as_strong():
    along, across = K.theory(K.by_id("34-L"), 10), K.theory(K.by_id("34-X"), 10)
    assert across["sag_mm"] == pytest.approx(2 * along["sag_mm"])
    assert across["breaks_lb"] == pytest.approx(along["breaks_lb"] / 2)


def test_a_printed_coupon_gets_the_checks_own_values():
    from whittle import MATERIALS

    got = K.material(K.by_id("PG-F"))
    # 1.2 mm walls and 20% infill on a 1 x 1/2 x 8 in bar: 43.6% of it is plastic
    assert got["E"] == pytest.approx(MATERIALS["petg"].youngs_modulus * 0.4362, rel=1e-3)
    assert got["strength"] == pytest.approx(MATERIALS["petg"].strength * 0.4362 * L.LAYERS_ACROSS, rel=1e-3)


@pytest.mark.parametrize("c", K.COUPONS, ids=lambda c: c.id)
def test_the_load_steps_stay_well_short_of_the_break(c):
    assert c.steps[-1] <= K.MOST_OF_BREAK * K.theory(c)["breaks_lb"]
    assert list(c.steps) == sorted(set(c.steps))


def test_the_coupons_are_the_ones_on_the_plan():
    names = [c.name for c in K.COUPONS]
    for want in ("2x4 on edge", "2x4 flat", "3/4 in ply, along", "3/4 in ply, across", "1/2 in ply, along",
                 "1/2 in ply, across", "PETG, printed flat", "PETG, printed on edge"):
        assert want in names


def test_the_sheet_on_disk_is_what_the_code_writes():
    assert _read("coupon-sheet.html") == K.sheet_html()


def test_the_sheet_says_how_to_load_and_read_it_with_what_he_may_have():
    page = K.sheet_html()
    for need in ("Sand or gravel in buckets", "Bathroom scale", "Hanging scale", "Dial indicator", "Rule and thread",
                 "How it broke", "Safety", "Most it held"):
        assert need in page


@pytest.mark.parametrize("words", [
    "Eye protection", "gloves and closed shoes", "so they can't tip", "so they can't roll", "ends can turn and slide",
    "no hand or foot under the load", "never lean over the strip", "never in line with either end",
    "keep people and pets out", "at arm's length", "stop reading sag", "floor gap above a block or pad",
    "rated above the most you'll hang", "luggage scales often stop near 110 lb", "keep your face out of its line",
    "Nobody stands on a coupon", "60 to 80 lb",
])
def test_the_sheets_safety_words_are_there(words):
    assert words in K.sheet_html()


@pytest.mark.parametrize("words", [
    "which includes the hanger and strap", "test all three bars on their 1 in face, 1/2 in deep",
    "take twice the rise", "can't be zeroed with the strip on it", "too coarse for 4 and 5 lb steps",
    "rests on the strip over the supports", "Not on a stand on the floor", "held N, didn't break",
    "a loose block each side at each end", "5 in clear between the 2x4s", "23/32", "15/32", "Skip the sag",
])
def test_the_sheet_heads_off_the_ways_to_write_down_a_wrong_number(words):
    assert words in K.sheet_html()


@pytest.mark.parametrize("c", K.COUPONS, ids=lambda c: c.id)
def test_the_floor_gap_is_more_than_the_sag_when_it_breaks(c):
    gap, top = K.floor_gap_in(c) * K.IN, K.theory(c)["breaks_lb"] if c.breaks else c.steps[-1]
    assert gap > 1.75 * K.theory(c, top)["sag_mm"]                # wood's clear strength is 1.75 times the table's
    assert f"<td class=n>{K.floor_gap_in(c)} in</td>" in next(r for r in K.sheet_html().split("<tr>") if f"<b>{c.id}</b>" in r)


def test_the_check_sizes_voxels_from_the_thinnest_side_and_its_length():
    assert K.check_spacing(K.by_id("2x4-E")) == pytest.approx(2286 / 160, abs=0.01)      # by its length, not its 3.5 in depth
    assert K.across(K.by_id("2x4-E"), 4) == pytest.approx(38.1 / 4)


@pytest.mark.parametrize("c", K.COUPONS, ids=lambda c: c.id)
def test_the_sheet_says_a_rule_wont_do_where_the_sag_is_too_small(c):
    t = K.theory(c)
    row = next(r for r in K.sheet_html().split("<tr>") if f"<b>{c.id}</b>" in r)
    assert ("dial, or skip sag" in row) == (t["sag_mm"] < K.RULER_MM)
    assert ("rule or dial" in row) == (t["sag_mm"] >= K.RULER_MM)
    assert f"{t['sag_mm']:.1f} mm" in row


def test_the_sheet_only_asks_for_a_break_it_can_reach():
    row = next(r for r in K.sheet_html().split("<tr>") if "<b>2x4-E</b>" in r)
    assert "no, it takes 425+ lb" in row
    row = next(r for r in K.sheet_html().split("<tr>") if "<b>2x4-F</b>" in r)
    assert "yes, at 180+ lb" in row


def test_the_table_on_disk_is_the_recorded_runs():
    rows = _rows()
    assert [r["id"] for r in rows] == [c.id for c in K.COUPONS]
    for r in rows:
        t = K.theory(K.by_id(r["id"]))
        assert r["lb"] == K.by_id(r["id"]).steps[-1]
        assert r["theory_sag_mm"] == pytest.approx(t["sag_mm"], abs=0.006)
        assert r["theory_breaks_lb"] == pytest.approx(t["breaks_lb"], abs=0.06)
        for how in ("check", "four", "six", "alone_four", "alone_six"):
            assert r[how]["converged"] is True
    assert _read("theory-vs-whittle.md") == K.table_md(rows)


def _recorded(key, how):
    return next(r for r in _rows() if r["id"] == key)[how]


def test_the_solver_alone_still_matches_beam_theory():
    pytest.importorskip("whittle")
    c = K.by_id("2x4-F")
    t, got = K.theory(c), K.fea(c, K.across(c, 4), how="alone")
    assert 0.8 <= got["sag_mm"] / t["sag_mm"] <= 1.0
    assert got["sag_mm"] == pytest.approx(_recorded("2x4-F", "alone_four")["sag_mm"], rel=0.03)
    assert got["breaks_lb"] == pytest.approx(_recorded("2x4-F", "alone_four")["breaks_lb"], rel=0.03)


def test_held_as_the_check_holds_it_the_strip_still_reads_clamped():
    # the finding the table reports: if this moves, the table and what #42 concludes from it have to be redone
    pytest.importorskip("whittle")
    c = K.by_id("2x4-F")
    t, got = K.theory(c), K.fea(c, K.across(c, 4))
    assert 0.15 <= got["sag_mm"] / t["sag_mm"] <= 0.3
    assert 1.5 <= got["breaks_lb"] / t["breaks_lb"] <= 3.0
    assert got["sag_mm"] == pytest.approx(_recorded("2x4-F", "four")["sag_mm"], rel=0.03)
    assert got["breaks_lb"] == pytest.approx(_recorded("2x4-F", "four")["breaks_lb"], rel=0.03)


def test_a_depth_that_isnt_a_whole_number_of_voxels_is_rounded_up():
    pytest.importorskip("whittle")
    c = K.by_id("2x4-F")
    assert K.fea(c, K.across(c, 4))["layers"] == 4                    # 38.1 mm in 9.525 mm voxels: fits
    assert K.fea(c, K.check_spacing(c))["layers"] == 3                # 38.1 mm in 14.29 mm voxels: 42.9 mm deep


#: The PETG bar as a real part: its own script, loads and supports, through the real strength check.
BAR = '''import cadquery as cq


def build(params):
    return cq.Workplane().box({length}, {width}, {depth}, centered=False)


def construction(params, build=None):
    return [{{"name": "bar", "kind": "printed", "material": "petg"}}]


def loads(params, build=None):
    return [{{"name": "the load", "lb": {lb}, "factor": 1.0, "lo": {load[0]}, "hi": {load[1]}}}]


def held(params, build=None):
    return [{{"name": "one support", "lo": {one[0]}, "hi": {one[1]}}},
            {{"name": "the other", "lo": {two[0]}, "hi": {two[1]}}}]
'''


def test_the_coupon_run_is_what_the_real_check_gets(tmp_path):
    pytest.importorskip("whittle")
    pytest.importorskip("cadquery")
    c = K.by_id("PG-F")
    one, two = K.held_boxes(c)
    store = DesignStore.create("a coupon", base=str(tmp_path / "designs"))
    store.write_part("bar", BAR.format(length=c.length, width=c.width, depth=c.depth, lb=c.steps[-1],
                                       load=K.load_box(c), one=one, two=two), intent="a bar")
    spacing = K.check_spacing(c)
    case = L.study(store, "bar", spacing=spacing)["cases"][0]
    mine = K.fea(c, spacing)
    assert case["fea"]["deflection_mm"] == pytest.approx(mine["sag_mm"], rel=0.01)
    assert case["fea"]["peak_mpa"] == pytest.approx(mine["peak_mpa"], rel=0.01)
