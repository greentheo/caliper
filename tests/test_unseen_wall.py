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
    assert v["why"] == ("the seat's plate check holds 3.3 times over; the printed walls are too thin to check at this size (5.8 mm, needs 4 "
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


def test_a_sheet_too_thin_for_the_voxels_is_its_own_plate_check_s_and_holds():
    """A plywood sheet is judged by its plate check, which needs no voxels: no gap where the unseen wall is its own sheet."""
    run = {**RUN, "thinnest_mm": 6.35, "across": 2.44, "thinnest_where": {"piece": "seat"}, "unseen": [{"mm": 6.35, "piece": "seat"}]}
    c = _case("plate", 3.31, 6.7)
    assert verdicts.case(run, c)["kind"] == "holds" and not load_study.unresolved(run, c)


def test_a_shelf_the_voxels_can_t_see_isn_t_cleared_by_the_seat_s_plate_check():
    """#248 review, the foreman's scope: an unseen wall is cleared only by a resolved check of that same piece."""
    run = {**RUN, "thinnest_mm": 6.35, "across": 2.44, "thinnest_where": {"piece": "shelf"},
           "unseen": [{"mm": 6.35, "piece": "shelf"}, {"mm": 6.35, "piece": "seat"}]}
    v = verdicts.case(run, _case("plate", 3.31, 6.7))
    assert v["kind"] == "unchecked" and not v["counts_as_pass"]
    assert v["why"] == ("the seat's plate check holds 3.3 times over; the shelf is too thin to check at this size (6.35 mm, "
                        "needs 4 voxels across, and these are 2.6 mm)")


def test_a_printed_wall_a_little_thicker_than_the_seat_still_counts():
    """#248 review: the run recorded only its thinnest, a sheet; a printed wall under 4 voxels beside it went uncounted."""
    run = {**RUN, "thinnest_mm": 6.35, "across": 2.44, "thinnest_where": {"piece": "seat"},
           "unseen": [{"mm": 6.35, "piece": "seat"}, {"mm": 8.0, "at": [0.0, 0.0, 300.0]}]}
    v = verdicts.case(run, _case("plate", 3.31, 6.7))
    assert v["kind"] == "unchecked" and "the printed walls are too thin to check at this size (8 mm" in v["why"]


def test_an_older_run_that_names_only_its_thinnest_sheet_is_unknown_the_safe_side():
    """It doesn't say what else the voxels couldn't see (#248 review)."""
    run = {**RUN, "thinnest_mm": 6.35, "across": 2.44, "thinnest_where": {"piece": "seat"}}
    assert not verdicts.case(run, _case("plate", 3.31, 6.7))["counts_as_pass"]


def test_the_run_records_every_wall_it_couldn_t_see_thinnest_first():
    found = [(19.05, {"piece": "seat"}), (6.35, {"piece": "shelf"}), (8.0, {"at": [1.0, 2.0, 3.0]}), (12.0, {"piece": "leg"})]
    assert load_study.unseen_walls(found, 2.6) == [{"mm": 6.35, "piece": "shelf"}, {"mm": 8.0, "at": [1.0, 2.0, 3.0]}]
    assert load_study.unseen_walls(found, 1.0) == []


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
    assert line["text"] == ("An adult sitting: not checked: the seat's plate check holds 3.3 times over; the printed walls "
                            "are too thin to check at this size (5.8 mm, needs 4 voxels across, and these are 2.6 mm). A hand "
                            "check or a printed test piece is the way to know."), line["text"]     # once each (#248 review)
    assert line["text"].lower().count("not checked") == 1


# --- #248 review ------------------------------------------------------------------------------------------------------------
def test_a_resolved_plate_fail_over_an_unseen_wall_is_a_plain_fail():
    """Rule 6 both ways: "unseen" softens a pass, never a resolved ✗. The plate check needs no voxels."""
    from caliper import studies

    c = _case("plate", 1.4, 6.7, holds=False)
    v = verdicts.case(RUN, c)
    assert v["kind"] == "fails" and not v.get("coarse")
    assert "the model's" not in answers._case_line("stool", RUN, c, None, False, False)["text"]
    text, ok = studies._headline("load", {**RUN, "safety": 1.4, "cases": [c]})
    assert ok is False and "the model's" not in text, text


def test_an_fea_fail_on_a_wall_it_can_t_see_may_still_be_the_model_s():
    c = _case("fea", 1.4, 1.4, holds=False)
    assert verdicts.case(RUN, c)["coarse"]
    assert verdicts.case(RUN, _case("fea-calibrated", 1.4, 1.4, holds=False))["coarse"]


def test_a_buckling_pass_over_the_plate_names_the_wall_that_buckles():
    c = {**_case("buckling", 3.0, 6.7), "over": "plate", "plate": {"piece": "seat", "done": True, "safety_across": 3.31},
         "buckling": [{"piece": "back", "done": True, "safety": 4.0}, {"piece": "leg", "done": True, "safety": 3.0}]}
    v = verdicts.case(RUN, c)
    assert v["why"].startswith("the leg's buckling check holds 3 times over; the printed walls"), v["why"]


def test_a_calibrated_fea_is_the_fea_that_can_t_see_the_wall():
    """lighten.judged's "fea-calibrated" is the FEA's own number: no "fea-calibrated check" in the words."""
    c = _case("fea-calibrated", 3.0, 3.0)
    v = verdicts.case(RUN, c)
    assert v["kind"] == "unchecked" and "calibrated" not in v.get("why", "") and load_study.unresolved(RUN, c)


def test_studies_names_the_governing_check_with_its_own_number():
    from caliper import studies

    text, ok = studies._headline("load", {**RUN, "safety": 3.31, "cases": [_case("plate", 3.31, 6.7)]})
    assert text == "not checked: its walls are too thin for the voxels (the seat's plate check read 3.3x; the FEA read 6.7x)", text
    text, _ = studies._headline("load", {**RUN, "safety": 2.05, "cases": [_case("fea", 2.05, 2.05)]})
    assert text == "not checked: its walls are too thin for the voxels (the FEA read 2.05x)", text


def test_the_run_s_own_verdict_is_unknown_too():
    """Every reader through the one verdict: a run is its worst case."""
    assert verdicts.run({**RUN, "cases": [_case("plate", 3.31, 6.7)]})["kind"] in ("unchecked", "unresolved")


def test_the_design_card_says_it_once_with_the_check_that_holds(tmp_path):
    """#248 review: the card's goal line said "its walls are too thin for the voxel check" for the seat's plate pass."""
    from caliper.design import DesignStore

    store = DesignStore.create("a bar stool", base=str(tmp_path))
    store.write_part("stool", "def build(params):\n    return None\n", intent="x")
    run = {**RUN, "part": "stool", "version": 1, "cut": True, "safety": 3.31, "cases": [_case("plate", 3.31, 6.7)]}
    now = answers.measured(store, {"parts": [{"id": "stool", "version": 1}], "load_runs": [run]})
    assert now["strength.unresolved"] == ("Not checked: the seat's plate check holds 3.3 times over; the printed walls are too "
                                          "thin to check at this size (5.8 mm, needs 4 voxels across, and these are 2.6 mm). "
                                          "A hand check or a printed test piece is the way to know.")


def test_a_trial_s_prediction_says_why_there_s_no_break_to_test_against(tmp_path, monkeypatch):
    """#248 CI: an unknown case has no breaking load to load it up to; the plan says why, never None unexplained."""
    from caliper import trials
    from caliper.design import DesignStore

    store = DesignStore.create("a bar stool", base=str(tmp_path))
    store.write_part("stool", "def build(params):\n    return None\n", intent="x")
    c = {**_case("plate", 3.31, 6.7), "lb": 200.0, "factor": 2.0, "breaks_lb": 1300.0,
         "fea": {"supported": True, "safety": 6.7, "deflection_mm": 0.2},
         "plate": {"piece": "seat", "done": True, "safety_across": 3.31, "deflection_mm": 0.4}}
    run = {**RUN, "id": "r1", "version": 1, "material": {"key": "plywood", "E": 8000.0, "across": 0.5}, "cases": [c]}
    monkeypatch.setattr(trials, "_run", lambda s, pid: run)
    pr = trials.predict(store, "stool")
    assert pr["breaks_lb"] is None and pr["over"] is None
    assert pr["why_no_break"] == ("no prediction: the check couldn't see the wall: the printed walls are too thin to check "
                                  "at this size (5.8 mm, needs 4 voxels across, and these are 2.6 mm)"), pr["why_no_break"]
    assert pr["basis"].startswith("from checks that couldn't see every wall, so a rough guess until it's checked again: ")
    run["cases"] = [{**c, "governs": "fea", "safety": 6.7}]                # the FEA governs, too coarse to see its walls
    pr = trials.predict(store, "stool")
    assert pr["why_no_break"] == "no prediction: the check was too coarse to see its walls" and pr["breaks_lb"] is None
