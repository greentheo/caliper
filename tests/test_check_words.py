"""CALI-228 (#386), the page's part: the design checks said in words, not as code.

The tester's walk (11-21), step-stool-5's design view: "Design checks ✓ one_body `body_count == 1` ✓ watertight
`is_watertight`". Theo reads what a check says, not the expression it is. Caliper's own rules are said in words, a wall
rule by its number, anything else by its name in words; the expression stays in the title for whoever hovers."""
import json

import pytest

from .test_carve_click import _page, _run


def _said(id_, expr):
    return _run(_page(["ruleSaid"], consts=["esc", "RULE_WORDS"], extra=f"out = ruleSaid({json.dumps(id_)}, {json.dumps(expr)});"))


@pytest.mark.parametrize("id_,expr,want", [
    ("one_body", "body_count == 1", '<b title="body_count == 1">it\'s one solid piece</b>'),
    ("watertight", "is_watertight", '<b title="is_watertight">it\'s closed all round</b>'),
    ("one_body", "body_count == 1  and is_watertight", '<b title="body_count == 1 and is_watertight">it\'s one solid piece, closed all round</b>'),
    ("manifold", "is_manifold", '<b title="is_manifold">its surface has no gaps or folds</b>'),
    ("min_wall_print", "min_wall >= 1.2", '<b title="min_wall &gt;= 1.2">its walls are at least 1.2 mm</b>'),
    ("shell_wall_thickness", "min_wall >= 3.0 - 0.15", '<b title="min_wall &gt;= 3.0 - 0.15">shell wall thickness</b>'),
    ("fits_<b>", "bbox_x <= 600", '<b title="bbox_x &lt;= 600">fits &lt;b&gt;</b>')])
def test_a_rule_is_said_in_words_with_its_expression_in_the_title(id_, expr, want):
    assert _said(id_, expr) == want


def _checks(results):
    return _run(_page(["checks", "ruleSaid"], consts=["esc", "RULE_WORDS"], extra=f"out = checks({{ results: {json.dumps(results)} }});"))


def test_step_stool_5_s_design_checks_read_as_words():
    html = _checks([{"id": "one_body", "expr": "body_count == 1", "status": "pass", "actual": 1},
                    {"id": "watertight", "expr": "is_watertight", "status": "pass", "actual": True}])
    assert "it's one solid piece" in html and "it's closed all round" in html
    assert "<code>" not in html and "one_body" not in html.replace('title="', "")


def test_a_failing_check_says_what_it_measured_without_a_long_tail_and_no_bare_false():
    html = _checks([{"id": "one_body", "expr": "body_count == 1", "status": "fail", "actual": 2},
                    {"id": "watertight", "expr": "is_watertight", "status": "fail", "actual": False},
                    {"id": "w", "expr": "min_wall >= 1.2", "status": "fail", "actual": 0.25381}])
    assert ": measured 2</span>" in html and "2.000" not in html                 # body_count 2 read "→ 2.000"
    assert "false" not in html                                                     # the words say it isn't closed
    assert ": measured 0.254</span>" in html


def test_the_part_s_rules_and_the_plan_s_checks_say_it_the_same_way():
    from .test_carve_click import JS, _fn

    src = open(JS).read()
    assert "${ruleSaid(r.id, r.expr)}" in _fn(src, "ruleItem")
    assert "d.plan.checks.map((c) => `<li class=\"small\">${ruleSaid(c.id, c.expr)}" in src
    assert "<code>${esc(r.expr)}</code>" not in src and "<code>${esc(c.expr)}</code>" not in src
