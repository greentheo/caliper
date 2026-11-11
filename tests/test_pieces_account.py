"""CALI-155 (#219; rule 6) — pieces that don't account for the solid: the view, the make side and the advice go by what's true.

A first build's solid was right, with two splayed plywood sides, but construction() declared each side as a flat strip inside the top
panel. The screen showed two floating boards, "Patterns ready" came from the strips, and the advice would have deleted the real sides."""

import os

import pytest

from caliper import answers, authoring, consistency, cutplan, design_api, patterns, scorecard
from caliper import construction as C
from caliper.design import DesignStore
from caliper.spec import Spec

pytest.importorskip("cadquery")

#: The shape of Theo's stool: a top on two sides splayed outward, and a stretcher. ``{sides}`` is how its construction() says the sides.
STOOL = '''import cadquery as cq
import math

W, D, H, T, SPLAY = 304.8, 254.0, 228.6, 19.05, 10.0
SIDE_H = H - T
FOOT = SIDE_H * math.tan(math.radians(SPLAY))
HALF = D / 2
HW = W / 2
INNER = HALF - T + FOOT * (1 - (T / 2) / SIDE_H)


def build(params):
    def side(s):
        pts = [(SIDE_H, s * (HALF - T)), (SIDE_H, s * HALF), (0, s * (HALF + FOOT)), (0, s * (HALF - T + FOOT))]
        return cq.Workplane("ZY").workplane(offset=-HW).polyline(pts).close().extrude(W)

    top = cq.Workplane("XY").box(W, D, T).translate((0, 0, H - T / 2))
    rail = cq.Workplane("XY").box(W, INNER * 2, T).translate((0, 0, T / 2))
    return top.union(side(1)).union(side(-1)).union(rail)


def construction(params, build=None):
    def side(s):
{sides}

    def sheet(name, outline):
        return {{"name": name, "kind": "sheet", "material": "plywood", "thickness": T, "outline": outline}}

    return [sheet("top", [(-HW, -HALF, H), (HW, -HALF, H), (HW, HALF, H), (-HW, HALF, H)]),
            sheet("side back", side(1)), sheet("side front", side(-1)),
            sheet("stretcher", [(-HW, -INNER, T), (HW, -INNER, T), (HW, INNER, T), (-HW, INNER, T)])]


def loads(params, build=None):
    return [{{"name": "a foot", "lb": 200, "factor": 2.0, "lo": (-50, -50, H - 2), "hi": (50, 50, H)}}]
'''
STRIPS = STOOL.format(sides="        return [(-HW, s * (HALF - T), SIDE_H), (HW, s * (HALF - T), SIDE_H), (HW, s * HALF, SIDE_H), (-HW, s * HALF, SIDE_H)]")
RIGHT = STOOL.format(sides="        return [(-HW, s * HALF, SIDE_H), (HW, s * HALF, SIDE_H), (HW, s * (HALF + FOOT), 0.0), (-HW, s * (HALF + FOOT), 0.0)]")
INNER_FACE = STOOL.format(sides="        return [(-HW, s * (HALF - T), SIDE_H), (HW, s * (HALF - T), SIDE_H), (HW, s * (HALF - T + FOOT), 0.0), (-HW, s * (HALF - T + FOOT), 0.0)]")


def _store(tmp_path, script):
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a step stool")
    return s


def _check(store):
    return {r.id: r for r in consistency.check(C.declared(store, "stool"), store.part_geometry("stool"))}


@pytest.mark.parametrize("script", [RIGHT, INNER_FACE], ids=["outer face", "inner face"])
def test_a_sloped_panel_written_right_passes_every_check(tmp_path, script):
    got = _check(_store(tmp_path, script))
    assert got and all(r.passed for r in got.values()), {k: r.detail for k, r in got.items() if not r.passed}


def test_the_round_fails_on_the_strips_names_where_and_says_how(tmp_path):
    seen = []

    def designer(spec, feedback, prior):
        seen.append(feedback)
        return STRIPS if len(seen) == 1 else RIGHT

    got = authoring.improve(Spec(part="stool", intent="a step stool"), author=designer)
    assert got.ok and got.rounds == 2
    said = seen[1]
    assert "no piece describes" in said
    assert "y -" in said and "y 1" in said                          # each side, not the middle of the part between them
    assert "real corners in 3D" in said


def test_the_material_no_piece_accounts_for_is_found_side_by_side(tmp_path):
    s = _store(tmp_path, STRIPS)
    from caliper.consistency import _loose_regions, _sides, shapes, tolerance

    mesh = s.part_geometry("stool").require_mesh()
    pieces = shapes(C.declared(s, "stool"))
    _sides(mesh, pieces)
    regions = _loose_regions(mesh, pieces, tolerance(mesh))
    assert len(regions) == 2 and all(r["panel"] for r in regions)
    assert sorted(r["lo"][1] > 0 for r in regions) == [False, True]


FILLED = '''import cadquery as cq


def build(params):
    return cq.Workplane().box(300, 200, 200, centered=False)


def construction(params, build=None):
    t = 19.05
    def sheet(name, o):
        return {"name": name, "kind": "sheet", "material": "plywood", "thickness": t, "outline": o}
    return [sheet("top", [(0, 0, 200), (300, 0, 200), (300, 200, 200), (0, 200, 200)]),
            sheet("bottom", [(0, 0, 0), (300, 0, 0), (300, 200, 0), (0, 200, 0)]),
            sheet("left", [(0, 0, 0), (0, 200, 0), (0, 200, 200), (0, 0, 200)]),
            sheet("right", [(300, 0, 0), (300, 200, 0), (300, 200, 200), (300, 0, 200)]),
            sheet("front", [(0, 0, 0), (300, 0, 0), (300, 0, 200), (0, 0, 200)]),
            sheet("back", [(0, 200, 0), (300, 200, 0), (300, 200, 200), (0, 200, 200)])]


def loads(params, build=None):
    return [{"name": "a foot", "lb": 100, "factor": 2.0, "lo": (100, 50, 198), "hi": (200, 150, 200)}]
'''


def test_a_filled_box_has_right_pieces_so_the_make_side_stands_and_both_fixes_are_said(tmp_path):
    s = _store(tmp_path, FILLED)
    assert consistency.not_accounted(s, "stool") is None
    why = consistency.filled(s, "stool")
    assert why and "filled in" in why
    said = answers.untrusted("stool", why)
    assert answers.fix_shape("stool") in said and answers.fix_piece("stool") in said


def test_a_lid_left_off_or_a_filled_shape_is_not_a_panel_left_out(tmp_path):
    from .test_construction import BOX
    from .test_filled_verdict import FILLED as BLOCK

    assert consistency.not_accounted(_store(tmp_path / "a", BOX), "stool") is None       # surface on no piece, its pieces still right
    assert consistency.not_accounted(_store(tmp_path / "b", BLOCK), "stool") is None


@pytest.fixture
def strips(tmp_path):
    return _store(tmp_path, STRIPS)


def _cards(store):
    state = design_api.design_state(store)
    return answers.answers(store, state, "stool")


def _all_text(cards):
    cards = cards if isinstance(cards, list) else cards.get("cards", cards)
    return " ".join(ln["text"] for c in cards for ln in c["lines"])


def test_the_strips_are_said_not_to_account_for_the_solid(strips):
    why = consistency.not_accounted(strips, "stool")
    assert why and "no piece describes" in why


def test_the_advice_says_fix_the_pieces_not_the_shape(strips):
    why = consistency.filled(strips, "stool")
    said = answers.untrusted("stool", why)
    assert answers.fix_piece("stool") in said and answers.fix_shape("stool") not in said
    fix = answers.fix_for("construction_volume", why, "stool")
    assert answers.fix_piece("stool") in fix and answers.fix_shape("stool") not in fix
    fix = answers.fix_for("construction_covers", consistency.not_accounted(strips, "stool"), "stool")
    assert answers.fix_piece("stool") in fix and answers.fix_shape("stool") not in fix


def test_no_weight_from_pieces_that_dont_account_for_the_solid(strips):
    r = C.report(strips, "stool")
    assert r["mass_lb"] is None and r["not_accounted"] and "no piece describes" in r["unweighed"]
    assert C.balance(strips)["mass_lb"] is None


def test_the_card_offers_no_patterns_cut_list_or_weight(strips):
    said = _all_text(_cards(strips))
    assert "Patterns ready" not in said and "Make the patterns" not in said and "It weighs" not in said
    assert "sheets of" not in said and "sheet of" not in said
    assert consistency.NO_MAKE in said


def test_patterns_and_a_cut_plan_are_refused(strips, monkeypatch):
    with pytest.raises(ValueError, match=consistency.NO_MAKE):
        patterns.make(strips, "stool")
    monkeypatch.setattr(cutplan, "available", lambda: None)
    with pytest.raises(ValueError, match=consistency.NO_MAKE):
        cutplan.run(strips, "stool")


def test_a_build_package_is_refused(strips, monkeypatch):
    from caliper import release

    monkeypatch.setattr(cutplan, "available", lambda: None)
    with pytest.raises(ValueError, match=f"for the stool, {consistency.NO_MAKE}"):
        release.make(strips)


def test_the_view_is_told_to_draw_the_solid_and_why(strips):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        design_api.pieces_or_why(strips, "stool")
    assert e.value.status_code == 409 and "no piece describes" in e.value.detail and "one body" in e.value.detail


def test_the_views_piece_meshes_are_refused_too(strips, monkeypatch):
    """What the 3D view fetches for each piece: the two floating boards came from here."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(strips.root))
    app = FastAPI()
    app.include_router(design_api.router())
    slug = os.path.basename(strips.root)
    key = next(p for p in design_api.design_state(strips)["parts"] if p["id"] == "stool")["pieces"][0]["key"]
    got = TestClient(app).get(f"/api/designs/{slug}/parts/stool/piece.stl", params={"key": key})
    assert got.status_code == 409 and "one body" in got.json()["detail"] and "no piece describes" in got.json()["detail"]


def test_a_tipping_case_with_no_weight_doesnt_crash_the_card():
    assert answers._line("not checked", "unknown")["status"] == "warn"


def test_a_cost_goal_says_it_cant_be_priced_not_the_last_cards_number(strips):
    import yaml

    with open(scorecard.goals_path(strips), "w") as f:
        yaml.safe_dump({"checks": [{"id": "cheap", "label": "cheap", "metric": "cost.usd", "op": "<=", "limit": 20}]}, f)
    state = design_api.design_state(strips)
    state["scorecards"] = [{"metrics": {"cost.usd": {"value": 36, "unit": "$"}}, "versions": {}}]
    line = next(ln for ln in answers.held_to(state, answers.measured(strips, state)) if ln["text"].startswith("Cheap"))
    assert "$36" not in line["text"] and "no piece describes" in line["text"] and line["status"] == "warn"


def test_the_state_tells_the_page(strips):
    part = next(p for p in design_api.design_state(strips)["parts"] if p["id"] == "stool")
    assert part["not_accounted"]


def test_the_scorecard_doesnt_price_them(strips):
    card = scorecard.compute(strips)
    assert card["metrics"]["cost.usd"]["value"] is None and card["metrics"]["weight.stool"]["value"] is None


@pytest.fixture
def right(tmp_path):
    return _store(tmp_path, RIGHT)


def test_a_right_declaration_keeps_all_of_it(right):
    assert consistency.not_accounted(right, "stool") is None
    r = C.report(right, "stool")
    assert r["mass_lb"] and not r.get("not_accounted")
    assert design_api.pieces_or_why(right, "stool")["pieces"]
    said = _all_text(_cards(right))
    assert consistency.NO_MAKE not in said and "It weighs" in said and "Make the patterns" in said
    assert patterns.make(right, "stool")["pages"]


def test_the_guide_says_a_sloped_panels_outline_is_its_real_corners():
    with open(os.path.join(os.path.dirname(C.__file__), "part_scripts.md")) as f:
        guide = f.read()
    assert "real corners in 3D" in guide and "never a flat stand-in" in guide
