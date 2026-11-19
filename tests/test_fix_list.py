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
    assert [c["fix"] for c in row["choices"]] == [                                  # Theo's three ways out (#324)
        "They're trim, not holding anything up: declare the inside corner fillet strips trim",
        "Give the inside corner fillet strips their size: a declared section, in mm",
        "Remove the inside corner fillet strips"]
    assert {c["kind"] for c in row["choices"]} == {"designer"}                       # no number turns them off here
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
    assert row["id"] == "plate:top" and row["problem"] == f"The top fails by the plate check: 1.4× where it needs {NEED}×"
    (c,) = row["choices"]
    # 5/8 in clears 2 at 2.3x; 1/2 in (1.4x) doesn't: the smallest stock sheet that does
    assert c == {"fix": "Make the top from 5/8 in instead of 1/2 in", "kind": "number", "cost": "a number change, at once",
                 "param": "t", "value": 15.875, "unit": "mm", "moves": ["top"]}


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
    assert row["problem"] == f"The left side buckles under a foot: 1.2× where it needs {NEED}×"
    # its buckling load goes as t³: 19.05 × (2/1.2)^(1/3) = 22.6 mm, so 1 in, the next stock sheet
    assert [(c["fix"], c["kind"]) for c in row["choices"]] == [("Make the left side from 1 in instead of 3/4 in", "number"),
                                                              ("Brace the left side", "designer")]
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

    return _run(page(["fixesView", "fixRow", "fixGo", "fixTicked"], consts=["esc", "fixRowKey"], extra=extra))


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
    key = {r["id"]: f"{r['id']}|{r['problem']}" for r in ROWS["rows"]}           # a row by its id and its measurement
    mine = {"untick": [key["plate:top"]], "words": {key["unsized"]: "Take the strips off"},
            "own": [{"fix": "round the top's corners"}]}
    html = _page(f"out = fixesView({json.dumps(ROWS)}, {json.dumps(mine)});")
    row = html[html.index('data-fix-row="unsized"'):html.index('data-fix-row="plate:top"')]
    assert "Take the strips off" in row and "your words" in row and "measured" not in row
    top = html[html.index('data-fix-row="plate:top"'):html.index("round the top")]
    tick = f'data-fix-tick="{key["plate:top"]}"'
    assert tick in top and "checked" not in top.split(tick)[1].split(">")[0]
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



# --- #318 review ---------------------------------------------------------------------------------------------------------

def _buckles(store, safety, down=True, sheet=None):
    wall = {"done": True, "piece": "left side", "thickness_mm": 19.05, "safety": safety, "load_n": 900, "down": down}
    _check(store, "stool", safety, sheet=sheet or {"pieces": {"left side": "t"}})
    run = _run(store)
    run["cases"][0].update(governs="buckling", buckling=[wall])
    _resave(store, run)


def test_a_plate_no_stock_sheet_clears_is_a_row_that_says_so_with_the_designer_s_choices(tmp_path):
    """reviewer-2's v7 at 500 lb: the step at 1.07x, its table to 1 in at 1.91x. It read "Nothing measured wrong"."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.07, plate={**_plate(t=19.05, rows=((15.875, "5/8 in", 0.74), (19.05, "3/4 in", 1.07),
                                                                (25.4, "1 in", 1.91))), "safety_across": 1.07},
           sheet={"pieces": {"top": "t"}})
    (row,) = _list(store)["rows"]
    # the card's numbers: 1.07 well under 2 is "1", 1.91 near it is "1.91" (answers.safety_num)
    assert row["problem"] == (f"The top fails by the plate check: 1× where it needs {NEED}×; no stock sheet clears it: "
                              "the thickest, 1 in, is 1.91×")
    assert [c["kind"] for c in row["choices"]] == ["designer"] * 3
    assert [c["fix"] for c in row["choices"]] == ["Hold the top up underneath: another support or a rail under it",
                                                 "Brace the top", "Ask it to hold less: a lighter load in its loads()"]


def test_a_failing_case_the_fea_governs_is_a_row(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.3)
    run = _run(store)
    run["cases"][0]["fea"]["in"] = "front rail"
    _resave(store, run)
    (row,) = _list(store)["rows"]
    assert row["id"] == "fails:a foot"
    assert row["problem"] == f"It doesn't hold a foot: 1.3× where it needs {NEED}×; it works hardest in the front rail"
    assert row["choices"][0]["fix"] == "Make the front rail stronger: thicker, or with a rib or a brace"


def test_a_number_that_moves_several_panels_names_them_all_and_offers_the_one_alone(tmp_path):
    """reviewer-2's v7 at 350 lb: ``ply_t`` sets all six panels, and the row said only the step."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4},
           sheet={"pieces": {"top": "ply_t", "left side": "ply_t", "right side": "ply_t"}})
    (row,) = _list(store)["rows"]
    number, alone = row["choices"]
    # the box has more panels than these three: they're named, never "every panel" (#318 re-check)
    assert number["fix"] == "Make the top, left side and right side 5/8 in (ply_t sets the top and the other two)"
    assert number["kind"] == "number"
    assert number["cost"] == "a number change, at once: it moves the top, left side and right side"
    assert number["moves"] == ["top", "left side", "right side"] and number["param"] == "ply_t"
    assert alone == {"fix": "Make the top alone from 5/8 in", "kind": "designer",
                     "cost": "a designer edit on the stool (one Claude call)"}


def test_a_failing_number_is_never_rounded_up_to_what_it_needs(tmp_path):
    """reviewer-2's v2 doctored to 1.96x: it read "about 2.0× where it needs 2×"."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _buckles(store, 1.96)
    (row,) = _list(store)["rows"]
    assert row["problem"].startswith(f"The left side buckles under a foot: 1.96× where it needs {NEED}×"), row["problem"]


def test_buckling_scales_as_t_cubed_not_t_squared(tmp_path):
    """3/4 in at 0.9x: by t³ 1 in clears it (2.13x); by t² it needs 28 mm, which no stock sheet is."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _buckles(store, 0.9)
    (row,) = _list(store)["rows"]
    assert row["choices"][0]["fix"] == "Make the left side from 1 in instead of 3/4 in" and row["choices"][0]["value"] == 25.4


def test_a_wall_no_stock_sheet_clears_says_so_from_the_plate_check_s_stock(tmp_path):
    """Theo's v2 left side at 0.69x needs 27.2 mm: past the 1 in the plate check's stock goes to, so no 1 1/2 in."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _buckles(store, 0.69)
    (row,) = _list(store)["rows"]
    assert row["problem"] == (f"The left side buckles under a foot: 0.6× where it needs {NEED}×; no stock sheet clears it: "
                              "the thickest, 1 in, is 1.6×"), row["problem"]              # the card's: cut to one place
    assert "1 1/2 in" not in json.dumps(row) and [c["fix"] for c in row["choices"]][0] == "Brace the left side"


def test_a_wall_pushed_in_its_own_plane_says_racking_isn_t_checked(tmp_path):
    from caliper.answers import RACKING

    store = _store(tmp_path, BOX_STOOL, "stool")
    _buckles(store, 1.5, down=False)
    assert RACKING in _list(store)["limits"]


def test_a_finding_that_wasn_t_measured_is_no_row(tmp_path, monkeypatch):
    store = _store(tmp_path, BOX_STOOL, "stool")
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [
        {"kind": "read", "parts": ["stool"], "said": "it looks lopsided", "fix": "even it up", "measured": False}]})
    assert _list(store)["rows"] == []


def test_the_page_keys_the_list_by_design_and_part_and_clears_it_for_another_design_but_not_your_rows():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "const fixKey = (part) => `${S.slug}/${part}`;" in src
    assert "if (first) { S.fixes = {}; S.fixOpen = null; }" in src                 # your own rows kept per design (#318)
    assert "S.fixMine = {}" not in src
    assert "S.fixes[part]" not in src and "S.fixMine[part]" not in src
    assert "const fixRowKey = (r) => `${r.id}|${r.problem}`;" in src                 # a new number is a new row


def test_the_page_says_the_problem_is_measured_and_the_fix_proposed():
    html = _page(f"out = fixesView({json.dumps(ROWS)}, {{}});")
    row = html[html.index('data-fix-row="plate:top"'):html.index("Known limits")]
    assert row.index("The top fails by the plate check") < row.index("measured") < row.index("Make the top from 5/8 in")
    assert "proposed" in row


# --- after #311, #313 and #312: joint rows and the edited loads' rows ------------------------------------------------------

def test_a_joint_that_gives_first_is_its_own_row_and_covers_its_case(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4)
    run = _run(store)
    weakest = {"pieces": ["front rail", "left side"], "between": "the front rail and the left side", "mode": "withdrawal",
               "safety": 1.4, "need": 2.0, "holds": False, "said": "two #8 screws pulled out of the front rail's edge"}
    run["cases"][0].update(governs="joint", joints={"chain": True, "n": 4, "unchecked": [], "governing": weakest, "rows": [
        weakest,
        {"pieces": ["left side", "top"], "between": "the top and the left side", "mode": "bearing", "safety": 9.0,
         "need": 2.0, "holds": True, "said": "the left side's edge bearing on the top"}]})
    _resave(store, run)
    (row,) = _list(store)["rows"]                                   # the joint's row, and no "doesn't hold" beside it
    assert row["id"] == "joint:front rail|left side"
    assert row["problem"] == ("The joint between the front rail and the left side gives first under a foot: two #8 screws "
                              f"pulled out of the front rail's edge; 1.4× where it needs {NEED}×")          # as the card
    # only what the check credits (#344): no glue block, no dado; with no count that passes, ask it to hold less
    assert [c["fix"] for c in row["choices"]] == ["Ask it to hold less: a lighter load in its loads()"]
    assert {c["kind"] for c in row["choices"]} == {"designer"}
    entry = {"pieces": ["front rail", "left side"], "kind": "butt", "fix": ["glue", "screws"], "screws": 3}
    weakest["more_screws"] = {"to": 3, "more": 1, "reads": 2.1, "entry": entry}
    _resave(store, run)
    (row,) = _list(store)["rows"]                                   # a count that passes: the JOINTS entry, its reading
    assert [(c["fix"], c["entry"]) for c in row["choices"]] == [(
        '3 #8 screws where the front rail and the left side meet, 1 more: its JOINTS entry {"pieces": ["front rail", '
        '"left side"], "kind": "butt", "fix": ["glue", "screws"], "screws": 3}; it would read 2.1×', entry)]


def test_a_joint_the_hand_check_couldn_t_place_is_a_known_limit(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1)
    run = _run(store)
    run["cases"][0]["joints"] = {"chain": True, "n": 4, "unchecked": ["the joint between the stretcher and the left side (a dowel)"],
                                 "rows": [{"pieces": ["left side", "top"], "between": "the top and the left side",
                                           "mode": "bearing", "safety": 9.0, "need": 2.0, "holds": True, "said": "x"}]}
    _resave(store, run)
    got = _list(store)
    # the card's words for a joint #311 couldn't place (answers.joint_said), and only that: the rest are checked
    assert got["rows"] == [] and got["limits"] == [
        "The joint between the stretcher and the left side (a dowel) isn't checked by hand"], got["limits"]


def test_joints_all_checked_by_hand_are_no_limit(tmp_path):
    """reviewer-2's v7 and step-stool-3 on main: "Its joints aren't checked" where #311 checks them all, false."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1, joints_checked=True)
    run = _run(store)
    run["cases"][0]["joints"] = {"chain": True, "n": 4, "unchecked": [], "rows": [
        {"pieces": ["left side", "top"], "between": "the top and the left side", "mode": "bearing", "safety": 9.0,
         "need": 2.0, "holds": True, "said": "x"}]}
    _resave(store, run)
    assert _list(store)["limits"] == []


def test_a_number_that_sets_every_panel_says_every_panel(tmp_path):
    from caliper import construction as C

    store = _store(tmp_path, BOX_STOOL, "stool")
    names = [it["name"] for it in C.declared(store, "stool")["construction"] if it.get("kind") == "sheet"]
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {n: "ply_t" for n in names}})
    (row,) = _list(store)["rows"]
    assert row["choices"][0]["fix"].startswith("Make every panel 5/8 in (ply_t sets the top and the other "), row["choices"][0]


def test_an_open_question_on_its_loads_and_a_case_turned_off_are_rows_of_their_own(tmp_path):
    from caliper import scenarios as S

    from .test_scenarios import RAISED, RATED

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a step stool")
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, {**got["scenarios"][1], "on": False}], got["supports"])
    store.write_part("stool", RAISED, intent="heavier")
    rows = _by_id(_list(store))
    q = rows["asked:stepping on the front edge"]
    assert q["problem"].startswith("You'd edited 'stepping on the front edge' to 260 lb; the design now asks 300 lb: "
                                   "checked at the design's 300 lb until you choose")
    assert [(c["fix"], c["kind"], c["take"]) for c in q["choices"]] == [("Take the design's", "loads", "design"),
                                                                       ("Keep mine", "loads", "mine")]
    off = rows["off:its rating (EN 14183, 150 kg)"]
    assert off["problem"] == "'its rating (EN 14183, 150 kg)' is turned off, so nothing checks it"
    assert off["choices"] == [{"fix": "Turn it back on", "kind": "loads", "cost": "a change to its loads, at once",
                               "scenario": "its rating (EN 14183, 150 kg)", "take": "on"}]


def test_a_case_failing_that_the_fea_doesn_t_judge_never_says_where_it_works_hardest(tmp_path):
    """reviewer-2's step-stool-3: a joint governs, and the catch-all named a panel the card doesn't."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.3)
    run = _run(store)
    run["cases"][0].update(governs="joint", joints={"chain": False, "n": 4, "rows": [],
                                                    "unchecked": ["its load path isn't a simple chain"]})
    run["cases"][0]["fea"]["in"] = "side front"
    _resave(store, run)
    (row,) = _list(store)["rows"]
    assert "works hardest" not in row["problem"] and "side front" not in json.dumps(row), row


def test_a_row_under_an_open_question_says_which_value_it_s_of(tmp_path):
    """The plate row of the design's 300 lb, while the person's 260 lb waits (#318 re-check)."""
    from caliper import load_study as L
    from caliper import scenarios as S

    from .test_scenarios import RAISED, RATED

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a step stool")
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, got["scenarios"][1]], got["supports"])
    store.write_part("stool", RAISED, intent="heavier")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    run = _run(store)
    run["cases"][0]["name"] = "stepping on the front edge"
    _resave(store, run)
    (row,) = [r for r in _list(store)["rows"] if r["id"] == "plate:top"]
    assert row["problem"].endswith("; of the design's 300 lb, pending your choice"), row["problem"]


def test_only_the_joint_that_gives_first_says_so(tmp_path):
    """step-stool-3: the top's joint to the side front fails at 1.3x too, but the stretcher's gives first."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 0.05)
    run = _run(store)
    first = {"pieces": ["side back", "stretcher"], "between": "the side back and the stretcher", "mode": "withdrawal",
             "safety": 0.05, "need": 2.0, "holds": False, "said": "three #8 screws pulled out of the stretcher's edge"}
    too = {"pieces": ["side front", "top"], "between": "the top and the side front", "mode": "shear", "safety": 1.3,
           "need": 2.0, "holds": False, "said": "three #8 screws in shear into the top's edge"}
    run["cases"][0].update(governs="joint", joints={"chain": True, "n": 4, "unchecked": [], "governing": first,
                                                    "rows": [first, too]})
    _resave(store, run)
    rows = _by_id(_list(store))
    assert rows["joint:side back|stretcher"]["problem"] == (
        "The joint between the side back and the stretcher gives first under a foot: three #8 screws pulled out of the "
        f"stretcher's edge; under 0.1× where it needs {NEED}×")                     # the card's "under 0.1"
    assert rows["joint:side front|top"]["problem"].startswith("The joint between the top and the side front gives too under")


def test_a_joint_weakest_where_a_panel_governs_never_says_it_gives_first(tmp_path):
    """#318: "gives first" only where a joint governs the case; where the plate or the FEA does, the weakest joint."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.2, governs="plate")
    run = _run(store)
    weakest = {"pieces": ["side back", "stretcher"], "between": "the side back and the stretcher", "mode": "withdrawal",
               "safety": 1.4, "need": 2.0, "holds": False, "said": "three #8 screws pulled out of the stretcher's edge"}
    other = {"pieces": ["side front", "top"], "between": "the top and the side front", "mode": "shear", "safety": 1.6,
             "need": 2.0, "holds": False, "said": "three #8 screws in shear into the top's edge"}
    run["cases"][0].update(governs="plate", joints={"chain": True, "n": 4, "unchecked": [], "governing": weakest,
                                                    "rows": [weakest, other]})
    _resave(store, run)
    rows = _by_id(_list(store))
    assert rows["joint:side back|stretcher"]["problem"].startswith(
        "The joint between the side back and the stretcher is the weakest joint under a foot: ")
    assert rows["joint:side front|top"]["problem"].startswith("The joint between the top and the side front gives too under")
    assert not any("gives first" in r["problem"] for r in rows.values())


def test_a_row_of_your_own_loads_is_badged_so_and_an_open_question_starts_unticked(tmp_path):
    """#318: the person's own loads aren't a measurement; an untouched question never settles itself."""
    from caliper import scenarios as S

    from .test_scenarios import RAISED, RATED

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a step stool")
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, {**got["scenarios"][1], "on": False}], got["supports"])
    store.write_part("stool", RAISED, intent="heavier")
    rows = _by_id(_list(store))
    q, off = rows["asked:stepping on the front edge"], rows["off:its rating (EN 14183, 150 kg)"]
    assert (q["measured"], q["badge"], q["ticked"]) == (False, "your loads", False)
    assert (off["measured"], off["badge"]) == (False, "your loads") and off.get("ticked", True) is True


def test_a_joint_failing_in_two_cases_is_one_row_speaking_for_both(tmp_path):
    """#322 review: Fix these reads a row's cases to say whether it's fixed, so a joint's row names each it gives in."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4)
    run = _run(store)
    weak = {"pieces": ["front rail", "left side"], "between": "the front rail and the left side", "mode": "withdrawal",
            "safety": 1.4, "need": 2.0, "holds": False, "said": "two #8 screws pulled out of the front rail's edge"}
    run["cases"][0].update(governs="joint", joints={"chain": True, "n": 1, "unchecked": [], "governing": weak,
                                                    "rows": [weak]})
    run["cases"].append({**run["cases"][0], "name": "a hand"})
    _resave(store, run)
    (row,) = _list(store)["rows"]
    assert (row["id"], row["cases"], row["what"]) == ("joint:front rail|left side", ["a foot", "a hand"],
                                                      "the joint between the front rail and the left side")


def test_unsized_strips_a_number_turns_off_are_removed_by_it_at_once(tmp_path):
    """#324, Theo's step_stool: fillet_r = 0 skips its strips, so Remove them is a number change, no Claude."""
    from .test_piece_delete import STRIPPED

    from caliper import pieces

    store = _store(tmp_path, STRIPPED, "stool")
    _check(store, "stool", 2.15, thinnest=19.05, spacing=4.76, unsized=["fillet strips"],
           unseen=[{"mm": None, "piece": "fillet strips"}])
    pieces.off_switch(store, "stool", "fillet strips")      # its Delete… built it (#332: Things to fix never does)
    (row,) = [r for r in _list(store)["rows"] if r["id"] == "unsized"]
    rm = row["choices"][2]
    assert (rm["fix"], rm["kind"], rm["param"], rm["value"]) == ("Remove the fillet strips: fillet_r to 0", "number",
                                                                 "fillet_r", 0)
    assert [c["kind"] for c in row["choices"][:2]] == ["designer", "designer"]


def test_things_to_fix_never_builds_to_find_a_number_and_says_the_designer_s_way_till_one_is_known(tmp_path, monkeypatch):
    """#332 review: the off switch's builds took 37–110 s on step_stool, and Things to fix asks on every open."""
    from caliper import pieces

    from .test_piece_delete import STRIPPED

    store = _store(tmp_path, STRIPPED, "stool")
    _check(store, "stool", 2.15, thinnest=19.05, spacing=4.76, unsized=["fillet strips"],
           unseen=[{"mm": None, "piece": "fillet strips"}])
    monkeypatch.setattr(pieces, "_FOUND", {})

    def built(*a, **k):
        raise AssertionError("built")

    monkeypatch.setattr(pieces, "_build", built)
    (row,) = [r for r in _list(store)["rows"] if r["id"] == "unsized"]
    assert (row["choices"][2]["fix"], row["choices"][2]["kind"]) == ("Remove the fillet strips", "designer")
