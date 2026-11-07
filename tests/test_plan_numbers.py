"""CALI-119 (#127) — a rule over the plan's own numbers is decided when it's planned, and no rule sinks the plan.

#117's live re-run: the camper's planner wrote ``tube_size * 25.4 <= 50.8`` (the frame tube fits the 2 in receiver),
twice; #117 refused a numbers-only rule, so the whole plan fell back to one part. Now such a rule is decided at plan
time (true: a note; false: a contradiction, refused with it), and after the one retry a bad rule is dropped and said,
never the plan. And "60 mph" is the person's number in m/s too."""

import copy

import pytest

from caliper import firstrun
from caliper import plan as P
from caliper.design import DesignStore

from .test_plan_live import _never, fake

CAMPER_SAID = "A camper: a plywood cargo box on a welded frame that slides into my 2 in hitch receiver."
#: The camper as the re-run had it (cut down): the frame tube's size against the receiver's, by the numbers.
CAMPER = {
    "parts": [{"id": "cargo_box", "what": "a plywood cargo box", "made": "sheet", "mounts_on": ["frame"]},
              {"id": "frame", "what": "a welded steel frame", "made": "welded tube"}],
    "skeleton": [{"name": "tube_size", "value": 2, "unit": "in", "why": "the receiver's size"},
                 {"name": "receiver", "value": 2, "unit": "in", "why": "a class III hitch"}],
    "mates": [{"between": ["cargo_box", "frame"], "kind": "touch"}],
    "rules": [{"id": "frame_tube_fits_receiver", "expr": "tube_size * 25.4 <= 50.8", "why": "the frame tube fits the receiver"},
              {"id": "box_on_frame", "expr": "bbox(cargo_box).min_z >= bbox(frame).max_z - 1"}],
}


def _with(rule_expr):
    got = copy.deepcopy(CAMPER)
    got["rules"][0]["expr"] = rule_expr
    return got


def test_a_numbers_only_rule_that_holds_is_a_note_not_a_check():
    plan = P.validate(_with("tube_size <= receiver"))
    # plan data (#130 review): it stays in the rules, decided again each validate; never a check
    assert [r.id for r in plan.rules] == ["frame_tube_fits_receiver", "box_on_frame"]
    assert [r.id for r in P.binding(plan)] == [] or "frame_tube_fits_receiver" not in [r.id for r in P.binding(plan)]
    assert plan.notes == ["the frame tube fits the receiver (tube_size <= receiver)"]


def test_one_that_doesn_t_hold_refuses_the_plan_with_the_contradiction():
    with pytest.raises(P.PlanError) as e:
        P.validate(_with("tube_size > receiver"))
    assert ("the check 'frame_tube_fits_receiver' contradicts the plan's own numbers: the frame tube fits the "
            "receiver, but tube_size > receiver is false (tube_size 50.8 mm, receiver 50.8 mm)") in str(e.value), str(e.value)
    assert e.value.rule == "frame_tube_fits_receiver"


def test_the_camper_s_rule_verbatim_says_what_a_number_reads_as_in_a_check():
    """In a check a length reads in mm, so `tube_size * 25.4` is 1290: the refusal says so, for the retry."""
    with pytest.raises(P.PlanError) as e:
        P.validate(CAMPER)
    assert "tube_size * 25.4 <= 50.8 is false (tube_size 50.8 mm)" in str(e.value)
    # the hint is the planner's, for its retry; what the person reads doesn't carry it (#130 review)
    assert e.value.hint == "lengths in a check read in mm" and "lengths in a check" not in str(e.value)


def test_a_rule_of_literals_alone_is_dropped_and_said():
    plan = P.validate(_with("25.4 == 25.4"))
    assert [r.id for r in plan.rules] == ["box_on_frame"]
    assert plan.dropped_rules == ["the check 'frame_tube_fits_receiver' (25.4 == 25.4): it reads only numbers"]
    assert plan.left_out == plan.dropped_rules                  # plan data: saved, and a revision sees it


@pytest.mark.parametrize("bad,why", [
    ("tube_size * 25.4 <= 50.8", "contradicts the plan's own numbers"),
    ("bbox(cargo_box).dy = 4", "`=` isn't a comparison; use `==`"),
    ("min_clearance(cargo_box, trailer) >= 5", "names 'trailer', which isn't a part"),
])
def test_after_the_retry_a_bad_rule_is_dropped_and_said_and_the_plan_stands(tmp_path, bad, why):
    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    client = fake(_with(bad))                                  # the same rule both times, as the live run had it
    got = firstrun.build(store, use_llm=True, client=client, author=_never, strength=False)
    assert len(client.plan_calls()) == 2
    assert got["plan"] == "review", got["steps"]               # the plan stands: two parts, to review
    plan = P.load(store)
    assert plan.ids() == ["cargo_box", "frame"] and [r.id for r in plan.rules] == ["box_on_frame"]
    (dropped,) = plan.dropped_rules
    assert dropped.startswith("the check 'frame_tube_fits_receiver'") and why in dropped, dropped
    assert "I left out the check 'frame_tube_fits_receiver'" in got["reply"], got["reply"]
    from caliper import design_api

    assert design_api.design_state(store)["plan"]["dropped_rules"] == [dropped]


def test_a_plan_level_fault_still_falls_back_to_one_part(tmp_path):
    from caliper import chat

    looped = copy.deepcopy(CAMPER)
    looped["parts"][1]["mounts_on"] = ["cargo_box"]
    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    built = []
    import caliper.chat as C

    orig = C.author_part
    C.author_part = lambda *a, **k: built.append(a[1]) or chat.TurnResult("author", "no", ok=False, error="stub")
    try:
        got = firstrun.build(store, use_llm=True, client=fake(looped), strength=False)
    finally:
        C.author_part = orig
    assert built and store.design.plan is None
    assert got["steps"]["plan"].startswith("planning it in several parts didn't work (the parts mount on each other")


@pytest.mark.parametrize("value,unit", [(26.82, "m/s"), (60, "mph"), (96.56, "km/h")])
def test_60_mph_is_the_person_s_number_in_any_unit(value, unit):
    plan = P.validate({"parts": [{"id": "rotor", "what": "a printed rotor", "made": "printed"}],
                       "skeleton": [{"name": "design_wind_speed_ms", "value": value, "unit": unit}]})
    got = P.classify(plan, "A wind turbine that survives a 60 mph gust.")
    assert got.skeleton[0].source == "stated", (value, unit)


def test_a_speed_goes_by_its_unit_not_its_name():
    """#130 review: "m" isn't a speed, whatever the name says ("rotor_d" read as one); a length in m is a length."""
    plan = P.validate({"parts": [{"id": "rotor", "what": "a printed rotor", "made": "printed"}],
                       "skeleton": [{"name": "design_wind_speed_ms", "value": 26.82, "unit": "m"},
                                    {"name": "rotor_d", "value": 0.6, "unit": "m"}]})
    got = P.classify(plan, "A wind turbine that survives a 60 mph gust, a 600 mm rotor.")
    assert [s.source for s in got.skeleton] == ["assumed", "stated"]


@pytest.mark.parametrize("value,unit", [(90.7, "kg"), (200, "lb")])
def test_200_lb_is_the_person_s_number_in_kg_too(value, unit):
    plan = P.validate({"parts": [{"id": "stool", "what": "a stool", "made": "sheet"}],
                       "skeleton": [{"name": "load", "value": value, "unit": unit}]})
    assert P.classify(plan, "A step stool that holds 200 lb.").skeleton[0].source == "stated"


def test_the_planner_is_told():
    assert "decided when it's planned" in P.SYSTEM and "m/s" in P.SYSTEM


# --- #130 review --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("expr,note", [("approx(tube_size, receiver)", True), ("within(tube_size, 40, 60)", True)])
def test_the_checks_own_functions_decide_a_rule_by_the_numbers(expr, note):
    plan = P.validate(_with(expr))
    assert plan.notes == [f"the frame tube fits the receiver ({expr})"]


def test_an_error_deciding_a_rule_is_the_rule_s_fault_never_the_plan_s():
    with pytest.raises(P.PlanError) as e:
        P.validate(_with("tube_size / 0 > 1"))
    assert e.value.rule == "frame_tube_fits_receiver" and "can't be decided by the numbers" in str(e.value)
    plan = P.validate(_with("tube_size / 0 > 1"), drop_bad_rules=True)
    assert plan.ids() == ["cargo_box", "frame"] and plan.left_out[0].startswith("the check 'frame_tube_fits_receiver'")


def test_a_note_through_the_review_the_saved_plan_the_card_and_keep(tmp_path):
    """The four steps a note takes after validate (the surviving mutants): the reply says it, it's saved, the card
    shows it apart from the checks, and keeping another check keeps it."""
    from caliper import design_api

    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, client=fake(_with("tube_size <= receiver")), author=_never,
                         strength=False)
    note = "the frame tube fits the receiver (tube_size <= receiver)"
    assert f"By the numbers: {note}." in got["reply"]
    assert P.load(store).notes == [note]
    shown = design_api.design_state(store)["plan"]
    assert shown["notes"] == [note] and "frame_tube_fits_receiver" not in [c["id"] for c in shown["checks"]]
    P.keep(store, "box_on_frame")
    assert P.load(store).notes == [note]
    assert "frame_tube_fits_receiver" not in [a.id for a in store.assembly.assertions]      # a note, never a check


def test_an_edit_a_note_contradicts_is_refused_with_it_never_a_silent_drop(tmp_path):
    """"make the frame tube 3 in": the note says it fits the 2 in receiver; the edit is refused, the plan as it was."""
    from caliper import chat

    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    store.design.display_units = "in"
    store.save()
    firstrun.build(store, use_llm=True, client=fake(_with("tube_size <= receiver")), author=_never, strength=False)
    wider = _with("tube_size <= receiver")
    wider["skeleton"][0]["value"] = 3
    client = fake(wider)
    got = chat.turn(store, "make the frame tube 3 in", client=client, use_llm=True)
    assert got.action == "plan" and not got.ok
    assert "the frame tube fits the receiver, but tube_size <= receiver is false (tube_size 76.2 mm" in got.reply
    assert '"tube_size <= receiver"' in client.plan_calls()[0]["messages"][0]["content"]       # the planner saw it
    assert P.load(store).value("tube_size").value == 2 and P.load(store).notes        # as it was


def test_the_retry_gets_the_hint_and_the_person_doesn_t(tmp_path):
    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    client = fake(CAMPER)
    got = firstrun.build(store, use_llm=True, client=client, author=_never, strength=False)
    retry = client.plan_calls()[1]["messages"][0]["content"]
    assert "(lengths in a check read in mm)" in retry
    assert "lengths in a check" not in got["reply"]


def test_left_out_is_validate_s_own_and_a_revision_keeps_the_prior_s(tmp_path):
    """#130 review: a planner's answer can't claim checks were left out; an edit keeps what the plan left out."""
    from caliper import chat

    claimed = _with("25.4 == 25.4")
    claimed["left_out"] = ["the check 'made_up' (1 > 0): the planner says so"]
    plan = P.validate(claimed)
    assert plan.left_out == ["the check 'frame_tube_fits_receiver' (25.4 == 25.4): it reads only numbers"]
    store = DesignStore.create(CAMPER_SAID, base=str(tmp_path / "designs"))
    firstrun.build(store, use_llm=True, client=fake(_with("25.4 == 25.4")), author=_never, strength=False)
    kept = P.load(store).left_out
    assert kept == plan.left_out
    wider = _with("25.4 == 25.4")
    wider["rules"] = wider["rules"][1:]                       # the planner's answer leaves the literal rule out
    wider["skeleton"][1]["value"] = 2.5
    got = chat.turn(store, "make the receiver 2 1/2 in", client=fake(wider), use_llm=True)
    assert got.ok, got.reply
    assert P.load(store).left_out == kept                     # carried through the edit
