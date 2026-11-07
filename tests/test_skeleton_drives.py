"""CALI-35c (#3c) — the skeleton's numbers drive the parts.

#3's accept: changing ``mast_top_z`` rebuilds the mast and the hub without an authoring call, and re-measures every
rule. Stubbed throughout: a fake planner answers the plan and its revision; the parts are written as simple boxes that
read the skeleton (as #3b's designers are told to)."""

import copy

import pytest

from caliper import chat, firstrun, skeleton
from caliper import construction as C
from caliper.assembly import skeleton_params
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


def _turbine(tmp_path, hub=HUB):
    store = DesignStore.create(TURBINE_SAID, base=str(tmp_path / "designs"))
    store.design.display_units = "in"
    store.save()
    firstrun.build(store, use_llm=True, client=fake(PLAN), author=_never, strength=False)     # the plan, reviewed
    for pid, script in (("base", BASE), ("mast", MAST), ("hub", hub)):                         # built, as #3b builds
        store.write_part(pid, script, intent=pid)
    return store


def _ten_ft():
    taller = copy.deepcopy(PLAN)
    taller["skeleton"][0]["value"] = 10
    return taller


def test_a_part_reads_only_the_skeleton_numbers_its_params_name():
    values = {"mast_top_z": 3048.0, "shaft_d": 25.4}
    assert skeleton_params(MAST, values) == {"mast_top_z": 3048.0}
    assert skeleton_params(BASE, values) == {}
    assert skeleton_params(MAST, None) == {} and skeleton_params(HARD_HUB, values) == {}


def test_the_mast_is_built_from_the_skeleton_not_its_own_default(tmp_path):
    store = _turbine(tmp_path)
    store.design.skeleton[0]["value"] = 8                                          # 8 ft = 2438.4 mm
    store.save()
    assert store.part_geometry("mast").require_mesh().bounds[1][2] == pytest.approx(2438.4, abs=0.01)
    assert store.part_geometry("hub").require_mesh().bounds[0][2] == pytest.approx(2438.4, abs=0.01)
    assert store.part_geometry("base").require_mesh().bounds[1][2] == pytest.approx(0.0, abs=0.01)
    # what it declares moves with it: its pieces are of the shape it has
    (stick,) = C.declared(store, "mast")["construction"]
    assert stick["b"][2] == pytest.approx(2438.4, abs=0.01)


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
    assert store.history("mast")[-1]["action"] == "skeleton"
    assert store.history("mast")[-1]["skeleton"] == {"mast_top_z": [7, 10]}
    assert store.part_geometry("mast").require_mesh().bounds[1][2] == pytest.approx(3048.0, abs=0.01)
    assert store.part_geometry("hub").require_mesh().bounds[0][2] == pytest.approx(3048.0, abs=0.01)
    # every rule measured again, with the new number
    rep = {r.id: r for r in store.evaluate().results}
    assert rep["mast_height"].status == "pass" and rep["hub_on_mast"].status == "pass"
    assert got.reply.startswith("Changed mast top z from 7 to 10 ft.")
    assert "Rebuilt from it, with no new design: the mast, the hub." in got.reply
    assert "The design checks:" in got.reply


def test_a_part_that_hard_codes_a_shared_number_doesn_t_move_and_its_rule_fails(tmp_path):
    store = _turbine(tmp_path, hub=HARD_HUB)
    got = chat.turn(store, "make the mast 10 ft", client=fake(_ten_ft()), use_llm=True, author=_never)
    assert got.action == "skeleton" and not got.ok
    assert "the mast." in got.reply and "the hub" not in got.reply.split("The design checks:")[0]
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
