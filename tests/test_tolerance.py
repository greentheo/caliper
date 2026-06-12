"""CALI-19 — fits & tolerances: fit-class bands, tolerant helpers, two-sided margins."""

import math

import pytest

from caliper import evaluate, tolerance
from caliper.spec import Assertion


def test_fit_band_classes_and_aliases():
    assert tolerance.fit_band("slip") == (0.12, 0.30)
    assert tolerance.fit_band("press")[0] < 0          # interference band dips negative
    assert tolerance.fit_band("clearance") == tolerance.fit_band("slip")   # alias
    assert tolerance.fit_band("interference") == tolerance.fit_band("press")
    with pytest.raises(ValueError):
        tolerance.fit_band("nonsense")


def test_fit_band_widens_for_large_nominal():
    lo0, hi0 = tolerance.fit_band("slip")
    lo1, hi1 = tolerance.fit_band("slip", nominal=150)
    assert hi1 > hi0  # bigger mating size → a touch more clearance


def test_tolerant_helpers():
    assert tolerance.approx(2.99, 3.0, tol=0.05) is True
    assert tolerance.approx(2.8, 3.0, tol=0.05) is False
    assert tolerance.within(0.2, 0.1, 0.3) is True
    assert tolerance.fits(0.2, "slip") is True
    assert tolerance.fits(0.5, "slip") is False


# --- evaluator: two-sided band margin (the thing that makes a fit tunable) -----------------
def _ctx(x):
    return {"x": x, "approx": tolerance.approx, "within": tolerance.within, "fits": tolerance.fits}


def test_band_margin_is_distance_to_nearest_bound():
    r = evaluate.evaluate_assertion(Assertion(id="band", expr="10 <= x <= 20"), _ctx(12))
    assert r.status == "pass"
    assert math.isclose(r.actual, 12) and math.isclose(r.margin, 2.0)   # min(12-10, 20-12)=2

    r2 = evaluate.evaluate_assertion(Assertion(id="band", expr="10 <= x <= 20"), _ctx(25))
    assert r2.status == "fail" and r2.margin < 0    # outside → negative


def test_descending_band_margin():
    r = evaluate.evaluate_assertion(Assertion(id="band", expr="20 >= x >= 10"), _ctx(18))
    assert r.status == "pass" and math.isclose(r.margin, 2.0)


def test_approx_absorbs_measurement_noise():
    # the exact CALI-17 failure: min_wall 2.99 vs a hard 3.0 — approx makes it pass
    r = evaluate.evaluate_assertion(Assertion(id="wall", expr="approx(x, 3.0, 0.05)"), _ctx(2.99))
    assert r.status == "pass"
