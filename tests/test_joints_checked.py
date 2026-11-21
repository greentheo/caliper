"""CALI-225 (#383): a pass is what was checked. A joint the FEA read is checked; one nothing read is said, everywhere.

caliper-ui's tester walk, on step-stool-5: "holds, 19 joints not checked by hand" was green and ✓, the design's view
showed ✓ where the part's own view of the same card showed !, and Things to fix read "✓ nothing measured wrong" beside it.
The foreman's rule, built here:
1. a joint the FEA read (#344) counts as checked, and says "checked by the FEA";
3. the design's "Will it work?" says what its parts' cards say isn't checked yet, so the two views read alike;
4. Things to fix lists the joints nothing checked, as a row that wasn't measured, with the way to have them read.
Rule 2, a pass resting on joints nothing checked reading "not checked", reverses Theo's #222 answer ("✓ with a note"), so
it waits on his word behind one switch, ``verdicts.JOINT_CAP``. Rule 4's row follows it: while the pass is a ✓ with its
note, the joints stay a known limit (#318), and the switch makes them a row instead, said once either way."""

import pytest

from caliper import answers, design_api, fixes, verdicts

pytest.importorskip("cadquery")


def _row(**k):
    return {"pieces": ["a", "b"], "between": "the a and the b", **k}


def test_a_joint_the_fea_read_is_checked_and_one_nothing_read_isn_t():
    assert verdicts.checked(_row(safety=2.4))                                       # by hand
    assert verdicts.checked(_row(safety=None, fea={"safety": 3.1}))                 # by the FEA
    assert not verdicts.checked(_row(safety=None, fea={"safety": 3.1, "unread": "it bonds them"}))
    assert not verdicts.checked(_row(safety=None))


def test_a_path_the_hand_rule_can_t_follow_counts_only_the_joints_nothing_read():
    run = {"min_safety": 2.0}
    J = {"chain": False, "n": 3, "unchecked": ["its load path isn't a simple chain"],
         "rows": [_row(safety=None, fea={"safety": 4.0}), _row(safety=None, fea={"safety": 5.0})]}
    brace = verdicts.wood_brace(run, {"joints": J})
    assert brace["joints_n"] == 1 and verdicts.brace_why(brace) == "1 joint not checked"
    J["rows"].append(_row(safety=None, fea={"safety": 6.0}))
    assert verdicts.wood_brace(run, {"joints": J}) is None                          # all three read: nothing left


CASE = {"name": "standing on it", "safety": 3.8, "holds": True, "governs": "fea", "fea": {"safety": 3.8},
        "joints": {"chain": False, "n": 19, "rows": [], "unchecked": ["it rests on more supports one way than the other"]}}
RUN = {"min_safety": 2.0, "safety": 3.8, "spacing_mm": 3.0, "thinnest_mm": 19.05, "across": 6.35, "cases": [CASE]}


def test_as_theo_s_222_answer_stands_a_pass_on_unchecked_joints_is_a_tick_with_its_note():
    v = verdicts.case(RUN, CASE)
    assert verdicts.JOINT_CAP == "holds"
    assert v["kind"] == "holds" and v["counts_as_pass"] and v["why"] == "19 joints not checked"


def test_the_one_switch_makes_it_not_checked_everywhere(monkeypatch):
    """#383 rule 2, ready for Theo's word: one line, and the case, the run, a close case and the goal all say it."""
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")
    v = verdicts.case(RUN, CASE)
    assert v["kind"] == "unchecked" and not v["counts_as_pass"] and v["why"] == "19 joints not checked"
    assert verdicts.run(RUN)["kind"] == "unchecked"
    close = {**CASE, "safety": 2.2, "fea": {"safety": 2.2}}
    assert verdicts.case({**RUN, "safety": 2.2, "cases": [close]}, close)["kind"] == "unchecked"
    assert verdicts.goal(True, joints="joints not checked")["kind"] == "unchecked"
    assert verdicts.summary({"pass": 1, "joints": 1})["kind"] == "unchecked"


def test_the_design_s_view_and_the_part_s_view_read_alike(tmp_path):
    """The part's card said "Not checked yet for a seat: …" (amber) and the design's card didn't (green)."""
    from .test_check_own_frame import _stool

    store = _stool(tmp_path)
    state = design_api.design_state(store)
    part = next(c for c in answers.part(store, state, "stool") if c["key"] == "work")
    whole = next(c for c in answers.design(store, state) if c["key"] == "work")
    seat = [ln["text"] for ln in part["lines"] if ln["text"].startswith("Not checked yet for a seat")]
    assert seat and seat[0] in [ln["text"] for ln in whole["lines"]]
    assert whole["status"] == part["status"] == "warn"


def test_an_older_run_naming_none_keeps_the_card_s_words_both_ways(tmp_path, monkeypatch):
    """#413 moved the row: a joint the check credits a fixing for is a row of its own, the rest a named limit
    (test_joints_row_clears). A run with no named list falls back to the card's words, never a tick it can't clear."""
    from .test_check_own_frame import _stool

    store = _stool(tmp_path)
    p = {"id": "stool", "version": store.design.part("stool").version}
    run = {**RUN, "version": p["version"]}
    rows, limits = fixes._run_rows(store, p, run, "the designer")            # Theo's #222 stands: a known limit
    assert "joints_unchecked" not in [r["id"] for r in rows]
    assert limits == ["Not checked by hand: it rests on more supports one way than the other"]
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")                  # flipped: an older run, nothing named
    rows, limits = fixes._run_rows(store, p, run, "the designer")            # in it, keeps the card's words (#413)
    assert not [r for r in rows if r["id"].startswith("joints_unchecked")]
    assert limits == ["Not checked by hand: it rests on more supports one way than the other"]