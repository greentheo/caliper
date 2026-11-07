"""CALI-112 (#132 review) — the foreman's sweep: what the first guards missed, each through its reader.

A. a design-level verdict covered only some of its parts (an unchecked part, an errored study, a partial kid's book,
   an older frame run); B. ``stale`` was never produced; C. readers that still decided a pass themselves (carve's
   whole part, lightening estimates, the plate check's rows, the first reply's order, a part's rules, a rule's
   holds_now). Each is pinned here; the widened guards in test_verdicts.py fail on any of them coming back."""

import json
import os
import time

import pytest

from caliper import answers, chat, design_api, firstrun, kidbook, load_study, promote, studies, verdicts
from caliper.design import DesignStore

from .test_resolved import TUBE

pytest.importorskip("cadquery")

GOAL = """written_by: caliper
checks:
- id: strength_foot
  label: holds a foot (40 lb), 2 times over
  metric: strength.safety
  op: '>='
  limit: 2.0
  source: assumed
"""


def _store(tmp_path, parts=("tube",), goals=GOAL):
    store = DesignStore.create("printed tubes", base=str(tmp_path / "designs"))
    for pid in parts:
        store.write_part(pid, TUBE, intent="a printed tube")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(goals)
    return store


def _run(store, pid, version, safety=3.1, plate=None):
    """A strength run on file, as load_study writes one (no FEA here)."""
    rid = f"r-{pid}-{version}-{int(time.time() * 1e6)}"
    folder = os.path.join(load_study.runs_dir(store), rid)
    os.makedirs(folder)
    case = {"name": "a foot", "lb": 40, "factor": 2.0, "safety": safety, "holds": safety >= 2.0, "governs": "fea",
            "breaks_lb": round(80 * safety), "fea": {"safety": safety, "supported": True, "deflection_mm": 0.2}, **({"plate": plate} if plate else {})}
    rec = {"id": rid, "part": pid, "kind": "load", "created": time.time(), "version": version, "min_safety": 2.0,
           "cases": [case], "safety": safety, "holds": safety >= 2.0, "spacing_mm": 0.5, "thinnest_mm": 4.0, "across": 8.0}
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(rec, f)
    return rec


# --- B. an older run is "older version", everywhere -----------------------------------------------------------------
def test_a_check_of_an_older_version_never_reads_holds(tmp_path):
    store = _store(tmp_path)
    _run(store, "tube", 1, plate={"done": True, "by_thickness": [{"label": "1/2 in", "thickness_mm": 12.7,
                                                                 "safety_across": 4.0, "safety": 8.0}]})
    store.write_part("tube", TUBE.replace('"wall": 4.0', '"wall": 5.0'), intent="a printed tube")      # v2
    state = design_api.design_state(store)
    (run,) = state["load_runs"]
    assert run["verdict"]["kind"] == "stale" and run["cases"][0]["verdict"]["kind"] == "stale"
    (row,) = run["cases"][0]["plate"]["by_thickness"]
    assert not row["verdict"]["counts_as_pass"]                  # the plate check's Use: not on an older case
    lines = [ln for ln in answers.answers(store, state, "tube")[1]["lines"] if ln.get("study") == "load"]
    assert lines and all(ln["status"] != "ok" and not ln["text"].startswith("Holds") for ln in lines), lines
    assert "verdict OLDER VERSION" in chat._facts(store, None)
    rows = studies.index(store, {"load": load_study.list_runs(store)}, state["parts"])["runs"]
    assert rows[0]["stale"] and rows[0]["ok"] is not True


def test_a_package_of_older_versions_isn_t_ready_to_cut(tmp_path):
    rel = {"ready": True, "versions": {"tube": 1}}
    assert verdicts.release(rel, {"tube": 1})["kind"] == "holds"
    assert verdicts.release(rel, {"tube": 2})["kind"] == "stale" and not verdicts.release(rel, {"tube": 2})["counts_as_pass"]


# --- A. a design's verdict never leaves a part out -------------------------------------------------------------------
def test_a_part_left_unchecked_isn_t_covered_by_the_rest(tmp_path):
    store = _store(tmp_path, ("left", "right"))
    _run(store, "left", 1)                                       # the right tube has loads() and no check
    state = design_api.design_state(store)
    now = answers.measured(store, state)
    assert now["strength.safety"] == 3.1 and now["strength.unchecked"].startswith("not checked yet on the right")
    (line,) = [ln for ln in answers.held_to(state, now) if "foot" in ln["text"]]
    assert line["status"] == "warn" and not line["text"].startswith("✓"), line
    assert "for the rest, but not checked yet on the right" in line["text"]


def test_an_errored_study_leaves_the_goal_unknown_and_the_book_not_ready(tmp_path, monkeypatch):
    from caliper import release, scorecard

    store = _store(tmp_path, ("left", "right"))
    _run(store, "left", 1)

    def boom(store_, pid, **k):
        raise ValueError("the right tube won't voxelize")
    monkeypatch.setattr(load_study, "study", boom)
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_foot"]
    assert check["status"] == "unknown" and "the right's strength couldn't be checked" in check["note"]
    assert not verdicts.summary(card["summary"])["counts_as_pass"] and "Ready to cut" not in release._status(card)


def test_the_kids_book_s_your_turn_needs_every_part_to_hold():
    holds = {"name": "a foot", "safety": 3.1, "verdict": {"kind": "holds"}}
    assert kidbook._strength_page({"left": [holds]}, ["left"])["title"] == "Test it"
    assert kidbook._strength_page({"left": [holds]}, ["left", "right"])["title"] == "Don't stand on it yet"
    assert kidbook._strength_page({}, ["left"])["title"] == "Don't stand on it yet"
    assert kidbook._strength_page({}, [])["title"] == "Don't stand on it yet"


def test_an_older_frame_run_isn_t_the_frame_holding(tmp_path):
    store = _store(tmp_path, goals="written_by: caliper\nchecks: []\n")
    state = design_api.design_state(store)
    state["frame_runs"] = [{"part": "tube", "drawn": {"safety": 3.0}, "min_safety": 2.0}]   # no version: older
    work = answers.answers(store, state, "tube")[1]["lines"]
    (frame,) = [ln for ln in work if ln.get("study") == "frame"]
    assert frame["status"] == "warn" and "on an older version" in frame["text"] and "holds" not in frame["text"]
    state["frame_runs"][0]["version"] = 1
    (frame,) = [ln for ln in answers.answers(store, state, "tube")[1]["lines"] if ln.get("study") == "frame"]
    assert frame["text"].startswith("The frame holds") and frame["status"] == "ok"


# --- C. readers that decided a pass themselves -----------------------------------------------------------------------
CARVED = {"index": 2, "holds": True, "safety": 3.0, "whole_holds": False, "whole": 0.6, "removed": 0.3,
          "saved_g": 120, "printed_g": 400}


def test_a_carve_whose_whole_part_fails_never_says_the_lightest_that_holds(tmp_path, monkeypatch):
    from caliper import carve

    assert verdicts.carve_step(CARVED)["kind"] == "fails"
    assert verdicts.carve_step({**CARVED, "whole_holds": True}, filled="a block")["kind"] == "untrusted"
    rec = {"status": "cancelled", "steps": 4, "stations": [CARVED], "best": 2}
    assert "lightest that held" not in studies._headline("carve", rec)[0]
    store = _store(tmp_path, goals="written_by: caliper\nchecks: []\n")
    monkeypatch.setattr(carve, "study", lambda *a, **k: {"stations": [CARVED], "best": 2, "weak": "", "share": "printed"})
    got = chat.carve_part(store, "tube")
    assert not got.ok and "The lightest that holds" not in got.reply and "the whole part is then 0.6x" in got.reply


def test_a_lightening_estimate_is_never_the_lightest_that_holds():
    est = {"index": 5, "holds": True, "estimate": True, "safety": 2.4, "saved_lb": 3.0, "label": "1/2 in"}
    real = {"index": 2, "holds": True, "safety": 2.8, "saved_lb": 1.0}
    assert verdicts.lighten_step(est)["kind"] == "estimate" and not verdicts.lighten_step(est)["counts_as_pass"]
    text, ok = studies._headline("lighten", {"stations": [real, est]})
    assert text.startswith("up to 1 lb lighter") and "estimate" not in text and ok is True


def test_the_first_reply_puts_a_warning_before_what_holds():
    cards = [{"q": "Will it work?", "key": "work", "lines": [
        {"text": "Holds a foot, 3.1 times over.", "status": "ok"},
        {"text": "Holds a hand, 4 times over.", "status": "ok"},
        {"text": "Not trusted yet: it ran on a filled-in shape.", "status": "warn"}]}]
    reply = firstrun.summary(cards)
    assert "Not trusted yet" in reply


@pytest.mark.parametrize("statuses,status,starts", [
    (["pass", "pass"], "ok", "Its 2 rules all pass."),
    (["pass", "deferred"], "warn", "1 of its 2 rules pass; 1 not checked yet"),
    (["pass", "error"], "bad", "1 of its rules fail"),
])
def test_a_part_s_rules_all_pass_only_when_every_one_ran(statuses, status, starts):
    ln = answers._rules_line([{"id": f"r{i}", "status": s} for i, s in enumerate(statuses)])
    assert ln["status"] == status and ln["text"].startswith(starts), ln


def test_a_rule_whose_holding_isn_t_known_is_never_a_tick():
    p = promote.Proposal.from_dict({"id": "r", "expr": "x > 0", "level": "part", "part": "tube"})
    assert p.holds_now is None
    text = p.describe()
    assert "✓ it holds now" not in text and "isn't known yet" in text


# --- merged with #125 and #129: their readers ask the verdict too ---------------------------------------------------
def test_an_unweighed_total_is_not_checked_never_the_last_card_s_lower_number(tmp_path, monkeypatch):
    """#125's unknown weight, through the design card: even with an older card's number on file it's "not checked",
    never that number's ✓ (#132's merge with #125)."""
    from caliper import construction

    store = _store(tmp_path, goals="written_by: caliper\nchecks:\n- id: light\n  label: keeps total weight down\n"
                                   "  metric: weight.total_lb\n  op: <=\n  limit: 10.0\n  source: assumed\n")
    state = design_api.design_state(store)
    state["scorecards"] = [{"metrics": {"weight.total_lb": {"value": 0.1, "unit": "lb"}}, "versions": {"tube": 1},
                            "summary": {"pass": 1, "fail": 0, "unknown": 0}, "checks": []}]

    def throws(*a, **k):
        raise ValueError("Not all meshes are volumes!")
    monkeypatch.setattr(construction, "printed_solid", throws)
    now = answers.measured(store, state)
    assert now["weight.total_lb"] is None
    (line,) = [ln for ln in answers.held_to(state, now) if "weight down" in ln["text"]]
    assert line["status"] == "warn" and "not checked" in line["text"] and "✓" not in line["text"], line
    assert verdicts.goal(None, incomplete="why")["why"] == "why"


# --- #132 review, round 2: the release panel, the history badge, and the small asks -------------------------------
def _rep(*statuses):
    return {"results": [{"id": f"r{i}", "status": st} for i, st in enumerate(statuses)], "said": "…"}


@pytest.mark.parametrize("statuses,kind,word", [
    (("pass", "fail"), "fails", "doesn't hold"),
    (("pass", "deferred"), "waiting", "not all checked"),
    (("deferred",), "waiting", "nothing checked yet"),
    ((), "waiting", "nothing checked yet"),
    (("pass", "pass"), "holds", "holds"),
])
def test_a_report_s_verdict_fails_only_with_a_failure(statuses, kind, word):
    v = verdicts.report(_rep(*statuses))
    assert (v["kind"], v["word"]) == (kind, word) and (v["status"] == "bad") is (kind == "fails")


def test_the_history_stores_the_report_s_verdict_and_the_page_reads_it(tmp_path):
    from caliper.evaluate import AssertionResult, Report

    store = _store(tmp_path, goals="written_by: caliper\nchecks: []\n")
    rep = Report([AssertionResult("a", "x > 0", "pass", 1), AssertionResult("b", "y > 0", "deferred", None)])
    store.write_part("tube", TUBE, intent="a printed tube", report=rep.to_dict())
    h = store.history("tube")[-1]
    assert h["result"] == "waiting" and h["word"] == "not all checked" and "all_pass" not in h.values()
    only = Report([AssertionResult("b", "y > 0", "deferred", None)])
    store.write_part("tube", TUBE.replace('"wall": 4.0', '"wall": 4.5'), intent="a printed tube", report=only.to_dict())
    shown = [x for x in design_api.design_state(store)["parts"][0]["history"] if x.get("kind") == "revision"]
    assert shown[-1]["verdict"]["word"] == "nothing checked yet" and shown[-1]["verdict"]["status"] != "bad"
    assert shown[-2]["verdict"]["kind"] == "waiting"
    assert verdicts.history({"result": "all_pass"})["kind"] == "holds"     # a record from before: single-part


def test_the_release_panel_reads_the_release_s_verdict(tmp_path):
    store = _store(tmp_path, goals="written_by: caliper\nchecks: []\n")
    rel = {"id": "001", "ready": True, "versions": {"tube": 1}, "steps": [], "card": {"summary": {"pass": 1}}}
    store.write_part("tube", TUBE.replace('"wall": 4.0', '"wall": 5.0'), intent="a printed tube")      # v2
    assert verdicts.release(rel, {"tube": 2})["kind"] == "stale"
    waits = {**rel, "ready": False, "card": {"summary": {"pass": 1, "fail": 0, "unknown": 1}}}
    assert verdicts.release(waits, {"tube": 1})["kind"] == "waiting"          # its own reason, not "a check fails"
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "rel.verdict && rel.verdict.kind === 'holds'" in src and "rel.ready" not in src


def test_the_small_asks():
    from caliper.evaluate import AssertionResult, Report

    assert verdicts.summary(None)["kind"] == "waiting" and verdicts.summary({})["kind"] == "waiting"
    assert verdicts.meets(3.0, None)["kind"] == "waiting"
    rep = Report([AssertionResult("a", "x > 0", "pass", 1), AssertionResult("b", "y > 0", "deferred", None)])
    assert rep.to_text().startswith("Measurement report — NOT ALL CHECKED")
    assert Report([AssertionResult("a", "x > 0", "pass", 1)]).to_text().startswith("Measurement report — ALL PASS")
