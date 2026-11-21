"""CALI-227 (#385) — a chat reply says a failing rule in words, rounded to the rule's own precision and cut toward safe.

The tester's walk on the bar stool: a revise reply ended "• shell_wall_thickness: min_wall >= 3.0 - 0.15 →
actual=0.22303847515793196 (margin -2.63)", while the card said it well: "its thinnest walls are 0.22 mm …; it says at
least 2.85 mm". Now the chat says what the card says (``part_rules._said``), and a number is never rounded onto its limit:
an "at least" is cut down, an "at most" up. Stub designer only: no live call."""

import pytest

from caliper import chat, part_rules
from caliper.design import DesignStore
from caliper.evaluate import AssertionResult, Report
from caliper.spec import Assertion, Spec

WALL = "min_wall >= 3.0 - 0.15"


@pytest.mark.parametrize("actual,expr,said", [
    (0.22303847515793196, WALL, "0.22"),          # two places, as the rule writes 0.15
    (2.849, WALL, "2.84"),                       # an "at least": cut down, never onto 2.85
    (400.5, "bbox(seat).dz >= 401", "400"),     # whole millimetres, cut down
    (12.01, "bbox(seat).dz <= 12", "13"),       # an "at most": cut up, never onto 12
    (12.04, "bbox(seat).dz <= 12.0", "12.1"),
    (5.06, "approx(bbox(seat).dz, 5, 0.1)", "5.1"),   # neither: rounded
])
def test_a_rule_s_number_is_rounded_to_its_precision_and_cut_toward_safe(actual, expr, said):
    assert part_rules.cut(actual, expr) == said


def test_the_wall_rule_reads_as_the_card_does():
    r = {"id": "shell_wall_thickness", "expr": WALL, "status": "fail", "actual": 0.22303847515793196}
    assert part_rules._said(r, None, False) == "shell wall thickness: its thinnest walls are 0.22 mm; it says at least 2.85 mm"
    near = {**r, "actual": 2.849}
    assert "its thinnest walls are 2.84 mm" in part_rules._said(near, None, False)
    big = {"id": "base_wall", "expr": "min_wall >= 10", "status": "fail", "actual": 9.96}
    assert "its thinnest walls are 9 mm; it says at least 10 mm" in part_rules._said(big, None, False)   # never "10 mm"


def test_the_chat_s_failing_lines_are_words_not_code():
    rep = Report([AssertionResult("shell_wall_thickness", WALL, "fail", False, 0.22303847515793196, -2.63),
                  AssertionResult("seat_height", "bbox(seat).dz >= 401", "fail", False, 400.5, -0.5),
                  AssertionResult("fits", "fit_off(a, b, 0.3) <= 0.5", "error", None, None, None, "a isn't built")])
    lines = chat._fail_lines(rep)
    assert lines == ["  • shell wall thickness: its thinnest walls are 0.22 mm; it says at least 2.85 mm",
                     "  • seat height: it measures 400 (bbox(seat).dz >= 401)",
                     "  • fits: fit_off(a, b, 0.3) <= 0.5, not measured: a isn't built"], lines
    assert not any("actual=" in ln or "margin" in ln for ln in lines)


THIN = ("def build(params):\n    import cadquery as cq\n"
        "    return cq.Workplane('XY').box(100, 100, 0.25)\n")


def test_a_revise_reply_says_the_rule_in_words(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pytest.importorskip("cadquery")
    s = DesignStore.create("a bar stool", base=str(tmp_path / "designs"))
    spec = Spec(part="shell", intent="a printed shell", assertions=[Assertion(id="shell_wall_thickness", expr=WALL)])
    s.write_part("shell", THIN.replace("0.25", "0.3"), intent="a printed shell", spec=spec)
    res = chat.turn(s, "make it thinner", scope="shell", use_llm=False, author=lambda spec, f, p: THIN)
    import re

    assert re.search(r"• shell wall thickness: its thinnest walls are 0\.2\d mm; it says at least 2\.85 mm", res.reply), res.reply
    assert "actual=" not in res.reply and "margin" not in res.reply



def test_a_change_that_breaks_a_design_check_says_it_in_words(tmp_path, monkeypatch):
    """The "broke" lines go through the same words (and the same call: a wrong argument there raised)."""
    from caliper.assembly import Mate

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pytest.importorskip("cadquery")
    box = ("def build(params):\n    import cadquery as cq\n"
           "    return cq.Workplane('XY').box(20, 20, 20).translate(({x}, 0, 0))\n")
    s = DesignStore.create("two blocks", base=str(tmp_path / "designs"))
    s.write_part("a", box.format(x=0), intent="a block")
    s.write_part("b", box.format(x=100), intent="a block")
    s.assembly.mates.append(Mate(id="apart", between=["a", "b"], kind="no_interference"))
    s.save()
    res = chat.turn(s, "move it right", scope="a", use_llm=False, author=lambda spec, f, p: box.format(x=95))
    assert "broke 1 design check" in res.reply and "• apart: it measures " in res.reply, res.reply
    assert "actual=" not in res.reply


def test_a_revert_that_breaks_a_design_check_says_it_in_words(tmp_path, monkeypatch):
    from caliper.assembly import Mate

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pytest.importorskip("cadquery")
    box = ("def build(params):\n    import cadquery as cq\n"
           "    return cq.Workplane('XY').box(20, 20, 20).translate(({x}, 0, 0))\n")
    s = DesignStore.create("two blocks", base=str(tmp_path / "designs"))
    s.write_part("a", box.format(x=95), intent="a block")          # v1 runs into b
    s.write_part("b", box.format(x=100), intent="a block")
    s.write_part("a", box.format(x=0), intent="a block")           # v2 clear of it
    s.assembly.mates.append(Mate(id="apart", between=["a", "b"], kind="no_interference"))
    s.save()
    res = chat.revert_part(s, "a")
    assert "• apart: it measures " in res.reply and "actual=" not in res.reply, res.reply


# --- #392 review (caliper-reviewer) --------------------------------------------------------------------------------------
@pytest.mark.parametrize("actual,expr,said", [
    (400.4, "height_mm == 400", "401"),              # over its target: up, never "400"
    (399.6, "height_mm == 400", "399"),              # under it: down
    (299.7, "300 <= height_mm <= 400", "299"),       # under the band: down, never onto 300
    (400.3, "300 <= height_mm <= 400", "401"),       # over it: up
    (2.849, WALL, "2.84"),                           # the computed limit (2.85) is a limit too
    (5.04, "approx(height_mm, 5, 0.1)", "5.04"),     # no side to cut from: places added until it isn't 5.0
    (-0.4, "seat_mm >= leg_gap_mm", "-0.400"),       # no number: three significant figures
])
def test_a_failing_number_is_cut_away_from_the_bound_it_misses(actual, expr, said):
    assert part_rules.cut(actual, expr, failing=True) == said


def test_a_rule_with_no_number_says_three_significant_figures():
    assert part_rules.cut(0.2230384, "seat_mm > leg_gap_mm") == "0.223"
    r = {"id": "seat_over_gap", "expr": "seat_mm > leg_gap_mm", "status": "pass", "actual": 0.2230384}
    assert part_rules._said(r, None, False) == "seat over gap: it measures 0.223 (seat_mm > leg_gap_mm)"


def test_the_card_and_the_chat_say_a_failing_equality_off_its_target():
    r = {"id": "height", "expr": "height_mm == 400", "status": "fail", "actual": 400.4}
    assert part_rules._said(r, None, False) == "height: it measures 401 (height_mm == 400)"
