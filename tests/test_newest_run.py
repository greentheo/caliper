"""CALI-123 (#138) — no card reads greener than the newest strength run.

From the reviewer's cards-only re-pre-flight of Theo's bar stool on main: the design card said "! Holds … 2.58x"
from the v1 scorecard while the part card and Studies said v4 doesn't hold at 1.7x; the scorecard panel kept v1's
✓ rows; v3's runs, whose load never reached a support, read "doesn't hold, 0x"; and a cold /answers took 2 min."""

import json

import pytest

from caliper import answers, printing, verdicts

from .test_carve_click import _page, _run

GOAL = {"id": "holds", "metric": "strength.safety", "op": ">=", "limit": 2, "source": "assumed",
        "label": "holds a 250 lb person sitting, 2× safety"}


def _state(card_safety=2.58):
    return {"goals": {"checks": [GOAL]}, "parts": [{"id": "i_want", "version": 7}],
            "scorecards": [{"metrics": {"strength.safety": {"value": card_safety, "unit": "×"}},
                            "versions": {"i_want": 1}, "outdated": True}]}


# --- 1. the design card takes the newest run, and says how old it is --------------------------------------------------

def test_the_design_line_takes_the_newest_run_over_an_older_card():
    (line,) = answers.held_to(_state(), {"strength.last": {"part": "i_want", "version": 4, "now": 7, "safety": 1.67}})
    assert line["text"] == ("✗ Holds a 250 lb person sitting, 2× safety (assumed): last checked on v4: 1.7x, needs 2x · "
                            "v7 not checked yet.")
    assert line["status"] == "bad"


def test_a_newest_run_that_held_is_amber_and_old_not_a_tick():
    (line,) = answers.held_to(_state(), {"strength.last": {"part": "i_want", "version": 4, "now": 7, "safety": 2.4}})
    assert line["text"] == "! Holds a 250 lb person sitting, 2× safety (assumed): last checked on v4: 2.4x · v7 not checked yet."
    assert line["status"] == "warn"


def test_a_card_newer_than_the_last_run_still_reads_as_the_card():
    state = _state()
    state["scorecards"][0]["versions"] = {"i_want": 5}
    (line,) = answers.held_to(state, {"strength.last": {"part": "i_want", "version": 4, "now": 7, "safety": 1.67}})
    assert "last checked on v4" not in line["text"] and "score it again" in line["text"]


# --- 2. a stale scorecard's rows: no ✓, said as of when ----------------------------------------------------------------

def test_a_stale_scorecard_row_is_no_tick_and_says_as_of_when():
    out = _run(_page(["scoreMark", "asOf"], consts=["esc"], extra=(
        "const card = {versions: {i_want: 1}};\n"
        "out = [asOf(card), scoreMark({status: 'pass'}, true, asOf(card)), scoreMark({status: 'pass'}, false, ''),"
        " scoreMark({status: 'fail'}, true, asOf(card)), asOf({versions: {a: 1, b: 2}})];")))
    assert out[0] == "as of v1"
    assert "✓" not in out[1] and "·" in out[1] and "amber" in out[1] and 'title="as of v1"' in out[1]
    assert out[2] == "✓"
    assert "✗" in out[3]                                                         # a fail stays a fail
    assert out[4] == "as of an older version"


# --- 3. a check whose load never reached a support isn't a 0x ✗ --------------------------------------------------------

def _unjoined():
    case = {"name": "250 lb person seated", "lb": 250, "factor": 1.5, "holds": False, "safety": 0.0, "governs": "fea",
            "fea": {"supported": False}, "why": "nothing connects where it's pushed to where it's held"}
    return {"id": "r3", "part": "i_want", "version": 3, "min_safety": 2, "safety": 0.0, "holds": False,
            "cases": [case]}, case


def test_a_check_that_couldn_t_run_is_unchecked_with_its_reason():
    run, case = _unjoined()
    v = verdicts.case(run, case)
    assert v["kind"] == "unchecked" and not v["counts_as_pass"] and v["why"] == case["why"]
    assert verdicts.run(run)["kind"] == "unchecked" and "0" not in verdicts.run(run)["short"]
    assert answers.ran_safety(run) is None                                     # no 0x into the design's minimum
    line = answers._case_line("i_want", run, case, None, False, True)
    assert line["text"] == ("250 lb person seated: not checked: nothing connects where it's pushed to where it's held. "
                            "Check where it's held and pushed, then check it again.")
    assert line["status"] == "warn"


def test_a_case_that_ran_still_counts_beside_one_that_couldn_t():
    run, case = _unjoined()
    ran = {**case, "name": "a foot", "holds": True, "safety": 2.4, "fea": {"supported": True}}
    run["cases"].append(ran)
    assert answers.ran_safety(run) == 2.4


def test_the_history_line_says_why_not_0x():
    src = open(__file__.replace("tests/test_newest_run.py", "src/caliper/web/static/design.js")).read()
    line = next(ln for ln in src.splitlines() if "h.kind === 'load' && h.action === 'studied'" in ln)
    assert "h.verdict.kind === 'unchecked' && h.verdict.why" in line and "['holds', 'fails'].includes(h.verdict.kind)" in line


# --- 4. a cold /answers sliced every printed piece three times ---------------------------------------------------------

def test_a_piece_is_sliced_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_estimate", lambda *a: calls.append(a) or {"hours": 1.0, "filament_g": 10.0})
    stl = tmp_path / "a.stl"
    stl.write_bytes(b"solid a\nendsolid a\n")
    first = printing.estimate(str(stl), "petg", (220, 220, 250))
    first["hours"] = 99                                                         # a caller's change isn't kept
    assert printing.estimate(str(stl), "petg", (220, 220, 250)) == {"hours": 1.0, "filament_g": 10.0}
    assert len(calls) == 1
    stl.write_bytes(b"solid b\nendsolid b\n")                                   # another piece: sliced
    printing.estimate(str(stl), "petg", (220, 220, 250))
    printing.estimate(str(stl), "pla", (220, 220, 250))                         # another plastic: sliced
    assert len(calls) == 3


# --- #140 review: the survivors pinned, and the number written where it's made ----------------------------------------

def _tube_with_an_unjoined_check(tmp_path, monkeypatch):
    import os

    from caliper import load_study
    from caliper.design import DesignStore

    from .test_resolved import TUBE

    pytest.importorskip("cadquery")
    monkeypatch.setenv("CALIPER_SLICER", "")                        # rough print times: no slicer in a test
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    run, case = _unjoined()
    run.update({"id": "20261105-204152-4419", "part": "tube", "version": store.design.part("tube").version,
                "created": 1.0, "spacing_mm": 3.0})
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    # as an older run stored it: holds False and 0.0, and a verdict that said "doesn't hold"
    store.append_history("tube", {"kind": "load", "action": "studied", "run": run["id"], "cases": 1, "safety": 0.0,
                                  "holds": False, "verdict": {"kind": "fails", "word": "doesn't hold"}})
    return store


def test_studies_says_why_a_check_couldn_t_run_with_no_number():
    from caliper import studies

    run, _ = _unjoined()
    assert studies._headline("load", run) == ("not checked: nothing connects where it's pushed to where it's held", None)


def test_an_older_history_line_reads_its_run_s_verdict_through_the_page_state(tmp_path, monkeypatch):
    from caliper import design_api

    store = _tube_with_an_unjoined_check(tmp_path, monkeypatch)
    (p,) = design_api.design_state(store)["parts"]
    (h,) = [h for h in p["history"] if h.get("kind") == "load"]
    assert h["verdict"]["kind"] == "unchecked" and "nothing connects" in h["verdict"]["why"]


def test_the_scorecard_gives_no_number_for_a_check_that_couldn_t_run(tmp_path, monkeypatch):
    from caliper import scorecard

    store = _tube_with_an_unjoined_check(tmp_path, monkeypatch)
    card = scorecard.compute(store)
    assert "strength.safety" not in card["metrics"] and "strength.tube.safety" not in card["metrics"]
    assert any("nothing connects" in (c.get("note") or "") for c in card["checks"] if c.get("metric") == "strength.safety"), card["checks"]


def test_the_slicer_key_holds_its_infill_and_a_timeout_isn_t_remembered(tmp_path, monkeypatch):
    import subprocess

    calls = []
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_estimate", lambda *a: calls.append(a) or {"hours": 1.0})
    stl = tmp_path / "a.stl"
    stl.write_bytes(b"solid a\nendsolid a\n")
    printing.estimate(str(stl), "petg", (220, 220, 250), infill=0.2)
    printing.estimate(str(stl), "petg", (220, 220, 250), infill=0.4)               # another infill: sliced again
    assert len(calls) == 2
    # a slicer that times out: said so, and sliced again next time
    monkeypatch.undo()
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/true")
    ran = []

    def times_out(*a, **k):
        ran.append(a)
        raise subprocess.TimeoutExpired(a[0], 600)

    monkeypatch.setattr(printing.subprocess, "run", times_out)
    box = pytest.importorskip("trimesh").creation.box((10, 10, 10))
    box.export(str(stl))
    got = printing.estimate(str(stl), "petg", (220, 220, 250))
    assert got["trust"] == "rough" and "the slicer timed out" in got["from"] and "_retry" not in got
    printing.estimate(str(stl), "petg", (220, 220, 250))
    assert len(ran) == 2
