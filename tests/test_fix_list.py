"""CALI-189 (#300) slice A — "Things to fix" under *Will it work?*: what's measured wrong, each with a tick, its fix, its
kind and its cost; the known limits apart, with no tick. Runs are written as the studies write them, synthetic, never
Theo's designs; no FEA, no Claude.

Theo, reading step-stool-5 v6's *Will it work?*: "give me some check boxes and if I check and submit them, it will go
over to the builder and make those build changes and rebuild"."""

import json
import os

import pytest

from caliper import design_api, fixes, review
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL
from .test_make_it_better import NEED, _check, _plate, _store

pytest.importorskip("cadquery")

STRIPS = "inside corner fillet strips"


def _list(store, pid="stool", **kw):
    return fixes.listed(store, design_api.design_state(store), pid, **kw)


def _by_id(got):
    return {r["id"]: r for r in got["rows"]}


@pytest.fixture(autouse=True)
def _no_findings(monkeypatch):
    """The after-build findings are their own test; elsewhere they find nothing (a box stool has no plan)."""
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [], "checks": 0})


def test_v6_s_unsized_strips_are_one_choice_and_its_joints_a_known_limit(tmp_path):
    """v6's fillet strips: remove them, or give them a size, as one row; checking finer wouldn't see them, so it isn't
    offered; and its joints, taken as solid wood, are a known limit, never a row."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 2.15, thinnest=19.05, spacing=4.76, unsized=[STRIPS],
           unseen=[{"mm": None, "piece": STRIPS}], wood_joints=4, finer={"spacing_mm": 3.3, "minutes": 12})
    got = _list(store)
    (row,) = got["rows"]
    assert row["id"] == "unsized" and row["measured"]
    assert row["problem"] == "The inside corner fillet strips aren't checked: their size isn't declared"
    assert [c["fix"] for c in row["choices"]] == ["Remove the inside corner fillet strips",
                                                 "Give the inside corner fillet strips a declared size"]
    assert {c["kind"] for c in row["choices"]} == {"designer"}
    assert row["choices"][0]["cost"] == "a designer edit on the stool (one Claude call)"
    assert got["limits"] == ["Its joints aren't checked: the check takes its 4 joints as solid wood"]


def test_a_case_too_coarse_to_see_its_wall_is_checked_again_finer_with_its_time(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 2.6, thinnest=4.0, spacing=4.0, finer={"spacing_mm": 1.3, "minutes": 12})
    (row,) = _list(store)["rows"]
    assert row["id"] == "finer" and row["problem"] == ("A foot: not resolved, the check was too coarse to see its "
                                                       "thinnest wall")
    (c,) = row["choices"]
    assert c == {"fix": "Check it again at 1.3 mm", "kind": "check", "cost": "a finer check, about 12 min", "spacing_mm": 1.3}


def test_too_coarse_with_no_finer_check_that_could_see_it_is_a_known_limit(tmp_path):
    from caliper import load_study as L

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 2.6, thinnest=4.0, spacing=4.0)
    got = _list(store)
    assert got["rows"] == [] and L.NOT_CHECKED in got["limits"]


def test_a_failing_plate_proposes_the_smallest_stock_sheet_that_clears_it_as_a_number(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {"top": "t"}})
    (row,) = _list(store)["rows"]
    assert row["id"] == "plate:top" and row["problem"] == f"The top fails by the plate check: about 1.4× where it needs {NEED}×"
    (c,) = row["choices"]
    # 5/8 in clears 2 at 2.3x; 1/2 in (1.4x) doesn't: the smallest stock sheet that does
    assert c == {"fix": "Make the top from 5/8 in instead of 1/2 in", "kind": "number", "cost": "a number change, at once",
                 "param": "t", "value": 15.875, "unit": "mm"}


def test_a_failing_plate_with_no_parameter_for_its_sheet_is_the_designer_s(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    (row,) = _list(store)["rows"]
    assert [(c["fix"], c["kind"]) for c in row["choices"]] == [("Make the top from 5/8 in instead of 1/2 in", "designer")]


def test_a_wall_that_buckles_proposes_a_thicker_stock_sheet_or_a_brace(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    wall = {"done": True, "piece": "left side", "thickness_mm": 19.05, "safety": 1.2, "load_n": 900, "down": True}
    _check(store, "stool", 1.2, governs="buckling", sheet={"pieces": {"left side": "t"}})
    run = _run(store)
    run["cases"][0].update(governs="buckling", buckling=[wall])
    _resave(store, run)
    (row,) = _list(store)["rows"]
    assert row["id"] == "buckling:left side"
    assert row["problem"] == f"The left side buckles under a foot: about 1.2× where it needs {NEED}×"
    # its buckling load goes as t³: 19.05 × (2/1.2)^(1/3) = 22.6 mm, so 1 in, the next stock sheet
    assert [(c["fix"], c["kind"]) for c in row["choices"]] == [("Make the left side 1 in instead of 3/4 in", "number"),
                                                              ("Add a brace to the left side", "designer")]
    assert row["choices"][0]["value"] == 25.4


def test_a_check_of_an_older_version_is_checked_again_and_nothing_else_is_said_of_it(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    store.write_part("stool", BOX_STOOL + "\n# again\n", intent="again")
    (row,) = _list(store)["rows"]
    assert row["id"] == "stale" and row["problem"] == "Its strength check is of v1, not this version"
    assert row["choices"] == [{"fix": "Check it again", "kind": "check", "cost": "a check, about 1 min"}]


def test_a_front_edge_nobody_stands_on_is_the_designer_s_to_add(tmp_path, monkeypatch):
    from caliper import consistency

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1)
    monkeypatch.setattr(consistency, "bare_edge", lambda store, pid: "the top is held on two sides, and no load stands on its free edge")
    (row,) = _list(store)["rows"]
    assert row["id"] == "edge" and row["problem"].startswith("The top is held on two sides")
    assert row["choices"][0]["fix"] == "Add a case standing at its free edge"


def test_an_after_build_finding_naming_the_part_is_a_row_and_one_naming_another_isn_t(tmp_path, monkeypatch):
    store = _store(tmp_path, BOX_STOOL, "stool")
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [
        {"kind": "fit", "parts": ["stool", "rail"], "said": "the rail has 19.1 mm of play in stool's pocket",
         "fix": "Size stool's pocket to the rail: 0.2 mm a side.", "measured": True},
        {"kind": "mirror", "parts": ["other"], "said": "x", "fix": "y", "measured": True}]})
    (row,) = _list(store)["rows"]
    assert row["problem"] == "The rail has 19.1 mm of play in stool's pocket" and row["measured"]
    assert row["choices"][0] == {"fix": "Size stool's pocket to the rail: 0.2 mm a side", "kind": "designer",
                                 "cost": "a designer edit on the stool (one Claude call)"}


def test_a_broken_rule_is_a_row(tmp_path, monkeypatch):
    from caliper import part_rules

    store = _store(tmp_path, BOX_STOOL, "stool")
    monkeypatch.setattr(part_rules, "failing", lambda rules: [{"said": "the wall is at least 3 mm"}])
    (row,) = _list(store)["rows"]
    assert row["problem"] == "It breaks its rule the wall is at least 3 mm"
    assert row["choices"][0]["kind"] == "designer"


def test_a_part_that_holds_with_nothing_measured_wrong_has_no_rows(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1)
    # a plywood box's joints are taken as solid wood: its known limit, never a row
    assert _list(store) == {"part": "stool", "rows": [],
                            "limits": ["Its joints aren't checked: the check takes its joints as solid wood"]}


def test_the_list_makes_no_model_call():
    import inspect

    src = inspect.getsource(fixes)
    assert "llm" not in src and "chat" not in src and "anthropic" not in src.lower()


def test_the_route_lists_them(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    c = TestClient(create_app())
    got = c.get(f"/api/designs/{store.design.slug}/parts/stool/fixes")
    assert got.status_code == 200 and [r["id"] for r in got.json()["rows"]] == ["plate:top"]
    assert c.get(f"/api/designs/{store.design.slug}/parts/nope/fixes").status_code == 404


# --- the page --------------------------------------------------------------------------------------------------------

def _page(extra):
    from .test_carve_click import _page as page, _run

    return _run(page(["fixesView", "fixRow"], consts=["esc"], extra=extra))


ROWS = {"part": "stool", "rows": [
    {"id": "unsized", "problem": "The strips aren't checked: their size isn't declared", "part": "stool", "measured": True,
     "choices": [{"fix": "Remove the strips", "kind": "designer", "cost": "a designer edit on the stool (one Claude call)"},
                 {"fix": "Give the strips a declared size", "kind": "designer", "cost": "a designer edit on the stool (one Claude call)"}]},
    {"id": "plate:top", "problem": "The top fails by the plate check", "part": "stool", "measured": True,
     "choices": [{"fix": "Make the top from 5/8 in instead of 1/2 in", "kind": "number", "cost": "a number change, at once",
                  "param": "t", "value": 15.875, "unit": "mm"}]}],
    "limits": ["Its joints aren't checked: the check takes its 4 joints as solid wood"]}


def test_the_page_draws_each_row_with_a_tick_its_choices_and_the_limits_apart():
    html = _page(f"out = fixesView({json.dumps(ROWS)}, {{}});")
    assert html.count('type="checkbox"') == 2 and html.count('data-fix-tick=') == 2
    assert 'type="radio"' in html and "Remove the strips" in html and "Give the strips a declared size" in html
    assert html.count("measured") >= 2 and "a number change, at once" in html
    limits = html[html.index("Known limits"):]
    assert "Its joints aren't checked" in limits and 'type="checkbox"' not in limits      # said, never ticked
    assert html.index('data-fix-row="plate:top"') < html.index("Known limits")


def test_a_reworded_or_added_row_is_the_person_s_words_never_measured():
    mine = {"untick": ["plate:top"], "words": {"unsized": "Take the strips off"},
            "own": [{"fix": "round the top's corners"}]}
    html = _page(f"out = fixesView({json.dumps(ROWS)}, {json.dumps(mine)});")
    row = html[html.index('data-fix-row="unsized"'):html.index('data-fix-row="plate:top"')]
    assert "Take the strips off" in row and "your words" in row and "measured" not in row
    top = html[html.index('data-fix-row="plate:top"'):html.index("round the top")]
    assert 'data-fix-tick="plate:top"' in top and "checked" not in top.split('data-fix-tick="plate:top"')[1].split(">")[0]
    own = html[html.index('data-fix-own="0"'):html.index("Known limits")]
    assert "your words" in own and "measured" not in own


def test_the_card_has_the_list_under_will_it_work():
    import inspect  # noqa: F401

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "api('GET', `/api/designs/${S.slug}/parts/${part}/fixes`)" in src
    # the first draw and the fill when the answers come in both paint it: the fill with qlines alone dropped it
    assert src.count("cardLines(") == 3 and "innerHTML = qlines(c)" not in src
    assert "<div class=\"qlines\" id=\"q-${k}\">${cardLines(k, c)}</div>" in src
    assert "card.querySelector('.qlines').innerHTML = cardLines(c.key, c);" in src


def _run(store):
    from caliper import load_study

    return load_study.list_runs(store, "stool")[0]


def _resave(store, run):
    from caliper import load_study

    with open(os.path.join(load_study.runs_dir(store), run["id"], "run.json"), "w") as f:
        json.dump(run, f)
