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
    assert got["kind"] == "unseen" and got["offers"] is False and "couldn't settle" in got["said"] and "in the study" in got["said"] and "room" not in got["said"]


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
    assert got["kind"] == "unknown" and got["offers"] is False and "didn't record" in got["said"] and "run the study again" in got["said"]


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


# --- the last round -------------------------------------------------------------------------------------------------------
def _worth(usd):
    return lambda st: usd


def test_where_the_walls_can_t_be_seen_there_s_nothing_to_click():
    assert _choose([(23.4, False), (9.0, False)])["offers"] is False


def test_a_step_it_can_see_is_offered():
    assert _choose([(4.0, True)])["offers"] is True


def test_under_a_dollar_there_s_no_button_and_it_says_what_it_would_save():
    got = use_step.choose(_steps((5.68, True)), 2.0, "saved_g", _further, as_drawn=8.16, worth=_worth(0.22))
    assert got["kind"] == "small" and got["offers"] is False
    assert got["said"] == ("It would save about 22¢ of material, taking it from about 8.2 to 5.7 times over: too little to be worth a re-check, "
                           "so it's left in the study.")


def test_at_a_dollar_it_is_offered():
    assert use_step.choose(_steps((5.68, True)), 2.0, "saved_g", _further, worth=_worth(use_step.USE_MIN_USD))["offers"] is True


def test_the_dollar_is_a_named_number():
    assert use_step.USE_MIN_USD == 1.0


def test_where_it_can_t_be_priced_it_isn_t_judged_by_price():
    assert use_step.choose(_steps((5.68, True)), 2.0, "saved_g", _further, worth=_worth(None))["offers"] is True


def test_an_offer_says_the_strength_it_gives_up():
    got = use_step.choose(_steps((5.68, True)), 2.0, "saved_g", _further, as_drawn=8.16, worth=_worth(13.0))
    assert "That takes it from about 8.2 to 5.7 times over." in got["said"]


def test_nearly_free_is_said():
    got = use_step.choose(_steps((5.7, True)), 2.0, "saved_g", _further, as_drawn=5.75, worth=_worth(13.0))
    assert "It comes at almost no cost in strength." in got["said"]


def test_a_sliver_of_extra_isn_t_given_up():
    steps = [{"index": 1, "safety": 3.01, "saved_lb": 3.35, "seen": True}, {"index": 2, "safety": 2.98, "saved_lb": 3.37, "seen": True}]
    assert "got as far" not in use_step.choose(steps, 2.0, "saved_lb", _further)["said"]


def test_a_carve_prices_its_filament_and_keeps_nothing_to_click_off_best(tmp_path):
    import json

    from caliper import carve
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(carve.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 0, "removed": 0, "safety": 8.16, "whole": 8.16, "holds": True, "whole_holds": True, "saved_g": 0},
          {"index": 1, "removed": 0.12, "safety": 5.68, "whole": 5.68, "holds": True, "whole_holds": True, "saved_g": 10, "seen": True}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "status": "done", "min_safety": 2.0, "best": 1, "share": "printed", "material": "PETG (printed)", "stations": st}, f)
    got = carve.load_run(s, "r1")
    assert got["offer"]["offers"] is False and got["best"] is None and "22¢" in got["offer"]["said"]


def test_a_big_carve_is_offered(tmp_path):
    import json

    from caliper import carve
    from caliper.design import DesignStore

    s = DesignStore.create("x", base=str(tmp_path))
    d = os.path.join(carve.runs_dir(s), "r1")
    os.makedirs(d)
    st = [{"index": 0, "removed": 0, "safety": 8.0, "whole": 8.0, "holds": True, "whole_holds": True, "saved_g": 0},
          {"index": 1, "removed": 0.12, "safety": 5.0, "whole": 5.0, "holds": True, "whole_holds": True, "saved_g": 600, "seen": True}]
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r1", "part": "p", "status": "done", "min_safety": 2.0, "best": 1, "share": "printed", "material": "PETG (printed)", "stations": st}, f)
    got = carve.load_run(s, "r1")
    assert got["offer"]["offers"] is True and got["best"] == 1


def test_no_button_on_a_line_with_nothing_to_click():
    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "${ln.button ? `<button" in js


def test_the_card_quotes_the_number_it_chose_by(tmp_path, monkeypatch):
    from caliper import better

    src = open(better.__file__).read()
    assert "_times(offer['quote'], about=True)" in src and "_times(best['safety'], about=True)} by the carve" not in src

