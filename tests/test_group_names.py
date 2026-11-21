"""CALI-242 (#17), #399's follow-up: no part, copied or added, takes a group's name; and slice E's contract branches pinned.

#374's Copy… picks the next free name, ``wall_2``, and a mesh part is written by ``write_mesh_part``. Neither knew the plan's
groups, so a copy could land on a group named ``wall_2`` (its rules then errored, unmeasured, or a scripted copy was
refused outright). And three branches of #399's contract had no test: ``store.group_geometry`` over a name that's a part
and a group, over a part that didn't build, and the first run's own id. No live call."""

import pytest

from caliper import firstrun, placing
from caliper import plan as P
from caliper.design import DesignStore

from .test_group_rules import DECK, FLOOR, LEGS, PLAN, WALL, _box, _camper

pytest.importorskip("cadquery")


def test_a_copy_skips_a_group_s_name(tmp_path):
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    plan = {**PLAN, "groups": PLAN["groups"] + [{"id": "wall_2", "what": "the other wall", "parts": ["legs"]}]}
    plan["groups"][0] = {**plan["groups"][0], "parts": ["deck"]}          # legs move to wall_2
    P.save(s, P.validate(plan))
    s.write_part("wall", WALL, intent="a wall")
    assert placing.free_id(s, "wall") == "wall_3"


def test_a_mesh_part_never_takes_a_group_s_name(tmp_path):
    s = _camper(tmp_path)
    stl = s.version_stl("wall", 1)
    with pytest.raises(ValueError, match="'platform' is a group of this design's plan"):
        s.write_mesh_part("platform", stl)


def test_the_group_geometry_of_a_name_that_s_a_part_and_a_group_says_so(tmp_path):
    s = DesignStore.create("a camper", base=str(tmp_path / "designs"))
    s.write_part("platform", _box(100, 100, 20, 2000), intent="a shelf")            # a part, before any plan
    P.save(s, P.validate(PLAN))
    assert s.group_geometry("platform") == (None, "platform names both a part and a group: rename the part")


def test_the_group_geometry_with_a_part_that_didn_t_build_says_which(tmp_path):
    s = DesignStore.create("a camper", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN))
    for pid, src in (("legs", LEGS), ("deck", DECK), ("floor", FLOOR)):
        s.write_part(pid, src, intent=pid)
    s.write_part("wall", "def build(params):\n    raise ValueError('no wall today')\n", intent="a wall")
    got, why = s.group_geometry("box")
    assert got is None and why.startswith("box isn't measured: wall didn't build"), why


def test_the_first_run_s_part_never_takes_a_group_s_name(tmp_path):
    s = DesignStore.create("a platform", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN))
    pid, _ = firstrun.first_part(s)
    assert pid != "platform" and pid.startswith("platform"), pid
