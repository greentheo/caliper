"""CALI-94 (#73; rule 6) — a step is stood on at its front edge, so a load case puts a foot there.

A top resting on only two sides is weakest at its free edge, where a foot spreads over less of it (BS 8110 cl.
3.5.2.2's edge width; NEEDS ENGINEER CHECK). The designer put one foot in the middle, so a stool that fails at its
front edge read as holding, from a load case nobody stands in."""

import pytest

from caliper import answers, consistency, design_api, sandbox
from caliper.design import DesignStore

from .test_consistency import STOOL
from .test_load_study import BOX_STOOL, LOADS

pytest.importorskip("cadquery")

#: The test stool as the designer used to load it: the middle only (and the shove, side-on).
CENTRED = LOADS.replace('''    return [{"name": "stepping on the front edge", "lb": 200, "factor": 2.0,
             "lo": (-50, -d / 2, h - 2), "hi": (50, -d / 2 + 100, h)},
            {"name": "an adult stepping up"''', '''    return [{"name": "an adult stepping up"''')
WARN = ("the top is held on two sides, and no load stands on its free edge, where it's weakest: add a case, the same "
        "foot mid-span with its edge on the free edge (\"stepping on the front edge\")")


def _checks(src):
    run = sandbox.run_script(src, timeout=120)
    return {r.id: r for r in consistency.check(run.declared, run.geometry)}


def test_the_fixtures_are_what_they_say():
    assert CENTRED != LOADS and "stepping on the front edge" in LOADS and "front edge\"" not in CENTRED


def test_a_two_sided_top_with_only_a_centred_foot_gets_a_warning_and_still_passes():
    got = _checks(STOOL + CENTRED)
    edge = got["loads_edge"]
    assert edge.passed and edge.status == "pass" and edge.detail == WARN       # a warning: the round passes
    assert got["loads_land"].passed


def test_with_a_foot_at_the_edge_there_s_no_warning_and_it_lands():
    got = _checks(STOOL + LOADS)
    assert got["loads_edge"].passed and got["loads_edge"].detail == ""
    assert got["loads_land"].passed, got["loads_land"].detail                # the edge case is on the top


def test_a_top_held_all_round_keeps_its_one_centred_foot():
    assert "loads_edge" not in _checks(BOX_STOOL)


def test_the_part_card_says_what_s_missing(tmp_path):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", STOOL + CENTRED, intent="a step stool")
    lines = answers.answers(store, design_api.design_state(store), "stool")[0]["lines"]
    assert {"text": WARN[0].upper() + WARN[1:] + ".", "status": "warn", "study": "load"} in lines
    store.write_part("stool", STOOL + LOADS, intent="a step stool")
    lines = answers.answers(store, design_api.design_state(store), "stool")[0]["lines"]
    assert not [ln for ln in lines if "free edge" in ln["text"]]


def test_the_designer_is_told_to_put_a_foot_there():
    import os

    import caliper

    text = open(os.path.join(os.path.dirname(caliper.__file__), "part_scripts.md")).read()
    assert '"stepping on the front edge", the same foot mid-span with its edge on the free edge' in text
    assert "A top held all round keeps the one centred foot." in text
