"""CALI-4 — generator: the corner-bracket family builds, is watertight, has the right holes."""

import os

import pytest

from caliper import measure
from caliper.spec import Spec

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "corner_bracket.yaml")

# The whole module needs the CadQuery kernel.
pytest.importorskip("cadquery")

from caliper import generate  # noqa: E402  (after importorskip)


def test_default_bracket_builds_watertight():
    res = generate.build(Spec(part="bracket"))
    assert res.build_ok, res.error
    g = res.geometry
    assert measure.is_watertight(g)
    assert measure.body_count(g) == 1


def test_default_bracket_has_four_m5_holes():
    res = generate.build(Spec(part="bracket"))
    assert res.build_ok, res.error
    hs = measure.holes(res.geometry)
    m5 = [h for h in hs if abs(h.diameter - 5.2) <= 0.3]
    assert len(m5) == 4
    assert measure.holes_matching(res.geometry, diameter=5.2, count=4)


def test_builds_from_worked_example_spec():
    spec = Spec.load(FIXTURE)
    res = generate.build(spec)
    assert res.build_ok, res.error
    # spec sets wall=3, bolt_circle=60 → thickness 3, leg 60
    assert res.params.thickness == 3
    assert res.params.leg == 60
    bb = measure.bounding_box(res.geometry)
    # L-bracket spans ~leg in x and z
    assert 55 <= bb.dx <= 65
    assert 55 <= bb.dz <= 65


def test_cable_bore_adds_a_larger_bore():
    # cable_bore=10 from the worked example → a Ø10 bore present in addition to the M5 holes
    spec = Spec.load(FIXTURE)
    res = generate.build(spec)
    assert res.build_ok, res.error
    assert measure.largest_through_bore(res.geometry) >= 9.0


def test_build_error_is_captured_not_raised(monkeypatch):
    # Force the kernel call to blow up; build() must return a structured error, not raise.
    monkeypatch.setattr(
        generate, "make_bracket", lambda p: (_ for _ in ()).throw(RuntimeError("kernel boom"))
    )
    res = generate.build(Spec(part="bracket"))
    assert res.build_ok is False
    assert "kernel boom" in res.error
