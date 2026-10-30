"""CALI-48 (#4) — the shop: what you have, which of it makes each piece, and printed parts fitted to it."""

import os

import pytest

from caliper import making, printing, scorecard, shop
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

IN = 25.4
ROUTER = {"id": "router", "kind": "router", "bed_in": [24, 36], "materials": ["plywood", "xps"]}
PLASMA = {"id": "plasma", "kind": "plasma", "bed_in": [48, 48], "plate_max_in": 0.25, "materials": ["steel"]}
PRINTER = {"id": "printer", "kind": "printer", "volume_mm": [256, 256, 256], "materials": ["pla", "petg"]}


def ply(w, h, t=19.05, **kw):
    return {"kind": "sheet", "material": "plywood", "thickness": t, "size_mm": [w, h], "flat": True, **kw}


def test_a_hand_tool_shop_is_the_default_and_your_own_is_kept():
    assert shop.read() == {**shop.DEFAULT, "default": True}
    got = shop.write({"hand": ["jigsaw", "welder", "a lightsaber"], "machines": [{"kind": "printer", "volume_mm": [180] * 3},
                                                                                 {"kind": "loom"}]})
    assert got["hand"] == ["jigsaw", "welder"] and [m["kind"] for m in got["machines"]] == ["printer"]
    assert got["machines"][0]["id"] == "printer" and "default" not in got
    assert os.path.exists(shop.path())


def test_each_piece_goes_to_what_your_shop_has():
    hand = shop.read()
    assert shop.route(ply(400, 250), hand)["how"] == "jigsaw"
    holed = shop.route(ply(400, 250, holes=2), hand)
    assert holed["how"] == "jigsaw" and "start" in holed["why"]
    thick = shop.route(ply(400, 250, t=50.8), hand)
    assert thick["how"] == "circular saw"                                    # straight, no holes: it'll do
    assert not shop.route(ply(400, 250, t=50.8, holes=1), hand)["ok"]       # a hole in 2 in ply: no
    assert not shop.route({"kind": "sheet", "material": "steel", "thickness": 4.76, "size_mm": [150, 150]}, hand)["ok"]
    assert not shop.route({"kind": "printed", "material": "petg"}, hand)["ok"]
    tube = shop.route({"kind": "stick", "material": "steel"}, hand)
    assert not tube["ok"] and "welder" in tube["why"]

    machines = {"hand": ["jigsaw", "chop saw"], "machines": [ROUTER, PLASMA, PRINTER]}
    assert shop.route(ply(500, 300), machines)["how"] == "router"
    assert shop.route(ply(1200, 300), machines)["how"] == "jigsaw"           # longer than the router's bed
    plate = {"kind": "sheet", "material": "steel", "thickness": 4.76, "size_mm": [150, 150]}
    assert shop.route(plate, machines)["how"] == "plasma"
    assert not shop.route({**plate, "thickness": 9.525}, machines)["ok"]    # thicker than the table cuts
    assert shop.route({"kind": "printed", "material": "petg"}, machines)["how"] == "printer"
    assert shop.route({"kind": "stick", "material": "steel"}, machines)["why"].startswith("and a welder")


def test_the_stool_is_made_with_a_jigsaw(tmp_path):
    pytest.importorskip("cadquery")
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box stool")
    got = making.plan(store, "stool")
    assert got["ok"] and got["shop_default"]
    assert sorted(got["by_how"]["jigsaw"]) == ["back", "front", "left", "right", "top"]


PRINTED = '''import cadquery as cq

def build(params):
    return cq.Workplane("XY").box(400, 60, 40)

def construction(params, build=None):
    return [{"name": "the bar", "kind": "printed", "material": "petg"}]
'''


def test_a_printed_part_too_big_for_the_printer_is_split_and_pinned(tmp_path):
    pytest.importorskip("cadquery")
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    assert not making.plan(store, "bar")["ok"]                               # no printer: said so
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    got = making.plan(store, "bar", out_dir=str(tmp_path / "print"))
    (pr,) = got["printed"]
    assert pr["pieces"] == 2 and pr["pinned"] and pr["trust"] == "rough"
    assert pr["hours"] > 0 and pr["filament_g"] > 0 and pr["usd"] > 0
    assert sorted(os.listdir(tmp_path / "print")) == ["bar-1-of-2.stl", "bar-2-of-2.stl"]
    # the take-off weighs it as printed: walls plus infill, far less than solid PETG
    from caliper import construction as C
    rep = C.report(store, "bar")
    solid_lb = 400 * 60 * 40 * 1e-9 * 1270 * 2.20462
    assert 0.1 * solid_lb < rep["mass_lb"] < 0.6 * solid_lb
    assert rep["bom"]["printed"][0]["filament_g"] > 0


def test_split_pieces_fit_and_keep_the_part(tmp_path):
    import trimesh

    bar = trimesh.creation.box(extents=(600, 80, 50))
    parts = printing.split(bar, (256, 256, 256))
    assert len(parts) == 3 and all(p.is_watertight and printing.fits(p.extents, (256, 256, 256)) for p in parts)
    pins = bar.volume - sum(p.volume for p in parts)
    assert 0 < pins < 0.01 * bar.volume                                      # only the pin holes are gone
    assert printing.split(trimesh.creation.box(extents=(240, 20, 20)), (256, 256, 256))[0] is not None
    assert printing.fits((300, 100, 50), (200, 320, 200))                    # turned, it fits


def test_the_scorecard_says_when_your_shop_cant_make_it(tmp_path):
    pytest.importorskip("cadquery")
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    card = scorecard.compute(store)
    check = next(c for c in card["checks"] if c["id"] == "make:shop")
    assert check["status"] == "fail" and "3D printer" in check["note"]
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    card = scorecard.compute(store)
    assert next(c for c in card["checks"] if c["id"] == "make:shop")["status"] == "pass"
    assert card["metrics"]["print.hours"]["value"] > 0
