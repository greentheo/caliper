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


def test_the_cases_are_made_safe_before_they_go_together(monkeypatch):
    """whittle's case threads take the process's BLAS default: solved() has blas.cases_safe settle it first (#346)."""
    from caliper import blas

    order = []
    monkeypatch.setattr(blas, "cases_safe", lambda: order.append("safe"))
    monkeypatch.setattr(_Each, "solve_each", lambda self, solid: order.append("each") or [None] * len(self.loads))
    L.solved(_ctx())
    assert order == ["safe", "each"]


def test_one_case_a_whittle_without_solve_each_or_too_many_at_once_go_alone(monkeypatch):
    """Alone is check_load's to solve, case by case, its solver let go before the next (#346): never all at once here."""
    assert L.solved(_ctx(n=1)) == [None] and _Plain.made == []
    assert L.solved(_ctx(each=False)) == [None] * 3
    assert [s.calls for s in _Plain.made] == [[]]                                   # made, found wanting, nothing solved
    _Plain.made = []
    monkeypatch.setattr(L, "TOGETHER_MAX", 11 ** 3 * 3 - 1)                        # one node short of three at once
    assert L.solved(_ctx()) == [None] * 3 and _Plain.made == []
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
    from whittle.physics.fea import VoxelFEA

    assert alone == ([] if hasattr(VoxelFEA, "solve_each") else [0, 1])   # exactly: never together and then alone too


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


# --- a holed panel's filled solve, and a Lighten step's cut (reviewer-2, on #346) ---------------------------------------

from .test_plate_held import RAILS  # noqa: E402

_ONE = ('''    return [{"name": "a mattress", "lb": 400, "factor": 2.0, "lo": (250, 150, T - 2), "hi": (350, 250, T)}]''')
#: #328's box on two rails, a 3/4 in floor stood on lightly in three places: the middle, its left end, its front edge.
#: It holds, so Lighten cuts it
THREE = (RAILS.replace("T, W, D, H, X = 9.525,", "T, W, D, H, X = 19.05,")
         .replace(_ONE, '''    return [{"name": "the middle", "lb": 10, "factor": 2.0, "lo": (250, 150, T - 2), "hi": (350, 250, T)},
            {"name": "its left end", "lb": 12, "factor": 2.0, "lo": (40, 150, T - 2), "hi": (140, 250, T)},
            {"name": "its front edge", "lb": 8, "factor": 2.0, "lo": (250, 20, T - 2), "hi": (350, 120, T)}]'''))
#: and a hole in the floor, clear of all three
HOLED = THREE + '''

HOLES = [{"piece": "floor", "normal": [0, 0, 1], "depth": 19.05,
          "polygons": [[[430, 150, 19.05], [500, 150, 19.05], [500, 250, 19.05], [430, 250, 19.05]]]}]
'''


def _box(tmp_path, src):
    from caliper.design import DesignStore

    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    store.write_part("box", src, intent="a foam box with a plywood floor, on two rails")
    return store


def _cases(rec):
    return [{k: v for k, v in c.items() if k not in ("seconds",)} for c in rec["cases"]]


def test_a_holed_panel_s_filled_solve_reads_its_own_case_as_main_does(tmp_path, monkeypatch):
    """The floor's hole is judged on a re-solve with the panel filled, of the load ``check_load`` left set. Handed its
    solve (``got``), it set none: the filled solve read every case at once (solve_each) or the last case (alone). Each
    case's numbers must be what they are with every case solved alone in ``check_load``, as main did."""
    pytest.importorskip("cadquery")
    assert THREE != RAILS and HOLED != THREE
    store = _box(tmp_path, HOLED)
    rec = L.study(store, "box")
    assert len(rec["cases"]) == 3 and any((c.get("plate") or {}).get("why", "").startswith("it has holes")
                                          for c in rec["cases"])            # the floor's hole was judged
    monkeypatch.setattr(L, "solved", lambda ctx, solid=None: [None] * len(ctx["loads"]))   # each alone, as on main
    assert _cases(L.study(store, "box")) == _cases(rec)


@pytest.mark.parametrize("held_at_once", [True, False])        # solve_each, where the whittle has it; every case alone
def test_each_lighten_step_s_cases_are_solved_on_its_cut_not_the_part(tmp_path, monkeypatch, held_at_once):
    pytest.importorskip("cadquery")
    from caliper import lighten

    if not held_at_once:
        monkeypatch.setattr(L, "TOGETHER_MAX", 0)
    seen = []
    real = L.check_load

    def check(ctx, i, min_safety, solid=None, got=None):
        case, r = real(ctx, i, min_safety, solid, got=got)
        if solid is not None:
            seen.append((solid, r.solid, ctx["ls"].solid))
        return case, r

    monkeypatch.setattr(L, "check_load", check)
    lighten.study(_box(tmp_path, THREE), "box", min_safety=1.3, steps=(0.5,))
    cut = [(on, got) for on, got, part in seen if (part & ~on).any()]          # steps that took material out
    assert cut, "no Lighten step cut the part"
    assert all(not got[~on].any() for on, got in cut)                          # solved on the cut, nothing it took out


def test_the_progress_line_says_together_only_where_they_are(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    from whittle.physics.fea import VoxelFEA

    store = _box(tmp_path, THREE)
    said = []
    L.study(store, "box", emit=lambda k, t="", **d: said.append(t))
    assert ("3 cases, solved together" in said) == hasattr(VoxelFEA, "solve_each")
    monkeypatch.setattr(L, "TOGETHER_MAX", 0)
    said.clear()
    L.study(store, "box", emit=lambda k, t="", **d: said.append(t))
    assert not any("together" in t for t in said)
    store.write_part("box", RAILS, intent="one case")
    said.clear()
    monkeypatch.undo()
    L.study(store, "box", emit=lambda k, t="", **d: said.append(t))
    assert not any("together" in t for t in said)


def test_the_joints_of_every_case_read_as_each_alone(tmp_path, monkeypatch):
    """#344 reads each joint's force off the solver, less the load applied there. On the one solver of every case
    (solve_each) the load is that case's row of its forces, not the first's: every case's joints read as they do with
    each case on its own solver."""
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    from .test_posts import LEGGED

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    rec = L.study(store, "stool")
    assert len(rec["cases"]) == 2 and all(c.get("joints") for c in rec["cases"])
    monkeypatch.setattr(L, "solved", lambda ctx, solid=None: [None] * len(ctx["loads"]))   # each alone
    assert _cases(L.study(store, "stool")) == _cases(rec)
