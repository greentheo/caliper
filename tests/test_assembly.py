"""CALI-20 — the assembly model: N parts + named mates + assembly-level assertions.

Mesh-only (no CadQuery) so the regression guard stays fast: small boxes stand in for parts. Covers
the data model (round-trip + validation), the N-body measurement helpers, mate → assertion
expansion, and the end-to-end evaluation of a posed assembly loaded from STL.
"""

import math

import pytest
import trimesh

from caliper import assembly, measure
from caliper.assembly import Assembly, Mate, Part, mate_assertion
from caliper.measure import Geometry


def _box(dx=10.0, dy=10.0, dz=10.0, at=(0.0, 0.0, 0.0)) -> Geometry:
    m = trimesh.creation.box(extents=(dx, dy, dz))
    m.apply_translation(list(at))
    return Geometry.from_mesh(m)


def _write_box(path, extents=(10, 10, 10)):
    trimesh.creation.box(extents=extents).export(str(path))


# --- N-body measurement helpers -------------------------------------------
def test_pairwise_interference_lists_every_pair():
    parts = {"a": _box(at=(0, 0, 0)), "b": _box(at=(20, 0, 0)), "c": _box(at=(40, 0, 0))}
    pairs = measure.pairwise_interference(parts)
    assert {(a, b) for a, b, _ in pairs} == {("a", "b"), ("a", "c"), ("b", "c")}
    assert all(v == 0.0 for _, _, v in pairs)  # all disjoint


def test_max_interference_picks_the_colliding_pair():
    parts = {"a": _box(at=(0, 0, 0)), "b": _box(at=(20, 0, 0)), "c": _box(at=(8, 0, 0))}  # a∩c overlap
    assert measure.max_interference(parts) > 100.0
    assert measure.max_interference({"only": _box()}) == 0.0  # <2 bodies → no collision


def test_min_pair_clearance_negative_when_a_pair_penetrates():
    clear = {"a": _box(at=(0, 0, 0)), "b": _box(at=(20, 0, 0))}
    assert measure.min_pair_clearance(clear) > 0.0
    overlap = {"a": _box(at=(0, 0, 0)), "b": _box(at=(8, 0, 0))}
    assert measure.min_pair_clearance(overlap) < 0.0


# --- model: round-trip + validation ---------------------------------------
def test_assembly_yaml_round_trip():
    asm = Assembly(
        name="stand",
        parts=[Part(id="base", source="base.stl", role="fixed"),
               Part(id="post", source="post.stl", position=[0, 0, 17])],
        mates=[Mate(id="m", between=["base", "post"], kind="touch")],
        assertions=[{"id": "clean", "expr": "max_interference() <= 0"}],
    )
    back = Assembly.from_yaml(asm.to_yaml())
    assert back.name == "stand"
    assert [p.id for p in back.parts] == ["base", "post"]
    assert back.parts[1].position == [0, 0, 17]
    assert back.mates[0].between == ["base", "post"]
    assert back.assertions[0].expr == "max_interference() <= 0"


def test_mate_requires_two_distinct_parts():
    with pytest.raises(ValueError):
        Mate(id="bad", between=["a"], kind="touch")
    with pytest.raises(ValueError):
        Mate(id="self", between=["a", "a"], kind="touch")


def test_assembly_rejects_mate_to_unknown_part():
    with pytest.raises(ValueError):
        Assembly(
            name="x",
            parts=[Part(id="a", source="a.stl")],
            mates=[Mate(id="m", between=["a", "ghost"], kind="touch")],
        )


def test_assembly_rejects_duplicate_part_id():
    with pytest.raises(ValueError):
        Assembly(name="x", parts=[Part(id="a", source="a.stl"), Part(id="a", source="b.stl")])


# --- mates → assertions ----------------------------------------------------
def test_mate_assertion_per_kind():
    assert mate_assertion(Mate(id="m", between=["a", "b"], kind="no_interference")).expr == \
        "interference(a, b) <= 0"
    assert mate_assertion(Mate(id="m", between=["a", "b"], kind="clearance", value=0.4)).expr == \
        "min_clearance(a, b) >= 0.4"
    touch = mate_assertion(Mate(id="m", between=["a", "b"], kind="touch")).expr
    assert touch == "-0.1 <= min_clearance(a, b) <= 0.1"
    fit = mate_assertion(Mate(id="m", between=["a", "b"], kind="fit", fit="slip")).expr
    assert "<= min_clearance(a, b) <=" in fit  # a tunable band


def test_derived_assertions_orders_mates_then_assembly():
    asm = Assembly(
        name="x",
        parts=[Part(id="a", source="a.stl"), Part(id="b", source="b.stl")],
        mates=[Mate(id="m1", between=["a", "b"], kind="no_interference")],
        assertions=[{"id": "a2", "expr": "max_interference() <= 0"}],
    )
    ids = [a.id for a in assembly.derived_assertions(asm)]
    assert ids == ["m1", "a2"]


# --- end-to-end evaluation (load posed STL parts) -------------------------
def test_evaluate_assembly_passes_for_a_clean_stack(tmp_path):
    _write_box(tmp_path / "base.stl", (40, 40, 4))
    _write_box(tmp_path / "post.stl", (10, 10, 30))
    asm = Assembly(
        name="stand",
        parts=[
            Part(id="base", source="base.stl", position=[0, 0, 0]),    # z -2..2
            Part(id="post", source="post.stl", position=[0, 0, 17]),   # z  2..32, bottom meets base top
        ],
        mates=[Mate(id="seated", between=["base", "post"], kind="touch")],
        assertions=[{"id": "clean", "expr": "max_interference() <= 0"}],
    )
    report = assembly.evaluate_assembly(asm, base_dir=str(tmp_path))
    assert report.all_pass
    assert {r.status for r in report.results} == {"pass"}


def test_evaluate_assembly_fails_when_parts_interpenetrate(tmp_path):
    _write_box(tmp_path / "a.stl", (20, 20, 20))
    _write_box(tmp_path / "b.stl", (20, 20, 20))
    asm = Assembly(
        name="clash",
        parts=[
            Part(id="a", source="a.stl", position=[0, 0, 0]),
            Part(id="b", source="b.stl", position=[8, 0, 0]),   # overlaps a
        ],
        mates=[Mate(id="no_clash", between=["a", "b"], kind="no_interference")],
        assertions=[{"id": "clean", "expr": "max_interference() <= 0"}],
    )
    report = assembly.evaluate_assembly(asm, base_dir=str(tmp_path))
    by_id = {r.id: r for r in report.results}
    assert by_id["no_clash"].status == "fail"
    assert by_id["clean"].status == "fail"
    assert not report.all_pass


def test_evaluate_assembly_fit_band_between_two_parts(tmp_path):
    # two posed parts with a ~1mm gap; a 'free' fit band (0.30..0.60) should fail (too loose),
    # demonstrating the band is measured as a two-sided margin between parts.
    _write_box(tmp_path / "a.stl", (10, 10, 10))
    _write_box(tmp_path / "b.stl", (10, 10, 10))
    asm = Assembly(
        name="gap",
        parts=[
            Part(id="a", source="a.stl", position=[0, 0, 0]),    # x -5..5
            Part(id="b", source="b.stl", position=[11, 0, 0]),   # x 6..16 → 1mm gap
        ],
        mates=[Mate(id="slipfit", between=["a", "b"], kind="fit", fit="free")],
    )
    report = assembly.evaluate_assembly(asm, base_dir=str(tmp_path))
    r = report.results[0]
    assert r.status == "fail"
    assert math.isclose(r.actual, 1.0, abs_tol=0.3)  # measured gap ≈ 1mm, outside the 0.30..0.60 band


def test_load_parts_bakes_the_pose(tmp_path):
    _write_box(tmp_path / "p.stl", (10, 10, 10))
    asm = Assembly(name="x", parts=[Part(id="p", source="p.stl", position=[100, 0, 0])])
    parts = assembly.load_parts(asm, base_dir=str(tmp_path))
    bb = measure.bounding_box(parts["p"])
    assert math.isclose((bb.min[0] + bb.max[0]) / 2, 100.0, abs_tol=1e-3)  # centered at x=100


# --- CALI-23: parts built from a CadQuery script + CALI-25 hole alignment --
def _plate_py(path, expr_translate="(0,0,0)", d=6):
    # a 40x40x8 plate with a central Z-hole, drilled then translated into place
    path.write_text(
        "def build(params):\n"
        "    import cadquery as cq\n"
        f"    return cq.Workplane('XY').box(40, 40, 8).faces('>Z').workplane().hole({d}).translate({expr_translate})\n"
    )
    return str(path)


def test_py_part_builds_with_brep_and_detects_holes(tmp_path):
    pytest.importorskip("cadquery")
    g = assembly._build_py_local(_plate_py(tmp_path / "plate.py"))
    assert g.solid is not None                      # CALI-23 keeps the B-rep
    hs = measure.holes_world(g)
    assert len(hs) >= 1 and abs(hs[0].diameter - 6) < 0.3


def test_hole_misalignment_zero_when_coaxial_grows_when_offset(tmp_path):
    pytest.importorskip("cadquery")
    a = assembly._build_py_local(_plate_py(tmp_path / "a.py", "(0,0,0)"))
    b0 = assembly._build_py_local(_plate_py(tmp_path / "b0.py", "(0,0,20)"))    # same XY, 20mm up
    b5 = assembly._build_py_local(_plate_py(tmp_path / "b5.py", "(5,0,20)"))    # offset 5mm in X
    assert measure.min_hole_misalignment(a, b0) < 0.2          # coaxial
    assert measure.min_hole_misalignment(a, b5) == pytest.approx(5.0, abs=0.3)  # offset measured


def test_hole_misalignment_deferred_without_holes(tmp_path):
    # a mesh-only part (no B-rep) can't expose holes → the probe defers, not silently passes
    _write_box(tmp_path / "p.stl", (10, 10, 10))
    asm = Assembly(
        name="x",
        parts=[Part(id="a", source="p.stl"), Part(id="b", source="p.stl", position=[20, 0, 0])],
        assertions=[{"id": "align", "expr": "hole_misalignment(a, b) <= 0.5"}],
    )
    report = assembly.evaluate_assembly(asm, base_dir=str(tmp_path))
    assert report.results[0].status == "deferred"


def test_evaluate_assembly_with_script_parts_and_hole_alignment(tmp_path):
    pytest.importorskip("cadquery")
    _plate_py(tmp_path / "bot.py", "(0,0,0)")        # z -4..4, hole at (0,0)
    _plate_py(tmp_path / "top.py", "(0,0,8)")        # z 4..12, hole at (0,0) — coaxial, just touching
    asm = Assembly(
        name="stack",
        parts=[Part(id="bot", source="bot.py"), Part(id="top", source="top.py")],
        assertions=[
            {"id": "aligned", "expr": "hole_misalignment(top, bot) <= 0.5"},
            {"id": "clean", "expr": "max_interference() <= 0"},
        ],
    )
    report = assembly.evaluate_assembly(asm, base_dir=str(tmp_path))
    by = {r.id: r for r in report.results}
    assert by["aligned"].status == "pass" and by["clean"].status == "pass"

    # offset the top plate's hole in X → the alignment assertion must now fail
    _plate_py(tmp_path / "top.py", "(6,0,8)")
    asm2 = Assembly(
        name="stack2",
        parts=[Part(id="bot", source="bot.py"), Part(id="top", source="top.py")],
        assertions=[{"id": "aligned", "expr": "hole_misalignment(top, bot) <= 0.5"}],
    )
    assert assembly.evaluate_assembly(asm2, base_dir=str(tmp_path)).results[0].status == "fail"
