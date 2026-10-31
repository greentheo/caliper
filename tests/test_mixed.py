"""CALI-82 — a plywood top on printed sides: one part, two materials."""

import numpy as np
import pytest

from caliper import construction as C
from caliper import making
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: Two printed sides (each 20 mm thick, open between), a 1/2 in plywood top across them.
MIXED = '''import cadquery as cq

PARAMS = {"w": 300.0, "d": 220.0, "h": 220.0, "side": 20.0}
BUILD = {"top": 12.7, "material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, s = BUILD["top"], p["side"]
    side = lambda x0: cq.Workplane().box(s, p["d"], p["h"] - t, centered=False).translate((x0, 0, 0))
    top = cq.Workplane().box(p["w"], p["d"], t, centered=False).translate((0, 0, p["h"] - t))
    return side(0).union(side(p["w"] - s)).union(top)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    w, d, h = p["w"], p["d"], p["h"]
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": b["top"],
             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]},
            {"name": "sides", "kind": "printed", "material": b["material"], "infill": b["infill"], "rest": True}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    cx, cy, h = p["w"] / 2, p["d"] / 2, p["h"]
    return [{"name": "an adult stepping up", "lb": 200, "factor": 2.0,
             "lo": (cx - 50, cy - 50, h - 2), "hi": (cx + 50, cy + 50, h)}]
'''


@pytest.fixture
def stool(tmp_path):
    s = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    s.write_part("stool", MIXED, intent="a plywood top on printed sides")
    return s


def test_the_printed_piece_is_the_solid_less_the_plywood(stool):
    whole = stool.part_geometry("stool").require_mesh()
    sides = C.printed_solid(stool, "stool")
    top = 300 * 220 * 12.7
    assert abs(whole.volume) == pytest.approx(top + 2 * 20 * 220 * (220 - 12.7), rel=0.01)
    assert abs(sides.volume) == pytest.approx(2 * 20 * 220 * (220 - 12.7), rel=0.02)
    assert sides.body_count == 2                               # two sides, apart
    rows = {r["name"]: r for r in C.takeoff(C.with_printed(stool, "stool", C._items(C.declared(stool, "stool"))))}
    assert rows["top"]["kind"] == "sheet" and rows["sides"]["kind"] == "printed"
    assert rows["sides"]["volume_mm3"] == pytest.approx(abs(sides.volume), rel=1e-6)
    bom = C.report(stool, "stool")["bom"]
    assert bom["sheets"] and bom["printed"]                     # plywood and filament on one list


def test_the_printer_gets_only_the_sides(stool, tmp_path):
    shop = {"hand": ["jigsaw", "drill"], "machines": [{"id": "mk4", "kind": "printer", "volume_mm": [256, 256, 256]}]}
    mk = making.plan(stool, "stool", shop, out_dir=str(tmp_path / "print"))
    (pr,) = mk["printed"]
    assert pr["name"] == "sides" and mk["ok"]
    import trimesh

    printed = sum(abs(trimesh.load(str(tmp_path / "print" / f["file"])).volume) for f in pr["files"])
    assert printed == pytest.approx(2 * 20 * 220 * (220 - 12.7), rel=0.03)
    assert "jigsaw" in mk["by_how"] and "top" in mk["by_how"]["jigsaw"]


def test_its_declarations_check_against_the_solid(stool):
    from caliper import consistency, sandbox

    run = sandbox.run_script(stool.read_script("stool"), timeout=120)
    got = {r.id: r for r in consistency.check(run.declared, run.geometry)}
    assert got["construction_inside"].passed and got["loads_land"].passed
    assert "construction_covers" not in got and "construction_volume" not in got


@pytest.mark.parametrize("per_voxel", [True, False])
def test_two_materials_each_judged_against_its_own_strength(stool, monkeypatch, per_voxel):
    pytest.importorskip("whittle")
    from caliper import load_study

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    if not per_voxel:                                        # an older whittle: one stiffness, and it says so
        monkeypatch.setattr(load_study, "per_voxel", lambda ls: False)
    ctx = load_study.prepare(stool, "stool")
    if per_voxel and not load_study.per_voxel(ctx["ls"]):
        pytest.skip("this whittle has no stiffness per voxel")
    assert ctx["mat"]["printed"] and ctx["plate_mat"]["key"] == "plywood"
    sm = ctx["strength_map"]
    assert set(np.unique(sm[ctx["ls"].solid]).round(3)) == {round(ctx["mat"]["strength"], 3),
                                                           round(ctx["plate_mat"]["strength"], 3)}
    rec = load_study.study(stool, "stool")
    (case,) = rec["cases"]
    assert case["safety"] and case["fea"]["in"] in ("top", None) or case["fea"]["safety"]
    # the top rests on the printed sides along two edges: a beam across them, the safe side
    pl = case["plate"]
    assert pl["piece"] == "top" and pl["edges_held"] == 2 and pl["done"] and pl["as"] == "beam"
    assert pl["span_mm"] == pytest.approx(300, abs=2)          # the top's outline: the safe side, like the plate check
    force = 200 * 4.44822 * 2
    assert pl["stress_mpa"] == pytest.approx(force * pl["span_mm"] / 4 / (220 * 12.7 ** 2 / 6), rel=0.02)
    assert case["governs"] == "plate" and case["safety"] == pl["safety_across"]       # plywood across its grain
    assert any(n.startswith("Two materials") for n in rec["notes"])
    if not per_voxel:
        assert any("stiffness throughout" in n for n in rec["notes"])
