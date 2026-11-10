"""CALI-132 (#163) — a Lighten beside a carve read its FEA wrong. Strength studies take turns, and a waiting one says so.
Stubbed: the studies here only record when they ran."""

import threading
import time

import pytest

from caliper import carve, frame_study, jobs, lighten, load_study, one_study


def _study(log, name, gate=None):
    @one_study.one_at_a_time
    def study(emit=None, stop=None):
        log.append(f"{name} in")
        if gate:
            gate.wait(5)
        time.sleep(0.02)
        log.append(f"{name} out")
        return name

    return study


def _start(fn, **kw):
    box = {}
    t = threading.Thread(target=lambda: box.update(result=_call(fn, **kw)))
    t.start()
    return t, box


def _call(fn, **kw):
    try:
        return fn(**kw)
    except Exception as e:  # noqa: BLE001
        return e


def _until(cond, seconds=3.0):
    t = time.time()
    while not cond() and time.time() - t < seconds:
        time.sleep(0.01)
    assert cond()


def test_two_studies_never_overlap():
    log = []
    threads = [_start(_study(log, f"s{i}"))[0] for i in range(6)]
    for t in threads:
        t.join(5)
    pairs = [log[i:i + 2] for i in range(0, len(log), 2)]
    assert all(a.endswith("in") and b == a.replace("in", "out") for a, b in pairs), log


def test_a_study_that_has_to_wait_says_so_once_and_names_nobody_s_part():
    log, said, gate = [], [], threading.Event()
    first, _ = _start(_study(log, "first", gate))
    _until(lambda: "first in" in log)
    second, _ = _start(_study(log, "second"), emit=lambda k, t="", **d: said.append((k, t)))
    _until(lambda: said)
    time.sleep(0.6)                                                         # waits through several polls
    assert "second in" not in log and said == [("waiting", one_study.WAITING)]
    gate.set()
    first.join(5), second.join(5)
    assert "second out" in log


def test_a_study_with_nothing_ahead_says_nothing():
    said = []
    assert _study([], "alone")(emit=lambda k, t="", **d: said.append(k)) == "alone" and said == []


def test_a_study_can_be_cancelled_while_it_waits():
    log, gate = [], threading.Event()
    first, _ = _start(_study(log, "first", gate))
    _until(lambda: "first in" in log)

    def stop():
        raise jobs.Cancelled()

    second, box = _start(_study(log, "second"), stop=stop)
    second.join(3)
    assert isinstance(box["result"], jobs.Cancelled) and "second in" not in log
    gate.set()
    first.join(5)


def test_a_failed_study_gives_up_its_turn():
    @one_study.one_at_a_time
    def bad(emit=None, stop=None):
        raise ValueError("no")

    with pytest.raises(ValueError):
        bad()
    assert _study([], "next")() == "next"


def test_a_study_inside_a_study_doesn_t_wait_for_itself():
    @one_study.one_at_a_time
    def outer(emit=None, stop=None):
        return _study([], "inner")()

    t, box = _start(outer)
    t.join(3)
    assert box["result"] == "inner"


@pytest.mark.parametrize("module", [load_study, carve, lighten, frame_study])
def test_every_structural_study_takes_its_turn(module):
    assert module.study.__wrapped__ is not None


def test_waiting_studies_leave_workers_for_the_chat():
    assert jobs.JobRunner()._pool._max_workers >= 8


# --- #169 review ------------------------------------------------------------------------------------------------------
from caliper import frame_study as _F  # noqa: E402
from caliper import parked, pictures  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

BOX = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box({x}, 20, 10)\n"


@pytest.fixture
def store(tmp_path):
    pytest.importorskip("cadquery")
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX.format(x=40), intent="a box")
    return s


@one_study.one_at_a_time
def _record(store, emit=None, stop=None):
    """What a study does: read the part and file what it read, against the version it read."""
    return {"version": store.design.part("box").version, "script": store.read_script("box")}


def test_a_study_that_waited_works_from_the_part_as_it_is_now(store):
    """The reviewer's case: asked for at v1, revised to v2 during the wait: the record's version and number must agree."""
    log, gate, said = [], threading.Event(), []
    first, _ = _start(_study(log, "first", gate))
    _until(lambda: "first in" in log)
    got = {}
    second = threading.Thread(target=lambda: got.update(_record(store, emit=lambda k, t="", **d: said.append(k))))
    second.start()
    _until(lambda: said)
    other = DesignStore.load(store.root)
    other.write_part("box", BOX.format(x=99), intent="a bigger box")
    gate.set()
    first.join(5), second.join(5)
    assert got["version"] == 2 and "box(99" in got["script"]
    assert store.design.part("box").version == 2                            # the caller's store too


def test_a_study_that_didn_t_wait_keeps_the_store_it_was_given(store):
    store.design.part("box").intent = "not saved yet"
    _record(store)
    assert store.design.part("box").intent == "not saved yet"


@pytest.mark.parametrize("fn", [pictures.put, _F.gussets, _F.analyse, parked.run])
def test_every_other_fea_takes_its_turn(fn):
    assert fn.__wrapped__ is not None


@pytest.mark.parametrize("module", [load_study, lighten])
def test_a_waiting_check_or_lighten_can_be_stopped(module):
    assert "stop" in __import__("inspect").signature(module.study).parameters


def _source(name):
    import caliper

    return open(__import__("os").path.join(__import__("os").path.dirname(caliper.__file__), name)).read()


def test_the_routes_let_a_waiting_check_or_lighten_be_cancelled():
    src = _source("design_api.py")
    assert src.count("emit=lambda k, t=\"\", **d: j.emit(k, t, **d), stop=j.check") >= 3


def test_the_scorecard_says_it_is_waiting():
    src = _source("scorecard.py")
    assert "load_study.study(store, p.id, emit=emit)" in src and 'bool(settings.get("walls", True)), emit=emit)' in src
