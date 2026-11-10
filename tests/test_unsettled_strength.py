"""CALI-147 (#191) — the card and `blocked` hedged a strength run too coarse to see its walls, and the scorecard didn't: `strength_loads`
read `fail` at 0.53x with an empty note, and `strength.breaks_lb` read 200 lb. A ✗ stays a ✗, but not as a settled number."""
import json
import os

import pytest

from caliper import goals, load_study, release, scorecard
from caliper.design import DesignStore

from .test_goals import BOX

pytest.importorskip("cadquery")

FEA = {"supported": True, "wall_mm": 5.18, "at": [-46.0, 165.7, 389.0], "in": "cone skirt"}
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
