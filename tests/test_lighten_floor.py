"""CALI-151 (#207) — a Lighten that saves a few ounces doesn't get a button.

The reviewer's re-check of #201: a Lighten is exempt from the $1 floor (the sheet is bought whole), but every hole is a cut in the shop
plus a re-check, so a few ounces is the same waste as a 7¢ carve, paid in labour. Under a quarter pound or 5% of the part, whichever
is larger, the card says what it would save and leaves it in the study."""
import json
import os

import pytest

from caliper import use_step


def _steps(*saved):
    return [{"index": i + 1, "safety": 6.0, "whole": 6.0, "saved_lb": lb, "seen": True} for i, lb in enumerate(saved)]


def _lb(st):
    return f"{st['saved_lb']:g} lb lighter"


def test_the_floor_is_one_named_number():
    assert use_step.LIGHTEN_MIN == {"lb": 0.25, "share": 0.05, "most_lb": 1.0}
    assert use_step.lighten_floor(None) == 0.25 and use_step.lighten_floor(2.0) == 0.25      # 5% of 2 lb is 0.1
    assert use_step.lighten_floor(10.0) == pytest.approx(0.5)                                # 5% bites between 5 and 20 lb
    assert use_step.lighten_floor(20.0) == pytest.approx(1.0)
    assert use_step.lighten_floor(40.0) == 1.0               # a pound saved is a pound carried, whatever it comes off (#252 review)


def test_under_the_floor_there_s_no_button_and_it_says_what_it_would_save():
    got = use_step.choose(_steps(0.2), 2.0, "saved_lb", _lb, as_drawn=6.1, least=0.25)
    assert got["offers"] is False and got["kind"] == "small"
    assert got["said"] == ("It would make it 0.2 lb lighter, at almost no cost in strength: too little to be worth the cuts and a re-check, "
                           "so it's left in the study.")


def test_at_the_floor_it_is_offered():
    assert use_step.choose(_steps(0.25), 2.0, "saved_lb", _lb, least=0.25)["offers"] is True
    assert use_step.choose(_steps(0.2), 2.0, "saved_lb", _lb)["offers"] is True                    # no floor given: none


def _lighten(tmp_path, saved, part_lb=None):
    from caliper import lighten
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(lighten.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 0, "removed": 0, "safety": 6.0, "holds": True, "saved_lb": 0},
          {"index": 1, "removed": 0.1, "safety": 5.9, "holds": True, "saved_lb": saved}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "min_safety": 2.0, "spacing_mm": 2.0, "thinnest_mm": 19.0, "across": 9.5, "stations": st,
                   **({"part_lb": part_lb} if part_lb is not None else {})}, f)
    return lighten.load_run(s, "r1")


@pytest.mark.parametrize("kind, steps", [
    ("no_room", [{"index": 1, "safety": 2.9, "saved_lb": 0.1, "seen": True}, {"index": 2, "safety": 2.4, "saved_lb": 1.0, "seen": True}]),
    ("room", [{"index": 1, "safety": 4.0, "saved_lb": 0.2, "seen": True}, {"index": 2, "safety": 2.5, "saved_lb": 1.0, "seen": True}]),
])
def test_the_floor_decides_the_button_only_and_a_deeper_step_over_it_is_still_named(kind, steps):
    """#252 review, Rule 6: the floor tested the step it picked, and the card said "too little" while a 1 lb step held in the
    study, four to ten times the floor."""
    got = use_step.choose(steps, 2.0, "saved_lb", _lb, as_drawn=4.2, least=0.25)
    assert got["kind"] == "small" and got["offers"] is False and got["index"] == 1 and got["deepest"] == 2, got
    assert got["said"].endswith("The study got as far as 1 lb lighter, and that step is there to choose."), got["said"]
    under = [steps[0], {**steps[1], "saved_lb": 0.24}]                      # deeper, but under the floor too: not named
    assert "there to choose" not in use_step.choose(under, 2.0, "saved_lb", _lb, least=0.25)["said"]


def test_the_panel_says_too_little_only_of_a_step_under_the_floor():
    """#252 re-check: keyed on offers === false, an unseen or unknown step read "Too little to use"."""
    from .test_carve_click import _page, _run

    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    lead = js[js.index("const lightenLead = (run) =>"):]
    lead = lead[:lead.index("\n")]
    out = _run(_page([], extra=lead + """
out = [lightenLead({ offer: { kind: 'small', offers: false } }), lightenLead({ offer: { kind: 'unseen', offers: false } }),
       lightenLead({ offer: { kind: 'unknown', offers: false } }), lightenLead({ offer: { kind: 'room', offers: true } }), lightenLead({})];
"""))
    assert out == ["Too little to use", "The step to use", "The step to use", "The step to use", "The step to use"], out


def test_the_panel_never_calls_a_step_under_the_floor_best():
    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "'Its best step'" not in js and "'Too little to use'" in js


def test_an_older_run_of_this_version_takes_the_part_s_weight_now(tmp_path):
    """#252 review: 0.25 lb is the most-offering floor, not the safe side. A run of the current version without part_lb takes the
    weight construction gives now; a quarter pound only where that can't be read."""
    from caliper import lighten
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    s = DesignStore.create("x", base=str(tmp_path))
    s.write_part("p", BOX_STOOL, intent="x")
    from caliper import construction

    weight = construction.report(s, "p")["mass_lb"]
    assert use_step.lighten_floor(weight) > 0.4 > use_step.LIGHTEN_MIN["lb"]   # 5% of it is over the 0.4 lb step
    d = os.path.join(lighten.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 0, "removed": 0, "safety": 6.0, "holds": True, "saved_lb": 0},
          {"index": 1, "removed": 0.1, "safety": 5.9, "holds": True, "saved_lb": 0.4}]
    rec = {"id": "r1", "part": "p", "version": s.design.part("p").version, "min_safety": 2.0, "spacing_mm": 2.0, "thinnest_mm": 19.0,
           "across": 9.5, "stations": st}
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump(rec, f)
    assert lighten.load_run(s, "r1")["offer"]["offers"] is False             # 0.4 lb under 5% of the box stool
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({**rec, "version": rec["version"] - 1}, f)                 # an older version's: its weight isn't now's
    assert lighten.load_run(s, "r1")["offer"]["offers"] is True


@pytest.mark.parametrize("saved, part_lb, offers", [
    (0.2, None, False),          # a few ounces, part unknown: the quarter pound
    (0.3, None, True),
    (0.4, 2.0, True),            # a 2 lb part: a quarter pound is the larger
    (0.4, 10.0, False),          # a 10 lb part: 5% is half a pound
    (0.5, 10.0, True),
])
def test_a_lightening_goes_by_the_larger_of_a_quarter_pound_and_5_percent(tmp_path, saved, part_lb, offers):
    assert _lighten(tmp_path, saved, part_lb)["offer"]["offers"] is offers


def test_the_card_gives_no_use_it_and_says_why(tmp_path):
    from caliper import lighten

    from .test_load_study import BOX_STOOL
    from .test_make_it_better import _check, _offers, _plate, _save, _store

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1, plate=_plate())
    _save(lighten.runs_dir(store), {"id": "20261107-000200-lighten", "part": "stool", "version": store.design.part("stool").version,
                                    "created": 3.0, "spacing_mm": 2.0, "thinnest_mm": 19.05, "across": 9.5, "part_lb": 12.0,
                                    "stations": [{"index": 0, "saved_lb": 0, "safety": 3.1, "holds": True},
                                                 {"index": 1, "saved_lb": 0.4, "safety": 3.05, "holds": True}]})
    (line,) = [ln for ln in _offers(store, "stool") if ln["action"] in ("lighten_use", "lighten", "")]
    assert line["action"] == "" and line["button"] == ""
    assert line["text"].startswith("The lightening's step isn't offered: it would make it 0.4 lb lighter"), line["text"]
    assert "too little to be worth the cuts and a re-check" in line["text"]


# the study records the part's weight, for the 5%: pinned on a real run in test_lighten.py::test_it_goes_down_until_the_safety_runs_out


def test_a_deeper_step_is_there_to_choose_only_where_the_re_check_can_see_it():
    """reviewer on #201: "that step is there to choose" was said of a deeper step the re-check can't see."""
    steps = [{"index": 1, "safety": 6.0, "saved_lb": 1.0, "seen": True}, {"index": 2, "safety": 5.0, "saved_lb": 3.0, "seen": False}]
    got = use_step.choose(steps, 2.0, "saved_lb", _lb)
    assert got["index"] == 1 and got["deepest"] is None and "there to choose" not in got["said"]
    assert got["said"].endswith("The study got as far as 3 lb lighter, but the re-check can't see that step's walls, so it couldn't be "
                                "settled."), got["said"]
    seen = [steps[0], {**steps[1], "seen": True, "safety": 2.9}]          # seen, short of half again: not the pick
    got = use_step.choose(seen, 2.0, "saved_lb", _lb)
    assert got["index"] == 1 and got["deepest"] == 2 and got["said"].endswith("The study got as far as 3 lb lighter, and that step is there to choose.")


def test_studies_says_why_there_s_nothing_to_use():
    """reviewer on #201: the Studies line for "nothing to use" survived its mutant."""
    from caliper import studies

    said = "It would save about 7¢ of material: too little to be worth a re-check, so it's left in the study."
    r = {"status": "done", "min_safety": 2.0, "best": None, "offer": {"offers": False, "said": said, "index": 1},
         "stations": [{"index": 0, "removed": 0, "safety": 8.0, "whole": 8.0, "holds": True, "whole_holds": True, "saved_g": 0},
                      {"index": 1, "removed": 0.1, "safety": 6.0, "whole": 6.0, "holds": True, "whole_holds": True, "saved_g": 3}]}
    assert studies._headline("carve", r) == (said, None)


def test_the_panel_doesn_t_call_a_step_with_no_button_the_step_to_use():
    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "${lightenLead(run)}: <b>${lbs(best.saved_lb)} lighter</b>" in js
