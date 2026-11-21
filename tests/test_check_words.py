"""CALI-228 (#386), the page's part: the design checks said in words, not as code.

The tester's walk (11-21), step-stool-5's design view: "Design checks ✓ one_body `body_count == 1` ✓ watertight
`is_watertight`".
- **The words:** a rule is said as what it asks for, the same in both states, so its mark says whether it holds: "✓ one
  solid piece", "✗ closed all round: it isn't" (#391 review: "✗ it's closed all round" stated the very thing that failed).
- **Its number:** a failing rule's number is cut away from the bound it misses, to the rule's own precision, and never
  printed as its limit (#392's part_rules.cut).
- **The expression:** it's a tap away ("as written"), by touch, keyboard or screen reader, not only in a hover title."""
import json
import re

import pytest

from .test_carve_click import JS, _fn, _page, _run

FNS = ["ruleWords", "ruleSaid", "ruleAsWritten", "ruleConst", "ruleCut", "ruleMiss"]
CONSTS = ["esc", "RULE_WORDS", "ruleNorm"]


def _text(page):
    """A row as it reads: tags gone (they add no space of their own), the summary apart from the expression it shows."""
    import html as H

    return " ".join(H.unescape(re.sub(r"<[^>]+>", "", page.replace("</summary>", " "))).split())


@pytest.mark.parametrize("id_,expr,want", [
    ("one_body", "body_count == 1", "one solid piece"),
    ("watertight", "is_watertight", "closed all round"),
    ("one_body", "body_count == 1  and is_watertight", "one solid piece, closed all round"),
    ("manifold", "is_manifold", "no gaps or folds in its surface"),
    ("min_wall_print", "min_wall >= 1.2", "walls 1.2 mm or more"),
    ("shell_wall_thickness", "min_wall >= 3.0 - 0.15", "shell wall thickness"),
    ("thin_cap", "min_wall <= 5", "thin cap"),                  # never "5 mm or more": only an "at least" is a wall's minimum
    ("fits_<b>", "bbox_x <= 600", "fits &lt;b&gt;")])
def test_a_rule_is_said_as_what_it_asks_for(id_, expr, want):
    assert _run(_page(["ruleWords", "ruleSaid"], consts=CONSTS, extra=f"out = ruleSaid({json.dumps(id_)}, {json.dumps(expr)});")) == \
        f"<b>{want}</b>"


def _checks(results):
    return _run(_page(["checks"] + FNS, consts=CONSTS, extra=f"out = checks({{ results: {json.dumps(results)} }});"))


def _rows(results):
    html = _checks(results)
    return [_text(li) for li in re.findall(r"<li class=\"check[^\"]*\">(.*?)</li>", html, re.S)]


def test_step_stool_5_s_design_checks_read_as_words():
    rows = _rows([{"id": "one_body", "expr": "body_count == 1", "status": "pass", "actual": 1},
                  {"id": "watertight", "expr": "is_watertight", "status": "pass", "actual": True}])
    assert rows == ["✓ one solid piece as written body_count == 1", "✓ closed all round as written is_watertight"]


@pytest.mark.parametrize("row,want", [
    ({"expr": "is_watertight", "actual": False}, "✗ closed all round: it isn't"),
    ({"expr": "body_count == 1", "actual": 2}, "✗ one solid piece: it's in 2 pieces"),
    ({"expr": "body_count == 1 and is_watertight", "actual": False}, "✗ one solid piece, closed all round: it isn't"),
    ({"expr": "is_manifold", "actual": False}, "✗ no gaps or folds in its surface: it isn't"),
    ({"expr": "min_wall >= 1.2", "actual": 1.1996}, "✗ walls 1.2 mm or more: measured 1.1 mm"),    # never "1.2"
    ({"expr": "min_wall >= 1.2", "actual": 1.19995}, "✗ walls 1.2 mm or more: measured 1.1 mm"),
    ({"expr": "min_wall >= 1.2", "actual": 0.25381}, "✗ walls 1.2 mm or more: measured 0.2 mm"),
    ({"expr": "min_wall >= 3.0 - 0.15", "actual": 2.849}, "✗ shell wall thickness: measured 2.84 mm"),   # never its 2.85
    ({"expr": "bbox_z <= 12", "actual": 12.01}, "✗ bbox z: measured 13"),                                # an "at most": up
    ({"expr": "height_mm == 400", "actual": 400.4}, "✗ height mm: measured 401")])                       # over: up
def test_a_failing_rule_says_what_s_wrong_never_what_holds(row, want):
    """#391 review: "✗ it's closed all round", "✗ it's one solid piece : measured 2", and 1.1996 as "measured 1.2" beside
    "at least 1.2 mm"."""
    rid = {"is_watertight": "watertight", "body_count == 1": "one_body", "is_manifold": "manifold"}.get(row["expr"])
    rid = rid or {"min_wall >= 3.0 - 0.15": "shell_wall_thickness", "bbox_z <= 12": "bbox_z", "height_mm == 400": "height_mm"}.get(row["expr"], "min_wall_print")
    (got,) = _rows([{"id": rid, "status": "fail", **row}])
    assert got == f"{want} as written {row['expr']}"


def test_the_mark_follows_the_status():
    """#391 review's survivor: a fail drawn as ✓ wasn't caught."""
    rows = _rows([{"id": "w", "expr": "is_watertight", "status": s, "actual": s == "pass"} for s in ("pass", "fail", "error", "deferred")])
    assert [r[0] for r in rows] == ["✓", "✗", "✗", "·"]
    assert rows[0] == "✓ closed all round as written is_watertight"                                  # a pass says nothing more


def test_a_deferred_check_says_why():
    (row,) = _rows([{"id": "w", "expr": "min_wall >= 1.2", "status": "deferred", "detail": "not measured"}])
    assert row == "· walls 1.2 mm or more · not measured as written min_wall >= 1.2"


def test_the_expression_is_a_tap_away_not_hover_only():
    html = _checks([{"id": "w", "expr": "min_wall >= 1.2", "status": "pass", "actual": 1.5}])
    assert '<details class="rule-expr"><summary>as written</summary><code>min_wall &gt;= 1.2</code></details>' in html
    assert "title=" not in html


def test_the_part_s_rules_and_the_plan_s_checks_say_it_the_same_way():
    src = open(JS).read()
    assert "${ruleSaid(r.id, r.expr)}${ruleAsWritten(r.expr)}" in _fn(src, "ruleItem")
    assert "d.plan.checks.map((c) => `<li class=\"small\">${ruleSaid(c.id, c.expr)}${ruleAsWritten(c.expr)}" in src
    assert "<code>${esc(r.expr)}</code>" not in src and "<code>${esc(c.expr)}</code>" not in src


def test_a_rule_with_no_side_to_cut_from_is_never_printed_as_its_own_number():
    """#392's case: rounded to the rule's one place, 5.04 would read "5.0", the rule's own number. A place is added."""
    (row,) = _rows([{"id": "height", "expr": "approx(height_mm, 5, 0.1)", "status": "fail", "actual": 5.04}])
    assert row == "✗ height: measured 5.04 as written approx(height_mm, 5, 0.1)"
