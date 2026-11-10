"""CALI-88 (#64; rule 6): the numbers a person reads are never greener than the check behind them."""

import pytest

from caliper import answers, verdicts


# --- item 1: a failing safety never rounds up to its limit ----------------------------------------------------------

@pytest.mark.parametrize("x, need, said", [
    (1.96, 2, "1.96 times over"),          # a fail: "only 2 times over, and it needs 2" read as a pass
    (1.999, 2, "1.99 times over"),         # cut, never rounded onto the limit
    (2.04, 2, "2.04 times over"),          # within 10% of the limit: the places that tell it from the limit
    (0.96, 2, "0.9 times over"),           # a fail well under: one place, cut
    (1.67, 2, "1.6 times over"),           # not the greener 1.7
    (2.4, 2, "2.4 times over"),            # clear of the limit: one place, as before
    (3.11, 2, "3.1 times over"),
    (9.96, 2, "9.9 times over"),           # not "more than 10"
    (10.0, 2, "more than 10 times over"),  # only from 10.0
])
def test_a_safety_is_said_to_the_places_that_keep_it_on_its_side_of_the_limit(x, need, said):
    assert answers._times(x, need=need) == said


def test_without_a_limit_it_never_rounds_up_to_ten():
    assert answers._times(9.96) == "9.9 times over" and answers._times(10.0) == "more than 10 times over"
    assert answers._times(3.11) == "3.1 times over"


def test_a_fail_line_never_says_the_limit_it_missed():
    run = {"min_safety": 2.0, "spacing_mm": 3.0, "cases": [{"name": "Dad stepping up", "lb": 200, "factor": 2.0,
                                                            "safety": 1.96, "holds": False,  # producer: a fail
                                                            "fea": {"supported": True, "safety": 1.96}, "governs": "fea"}]}
    c = run["cases"][0]
    v = verdicts.case(run, c)
    assert v["kind"] == "fails" and v["short"] == "doesn't hold 1.9x", v["short"]   # the badge, cut not rounded
    text = answers._case_line("stool", run, c, None, False, True)["text"]
    assert "only 1.96 times over, and it needs 2" in text, text


# --- item 2: a pass close to the line is amber ----------------------------------------------------------------------

def _run(safety, need=2.0):
    return {"min_safety": need, "spacing_mm": 3.0, "safety": safety,
            "cases": [{"name": "Dad stepping up", "lb": 200, "factor": need, "safety": safety,
                       "holds": safety >= need,  # producer: the study's own number
                       "fea": {"supported": True, "safety": safety}, "governs": "fea"}]}


@pytest.mark.parametrize("safety, kind, status", [(2.4, "close", "warn"), (2.5, "close", "warn"), (2.6, "holds", "ok"),
                                                  (1.9, "fails", "bad")])
def test_a_pass_within_a_quarter_of_its_limit_is_amber(safety, kind, status):
    run = _run(safety)
    v = verdicts.run(run)
    assert (v["kind"], v["status"]) == (kind, status)
    assert v["counts_as_pass"] == (safety >= 2)                     # close to the line still holds
    assert verdicts.meets(safety, 2.0)["kind"] == kind


def test_the_card_line_says_how_close():
    run = _run(2.4)
    line = answers._case_line("stool", run, run["cases"][0], None, False, True)
    assert line["status"] == "warn" and line["text"] == "Holds dad stepping up, 2.4 times over: close to the 2 it needs.", line
    far = _run(2.6)
    assert answers._case_line("stool", far, far["cases"][0], None, False, True)["status"] == "ok"
