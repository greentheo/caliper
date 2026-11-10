"""CALI-147 (#191) — the card and `blocked` hedged a strength run too coarse to see its walls, and the scorecard didn't: `strength_loads`
read `fail` at 0.53x with an empty note, and `strength.breaks_lb` read 200 lb. A ✗ stays a ✗, but not as a settled number."""
import json
import os

import pytest

from caliper import answers, design_api, goals, load_study, release, scorecard, trials
from caliper.design import DesignStore

from .test_goals import BOX

pytest.importorskip("cadquery")

FEA = {"supported": True, "deflection_mm": 1.5, "wall_mm": 5.18, "at": [-46.0, 165.7, 389.0], "in": "cone skirt"}
COARSE = {"spacing_mm": 4.6, "thinnest_mm": 0.25, "across": 0.053, "finer": True, "too_thin": True}
FINE = {"spacing_mm": 2.0, "thinnest_mm": 19.05, "across": 9.5, "finer": True}


def _case(safety, breaks, holds, **k):
    return {"name": "250 lb person seated", "lb": 250, "factor": 1.5, "safety": safety, "holds": holds, "governs": "fea",
            "breaks_lb": breaks, "fea": FEA, **k}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a stool")
    return s


def _run(store, part, safety, cases, **k):
    os.makedirs(load_study.runs_dir(store), exist_ok=True)
    d = os.path.join(load_study.runs_dir(store), f"20261110-000000-{part}")
    os.makedirs(d)
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": part, "part": part, "version": store.design.part(part).version, "created": 1.0, "safety": safety,
                   "min_safety": 2.0, "cases": cases, **k}, f)


def _goal(store):
    goals.write(store, {"checks": [{"id": "holds", "label": "holds it", "metric": "strength.safety", "op": ">=", "limit": 2, "source": "assumed"}]})


def _card(store):
    card = scorecard.compute(store)
    return card, {c["id"]: c for c in card["checks"]}


def test_a_fail_too_coarse_to_see_its_walls_says_it_isn_t_settled(store):
    _goal(store)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    card, by = _card(store)
    c = by["holds"]
    assert c["status"] == "fail" and c["margin"] is None                # a ✗ stays a ✗
    assert c["trust"] == "not resolved: too coarse to see its walls" and "may be the model" in c["note"]
    assert card["summary"]["fail"] == 1 and card["summary"]["unsettled"] == 1


def test_its_breaking_load_isn_t_reported(store):
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    card, _ = _card(store)
    m = card["metrics"]["strength.breaks_lb"]
    assert m["value"] is None and "may be the model" in m["note"]


def test_the_weakest_load_says_it_isn_t_settled(store):
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    m = _card(store)[0]["metrics"]["strength.safety"]
    assert m["value"] == 0.53 and m["trust"] == "not resolved" and "may be the model" in m["note"]


def test_a_too_coarse_pass_has_no_breaking_load_either(store):
    _goal(store)
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **COARSE)
    card, by = _card(store)
    assert by["holds"]["status"] == "unresolved" and card["metrics"]["strength.breaks_lb"]["value"] is None
    assert "too coarse" in card["metrics"]["strength.breaks_lb"]["note"]


@pytest.mark.parametrize("safety,breaks,holds,status", [(3.1, 1240, True, "pass"), (1.2, 480, False, "fail")])
def test_a_resolved_run_reads_as_it_did(store, safety, breaks, holds, status):
    _goal(store)
    _run(store, "stool", safety, [_case(safety, breaks, holds)], **FINE)
    card, by = _card(store)
    c = by["holds"]
    assert c["status"] == status and c["trust"] == "model" and c.get("note") is None and c["margin"] == pytest.approx(safety - 2, abs=1e-6)
    assert card["metrics"]["strength.breaks_lb"]["value"] == breaks and "note" not in card["metrics"]["strength.breaks_lb"]
    assert card["metrics"]["strength.safety"]["trust"] == "model" and "unsettled" not in card["summary"]


def test_one_part_unsettled_means_no_smallest_breaking_load_from_the_rest(store):
    store.write_part("lid", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a lid")
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **FINE)
    _run(store, "lid", 0.53, [_case(0.53, 200, False)], **COARSE)
    assert _card(store)[0]["metrics"]["strength.breaks_lb"]["value"] is None


# --- the build book -------------------------------------------------------------------------------------------------------
def test_the_book_s_row_says_it_isn_t_settled_and_has_no_breaking_load():
    c = {"safety": 0.53, "breaks_lb": 200, "verdict": {"kind": "fails", "coarse": True}}
    assert release._safety_cell(c) == ("about 0.53x, not settled: too coarse to see its walls", "—")


def test_the_book_s_row_for_a_settled_fail_is_as_it_was():
    c = {"safety": 1.2, "breaks_lb": 480, "verdict": {"kind": "fails"}}
    assert release._safety_cell(c) == ("1.2x", "about 480 lb")


def test_the_book_s_header_says_so():
    s = {"pass": 1, "fail": 1, "unsettled": 1, "unknown": 0, "untrusted": 0, "unresolved": 0, "edge": 0}
    assert "1 check(s) fail (1 not settled: too coarse to see its walls)" in release._status({"summary": s, "checks": [{}, {}]})


def test_the_book_s_header_for_a_settled_fail_is_as_it_was():
    s = {"pass": 1, "fail": 1, "unsettled": 0, "unknown": 0, "untrusted": 0, "unresolved": 0, "edge": 0}
    got = release._status({"summary": s, "checks": [{}, {}]})
    assert "1 check(s) fail" in got and "not settled" not in got


def test_the_book_shows_the_check_s_trust_as_the_reason(store):
    _goal(store)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    _, by = _card(store)
    assert release.TRUST.get(by["holds"]["trust"], by["holds"]["trust"]) == "not resolved: too coarse to see its walls"


def test_the_scorer_was_bumped():
    assert scorecard.SCORER >= 3


# --- the review of #195 ---------------------------------------------------------------------------------------------------
def _low(store, metric="strength.safety", op=">=", limit=0.4):
    goals.write(store, {"checks": [{"id": "low", "label": "at least a little", "metric": metric, "op": op, "limit": limit, "source": "assumed"}]})


def _held(store):
    state = design_api.design_state(store)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(store, state)) if "at least a little" in ln["text"].lower()]
    return line


def test_a_goal_under_an_unresolved_number_is_never_a_tick_on_the_scorecard(store):
    _low(store)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    card, by = _card(store)
    c = by["low"]
    assert c["status"] == "unresolved" and c["margin"] is None and c["note"] and card["summary"]["pass"] == 0


def test_a_goal_under_an_unresolved_number_is_never_a_tick_on_the_card(store):
    _low(store)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    line = _held(store)
    assert line["text"].startswith("! ") and "✓" not in line["text"] and line["status"] == "warn" and "may be the model" in line["text"]


def test_the_book_doesn_t_tick_it_either(store):
    _low(store)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    card, by = _card(store)
    assert release._mark(by["low"]["status"]) != release._mark("pass") and "Ready to cut" not in release._status(card)


def test_a_too_coarse_pass_that_misses_a_higher_goal_says_it_isn_t_settled(store):
    _low(store, limit=5)
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **COARSE)
    c = _card(store)[1]["low"]
    assert c["status"] == "fail" and c["trust"] == "not resolved: too coarse to see its walls" and "too coarse" in c["note"]


def test_a_goal_on_the_breaking_load_is_no_tick_on_the_card(store):
    _low(store, metric="strength.breaks_lb", limit=150)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    state = design_api.design_state(store)
    now = answers.measured(store, state)
    assert "strength.breaks_lb" not in now and "may be the model" in now["strength.no_breaks"]
    line = _held(store)
    assert line["text"].startswith("! ") and "200" not in line["text"] and line["status"] == "warn"


def test_a_goal_on_the_breaking_load_is_unknown_on_the_scorecard_with_the_reason(store):
    _low(store, metric="strength.breaks_lb", limit=150)
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    c = _card(store)[1]["low"]
    assert c["status"] == "unknown" and c["value"] is None and "may be the model" in c["note"]


@pytest.mark.parametrize("safety,breaks,holds", [(3.1, 1240, True), (1.2, 480, False)])
def test_a_resolved_run_s_goals_read_as_they_did_on_the_card(store, safety, breaks, holds):
    _low(store, metric="strength.breaks_lb", limit=150)
    _run(store, "stool", safety, [_case(safety, breaks, holds)], **FINE)
    state = design_api.design_state(store)
    assert answers.measured(store, state)["strength.breaks_lb"] == breaks
    assert _held(store)["text"].startswith("✓")


def test_the_part_s_own_number_says_it_isn_t_settled(store):
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    m = _card(store)[0]["metrics"]["strength.stool.safety"]
    assert m["value"] == 0.53 and m["trust"] == "not resolved" and "may be the model" in m["note"]


def test_a_coarse_pass_s_own_number_says_it_isn_t_settled(store):
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **COARSE)
    m = _card(store)[0]["metrics"]["strength.stool.safety"]
    assert m["trust"] == "not resolved" and "too coarse" in m["note"]


def test_a_resolved_part_s_own_number_is_as_it_was(store):
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **FINE)
    m = _card(store)[0]["metrics"]["strength.stool.safety"]
    assert m["trust"] == "model" and "note" not in m


def test_the_test_plan_gives_no_breaking_load_from_an_unresolved_run(store):
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    pr = trials.predict(store, "stool")
    assert pr["breaks_lb"] is None and pr["steps"] and "too coarse" in pr["basis"]


def test_the_test_plan_keeps_it_on_a_resolved_run(store):
    _run(store, "stool", 3.1, [_case(3.1, 1240, True)], **FINE)
    assert trials.predict(store, "stool")["breaks_lb"] == 1240


def test_the_page_says_it_isn_t_settled_when_there_is_no_breaking_load():
    js = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
    assert "Where it would break isn\\'t settled: the check was too coarse to see its walls." in open(js).read()


def test_the_multi_part_summary_says_how_many_aren_t_settled(store):
    store.write_part("lid", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a lid")
    _run(store, "stool", 0.53, [_case(0.53, 200, False)], **COARSE)
    _run(store, "lid", 3.1, [_case(3.1, 1240, True)], **FINE)
    scorecard.compute(store)
    work = next(c for c in answers.design(store, design_api.design_state(store)) if c["key"] == "work")
    assert any("1 fail (1 not settled: too coarse to see its walls)" in ln["text"] for ln in work["lines"]), work["lines"]

