"""CALI-3 — evaluator: expression parsing, margins, deferral, and end-to-end on a box."""

import math
from types import SimpleNamespace

from caliper import evaluate
from caliper.evaluate import safe_eval
from caliper.spec import Assertion, Reference, Spec


def _ctx(**over):
    base = {
        "bbox": SimpleNamespace(dx=100, dy=50, dz=30),
        "machine": SimpleNamespace(nozzle=0.4),
        "min_wall": 2.1,
        "body_count": 1,
        "is_watertight": True,
        "mass": lambda density: 47.0,
    }
    base.update(over)
    return base


def test_safe_eval_compound_and():
    assert safe_eval("bbox.dx <= 220 and bbox.dy <= 220 and bbox.dz <= 250", _ctx()) is True


def test_safe_eval_rejects_unknown_name():
    import pytest

    with pytest.raises(Exception):
        safe_eval("os.system('x')", _ctx())


def test_margin_for_le_comparison():
    r = evaluate.evaluate_assertion(Assertion(id="mass", expr="mass(density=1.24) <= 80"), _ctx())
    assert r.status == "pass"
    assert math.isclose(r.margin, 33.0, abs_tol=1e-6)  # 80 - 47
    assert math.isclose(r.actual, 47.0, abs_tol=1e-6)


def test_margin_for_ge_comparison():
    r = evaluate.evaluate_assertion(
        Assertion(id="walls", expr="min_wall >= 2 * machine.nozzle"), _ctx()
    )
    assert r.status == "pass"
    assert math.isclose(r.margin, 1.3, abs_tol=1e-6)  # 2.1 - 0.8


def test_failing_assertion_has_negative_margin():
    r = evaluate.evaluate_assertion(
        Assertion(id="mass", expr="mass(density=1.24) <= 40"), _ctx(mass=lambda density: 47.0)
    )
    assert r.status == "fail"
    assert r.margin < 0


def test_deferred_probe_marked_not_failed():
    ctx = _ctx(ref=SimpleNamespace(id="ref"),
               interference=lambda ref: (_ for _ in ()).throw(NotImplementedError("M3")))
    r = evaluate.evaluate_assertion(Assertion(id="coll", expr="interference(ref) == 0"), ctx)
    assert r.status == "deferred"
    assert r.passed is None


def test_end_to_end_on_box(box_geom):
    spec = Spec(
        part="block",
        references=[Reference(id="ref", file="x.stl")],
        assertions=[
            Assertion(id="fits_bed", expr="bbox.dx <= 220 and bbox.dy <= 220 and bbox.dz <= 250"),
            Assertion(id="mass_budget", expr="mass(density=1.24) <= 80"),
            Assertion(id="one_body", expr="body_count == 1 and is_watertight"),
            Assertion(id="walls", expr="min_wall >= 2 * machine.nozzle"),
            Assertion(id="no_collision", expr="interference(ref) == 0"),
        ],
    )
    report = evaluate.evaluate(spec, box_geom(10, 20, 30))
    by_id = {r.id: r for r in report.results}
    assert by_id["fits_bed"].status == "pass"
    assert by_id["mass_budget"].status == "pass"
    assert by_id["one_body"].status == "pass"
    assert by_id["walls"].status == "pass"
    assert by_id["no_collision"].status == "deferred"  # interference is M3
    assert report.all_pass is True  # deferred excluded from the verdict
    assert "ALL PASS" in report.to_text()
