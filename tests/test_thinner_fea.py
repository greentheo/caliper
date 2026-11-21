"""CALI-214 (#357): Lighten's thinner rows scale the FEA's worst as a panel in bending, t^2.

The FEA's number is the part's worst, wherever it is. A wall in compression goes as t, but a panel stood on goes as t^2.
The rows scaled it by t alone, so where the worst was a panel in bending, a thinner sheet's estimate read high. Now
t^2, the safe side: the estimates only move down."""

import pytest

from caliper import lighten

from .test_lighten_own_material import _row, _two_stocks


def test_the_fea_s_worst_scales_as_a_panel_in_bending(monkeypatch):
    """A plate-governed case (its plate clear, at 50) whose FEA worst is 8.0: at 1 1/2 in the FEA's estimate governs,
    8.0 x 0.75^2 = 4.5, where t alone said 6.0."""
    monkeypatch.setattr(lighten, "_plate_at", lambda ctx, name, t, thick=None: 50.0)
    rows, _, _ = _two_stocks({"name": "n", "safety": 8.0, "governs": "plate", "fea_safety": 8.0}, {})
    assert _row(rows, 38.1)["safety"] == pytest.approx(8.0 * 0.75 ** 2, abs=0.1)      # 4.5, not 6.0
    assert _row(rows, 25.4)["safety"] == pytest.approx(8.0 * 0.5 ** 2, abs=0.1)       # 2.0, not 4.0
