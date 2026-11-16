"""CALI-187 (#298): the carve's sweep solves at a looser tolerance (whittle#8's ``LoadStudy.sweep(rtol=)``, 25e282e); each
station's own re-check, the number the carve's verdict reads, stays at whittle's default 1e-5. The sweep only ranks which
voxels to take away next; the station's check is what's said."""

import pytest

from caliper import carve

from .test_carve_closed import _carve
from .test_resolved import TUBE


def test_the_sweep_solves_at_1e_3_and_each_station_s_check_at_1e_5(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    from whittle.physics import fea as F
    from whittle.study import LoadStudy

    seen = {"phase": "check", "rtols": []}
    real_solve, real_sweep = F.VoxelFEA.solve, LoadStudy.sweep

    def solve(self, solid, *, rtol=1e-5, **kw):
        seen["rtols"].append((seen["phase"], rtol))
        return real_solve(self, solid, rtol=rtol, **kw)

    def sweep(self, *a, **kw):
        seen["phase"] = "sweep"
        try:
            return real_sweep(self, *a, **kw)
        finally:
            seen["phase"] = "stations"

    monkeypatch.setattr(F.VoxelFEA, "solve", solve)
    monkeypatch.setattr(LoadStudy, "sweep", sweep)
    store, rec = _carve(tmp_path, monkeypatch, TUBE, "tube", 3)
    assert rec["status"] == "done", rec.get("status")
    by = {ph: {r for p, r in seen["rtols"] if p == ph} for ph in ("sweep", "stations")}
    assert carve.SWEEP_RTOL == 1e-3 and by["sweep"] == {1e-3}, by           # every sweep solve, looser
    assert by["stations"] == {1e-5}, by                                     # every station's re-check, as before
    assert sum(1 for p, _ in seen["rtols"] if p == "stations") >= len(rec["stations"])
