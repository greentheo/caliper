"""CALI-166 (#249) — tonight's small follow-ups: plan rules compare with a measuring allowance, the drive says what followed, a mirror
word about holes isn't a part mirror, and an older run's "not checked" gives one next step. Stubbed only."""

import pytest

from caliper import evaluate
from caliper.spec import Assertion


# --- 1. float noise, not a measuring tolerance -------------------------------------------------------------------------------
def _check(expr, **ctx):
    return evaluate.evaluate_assertion(Assertion(id="r", expr=expr), ctx)


def test_17_in_is_431_8_mm():
    """step-stool-4's top_at_height: 17 × 25.4 = 431.79999999999995 failed against 431.8."""
    assert 17 * 25.4 != 431.8                                       # the float that failed
    got = _check("top == 431.8", top=17 * 25.4)
    assert got.status == "pass" and got.margin == 0.0 and got.detail == "", got
    assert _check("top <= 431.8", top=17 * 25.4 + 1e-12).status == "pass"
    assert _check("top >= 431.8", top=17 * 25.4).status == "pass"
    assert _check("top != 431.8", top=17 * 25.4).status == "fail"           # the same number, said otherwise


def test_nothing_a_person_could_measure_moves():
    """The foreman (#249): an absolute allowance would pass safety >= 2.0 at 1.995, and a weight or a count by a hundredth."""
    assert evaluate.REL_TOL == evaluate.ABS_TOL == 1e-9
    assert _check("safety >= 2.0", safety=1.995).status == "fail"
    assert _check("safety >= 2.0", safety=1.99999).status == "fail"
    assert _check("lb <= 10.0", lb=10.001).status == "fail"
    assert _check("top == 431.8", top=431.81).status == "fail"
    assert _check("count == 1", count=1).status == "pass" and _check("count == 1", count=2).status == "fail"
    assert _check("count >= 4", count=3).status == "fail"
    assert _check("top < 431.8", top=17 * 25.4).status == "pass"            # strict stays strict: below, as stored
    assert _check("top > 431.8", top=17 * 25.4).status == "fail"


def test_a_band_at_the_noise_reads_margin_0_and_the_helpers_agree():
    """#253 review: a two-sided band at the noise read margin −5.68e-14; within() and fits() compared exactly."""
    from caliper import tolerance

    got = _check("0 <= top <= 431.8", top=17 * 25.4 + 1e-12)
    assert got.status == "pass" and got.margin == 0.0, got
    assert _check("431.8 >= top >= 0", top=17 * 25.4 + 1e-12).margin == 0.0
    assert _check("within(top, 0, 431.8)", top=17 * 25.4 + 1e-12, within=tolerance.within).status == "pass"   # bound as build_context does
    assert tolerance.within(17 * 25.4 + 1e-12, 0, 431.8) and tolerance.within(431.8, 17 * 25.4 + 1e-12, 500)
    assert not tolerance.within(431.81, 0, 431.8)
    hi = tolerance.fit_band("slip")[1]
    assert tolerance.fits(hi * (1 + 1e-12), "slip") and not tolerance.fits(hi + 0.001, "slip")
    assert tolerance.approx(0.30000000000000004, 0.2, tol=0.1) and not tolerance.approx(0.31, 0.2, tol=0.1)
    assert tolerance.REL_TOL == tolerance.ABS_TOL == evaluate.REL_TOL == 1e-9


def test_a_comparison_well_inside_keeps_its_margin():
    got = _check("top <= 500", top=431.8)
    assert got.status == "pass" and got.detail == "" and got.margin == pytest.approx(68.2)
    assert _check("safety >= 2.0", safety=1.995).margin == pytest.approx(-0.005)


def test_a_rule_in_the_assembly_uses_it_too():
    """The plan's rules are checked by evaluate_assertion as the parts' are: one allowance."""
    import inspect

    from caliper import assembly

    assert "evaluate_assertion(a, ctx)" in inspect.getsource(assembly.evaluate_assembly)


# --- 2. the drive says what followed -------------------------------------------------------------------------------------
def test_the_drive_s_reply_names_the_mirror_that_followed():
    from caliper import skeleton

    result = {"changed": {"top_height": (16.0, 17.0)}, "units": {"top_height": "in"}, "rebuilt": {"side_right": ["top_height"]},
              "follows": {"side_left": "side_right"}, "unmoved": {}, "refused": {}, "strength": [], "report": None}
    said = skeleton.said(result)
    assert "The side left follows the side right: both now 17 in." in said, said
    result["follows"] = {}
    assert "follows" not in skeleton.said(result)


# --- 3. a mirror word about holes ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("words, noted", [
    ("bolt holes mirrored to match the side flanges", False),
    ("slots mirrored on both sides", False),
    ("the cut-outs are mirrored", False),
    ("a mirror of the other side", True),             # a part mirror, with no part found: still noted
    ("mirrored, like the right one", True),
])
def test_a_mirror_word_about_holes_isn_t_a_part_mirror(words, noted, monkeypatch):
    from caliper import review

    monkeypatch.setattr(review, "_plan_parts", lambda store: [{"id": "top", "what": words}, {"id": "base", "what": "a base"}])
    pairs, unpaired = review.mirrored_pairs(None)
    assert pairs == [] and (unpaired == ["top"]) is noted, (words, unpaired)


# --- 4 and 5. an older run's "not checked" ---------------------------------------------------------------------------------
def _old(**kw):
    from .test_unseen_wall import RUN

    return {**{k: v for k, v in RUN.items() if k != "thinnest_where"}, "thinnest_where": {"piece": "seat"}, **kw}


def test_an_older_run_says_it_s_from_before_and_gives_one_next_step():
    from caliper import answers

    from .test_unseen_wall import _case

    run = _old(too_thin=None, finer=True)
    line = answers._case_line("stool", run, _case("plate", 3.31, 6.7), None, False, False)["text"]
    assert line == ("An adult sitting: not checked: the seat's plate check holds 3.3 times over; this run is from before unseen walls "
                    "were recorded: check it again."), line


def test_an_older_run_too_thin_for_any_run_adds_the_hand_check_after():
    from caliper import answers

    from .test_unseen_wall import _case

    line = answers._case_line("stool", _old(), _case("plate", 3.31, 6.7), None, False, False)["text"]
    assert line.endswith("this run is from before unseen walls were recorded: check it again. If it still can't see its walls, a "
                         "hand check or a printed test piece is the way to know."), line
    assert line.count("check it again") == 1


def test_an_older_run_s_trial_doesn_t_claim_an_unseen_wall(tmp_path, monkeypatch):
    from caliper import trials
    from caliper.design import DesignStore

    from .test_unseen_wall import _case

    store = DesignStore.create("a bar stool", base=str(tmp_path))
    store.write_part("stool", "def build(params):\n    return None\n", intent="x")
    c = {**_case("plate", 3.31, 6.7), "lb": 200.0, "factor": 2.0, "breaks_lb": 1300.0,
         "fea": {"supported": True, "safety": 6.7, "deflection_mm": 0.2},
         "plate": {"piece": "seat", "done": True, "safety_across": 3.31, "deflection_mm": 0.4}}
    run = {**_old(), "id": "r1", "version": 1, "material": {"key": "plywood", "E": 8000.0, "across": 0.5}, "cases": [c]}
    monkeypatch.setattr(trials, "_run", lambda s, pid: run)
    pr = trials.predict(store, "stool")
    assert pr["why_no_break"] == "no prediction: this run is from before unseen walls were recorded: check it again"
    assert "couldn't see" not in pr["why_no_break"] + pr["basis"]
    assert pr["basis"].startswith("from a run from before unseen walls were recorded, so a rough guess until it's checked again: ")
