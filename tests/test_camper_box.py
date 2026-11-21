"""CALI-54 (#1) slice C — a camper box's walls, roof and clear space, written from the chat and held to the shape.

Theo's next build is a truck camper: a platform, and a foam-core box on top. Its designer writes the box's sandwich
walls as ``construction()`` sheets with skins (``covers``, as #351 will read them), the walls as deep beams for the
frame study (``shell()``), and the space it keeps clear (``keeps()``). Each round now holds those to the shape: a wall
beam lies in a wall of its core, thickness and skins (``shell_in_walls``), and the surface cuts into nothing it keeps
clear (``keeps_clear``). A mismatch fails the round, as the construction checks do. Stub designer only: no live call."""

import os
import shutil

import pytest

from caliper import chat, consistency, construction as C, materials as M
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: A foam-core box, 2000 x 1500 x 1200 mm, its walls' and roof's outlines on the outside faces. The knobs at the top
#: are what a test turns wrong.
BOX = '''import cadquery as cq

BEAM_Y = 1500.0          # where the left wall's beam runs
BEAM_CORE_T = 50.8
BEAM_SKINS = ["fiberglass", "fiberglass"]
KEEP_HI_Y = 1400.0
EXTRA = []
BEAM_DEPTH = None        # None: the wall's height
LEFT_H = None            # None: the wall's full height
WALL_SKINS = ["fiberglass", {"material": "fiberglass", "face": "in"}]
BEAM_CORE = "xps"
BEAM_X1 = None           # None: the wall's length
BAD_KEEPS = False
TOP_PLY = False          # a bare plywood panel on wall_left's top, up to the roof
SPLIT_CORE = None        # wall_left in two panels, the second of this core

PARAMS = {"l": 2000.0, "w": 1500.0, "h": 1200.0}
BUILD = {"core": "xps", "core_t": 50.8, "floor_t": 19.05}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane("XY").box(p["l"], p["w"], p["h"], centered=False)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    L, W, H = p["l"], p["w"], p["h"]
    skins = WALL_SKINS
    LH = LEFT_H or H

    def wall(name, outline):
        return {"name": name, "kind": "sheet", "material": b["core"], "thickness": b["core_t"], "outline": outline,
                "covers": skins}
    return [{"name": "floor", "kind": "sheet", "material": "plywood", "thickness": b["floor_t"],
             "outline": [(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)], "covers": ["paint"]},
            *([wall("wall_left", [(0, W, 0), (L / 2, W, 0), (L / 2, W, LH), (0, W, LH)]),
               {**wall("wall_left_2", [(L / 2, W, 0), (L, W, 0), (L, W, LH), (L / 2, W, LH)]), "material": SPLIT_CORE}]
              if SPLIT_CORE else [wall("wall_left", [(0, W, 0), (L, W, 0), (L, W, LH), (0, W, LH)])]),
            *([{"name": "ply_top", "kind": "sheet", "material": "plywood", "thickness": 6.35,
                "outline": [(0, W, LH), (L, W, LH), (L, W, H), (0, W, H)]}] if TOP_PLY else []),
            wall("wall_right", [(0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H)]),
            wall("wall_front", [(L, 0, 0), (L, W, 0), (L, W, H), (L, 0, H)]),
            wall("wall_back", [(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)]),
            wall("roof", [(0, 0, H), (L, 0, H), (L, W, H), (0, W, H)])] + EXTRA


def shell(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    L, W, H = p["l"], p["w"], p["h"]

    def beam(name, a, bb, core_t=b["core_t"], skins=("fiberglass", "fiberglass")):
        return {"name": name, "a": a, "b": bb, "depth": BEAM_DEPTH if BEAM_DEPTH is not None else H, "core": BEAM_CORE,
                "core_t": core_t, "skins": list(skins)}
    return [beam("wall_left", (0, BEAM_Y, 0), (BEAM_X1 or L, BEAM_Y, 0), BEAM_CORE_T, BEAM_SKINS),
            beam("wall_right", (0, 0, 0), (L, 0, 0)), beam("wall_front", (L, 0, 0), (L, W, 0)),
            beam("wall_back", (0, 0, 0), (0, W, 0))]


def keeps(params, build=None):
    if BAD_KEEPS:
        return [{"name": "mattress"}]
    return [{"name": "mattress", "note": "a full, on the floor", "lo": (100, 100, 19.05), "hi": (1900, KEEP_HI_Y, 250)}]
'''


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def make(**knobs):
        script = BOX
        for k, v in knobs.items():
            script = script.replace(next(ln for ln in script.splitlines() if ln.startswith(f"{k} =")),
                                    f"{k} = {v!r}")
        s = DesignStore.create("a camper box", base=str(tmp_path / f"d{len(os.listdir(tmp_path))}"))
        s.write_part("box", script, intent="a foam-core camper box")
        got = {r.id: r for r in consistency.check(C.declared(s, "box"), s.part_geometry("box"))}
        return got
    return make


def test_a_true_box_passes_its_walls_and_its_clear_space(box):
    got = box()
    assert got["shell_in_walls"].status == "pass" and got["keeps_clear"].status == "pass", got
    assert all(got[k].status == "pass" for k in ("construction_inside", "construction_on_its_face"))


@pytest.mark.parametrize("knobs,said", [
    ({"BEAM_Y": 1300.0}, "wall_left lies in no wall the part is built from"),
    ({"BEAM_CORE_T": 25.4}, "wall_left says 25.4 mm xps, but its wall wall_left is 50.8 mm xps"),
    ({"BEAM_SKINS": ["fiberglass"]}, "wall_left's skins (fiberglass) aren't its wall wall_left's (fiberglass, fiberglass)"),
    ({"BEAM_SKINS": ["fiberglass", "fiberglass", "glass_patch"]}, "aren't its wall wall_left's"),
])
def test_a_wall_beam_off_its_wall_or_not_of_it_fails(box, knobs, said):
    r = box(**knobs)["shell_in_walls"]
    assert r.status == "fail" and said in r.detail, r.detail


def test_a_corner_patch_the_construction_declares_is_fine(box):
    patch = [{"name": "corner patch", "kind": "covering", "material": "glass_patch",
              "outline": [(0, 1500, 0), (300, 1500, 0), (300, 1500, 300), (0, 1500, 300)]}]
    assert box(BEAM_SKINS=["fiberglass", "fiberglass", "glass_patch"], EXTRA=patch)["shell_in_walls"].status == "pass"


def test_a_mattress_through_a_wall_fails_with_where_and_how_much(box):
    r = box(KEEP_HI_Y=1600.0)["keeps_clear"]
    assert r.status == "fail" and r.detail == "the outside cuts 100 mm into the mattress", r.detail


def test_a_designer_s_beam_off_its_wall_fails_the_round_and_is_fixed(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a camper box", base=str(tmp_path / "designs"))
    off = BOX.replace("BEAM_Y = 1500.0", "BEAM_Y = 1300.0")
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return off if len(seen) == 1 else BOX
    res = chat.author_part(s, "box", "a foam-core camper box", author=author, use_llm=False, promote_feedback=False,
                           max_rounds=3)
    assert len(seen) == 2 and "shell_in_walls" in (seen[1] or ""), seen
    assert res.version and "BEAM_Y = 1500.0" in s.read_script("box")


def test_the_trailer_s_cargo_box_still_passes(tmp_path):
    src = os.path.join(os.path.dirname(C.__file__), "samples", "camper")
    shutil.copytree(src, tmp_path / "camper")
    s = DesignStore.load(str(tmp_path / "camper"))
    got = {r.id: r for r in consistency.check(C.declared(s, "cargo_box"), s.part_geometry("cargo_box"))}
    assert got["shell_in_walls"].status == "pass" and got["keeps_clear"].status == "pass"


def test_a_skin_is_said_by_name_or_with_its_thickness_and_face():
    item = {"covers": ["fiberglass", {"material": "fiberglass_2", "t": 0.75, "face": "in"}, "paint"]}
    assert M.skins_of(item) == [{"material": "fiberglass", "t": 0.25, "face": "out"},
                                {"material": "fiberglass_2", "t": 0.75, "face": "in"}]      # paint: weight only
    assert M.skins_of({"covers": ["paint", "fiberglass"]}) == [{"material": "fiberglass", "t": 0.25, "face": "in"}]
    assert [M.cover_name(c) for c in item["covers"]] == ["fiberglass", "fiberglass_2", "paint"]
    sheet = {"name": "wall", "kind": "sheet", "material": "xps", "thickness": 50.8,
             "outline": [(0, 0, 0), (1000, 0, 0), (1000, 0, 1000), (0, 0, 1000)]}
    plain = C.piece({**sheet, "covers": ["fiberglass_2"]})
    thick = C.piece({**sheet, "covers": [{"material": "fiberglass_2", "t": 1.0}]})
    cov = lambda rows: next(r for r in rows if r["kind"] == "covering")    # noqa: E731
    assert cov(thick)["mass_kg"] == pytest.approx(cov(plain)["mass_kg"] * 2)    # twice the table's 0.5 mm
    assert cov(thick)["material"] == "fiberglass_2"



# --- #404 review (caliper-reviewer) ------------------------------------------------------------------------------------
@pytest.mark.parametrize("knobs,said", [
    ({"BEAM_DEPTH": 2400.0}, "wall_left is 2400 mm deep, but its wall stops 1200 mm up"),        # 8x as stiff, passed
    ({"LEFT_H": 300.0}, "wall_left is 1200 mm deep, but its wall stops 300 mm up"),
    ({"WALL_SKINS": [{"material": "fiberglass", "t": 0.05}, {"material": "fiberglass", "t": 0.05, "face": "in"}]},
     "wall_left's fiberglass skin is 0.05 mm, but the frame study reads fiberglass as 0.25 mm: name the skin the wall has"),
    ({"WALL_SKINS": ["paint", "fiberglass", "fiberglass"]}, "has a skin past its second with no face"),
    ({"BEAM_CORE": "eps"}, "wall_left says 50.8 mm eps, but its wall wall_left is 50.8 mm xps"),
    ({"BEAM_X1": 3000.0}, "wall_left lies in no wall the part is built from"),               # 1.5x its wall's length
    ({"BEAM_DEPTH": 0.0}, "wall_left has no depth"),
])
def test_a_beam_the_frame_study_would_overrate_fails(box, knobs, said):
    r = box(**knobs)["shell_in_walls"]
    assert r.status == "fail" and said in r.detail, r.detail


def test_keeps_that_aren_t_boxes_fail(box):
    r = box(BAD_KEEPS=True)["keeps_clear"]
    assert r.status == "fail" and r.detail.startswith("keeps() isn't a list of boxes"), r.detail



# --- #404 re-check (caliper-reviewer) ----------------------------------------------------------------------------------
def test_a_panel_of_another_build_above_the_wall_isn_t_its_wall(box):
    """300 mm of foam sandwich with thin bare plywood above it, up to 1200 mm, read as a 1200 mm sandwich beam."""
    r = box(LEFT_H=300.0, TOP_PLY=True)["shell_in_walls"]
    assert r.status == "fail" and "wall_left is 1200 mm deep, but its wall stops 300 mm up" in r.detail, r.detail


@pytest.mark.parametrize("depth,ok", [(1220.0, True), (1230.0, False)])       # 2% of 1200 is 24 mm
def test_a_beam_s_depth_may_run_two_percent_past_its_wall(box, depth, ok):
    assert (box(BEAM_DEPTH=depth)["shell_in_walls"].status == "pass") is ok


def test_a_skin_thicker_than_the_table_s_is_refused_too(box):
    thick = [{"material": "fiberglass", "t": 0.5}, {"material": "fiberglass", "t": 0.5, "face": "in"}]
    r = box(WALL_SKINS=thick)["shell_in_walls"]
    assert r.status == "fail" and "skin is 0.5 mm, but the frame study reads fiberglass as 0.25 mm" in r.detail, r.detail


@pytest.mark.parametrize("core_t,ok", [(51.2, True), (51.4, False)])          # CORE_TOL_MM 0.5 against 50.8
def test_a_beam_s_core_thickness_within_half_a_millimetre(box, core_t, ok):
    assert (box(BEAM_CORE_T=core_t)["shell_in_walls"].status == "pass") is ok


def test_every_panel_a_beam_lies_in_is_checked_not_only_the_first(box):
    r = box(SPLIT_CORE="eps")["shell_in_walls"]
    assert r.status == "fail" and "its wall wall_left_2 is 50.8 mm eps" in r.detail, r.detail
