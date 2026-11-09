"""CALI-129 (#158) — a go-ahead to fix a failing rule tells the designer what was measured and where. From the one live
"have a go" on the bar stool: told only the rule, the designer took ``min_wall`` from 0.25 to 0.225 mm and added 75% of
the volume; it was never told *where* the wall is thin. Stubbed: no Claude call."""

import re

import pytest

from caliper import awaiting, chat, part_rules, promote
from caliper.design import DesignStore

from .test_chat import _box

pytest.importorskip("cadquery")


def _never(*a, **k):
    raise AssertionError("routed by what Caliper asked, never by the router")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a plate", base=str(tmp_path / "designs"))
    s.write_part("plate", _box(dx=60, dy=20), intent="a plate")
    return s


def _lock(store, rid, expr):
    promote.park(store, promote.Proposal(id=rid, expr=expr, level="part", part="plate", holds_now=False, why="it must"))
    assert chat.turn(store, "yes, lock it in", use_llm=False, classifier=_never).action == "accept"
    assert awaiting.pending(store)["kind"] == "fix_rule"


def _go(store, **kw):
    told = {}

    def author(spec, feedback, prior):
        told["prompt"] = feedback
        return _box(dx=60, dy=20)

    got = chat.turn(store, "have a go", use_llm=False, classifier=_never, author=author, max_rounds=1, **kw)
    assert got.action == "refine" and got.part == "plate"
    return told["prompt"]


def _thinnest(store):
    from caliper import measure

    return measure.thinnest_wall(store.part_geometry("plate"))


def test_the_prompt_says_how_thin_where_and_what_the_rule_needs(store):
    _lock(store, "wall", "min_wall >= 100 - 0.15")
    thin, at = _thinnest(store)
    prompt = _go(store)
    assert "wall: min_wall >= 100 - 0.15" in prompt                     # the rule, as before
    assert f"{thin:g} mm" in prompt or f"{round(thin, 1):g} mm" in prompt
    for axis, v in zip("xyz", at):
        assert f"{axis} {v:g}" in prompt, prompt
    assert "at least 99.85 mm" in prompt


def test_a_wall_rule_says_it_counts_every_web_not_just_the_shell(store):
    """What the live run got wrong: it thickened walls that were already thick enough."""
    _lock(store, "wall", "min_wall >= 100")
    assert re.search(r"webs? between openings", _go(store))


FIN = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return (cq.Workplane('XY').box(60, 20, 10)\n"
       "            .union(cq.Workplane('XY').box(2, 20, 30).translate((0, 0, 20))))\n")


def test_the_location_is_in_the_script_s_own_coordinates(store):
    """A part placed in the design is measured where it sits; its script doesn't know that. The fin is the one thin
    spot: x within 1 mm of 0, z from 5 to 35 in the script's own frame."""
    store.write_part("plate", FIN, intent="a plate with a fin")
    _lock(store, "wall", "min_wall >= 100")
    part_rules.measured(store, "plate")                                 # measured once, before it's moved
    next(p for p in store.assembly.parts if p.id == "plate").position = (1000.0, 0.0, 500.0)
    store.save()
    told = {}

    def author(spec, feedback, prior):
        told["prompt"] = feedback
        return FIN

    chat.turn(store, "have a go", use_llm=False, classifier=_never, author=author, max_rounds=1)
    x, _, z = (float(v) for v in re.search(r"at x (\S+), y (\S+), z (\S+) mm", told["prompt"]).groups())
    assert abs(x) <= 1.5 and 5 <= z <= 35, told["prompt"]


def test_a_moved_part_says_where_it_sits_now(store):
    store.write_part("plate", FIN, intent="a plate with a fin")
    _lock(store, "wall", "min_wall >= 100")
    assert abs(part_rules.measured(store, "plate")[0]["where"][0]) <= 1.5
    next(p for p in store.assembly.parts if p.id == "plate").position = (1000.0, 0.0, 500.0)
    store.save()
    x, _, z = part_rules.measured(store, "plate")[0]["where"]
    assert abs(x - 1000) <= 1.5 and 505 <= z <= 535                     # no stale answer from before the move


def test_a_rule_with_no_location_still_gives_the_measured_value(store):
    _lock(store, "wide", "bbox.dx >= 500")
    prompt = _go(store)
    assert "wide: bbox.dx >= 500" in prompt and "Measured on it now: 60." in prompt
    assert " x " not in prompt.split("Measured on it now")[-1]


def test_a_wall_too_awkward_to_locate_still_gives_how_thin(store, monkeypatch):
    from caliper import measure

    _lock(store, "wall", "min_wall >= 100")
    thin, _ = _thinnest(store)
    monkeypatch.setattr(measure, "thinnest_wall", lambda g, *a, **k: (thin, None))
    part_rules._SEEN.clear()
    prompt = _go(store)
    assert f"{round(thin, 1):g} mm" in prompt and "at least 100 mm" in prompt


def test_only_the_designer_is_told_the_record_stays_the_request(store):
    """A location is true of this version only: it stays out of the part's history and its description."""
    _lock(store, "wall", "min_wall >= 100")
    _, at = _thinnest(store)
    _go(store)
    last = [h for h in store.history("plate") if h.get("kind") == "revision"][-1]
    assert last["feedback"] == "Change it so it meets its rule wall: min_wall >= 100. Change only what that needs."
    assert f"x {at[0]:g}" not in (store.design.part("plate").intent or "")


def test_a_rule_gone_by_the_go_ahead_asks_for_the_change_without_a_measurement(store):
    awaiting.park(store, "fix_rule", part="plate", rule="ghost", expr="bbox.dx >= 500")
    prompt = _go(store)
    assert "ghost: bbox.dx >= 500" in prompt and "Measured on it" not in prompt


def test_a_rule_that_holds_now_is_not_said_to_have_failed(store):
    _lock(store, "wide", "bbox.dx >= 500")
    spec = store.read_spec("plate")
    spec.assertions[-1].expr = "bbox.dx >= 1"
    store.write_spec("plate", spec)
    part_rules._SEEN.clear()
    assert part_rules.to_fix(store, "plate", "wide") == ""


# --- #165 review ---------------------------------------------------------------------------------------------------
def test_only_the_first_round_hears_the_measurement(store):
    """A location is true of the script as it stands: round 2 has changed it, so it would be told an old place as "now"."""
    _lock(store, "wall", "min_wall >= 100")
    rounds = []

    def author(spec, feedback, prior):
        rounds.append((spec.intent, feedback))
        return _box(dx=60, dy=20)

    chat.turn(store, "have a go", use_llm=False, classifier=_never, author=author, max_rounds=2)
    assert len(rounds) == 2
    assert "Measured on it now" in rounds[0][1] and "Measured on it now" not in rounds[1][1]
    assert "Measured on it now" not in rounds[0][0] and "Measured on it now" not in rounds[1][0]
    assert "wall: min_wall >= 100" in rounds[1][0]                       # the request itself carries on


#: the thin fin off to one side, so a turn moves it somewhere a turn can't hide
FIN_OFF = ("def build(params):\n"
           "    import cadquery as cq\n"
           "    return (cq.Workplane('XY').box(60, 120, 10)\n"
           "            .union(cq.Workplane('XY').box(2, 40, 30).translate((0, 40, 20))))\n")


def _pose(store, position, rotation):
    part = next(p for p in store.assembly.parts if p.id == "plate")
    part.position, part.rotation = position, rotation
    store.save()


def test_a_turned_and_moved_part_is_told_in_its_script_s_own_coordinates(store):
    store.write_part("plate", FIN_OFF, intent="a plate with a fin")
    _lock(store, "wall", "min_wall >= 100")
    _pose(store, (1000.0, 0.0, 500.0), (0.0, 0.0, 90.0))
    told = {}

    def author(spec, feedback, prior):
        told["prompt"] = feedback
        return FIN_OFF

    chat.turn(store, "have a go", use_llm=False, classifier=_never, author=author, max_rounds=1)
    x, y, z = (float(v) for v in re.search(r"at x (\S+), y (\S+), z (\S+) mm", told["prompt"]).groups())
    assert abs(x) <= 1.5 and 20 <= y <= 60 and 5 <= z <= 35, told["prompt"]


def test_a_part_only_turned_is_measured_again(store):
    store.write_part("plate", FIN_OFF, intent="a plate with a fin")
    _lock(store, "wall", "min_wall >= 100")
    before = next(r for r in part_rules.measured(store, "plate") if r["id"] == "wall")["where"]
    assert abs(before[0]) <= 1.5
    _pose(store, next(p for p in store.assembly.parts if p.id == "plate").position, (0.0, 0.0, 90.0))
    after = next(r for r in part_rules.measured(store, "plate") if r["id"] == "wall")["where"]
    assert -60 <= after[0] <= -20 and abs(after[1]) <= 1.5               # x came from y; no stale answer from before the turn


def test_a_rule_that_errors_at_the_go_ahead_says_it_couldn_t_be_measured(store):
    from caliper.spec import Assertion

    _lock(store, "wide", "bbox.dx >= 500")
    spec = store.read_spec("plate")
    spec.assertions.append(Assertion(id="odd", expr="no_such_measure >= 1"))
    store.write_spec("plate", spec)
    part_rules._SEEN.clear()
    awaiting.park(store, "fix_rule", part="plate", rule="odd", expr="no_such_measure >= 1")
    prompt = _go(store)
    assert "It couldn't be measured just now:" in prompt and "Measured on it now" not in prompt
