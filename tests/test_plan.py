"""CALI-35 (#3a) — the plan: parts, the numbers they share, the checks between them, and a build order."""

import copy

import pytest

from caliper import plan as P

#: The wind turbine (#11) as a planner might plan it: a base, a mast on it, a hub on the mast, a rotor on the hub.
TURBINE = {
    "parts": [
        {"id": "rotor", "what": "two printed buckets between two plates", "made": "printed", "mounts_on": ["hub"]},
        {"id": "hub", "what": "the hub that holds the rotor to the shaft", "made": "printed", "mounts_on": ["mast"]},
        {"id": "mast", "what": "a 2 in steel tube, 7 ft", "made": "welded tube", "mounts_on": ["base"]},
        {"id": "base", "what": "a plywood base, staked down", "made": "sheet"},
    ],
    "skeleton": [
        {"name": "mast_top_z", "value": 7, "unit": "ft", "why": "the mast's top"},
        {"name": "shaft_d", "value": 1, "unit": "in", "why": "the generator's shaft"},
        {"name": "rotor_d", "value": 900, "unit": "mm", "why": "the rotor's size"},
    ],
    "mates": [{"between": ["hub", "mast"], "kind": "touch"}, {"between": ["rotor", "mast"]}],
    "rules": [
        {"id": "mast_height", "expr": "abs(bbox(mast).max.z - mast_top_z) <= 1"},
        {"id": "hub_on_rotor", "expr": "hole_misalignment(hub, rotor) <= 0.5"},
        {"id": "rotor_clear", "expr": "min_clearance(rotor, mast) >= 20"},
    ],
}


def _with(**change):
    got = copy.deepcopy(TURBINE)
    for k, v in change.items():
        v(got) if callable(v) else got.__setitem__(k, v)
    return got


def test_the_turbine_plans_four_parts_built_base_first():
    plan = P.validate(TURBINE)
    assert plan.ids() == ["rotor", "hub", "mast", "base"]
    assert P.order(plan) == ["base", "mast", "hub", "rotor"]
    assert P.mm(plan.value("mast_top_z")) == pytest.approx(2133.6)
    assert P.mm(plan.value("shaft_d")) == pytest.approx(25.4)


def test_parts_that_mount_on_nothing_keep_the_plan_s_order():
    plan = P.validate({"parts": [{"id": "frame", "what": "a frame"}, {"id": "box", "what": "a box", "mounts_on": ["frame"]},
                                 {"id": "leaf", "what": "the car's back", "role": "fixed"}]})
    assert P.order(plan) == ["frame", "box", "leaf"]


@pytest.mark.parametrize("change,why", [
    (lambda p: p["parts"][3].__setitem__("mounts_on", ["rotor"]),
     "the parts mount on each other in a circle: rotor → hub → mast → base → rotor"),
    (lambda p: p["parts"][0].__setitem__("mounts_on", ["rotor"]), "'rotor' mounts on itself"),
    (lambda p: p["parts"][0].__setitem__("mounts_on", ["tower"]), "'rotor' mounts on 'tower', which isn't a part"),
    (lambda p: p["rules"].append({"id": "tail", "expr": "min_clearance(tail, mast) >= 5"}),
     "the check 'tail' names 'tail', which isn't a part or a skeleton number"),
    (lambda p: p["mates"].append({"between": ["hub", "tail"]}), "a mate names 'tail', which isn't a part"),
    (lambda p: p["skeleton"][1].__setitem__("unit", ""), "the skeleton number 'shaft_d' has no unit"),
    (lambda p: p["skeleton"][1].__setitem__("unit", "furlongs"), "'shaft_d' is in 'furlongs', not a unit"),
    (lambda p: p["skeleton"][1].pop("unit"), "the plan isn't in the shape a plan takes"),
    (lambda p: p["rules"].append({"id": "x", "expr": "__import__('os').system('ls') == 0"}),
     "the check 'x' calls something that isn't a measure"),
    (lambda p: p["rules"].append({"id": "z", "expr": "open('/etc/passwd') is None"}),
     "the check 'z' calls open(), which isn't a measure"),
    (lambda p: p["rules"].append({"id": "y", "expr": "bbox(mast).max.z >"}), "the check 'y' isn't an expression"),
    (lambda p: p["parts"].append({"id": "hub", "what": "another hub"}), "two parts are both called 'hub'"),
    (lambda p: p["parts"].append({"id": "Big Hub", "what": "x"}), "'Big Hub' isn't a plain name"),
    (lambda p: p["skeleton"].append({"name": "hub", "value": 1, "unit": "mm"}), "'hub' names two things"),
    (lambda p: p["parts"].clear(), "the plan has no parts"),
])
def test_a_plan_that_cant_be_used_is_refused_with_the_reason(change, why):
    with pytest.raises(P.PlanError, match=None) as e:
        P.validate(_with(x=change))
    assert why in str(e.value), str(e.value)


# --- the planner, the review, and building as today ------------------------------------------------------------
import json  # noqa: E402

from caliper import chat, firstrun  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

TURBINE_SAID = "A wind turbine from two plastic buckets, on a 7 ft steel mast, for my generator (1 in shaft)."


def fake(plan_json):
    """A stand-in for the Anthropic client: the plan tool answers with ``plan_json``; any other call (the goals)
    answers with no checks. It records what it was asked."""
    asked = []

    class Fake:
        class messages:  # noqa: N801 — the client's shape
            @staticmethod
            def create(**kw):
                asked.append(kw)
                if kw.get("tools"):
                    block = type("B", (), {"type": "tool_use", "input": copy.deepcopy(plan_json)})
                else:
                    block = type("B", (), {"type": "text", "text": json.dumps({"checks": [], "objectives": []})})
                return type("M", (), {"content": [block]})
    Fake.asked = asked
    return Fake


def _never(*a, **k):
    raise AssertionError("nothing is authored before the plan is reviewed")


def test_a_plan_of_four_parts_is_saved_and_stops_for_review(tmp_path):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    client = fake(TURBINE)
    got = firstrun.build(store, use_llm=True, client=client, author=_never, strength=False)
    assert got["plan"] == "review" and got["part"] is None and not store.design.parts
    assert got["reply"].startswith(
        "A wind turbine in 4 parts: the rotor (two printed buckets between two plates), the hub, the mast (a 2 in "
        "steel tube, 7 ft) and the base (a plywood base, staked down).\n\nThat's the plan, before anything's drawn"), \
        got["reply"]
    plan_call = next(k for k in client.asked if k.get("tools"))
    assert TURBINE_SAID in plan_call["messages"][0]["content"]
    assert plan_call["tool_choice"] == {"type": "tool", "name": "plan"}
    # what's on file, read back as the next load reads it
    again = DesignStore.load(store.design.slug, base=str(tmp_path / "designs"))
    assert [p.id for p in again.assembly.parts] == ["rotor", "hub", "mast", "base"]
    assert {a.id for a in again.assembly.assertions} == {"mast_height", "hub_on_rotor", "rotor_clear"}
    assert [m.kind for m in again.assembly.mates] == ["touch", "no_interference"]
    assert [s["name"] for s in again.design.skeleton] == ["mast_top_z", "shaft_d", "rotor_d"]
    assert again.design.plan["order"] == ["base", "mast", "hub", "rotor"] and again.design.plan["status"] == "review"
    # nothing's built, so nothing's broken: every rule waits for its parts
    report, errors = again.evaluate(tolerant=True)
    assert errors == {} and {r.status for r in report.results} == {"deferred"}
    assert any(r.detail == "waits for mast to be built" for r in report.results)
    assert "under What is it?. Say what to change" in got["reply"] and "*" not in got["reply"].split("**")[0]
    # and the page shows it: the plan on What is it?, its numbers one click down
    from caliper import answers
    from caliper.design_api import design_state

    state = design_state(again)
    assert [p["id"] for p in state["plan"]["parts"]] == ["base", "mast", "hub", "rotor"]
    assert "mast top z: 2134 mm (the mast's top)" in state["plan"]["numbers"]
    (what,) = [c for c in answers.answers(again, state) if c["key"] == "what"]
    assert what["lines"][1]["text"] == state["plan"]["headline"] and what["lines"][1]["status"] == "warn"


def test_build_it_on_a_reviewed_plan_says_what_comes_next_and_authors_nothing(tmp_path):
    """#3a builds nothing past today's one part: a second Build it is never a silent no-op."""
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    firstrun.build(store, use_llm=True, client=fake(TURBINE), author=_never, strength=False)
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=_never, strength=False)
    assert got["reply"] == "The plan's saved: 4 parts. Building them one by one, in order, comes next (#3b)."
    assert not store.design.parts and store.design.plan["status"] == "saved"
    assert store.log()[-1]["reply"] == got["reply"]


def test_make_the_mast_10_ft_changes_that_number_and_nothing_else(tmp_path):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    store.design.display_units = "in"
    store.save()
    firstrun.build(store, use_llm=True, client=fake(TURBINE), author=_never, strength=False)
    before_asm = store.assembly.to_yaml()
    taller = copy.deepcopy(TURBINE)
    taller["skeleton"][0]["value"] = 10
    client = fake(taller)
    got = chat.turn(store, "make the mast 10 ft", client=client, use_llm=True)
    assert got.action == "plan" and got.ok
    assert got.reply.startswith("Changed the plan: mast top z: 7 ft → 10 ft."), got.reply
    assert '"mast_top_z"' in client.asked[0]["messages"][0]["content"]          # it was shown the plan as it is
    assert [(s["name"], s["value"]) for s in store.design.skeleton] == [("mast_top_z", 10), ("shaft_d", 1),
                                                                          ("rotor_d", 900)]
    assert store.assembly.to_yaml() == before_asm and not store.design.parts
    # a question during review is answered, not taken as a change
    assert chat._reviewing(store)


def test_a_plan_the_planner_gets_wrong_is_refused_and_it_builds_as_one(tmp_path, monkeypatch):
    built = []
    looped = copy.deepcopy(TURBINE)
    looped["parts"][3]["mounts_on"] = ["rotor"]
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a) or chat.TurnResult("author", "no", ok=False,
                                                                                                    error="stub"))
    got = firstrun.build(store, use_llm=True, client=fake(looped), strength=False)
    assert built and store.design.plan is None
    assert got["steps"]["plan"].startswith("planning it in several parts didn't work (the parts mount on each other")


def test_the_stool_plans_one_part_and_builds_as_today(tmp_path, monkeypatch):
    built = []
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a[1]) or chat.TurnResult(
        "author", "no", ok=False, error="stub"))
    store = DesignStore.create("A box step stool from 3/4 in plywood.", base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, strength=False, client=fake(
        {"parts": [{"id": "step_stool", "what": "a box step stool of plywood panels", "made": "sheet"}]}))
    assert built == ["box_step"]                         # as today: the whole sentence, one part
    assert got["steps"]["plan"] == "one part" and store.design.plan is None


def test_with_no_key_it_builds_one_part_and_says_planning_needs_claude(tmp_path, monkeypatch):
    built = []
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a[1]) or chat.TurnResult(
        "author", "no", ok=False, error="stub"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, strength=False)
    assert len(built) == 1 and store.design.plan is None
    assert got["steps"]["plan"] == "planning it in several parts needs Claude: I built it as one"
