"""CALI-203 (#335): Lighten judges and weighs each panel in its own material, as the plate check does since #328.

It used the sheets' material, their most by volume, for everything it did to a panel: the allowable of a holed panel,
the allowable at a picture's edge, the allowable of the top's holes, and what every hole and every sheet weighs. In a
part of XPS walls with a plywood floor, the floor's holes were held to foam's strength, and weighed as foam.

Synthetic: #328's box, 2 in XPS walls on two rails with a 3/4 in plywood floor between them, a light load on the floor.
Its left wall is plywood too, so a wall of the part's lesser material has a picture's edge to judge."""

import numpy as np
import pytest

from caliper import lighten
from caliper import load_study as L
from caliper.design import DesignStore

from .test_plate_held import RAILS

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

_LEFT = '''            out.append({"name": name, "kind": "sheet", "material": "xps", "thickness": X,
                        "outline": [(x0, y0, 0), (x0, y1, 0), (x0, y1, H), (x0, y0, H)]})'''
MIXED = (RAILS.replace("T, W, D, H, X = 9.525,", "T, W, D, H, X = 19.05,").replace('"lb": 400', '"lb": 10')
         .replace(_LEFT, _LEFT.replace('"material": "xps"', '"material": "plywood" if name == "left" else "xps"')))
#: a square hole in the floor, beside the load; and a picture cut out of the plywood left wall
HOLED = MIXED + '''

HOLES = [{"piece": "floor", "normal": [0, 0, 1], "depth": 19.05,
          "polygons": [[[60, 60, 19.05], [120, 60, 19.05], [120, 120, 19.05], [60, 120, 19.05]]]},
         {"piece": "left", "normal": [1, 0, 0], "depth": 50.8, "picture": True,
          "polygons": [[[-50.8, 100, 80], [-50.8, 160, 80], [-50.8, 160, 140], [-50.8, 100, 140]]]}]
'''
PLY, XPS = (L.material([{"material": k, "volume": 1.0}]) for k in ("plywood", "xps"))


def _store(tmp_path, src):
    store = DesignStore.create("a cargo box", base=str(tmp_path / "designs"))
    store.write_part("box", src, intent="a foam box with a plywood floor and a plywood end")
    return store


def test_mixed_is_of_xps_with_a_plywood_floor_and_end(tmp_path):
    ctx = L.prepare(_store(tmp_path, MIXED), "box")
    assert ctx["mat"]["key"] == "xps" and (ctx.get("plate_mat") or ctx["mat"])["key"] == "xps"
    got = {pc["name"]: lighten.own_of(ctx, pc["name"], ctx["mat"])["key"] for pc in ctx["pieces"]}
    assert got == {"floor": "plywood", "left": "plywood", "right": "xps", "front": "xps", "back": "xps"}
    assert lighten.own_of(ctx, "no such piece", ctx["mat"]) is ctx["mat"]
    assert lighten.allow_of(PLY) == PLY["strength"] * 0.5 and lighten.allow_of(XPS) == XPS["strength"]


def test_the_holes_weigh_what_their_own_panels_are_made_of(tmp_path):
    from shapely.geometry import box

    ctx = L.prepare(_store(tmp_path, MIXED), "box")
    panels = [{"name": "floor", "t": 19.05}, {"name": "front", "t": 50.8}]
    holes = {"floor": [box(0, 0, 10, 10)], "front": [box(0, 0, 10, 10), box(20, 0, 30, 10)]}
    want = 100 * 19.05 * PLY["density"] * 1e-3 + 2 * 100 * 50.8 * XPS["density"] * 1e-3
    assert lighten.saved_grams(ctx, panels, holes, ctx["mat"]) == pytest.approx(want)


def test_the_check_judges_a_holed_floor_and_a_pictured_wall_each_in_its_own_material(tmp_path, monkeypatch):
    """The strength check's holed panels (judge_holed): the floor stood on, with a hole, in plywood, where it read 0.24 in
    foam on main; the plywood wall's picture edge in plywood, where it was held to the sheets' foam."""
    seen, edges = [], []
    real_allow, real_edge = lighten.allow_of, lighten.picture_edge
    monkeypatch.setattr(lighten, "allow_of", lambda m: seen.append(m["key"]) or real_allow(m))

    def edge(p, polys, vm, filled, s, allow):
        edges.append((p["name"], allow))
        return real_edge(p, polys, vm, filled, s, allow)

    monkeypatch.setattr(lighten, "picture_edge", edge)
    rec = L.study(_store(tmp_path, HOLED), "box")
    (c,) = rec["cases"]
    assert seen == ["plywood", "plywood"]                 # the holed floor's, then the pictured left wall's
    assert edges == [("left", PLY["strength"] * PLY["across"])]
    # judged in foam, the floor's hole read ✗ 0.24 on main. In plywood it holds. What governs is the FEA here, the
    # foam walls' buckling once the FEA judges each piece in its own material (#348): either way, not the hole
    assert c["holds"] and c["safety"] >= 2.0


def _area(poly) -> float:
    """A flat 3D polygon's area (Newell)."""
    pts = np.asarray(poly, float)
    return float(np.linalg.norm(np.cross(pts, np.roll(pts, -1, axis=0)).sum(axis=0)) / 2.0)


def test_lighten_holes_the_plywood_floor_by_plywood_and_weighs_each_panel_by_its_own(tmp_path):
    """On main, the floor's first holes were held to foam's strength (1.2, so Lighten stopped there) and weighed as
    foam. Now its holes hold, and every step weighs each panel's holes, and every thinner sheet, in its own material."""
    store = _store(tmp_path, MIXED)
    ctx = L.prepare(store, "box")
    own = {pc["name"]: (pc["thickness"], lighten.own_of(ctx, pc["name"], ctx["mat"])["density"] * 1e-3)
           for pc in ctx["pieces"]}
    rec = lighten.study(store, "box", steps=(0.5,))
    steps = [st for st in rec["stations"] if st["phase"] != "thinner"]
    holed = [st for st in steps if st["phase"] == "top" and st["holds"]]
    assert holed and max(st["top_holes"] for st in holed) >= 10        # main stopped at its first top step, ✗ 1.2
    for st in steps:
        grams = sum(_area(h) * own[name][0] * own[name][1] for name, hs in st["panels"].items() for h in hs)
        assert st["saved_lb"] == pytest.approx(grams / 453.59237, abs=0.011), st["index"]
    wood_lb = sum(pc["volume"] * own[pc["name"]][1] for pc in ctx["pieces"] if pc["kind"] == "sheet") / 453.59237
    t0 = max(pc["thickness"] for pc in ctx["pieces"] if pc["kind"] == "sheet")
    thinner = [st for st in rec["stations"] if st["phase"] == "thinner"]
    assert thinner
    for st in thinner:
        base = rec["stations"][st["from_step"]]["saved_lb"]
        assert st["saved_lb"] == pytest.approx(base + (wood_lb - base) * (1 - st["thickness_mm"] / t0), abs=0.011)
