"""CALI-92 (#70), the leftovers' second part: the reviewer's weight notes from #237, #235's three, #209's notes, the
filled() follow-up, the router's edge cases, and items 10 and 20. Stubbed models only."""

import pytest

from caliper import making

from .test_leftovers_70 import SLICED, _goal, mixed  # noqa: F401  (the fixture)

FAILED = {"hours": None, "filament_g": None, "usd": None, "trust": None, "from": "no estimate (it crashed)", "slicer_failed": True}


# --- #237's weight notes ---------------------------------------------------------------------------------------------------
def test_only_the_solid_s_share_is_a_bound():
    solid = {"bom": {"printed": [{"filament_from": making.FROM_SOLID}]}}
    rough = {"bom": {"printed": [{"filament_from": making.FROM_ROUGH}]}}
    sliced = {"bom": {"printed": [{"filament_from": making.FROM_SLICER}]}}
    assert making.filament_bound([solid]) and not making.filament_bound([rough]) and not making.filament_bound([sliced])
    assert not making.filament_bound([solid, rough])
    assert making.settled_by_bound("<=", True) and making.settled_by_bound(">=", False)
    assert not making.settled_by_bound("<=", False) and not making.settled_by_bound(">=", True)


@pytest.mark.parametrize("limit,guessed", [(5, False), (3, True)])
def test_a_weight_under_goal_on_the_solid_s_upper_bound(mixed, monkeypatch, limit, guessed):
    """Note 2: the solid's share is an upper bound: under the limit it passes; over it, it may still be under: a guess."""
    from caliper import answers, design_api, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    _goal(mixed, "weight.total_lb", limit)
    state = design_api.design_state(mixed)
    now = answers.measured(mixed, state)
    assert now["weight.total_lb"] == pytest.approx(3.5, abs=0.05) and now.get("filament.upper")
    (line,) = [ln for ln in answers.held_to(state, now) if "light enough" in ln["text"].lower()]
    assert ("a guess" in line["text"]) is guessed
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert (check["status"] == "pass") is not guessed


def test_a_part_s_weight_says_where_its_filament_came_from(mixed, monkeypatch):
    """Note 3: weight.table read trust model, source construction, while its value was the rough figure."""
    from caliper import printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: {**SLICED, "trust": "rough", "from": "rough"})
    m = scorecard.compute(mixed)["metrics"]["weight.table"]
    assert m["trust"] == "rough" and m["source"] == "a guess (the filament is a rough guess)"


def test_the_panel_says_its_table_is_the_solid_s(mixed):
    """Note 1: the table, the pieces and the balance are the solid's: said, where the part's weight above isn't."""
    from .test_small_words import _js

    got = _js(["solidSaid"], "return [solidSaid({mass_lb: 2.6, filament_more_kg: -0.396}), solidSaid({mass_lb: 3.5})];",
              "const lbs = (x) => `${(+x).toFixed(1)} lb`;")
    assert got[0].startswith("<div") and "the model's solid" in got[0] and "(3.5 lb)" in got[0] and "2.6 lb" in got[0]
    assert got[1] == ""


def test_a_slicer_that_failed_leaves_the_print_total_unknown_not_a_crash(mixed, monkeypatch):
    """Found on the way: a failed slice's hours are None, and the scorecard's sum raised TypeError."""
    from caliper import printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    m = scorecard.compute(mixed)["metrics"]
    assert m["print.hours"]["value"] is None and "the slicer couldn't" in m["print.hours"]["note"]
