"""CALI-234 (#398): a check and a Lighten stop between their steps, and Fix these before its check, writing no run.

#373's review: Stop it at 0:07, before any case, and a check ran all three cases and wrote a run. load_study.study and
lighten.study took ``stop`` and never called it; Fix these's one stop came before its check and didn't reach it. The
lines are night shift's files, agreed with them on #398: a check stops once voxelized, after its solve (the cases are
solved together), before each case, and before it writes its run; Lighten before each step and before its run; Fix these
before its check, and its check stops too. A stop leaves no run, and never a half-made folder."""
import os

import pytest

from caliper import fixing, lighten, load_study
from caliper.design import DesignStore
from caliper.jobs import Cancelled

from .test_load_study import BOX_STOOL

pytest.importorskip("whittle")


@pytest.fixture
def stool(tmp_path, monkeypatch):
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: quick, and the stop points are the same
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    return store


def _folders(store, runs_dir):
    root = runs_dir(store)
    return sorted(os.listdir(root)) if os.path.isdir(root) else []


def _stops_in(run):
    """How many times a whole run asks whether to stop."""
    n = []
    run(lambda: n.append(1))
    return len(n)


def _stop_at(k):
    calls = []

    def stop():
        calls.append(1)
        if len(calls) == k:
            raise Cancelled()
    return stop


def test_a_check_has_a_stop_after_voxelizing_after_its_solve_before_each_case_and_before_its_run(stool):
    cases = len(load_study.prepare(stool, "stool", lambda *a, **k: None)["loads"])
    n = _stops_in(lambda stop: load_study.study(stool, "stool", stop=stop))
    assert n >= 3 + cases, n                       # voxelized, solved, each case, written (one_at_a_time's turn too)


@pytest.mark.parametrize("where", ["first", "middle", "last"])
def test_a_check_stopped_at_any_step_writes_no_run_and_leaves_no_folder(stool, where):
    n = _stops_in(lambda stop: load_study.study(stool, "stool", stop=stop))
    before = _folders(stool, load_study.runs_dir)
    k = {"first": 1, "middle": max(1, n // 2), "last": n}[where]
    with pytest.raises(Cancelled):
        load_study.study(stool, "stool", stop=_stop_at(k))
    assert _folders(stool, load_study.runs_dir) == before and len(load_study.list_runs(stool, "stool")) == len(before)


@pytest.mark.parametrize("where", ["first", "last"])
def test_a_lighten_stopped_at_any_step_writes_no_run_and_leaves_no_folder(stool, where):
    run = lambda stop: lighten.study(stool, "stool", steps=(1.0,), stop=stop)
    n = _stops_in(run)
    assert n >= 3, n                                # before each step, and before its run
    before = _folders(stool, lighten.runs_dir)
    with pytest.raises(Cancelled):
        run(_stop_at(1 if where == "first" else n))
    assert _folders(stool, lighten.runs_dir) == before


def test_fix_these_stops_before_its_check_and_its_check_is_given_the_stop(stool, monkeypatch):
    seen = {}

    def check(store, pid, **kw):
        seen.update(kw)
        kw["stop"]()
        return {}

    monkeypatch.setattr(load_study, "study", check)
    plan = {"numbers": [], "loads": [], "designer": [], "check": {"spacing_mm": None}, "said": "", "gone": [], "left": [],
            "same": []}
    monkeypatch.setattr(fixing, "plan", lambda *a, **k: plan)
    stops = []
    fixing.apply(stool, "stool", [], stop=lambda: stops.append(1))
    assert "stop" in seen and len(stops) >= 2       # before its check, and inside it
    with pytest.raises(Cancelled):                  # a stop is the job's: never "not checked again: Cancelled"
        fixing.apply(stool, "stool", [], stop=_stop_at(len(stops)))


def test_a_stop_never_asked_changes_nothing(stool):
    rec = load_study.study(stool, "stool", stop=lambda: None)
    assert rec["cases"] and len(load_study.list_runs(stool, "stool")) == 1


def test_fix_these_stopped_before_its_check_never_starts_it(stool, monkeypatch):
    ran = []
    monkeypatch.setattr(load_study, "study", lambda *a, **k: ran.append(1) or {})
    plan = {"numbers": [], "loads": [], "designer": [], "check": {"spacing_mm": None}, "said": "", "gone": [], "left": [],
            "same": []}
    monkeypatch.setattr(fixing, "plan", lambda *a, **k: plan)
    asked = []
    fixing.apply(stool, "stool", [], stop=lambda: asked.append(1))           # how many stops come before the check
    before = len(asked)
    assert before == 2                              # before the edits (as ever), and before the check, after them (#398)
    ran.clear()
    with pytest.raises(Cancelled):
        fixing.apply(stool, "stool", [], stop=_stop_at(before))
    assert ran == []
