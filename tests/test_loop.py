"""CALI-6 — loop controller: converges, caps, detects oscillation, surfaces build failures."""

from caliper import loop
from caliper.evaluate import AssertionResult, Report
from caliper.spec import Assertion, Spec


def _spec(wall_init=3.0):
    return Spec(
        part="bracket",
        parameters={"wall": {"type": "continuous", "min": 2.4, "max": 6, "init": wall_init}},
        assertions=[Assertion(id="mass_budget", expr="mass<=50")],
    )


def _converging_eval(spec):
    wall = spec.parameters["wall"].init
    mass = wall * 20.0
    status = "pass" if mass <= 50.0 else "fail"
    return Report([AssertionResult("mass_budget", "mass<=50", status, status == "pass",
                                   actual=mass, margin=50.0 - mass)])


def _stuck_eval(spec):
    # mass never satisfies the budget no matter the wall → the loop must give up, not spin forever.
    return Report([AssertionResult("mass_budget", "mass<=50", "fail", False, actual=100.0, margin=-50.0)])


def test_loop_converges_to_pass():
    result = loop.run_loop(_spec(3.0), _converging_eval, max_iter=6)
    assert result.status == "passed"
    assert result.report.all_pass
    assert result.spec.parameters["wall"].init < 3.0


def test_loop_gives_up_on_non_converging_case():
    result = loop.run_loop(_spec(3.0), _stuck_eval, max_iter=6)
    assert result.status != "passed"
    assert result.status in ("oscillation", "capped", "stuck")
    assert result.iterations <= 6


def test_loop_surfaces_build_failure():
    def _build_fails(spec):
        return Report([AssertionResult("build", "kernel build", "error", None, detail="boom")])

    result = loop.run_loop(_spec(), _build_fails, max_iter=6)
    assert result.status == "build_failed"


def test_persist_run_writes_artifacts(tmp_path):
    spec = _spec()
    report = _converging_eval(spec)
    out = loop.persist_run(str(tmp_path / "run0"), spec, report)
    import os

    assert os.path.exists(os.path.join(out, "spec.yaml"))
    assert os.path.exists(os.path.join(out, "report.txt"))
