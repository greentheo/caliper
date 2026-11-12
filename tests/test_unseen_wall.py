"""CALI-164 (#244, rule 6) — a pass can't rest on a check that couldn't see the part.

reviewer-2 on the bar stool options study (2026-11-11, scratch copies of `i-want` v8): a copy with no openings read
"holds, 3.31×", the plywood seat's plate check, governing because it's lowest, while the run was too thin for the
voxels: the cone's own number, 6.7×, came from voxels that can't see its 5.8 mm wall. A sibling whose lowest number is
an FEA pass on the same kind of wall (2.05×) read "not checked". Stubbed runs, as those two copies recorded them."""

import pytest

from caliper import answers, load_study, verdicts

#: The bar stool's run, too thin for its voxels at its printed cone's wall (5.8 mm at 2.6 mm voxels: 2.2 across).
RUN = {"min_safety": 2.0, "spacing_mm": 2.6, "thinnest_mm": 5.8, "across": 2.231, "resolved": False, "finer": None,
       "too_thin": True, "thinnest_where": {"at": [0.0, 0.0, 300.0]}, "material": {"printed": True, "strength": 30.0}}


def _case(governs, safety, fea, holds=True, piece="seat"):
    return {"name": "an adult sitting", "safety": safety, "holds": holds, "governs": governs,
            "fea": {"supported": True, "safety": fea}, "plate": {"piece": piece, "done": True, "safety_across": safety}}


def test_no_openings_a_plate_pass_over_an_unseen_wall_is_not_checked():
    """The first copy: the seat's 3.31× under a cone the voxels can't see is unknown, not "holds"."""
    c = _case("plate", 3.31, 6.7)
    v = verdicts.case(RUN, c)
    assert v["kind"] in ("unchecked", "unresolved") and not v["counts_as_pass"]
    assert v["why"] == ("the seat holds 3.31x; the printed walls are too thin to check at this size (5.8 mm, needs 4 "
                        "voxels across, and these are 2.6 mm)")
    assert load_study.unresolved(RUN, c) and not verdicts.holds({**RUN, "cases": [c]})


def test_the_2_05x_sibling_an_fea_pass_on_the_same_wall_stays_not_checked():
    c = _case("fea", 2.05, 2.05)
    v = verdicts.case(RUN, c)
    assert v["kind"] in ("unchecked", "unresolved") and not v["counts_as_pass"]


def test_a_resolved_check_that_fails_still_fails():
    """Unless a resolved check already fails: a ✗ stays a ✗."""
    c = _case("plate", 1.4, 6.7, holds=False)
    assert verdicts.case(RUN, c)["kind"] == "fails"


def test_a_sheet_too_thin_for_the_voxels_is_the_plate_check_s_and_holds():
    """A plywood sheet is judged by its plate check, which needs no voxels: no gap where the thinnest is a sheet."""
    run = {**RUN, "thinnest_mm": 6.35, "across": 2.44, "thinnest_where": {"piece": "seat"}}
    c = _case("plate", 3.31, 6.7)
    assert verdicts.case(run, c)["kind"] == "holds" and not load_study.unresolved(run, c)


def test_an_older_run_that_doesn_t_say_where_is_unknown_the_safe_side():
    run = {k: v for k, v in RUN.items() if k != "thinnest_where"}
    assert not verdicts.case(run, _case("plate", 3.31, 6.7))["counts_as_pass"]


def test_a_resolved_run_is_unchanged():
    run = {**RUN, "spacing_mm": 1.2, "across": 4.83, "resolved": True, "too_thin": None}
    assert verdicts.case(run, _case("plate", 3.31, 6.7))["kind"] == "holds"
    assert load_study.unseen(run, _case("plate", 3.31, 6.7)) == ""          # seen: nothing to say


def test_the_card_says_which_check_couldn_t_see_what():
    line = answers._case_line("stool", RUN, _case("plate", 3.31, 6.7), None, False, False)
    assert line["status"] == "warn"
    assert line["text"].startswith("An adult sitting: not checked: The seat holds 3.31x; the printed walls are too thin "
                                   "to check at this size (5.8 mm")


def test_the_run_s_own_verdict_is_unknown_too():
    """Every reader through the one verdict: a run is its worst case."""
    assert verdicts.run({**RUN, "cases": [_case("plate", 3.31, 6.7)]})["kind"] in ("unchecked", "unresolved")
