"""CALI-240 — a sits-on rule is stated when the person's own sentence says the relation, enforced; inferred, it's assumed.

#1 slice D's end-to-end camper: the planner's "the box sits on the platform" rule came back assumed (shown, not enforced),
though "a box on top" is the person's own word. The foreman's call: when the person's sentence states the relation ("a box
on top of the platform"), the rule is stated and enforced; when the planner infers it, it stays assumed."""

import pytest

from caliper import plan as P

PLAN = {"parts": [{"id": "deck", "what": "a plywood deck", "made": "sheet"},
                  {"id": "box", "what": "a foam box", "made": "sheet", "mounts_on": ["deck"]}],
        "rules": [{"id": "box_on_deck", "expr": "bbox(box).min_z >= bbox(deck).max_z - 1"}]}


def _source(said):
    return {r.id: r.source for r in P.classify(P.validate(PLAN), said).rules}["box_on_deck"]


@pytest.mark.parametrize("said", [
    "A slide-in camper: a plywood deck in the bed, and a foam box on top of the deck.",
    "a deck plus a box on top",                          # Theo's own shape: "a platform plus a box on top"
    "a box sitting on the deck",
    "a box that rests on the deck",
    "a foam box atop the plywood deck",
    "a box that sits on top of the deck",                # the commonest phrasing (#410 review)
    "a box resting on top of the deck",
])
def test_the_person_s_own_relation_makes_the_rule_stated(said):
    assert _source(said) == "stated", said


@pytest.mark.parametrize("said", [
    "a deck and a box",                                  # no relation said: the planner inferred it
    "a box on top of the trailer",                       # a relation, but to something else
    "a deck on top of the box",                          # the other way round
    "a box, and a deck on the truck",
    "a box on the deck",                                 # a bare "on" isn't up and down (#410 review)
    "the truck has a box on top",                        # "plus/and/with" only, never any word before it
    "a box that isn't on top of the deck",               # a negation says no relation, by rule
    "a box, never on top of the deck",
    "a box on top of it",                                # "it" names no part
])
def test_a_relation_the_planner_inferred_stays_assumed(said):
    assert _source(said) == "assumed", said


def test_a_stated_sits_on_rule_is_enforced():
    plan = P.classify(P.validate(PLAN), "a box on top of the deck")
    assert [r.id for r in P.binding(plan)] == ["box_on_deck"]
    assert P.binding(P.classify(P.validate(PLAN), "a deck and a box")) == []


def test_the_planner_is_told_the_form_a_sits_on_rule_takes():
    assert "bbox(a).min_z >= bbox(b).max_z - 1" in P.SYSTEM


def test_only_a_sits_on_rule_is_stated_by_a_said_relation():
    """"a box on top of the deck" says where the box is, not a clearance the planner chose."""
    plan = {**PLAN, "rules": PLAN["rules"] + [{"id": "gap", "expr": "min_clearance(box, deck) >= 5"}]}
    got = {r.id: r.source for r in P.classify(P.validate(plan), "a box on top of the deck").rules}
    assert got == {"box_on_deck": "stated", "gap": "assumed"}



# --- #410 review (reviewer-3) -----------------------------------------------------------------------------------------
def _rule(a, b, said):
    plan = {"parts": [{"id": a, "what": a, "made": "sheet"}, {"id": b, "what": b, "made": "sheet"}],
            "rules": [{"id": "on", "expr": f"bbox({a}).min_z >= bbox({b}).max_z - 1"}]}
    return {r.id: r.source for r in P.classify(P.validate(plan), said).rules}["on"]


@pytest.mark.parametrize("a,b", [("box_lid", "deck_leg"), ("tool_box", "deck"), ("box", "deck_frame")])
def test_every_word_of_a_part_s_id_must_be_named(a, b):
    """"a box on top of the deck" names box and deck: not the lid, a tool box or the deck's frame."""
    assert _rule(a, b, "a box on top of the deck") == "assumed"
    assert _rule("tool_box", "deck", "the tool box on top of the deck") == "stated"


@pytest.mark.parametrize("said,a,b", [
    ("the logo on the box", "logo", "box"),
    ("a sign with the logo on the board", "logo", "board"),
    ("hinges on the lid", "hinge", "lid"),
    ("a shelf on the wall", "shelf", "wall"),
    ("paint on the box", "paint", "box"),
])
def test_on_in_another_sense_says_no_sits_on(said, a, b):
    assert _rule(a, b, said) == "assumed"


def test_a_prompt_and_an_answer_are_read_apart():
    """"a camper with a lid", then the answer "on the truck bed": the "on" was the camper's, not the lid's."""
    assert _rule("lid", "truck_bed", "a camper with a lid\non top of the truck bed") == "assumed"
    assert _rule("lid", "truck_bed", "a lid on top of the truck bed") == "stated"


def test_the_plus_form_needs_plus_and_or_with():
    """"the truck has a box on top" says where the box is on the truck only by a guess: it stays assumed."""
    assert _rule("box", "truck", "the truck has a box on top") == "assumed"
    assert _rule("box", "truck", "the truck with a box on top") == "stated"
