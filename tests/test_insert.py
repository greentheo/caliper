"""CALI-21 — insert-into-assembly: author a part that mates to two named interfaces.

Mesh-only + injected author (no key, no kernel needed for the spec/geometry plumbing; the build path
uses cadquery and is guarded with importorskip). Two posts with a gap stand in for "the wheel and the
XYZ assembly"; the injected author returns a bar that bridges them at the target clearance.
"""

import pytest
import trimesh

from caliper import insert
from caliper.assembly import Assembly, Part
from caliper.insert import _bridge, add_part_to_assembly, insert_spec


def _write_box(path, extents):
    trimesh.creation.box(extents=extents).export(str(path))


def _two_posts(tmp_path):
    # posts 10x10x30 at x=±30 → faces at x=-25 and x=+25, a 50mm gap along x
    _write_box(tmp_path / "post.stl", (10, 10, 30))
    return Assembly(
        name="two-posts",
        parts=[
            Part(id="post_left", source="post.stl", role="fixed", position=[-30, 0, 0]),
            Part(id="post_right", source="post.stl", role="fixed", position=[30, 0, 0]),
        ],
        assertions=[{"id": "clean", "expr": "max_interference() <= 0"}],
    )


# --- bridge geometry -------------------------------------------------------
def test_bridge_picks_the_separation_axis(tmp_path):
    asm = _two_posts(tmp_path)
    parts = insert._asm.load_parts(asm, base_dir=str(tmp_path))
    from caliper import measure

    a = measure.bounding_box(parts["post_left"])
    b = measure.bounding_box(parts["post_right"])
    br = _bridge(a, b)
    assert br.axis == 0 and br.axis_name == "x"
    assert abs(br.gap - 50.0) < 0.1
    assert abs(br.face_a - (-25.0)) < 0.1 and abs(br.face_b - 25.0) < 0.1


# --- the insert spec -------------------------------------------------------
def test_insert_spec_has_fit_bands_and_posed_references(tmp_path):
    asm = _two_posts(tmp_path)
    spec, bridge = insert_spec(asm, ["post_left", "post_right"], fit="slip", new_id="bar",
                               base_dir=str(tmp_path))
    ref_ids = {r.id for r in spec.references}
    assert ref_ids == {"post_left", "post_right"}
    # the references carry the parts' poses so clearance is measured where they sit
    posed = {r.id: r.position for r in spec.references}
    assert posed["post_left"] == [-30, 0, 0] and posed["post_right"] == [30, 0, 0]
    band_ids = {a.id for a in spec.assertions}
    assert "mate_post_left" in band_ids and "mate_post_right" in band_ids
    assert any("<= min_clearance(post_left) <=" in a.expr for a in spec.assertions)
    assert any(a.id == "one_body" for a in spec.assertions)
    # the enriched intent tells the author where to build (world coords + the facing faces)
    assert "WORLD" in spec.intent
    assert "x=-25.00" in spec.intent and "x=25.00" in spec.intent


def test_insert_spec_adds_no_interference_for_other_parts(tmp_path):
    asm = _two_posts(tmp_path)
    asm.parts.append(Part(id="floor", source="post.stl", position=[0, 0, -40]))
    spec, _ = insert_spec(asm, ["post_left", "post_right"], new_id="bar", base_dir=str(tmp_path))
    assert any(a.id == "clear_floor" and "interference(floor) <= 0" in a.expr for a in spec.assertions)


def test_insert_spec_rejects_bad_interfaces(tmp_path):
    asm = _two_posts(tmp_path)
    with pytest.raises(ValueError):
        insert_spec(asm, ["post_left"], base_dir=str(tmp_path))            # not two
    with pytest.raises(ValueError):
        insert_spec(asm, ["post_left", "ghost"], base_dir=str(tmp_path))   # unknown
    with pytest.raises(ValueError):
        insert_spec(asm, ["post_left", "post_right"], new_id="post_left",  # id collision
                    base_dir=str(tmp_path))


# --- add the authored part back to the assembly ---------------------------
def test_add_part_to_assembly_adds_part_and_fit_mates(tmp_path):
    asm = _two_posts(tmp_path)
    new = add_part_to_assembly(asm, "crossbar", "/abs/runs/run_0001", ["post_left", "post_right"],
                               fit="slip")
    assert any(p.id == "crossbar" and p.source == "/abs/runs/run_0001" for p in new.parts)
    mates = {m.id: m for m in new.mates}
    assert mates["crossbar_post_left"].kind == "fit" and mates["crossbar_post_left"].fit == "slip"
    assert mates["crossbar_post_right"].between == ["crossbar", "post_right"]


# --- end-to-end with an injected author (real build + measure) ------------
def test_insert_part_authors_a_bridge_that_mates_both(tmp_path):
    pytest.importorskip("cadquery")
    asm = _two_posts(tmp_path)

    # a bar from x=-24.8 to x=+24.8 (≈0.2mm clearance to each post face at ±25), 10x10 cross-section
    bar = (
        "def build(params):\n"
        "    import cadquery as cq\n"
        "    return cq.Workplane('XY').box(49.6, 10, 10)\n"  # centered → x∈[-24.8, 24.8]
    )
    res = insert.insert_part(asm, ["post_left", "post_right"], fit="slip", new_id="crossbar",
                             author=lambda s, fb, prior: bar, max_rounds=2, base_dir=str(tmp_path))
    assert res.ok, res.report.to_text() if res.report else res.error
    assert res.report.all_pass
    by_id = {r.id: r for r in res.report.results}
    assert by_id["mate_post_left"].status == "pass" and by_id["mate_post_right"].status == "pass"
