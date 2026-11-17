"""CALI-200 (#329): where a failing part fails is the piece its governing check fails, never the FEA's spot.

Found on reviewer-2's aero walk: the floor's plate check governs at 0.01×, while the FEA holds 1,360.9 times over with
its worst stress in the back. The card's ✗ read "Its worst stress is in the back around z 22.4 in", and Lighten's
refusal read "(…; in the back around z 22.4 in)". The back holds; the floor is what fails. The same on step-stool-5 v7 at
500 lb: the step's plate governs at 1.07×, and the card named the front rail."""

import json
import os

import pytest

from caliper import answers, carve, load_study, verdicts
from caliper.design import DesignStore

#: the FEA's spot: the back, holding 1,360.9 times over, its wall seen (19 mm at 3 mm voxels)
FEA = {"supported": True, "safety": 1360.9, "at": [0, 0, 568.96], "in": "back", "wall_mm": 19.05, "peak_mpa": 0.03}
FLOOR = {"done": True, "piece": "floor", "safety_across": 0.01, "safety": 0.01}
JOINT = {"pieces": ["front rail", "left side"], "between": "the front rail and the left side", "mode": "withdrawal",
         "safety": 1.62, "need": 2.0, "holds": False, "said": "two #8 screws pulled out of the front rail's edge"}
FOLD = {"done": True, "piece": "left side", "safety": 1.5, "down": True}


def _run(case):
    return {"id": "t", "min_safety": 2.0, "safety": case["safety"], "holds": False, "spacing_mm": 3.0,
            "thinnest_mm": 19.05, "across": 6.35, "cases": [case]}


def _case(governs, safety, **more):
    return {"name": "two people lying on the mattress", "safety": safety, "holds": False, "governs": governs,
            "fea": FEA, "plate": FLOOR, **more}


PLATE = _case("plate", 0.01)
JOINTED = _case("joint", 1.62, over="fea", joints={"chain": True, "n": 1, "unchecked": [], "governing": JOINT,
                                                    "rows": [JOINT]})
FOLDS = _case("buckling", 1.5, over="fea", buckling=[FOLD])


def _hedge(case):
    run = _run(case)
    v = verdicts.case(run, case)
    assert v["kind"] == "fails", v
    return answers.fail_hedge(run, case, v, True)


def test_a_plate_governed_fail_names_the_panel_never_the_fea_s_spot():
    said = _hedge(PLATE)
    assert said == " The floor fails first, by its plate check (a hand check of the panel on its own)."
    assert "back" not in said and "worst stress" not in said


def test_an_fea_governed_fail_still_says_where_its_worst_stress_is():
    said = _hedge(_case("fea", 0.53, fea={**FEA, "safety": 0.53}))
    assert said == " Its worst stress is in the back around z 22.4 in."


@pytest.mark.parametrize("case, words", [
    ({**JOINTED, "joints": {**JOINTED["joints"], "governing": {}}}, " It fails first at a joint."),
    ({**FOLDS, "buckling": [{"done": False, "piece": "left side"}]}, " It fails first by the buckling check."),
    ({**PLATE, "plate": {"done": True, "safety_across": 0.01}}, " It fails first by the plate check.")])
def test_a_hand_check_s_fail_with_no_piece_named_never_falls_back_to_the_fea_s_spot(case, words):
    assert _hedge(case) == words


def _store(tmp_path, case):
    store = DesignStore.create("a camper", base=str(tmp_path / "designs"))
    store.write_part("box", "def build(params):\n    return None\n", intent="a cargo box")
    run = os.path.join(load_study.runs_dir(store), "20261117-000000-test")
    os.makedirs(run)
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({**_run(case), "part": "box", "version": store.design.part("box").version, "created": 1.0}, f)
    store.design.display_units = "in"
    store.save()
    return DesignStore.load(store.root)


@pytest.mark.parametrize("case, where", [
    (PLATE, "by the floor's plate check"),
    (JOINTED, "at the joint between the front rail and the left side"),
    (FOLDS, "by the left side's buckling check"),
    (_case("fea", 0.53, fea={**FEA, "safety": 0.53}), "in the back around z 22.4 in")])
def test_lighten_s_refusal_names_what_fails(tmp_path, case, where):
    said = load_study.already_fails(_store(tmp_path, case), "box")
    assert said.startswith("it already fails (") and said.endswith(f", {where}): make it hold first"), said


def test_the_refusal_on_a_plate_fail_never_names_the_back(tmp_path):
    said = load_study.already_fails(_store(tmp_path, PLATE), "box")
    assert said == "it already fails (under 0.1 times over, by the floor's plate check): make it hold first"


@pytest.mark.parametrize("case, link", [(PLATE, "floor"), (JOINTED, "joint between the front rail and the left side"),
                                        (FOLDS, "left side"), (_case("fea", 0.53), "back")])
def test_carve_s_weak_link_is_what_its_governing_check_fails(case, link):
    assert load_study.weak_link(case) == link


def test_of_two_walls_the_one_that_folds_first_is_the_weak_link():
    stiff = {"done": True, "piece": "right side", "safety": 3.1, "down": True}
    two = {**FOLDS, "buckling": [stiff, FOLD, {"done": False, "piece": "back"}]}
    assert load_study.weak_link(two) == "left side"
    assert load_study.weak_link({**two, "buckling": [FOLD, stiff]}) == "left side"


def test_carve_reads_its_weak_link_from_the_governing_check():
    src = open(carve.__file__).read()
    assert "load_study.weak_link(case)" in src or "L.weak_link(case)" in src
    assert 'else case["fea"].get("in")' not in src
