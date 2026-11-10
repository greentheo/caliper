"""CALI-134 (#167) — Use it offered the deepest step that passed the study's own check, and that step has no room: the re-check at the rebuilt
part's own resolution reads lower, and usually left a part that didn't hold (thick tube 2.0 to 0.97, bridge 2.6 to 1.95)."""
import pytest

from caliper import better


def _steps(*numbers):
    return [{"index": i + 1, "safety": n, "whole": n, "saved_g": 100 * (i + 1)} for i, n in enumerate(numbers)]


def test_it_offers_the_deepest_step_with_room_to_spare():
    best, said = better._to_offer(_steps(5.68, 3.52, 3.05, 2.0), 2.0, "saved_g")
    assert best["index"] == 3 and said == better._ROOM


def test_the_deepest_step_at_the_goal_isn_t_the_one():
    best, _ = better._to_offer(_steps(5.0, 2.0), 2.0, "saved_g")
    assert best["safety"] == 5.0


def test_exactly_half_again_counts():
    assert better._to_offer(_steps(3.0, 2.9), 2.0, "saved_g")[0]["safety"] == 3.0


def test_with_no_room_it_offers_the_most_and_says_it_may_not_hold():
    best, said = better._to_offer(_steps(2.8, 2.53), 2.0, "saved_g")
    assert best["safety"] == 2.8 and said == better._NO_ROOM and "may not hold" in said


def test_the_whole_part_s_number_counts():
    steps = [{"index": 1, "safety": 5.0, "whole": 2.2, "saved_g": 900}, {"index": 2, "safety": 3.5, "whole": 3.5, "saved_g": 100}]
    assert better._to_offer(steps, 2.0, "saved_g")[0]["index"] == 2


def test_a_step_with_no_whole_number_uses_its_own():
    steps = [{"index": 1, "safety": 3.5, "saved_lb": 1.0}]
    assert better._to_offer(steps, 2.0, "saved_lb")[0]["index"] == 1


def test_no_steps_no_offer():
    assert better._to_offer([], 2.0, "saved_g")[0] is None


def test_it_goes_by_what_this_part_must_hold():
    assert better._to_offer(_steps(4.0, 3.2), 3.0, "saved_g")[1] == better._NO_ROOM
    assert better._to_offer(_steps(4.6, 3.2), 3.0, "saved_g")[0]["safety"] == 4.6


#: the five parts measured for #167: each step's own number, then what its re-check read. Saved grows with depth, as in the runs.
MEASURED = {"thick tube": [(5.68, 3.99), (3.52, 2.85), (3.05, 2.72), (2.0, 0.97)], "ring": [(2.8, 2.33), (2.53, 2.14)],
            "tall ring": [(3.86, 2.6), (2.87, 2.1), (2.27, 2.01)], "bridge": [(3.26, 2.18), (3.06, 2.23), (2.6, 1.95)],
            "step stool": [(3.09, 2.29), (3.07, 2.41), (3.01, 2.4), (2.98, 2.39)]}


@pytest.mark.parametrize("part", MEASURED)
def test_on_each_measured_part_the_offered_step_re_checks_at_the_goal(part):
    rows = MEASURED[part]
    best, said = better._to_offer(_steps(*[q for q, _ in rows]), 2.0, "saved_g")
    assert rows[best["index"] - 1][1] >= 2.0, f"{part}: {said}"


def test_the_old_choice_left_two_of_the_five_short():
    short = [p for p, rows in MEASURED.items() if rows[-1][1] < 2.0]
    assert short == ["thick tube", "bridge"]


def test_the_margin_covers_the_worst_ratio_measured_with_any_room():
    worst = min(r / q for rows in MEASURED.values() for q, r in rows if q > 2.0)
    assert better.USE_MARGIN * worst >= 1.0
