"""CALI-131 (#162) — a sheet's outline is one face of the panel. On Theo's stool the seat's outline sat at its mid-thickness,
so the checks built the slab half a thickness low and counted the top of the seat as printed plastic, about 2 lb of it,
with nothing to say so. Stubbed: no FEA, no Claude."""

import numpy as np
import pytest
import trimesh

from caliper import consistency
from caliper.measure import Geometry

T = 19.05


def _seat_on_a_post():
    """A round-ish seat 19.05 thick, top at z 100, on a hollow post: the bar stool, in small."""
    seat = trimesh.creation.box((300, 300, T))
    seat.apply_translation((0, 0, 100 - T / 2))
    post = trimesh.creation.box((60, 60, 100 - T))
    post.apply_translation((0, 0, (100 - T) / 2))
    return trimesh.util.concatenate([seat, post])


def _outline(z):
    return [(-150, -150, z), (150, -150, z), (150, 150, z), (-150, 150, z)]


def _declared(z, printed=True, name="seat top"):
    items = [{"name": name, "kind": "sheet", "material": "plywood", "thickness": T, "outline": _outline(z)}]
    if printed:
        items.append({"name": "post", "kind": "printed", "material": "petg", "rest": True})
    return {"construction": items}


def _result(declared, mesh):
    got = {r.id: r for r in consistency.check(declared, Geometry.from_mesh(mesh))}
    return got["construction_on_its_face"]


def test_a_sheet_declared_at_its_mid_thickness_is_caught_and_named():
    r = _result(_declared(100 - T / 2), _seat_on_a_post())
    assert r.status == "fail" and not r.passed
    assert r.detail.startswith("seat top: declared 9.5 mm above where the part has it")   # built upward from its middle
    assert "a face of the panel" in r.detail


def test_a_sheet_on_the_solid_s_surface_isn_t_flagged():
    assert _result(_declared(100), _seat_on_a_post()).passed


def test_the_lower_face_is_a_face_too():
    assert _result(_declared(100 - T), _seat_on_a_post()).passed


def test_a_sheet_built_down_from_its_middle_is_said_to_be_below():
    """The stool: the outline at mid-thickness, its thickness going down into the cone, the top of the seat left over."""
    mesh = _seat_on_a_post()
    pcs = consistency.shapes(_declared(100 - T / 2))
    consistency._sides(mesh, pcs)
    pcs[0]["sides"] = [-1.0]
    r = consistency._on_its_face(mesh, pcs, consistency.tolerance(mesh))
    assert r.status == "fail" and r.detail.startswith("seat top: declared 9.5 mm below where the part has it")


def _side(x):
    return {"construction": [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": T,
                              "outline": [(x, -150, -150), (x, 150, -150), (x, 150, 150), (x, -150, 150)]}]}


def test_a_sideways_sheet_says_off_not_below():
    wall = trimesh.creation.box((T, 300, 300))
    assert _result(_side(T / 2), wall).passed
    assert "9.5 mm off where the part has it" in _result(_side(0.0), wall).detail


def test_a_sheet_stacked_on_another_declared_sheet_isn_t_flagged():
    two = trimesh.creation.box((300, 300, 2 * T))
    two.apply_translation((0, 0, 100 - T))
    declared = {"construction": [
        {"name": "lower", "kind": "sheet", "material": "plywood", "thickness": T, "outline": _outline(100 - 2 * T)},
        {"name": "upper", "kind": "sheet", "material": "plywood", "thickness": T, "outline": _outline(100)}]}
    assert _result(declared, two).passed


def test_solid_beyond_an_outline_that_is_another_declared_sheet_isn_t_flagged():
    """Two sheets glued face to face, each outlined at the joint: what's beyond each outline is the other sheet."""
    two = trimesh.creation.box((300, 300, 2 * T))
    two.apply_translation((0, 0, 100 - T))
    pcs = consistency.shapes({"construction": [
        {"name": "lower", "kind": "sheet", "material": "plywood", "thickness": T, "outline": _outline(100 - T)},
        {"name": "upper", "kind": "sheet", "material": "plywood", "thickness": T, "outline": _outline(100 - T)}]})
    consistency._sides(two, pcs)
    pcs[0]["sides"], pcs[1]["sides"] = [-1.0], [1.0]
    assert consistency._on_its_face(two, pcs, consistency.tolerance(two)).passed


def test_a_small_offset_is_tessellation_not_a_mistake():
    assert _result(_declared(100 - 1.0), _seat_on_a_post()).passed


@pytest.mark.parametrize("name", ["step-stool", "camper"])
def test_the_samples_raise_no_false_alarm(name, tmp_path):
    """Their sheets are drawn the way the guide says."""
    import os
    import shutil

    from caliper import construction as C
    from caliper.design import DesignStore

    source = os.path.join(os.path.dirname(C.__file__), "samples", name)
    root = str(tmp_path / name)
    shutil.copytree(source, root)
    store = DesignStore.load(root)
    bad = []
    for part in store.design.parts:
        if not store.is_scripted(part.id):
            continue
        for r in consistency.check(C.declared(store, part.id), store.part_geometry(part.id)):
            if r.id == "construction_on_its_face" and not r.passed:
                bad.append((part.id, r.detail))
    assert not bad, bad


def test_the_guide_says_it_once():
    import os

    from caliper import construction as C

    text = open(os.path.join(os.path.dirname(C.__file__), "part_scripts.md")).read()
    assert "never its mid-plane" in text and "sits inside the solid or on its surface" not in text


def test_a_columns_outward_run_stops_at_the_surface():
    mesh = trimesh.creation.box((100, 100, 10))
    got = consistency._proud(mesh, np.array([[0.0, 0.0, 0.0]]), np.array([0.0, 0.0, 1.0]), 12.0)
    assert got[0] == pytest.approx(5.0, abs=0.6)


# --- #170 review ------------------------------------------------------------------------------------------------------
def _blocks(thick_below=40.0, thick_above=40.0):
    """A panel between two printed blocks, or set against one: solid runs on past the panel's faces."""
    solid = trimesh.creation.box((300, 300, thick_below + T + thick_above))
    solid.apply_translation((0, 0, (thick_below + T + thick_above) / 2 - thick_below))
    return solid


@pytest.mark.parametrize("z", [0.0, T])
def test_a_panel_between_printed_blocks_isn_t_flagged_on_either_face(z):
    r = _result(_declared(z), _blocks())
    assert r.passed, r.detail


def test_an_outline_on_its_joint_face_with_a_block_on_it_isn_t_flagged():
    assert _result(_declared(T), _blocks(thick_below=0.0, thick_above=T)).passed


def _ring(r_out, wall=6.0, h=100.0, sections=128):
    return trimesh.creation.annulus(r_out - wall, r_out, h, sections=sections)


def _facets(r, n, h=100.0):
    at = [(r * np.cos(2 * np.pi * i / n), r * np.sin(2 * np.pi * i / n)) for i in range(n + 1)]
    return [[(at[i][0], at[i][1], -h / 2 + 2), (at[i + 1][0], at[i + 1][1], -h / 2 + 2),
             (at[i + 1][0], at[i + 1][1], h / 2 - 2), (at[i][0], at[i][1], h / 2 - 2)] for i in range(n)]


def _bent(r, n=12):
    return {"construction": [{"name": "skin", "kind": "sheet", "material": "plywood", "thickness": 6.0, "facets": _facets(r, n)}]}


@pytest.mark.parametrize("n", [12, 16])
def test_coarse_facets_on_a_bent_panel_s_outer_face_aren_t_flagged(n):
    """A facet is a chord: 5 mm inside the curve at its middle, on it at its edges."""
    r = _result(_bent(150.0, n), _ring(150.0))
    assert r.passed, r.detail


def test_a_bent_panel_declared_at_mid_thickness_is_still_caught():
    r = _result(_bent(146.0, 48), _ring(150.0, wall=8.0))
    assert not r.passed and "skin: declared" in r.detail


def test_a_minority_overhang_isn_t_flagged():
    """A raised step on a third of the panel: under half of it has solid left over."""
    seat = trimesh.creation.box((300, 300, T))
    seat.apply_translation((0, 0, 100 - T / 2))
    step = trimesh.creation.box((100, 300, 8))
    step.apply_translation((-100, 0, 104))
    assert _result(_declared(100), trimesh.util.concatenate([seat, step])).passed


@pytest.mark.parametrize("detail,said", [
    ("seat top: declared 9.5 mm below where the part has it: an outline…", "move the seat top's outline up to its top face"),
    ("seat top: declared 9.5 mm above where the part has it: …", "move the seat top's outline down to its underside"),
    ("side: declared 3.0 mm off where the part has it: …", "move the side's outline onto its face"),
    ("something else", "move each sheet's outline onto its face"),
])
def test_what_to_say_moves_the_outline_not_the_shape(detail, said):
    assert consistency.remedy(detail) == said


def test_the_card_points_at_the_declared_piece(tmp_path):
    from caliper import answers, consistency

    detail = "the seat's outline is at its mid-plane"              # the card's fix for a piece off its face is its own
    assert answers.fix_for("construction_on_its_face", detail, "stool") == f'Say "{consistency.remedy(detail)}"'
