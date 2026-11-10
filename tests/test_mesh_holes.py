"""CALI-90 (#66 item 5): on a part that's a mesh (carved, whittled, imported) there's no B-rep to find holes in.
holes_world and largest_through_bore returned [] and 0, so `largest_through_bore <= 5` passed on a carved part
with a 10 mm bore. They now say "not measured", and a rule on them reads as not checked, never a pass."""

import pytest
import trimesh

from caliper import measure
from caliper.evaluate import build_context, evaluate_assertion
from caliper.spec import Assertion, Spec
from caliper.measure import Geometry


@pytest.fixture
def mesh_part():
    return Geometry.from_mesh(trimesh.creation.box((20, 20, 20)))


def test_a_mesh_parts_holes_are_not_measured_not_none(mesh_part):
    with pytest.raises(measure.NotMeasured, match="not measured: the part is a mesh"):
        measure.holes_world(mesh_part)
    with pytest.raises(measure.NotMeasured, match="not measured"):
        measure.largest_through_bore(mesh_part)
    assert issubclass(measure.NotMeasured, NotImplementedError)       # the evaluator's "deferred"


@pytest.mark.parametrize("expr", ["largest_through_bore <= 5", "largest_through_bore >= 8"])
def test_a_rule_on_a_mesh_parts_bore_is_not_checked_never_a_pass(mesh_part, expr):
    ctx = build_context(Spec(part="x"), mesh_part)
    got = evaluate_assertion(Assertion(id="bore", expr=expr), ctx)
    assert got.status == "deferred" and not got.passed and "not measured" in (got.detail or ""), got


def test_a_b_rep_parts_bore_is_still_measured():
    import cadquery as cq

    g = Geometry.from_cadquery(cq.Workplane().box(20, 20, 20).faces(">Z").workplane().hole(10))
    assert measure.largest_through_bore(g) == pytest.approx(10, abs=0.01)
    got = evaluate_assertion(Assertion(id="bore", expr="largest_through_bore >= 8"), build_context(Spec(part="x"), g))
    assert got.status == "pass"
