"""CALI-207 (#345): a check's cases, and a Lighten step's, solved on one solver, the set-up built once.

Theo asked for the Lighten speed-up. 44% of a Lighten of step-stool-5 was the multigrid hierarchy, rebuilt for every
case of every step. whittle's ``solve_each`` (greentheo/whittle#9) builds it once and gives each case bit for bit what a
solver of that case alone gives. ``load_study.solved`` uses it where the whittle has it, and holds the cases at once only
under ``TOGETHER_MAX``; otherwise each case is solved alone, as before."""

import numpy as np
import pytest

from caliper import load_study as L


class _Plain:
    """A stand-in for a whittle before solve_each: what it was asked, and which call."""

    made = []

    def __init__(self, loads):
        self.loads = list(loads)
        self.calls = []
        _Plain.made.append(self)

    def solve(self, solid):
        self.calls.append("solve")
        return ("alone", self.loads[0].force)


class _Each(_Plain):
    """And with it."""

    def solve_each(self, solid):
        self.calls.append("each")
        return [("each", ld.force, ld.case) for ld in self.loads]


class _Study:
    def __init__(self, shape=(10, 10, 10), each=True):
        self.grid = type("G", (), {"shape": shape})()
        self.solid = np.ones(shape, bool)
        self.loads = []
        self.each = each

    def region(self, box):
        return ("region", tuple(box[0]))

    def load(self, force, box):
        from whittle import Load

        self.loads.append(Load(np.ones(self.grid.shape, bool), force))

    def solver(self):
        return (_Each if self.each else _Plain)(self.loads)


def _ctx(n=3, shape=(10, 10, 10), each=True):
    loads = [{"force": (0.0, 0.0, -100.0 * (i + 1)), "factor": 2.0} for i in range(n)]
    boxes = [((i, 0, 0), (i + 1, 1, 1)) for i in range(n)]
    return {"ls": _Study(shape, each), "loads": loads, "boxes": boxes}


@pytest.fixture(autouse=True)
def _fresh():
    pytest.importorskip("whittle")
    _Plain.made = []


def test_a_check_s_cases_go_to_one_solver_each_at_its_case():
    got = L.solved(_ctx())
    assert len(_Plain.made) == 1 and _Plain.made[0].calls == ["each"]
    assert [r for _, r in got] == [("each", (0.0, 0.0, -200.0), 0), ("each", (0.0, 0.0, -400.0), 1),
                                   ("each", (0.0, 0.0, -600.0), 2)]                # each case's load, its factor in
    assert all(s is _Plain.made[0] for s, _ in got)


def test_one_case_a_whittle_without_solve_each_or_too_many_at_once_go_alone(monkeypatch):
    L.solved(_ctx(n=1))
    assert [s.calls for s in _Plain.made] == [["solve"]]
    _Plain.made = []
    L.solved(_ctx(each=False))
    assert [s.calls for s in _Plain.made] == [[], ["solve"], ["solve"], ["solve"]]   # made, found wanting, then alone
    _Plain.made = []
    monkeypatch.setattr(L, "TOGETHER_MAX", 11 ** 3 * 3 - 1)                        # one node short of three at once
    L.solved(_ctx())
    assert [s.calls for s in _Plain.made] == [["solve"], ["solve"], ["solve"]]
    monkeypatch.setattr(L, "TOGETHER_MAX", 11 ** 3 * 3)
    _Plain.made = []
    L.solved(_ctx())
    assert [s.calls for s in _Plain.made] == [["each"]]


# --- the study and Lighten call it, once a check and once a step -------------------------------------------------------

def _count(monkeypatch):
    calls = []
    real = L.solved

    def counted(ctx, solid=None):
        out = real(ctx, solid)
        calls.append(len(out))
        return out

    monkeypatch.setattr(L, "solved", counted)
    return calls


def test_the_strength_check_solves_its_cases_once_together(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    from .test_posts import LEGGED

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    calls = _count(monkeypatch)
    alone = []
    real = L._alone
    monkeypatch.setattr(L, "_alone", lambda *a: alone.append(a[1]) or real(*a))
    rec = L.study(store, "stool")
    assert calls == [2] and len(rec["cases"]) == 2
    assert alone in ([], [0, 1])                           # none with solve_each; both alone with a whittle without


def test_lighten_solves_each_step_s_cases_once(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    from caliper import lighten
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box stool")
    calls = _count(monkeypatch)
    alone = []
    real = L._alone
    monkeypatch.setattr(L, "_alone", lambda *a: alone.append(a[1]) or real(*a))
    lighten.study(store, "stool", min_safety=1.3, steps=(0.5,))
    assert len(calls) >= 2 and all(n == 1 for n in calls)   # once a step it checks, with BOX_STOOL's one case
    assert len(alone) == sum(calls)                         # its one case solved there, never again by check_load


# --- bit for bit, where the whittle has solve_each ---------------------------------------------------------------------

def test_every_case_together_is_bit_for_bit_each_alone(tmp_path):
    pytest.importorskip("cadquery")
    from whittle.physics.fea import VoxelFEA

    if not hasattr(VoxelFEA, "solve_each"):
        pytest.skip("this whittle has no solve_each (before greentheo/whittle#9)")
    from caliper.design import DesignStore

    from .test_posts import LEGGED

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    ctx = L.prepare(store, "stool")
    together = [r for _, r in L.solved(ctx)]
    alone = [L._alone(ctx, i, ctx["ls"].solid)[1] for i in range(len(ctx["loads"]))]
    assert len(together) == len(alone) == 2
    for a, b in zip(together, alone):
        for f in ("displacement", "von_mises", "strain_energy", "solid"):
            assert np.array_equal(getattr(a, f), getattr(b, f)), f
        for f in ("supported", "compliance", "peak_stress", "max_displacement", "converged", "iterations"):
            assert getattr(a, f) == getattr(b, f), f
