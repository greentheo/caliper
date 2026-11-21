"""CALI-226 (#384): the scorecard says a goal as a goal, and a scored strength goal leads with the number it does.

The tester's walk (11-21), step-stool-5's design view: "SCORECARD · holds 250 lb, 2 times over (assumed)", unscored, beside
a check that said 3.8x. The label is the goal's name, but it read as a result: the 2 is what it needs. #64 item 15 fixed the
same on the card ("3.1 times over (it needs 2)")."""
import json
import re

import pytest

from .test_carve_click import JS, _page, _run

FNS = ["scoreView", "scoreMark", "scoreNum", "safetyNum", "asOf", "goalSaid"]
CONSTS = ["esc", "TRUST", "goalLimit", "MUST", "NEED", "strengthGoal", "NO_NUMBER"]
HOLDS = {"id": "holds", "label": "holds 250 lb, 2 times over", "metric": "strength.safety", "op": ">=", "limit": 2.0,
         "source": "assumed"}


def _score(design):
    return _run(_page(FNS, consts=CONSTS, extra=f"out = scoreView({json.dumps(design)});"))


@pytest.mark.parametrize("label,want", [
    ("holds 250 lb, 2 times over", "must hold 250 lb, 2 times over"),
    ("Holds Dad (200 lb), 2 times over", "must hold Dad (200 lb), 2 times over"),
    ("carries 40 lb of soil", "must carry 40 lb of soil"),
    ("weighs under 10 lb", "must weigh under 10 lb"),
    ("keeps total weight down", "must keep total weight down"),
    ("fits in the hatchback", "must fit in the hatchback"),
    ("under $50", "under $50"),                                   # a label that's already a goal: as written
    ("holder <b>x</b>", "holder &lt;b&gt;x&lt;/b&gt;")])          # not a verb it knows, and text, not HTML
def test_a_goal_is_said_as_a_goal(label, want):
    assert _run(_page(["goalSaid"], consts=["esc", "MUST"], extra=f"out = goalSaid({json.dumps({'label': label})});")) == want


def test_step_stool_5_s_unscored_row_reads_as_a_goal():
    """The walk's row, with no card yet."""
    html = _score({"parts": [], "scorecards": [], "has_goals": True, "goals": {"ours": True, "checks": [HOLDS]}})
    assert "· must hold 250 lb, 2 times over" in html and "· holds 250 lb" not in html


def test_a_goal_new_since_the_card_reads_as_a_goal_too():
    card = {"created": 1, "summary": {"pass": 0, "fail": 0}, "checks": [], "objectives": []}
    html = _score({"parts": [], "scorecards": [card], "has_goals": True, "goals": {"ours": True, "checks": [HOLDS]}})
    assert "· must hold 250 lb, 2 times over" in html and "new since this card" in html


def test_a_scored_strength_goal_leads_with_the_number_it_does_and_says_what_it_needs():
    card = {"created": 1, "summary": {"pass": 1, "fail": 0}, "objectives": [],
            "checks": [{**HOLDS, "status": "pass", "value": 3.8, "unit": "×", "trust": "model"}]}
    html = _score({"parts": [], "scorecards": [card], "has_goals": True, "goals": {"ours": True, "checks": [HOLDS]}})
    assert "<b>3.8 ×</b> — holds 250 lb (needs 2 ×)" in html
    assert "2 times over" not in html                      # its need is said once, as what it needs


def test_a_weight_goal_scored_is_as_it_was():
    card = {"created": 1, "summary": {"pass": 0, "fail": 1}, "objectives": [],
            "checks": [{"id": "w", "label": "keeps total weight down", "metric": "weight.total", "status": "fail",
                        "value": 13.1, "unit": "lb", "op": "<=", "limit": 10}]}
    html = _score({"parts": [], "scorecards": [card], "has_goals": True, "goals": {"checks": []}})
    assert "keeps total weight down — 13.1 lb (cap 10 lb)" in html


@pytest.mark.parametrize("label", ["holds Dad (200 lb), 2 times over", "holds 250 lb, twice over", "holds me, 2.5 × over",
                                   "holds the bench, 3x safety", "holds what its loads say, at its factor (from its loads)"])
def test_the_page_drops_the_need_as_answers_does(label):
    """The pattern is answers._NEED's, so the card and the scorecard say a label the same way."""
    from caliper.answers import _without_need

    src = open(JS).read()
    need = re.search(r"^const NEED = (/.*/i);$", src, re.M).group(1)
    got = _run(f"console.log(JSON.stringify({json.dumps(label)}.replace({need}, '').trimEnd()));")
    assert got == _without_need(label)


@pytest.mark.parametrize("status,mark,tail", [("unresolved", "!", ": not resolved"), ("untrusted", "!", ": not trusted"),
                                              ("unknown", "?", ": not measured yet"), ("weird", "?", "")])
def test_a_scored_goal_with_no_number_is_still_said_as_a_goal(status, mark, tail):
    """#390 review: a strength check the card couldn't number read "! holds 250 lb, 2 times over", a claim beside its "!"."""
    card = {"created": 1, "summary": {"pass": 0, "fail": 0}, "objectives": [],
            "checks": [{**HOLDS, "status": status, "value": None, "unit": "×"}]}
    html = _score({"parts": [], "scorecards": [card], "has_goals": True, "goals": {"ours": True, "checks": [HOLDS]}})
    row = re.sub(r"<[^>]+>", "", html[html.index("<li>"):html.index("</li>")])
    row = " ".join(row.split())
    assert row.startswith(f"{mark} must hold 250 lb, 2 times over{tail}"), row
    assert "· holds" not in row and "! holds" not in row
