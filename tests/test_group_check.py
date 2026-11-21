"""CALI-36 (#17) slice E1: a group's own "Will it work?", Theo's "check the box on the platform".

The load study we have, run over a group's parts as one solid (the foreman's OK on #17):
- **A group that mounts on another** is checked with it, held where that one is held: the box's cases go through the
  platform to what the platform stands on. A support of the box that lands on the platform is the union's to carry.
- **A group that mounts on nothing** is checked alone, held where its parts are held.
- **Its cases** are its own parts', one at a time, named by part. Loads, supports and pieces are posed from each part's
  own frame into the design's.
- **Each piece is its own material** (#348), over every part.
- **Its run** is kept on the group, with each part's version, and goes stale when any of them changes.
- **Not checked, in words:** a part not built, a steel frame (its frame study's), a group with nothing to hold.

Synthetic parts only: a stool (the platform) and a plywood tray (the box) sitting on its top."""

import numpy as np
import pytest

from caliper import load_study, verdicts
from caliper import plan as P
from caliper.design import DesignStore

from .test_posts import LEGGED

pytest.importorskip("cadquery")

TRAY = '''import cadquery as cq

PARAMS = {"w": 300.0, "d": 300.0}
BUILD = {"t": 19.05}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["w"], p["d"], BUILD["t"], centered=False)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "floor", "kind": "sheet", "material": "MATERIAL", "thickness": BUILD["t"],
             "outline": [(0, 0, 0), (p["w"], 0, 0), (p["w"], p["d"], 0), (0, p["d"], 0)]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    t = BUILD["t"]
    return [{"name": "two bags", "lb": 100, "factor": 2.0, "lo": (100, 100, t - 2), "hi": (200, 200, t)}]
'''

FRAME = '''import cadquery as cq


def build(params):
    return cq.Workplane().box(40, 40, 40, centered=False)


def members(params):
    return [{"name": "post", "size": "2x2 tube", "a": (20, 20, 0), "b": (20, 20, 40)}]
'''

PLAN = {
    "parts": [{"id": "stool", "what": "the stool", "made": "lumber"},
              {"id": "tray", "what": "a tray", "made": "sheet", "mounts_on": ["stool"]}],
    "groups": [{"id": "platform", "what": "the platform", "parts": ["stool"]},
               {"id": "box", "what": "the box", "parts": ["tray"], "mounts_on": ["platform"]}],
}

ON_TOP = [50.0, 50.0, 450.0]                       # the tray on the stool's top (450 tall)


def _store(tmp_path, tray="plywood", at=None, turn=None, build=("stool", "tray"), loads=True, shift=None):
    s = DesignStore.create("a platform and a box on it", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN))
    src = TRAY.replace("MATERIAL", tray)
    if not loads:
        src = src[:src.index("def loads(")]
    for pid, script in (("stool", LEGGED), ("tray", src)):
        if pid in build:
            s.write_part(pid, script, intent=pid)
    for p in s.assembly.parts:
        off = np.asarray(shift or [0, 0, 0], float)
        if p.id == "tray":
            p.position = [float(v) for v in np.asarray(at or ON_TOP, float) + off]
            p.rotation = [float(v) for v in (turn or [0, 0, 0])]
        elif p.id == "stool":
            p.position = [float(v) for v in off]
    s.save()
    return DesignStore.load(s.root)


def _gs():
    from caliper import group_study

    return group_study


# --- what's checked ----------------------------------------------------------------------------------------------------

def test_the_box_on_the_platform_is_held_where_the_platform_is_held(tmp_path):
    ctx = _gs().prepare_group(_store(tmp_path), "box")
    assert [ld["name"] for ld in ctx["loads"]] == ["tray: two bags"]             # the box's own cases
    (ld,) = ctx["loads"]
    assert ld["lo"] == pytest.approx([150, 150, 467.05]) and ld["hi"] == pytest.approx([250, 250, 469.05])
    assert [h["name"] for h in ctx["held"]] == ["stool: the floor"]              # the tray's floor is the stool's top
    assert ctx["held"][0]["hi"][2] < 50
    assert {pc["part"] for pc in ctx["pieces"]} == {"stool", "tray"}
    assert "the tray's floor" in [f"the {pc['name']}" for pc in ctx["pieces"]]
    (floor,) = [pc for pc in ctx["pieces"] if pc["part"] == "tray"]
    assert np.asarray(floor["polys"][0])[:, 2] == pytest.approx([450.0] * 4)      # posed with its part


def test_a_group_that_mounts_on_nothing_is_checked_alone(tmp_path):
    ctx = _gs().prepare_group(_store(tmp_path), "platform")
    assert [ld["name"] for ld in ctx["loads"]] == ["stool: sitting toward the front right corner", "stool: its rating"]
    assert {pc["part"] for pc in ctx["pieces"]} == {"stool"}
    assert [h["name"] for h in ctx["held"]] == ["stool: the floor"]


def test_a_moved_group_reads_as_where_it_sits(tmp_path):
    here = _gs().prepare_group(_store(tmp_path / "a"), "box")
    there = _gs().prepare_group(_store(tmp_path / "b", shift=[1000.0, 0, 0]), "box")
    assert there["loads"][0]["lo"] == pytest.approx(np.add(here["loads"][0]["lo"], [1000, 0, 0]))
    assert there["held"][0]["lo"] == pytest.approx(np.add(here["held"][0]["lo"], [1000, 0, 0]))
    assert there["spacing"] == here["spacing"] and int(there["ls"].solid.sum()) == int(here["ls"].solid.sum())
    assert there["joints"]["joints"][0]["mid"] == pytest.approx(np.add(here["joints"]["joints"][0]["mid"], [1000, 0, 0]))


def test_a_quarter_turned_part_s_load_turns_with_it(tmp_path):
    ctx = _gs().prepare_group(_store(tmp_path, at=[350.0, 50.0, 450.0], turn=[0, 0, 90]), "box")
    (ld,) = ctx["loads"]                       # (100..200, 100..200) turned a quarter about z, then moved
    assert ld["lo"] == pytest.approx([150, 150, 467.05]) and ld["hi"] == pytest.approx([250, 250, 469.05])
    assert ld["force"] == pytest.approx([0, 0, -100 * load_study.LB])
    assert not ld.get("turned")


def test_a_load_turns_with_its_part_onto_its_side():
    """A part turned a quarter about x: its load's box and its force turn with it (down becomes along y)."""
    from caliper.measure import pose_matrix

    ld = {"name": "two bags", "force": [0.0, 0.0, -400.0], "factor": 2.0, "lo": [100, 100, 17], "hi": [200, 200, 19],
          "lb": 89.9}
    got = _gs().pose_load(ld, pose_matrix([0, 0, 0], [90, 0, 0]), "tray")
    assert got["force"] == pytest.approx([0, 400.0, 0], abs=1e-9) and got["name"] == "tray: two bags"
    assert got["lo"] == pytest.approx([100, -19, 100]) and got["hi"] == pytest.approx([200, -17, 200])
    assert not got.get("turned")


def test_parts_that_overlap_are_solid_where_they_overlap(tmp_path):
    """Each part voxelized on its own: the tray sunk 5 mm into the stool's top is solid there, never cancelled out."""
    ctx = _gs().prepare_group(_store(tmp_path, at=[50.0, 50.0, 445.0]), "box")
    grid = ctx["ls"].grid
    i = tuple(np.rint((np.asarray([200, 200, 447.5]) - np.asarray(grid.origin)) / grid.spacing).astype(int))
    assert ctx["ls"].solid[i]


def test_a_fixed_part_is_the_surroundings_never_in_the_solid(tmp_path):
    """The truck bed (#397): not checked with the group, and a support landing on it stays one."""
    store = _store(tmp_path)
    for p in store.assembly.parts:
        if p.id == "stool":
            p.role = "fixed"
    store.save()
    ctx = _gs().prepare_group(DesignStore.load(store.root), "box")
    assert {pc["part"] for pc in ctx["pieces"]} == {"tray"} and [h["name"] for h in ctx["held"]] == ["tray: the floor"]


def test_each_piece_is_its_own_material_over_every_part(tmp_path):
    ctx = _gs().prepare_group(_store(tmp_path, tray="xps"), "box")
    assert ctx["note"].startswith("Each piece in its own material")
    s, grid = ctx["strength_map"], ctx["ls"].grid
    origin, h = np.asarray(grid.origin), grid.spacing

    def at(p):
        return s[tuple(np.rint((np.asarray(p) - origin) / h).astype(int))]
    xps = load_study.material([{"material": "xps", "volume": 1.0}])["strength"]
    ply = load_study.material([{"material": "plywood", "volume": 1.0}])["strength"]
    assert at([200, 200, 460]) == pytest.approx(xps)                  # the tray, up on the stool
    assert at([200, 200, 440]) == pytest.approx(ply)                  # the stool's top under it


# --- not checked, in words --------------------------------------------------------------------------------------------

def test_a_part_not_built_yet_is_waited_for(tmp_path):
    with pytest.raises(ValueError, match="waits for tray to be built"):
        _gs().prepare_group(_store(tmp_path, build=("stool",)), "box")


def test_a_group_with_nothing_to_hold_says_so(tmp_path):
    with pytest.raises(ValueError, match="the box doesn't say what it must hold: none of its parts has loads"):
        _gs().prepare_group(_store(tmp_path, loads=False), "box")


def test_a_name_that_isn_t_a_group_says_so(tmp_path):
    with pytest.raises(ValueError, match="there's no group 'lid'"):
        _gs().prepare_group(_store(tmp_path), "lid")


def test_a_steel_frame_in_it_is_its_frame_study_s(tmp_path):
    store = _store(tmp_path)
    store.write_part("stool", FRAME, intent="a frame")
    with pytest.raises(ValueError, match="the stool is a frame of members: its frame study checks it"):
        _gs().prepare_group(store, "box")


# --- the run --------------------------------------------------------------------------------------------------------

def test_a_one_part_group_reads_as_its_part_s_own_check(tmp_path):
    store = _store(tmp_path)
    own = load_study.study(store, "stool")
    group = _gs().study_group(store, "platform")
    assert [c["name"] for c in group["cases"]] == [f"stool: {c['name']}" for c in own["cases"]]
    assert [c["safety"] for c in group["cases"]] == [c["safety"] for c in own["cases"]]
    assert group["spacing_mm"] == own["spacing_mm"] and group["voxels"] == own["voxels"]


def test_the_box_on_the_platform_s_run_is_kept_on_the_group_and_goes_stale_with_a_part(tmp_path):
    store = _store(tmp_path)
    rec = _gs().study_group(store, "box")
    assert rec["group"] == "box" and rec["kind"] == "load" and "part" not in rec
    assert rec["members"] == {"tray": 1, "stool": 1}
    assert [c["name"] for c in rec["cases"]] == ["tray: two bags"]
    (case,) = rec["cases"]                     # the platform's own joints judge the box's load too, as its own check's do
    from caliper import joint_check as JC

    assert case["joints"]["n"] == len(JC.setup(store, "stool")["joints"])
    assert all("the stool's " in u for u in case["joints"]["unchecked"][1:])
    v = verdicts.run(rec)
    assert v["kind"] != "holds" or "joints not checked" in v["why"], v           # never a bare tick
    assert any(n == _gs().OWN_WEIGHT for n in rec["notes"])               # the foreman: said until Theo answers
    (kept,) = _gs().list_runs(store, "box")
    assert kept["id"] == rec["id"] and _gs().stale(store, kept) is None
    assert load_study.list_runs(store) == []                              # a part's own runs never hold it
    store.write_part("stool", LEGGED.replace('"h": 450.0', '"h": 460.0'), intent="taller")
    assert _gs().stale(store, kept) == "the stool has changed since it was checked"
