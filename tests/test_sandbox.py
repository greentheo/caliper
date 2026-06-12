"""CALI-16 — the sandbox runner: execute authored CadQuery scripts in a subprocess (needs OCCT)."""

import pytest

pytest.importorskip("cadquery")

from caliper import measure, sandbox  # noqa: E402

GOOD = """
def build(params):
    import cadquery as cq
    w, h, t, d = params.get("w", 40), params.get("h", 30), params.get("t", 4), params.get("hole", 8)
    return cq.Workplane("XY").box(w, h, t).faces(">Z").workplane().hole(d)
"""


def test_runs_good_script_and_measures():
    r = sandbox.run_script(GOOD, {"w": 50, "h": 30, "t": 4, "hole": 10})
    assert r.ok and r.geometry is not None
    bb = measure.bounding_box(r.geometry)
    assert round(bb.dx) == 50 and round(bb.dy) == 30
    # STEP round-trip keeps the B-rep → the exact hole probe still works on an authored part
    assert any(abs(h.diameter - 10) < 0.3 for h in measure.holes(r.geometry))
    assert measure.is_watertight(r.geometry)


def test_build_error_is_structured_not_a_crash():
    r = sandbox.run_script("def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(1, 1)\n", {})
    assert not r.ok
    assert "TypeError" in r.error
    assert r.traceback and r.feedback


def test_missing_build_contract():
    r = sandbox.run_script("x = 1\n", {})
    assert not r.ok and "build(params)" in r.error


def test_returns_none_is_caught():
    r = sandbox.run_script("def build(params):\n    return None\n", {})
    assert not r.ok and "None" in r.error


def test_timeout_kills_runaway_script():
    r = sandbox.run_script("def build(params):\n    while True:\n        pass\n", {}, timeout=3)
    assert not r.ok and "timed out" in r.error
