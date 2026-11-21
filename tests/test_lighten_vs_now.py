"""CALI-224 (#382): a Lighten on a lightened part weighs every step against the part as it is now.

Found on caliper-ui's tester walk: step-stool-5 v16, already lightened (17 holes, 5.59 lb lighter), was offered "5.23 lb
lighter" by a second Lighten. Use it made it 0.36 lb heavier: a step's holes replace the part's, and the step was weighed
from the part with no holes. Now each step's ``saved_lb`` is against now (``now_lb``, what the part's own holes save), an
offer is made only where that's lighter than now, and an older run of this version is read the same way."""

import json
import os

import pytest

from caliper import construction as C
from caliper import lighten
from caliper.design import DesignStore

from .test_cases_together import THREE

pytest.importorskip("cadquery")
pytest.importorskip("whittle")


def _box(tmp_path):
    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    store.write_part("box", THREE, intent="a foam box with a plywood floor, on two rails")
    return store


def test_a_second_lighten_weighs_its_steps_against_the_lightened_part(tmp_path):
    store = _box(tmp_path)
    first = lighten.study(store, "box", min_safety=1.3, steps=(0.5,))
    assert first["now_lb"] == 0.0                                       # no holes yet: bare and now are the same
    holed = max((st for st in first["stations"] if st["holds"] and not st.get("estimate") and st["holes"]),
                key=lambda st: st["saved_lb"])
    lighten.adopt(store, first["id"], holed["index"])
    store = DesignStore.load(store.root)
    assert lighten.holes_now_lb(store, "box") == pytest.approx(holed["saved_lb"], abs=0.02)   # what its holes save

    second = lighten.study(store, "box", min_safety=1.3, steps=(0.5,))
    assert second["now_lb"] == pytest.approx(holed["saved_lb"], abs=0.02)
    # its first step cuts no hole at all: used, it would fill the part's holes back in, so it reads that much heavier
    assert second["stations"][0]["holes"] == 0
    assert second["stations"][0]["saved_lb"] == pytest.approx(-second["now_lb"], abs=0.02)
    rec = lighten.load_run(store, second["id"])
    offer = rec.get("offer") or {}
    for st in rec["stations"]:
        if offer.get("offers") and st["index"] == offer["index"]:
            assert st["saved_lb"] > 0                                      # never an offer that puts weight back
    if offer.get("offers"):                                              # used, it's that much lighter than now
        before = C.report(store, "box")["mass_lb"]
        lighten.adopt(store, rec["id"], offer["index"])
        after = C.report(DesignStore.load(store.root), "box")["mass_lb"]
        st = next(s for s in rec["stations"] if s["index"] == offer["index"])
        assert before - after == pytest.approx(st["saved_lb"], abs=0.05)


def test_a_step_that_puts_weight_back_reads_below_zero_and_isn_t_offered():
    rec = {"min_safety": 2.0, "part_lb": 20.0,
           "stations": [{"index": 0, "phase": "walls", "safety": 3.8, "holds": True, "holes": 17, "saved_lb": 5.59},
                        {"index": 1, "phase": "walls", "safety": 3.8, "holds": True, "holes": 13, "saved_lb": 5.23}]}
    lighten.against_now(rec, 5.59)
    assert [st["saved_lb"] for st in rec["stations"]] == [0.0, -0.36] and rec["now_lb"] == 5.59
    assert not (lighten._offered(rec) or {}).get("offers")              # 0.36 lb heavier than now: never an offer


def test_an_older_run_of_this_version_is_read_against_now(tmp_path):
    """A run written before this fix has no ``now_lb``: read back, it's weighed against the part's holes as they are."""
    store = _box(tmp_path)
    first = lighten.study(store, "box", min_safety=1.3, steps=(0.5,))
    holed = max((st for st in first["stations"] if st["holds"] and not st.get("estimate") and st["holes"]),
                key=lambda st: st["saved_lb"])
    lighten.adopt(store, first["id"], holed["index"])
    store = DesignStore.load(store.root)
    rec = lighten.study(store, "box", min_safety=1.3, steps=(0.5,))
    path = os.path.join(lighten.runs_dir(store), rec["id"], "run.json")
    old = json.load(open(path))
    now = old.pop("now_lb")
    for st in old["stations"]:
        st["saved_lb"] = round(st["saved_lb"] + now, 2)                   # as it was written: from the bare part
    json.dump(old, open(path, "w"))
    back = lighten.load_run(store, rec["id"])
    assert back["now_lb"] == pytest.approx(now, abs=0.01)
    assert [st["saved_lb"] for st in back["stations"]] == pytest.approx([st["saved_lb"] for st in rec["stations"]],
                                                                         abs=0.011)


def test_the_study_s_line_never_says_lighter_for_a_step_heavier_than_now():
    """The studies' line for a lightening: a best step at or below now is "nothing lighter holds", never "up to -0.36 lb"."""
    from caliper import studies

    rec = {"kind": "lighten", "min_safety": 2.0,
           "stations": [{"index": 0, "phase": "walls", "safety": 3.8, "holds": True, "holes": 13, "saved_lb": 5.23}]}
    lighten.against_now(rec, 5.59)
    text, ok = studies._headline("lighten", rec)
    assert text == "nothing lighter holds" and ok is False


def test_a_picture_cut_into_a_panel_isn_t_a_lightening_hole(tmp_path):
    """Use it keeps a picture (CALI-78) and replaces only the lightening holes: so only those are what the part saves now."""
    from .test_lighten import HOLE
    from .test_load_study import BOX_STOOL

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL + HOLE.replace('"piece": "left"', '"piece": "left", "picture": "T-rex"'),
                     intent="a box stool with a picture")
    assert lighten.holes_now_lb(store, "stool") == 0.0
    store.write_part("stool", BOX_STOOL + HOLE, intent="a box stool with a hole")
    assert lighten.holes_now_lb(store, "stool") > 0.0


def test_a_hole_weighs_as_deep_as_it_goes(tmp_path):
    """A lightening hole goes right through its sheet (its depth is the sheet's); one written by hand can be a pocket."""
    from .test_lighten import HOLE
    from .test_load_study import BOX_STOOL

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL + HOLE, intent="a box stool with a hole")
    through = lighten.holes_now_lb(store, "stool")
    store.write_part("stool", BOX_STOOL + HOLE.replace('"depth": 19.05', '"depth": 9.525'), intent="half as deep")
    assert lighten.holes_now_lb(store, "stool") == pytest.approx(through / 2, abs=0.006)
    store.write_part("stool", BOX_STOOL + HOLE.replace('"depth": 19.05', '"depth": 40.0'), intent="deeper than its sheet")
    assert lighten.holes_now_lb(store, "stool") == pytest.approx(through, abs=0.006)
