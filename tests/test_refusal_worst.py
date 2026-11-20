"""CALI-205 (#339): Carve's and Lighten's refusal names the worst failing case, and so does every line that says one.

``load_study.already_fails`` names the lowest case: ``min(cases, key=safety)``. A mutant that took the first failing
case instead survived every test. Since #338 the refusal's words depend on that case: its number, and where it fails
("by the step's plate check", "at the joint between …", the FEA's spot). So a part with two failing cases could be
refused naming the lesser fail.

Checked beside it: the design's line for a coarse fail (``answers.measured``'s ``strength.coarse_fail``) and the
scorecard's took the *first* coarse fail. On a part with two, they named a different case from the refusal. They take
the worst now (``answers.worst_failed``)."""

import json
import os

import pytest

from caliper import answers, load_study, scorecard, verdicts

from .test_fails_where import FEA, FLOOR, JOINT, _case, _run, _store

#: a foot on the step: the floor's plate check fails at 1.6
FOOT = {**_case("plate", 1.6, plate={**FLOOR, "safety_across": 1.6, "safety": 1.6}), "name": "a foot on the step"}
#: a hand on the top: a joint fails at 0.9, worse
HAND = {**_case("joint", 0.9, over="fea", joints={"chain": True, "n": 1, "unchecked": [],
                                                  "governing": {**JOINT, "safety": 0.9}, "rows": [{**JOINT, "safety": 0.9}]}),
        "name": "a hand on the top"}


def _two(tmp_path, cases, **run):
    store = _store(tmp_path, cases[0])
    rid = os.listdir(load_study.runs_dir(store))[0]
    rec = {**_run(cases[0]), "safety": min(c["safety"] for c in cases), "cases": cases, "part": "box",
           "version": store.design.part("box").version, "created": 1.0, **run}
    with open(os.path.join(load_study.runs_dir(store), rid, "run.json"), "w") as f:
        json.dump(rec, f)
    return store, rec


@pytest.mark.parametrize("order", [(FOOT, HAND), (HAND, FOOT)])
def test_the_refusal_names_the_worse_of_two_failing_cases(tmp_path, order):
    store, rec = _two(tmp_path, list(order))
    assert [verdicts.case(rec, c)["kind"] for c in rec["cases"]] == ["fails", "fails"]
    said = load_study.already_fails(store, "box")
    assert said == ("it already fails (0.9 times over, at the joint between the front rail and the left side): "
                    "make it hold first"), said
    assert "plate check" not in said


#: two FEA fails on a run too coarse to see its walls: the back at 0.8, then the front at 0.4
_PLATE = {**FLOOR, "safety_across": 5.0, "safety": 5.0, "deflection_mm": 1.0}
BACK = _case("fea", 0.8, lb=200, factor=1.0, plate=_PLATE,
             fea={**FEA, "safety": 0.8, "wall_mm": 2.0, "deflection_mm": 1.0})
FRONT = {**_case("fea", 0.4, lb=150, factor=1.0, plate=_PLATE,
                 fea={**FEA, "safety": 0.4, "in": "front", "at": [0, 0, 100.0], "wall_mm": 2.0, "deflection_mm": 1.0}),
         "name": "a hand on the front"}
COARSE = {"across": 1.0, "thinnest_mm": 3.0}


@pytest.mark.parametrize("order", [(BACK, FRONT), (FRONT, BACK)])
def test_the_design_s_coarse_fail_line_names_the_case_the_refusal_does(tmp_path, order):
    store, rec = _two(tmp_path, list(order), **COARSE)
    assert all(verdicts.case(rec, c).get("coarse") for c in rec["cases"])
    refusal = load_study.already_fails(store, "box")
    assert refusal.startswith("its check says it fails (0.4 times over, a coarse run") and "in the front" in refusal
    state = {"parts": [{"id": "box", "version": rec["version"]}], "display_units": "in", "load_runs": [rec]}
    line = answers.measured(store, state)["strength.coarse_fail"]
    assert "in the front" in line and "in the back" not in line, line


def test_the_worst_of_several_fails_is_the_lowest_whichever_comes_first():
    c1, c2, c3 = ({"safety": s} for s in (0.8, 0.4, 0.6))
    assert answers.worst_failed([("r", c1, "v1"), ("r", c2, "v2"), ("r", c3, "v3")]) == ("r", c2, "v2")
    assert answers.worst_failed([(c1, "v1"), (c3, "v3"), (c2, "v2")]) == (c2, "v2")


def test_the_scorecard_s_coarse_fail_is_the_worst_too():
    src = open(scorecard.__file__).read()
    assert "hedged = worst_failed(hedged) if hedged else None" in src
    assert 'hedged = next(((c, v) for c, v in said if v["kind"] == "fails" and v.get("coarse")), None)' not in src
