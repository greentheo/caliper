"""CALI-35c (#3c) — the skeleton's numbers drive the parts.

#3's accept: changing ``mast_top_z`` rebuilds the mast and the hub without an authoring call, and re-measures every
rule. #143 review, the foreman's call: the drive writes the number into each part's PARAMS as a new version; builds
never override. Stubbed throughout: a fake planner answers the plan and its revision; the parts are simple boxes whose
PARAMS carry the skeleton's numbers (as #3b's designers are told to)."""

import copy

import pytest

from caliper import chat, firstrun, skeleton
from caliper import construction as C
from caliper.design import DesignStore

from .test_plan import TURBINE, TURBINE_SAID, _never, fake

pytest.importorskip("cadquery")

#: The turbine's plan with a rule that pins the hub to the mast's top: every interface is measured.
PLAN = copy.deepcopy(TURBINE)
PLAN["rules"].append({"id": "hub_on_mast", "expr": "abs(bbox(hub).min_z - mast_top_z) <= 1"})

BASE = '''import cadquery as cq

PARAMS = {"t": 19.0, "w": 600.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["w"], p["w"], p["t"], centered=(True, True, False)).translate((0, 0, -p["t"]))
'''

MAST = '''import cadquery as cq

PARAMS = {"mast_top_z": 2133.6, "d": 50.8}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["d"], p["d"], p["mast_top_z"], centered=(True, True, False))


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "mast", "kind": "stick", "material": "steel", "size": "2x2", "a": (0, 0, 0),
             "b": (0, 0, p["mast_top_z"])}]
'''

HUB = '''import cadquery as cq

PARAMS = {"mast_top_z": 2133.6, "h": 100.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(120, 120, p["h"], centered=(True, True, False)).translate((0, 0, p["mast_top_z"]))
'''

#: A hub that hard-codes the mast's top instead of reading it: it doesn't move, and the rule pinning it says so.
HARD_HUB = HUB.replace('PARAMS = {"mast_top_z": 2133.6, "h": 100.0}', 'PARAMS = {"h": 100.0}').replace(
    '.translate((0, 0, p["mast_top_z"]))', '.translate((0, 0, 2133.6))')


def _turbine(tmp_path, hub=HUB, plan=PLAN):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    store.design.display_units = "in"
    store.save()
    firstrun.build(store, use_llm=True, client=fake(plan), author=_never)     # the plan, reviewed
    for pid, script in (("base", BASE), ("mast", MAST), ("hub", hub)):                         # built, as #3b builds
        store.write_part(pid, script, intent=pid)
    return store


def _ten_ft(plan=PLAN):
    taller = copy.deepcopy(plan)
    taller["skeleton"][0]["value"] = 10
    return taller


def test_a_skeleton_number_changed_outside_a_drive_moves_nothing(tmp_path):
    """#143 review: a build never overrides a part's own PARAMS, so no part changes shape at the same version."""
    store = _turbine(tmp_path)
    store.design.skeleton[0]["value"] = 8                                          # 8 ft = 2438.4 mm, not driven
    store.save()
    assert store.part_geometry("mast").require_mesh().bounds[1][2] == pytest.approx(2133.6, abs=0.01)
    (stick,) = C.declared(store, "mast")["construction"]
    assert stick["b"][2] == pytest.approx(2133.6, abs=0.01)
    assert skeleton.readers(store, "mast_top_z") == ["mast", "hub"]             # the plan's rules name them


def test_make_the_mast_10_ft_rebuilds_the_mast_and_the_hub_with_no_authoring_call(tmp_path):
    store = _turbine(tmp_path)
    before = {p.id: p.version for p in store.design.parts}
    client = fake(_ten_ft())
    got = chat.turn(store, "make the mast 10 ft", client=client, use_llm=True, author=_never)
    assert got.action == "skeleton" and got.ok, got.reply
    assert len(client.asked) == 1                                                  # the plan's revision, nothing else
    after = {p.id: p.version for p in store.design.parts}
    assert after["mast"] == before["mast"] + 1 and after["hub"] == before["hub"] + 1
    assert after["base"] == before["base"]                                         # it doesn't read the number
    h = store.history("mast")[-1]
    assert h["action"] == "skeleton" and h["skeleton"] == {"mast_top_z": [7, 10]}
    assert h["feedback"] == "mast_top_z set to 10 ft (3048 mm) by the skeleton"
    # written into the script, its comment and the other lines kept: the build uses it as any number of its own
    assert '"mast_top_z": 3048.0, "d": 50.8}' in store.read_script("mast")
    assert '"mast_top_z": 3048.0, "h": 100.0}' in store.read_script("hub")
    assert store.part_geometry("mast").require_mesh().bounds[1][2] == pytest.approx(3048.0, abs=0.01)
    assert store.part_geometry("hub").require_mesh().bounds[0][2] == pytest.approx(3048.0, abs=0.01)
    # every rule measured again, with the new number
    rep = {r.id: r for r in store.evaluate().results}
    assert rep["mast_height"].status == "pass" and rep["hub_on_mast"].status == "pass"
    assert got.reply.startswith("Changed mast top z from 7 to 10 ft.")
    assert "Rebuilt from it, with no new design: the mast (mast_top_z), the hub (mast_top_z)." in got.reply
    assert "The design checks:" in got.reply


def test_a_part_that_hard_codes_a_shared_number_doesn_t_move_and_its_rule_fails(tmp_path):
    store = _turbine(tmp_path, hub=HARD_HUB)
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft()), use_llm=True, author=_never)
    assert got.action == "skeleton" and not got.ok
    assert "Rebuilt from it, with no new design: the mast (mast_top_z)." in got.reply
    assert ("! The hub: the plan's rules read mast_top_z on it, but its PARAMS has no mast_top_z: it doesn't move with "
            "it.") in got.reply
    rep = {r.id: r for r in store.evaluate().results}
    assert rep["mast_height"].status == "pass" and rep["hub_on_mast"].status == "fail"


def test_a_message_that_changes_more_than_a_number_isn_t_a_drive(tmp_path):
    store = _turbine(tmp_path)
    merged = _ten_ft()
    merged["rules"] = merged["rules"][:1]                                          # a check dropped too
    assert chat.skeleton_edit(store, "make the mast 10 ft and drop the checks", client=fake(merged)) is None
    assert chat.skeleton_edit(store, "make it blue", client=fake(_ten_ft())) is None          # no number named
    assert store.design.skeleton[0]["value"] == 7


def test_drive_names_an_unknown_number_and_changes_nothing(tmp_path):
    store = _turbine(tmp_path)
    with pytest.raises(ValueError, match="the skeleton has no hub_d"):
        skeleton.drive(store, [*store.design.skeleton, {"name": "hub_d", "value": 4, "unit": "in"}])
    assert skeleton.drive(store, store.design.skeleton)["changed"] == {}



# --- #143 review: who reads a number, inches, all or nothing, and what to check again -------------------------------

def test_a_params_key_that_only_shares_the_name_isn_t_driven(tmp_path):
    """No rule names the base with mast_top_z, so its own key of that name is its own. The base is in a rule of its
    own (#143's mutant: readers from any rule, not the number's, survived when the base was in none)."""
    base = BASE.replace('PARAMS = {"t": 19.0, "w": 600.0}', 'PARAMS = {"t": 19.0, "w": 600.0, "mast_top_z": 5.0}')
    plan = copy.deepcopy(PLAN)
    plan["rules"].append({"id": "base_flat", "expr": "bbox(base).max_z <= 1"})     # names the base, not the number
    store = _turbine(tmp_path, plan=plan)
    store.write_part("base", base, intent="base")
    assert skeleton.readers(store, "mast_top_z") == ["mast", "hub"]
    v = store.design.part("base").version
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft(plan)), use_llm=True, author=_never)
    assert got.action == "skeleton" and got.ok, got.reply
    assert store.design.part("base").version == v and '"mast_top_z": 5.0' in store.read_script("base")
    assert "the base" not in got.reply.split("The design checks:")[0]


def test_a_part_written_in_inches_is_refused_and_nothing_changes(tmp_path):
    inches = HUB.replace('"mast_top_z": 2133.6', '"mast_top_z": 84.0').replace(
        '.translate((0, 0, p["mast_top_z"]))', '.translate((0, 0, p["mast_top_z"] * 25.4))')
    store = _turbine(tmp_path, hub=inches)
    before = {p.id: p.version for p in store.design.parts}
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft()), use_llm=True, author=_never)
    assert got.action == "skeleton" and not got.ok
    assert got.reply.startswith("Nothing changed: the hub can't take it: its PARAMS has mast_top_z = 84, the skeleton's "
                                "2133.6 mm in inches: write it in mm")
    assert {p.id: p.version for p in store.design.parts} == before and store.design.skeleton[0]["value"] == 7


def test_a_part_that_won_t_build_with_the_new_number_changes_nothing(tmp_path):
    short = MAST.replace('    return cq.Workplane()', '    assert p["mast_top_z"] <= 2500, "too tall for one tube"\n'
                                                    '    return cq.Workplane()')
    store = _turbine(tmp_path)
    store.write_part("mast", short, intent="mast")
    before = {p.id: p.version for p in store.design.parts}
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft()), use_llm=True, author=_never)
    assert not got.ok and got.reply.startswith("Nothing changed: the mast can't take it: it won't build with it:")
    assert "too tall for one tube" in got.reply
    assert {p.id: p.version for p in store.design.parts} == before and store.design.skeleton[0]["value"] == 7
    assert '"mast_top_z": 2133.6' in store.read_script("hub")                     # the hub wasn't saved either


def test_a_driven_part_with_a_strength_check_says_check_it_again(tmp_path):
    import json
    import os

    from caliper import load_study

    store = _turbine(tmp_path)
    run = {"id": "20261107-000000-mast", "part": "mast", "version": store.design.part("mast").version, "created": 1.0,
           "min_safety": 2, "safety": 3.0, "holds": True, "cases": []}
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft()), use_llm=True, author=_never)
    assert got.ok and "Strength: check it again on the mast." in got.reply
