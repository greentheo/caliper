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
    # a thinner sheet thins the thickest stock only (#354): the 2 in walls, never the 3/4 in floor. On 79cfb35 every sheet
    # thinned, so the "1 1/2 in" row also shaved the plywood floor to 14.3 mm: 1.41 lb of its 7.46 lb
    sheets = [pc for pc in ctx["pieces"] if pc["kind"] == "sheet"]
    t0 = max(pc["thickness"] for pc in sheets)
    thick_lb = sum(pc["volume"] * own[pc["name"]][1] for pc in sheets if pc["thickness"] >= t0 - 0.01) / 453.59237
    floor_lb = sum(pc["volume"] * own[pc["name"]][1] for pc in sheets if pc["name"] == "floor") / 453.59237
    assert t0 == pytest.approx(50.8) and floor_lb > 1.0
    thinner = [st for st in rec["stations"] if st["phase"] == "thinner"]
    assert any(st["thickness_mm"] == pytest.approx(38.1) for st in thinner)
    for st in thinner:
        from_ = rec["stations"][st["from_step"]]
        assert not from_.get("top_holes") and all(n != "floor" or not hs for n, hs in from_["panels"].items())
        base, off = from_["saved_lb"], 1 - st["thickness_mm"] / t0
        assert st["saved_lb"] == pytest.approx(base + (thick_lb - base) * off, abs=0.011)    # the walls' stock only
        every = base + (thick_lb + floor_lb - base) * off                                    # 79cfb35's
        assert every - st["saved_lb"] == pytest.approx(floor_lb * off, abs=0.011)             # the floor's share, gone


def test_a_thinner_sheet_leaves_the_floor_s_plate_check_at_its_own_thickness(tmp_path):
    """The safety side (#354): a plate check of a sheet of the other stock reads at its own thickness, never thinned."""
    ctx = L.prepare(_store(tmp_path, MIXED), "box")
    walls = {pc["name"]: pc for pc in ctx["pieces"] if pc["kind"] == "sheet" and pc["thickness"] > 40}
    name = ctx["loads"][0]["name"]
    pl = L.plate_check(ctx["pieces"], ctx["loads"][0], lighten.sheet_of(ctx), ctx["tol"], held=ctx.get("held"),
                       voxel=ctx.get("spacing"))
    assert pl["done"] and pl["piece"] == "floor" and pl["piece"] not in walls
    assert lighten._plate_at(ctx, name, 38.1, walls) == pl["safety_across"]                 # the floor stays 3/4 in
    assert lighten._plate_at(ctx, name, 15.875, {"floor": None}) == pytest.approx(           # its own stock thins
        min(pl["by_thickness"], key=lambda b: abs(b["thickness_mm"] - 15.875))["safety_across"])


# --- the thinner rows, each part of the estimate, on a part of two stocks (#354) ----------------------------------------

def _two_stocks(case, panels):
    """A 2 in XPS wall (the thickest stock) and a 3/4 in plywood floor, and a base step holding at 1.0 lb saved."""
    from caliper import construction as C, materials as M

    wall = {"name": "wall", "kind": "sheet", "material": "xps", "thickness": 50.8, "volume": 50.8 * 400 * 300}
    floor = {"name": "floor", "kind": "sheet", "material": "plywood", "thickness": 19.05, "volume": 19.05 * 600 * 400}
    base = {"index": 0, "phase": "walls", "holds": True, "top_holes": 0, "saved_lb": 1.0, "removed": 0.1, "holes": 2,
            "panels": panels, "cases": [case]}
    rows = lighten._thinner({"pieces": [wall, floor], "loads": []}, [base], [], 2.0, XPS, C, M)
    return {r["thickness_mm"]: r for r in rows}, wall, floor


def _hole(side):
    return [[0, 0, 0], [side, 0, 0], [side, side, 0], [0, side, 0]]


def test_a_thinner_row_keeps_what_the_other_stock_s_holes_saved_and_thins_only_the_thick_stock():
    rows, wall, _ = _two_stocks({"name": "n", "safety": 9.0, "governs": "fea", "fea_safety": 9.0},
                                {"wall": [_hole(100)], "floor": [_hole(100)]})
    floor_hole_lb = 100 * 100 * 19.05 * PLY["density"] * 1e-3 / 453.59237
    wall_lb = wall["volume"] * XPS["density"] * 1e-3 / 453.59237
    row = next(r for t, r in rows.items() if abs(t - 38.1) < 0.01)
    off = 1 - 38.1 / 50.8
    assert row["saved_lb"] == pytest.approx(1.0 + (wall_lb - (1.0 - floor_hole_lb)) * off, abs=0.006)


def test_a_wall_of_the_other_stock_buckles_at_its_own_thickness():
    rows, _, _ = _two_stocks({"name": "n", "safety": 2.5, "governs": "buckling", "fea_safety": 50.0,
                              "buckling": [{"piece": "wall", "safety": 60.0}, {"piece": "floor", "safety": 2.5}]}, {})
    row = next(r for t, r in rows.items() if abs(t - 38.1) < 0.01)
    assert row["safety"] == pytest.approx(2.5, abs=0.01)                   # the floor's 2.5, never thinned


def _row(rows, t):
    return next(r for x, r in rows.items() if abs(x - t) < 0.01)


def test_a_thinned_wall_s_buckling_goes_as_its_thickness_cubed():
    """caliper-reviewer on #354: buckling.check's safety is sigma_cr x b x t / push, sigma_cr going as t^2. The all-XPS-walls
    box's 16.88 at 2 in, rebuilt and checked, read 6.76 at 1 1/2 in and fails at 1 in (1.89). At t^2 the rows said 9.49
    and a passing 4.22."""
    rows, _, _ = _two_stocks({"name": "n", "safety": 16.88, "governs": "buckling", "fea_safety": 500.0,
                              "buckling": [{"piece": "wall", "safety": 16.88}]}, {})
    assert _row(rows, 38.1)["safety"] == pytest.approx(16.88 * 0.75 ** 3, abs=0.1)      # 7.12, not 9.49
    assert _row(rows, 25.4)["safety"] == pytest.approx(16.88 * 0.5 ** 3, abs=0.1)       # 2.11, not 4.22


def test_a_check_it_can_t_name_a_piece_for_goes_as_the_cube_too():
    rows, _, _ = _two_stocks({"name": "n", "safety": 8.0, "governs": "joint", "fea_safety": 500.0}, {})
    assert _row(rows, 38.1)["safety"] == pytest.approx(8.0 * 0.75 ** 3, abs=0.1)        # 3.37, not 4.5


def test_a_plate_governed_case_asks_for_the_plate_at_the_thick_stock_only(monkeypatch):
    asked = []
    monkeypatch.setattr(lighten, "_plate_at", lambda ctx, name, t, thick=None: asked.append(set(thick or ())) or 9.0)
    _two_stocks({"name": "n", "safety": 9.0, "governs": "plate", "fea_safety": 50.0}, {})
    assert asked and all(a == {"wall"} for a in asked)


def test_a_thinner_estimate_within_cut_drift_of_its_bar_is_never_a_tick():
    """The foreman's rule (#354): the all-XPS box's 1 in row estimates 2.11 at t^3, where the rebuilt check reads 1.89. An
    estimate within CUT_DRIFT (7%) of its minimum doesn't hold: it's close, and the check of the part rebuilt decides."""
    from caliper import verdicts

    rows, _, _ = _two_stocks({"name": "n", "safety": 16.88, "governs": "buckling", "fea_safety": 500.0,
                              "buckling": [{"piece": "wall", "safety": 16.88}]}, {})
    one, inch_half = _row(rows, 25.4), _row(rows, 38.1)
    assert one["safety"] == pytest.approx(2.1, abs=0.01)                               # 2.1 against 2: within 7%
    v = verdicts.lighten_step(one, None, {"min_safety": 2.0})
    assert v["kind"] == "estimate" and not v["counts_as_pass"] and v["word"] == verdicts.THIN_DECIDES
    assert "thin it and the check decides" in v["short"]
    far = verdicts.lighten_step(inch_half, None, {"min_safety": 2.0})
    assert far["kind"] == "estimate" and far["word"] != verdicts.THIN_DECIDES
    assert verdicts.thin_close(2.14, 2.0) and not verdicts.thin_close(2.15, 2.0) and not verdicts.thin_close(1.99, 2.0)
