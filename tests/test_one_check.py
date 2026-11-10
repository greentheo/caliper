"""CALI-144 (#184) — a build package queued behind a strength check looked for a run before it took its turn, found none yet, and ran the
same check again straight after the first finished: 351 s then 239 s, both 0.58x. Stubbed: no FEA."""
import json
import os
import threading

import pytest

from caliper import jobs, load_study, one_study, scorecard
from caliper.design import DesignStore

from .test_goals import BOX

pytest.importorskip("cadquery")


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a stool")
    return s


def _filed(store):
    d = os.path.join(load_study.runs_dir(store), "20261110-000000-test")
    os.makedirs(d)
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "x", "part": "stool", "version": store.design.part("stool").version, "created": 1.0, "safety": 3.1,
                   "cases": [{"name": "Dad", "safety": 3.1, "breaks_lb": 1240}]}, f)


def _no_second(monkeypatch):
    calls = []
    monkeypatch.setattr(load_study, "study", lambda *a, **k: calls.append(1) or {"cases": []})
    return calls


def test_queued_behind_the_same_check_it_uses_that_check(store, monkeypatch):
    calls = _no_second(monkeypatch)
    real = one_study.take_turn

    def waits_then_the_check_is_there(emit=None, stop=None):
        _filed(store)
        return real(emit, stop) or True

    monkeypatch.setattr(one_study, "take_turn", waits_then_the_check_is_there)
    card = scorecard.compute(store)
    assert calls == [] and card["metrics"]["strength.safety"]["value"] == 3.1


def test_really_waiting_behind_another_thread(store, monkeypatch):
    calls = _no_second(monkeypatch)
    held, go, said = threading.Event(), threading.Event(), []

    def first():
        with one_study.my_turn(store):
            held.set()
            go.wait(10)
            _filed(store)

    t = threading.Thread(target=first)
    t.start()
    held.wait(5)
    out = {}
    s2 = DesignStore.load(store.root)
    w = threading.Thread(target=lambda: out.update(card=scorecard.compute(s2, emit=lambda k, *a, **d: said.append(k))))
    w.start()
    while "waiting" not in said and w.is_alive():
        pass
    go.set()
    t.join(10)
    w.join(60)
    assert calls == [] and "waiting" in said and out["card"]["metrics"]["strength.safety"]["value"] == 3.1


def test_with_nothing_filed_it_runs_the_check(store, monkeypatch):
    calls = _no_second(monkeypatch)
    scorecard.compute(store)
    assert calls == [1]


def test_a_check_of_an_older_version_doesn_t_count(store, monkeypatch):
    calls = _no_second(monkeypatch)
    _filed(store)
    store.write_part("stool", store.read_script("stool") + "\n# a change\n", intent="a stool")
    scorecard.compute(store)
    assert calls == [1]


def test_cancelled_while_it_waits_stops(store, monkeypatch):
    calls = _no_second(monkeypatch)

    def stops(emit=None, stop=None):
        raise jobs.Cancelled()

    monkeypatch.setattr(one_study, "take_turn", stops)
    with pytest.raises(jobs.Cancelled):
        scorecard.compute(store)
    assert calls == []


def test_the_turn_is_given_back(store):
    with one_study.my_turn(store):
        pass
    assert one_study._TURN.acquire(blocking=False)
    one_study._TURN.release()


def test_it_reads_the_design_again_if_it_waited(store, monkeypatch):
    monkeypatch.setattr(one_study, "take_turn", lambda *a: one_study._TURN.acquire() and True)
    other = DesignStore.load(store.root)
    other.write_part("stool", other.read_script("stool") + "\n# moved on\n", intent="a stool")
    with one_study.my_turn(store):
        assert store.design.part("stool").version == other.design.part("stool").version
