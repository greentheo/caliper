"""CALI-144 (#184) — a build package queued behind a strength check looked for a run before it took its turn, found none yet, and ran the
same check again straight after the first finished: 351 s then 239 s, both 0.58x. Stubbed: no FEA."""
import json
import os
import threading

import pytest

from caliper import cutplan, jobs, load_study, one_study, release, scorecard
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


# --- the review of #198: a revision during the wait -------------------------------------------------------------------------
def _script(h):
    return f"""import cadquery as cq

def build(params):
    return cq.Workplane('XY').box(20, 20, {h}, centered=(True, True, False))

def construction(params, build=None):
    return [{{"name": "body", "kind": "printed", "material": "petg", "infill": 0.4}}]

def loads(params, build=None):
    return []
"""


def _file(store, pid, safety, breaks=1000):
    v = store.design.part(pid).version
    d = os.path.join(load_study.runs_dir(store), f"20261110-00000{v}-{pid}")
    os.makedirs(d, exist_ok=True)
    rec = {"id": f"{pid}{v}", "part": pid, "version": v, "created": 1.0 + v, "safety": safety, "min_safety": 2.0, "holds": True,
           "cases": [{"name": "Dad", "lb": 200, "factor": 2.0, "safety": safety, "holds": True, "breaks_lb": breaks}]}
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump(rec, f)
    return rec


def _once(monkeypatch, then):
    """The first wait: ``then`` happens while it waits, and it has waited."""
    real, done = one_study.take_turn, []

    def turn(emit=None, stop=None):
        if not done:
            done.append(1)
            then()
            real(emit, stop)
            return True
        return real(emit, stop)

    monkeypatch.setattr(one_study, "take_turn", turn)


def _study_files(monkeypatch, by_version):
    calls = []

    def study(store, part, *, emit=None, stop=None, **k):
        v = store.design.part(part).version
        calls.append((part, v))
        return _file(store, part, by_version[v])

    monkeypatch.setattr(load_study, "study", study)
    return calls


@pytest.fixture
def forty(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    monkeypatch.setenv("CALIPER_SLICER", "")
    s = DesignStore.create("a post", base=str(tmp_path / "designs"))
    s.write_part("p", _script(40), intent="a post")
    return s


def _revise(store, pid, h):
    other = DesignStore.load(store.root)
    other.write_part(pid, _script(h), intent="a post")


def test_a_revision_during_the_wait_scores_the_new_version(forty, monkeypatch):
    calls = _study_files(monkeypatch, {1: 3.1, 2: 9.0})

    def first_check_finishes_then_it_s_revised():
        _file(forty, "p", 3.1)
        _revise(forty, "p", 50)

    _once(monkeypatch, first_check_finishes_then_it_s_revised)
    said = []
    card = scorecard.compute(forty, emit=lambda k, t="", **d: said.append(t))
    assert card["versions"] == {"p": 2} and card["metrics"]["strength.safety"]["value"] == 9.0
    assert calls == [("p", 2)] and any("A part changed" in t for t in said)


def test_the_package_names_one_version(forty, monkeypatch):
    """The reviewer's case: 40 mm at v1, 50 mm at v2 during the wait, and the book said v1 with v2's shape and v1's strength."""
    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    _study_files(monkeypatch, {1: 3.1, 2: 9.0})

    def first_check_finishes_then_it_s_revised():
        _file(forty, "p", 3.1)
        _revise(forty, "p", 50)

    _once(monkeypatch, first_check_finishes_then_it_s_revised)
    made = release.make(forty, pdf=False)
    root = os.path.join(release.releases_dir(forty), made["id"])
    assert made["versions"] == {"p": 2}
    assert sorted(os.listdir(os.path.join(root, "source"))).count("p-v002.py") == 1 and "p-v001.py" not in os.listdir(os.path.join(root, "source"))
    assert made["strength"]["p"][0]["safety"] == 9.0
    with open(os.path.join(root, "index.html")) as f:
        book = f.read()
    assert "p v2" in book and "p v1" not in book


def test_another_part_revised_during_the_wait_isn_t_read_at_its_old_version(forty, monkeypatch):
    forty.write_part("b", _script(30), intent="another")
    _file(forty, "b", 2.9)
    calls = _study_files(monkeypatch, {1: 3.1, 2: 8.0})
    _once(monkeypatch, lambda: _revise(forty, "b", 35))
    card = scorecard.compute(forty)
    assert card["versions"] == {"p": 1, "b": 2}
    assert card["metrics"]["strength.b.safety"]["value"] == 8.0 and ("b", 2) in calls


def test_a_part_removed_during_the_wait_is_scored_as_gone(forty, monkeypatch):
    forty.write_part("b", _script(30), intent="another")
    _study_files(monkeypatch, {1: 3.1})

    def remove():
        from caliper import trash

        trash.remove(DesignStore.load(forty.root), "b")

    _once(monkeypatch, remove)
    card = scorecard.compute(forty)
    assert "b" not in card["versions"] and "strength.b.error" not in card["metrics"]


def test_a_design_that_keeps_changing_stops_and_says_so(forty, monkeypatch):
    _study_files(monkeypatch, {v: 3.0 for v in range(1, 9)})
    real, n = one_study.take_turn, [40]

    def always(emit=None, stop=None):
        n[0] += 1
        _revise(forty, "p", n[0])
        real(emit, stop)
        return True

    monkeypatch.setattr(one_study, "take_turn", always)
    with pytest.raises(ValueError, match="kept changing"):
        scorecard.compute(forty)


def test_a_cancel_reaches_the_real_wait(forty, monkeypatch):
    calls = _study_files(monkeypatch, {1: 3.1})
    held, go = threading.Event(), threading.Event()

    def hold():
        with one_study.my_turn(forty):
            held.set()
            go.wait(10)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(5)

    def stop():
        raise jobs.Cancelled()

    try:
        with pytest.raises(jobs.Cancelled):
            scorecard.compute(DesignStore.load(forty.root), stop=stop)
    finally:
        go.set()
        t.join(10)
    assert calls == []

