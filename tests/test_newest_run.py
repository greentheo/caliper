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


# --- #139's whole pass, the non-blocking asks (carried on #140) -------------------------------------------------------

def test_the_page_s_blocked_carve_and_lighten_hedge_on_a_coarse_run():
    """The words are the server's (``load_study.blocked``, #144 review): the page shows them as they come."""
    from caliper import load_study

    from .test_wording import _checked

    fea = {"name": "sitting", "safety": 0.53, "holds": False, "governs": "fea"}
    for coarse, carve, light in (
            (True, "its check says it fails (0.5 times over, a coarse run: the fail may be the model's): make it hold "
                   "first, then carve",
             "Its check says it fails (0.5 times over, a coarse run: the fail may be the model's): make it hold first, "
             "then lighten it"),
            (False, "it already fails (0.5 times over): make it hold first, then carve",
             "It already fails (0.5 times over): make it hold first, then lighten it")):
        check = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "safety": 0.53, "min_safety": 2,
                 "thinnest_mm": 4.0 if coarse else 19.0, "across": 4.0 / 4.6 if coarse else 19.0 / 4.6,
                 "cases": [fea if coarse else {**fea, "governs": "plate"}]}
        got = load_study.blocked(_checked([check]), "stool")
        out = _run(_page(["carveBlocked", "lightenBlocked"], extra=(
            f"const p = {{id: 'stool', version: 7, blocked: {json.dumps(got)}}};\n"
            "out = [carveBlocked(p), lightenBlocked(p)];")))
        assert out == [carve, light]


def test_the_design_card_and_the_part_card_name_the_same_wall():
    """#139's pass: the design card's hedge named the 0.25 mm webs, the part card the 5.2 mm wall at the peak."""
    run = {"spacing_mm": 4.6, "min_safety": 2, "thinnest_mm": 0.25, "thinnest_where": {"at": [108.7, -129.8, 409.0]},
           "too_thin": True, "across": 0.054, "resolved": False,
           "cases": [{"name": "250 lb person seated", "safety": 0.53, "holds": False, "governs": "fea",
                      "fea": {"at": [-46.0, 165.7, 389.0], "in": "cone skirt", "wall_mm": 5.2, "safety": 0.53}}]}
    (c,) = run["cases"]
    v = verdicts.case(run, c)
    part = answers._case_line("i_want", run, c, None, False, True)["text"]
    hedge = answers.fail_hedge(run, c, v, True)
    assert part.endswith(hedge) and "where its wall is 5.2 mm" in hedge and "0.25 mm" not in hedge
    src = open(answers.__file__).read()
    assert 'out["strength.coarse_fail"] = fail_hedge(*failed[0], inches).strip()' in src


def test_a_rule_whose_measurement_errors_is_a_fail_not_a_pass():
    """#139's pass, a survivor: a rule whose measurement errors. It reads as verdicts.report reads an error, a fail
    (rule 6: never greener than its check), with why; never a pass."""
    from types import SimpleNamespace

    from caliper import part_rules
    from caliper.spec import Assertion, Spec

    def broken(pid):
        raise ValueError("the cone won't build")

    store = SimpleNamespace(read_spec=lambda pid: Spec(part="cone", intent="a cone",
                                                       assertions=[Assertion(id="wall", expr="min_wall >= 2.85")]),
                            design=SimpleNamespace(part=lambda pid: SimpleNamespace(version=9), display_units="in"),
                            root="/nowhere", part_geometry=broken)
    (r,) = part_rules.measured(store, "cone")
    assert r["status"] == "error" and r["verdict"]["kind"] == "fails" and not r["verdict"]["counts_as_pass"]
    assert r["said"] == "wall: not measured (the cone won't build)"


def test_a_hot_voxel_in_the_printed_part_is_named_for_it_not_the_nearest_wood():
    """#139's pass, a survivor: _peak_in must keep ``within`` (the "seat top" at z 389 mm, in the cone)."""
    import numpy as np

    from caliper import load_study

    seat = {"name": "seat top", "kind": "sheet", "thickness": 19.05, "sides": [-1.0],
            "polys": [np.array([[-150, -150, 717.5], [150, -150, 717.5], [150, 150, 717.5], [-150, 150, 717.5]])]}
    ctx = {"declared": {"construction": [{"kind": "printed", "name": "cone skirt"}]}, "pieces": [seat],
           "_walls": (np.array([5.2, 0.25]), np.array([[-46.0, 165.7, 389.0], [108.7, -129.8, 409.0]]))}
    got = load_study._peak_in(ctx, np.array([-46.0, 165.7, 389.0]), 4.6)
    assert got == {"in": "cone skirt", "wall_mm": 5.2}


def test_the_page_state_rebuilds_an_older_run_s_plate_words(tmp_path):
    """#139's pass, a survivor: design_state calls plate_why on an older run's stored "only 16 of its 16"."""
    import os

    from caliper import design_api, load_study
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    pytest.importorskip("cadquery")
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box stool")
    plate = {"done": False, "piece": "seat top", "edges": 16, "edges_held": 16,
             "why": "only 16 of its 16 edges rest on another piece; the plate check covers a panel held all round"}
    run = {"id": "20261106-100518-18da", "part": "stool", "version": store.design.part("stool").version,
           "created": 1.0, "min_safety": 2, "safety": 1.67, "holds": False, "spacing_mm": 3.0,
           "cases": [{"name": "sitting", "safety": 1.67, "holds": False, "governs": "fea",
                      "fea": {"supported": True, "safety": 1.67}, "plate": plate}]}
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    (shown,) = design_api.design_state(store)["load_runs"]
    why = shown["cases"][0]["plate"]["why"]
    assert "16 of its 16" not in why and why.startswith("it's held all round, but its 16-sided outline")


def test_a_run_s_number_is_written_from_the_cases_that_ran():
    """#140's re-review: study() writes ``safety`` from run_safety, the source of every reader's number."""
    from caliper import load_study

    run, case = _unjoined()
    assert load_study.run_safety([case]) is None                                 # none ran: no number, never 0x
    ran = {**case, "name": "a foot", "safety": 2.4, "fea": {"supported": True}}
    assert load_study.run_safety([case, ran]) == 2.4
    assert load_study.run_safety([ran, {**ran, "safety": 1.9}]) == 1.9
    assert "worst = run_safety(cases)" in open(load_study.__file__).read()
