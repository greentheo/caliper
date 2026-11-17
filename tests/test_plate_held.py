"""CALI-199 (#328): the plate check spans only a panel that spans, and checks each sheet in its own material.

Found on a copy of the camper sample: a 3/8 in plywood floor resting on its support over its whole underside read 0.01×
by the plate check (its four edges freed and spanned, and at XPS foam's strength, the part's most-by-volume material)
where the FEA read 1,361×.

Synthetic: a box of 2 in XPS walls with a 3/8 in plywood floor between them, a load on the floor's middle. As drawn it
rests on the floor (the default support, under its whole underside). ``RAILS`` stands it on two rails under its end
walls instead, so the floor spans between the walls. No FEA: the strength check's own set-up, then the plate check."""

import pytest

from caliper import load_study as L
from caliper.design import DesignStore

pytest.importorskip("cadquery")

BOX = '''import cadquery as cq

T, W, D, H, X = 9.525, 600.0, 400.0, 300.0, 50.8      # the floor, the inside, the walls' height and thickness


def _walls():
    return {"left": ((-X, -X, 0), (0, D + X, H)), "right": ((W, -X, 0), (W + X, D + X, H)),
            "front": ((0, -X, 0), (W, 0, H)), "back": ((0, D, 0), (W, D + X, H))}


def build(params):
    out = cq.Workplane().box(W, D, T, centered=False)
    for (x0, y0, z0), (x1, y1, z1) in _walls().values():
        out = out.union(cq.Workplane().box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0)))
    return out


def construction(params, build=None):
    out = [{"name": "floor", "kind": "sheet", "material": "plywood", "thickness": T,
            "outline": [(0, 0, T), (W, 0, T), (W, D, T), (0, D, T)]}]
    for name, ((x0, y0, z0), (x1, y1, z1)) in _walls().items():
        if name in ("left", "right"):
            out.append({"name": name, "kind": "sheet", "material": "xps", "thickness": X,
                        "outline": [(x0, y0, 0), (x0, y1, 0), (x0, y1, H), (x0, y0, H)]})
        else:
            out.append({"name": name, "kind": "sheet", "material": "xps", "thickness": X,
                        "outline": [(x0, y0, 0), (x1, y0, 0), (x1, y0, H), (x0, y0, H)]})
    return out


def loads(params, build=None):
    return [{"name": "a mattress", "lb": 400, "factor": 2.0, "lo": (250, 150, T - 2), "hi": (350, 250, T)}]
'''

#: stood on two rails under its end walls: the floor spans between the walls, nothing under its middle
RAILS = BOX + '''

def held(params, build=None):
    return [{"name": "left rail", "lo": (-X, -X, -5), "hi": (0, D + X, 0)},
            {"name": "right rail", "lo": (W, -X, -5), "hi": (W + X, D + X, 0)}]
'''


def _plate(tmp_path, src):
    store = DesignStore.create("a cargo box", base=str(tmp_path / "designs"))
    store.write_part("box", src, intent="a foam box with a plywood floor")
    ctx = L.prepare(store, "box")
    (load,) = ctx["loads"]
    return ctx, L.plate_check(ctx["pieces"], load, ctx.get("plate_mat") or ctx["mat"], ctx["tol"],
                              under=L.with_held(ctx.get("under"), ctx.get("held") or [], ctx["tol"]),
                              held=ctx.get("held"))


def test_a_panel_resting_on_its_support_under_the_load_isn_t_spanned(tmp_path):
    ctx, pl = _plate(tmp_path, BOX)
    assert ctx["mat"]["key"] == "xps" and [h["name"] for h in ctx["held"]] == ["the floor"]
    assert pl["piece"] == "floor" and not pl["done"] and pl["rests_on"] == "the floor"
    assert pl["why"] == ("the load goes straight through it into what it stands on, so it doesn't span: the FEA is the "
                         "number for it")


def test_a_panel_spanning_between_its_supports_is_still_checked_and_in_its_own_material(tmp_path):
    ctx, pl = _plate(tmp_path, RAILS)
    ply = L.material([{"material": "plywood", "volume": 1.0}])
    assert ctx["mat"]["key"] == "xps" and pl["piece"] == "floor" and pl["done"] and pl["edges_held"] == 4
    assert pl["material"] == "softwood plywood"
    assert pl["safety"] == pytest.approx(ply["strength"] / pl["stress_mpa"], rel=0.01)
    assert pl["safety_across"] == pytest.approx(pl["safety"] * ply["across"], abs=0.01)   # each cut to 2 places
    by = next(b for b in pl["by_thickness"] if b["thickness_mm"] == pytest.approx(9.525))
    assert by["safety"] == pytest.approx(pl["safety"], rel=0.02)


def test_a_sheet_of_the_material_it_s_analysed_in_keeps_the_material_given(tmp_path):
    """A caller's material for the part's own sheets (the bar stool's test hands one in) is kept: only a sheet of another
    material is checked in its own."""
    ctx, _ = _plate(tmp_path, RAILS)
    (load,) = ctx["loads"]
    given = {"key": "plywood", "name": "given", "strength": 30.0, "across": 0.5, "E": 8000.0}
    pl = L.plate_check(ctx["pieces"], load, given, ctx["tol"], held=ctx.get("held"))
    assert pl["material"] == "given" and pl["safety"] == pytest.approx(30.0 / pl["stress_mpa"], rel=0.01)


def test_lighten_reads_the_rested_panel_as_the_check_does(tmp_path):
    """Lighten's thicknesses come from the same plate check, so the floor resting on its support has none either."""
    from caliper import lighten

    ctx, _ = _plate(tmp_path, BOX)
    assert lighten._plate_at(ctx, "a mattress", 9.525) is None
    ctx, _ = _plate(tmp_path / "rails", RAILS)
    assert lighten._plate_at(ctx, "a mattress", 9.525) is not None


def _held(*boxes):
    return BOX + "\n\ndef held(params, build=None):\n    return [" + ", ".join(
        f'{{"name": "{n}", "lo": {lo}, "hi": {hi}}}' for n, lo, hi in boxes) + "]\n"


#: a pad under the floor's whole underside, said by the part: named in the words
PAD = _held(("a pad", "(0, 0, -5)", "(W, D, 0)"))

#: a pad under part of the load (the floor's left half): less than nine tenths of it backed, so the floor still spans
HALF = _held(("a pad", "(0, 0, -5)", "(300, D, 0)"), ("right rail", "(W, -X, -5)", "(W + X, D + X, 0)"))

#: the pad, the load pushing up: the floor lifts off it, so it spans
LIFT = PAD.replace('"lb": 400, "factor": 2.0', '"force": (0, 0, 1779.3), "factor": 2.0')


def test_a_named_support_under_the_load_is_said_by_its_name(tmp_path):
    _, pl = _plate(tmp_path, PAD)
    assert not pl["done"] and pl["rests_on"] == "a pad"
    assert pl["why"].startswith("the load goes straight through it into 'a pad', so it doesn't span")


@pytest.mark.parametrize("src", [HALF, LIFT], ids=["half under the load", "pushed off it"])
def test_a_support_not_backing_the_load_leaves_the_plate_check_on(tmp_path, src):
    _, pl = _plate(tmp_path, src)
    assert pl["piece"] == "floor" and pl["done"] and "rests_on" not in pl


# --- the walls: a load that goes straight into a support doesn't run down them (#328, the foreman's rules) ---------------

#: a second load, on the left wall's top: in its plane, down it. Beside the floor's, which rests
ROOFED = BOX.replace('''    return [{"name": "a mattress", "lb": 400, "factor": 2.0, "lo": (250, 150, T - 2), "hi": (350, 250, T)}]''',
                     '''    return [{"name": "a mattress", "lb": 400, "factor": 2.0, "lo": (250, 150, T - 2), "hi": (350, 250, T)},
            {"name": "a roof", "lb": 200, "factor": 2.0, "lo": (-X, 100, H - 2), "hi": (0, 300, H)}]''')


def _walls(tmp_path, src, which=0, mat=None):
    from caliper import buckling as B

    store = DesignStore.create("a cargo box", base=str(tmp_path / "designs"))
    store.write_part("box", src, intent="a foam box with a plywood floor")
    ctx = L.prepare(store, "box")
    load = ctx["loads"][which]
    return ctx, B.check(ctx["pieces"], load, mat or ctx.get("plate_mat") or ctx["mat"], ctx["tol"], held=ctx.get("held"))


def test_a_load_resting_on_its_support_runs_down_no_wall_and_leaves_no_gap(tmp_path):
    ctx, rows = _walls(tmp_path, BOX)
    assert sorted(r["piece"] for r in rows) == ["back", "front", "left", "right"]
    assert all(r["rests"] and not r["done"] and "safety" not in r for r in rows)
    assert rows[0]["why"] == "the load goes straight through the floor into what it stands on, so it doesn't run down this wall"
    # not #272's "not checked": nothing said of buckling at all, where no wall carries anything
    assert L.buckling_notes(ctx["pieces"], ctx["loads"], ctx["mat"], ctx["tol"], ctx.get("plate_mat"),
                            held=ctx.get("held")) == []


def test_a_load_over_a_gap_in_its_support_still_runs_down_the_walls(tmp_path):
    """Less than nine tenths of it backed: the walls carry all of it, as before (when in doubt, they do)."""
    _, rows = _walls(tmp_path, HALF)
    assert rows and all(r["done"] and r["share"] == 1.0 and not r.get("rests") for r in rows)


def test_a_wall_load_beside_a_resting_floor_load_still_buckles_the_walls_in_their_own_material(tmp_path):
    ctx, rows = _walls(tmp_path, ROOFED, which=1, mat={"key": "plywood", "name": "given", "E": 8000.0, "strength": 30.0,
                                                        "across": 0.5})
    left = next(r for r in rows if r["piece"] == "left")
    assert left["done"] and not left.get("rests") and left["safety"] > 0
    xps = L.material([{"material": "xps", "volume": 1.0}])
    assert left["E_mpa"] == pytest.approx(xps["E"])          # the foam wall in foam, not the plywood handed in
    _, floor = _walls(tmp_path / "again", ROOFED, which=0)
    assert all(r["rests"] for r in floor)                   # only the floor's load is dropped


def test_a_part_whose_only_load_rests_on_its_support_reads_not_resolved_and_says_why(tmp_path, monkeypatch):
    """The camper's case through the check itself: neither the plate check's 0.01× nor the walls' buckling, and no ✓
    either: the FEA sees nothing between the load and its support (#202), and the words say that's why."""
    pytest.importorskip("whittle")
    from caliper import verdicts as V

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a cargo box", base=str(tmp_path / "designs"))
    store.write_part("box", BOX, intent="a foam box with a plywood floor")
    rec = L.study(store, "box")
    (case,) = rec["cases"]
    assert case["plate"]["rests_on"] == "the floor" and not case["plate"]["done"]
    assert case["governs"] == "fea" and all(r.get("rests") for r in case["buckling"])
    got = V.case(rec, case)
    assert got["kind"] == "unresolved" and got["blind"]
    assert got["why"] == ("Not resolved: the load goes straight through the floor into what it stands on: nothing between "
                          "to check.")
    assert not any("uckling" in n for n in rec["notes"])


def test_a_load_that_doesn_t_rest_still_gets_its_own_verdict_beside_one_that_does(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import verdicts as V

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a cargo box", base=str(tmp_path / "designs"))
    store.write_part("box", ROOFED, intent="a foam box with a plywood floor")
    rec = L.study(store, "box")
    floor, roof = rec["cases"]
    assert V.case(rec, floor)["kind"] == "unresolved" and floor["rests"]["piece"] == "floor"
    assert "rests" not in roof and roof["governs"] == "buckling"
    assert V.case(rec, roof)["kind"] == "fails" and roof["safety"] < 1     # the foam wall folds under the roof's load
    assert V.run(rec)["kind"] == "fails"                                    # and the part's verdict is the roof's


def test_a_resting_load_the_fea_reads_a_number_for_is_still_not_a_tick():
    """Where the FEA does read a stress for a load that goes straight into its support (the camper's 1,360.9×), it's the
    stress where the load meets what holds it: never ✓, never ✗, and said why (#328)."""
    from caliper import verdicts as V

    run = {"min_safety": 2.0, "material": {"strength": 15.0}}
    case = {"name": "a mattress", "force_n": [0, 0, -1779.3], "lo": [250, 150, 7.5], "hi": [350, 250, 9.5],
            "fea": {"supported": True, "safety": 1360.9}, "governs": "fea", "safety": 1360.9, "holds": True}
    assert V.case(run, case)["kind"] == "holds"                      # read as the FEA's own, without the rest
    case["rests"] = {"piece": "floor", "on": "the floor",
                     "said": "the load goes straight through the floor into what it stands on: nothing between to check"}
    got = V.case(run, case)
    assert got["kind"] == "unresolved" and got["why"].startswith("Not resolved: the load goes straight through the floor")
