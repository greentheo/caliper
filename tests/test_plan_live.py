"""CALI-115 (#117) — what #3a's live run got wrong, before #3b builds on plans.

The foreman's live run (2026-11-06, at main 646a20a) planned three sentences. The plans here are written afresh in
the shapes it saw (the run's own plans stay in the foreman's scratchpad):
- the turbine's welded mast and staked base came back ``fixed`` ("which you have");
- a rule compared a skeleton number with its own value (always passes);
- invented rules of thumb were binding checks;
- the camper's plan had one ``=`` for ``==`` and the whole plan was thrown away, with no retry;
- the stool planned the bathroom floor as a second part, so its first run stopped for a review it never had."""

import copy
import json

import pytest

from caliper import chat, firstrun
from caliper import plan as P
from caliper.design import DesignStore

TURBINE_SAID = ("A Savonius wind turbine: printed buckets, plasma-cut end plates, a welded 7 ft mast on a staked base, "
                "for a generator I already have with a 1 in shaft. It survives a 60 mph gust.")

#: The turbine as the live planner had it (cut to five parts): the mast and base marked as his.
TURBINE = {
    "parts": [
        {"id": "base", "what": "a staked steel base", "made": "welded steel", "role": "fixed"},
        {"id": "mast", "what": "a welded 7 ft mast", "made": "welded steel tube", "role": "fixed",
         "mounts_on": ["base"]},
        {"id": "generator", "what": "the generator you have, 1 in shaft", "role": "fixed", "mounts_on": ["mast"]},
        {"id": "end_plates", "what": "two plasma-cut end plates", "made": "plasma-cut steel",
         "mounts_on": ["generator"]},
        {"id": "buckets", "what": "two printed buckets", "made": "printed", "mounts_on": ["end_plates"]},
    ],
    "skeleton": [
        {"name": "mast_h", "value": 7, "unit": "ft", "why": "the mast you asked for"},
        {"name": "shaft_d", "value": 25.4, "unit": "mm", "why": "the generator's shaft"},
        {"name": "rotor_d", "value": 600, "unit": "mm", "why": "a rotor this size"},
        {"name": "bucket_wall", "value": 5, "unit": "mm", "why": "to survive 60 mph"},
    ],
    "mates": [{"between": ["end_plates", "buckets"], "kind": "touch"}],
    "rules": [
        {"id": "mast_height", "expr": "abs(bbox(mast).dz - mast_h) <= 5", "source": "stated"},
        {"id": "base_stable", "expr": "bbox(base).dx >= bbox(mast).dz / 3", "why": "a third of the mast for gusts",
         "source": "stated"},
        {"id": "rotor_size", "expr": "bbox(buckets).dx <= rotor_d + 1"},
    ],
}


def _fixed_ok(plan):
    """The turbine with the mast and base to be made, as they should have come back."""
    got = copy.deepcopy(plan)
    for p in got["parts"]:
        if p["id"] in ("base", "mast"):
            p["role"] = "movable"
    return got


def fake(*plans):
    """The Anthropic client, stubbed: each plan tool call answers with the next of ``plans`` (the last repeats);
    any other call (the goals) answers with no checks. It records what it was asked."""
    asked = []

    class Fake:
        class messages:  # noqa: N801 — the client's shape
            @staticmethod
            def create(**kw):
                asked.append(kw)
                if kw.get("tools"):
                    n = sum(1 for k in asked if k.get("tools")) - 1
                    block = type("B", (), {"type": "tool_use", "input": copy.deepcopy(plans[min(n, len(plans) - 1)])})
                else:
                    block = type("B", (), {"type": "text", "text": json.dumps({"checks": [], "objectives": []})})
                return type("M", (), {"content": [block]})
    Fake.asked = asked
    Fake.plan_calls = lambda: [k for k in asked if k.get("tools")]
    return Fake


def _never(*a, **k):
    raise AssertionError("nothing is authored before the plan is reviewed")


# --- 1. fixed only for what the person has ------------------------------------------------------------------------
def test_a_part_to_be_made_is_never_one_you_have():
    with pytest.raises(P.PlanError) as e:
        P.validate(TURBINE, said=TURBINE_SAID)
    assert "'base' is marked as something you have, but it's to be made (welded)" in str(e.value), str(e.value)
    plan = P.validate(_fixed_ok(TURBINE), said=TURBINE_SAID)
    assert [p.id for p in plan.parts if p.role == "fixed"] == ["generator"]
    assert "the generator, which you have" in P.headline(plan, "a turbine")
    assert "the mast (a welded 7 ft mast), which you have" not in P.headline(plan, "a turbine")


@pytest.mark.parametrize("made", ["printed", "plasma cut", "laser-cut", "to build", "welded", "cut from ply"])
def test_each_way_of_making_it_says_it_isn_t_yours(made):
    plan = _fixed_ok(TURBINE)
    plan["parts"][2]["made"] = made
    with pytest.raises(P.PlanError, match="'generator' is marked as something you have, but it's to be made"):
        P.validate(plan)


def test_a_fixed_part_needs_words_that_say_you_have_something():
    with pytest.raises(P.PlanError, match="nothing you said says you have the generator"):
        P.validate(_fixed_ok(TURBINE), said="A Savonius wind turbine on a 7 ft mast.")


# --- 2. the floor isn't a part; one part to build builds at once -----------------------------------------------------
STOOL_SAID = "A box step stool from 3/4 in plywood, for the bathroom."
STOOL = {
    "parts": [{"id": "step_stool", "what": "a box step stool of plywood panels", "made": "sheet"},
              {"id": "bathroom_floor", "what": "the bathroom floor it stands on", "role": "fixed"}],
    "skeleton": [{"name": "top_w", "value": 14, "unit": "in"}, {"name": "leg_splay", "value": 3, "unit": "in"}],
    "mates": [{"between": ["step_stool", "bathroom_floor"], "kind": "touch"}],
    "rules": [{"id": "stable_base", "expr": "bbox(step_stool).dx >= top_w + 2 * leg_splay"},
              {"id": "on_floor", "expr": "abs(bbox(step_stool).min_z - bbox(bathroom_floor).max_z) <= 1"}],
}


@pytest.mark.parametrize("pid", ["bathroom_floor", "floor", "ground", "the_ground", "garage_wall", "room"])
def test_the_ground_the_floor_or_the_room_is_dropped_with_what_names_it(pid):
    plan = json.loads(json.dumps(STOOL).replace("bathroom_floor", pid))
    got = P.validate(plan)
    assert got.ids() == ["step_stool"] and not got.mates
    assert [r.id for r in got.rules] == ["stable_base"]
    assert got.dropped == [pid]


def test_the_stool_plans_one_part_and_its_first_run_doesn_t_stop(tmp_path, monkeypatch):
    built = []
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a[1]) or chat.TurnResult(
        "author", "no", ok=False, error="stub"))
    store = DesignStore.create(STOOL_SAID, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, strength=False, client=fake(STOOL))
    assert built and got.get("plan") is None and store.design.plan is None
    assert got["steps"]["plan"] == "one part (the bathroom floor is what it stands on, not a part)"


def test_one_part_to_build_beside_one_you_have_builds_at_once(tmp_path, monkeypatch):
    """A reference part doesn't stop the first run for review: there's still only one thing to make."""
    built = []
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a[1]) or chat.TurnResult(
        "author", "no", ok=False, error="stub"))
    store = DesignStore.create("A bracket for my generator (1 in shaft).", base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, strength=False, client=fake({"parts": [
        {"id": "bracket", "what": "a printed bracket", "made": "printed"},
        {"id": "generator", "what": "the generator you have", "role": "fixed"}]}))
    assert built and got.get("plan") is None and got["steps"]["plan"] == "one part"
    assert P.buildable(P.validate({"parts": [{"id": "a", "what": "x"}, {"id": "b", "what": "y", "role": "fixed"}]})) \
        == ["a"]


# --- 3. one retry, with the reason -----------------------------------------------------------------------------------
CAMPER = {"parts": [{"id": "cargo_box", "what": "a plywood cargo box", "made": "sheet"},
                    {"id": "frame", "what": "a welded frame", "made": "welded tube"}],
          "skeleton": [{"name": "box_width", "value": 48, "unit": "in"}],
          "rules": [{"id": "box_fits", "expr": "bbox(cargo_box).dy = box_width"}]}


def test_an_equals_sign_says_use_double_equals():
    with pytest.raises(P.PlanError) as e:
        P.validate(CAMPER)
    assert "`=` isn't a comparison; use `==`" in str(e.value), str(e.value)


def test_a_refused_plan_is_asked_for_again_once_with_the_reason(tmp_path):
    fixed = copy.deepcopy(CAMPER)
    fixed["rules"][0]["expr"] = "abs(bbox(cargo_box).dy - box_width) <= 2"
    store = DesignStore.create("A camper: a 48 in wide plywood cargo box on a welded frame.",
                               base=str(tmp_path / "designs"))
    client = fake(CAMPER, fixed)
    plan = P.propose(store, client=client)
    assert plan.ids() == ["cargo_box", "frame"]
    first, second = client.plan_calls()
    retry = second["messages"][0]["content"]
    assert "Your last plan was refused: the check 'box_fits'" in retry and "use `==`" in retry
    assert first["messages"][0]["content"] in retry                   # the same ask, with the reason after it


def test_refused_twice_it_falls_back_to_one_part_saying_why(tmp_path, monkeypatch):
    built = []
    monkeypatch.setattr(chat, "author_part", lambda *a, **k: built.append(a[1]) or chat.TurnResult(
        "author", "no", ok=False, error="stub"))
    store = DesignStore.create("A camper: a 48 in wide plywood cargo box on a welded frame.",
                               base=str(tmp_path / "designs"))
    client = fake(CAMPER)
    got = firstrun.build(store, use_llm=True, strength=False, client=client)
    assert len(client.plan_calls()) == 2 and built and store.design.plan is None
    assert got["steps"]["plan"].startswith("planning it in several parts didn't work (the check 'box_fits'")


# --- 4. no tautologies ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("expr", ["shaft_d == 25.4", "abs(rotor_d - 600) < 1", "rotor_d > mast_h", "1 < 2"])
def test_a_rule_that_measures_nothing_is_refused(expr):
    plan = _fixed_ok(TURBINE)
    plan["rules"].append({"id": "same", "expr": expr})
    with pytest.raises(P.PlanError, match="the check 'same' reads only the plan's own numbers, so it can't measure "
                                          "anything"):
        P.validate(plan)


@pytest.mark.parametrize("expr", ["bbox(mast).dz >= mast_h", "holes_aligned(end_plates, buckets)",
                                  "min_clearance(buckets, mast) >= 20"])
def test_a_rule_that_measures_a_part_isn_t(expr):
    plan = _fixed_ok(TURBINE)
    plan["rules"].append({"id": "real", "expr": expr})
    P.validate(plan)


# --- 5. invented numbers are proposals, not rules ---------------------------------------------------------------------
def test_what_the_person_didn_t_say_is_assumed_and_not_enforced(tmp_path):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    store.design.display_units = "in"
    store.save()
    got = firstrun.build(store, use_llm=True, client=fake(_fixed_ok(TURBINE)), author=_never, strength=False)
    assert got["plan"] == "review"
    plan = P.load(store)
    src = {s.name: s.source for s in plan.skeleton}
    assert src == {"mast_h": "stated", "shaft_d": "stated", "rotor_d": "assumed", "bucket_wall": "assumed"}
    # a rule is stated only when it reads a number the person gave: the planner's "stated" on the rule of thumb isn't
    rules = {r.id: r.source for r in plan.rules}
    assert rules == {"mast_height": "stated", "base_stable": "assumed", "rotor_size": "assumed"}
    assert [a.id for a in store.assembly.assertions] == ["mast_height"]          # only what was said is enforced
    from caliper import design_api

    shown = design_api.design_state(store)["plan"]
    assert "bucket wall: 0.197 in (to survive 60 mph) · assumed" in shown["numbers"]
    assert "mast h: 7 ft (the mast you asked for)" in shown["numbers"]
    checks = {c["id"]: c for c in shown["checks"]}
    assert checks["base_stable"]["source"] == "assumed" and checks["mast_height"]["source"] == "stated"


def test_keeping_an_assumed_check_enforces_it_and_a_revision_keeps_it_kept(tmp_path):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    firstrun.build(store, use_llm=True, client=fake(_fixed_ok(TURBINE)), author=_never, strength=False)
    P.keep(store, "base_stable")
    assert {a.id for a in store.assembly.assertions} == {"mast_height", "base_stable"}
    assert {r.id: r.source for r in P.load(store).rules}["base_stable"] == "kept"
    with pytest.raises(KeyError):
        P.keep(store, "no_such_check")
    # "make the mast 10 ft": the planner's answer doesn't say kept; the person's keep stands
    taller = _fixed_ok(TURBINE)
    taller["skeleton"][0]["value"] = 10
    got = chat.turn(store, "make the mast 10 ft", client=fake(taller), use_llm=True)
    assert got.action == "plan" and got.ok, got.reply
    assert {r.id: r.source for r in P.load(store).rules}["base_stable"] == "kept"
    assert {a.id for a in store.assembly.assertions} == {"mast_height", "base_stable"}


def test_the_planner_is_told_all_five():
    for said in ('role "fixed" only for what the person said they already have', "never the ground, the floor",
                 "compares a measure of a part", "`==`", '"assumed"'):
        assert said in P.SYSTEM, said


def test_keep_from_the_page(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    firstrun.build(store, use_llm=True, client=fake(_fixed_ok(TURBINE)), author=_never, strength=False)
    app = TestClient(create_app())
    got = app.post(f"/api/designs/{store.design.slug}/plan/checks/base_stable/keep")
    assert got.status_code == 200, got.text
    checks = {c["id"]: c["source"] for c in got.json()["plan"]["checks"]}
    assert checks["base_stable"] == "kept" and checks["rotor_size"] == "assumed"
    assert app.post(f"/api/designs/{store.design.slug}/plan/checks/nope/keep").status_code == 404
