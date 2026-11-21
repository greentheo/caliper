"""CALI-36 (#17) slice A — groups: a plan's parts in named sub-assemblies, inside one design.

Theo's next build is a truck camper, "a platform plus a box on top, built in one go". A group is a named set of parts (or of
groups, two deep at most); a group may mount on a group or a part, and everything it mounts on is built before any of its
parts. Everything stays one design: one skeleton, one assembly, one flat part list, so every check works as it did. Saved
in the plan; ``Design.groups`` is the page's contract. A design without groups is exactly as it was."""

import copy

import pytest

from caliper import plan as P
from caliper.design import DesignStore

#: A truck camper as a planner might group it: a platform of four parts, a box of five on it.
CAMPER = {
    "parts": [
        {"id": "box_floor", "what": "the box's floor panel", "made": "sheet"},
        {"id": "box_wall_left", "what": "the box's left wall", "made": "sheet", "mounts_on": ["box_floor"]},
        {"id": "box_wall_right", "what": "the box's right wall", "made": "sheet", "mounts_on": ["box_floor"]},
        {"id": "box_front", "what": "the box's front wall", "made": "sheet", "mounts_on": ["box_floor"]},
        {"id": "box_roof", "what": "the roof", "made": "sheet", "mounts_on": ["box_wall_left", "box_wall_right"]},
        {"id": "deck", "what": "the platform's deck", "made": "sheet", "mounts_on": ["rails"]},
        {"id": "rails", "what": "two rails on the bed", "made": "lumber", "mounts_on": ["legs"]},
        {"id": "legs", "what": "four legs", "made": "lumber"},
        {"id": "cleats", "what": "cleats that hold the platform in the bed", "made": "printed", "mounts_on": ["rails"]},
    ],
    "groups": [
        {"id": "box", "what": "the camper box", "parts": ["box_floor", "box_wall_left", "box_wall_right", "box_front",
                                                          "box_roof"], "mounts_on": ["platform"]},
        {"id": "platform", "what": "the bed platform", "parts": ["deck", "rails", "legs", "cleats"]},
    ],
    "skeleton": [{"name": "platform_h", "value": 12, "unit": "in", "why": "the deck's top off the bed", "kind": "position"}],
}


def _with(change):
    got = copy.deepcopy(CAMPER)
    change(got)
    return got


def test_a_group_is_built_after_what_it_mounts_on_its_own_parts_in_their_order():
    plan = P.validate(CAMPER)
    assert [g.id for g in plan.groups] == ["box", "platform"]
    assert P.order(plan) == ["legs", "rails", "deck", "cleats", "box_floor", "box_wall_left", "box_wall_right",
                             "box_front", "box_roof"]


def test_a_part_may_mount_on_a_group_and_groups_nest_two_deep():
    got = _with(lambda p: (p["parts"].append({"id": "awning", "what": "an awning", "made": "sheet", "mounts_on": ["box"]}),
                           p["groups"].append({"id": "camper", "what": "the whole camper", "parts": ["box", "platform"]})))
    plan = P.validate(got)
    order = P.order(plan)
    assert order.index("awning") > max(order.index(x) for x in CAMPER["groups"][0]["parts"])
    assert P.group_of(plan, "deck") == ["camper", "platform"]
    assert P.group_parts(plan, "camper") == [p["id"] for p in CAMPER["parts"]]


@pytest.mark.parametrize("change,why", [
    (lambda p: p["groups"][1].__setitem__("mounts_on", ["box"]),
     "the parts mount on each other in a circle: box_floor → platform → deck → box → box_floor"),
    (lambda p: p["parts"][5].__setitem__("mounts_on", ["platform"]), "'deck' mounts on 'platform', the group it's in"),
    (lambda p: p["groups"][0]["parts"].append("deck"), "'deck' is in two groups, 'box' and 'platform'"),
    (lambda p: p["groups"][0]["parts"].append("hatch"), "the group 'box' holds 'hatch', which isn't a part or a group"),
    (lambda p: p["groups"].append({"id": "deck", "what": "x", "parts": ["legs"]}),
     "'deck' names two things (a part, a group, a skeleton number or a measure)"),
    (lambda p: p["groups"][1].__setitem__("parts", []), "the group 'platform' holds nothing"),
    (lambda p: p["groups"][1]["parts"].append("platform"), "the group 'platform' holds itself"),
    (lambda p: (p["groups"].append({"id": "camper", "what": "x", "parts": ["box"]}),
                p["groups"].append({"id": "lot", "what": "x", "parts": ["camper"]})),
     "the group 'lot' is three deep (lot → camper → box): groups go two deep at most"),
    (lambda p: (p["groups"][0]["parts"].append("platform"), p["groups"][1]["parts"].append("box")),
     "the groups hold each other in a circle: box → platform → box"),
    (lambda p: p["groups"][0].__setitem__("mounts_on", ["truck"]), "the group 'box' mounts on 'truck', which isn't a part"),
    (lambda p: p["groups"][0].__setitem__("id", "Box Group"), "the group name 'Box Group' isn't a plain name"),
])
def test_a_grouping_that_can_t_be_used_is_refused_in_words(change, why):
    with pytest.raises(P.PlanError) as e:
        P.validate(_with(change))
    assert why in str(e.value), str(e.value)


def test_the_floor_dropped_from_a_plan_leaves_its_group():
    got = _with(lambda p: (p["parts"].append({"id": "truck_bed_floor", "what": "the bed's floor", "role": "fixed"}),
                           p["groups"][1]["parts"].append("truck_bed_floor")))
    plan = P.validate(got)
    assert plan.dropped == ["truck_bed_floor"] and "truck_bed_floor" not in P.group_parts(plan, "platform")


def test_groups_are_saved_with_the_plan_and_read_back_and_a_design_without_them_is_as_it_was(tmp_path):
    store = DesignStore.create("a slide-in camper for my small truck", base=str(tmp_path / "designs"))
    P.save(store, P.validate(CAMPER))
    again = DesignStore.load(store.design.slug, base=str(tmp_path / "designs"))
    assert again.design.groups == [
        {"id": "box", "what": "the camper box", "parts": CAMPER["groups"][0]["parts"], "mounts_on": ["platform"]},
        {"id": "platform", "what": "the bed platform", "parts": ["legs", "rails", "deck", "cleats"], "mounts_on": []}]
    assert [g.id for g in P.load(again).groups] == ["box", "platform"]
    assert again.design.plan["order"][0] == "legs"
    assert "groups" not in again.design.to_dict()                       # the plan holds them; design.yaml gains no key
    # a plan without groups: nothing about it changes, on file or read back
    flat = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    P.save(flat, P.validate({"parts": [{"id": "stool", "what": "a stool"}]}))
    assert flat.design.groups == [] and "groups" not in flat.design.plan
    assert P.load(flat).groups == []


def test_the_planner_is_told_about_groups_and_its_tool_takes_them():
    assert "groups" in P._tool()["input_schema"]["properties"]
    assert "sub-assembl" in P.SYSTEM and "two deep" in P.SYSTEM


def test_the_review_says_each_group_with_its_parts():
    got = P.headline(P.validate(CAMPER), "a slide-in camper")
    assert got == ("A slide-in camper in 9 parts, in 2 groups: the box, the camper box (the box floor (the box's floor "
                   "panel), the box wall left (the box's left wall), the box wall right (the box's right wall), the box "
                   "front (the box's front wall) and the box roof (the roof)); the platform, the bed platform (the deck "
                   "(the platform's deck), the rails (two rails on the bed), the legs (four legs) and the cleats (cleats "
                   "that hold the platform in the bed))."), got
    flat = {"parts": [{"id": "frame", "what": "a frame"}, {"id": "box", "what": "a box", "mounts_on": ["frame"]}]}
    assert P.headline(P.validate(flat), "a cargo box") == "A cargo box in 2 parts: the frame (a frame) and the box (a box)."



# --- #369 review -------------------------------------------------------------------------------------------------------
def test_a_group_s_parts_are_saved_in_build_order_however_the_planner_listed_them(tmp_path):
    """reviewer-2: the box listed roof, walls, floor was saved so, and read as the build order."""
    got = _with(lambda p: p["groups"][0].__setitem__("parts", ["box_roof", "box_wall_left", "box_wall_right",
                                                                "box_front", "box_floor"]))
    got["groups"].append({"id": "camper", "what": "the whole camper", "parts": ["box", "platform"]})
    store = DesignStore.create("a camper", base=str(tmp_path / "designs"))
    P.save(store, P.validate(got))
    by = {g["id"]: g["parts"] for g in store.design.groups}
    assert by["box"] == ["box_floor", "box_wall_left", "box_wall_right", "box_front", "box_roof"]
    assert by["platform"] == ["legs", "rails", "deck", "cleats"]
    assert by["camper"] == ["platform", "box"]                          # a group at its first part built
    built = store.design.plan["order"]
    for parts in by.values():
        firsts = [built.index(m) if m in built else min(built.index(x) for x in by[m]) for m in parts]
        assert firsts == sorted(firsts)


def test_design_groups_hands_out_copies(tmp_path):
    store = DesignStore.create("a camper", base=str(tmp_path / "designs"))
    P.save(store, P.validate(CAMPER))
    store.design.groups[0]["parts"].append("x")
    store.design.groups[0]["mounts_on"].append("y")
    assert "x" not in store.design.groups[0]["parts"] and "y" not in store.design.groups[0]["mounts_on"]


def test_the_review_names_the_groups_inside_a_group():
    got = _with(lambda p: p["groups"].append({"id": "camper", "what": "", "parts": ["box", "platform"]}))
    line = P.headline(P.validate(got), "a truck camper")
    assert line.startswith("A truck camper in 9 parts, in 1 group: the camper (the box, the camper box (the box floor"), line
    assert "; " not in line and "the platform, the bed platform (the deck (the platform's deck)" in line, line


def test_a_group_the_floor_s_removal_empties_goes_with_it():
    got = _with(lambda p: (p["parts"].append({"id": "bed_floor", "what": "the truck bed's floor", "role": "fixed"}),
                           p["groups"].append({"id": "bed", "what": "the truck bed", "parts": ["bed_floor"]}),
                           p["groups"][1].__setitem__("mounts_on", ["bed"])))
    plan = P.validate(got)
    assert [g.id for g in plan.groups] == ["box", "platform"] and plan.dropped == ["bed_floor"]
    assert P._group(plan, "platform").mounts_on == []
    assert P.dropped_line(plan) == "the bed floor is what it stands on, not a part"


@pytest.mark.parametrize("change,why", [
    (lambda p: p["groups"][0].__setitem__("mounts_on", ["box_floor"]), "the group 'box' mounts on 'box_floor', which it holds"),
    (lambda p: (p["groups"].append({"id": "camper", "what": "x", "parts": ["box", "platform"]}),
                p["groups"][0].__setitem__("mounts_on", ["camper"])),
     "the group 'box' mounts on 'camper', the group it's in"),
])
def test_a_group_mounting_on_its_own_or_its_holder_is_said_so(change, why):
    with pytest.raises(P.PlanError) as e:
        P.validate(_with(change))
    assert why in str(e.value), str(e.value)
