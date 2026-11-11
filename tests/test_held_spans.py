"""CALI-153 (#217; rule 6) — a part spanning between held patches can read a false green, because the check holds its ends fixed.

A shelf on two held() patches read "holds" 5.06, where beam theory gives about 1 across the grain. So a verdict resting on the FEA
alone for a part spanning between its holds can't read a plain ✓, and a panel on held patches gets the beam check it can get."""

import numpy as np
import pytest

from caliper import answers, load_study, samples, scorecard, verdicts
from caliper.design import DesignStore

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

IN = 25.4

#: 3/4 in plywood, 12 in deep, 30 in long, on a patch under each end, a load over a 4 in pad at the middle.
SHELF = '''import cadquery as cq

L, W, T = 30 * 25.4, 12 * 25.4, 19.05
LB = {lb}


def build(params):
    return cq.Workplane().box(L, W, T, centered=False)


def construction(params, build=None):
    return [{{"name": "shelf", "kind": "sheet", "material": "plywood", "thickness": T,
             "outline": [(0, 0, T), (L, 0, T), (L, W, T), (0, W, T)]}}]


def loads(params, build=None):
    return [{{"name": "a load", "lb": LB, "factor": 1.0,
             "lo": (L / 2 - 50.8, W / 2 - 50.8, T - 2), "hi": (L / 2 + 50.8, W / 2 + 50.8, T)}}]


def held(params, build=None):
    return [{{"name": "left", "lo": (0, 0, -1), "hi": (25.4, W, 0)}},
            {{"name": "right", "lo": (L - 25.4, 0, -1), "hi": (L, W, 0)}}]
'''

#: A printed bridge standing on its own two feet on the floor, pushed at the middle: it has no plate or beam check.
BRIDGE = '''import cadquery as cq


def build(params):
    deck = cq.Workplane().box(200, 40, 12, centered=False).translate((0, 0, 30))
    return (deck.union(cq.Workplane().box(20, 40, 42, centered=False))
            .union(cq.Workplane().box(20, 40, 42, centered=False).translate((180, 0, 0))))


def construction(params, build=None):
    return [{"name": "bridge", "kind": "printed", "material": "petg", "infill": 1.0}]


def loads(params, build=None):
    return [{"name": "a push", "lb": 5, "factor": 1.0, "lo": (90, 10, 40), "hi": (110, 30, 42)}]
'''

#: The same bridge pushed straight down over one foot: that goes into the floor, and spans nothing.
OVER_A_FOOT = BRIDGE.replace('"lo": (90, 10, 40), "hi": (110, 30, 42)', '"lo": (2, 10, 40), "hi": (18, 30, 42)')
assert OVER_A_FOOT != BRIDGE


def _store(tmp_path, monkeypatch, script):
    s = DesignStore.create("a thing", base=str(tmp_path / "designs"))
    s.write_part("it", script, intent="a thing")
    return s


def test_the_shelf_on_two_held_patches_is_checked_as_a_beam_and_no_longer_reads_holds(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch, SHELF.format(lb=350))
    rec = load_study.study(s, "it")
    (case,) = rec["cases"]
    assert case["plate"]["done"] and case["plate"]["as"] == "beam" and case["governs"] == "plate"
    # beam theory, held at its ends, 30 in, the load over a 4 in pad: across the grain half of about 2
    assert case["safety"] == pytest.approx(1.0, abs=0.25)
    assert verdicts.run(rec)["kind"] == "fails"


def test_a_shelf_the_beam_check_clears_keeps_a_plain_verdict_resting_on_it(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch, SHELF.format(lb=40))
    rec = load_study.study(s, "it")
    (case,) = rec["cases"]
    assert case["governs"] == "plate" and case["safety"] >= 2
    assert verdicts.run(rec)["kind"] in verdicts.PASSES


def test_a_printed_span_on_two_feet_cant_read_a_plain_tick(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch, BRIDGE)
    rec = load_study.study(s, "it")
    (case,) = rec["cases"]
    assert case["spans"] is True and case["governs"] == "fea" and case["holds"]
    v = verdicts.run(rec)
    assert v["kind"] == "span" and not v["counts_as_pass"] and v["status"] == "warn"
    assert "fixed" in v["why"] and v["short"] == "not settled"


def test_pushing_over_a_foot_spans_nothing(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch, OVER_A_FOOT)
    rec = load_study.study(s, "it")
    (case,) = rec["cases"]
    assert case["spans"] is False and verdicts.run(rec)["kind"] in verdicts.PASSES


def _square(x, y, size=10.0):
    return np.array([[x + i, y + j, 0.0] for i in (0, size) for j in (0, size)])


DOWN = [0.0, 0.0, -100.0]


@pytest.mark.parametrize("mid, spans", [(55.0, True), (5.0, False), (200.0, False)])
def test_a_load_spans_only_between_its_patches(mid, spans):
    patches = [_square(0, 0), _square(100, 0)]
    lo, hi = [mid - 2, 3.0, 10.0], [mid + 2, 7.0, 12.0]            # between; over the first; past the second (a bracket's arm)
    assert load_study.spans_between(patches, lo, hi, DOWN, 2.0) is spans


def test_a_part_that_only_stands_on_the_floor_has_no_held_edges_from_it():
    floor = [{"name": "the floor", "lo": [0, 0, -1], "hi": [500, 500, 5], "default": True}]
    assert load_study.with_held(None, floor, 2.0) is None         # anything would rest on that
    patch = [{"name": "a patch", "lo": [0, 0, -1], "hi": [10, 10, 0]}]
    assert load_study.with_held(None, patch, 2.0)(np.array([[5.0, 5.0, -4.0], [50.0, 5.0, -4.0]])).tolist() == [True, False]


def test_one_patch_spans_nothing():
    assert load_study.spans_between([_square(0, 0)], [4.0, 4.0, 5.0], [6.0, 6.0, 6.0], DOWN, 2.0) is False


def _fea_case(**extra):
    return {"name": "a load", "lb": 100, "factor": 1.0, "safety": 5.0, "holds": True, "governs": "fea",
            "force_n": [0.0, 0.0, -444.8], "lo": [50.0, 3.0, 10.0], "hi": [60.0, 7.0, 12.0],
            "fea": {"supported": True, "safety": 5.0}, **extra}


def _run(*cases, held=()):
    return {"min_safety": 2.0, "cut": True, "version": 1, "safety": 5.0, "cases": list(cases), "held": list(held),
            "material": {"strength": 30.0}}


TWO = [{"name": "a", "lo": [0.0, 0.0, -1.0], "hi": [10.0, 10.0, 0.0]},
       {"name": "b", "lo": [100.0, 0.0, -1.0], "hi": [110.0, 10.0, 0.0]}]


def test_a_stored_run_on_two_held_patches_is_read_the_same_way():
    run = _run(_fea_case(), held=TWO)                               # written before ``spans`` was
    assert verdicts.case(run, run["cases"][0])["kind"] == "span"


def test_a_stored_run_on_the_floor_says_nothing_new():
    run = _run(_fea_case(), held=[{"name": "the floor", "lo": [0, 0, -1], "hi": [110, 10, 1], "default": True}])
    assert verdicts.case(run, run["cases"][0])["kind"] == "holds"


@pytest.mark.parametrize("extra", [{"plate": {"done": True}}, {"governs": "plate"}, {"spans": False}, {"holds": False}])
def test_what_has_a_plate_or_beam_check_or_doesnt_span_is_unchanged(extra):
    run = _run(_fea_case(**{"spans": True, **extra}))
    assert verdicts.case(run, run["cases"][0])["kind"] != "span"


def test_a_fail_stays_a_fail():
    run = _run(_fea_case(spans=True, holds=False, safety=1.2))
    assert verdicts.case(run, run["cases"][0])["kind"] == "fails"


def test_the_sample_stool_is_unchanged(tmp_path):
    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    run = load_study.list_runs(store, "step_stool")[0]
    v = verdicts.run(run)
    assert v["kind"] == "holds" and v["short"] == "holds 3.1x"


# --- every reader says it, and none gives the number as a verdict -------------------------------------------------
@pytest.fixture
def bridge(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch, BRIDGE)
    return s, load_study.study(s, "it")


def test_the_card_says_not_settled_and_why(bridge):
    s, rec = bridge
    line = answers._case_line("it", rec, rec["cases"][0], None, False, True)
    assert "not settled" in line["text"] and "fixed" in line["text"] and "times over" not in line["text"] and line["status"] == "warn"


def test_a_goal_on_it_says_not_settled():
    v = verdicts.goal(True, span=verdicts.SPAN_WHY)
    assert v["kind"] == "span" and not v["counts_as_pass"] and v["why"] == verdicts.SPAN_WHY
    assert verdicts.goal(False, span=verdicts.SPAN_WHY)["kind"] == "fails"          # a ✗ stays a ✗
    assert verdicts.STATUS["span"] == "unknown"


def test_the_last_line_of_a_check_gives_no_number():
    from caliper.load_study import done_words

    said = done_words(1, verdicts._make("span", 5.06, why=verdicts.SPAN_WHY), 5.06)
    assert "5.06" not in said and "not settled" in said


# --- a carve or lightening step ------------------------------------------------------------------------------------
def test_a_step_spanning_its_holds_is_not_a_pass():
    st = {"holds": True, "safety": 5.0, "span": True, "whole_holds": True, "whole": 5.0}
    assert verdicts.station(st)["kind"] == "span"
    assert verdicts.carve_step(st)["kind"] == "span"
    assert verdicts.lighten_step(st)["kind"] == "span"
    assert verdicts.station({**st, "holds": False})["kind"] == "fails"
    assert verdicts.carve_step({**st, "span": False})["kind"] != "span"


def test_a_stations_span_comes_from_its_cases():
    assert load_study.fixed_ends(_run(), _fea_case(spans=True)) is True
    assert load_study.fixed_ends(_run(), _fea_case(spans=True, governs="plate")) is False


def test_a_release_row_and_a_studies_line_say_not_settled(bridge):
    from caliper import release, studies

    _, rec = bridge
    cell = release._safety_cell({"verdict": verdicts.case(rec, rec["cases"][0]), "breaks_lb": 300})
    assert cell == (f"not settled: {verdicts.SPAN_WHY}", "—")
    text, good = studies._headline("load", rec)
    assert text.startswith("not settled") and verdicts.SPAN_WHY in text and good is None


def test_a_scorecard_goal_on_a_span_isnt_a_pass(bridge):
    import yaml

    s, _ = bridge
    with open(scorecard.goals_path(s), "w") as f:
        yaml.safe_dump({"checks": [{"id": "holds", "label": "holds", "metric": "strength.safety", "op": ">=", "limit": 2.0}]}, f)
    card = scorecard.compute(s)
    check = next(c for c in card["checks"] if c["id"] == "holds")
    assert check["status"] == "unknown" and verdicts.SPAN_WHY in (check.get("note") or "")
