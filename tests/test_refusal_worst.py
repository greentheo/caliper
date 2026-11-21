"""CALI-205 (#339): Carve's and Lighten's refusal names the worst failing case, and so does every line that says one.

``load_study.already_fails`` names the lowest case: ``min(cases, key=safety)``. A mutant that took the first failing
case instead survived every test. Since #338 the refusal's words depend on that case: its number, and where it fails
("by the step's plate check", "at the joint between …", the FEA's spot). So a part with two failing cases could be
refused naming the lesser fail.

Checked beside it, every line that names a part's failure: the design card's line (``answers.measured``'s
``strength.coarse_fail`` and ``strength.case``) and the scorecard took the *first* coarse fail, and the refusal took
its doubt from the run and counted an unsupported case. Now one definition, ``verdicts.worst_fail``: the lowest
safety among cases whose own verdict fails, its own verdict deciding the coarse hedge (reviewer-2 on #355).
``answers.fail_said`` is the coarse line the design card and the scorecard both say."""

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
    rec = {**_run(cases[0]), "safety": load_study.run_safety(cases), "cases": cases, "part": "box",
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


#: on a run too coarse to see its walls (3 mm voxels across a 3 mm wall)
COARSE = {"across": 1.0, "thinnest_mm": 3.0}
_PLATE = {**FLOOR, "safety_across": 5.0, "safety": 5.0, "deflection_mm": 1.0}
#: FEA fails, coarse: the back at 0.8, the front at 0.4
BACK = _case("fea", 0.8, lb=200, factor=1.0, plate=_PLATE,
             fea={**FEA, "safety": 0.8, "wall_mm": 2.0, "deflection_mm": 1.0})
FRONT = {**_case("fea", 0.4, lb=150, factor=1.0, plate=_PLATE,
                 fea={**FEA, "safety": 0.4, "in": "front", "at": [0, 0, 100.0], "wall_mm": 2.0, "deflection_mm": 1.0}),
         "name": "a hand on the front"}
#: a foot on the floor: its plate check fails at 0.3, a hand check, settled however coarse the run
FLOORED = {**_case("plate", 0.3, lb=250, factor=2.0, plate={**_PLATE, "safety_across": 0.3, "safety": 0.3},
                   fea={**FEA, "deflection_mm": 1.0}), "name": "a foot on the floor"}
#: a load that reaches no support: no number, never a 0x fail
LOOSE = {**_case("fea", 0.0, lb=100, factor=1.0, plate=_PLATE, fea={"supported": False}),
         "name": "a hand on the lid", "why": "nothing connects where it's pushed to where it's held"}


def _places(tmp_path, cases):
    """Every line that names a part's failure: the refusal, the design card's coarse line and its case, the scorecard's."""
    store, rec = _two(tmp_path, list(cases), **COARSE)
    pairs = [(rec, c) for c in rec["cases"]]
    state = {"parts": [{"id": "box", "version": rec["version"]}], "display_units": "in", "load_runs": [rec]}
    got = answers.measured(store, state)
    return {"refusal": load_study.already_fails(store, "box"), "coarse_fail": got.get("strength.coarse_fail"),
            "case": got.get("strength.case"), "scorecard": answers.fail_said(pairs, True),
            "worst": (verdicts.worst_fail(pairs) or (None, {}))[1].get("name")}


@pytest.mark.parametrize("order", [(BACK, FRONT), (FRONT, BACK)])
def test_s1_two_coarse_fails_every_line_names_the_front(tmp_path, order):
    got = _places(tmp_path, order)
    assert got["worst"] == "a hand on the front"
    assert got["refusal"].startswith("its check says it fails (0.4 times over, a coarse run")
    assert "in the front" in got["refusal"]
    for line in (got["coarse_fail"], got["scorecard"]):
        assert "in the front" in line and "in the back" not in line, line
    assert got["case"] == {"lb": 150, "factor": 1.0}


@pytest.mark.parametrize("order", [(FLOORED, FRONT), (FRONT, FLOORED)])
def test_s2_a_settled_plate_fail_below_a_coarse_fea_fail_is_said_settled_everywhere(tmp_path, order):
    """reviewer-2's S2: the floor's plate check fails at 0.3, settled; the front's FEA fails at 0.4, coarse. The worst is
    the floor: no line puts the front's place or doubt beside the floor's number."""
    got = _places(tmp_path, order)
    assert got["worst"] == "a foot on the floor"
    assert got["refusal"] == "it already fails (0.3 times over, by the floor's plate check): make it hold first"
    assert got["coarse_fail"] is None and got["scorecard"] is None
    assert got["case"] == {"lb": 250, "factor": 2.0}


@pytest.mark.parametrize("order", [(LOOSE, FRONT), (FRONT, LOOSE)])
def test_s3_an_unsupported_case_is_never_the_worst_fail(tmp_path, order):
    """reviewer-2's S3: a load that reaches no support (no number) beside a coarse FEA fail at 0.4. The worst is the
    front, named everywhere, never a refusal with no place."""
    got = _places(tmp_path, order)
    assert got["worst"] == "a hand on the front"
    assert got["refusal"].startswith("its check says it fails (0.4 times over, a coarse run")
    assert "in the front" in got["refusal"]
    for line in (got["coarse_fail"], got["scorecard"]):
        assert "in the front" in line, line
    assert got["case"] == {"lb": 150, "factor": 1.0}


def test_the_scorecard_says_the_shared_line():
    """The scorecard says ``answers.fail_said``, the design card's own line: never a hedge of its own pick."""
    src = open(scorecard.__file__).read()
    assert "hedged = fail_said([(run, c) for c, _ in said], inches)" in src
    assert "fail_hedge(" not in src


#: a plate check that fails at 0.2 on a case whose FEA found no support: the run's number leaves it out (run_safety)
UNHELD_PLATE = {**_case("plate", 0.2, lb=300, factor=1.0, plate={**_PLATE, "safety_across": 0.2, "safety": 0.2},
                        fea={"supported": False}), "name": "a foot on the lid"}


@pytest.mark.parametrize("order", [(UNHELD_PLATE, FRONT), (FRONT, UNHELD_PLATE)])
def test_s4_a_fail_the_run_s_number_leaves_out_is_never_the_worst_fail(tmp_path, order):
    """The run's own number never counts a case whose FEA found no support, whatever governs it. So the worst fail doesn't
    either: no line puts the lid's place beside the front's 0.4."""
    got = _places(tmp_path, order)
    assert got["worst"] == "a hand on the front"
    assert got["refusal"].startswith("its check says it fails (0.4 times over, a coarse run")
    assert "in the front" in got["refusal"] and "lid" not in got["refusal"]
    assert got["case"] == {"lb": 150, "factor": 1.0}


def test_a_part_that_holds_has_no_worst_fail_and_no_coarse_line():
    """Only a case whose own verdict fails is a worst fail: a part whose cases hold, coarse or not, has none to name."""
    holds = {**_case("fea", 3.0, lb=150, factor=1.0, plate=_PLATE, fea={**FEA, "safety": 3.0, "deflection_mm": 1.0}),
             "holds": True}
    for run in (_run(holds), {**_run(holds), **COARSE}):
        assert verdicts.case(run, holds)["kind"] != "fails"
        assert verdicts.worst_fail([(run, holds)]) is None and answers.fail_said([(run, holds)], True) is None
