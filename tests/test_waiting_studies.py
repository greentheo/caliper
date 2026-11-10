"""CALI-136 (#174) — strength studies take turns on a worker (#163). With a queue of them every worker was waiting, and a chat waited behind
them. They have workers of their own now, and one that waits says how long the turn ahead has been going."""
import threading
import time

import pytest

from caliper import jobs, one_study


@pytest.fixture
def held():
    """Another study has the turn."""
    got, go = threading.Event(), threading.Event()

    def hold():
        one_study._TURN.acquire()
        got.set()
        go.wait(20)
        one_study._TURN.release()

    t = threading.Thread(target=hold)
    t.start()
    got.wait(5)
    yield go
    go.set()
    t.join(10)


def _waits(job):
    one_study.take_turn(lambda k, t="", **d: job.emit(k, t, **d), job.check)
    one_study._TURN.release()


def _settle(runner, held):
    held.set()
    end = time.time() + 15
    while time.time() < end and runner.active():
        time.sleep(0.02)
    assert not runner.active()


@pytest.mark.parametrize("n", [8, 12])
def test_with_a_queue_of_studies_a_chat_starts_straight_away(held, n):
    r = jobs.JobRunner()
    waiting = [r.submit("load", _waits, lock=f"load:{i}") for i in range(n)]
    end = time.time() + 5
    while time.time() < end and not all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in waiting):
        time.sleep(0.02)
    assert all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in waiting)
    began = threading.Event()
    r.submit("chat", lambda j: began.set(), lock="design:a")
    assert began.wait(2), "the chat waited behind the studies"
    _settle(r, held)


@pytest.mark.parametrize("kind", sorted(jobs.STUDIES))
def test_each_long_kind_goes_to_the_studies_workers(kind):
    r = jobs.JobRunner()
    name = []
    j = r.submit(kind, lambda j: name.append(threading.current_thread().name))
    end = time.time() + 5
    while time.time() < end and not j.over:
        time.sleep(0.01)
    assert name[0].startswith("caliper-study")


@pytest.mark.parametrize("kind", ["chat", "clarify", "goals", "firstrun", "cutplan"])
def test_a_conversation_stays_on_its_own_workers(kind):
    r = jobs.JobRunner()
    name = []
    j = r.submit(kind, lambda j: name.append(threading.current_thread().name))
    end = time.time() + 5
    while time.time() < end and not j.over:
        time.sleep(0.01)
    assert name[0].startswith("caliper-job")


def test_a_waiting_study_says_how_long_it_has_been(held, monkeypatch):
    monkeypatch.setattr(one_study, "TELL_EVERY_S", 0.05)
    said, done = [], threading.Event()

    def stop():
        if len(said) >= 3:
            done.set()
            raise jobs.Cancelled()

    with pytest.raises(jobs.Cancelled):
        one_study.take_turn(lambda k, t="", **d: said.append((k, t)), stop)
    assert said[0] == ("waiting", one_study.WAITING)
    assert all(k == "waiting" for k, _ in said) and "It's been running" in said[1][1] and one_study._queued == 0


def test_it_says_how_many_others_are_waiting(monkeypatch):
    monkeypatch.setattr(one_study, "_since", time.monotonic() - 125)
    assert one_study._how_long(0).endswith("It's been running 2 min.")
    assert one_study._how_long(1).endswith("and 1 other is waiting too.")
    assert one_study._how_long(3).endswith("and 3 others are waiting too.")


def test_a_study_inside_a_study_doesn_t_restart_the_clock():
    one_study.take_turn()
    first = one_study._since
    time.sleep(0.01)
    one_study.take_turn()
    assert one_study._since == first
    one_study._TURN.release()
    one_study._TURN.release()


def test_getting_the_turn_after_waiting_starts_the_clock(held):
    first = one_study._since
    t = threading.Timer(0.05, held.set)
    t.start()
    assert one_study.take_turn() is True
    assert one_study._since > first
    one_study._TURN.release()
