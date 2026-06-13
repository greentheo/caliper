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


# --- CALI-19b: multi-parameter optimizer (coupled fits) --------------------
def _coupled_spec(w_init=20.0, d_init=20.0):
    # two knobs, two coupled checks: a gap band on (W+D) and a budget on (W*D). Feasible only with an
    # ASYMMETRIC pair (W=D drives the product over budget) — the case coordinate descent can't solve.
    return Spec(
        part="pocket",
        parameters={
            "W": {"type": "continuous", "min": 10.0, "max": 30.0, "init": w_init},
            "D": {"type": "continuous", "min": 10.0, "max": 30.0, "init": d_init},
        },
        assertions=[
            Assertion(id="gap", expr="0.0 <= 40 - W - D <= 0.5"),
            Assertion(id="budget", expr="W * D <= 380"),
        ],
    )


def _coupled_eval(spec):
    W = spec.parameters["W"].init
    D = spec.parameters["D"].init
    gap = 40.0 - W - D
    gmargin = min(gap - 0.0, 0.5 - gap)                 # two-sided band margin
    gstatus = "pass" if 0.0 <= gap <= 0.5 else "fail"
    mass = W * D
    mstatus = "pass" if mass <= 380.0 else "fail"
    return Report([
        AssertionResult("gap", "0.0 <= 40 - W - D <= 0.5", gstatus, gstatus == "pass",
                        actual=gap, margin=gmargin),
        AssertionResult("budget", "W * D <= 380", mstatus, mstatus == "pass",
                        actual=mass, margin=380.0 - mass),
    ])


def _assert_coupled_feasible(spec):
    W, D = spec.parameters["W"].init, spec.parameters["D"].init
    assert 0.0 <= 40.0 - W - D <= 0.5
    assert W * D <= 380.0


def test_tune_multi_solves_a_coupled_fit():
    # init (20,20): gap=0 ok-ish but product=400 > 380 → both can't hold without moving BOTH knobs.
    new_spec, rep = decide.tune_multi(_coupled_spec(), ["W", "D"], _coupled_eval)
    assert rep.all_pass
    _assert_coupled_feasible(new_spec)


def test_tune_multi_scipy_engine_solves_coupled_fit():
    new_spec, rep = decide.tune_multi(_coupled_spec(), ["W", "D"], _coupled_eval, engine="scipy")
    assert rep.all_pass
    _assert_coupled_feasible(new_spec)


def test_decide_routes_coupled_failures_to_multi():
    spec = _coupled_spec()
    report = _coupled_eval(spec)
    assert len(report.failures) >= 1  # product over budget at init
    dec = decide.decide(spec, report, _coupled_eval)
    assert dec.kind == "continuous" and "multi" in dec.move
    assert dec.projected_report.all_pass
    _assert_coupled_feasible(dec.new_spec)


def test_tune_multi_separable_stays_cheap_via_coordinate_descent(monkeypatch):
    # a SEPARABLE 2-knob problem must be solved by coordinate descent alone — scipy must NOT be invoked.
    import caliper.decide as d

    called = {"scipy": False}
    orig = d._scipy_tune_multi

    def spy(*a, **k):
        called["scipy"] = True
        return orig(*a, **k)

    monkeypatch.setattr(d, "_scipy_tune_multi", spy)

    spec = Spec(
        part="x",
        parameters={
            "a": {"type": "continuous", "min": 0.0, "max": 10.0, "init": 9.0},
            "b": {"type": "continuous", "min": 0.0, "max": 10.0, "init": 9.0},
        },
        assertions=[Assertion(id="a_ok", expr="a <= 5"), Assertion(id="b_ok", expr="b <= 5")],
    )

    def ev(s):
        a, b = s.parameters["a"].init, s.parameters["b"].init
        ra = AssertionResult("a_ok", "a<=5", "pass" if a <= 5 else "fail", a <= 5, actual=a, margin=5 - a)
        rb = AssertionResult("b_ok", "b<=5", "pass" if b <= 5 else "fail", b <= 5, actual=b, margin=5 - b)
        return Report([ra, rb])

    new_spec, rep = d.tune_multi(spec, ["a", "b"], ev)
    assert rep.all_pass and not called["scipy"]  # CD reached feasibility, no global search needed
