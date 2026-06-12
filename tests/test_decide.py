"""CALI-7 — decide: the optimizer fixes a continuous failure; structural route bumps a discrete param."""

from caliper import decide
from caliper.evaluate import AssertionResult, Report
from caliper.spec import Assertion, Spec


def _spec(wall_init=3.0, with_rib=False):
    params = {"wall": {"type": "continuous", "min": 2.4, "max": 6, "init": wall_init, "unit": "mm"}}
    if with_rib:
        params["rib_count"] = {"type": "discrete", "choices": [0, 1, 2], "init": 0}
    return Spec(
        part="bracket",
        parameters=params,
        assertions=[Assertion(id="mass_budget", expr="mass(density=1.24) <= 50")],
    )


def _mass_eval(spec):
    """Closed-form stand-in for build+measure: mass is linear in wall thickness."""
    wall = spec.parameters["wall"].init
    mass = wall * 20.0  # wall 3 → 60 (fails vs 50); wall ≤ 2.5 → passes
    margin = 50.0 - mass
    status = "pass" if mass <= 50.0 else "fail"
    return Report([AssertionResult("mass_budget", "mass<=50", status, status == "pass",
                                   actual=mass, margin=margin)])


def test_optimizer_fixes_mass_over_budget():
    spec = _spec(3.0)
    report = _mass_eval(spec)
    assert report.failures  # over budget at init

    dec = decide.decide(spec, report, _mass_eval)
    assert dec.kind == "continuous"
    assert dec.new_spec.parameters["wall"].init < 3.0  # optimizer reduced the wall
    assert dec.projected_report.all_pass  # and it now passes
    assert "optimizer" in dec.move and "wall" in dec.move


def test_tune_continuous_respects_bounds():
    spec = _spec(6.0)
    value, _, _ = decide.tune_continuous(spec, "wall", "mass_budget", _mass_eval)
    assert 2.4 <= value <= 6.0


def test_structural_route_bumps_discrete_when_no_continuous_knob():
    # A failure with no continuous tuning mapping → structural move flips the discrete rib_count.
    spec = _spec(3.0, with_rib=True)
    report = Report([AssertionResult("one_body", "body_count==1", "fail", False, margin=None)])
    dec = decide.decide(spec, report, _mass_eval)
    assert dec.kind == "structural"
    assert dec.new_spec.parameters["rib_count"].init != 0


def test_no_move_defers_to_llm():
    spec = _spec(3.0)  # only a continuous param, but the failing assertion isn't numerically tunable
    report = Report([AssertionResult("one_body", "body_count==1", "fail", False, margin=None)])
    dec = decide.decide(spec, report, _mass_eval)
    assert dec.kind == "llm"
