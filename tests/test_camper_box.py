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

PARAMS = {"l": 2000.0, "w": 1500.0, "h": 1200.0}
BUILD = {"core": "xps", "core_t": 50.8, "floor_t": 19.05}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane("XY").box(p["l"], p["w"], p["h"], centered=False)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    L, W, H = p["l"], p["w"], p["h"]
    skins = ["fiberglass", {"material": "fiberglass", "face": "in"}]

    def wall(name, outline):
        return {"name": name, "kind": "sheet", "material": b["core"], "thickness": b["core_t"], "outline": outline,
                "covers": skins}
    return [{"name": "floor", "kind": "sheet", "material": "plywood", "thickness": b["floor_t"],
             "outline": [(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)], "covers": ["paint"]},
            wall("wall_left", [(0, W, 0), (L, W, 0), (L, W, H), (0, W, H)]),
            wall("wall_right", [(0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H)]),
            wall("wall_front", [(L, 0, 0), (L, W, 0), (L, W, H), (L, 0, H)]),
            wall("wall_back", [(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)]),
            wall("roof", [(0, 0, H), (L, 0, H), (L, W, H), (0, W, H)])] + EXTRA


def shell(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    L, W, H = p["l"], p["w"], p["h"]

    def beam(name, a, bb, core_t=b["core_t"], skins=("fiberglass", "fiberglass")):
        return {"name": name, "a": a, "b": bb, "depth": H, "core": b["core"], "core_t": core_t, "skins": list(skins)}
    return [beam("wall_left", (0, BEAM_Y, 0), (L, BEAM_Y, 0), BEAM_CORE_T, BEAM_SKINS),
            beam("wall_right", (0, 0, 0), (L, 0, 0)), beam("wall_front", (L, 0, 0), (L, W, 0)),
            beam("wall_back", (0, 0, 0), (0, W, 0))]


def keeps(params, build=None):
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
