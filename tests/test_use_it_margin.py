"""CALI-134 (#167) — Use it offered the deepest step that passed the study's own check. How far the re-check lands below it follows the walls, not
the number: a lighter load scales the number and leaves the shape alone. So a step needs walls the re-check can see, and then a floor of 1.5 times."""
import os

import pytest

from caliper import use_step


def _further(st):
    return f"step {st['index']}"


def _steps(*rows):
    """(number, can the re-check see its walls)"""
    return [{"index": i + 1, "safety": n, "whole": n, "saved_g": 100 * (i + 1), "seen": s} for i, (n, s) in enumerate(rows)]


def _choose(rows, need=2.0):
    return use_step.choose(_steps(*rows), need, "saved_g", _further)


def test_the_deepest_step_with_seen_walls_and_room():
    got = _choose([(5.68, True), (3.52, True), (3.05, True), (2.0, True)])
    assert got["index"] == 3 and got["kind"] == "room" and got["quote"] == 3.05


def test_a_step_whose_walls_it_can_t_see_never_has_room():
    """The bridge at 15 lb: 3.06 at the deepest step, thin walls, and the re-check read 0.94."""
    got = _choose([(4.0, True), (3.06, False)])
    assert got["index"] == 1 and got["kind"] == "room"


def test_when_it_can_t_see_any_step_it_says_so_up_front():
    got = _choose([(4.0, False), (3.06, False)])
    assert got["kind"] == "unseen" and got["index"] == 1 and "may not settle" in got["said"] and "room" not in got["said"]


def test_a_seen_step_short_of_the_floor_beats_an_unseen_one_past_it():
    got = _choose([(2.4, True), (5.0, False)])
    assert got["index"] == 1 and got["kind"] == "no_room" and "may not hold" in got["said"]


def test_short_of_the_floor_it_offers_the_most_room_not_the_deepest():
    assert _choose([(2.8, True), (2.5, True)])["index"] == 1


def test_exactly_half_again_counts():
    assert _choose([(3.0, True)])["kind"] == "room"


def test_just_under_half_again_doesn_t():
    assert _choose([(2.99, True)])["kind"] == "no_room"


def test_it_goes_by_what_this_part_must_hold():
    assert _choose([(4.0, True)], need=3.0)["kind"] == "no_room"
    assert _choose([(4.5, True)], need=3.0)["kind"] == "room"


def test_a_study_from_before_this_says_what_s_missing():
    got = _choose([(4.0, None), (3.0, None)])
    assert got["kind"] == "unknown" and "didn't record" in got["said"] and got["index"] == 1


def test_the_floor_is_called_a_rule_of_thumb_and_nothing_promises_a_ratio():
    for kind in ("room", "no_room"):
        assert "rule of thumb" in use_step.SAID[kind]
    assert "third lower" not in " ".join(use_step.SAID.values())


def test_it_says_what_it_gives_up():
    got = _choose([(4.0, True), (2.2, True)])
    assert "The study got as far as step 2, and that step is there to choose." in got["said"] and got["deepest"] == 2


def test_it_doesn_t_promise_deeper_steps_that_aren_t_there():
    got = _choose([(2.0, True), (4.0, True)])
    assert got["index"] == 2 and got["deepest"] is None and "got as far" not in got["said"]


def test_it_chooses_by_the_weaker_number_and_quotes_it():
    steps = [{"index": 1, "safety": 5.0, "whole": 3.1, "saved_g": 900, "seen": True}]
    assert use_step.choose(steps, 2.0, "saved_g", _further)["quote"] == 3.1


def test_the_whole_part_can_take_the_room_away():
    steps = [{"index": 1, "safety": 5.0, "whole": 2.2, "saved_g": 900, "seen": True}]
    assert use_step.choose(steps, 2.0, "saved_g", _further)["kind"] == "no_room"


def test_a_step_with_no_whole_number_uses_its_own():
    assert use_step.own({"safety": 3.5}) == 3.5


def test_no_steps_no_offer():
    assert use_step.choose([], 2.0, "saved_g", _further) is None


# --- one answer everywhere -----------------------------------------------------------------------------------------------
def test_a_carve_record_carries_the_choice_and_best_follows_it(tmp_path):
    import json
    import os

    from caliper import carve
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(carve.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 1, "removed": 0.2, "safety": 4.0, "whole": 4.0, "holds": True, "whole_holds": True, "saved_g": 100, "seen": True},
          {"index": 2, "removed": 0.4, "safety": 2.1, "whole": 2.1, "holds": True, "whole_holds": True, "saved_g": 200, "seen": True}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "status": "done", "min_safety": 2.0, "best": 2, "share": "printed", "stations": st}, f)
    got = carve.load_run(s, "r1")
    assert got["best"] == 1 and got["offer"]["index"] == 1 and "40% carved away" in got["offer"]["said"]


def test_a_carve_goes_by_its_own_goal(tmp_path):
    import json
    import os

    from caliper import carve
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(carve.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 1, "removed": 0.2, "safety": 4.0, "whole": 4.0, "holds": True, "whole_holds": True, "saved_g": 100, "seen": True}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "status": "done", "min_safety": 3.0, "best": 1, "share": "printed", "stations": st}, f)
    assert carve.load_run(s, "r1")["offer"]["kind"] == "no_room"


def test_a_lightening_goes_by_its_own_goal(tmp_path):
    import json
    import os

    from caliper import lighten
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(lighten.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 1, "removed": 0.2, "safety": 4.0, "holds": True, "saved_lb": 1.0}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "min_safety": 3.0, "spacing_mm": 2.0, "thinnest_mm": 19.0, "across": 9.5, "stations": st}, f)
    assert lighten.load_run(s, "r1")["offer"]["kind"] == "no_room"


def test_the_page_opens_the_offered_step_and_says_why():
    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "The step to use: step <b>" in js and "The lightest step where the printed part holds" not in js
    assert "esc(run.offer.said)" in js and "showStation(p.id, run, run.offer.index)" in js


def test_the_chat_reply_names_the_same_step():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "chat.py")).read()
    assert "The step to use is step" in src and "The lightest that holds is step" not in src


@pytest.mark.parametrize("name", ["room", "no_room", "unseen", "unknown"])
def test_every_kind_has_words(name):
    assert use_step.SAID[name]


# --- what the study records --------------------------------------------------------------------------------------------
def test_a_thin_wall_isn_t_seen_at_the_voxels_a_check_would_use():
    import trimesh

    from caliper import load_study as L

    declared = {"construction": [{"kind": "printed", "material": "petg", "name": "x"}]}
    fat = trimesh.creation.box((40, 40, 40))
    assert L.would_see(declared, fat, [])["seen"] is True
    # a long box with a thin side: the check's voxels are limited by its size, and 1 mm against 1000 mm long is more than it may do
    sliver = trimesh.creation.box((1000, 1000, 1))
    got = L.would_see(declared, sliver, [])
    assert got["seen"] is False and got["thin_mm"] < 2.0
