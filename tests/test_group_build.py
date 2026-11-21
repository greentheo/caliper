"""CALI-36 (#17) slice C — a plan in groups, built in one go: the cost said per group first, the progress and the reply
by group, and each part's designer told the group it's in and what that sits on.

Theo's truck camper: "a platform plus a box on top, built in one go". A stub designer builds each part as a box: no live
call. A plan without groups builds and says exactly what it did."""

import pytest

from caliper import build_plan
from caliper import plan as P
from caliper.design import DesignStore

pytest.importorskip("cadquery")


def _box(x, y, z, at_z):
    return ("def build(params):\n    import cadquery as cq\n"
            f"    return cq.Workplane('XY').box({x}, {y}, {z}, centered=False).translate((0, 0, {at_z}))\n")


SCRIPTS = {"legs": _box(40, 40, 300, 0), "deck": _box(1000, 600, 19, 300), "floor": _box(1000, 600, 12, 319),
           "wall": _box(12, 600, 500, 331), "ladder": _box(40, 300, 800, 0).replace("translate((0, 0, 0))",
                                                                                     "translate((-200, 0, 0))")}
CAMPER = {
    "parts": [{"id": "floor", "what": "the box's floor", "made": "sheet", "mounts_on": ["platform"]},
              {"id": "wall", "what": "a wall", "made": "sheet", "mounts_on": ["floor"]},
              {"id": "legs", "what": "four legs", "made": "lumber"},
              {"id": "deck", "what": "the deck", "made": "sheet", "mounts_on": ["legs"]},
              {"id": "ladder", "what": "a ladder up to the box", "made": "printed"}],
    "groups": [{"id": "box", "what": "the camper box", "parts": ["floor", "wall"], "mounts_on": ["platform"]},
               {"id": "platform", "what": "the bed platform", "parts": ["legs", "deck"]}],
}


class Stub:
    def __init__(self):
        self.asked = {}

    def __call__(self, spec, feedback, prior):
        self.asked.setdefault(spec.part, spec.intent)
        return SCRIPTS[spec.part]


def _build(tmp_path, plan):
    s = DesignStore.create("a slide-in camper for my small truck", base=str(tmp_path / "designs"))
    P.save(s, P.validate(plan), status="review")
    stub, steps = Stub(), []
    got = build_plan.build(s, {}, lambda kind, text, **k: steps.append((text, k)), author=stub, use_llm=False)
    return s, got, stub, steps


def test_the_cost_is_said_per_group_first():
    assert build_plan.cost(P.validate(CAMPER)) == ("5 parts to make (the platform: 2, the box: 2, and 1 on its own), "
                                                   "up to 2 designer tries each (at most 10)")
    flat = P.validate({"parts": [{"id": "a", "what": "a"}, {"id": "b", "what": "b"}]})
    assert build_plan.cost(flat) == "2 parts to make, up to 2 designer tries each (at most 4)"


def test_a_plan_in_groups_is_built_group_by_group_and_said_so(tmp_path):
    s, got, stub, steps = _build(tmp_path, CAMPER)
    assert got["ok"] and got["plan"] == "built", got["reply"]
    assert list(stub.asked) == ["legs", "deck", "floor", "wall", "ladder"]
    groups = [(t, k) for t, k in steps if k.get("step") == "group"]
    assert groups == [("The platform: 2 parts", {"step": "group", "group": "platform"}),
                      ("The box: 2 parts", {"step": "group", "group": "box"})]
    reply = got["reply"]
    assert reply.startswith("I built the plan's 5 parts, in order:\nThe platform:\n- the legs: built"), reply
    assert "\nThe box:\n- the floor: built" in reply and reply.index("The box:") > reply.index("- the deck: built")
    assert "\nOn its own:\n- the ladder: built" in reply, reply


def test_each_part_s_designer_is_told_its_group_and_what_that_sits_on(tmp_path):
    _, _, stub, _ = _build(tmp_path, CAMPER)
    assert ("This part is in the box (the camper box), with the wall. The box sits on the platform (the legs and the "
            "deck), built before it.") in stub.asked["floor"], stub.asked["floor"]
    assert "This part is in the platform (the bed platform), with the deck." in stub.asked["legs"]
    assert "sits on" not in stub.asked["legs"]
    assert "This part is in" not in stub.asked["ladder"]


def test_a_plan_without_groups_builds_and_says_what_it_did(tmp_path):
    flat = {"parts": [p for p in CAMPER["parts"]]}
    flat["parts"] = [{**p, "mounts_on": [m for m in p.get("mounts_on", []) if m != "platform"]} for p in flat["parts"]]
    _, got, stub, steps = _build(tmp_path, flat)
    assert not [s for s in steps if s[1].get("step") == "group"]
    assert got["reply"].startswith("I built the plan's 5 parts, in order:\n- the floor: built"), got["reply"]
    assert "The platform" not in got["reply"] and "On its own" not in got["reply"]
    assert not any("This part is in" in v for v in stub.asked.values())


def test_the_group_line_is_for_the_designer_never_the_part_s_intent(tmp_path):
    s, _, _, _ = _build(tmp_path, CAMPER)
    assert s.design.part("floor").intent == "the box's floor (sheet)"
    assert not any("This part is in" in (p.intent or "") for p in s.design.parts)


# --- #415 review (reviewer-2) -----------------------------------------------------------------------------------------
class Refuses(Stub):
    def __init__(self, no):
        super().__init__()
        self.no = no

    def __call__(self, spec, feedback, prior):
        self.asked.setdefault(spec.part, spec.intent)
        if spec.part == self.no:
            return "def build(params):\n    raise ValueError('the stub says no')\n"
        return SCRIPTS[spec.part]


def _run(tmp_path, plan, author):
    s = DesignStore.create("a slide-in camper for my small truck", base=str(tmp_path / "designs"))
    P.save(s, P.validate(plan), status="review")
    steps = []
    got = build_plan.build(s, {}, lambda kind, text, **k: steps.append((text, k)), author=author, use_llm=False)
    return s, got, steps


def test_a_stop_in_a_group_names_the_group_what_stays_and_what_isn_t_built(tmp_path):
    _, got, _ = _run(tmp_path, CAMPER, Refuses("wall"))
    assert got["reply"] == ("I couldn't build the wall, in the box: the stub says no.\n\nThe platform's 2 parts, and the "
                            "box's floor stay; the ladder isn't built yet. Build it again to retry it, change the plan, "
                            "or carry on without it."), got["reply"]


def test_a_stop_in_a_plan_without_groups_says_what_it_said(tmp_path):
    flat = {"parts": [{**p, "mounts_on": [m for m in p.get("mounts_on", []) if m != "platform"]} for p in CAMPER["parts"]]}
    _, got, _ = _run(tmp_path, flat, Refuses("wall"))
    assert got["reply"].startswith("I couldn't build the wall: the stub says no.\n\nThe parts before it stay ("), got["reply"]


def test_a_group_whose_parts_aren_t_listed_together_is_headed_once(tmp_path):
    split = {"parts": [{"id": "legs", "what": "four legs", "made": "lumber"},
                       {"id": "ladder", "what": "a ladder", "made": "printed"},
                       {"id": "deck", "what": "the deck", "made": "sheet"}],
             "groups": [{"id": "platform", "what": "the bed platform", "parts": ["legs", "deck"]}]}
    _, got, steps = _run(tmp_path, split, Stub())
    assert [t for t, k in steps if k.get("step") == "group"] == ["The platform: 2 parts"]
    assert got["reply"].count("The platform:") == 1 and "\nThe platform:\n- the legs: built" in got["reply"]
    assert got["reply"].index("- the deck: built") < got["reply"].index("On its own:"), got["reply"]


def test_two_deep_groups_keep_their_own_heads(tmp_path):
    deep = {**CAMPER, "groups": CAMPER["groups"] + [{"id": "camper", "what": "the whole camper", "parts": ["box", "platform"]}]}
    assert build_plan.cost(P.validate(deep)).startswith("5 parts to make (the platform: 2, the box: 2, and 1 on its own)")
    _, got, steps = _run(tmp_path, deep, Stub())
    assert [t for t, k in steps if k.get("step") == "group"] == ["The platform: 2 parts", "The box: 2 parts"]


def test_a_part_you_have_isn_t_counted_in_its_group_s_progress(tmp_path):
    mine = {**CAMPER, "parts": CAMPER["parts"] + [{"id": "bed_liner", "what": "the bed liner I have", "role": "fixed"}],
            "groups": [CAMPER["groups"][0], {**CAMPER["groups"][1], "parts": ["legs", "deck", "bed_liner"]}]}
    assert "the platform: 2" in build_plan.cost(P.validate(mine))
    _, _, steps = _run(tmp_path, mine, Stub())
    assert "The platform: 2 parts" in [t for t, k in steps if k.get("step") == "group"]


def test_what_a_designer_is_told_two_deep_and_of_a_group_on_a_part():
    deep = P.validate({**CAMPER, "groups": [
        {"id": "box", "what": "the camper box", "parts": ["floor", "wall"], "mounts_on": ["ladder"]},
        {"id": "platform", "what": "the bed platform", "parts": ["legs", "deck"]},
        {"id": "camper", "what": "the whole camper", "parts": ["platform"], "mounts_on": ["ladder"]}]})
    legs = build_plan.told(deep, "legs")
    assert "This part is in the platform (the bed platform), part of the camper, with the deck." in legs, legs  # inner
    assert "The platform sits on the ladder, built before it." in legs, legs          # the outer group's mount, said
    floor = build_plan.told(deep, "floor")
    assert "The box sits on the ladder, built before it." in floor, floor             # on a part: no "(the ladder)"
    assert floor.rstrip().endswith("Build only this part: the group's other parts are built on their own, from the same "
                                   "skeleton.")


def test_the_group_line_never_reaches_the_stored_spec(tmp_path):
    s, _, _, _ = _build(tmp_path, CAMPER)
    assert "This part is in" not in (s.read_spec("floor").intent or "")
