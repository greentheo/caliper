"""CALI-10 — references / fit: interference + min_clearance probes and the fit loop.

Mesh-only (no CadQuery) so the regression guard stays fast: two boxes stand in for a part and an
imported reference. The fit loop is exercised with a synthetic eval_fn that models clearance as a
function of one continuous parameter, mirroring how shrinking the part clears a reference.
"""

import math

import pytest
import trimesh

from caliper import decide, evaluate, loop, measure
from caliper.evaluate import load_references
from caliper.measure import Geometry
from caliper.spec import Assertion, Reference, Spec


def _box(dx=10.0, dy=10.0, dz=10.0, at=(0.0, 0.0, 0.0)) -> Geometry:
    m = trimesh.creation.box(extents=(dx, dy, dz))
    m.apply_translation(list(at))
    return Geometry.from_mesh(m)


# --- measurements ----------------------------------------------------------
def test_interference_zero_when_disjoint():
    part = _box(at=(0, 0, 0))
    ref = _box(at=(20, 0, 0))  # 10mm gap, no overlap
    assert measure.interference(part, ref) == 0.0


def test_interference_volume_when_overlapping():
    part = _box(at=(0, 0, 0))         # x in [-5, 5]
    ref = _box(at=(8, 0, 0))          # x in [3, 13] → overlap x in [3,5] = 2*10*10 = 200
    vol = measure.interference(part, ref)
    assert math.isclose(vol, 200.0, rel_tol=0.05)


def test_min_clearance_positive_gap_when_disjoint():
    part = _box(at=(0, 0, 0))         # x max = 5
    ref = _box(at=(20, 0, 0))         # x min = 15 → gap 10
    assert math.isclose(measure.min_clearance(part, ref), 10.0, abs_tol=0.5)


def test_min_clearance_negative_when_interpenetrating():
    part = _box(at=(0, 0, 0))
    ref = _box(at=(8, 0, 0))          # overlapping
    assert measure.min_clearance(part, ref) < 0.0


def test_as_mesh_accepts_geometry_and_mesh_rejects_handle():
    g = _box()
    assert measure._as_mesh(g) is g.require_mesh()
    raw = trimesh.creation.box(extents=(1, 1, 1))
    assert measure._as_mesh(raw) is raw
    from types import SimpleNamespace

    with pytest.raises(ValueError):
        measure._as_mesh(SimpleNamespace(id="ref", file="x.stl"))


# --- evaluator binding -----------------------------------------------------
def _fit_spec():
    return Spec(
        part="block",
        references=[Reference(id="obstacle", file="obstacle.stl")],
        assertions=[
            Assertion(id="obstacle_no_interference", expr="interference(obstacle) <= 0"),
            Assertion(id="obstacle_clearance", expr="min_clearance(obstacle) >= 2.0"),
        ],
    )


def test_evaluate_passes_when_clear():
    part = _box(at=(0, 0, 0))                 # x max 5
    refs = {"obstacle": _box(at=(20, 0, 0))}  # gap 10 ≥ 2
    report = evaluate.evaluate(_fit_spec(), part, references=refs)
    assert report.all_pass
    assert {r.status for r in report.results} == {"pass"}


def test_evaluate_fails_when_colliding():
    part = _box(at=(0, 0, 0))
    refs = {"obstacle": _box(at=(8, 0, 0))}   # overlapping
    report = evaluate.evaluate(_fit_spec(), part, references=refs)
    by_id = {r.id: r for r in report.results}
    assert by_id["obstacle_no_interference"].status == "fail"
    assert by_id["obstacle_clearance"].status == "fail"
    assert not report.all_pass


def test_unloaded_reference_surfaces_error_not_silent_pass():
    # a referenced part with no loaded geometry must NOT silently pass a collision check.
    part = _box()
    report = evaluate.evaluate(_fit_spec(), part)  # no references dict
    assert any(r.status == "error" for r in report.results)
    assert not report.all_pass


def test_load_references_from_stl(tmp_path):
    path = tmp_path / "obstacle.stl"
    trimesh.creation.box(extents=(10, 20, 30)).export(str(path))
    spec = Spec(part="x", references=[Reference(id="obstacle", file=str(path))])
    refs = load_references(spec)
    bb = measure.bounding_box(refs["obstacle"])
    assert math.isclose(bb.dx, 10, abs_tol=1e-3)
    assert math.isclose(bb.dz, 30, abs_tol=1e-3)


# --- decide + loop fit routing --------------------------------------------
def _clearance_spec(init=60.0):
    # one continuous size param; clearance to an obstacle at x=50 is (50 - leg).
    return Spec(
        part="bracket",
        parameters={"bolt_circle": {"type": "continuous", "min": 30.0, "max": 70.0, "init": init}},
        references=[Reference(id="obs", file="obs.stl")],
        assertions=[Assertion(id="obs_clearance", expr="min_clearance(obs) >= 2.0")],
    )


def _clearance_eval(spec):
    from caliper.evaluate import AssertionResult, Report

    leg = spec.parameters["bolt_circle"].init
    clearance = 50.0 - leg
    margin = clearance - 2.0
    status = "pass" if margin >= 0 else "fail"
    return Report([AssertionResult("obs_clearance", "min_clearance(obs) >= 2.0", status,
                                   status == "pass", actual=clearance, margin=margin)])


def test_decide_routes_fit_failure_to_size_param():
    spec = _clearance_spec(init=60.0)  # clearance -10 → fails
    report = _clearance_eval(spec)
    dec = decide.decide(spec, report, _clearance_eval)
    assert dec.kind == "continuous"
    assert "bolt_circle" in dec.move
    assert dec.new_spec.parameters["bolt_circle"].init <= 48.0  # must shrink to clear
    assert _clearance_eval(dec.new_spec).all_pass


def test_fit_loop_converges():
    result = loop.run_loop(_clearance_spec(init=60.0), _clearance_eval, max_iter=6)
    assert result.status == "passed"
    assert result.report.all_pass
    assert result.spec.parameters["bolt_circle"].init <= 48.0


def test_fit_is_snug_not_collapsed():
    # snug fit: shrink just enough to clear (≤48 for the 2mm rule), NOT down to the 30mm floor.
    result = loop.run_loop(_clearance_spec(init=60.0), _clearance_eval, max_iter=6)
    leg = result.spec.parameters["bolt_circle"].init
    assert 40.0 <= leg <= 48.0


# --- CALI-19: fit classes (tunable clearance bands) -----------------------
def test_attach_reference_fit_class_emits_band():
    from caliper.fit import attach_reference

    spec = Spec(part="b", parameters={}, assertions=[])
    attach_reference(spec, "obs", "/abs/obs.stl", fit="slip")
    band = [a for a in spec.assertions if a.id == "obs_fit"]
    assert band and "<= min_clearance(obs) <=" in band[0].expr
    assert any(r.id == "obs" for r in spec.references)


def test_decide_is_band_detects_two_sided():
    from caliper.decide import _is_band

    assert _is_band("0.12 <= min_clearance(obs) <= 0.3")
    assert not _is_band("min_clearance(obs) >= 2")


def _band_spec(init=42.0):
    return Spec(
        part="bracket",
        parameters={"bolt_circle": {"type": "continuous", "min": 40.0, "max": 55.0, "init": init}},
        references=[Reference(id="obs", file="o.stl")],
        assertions=[Assertion(id="obs_fit", expr="0.12 <= min_clearance(obs) <= 0.3")],
    )


def _band_eval(spec):
    from caliper.evaluate import AssertionResult, Report

    leg = spec.parameters["bolt_circle"].init
    clearance = 50.0 - leg                       # obstacle at x=50
    margin = min(clearance - 0.12, 0.30 - clearance)   # two-sided band margin
    status = "pass" if margin >= 0 else "fail"
    return Report([AssertionResult("obs_fit", "0.12 <= min_clearance(obs) <= 0.3", status,
                                   status == "pass", actual=clearance, margin=margin)])


def test_fit_band_loop_lands_in_band():
    # the optimizer must tune the part until the clearance sits inside the (narrow) slip band.
    result = loop.run_loop(_band_spec(42.0), _band_eval, max_iter=6)
    assert result.status == "passed"
    clearance = 50.0 - result.spec.parameters["bolt_circle"].init
    assert 0.12 <= clearance <= 0.30
