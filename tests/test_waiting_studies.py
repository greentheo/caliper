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


#: written out: a kind dropped from the list must fail here, not stop being tested
LONG = ["aero", "carve", "firstrun", "frame", "gussets", "lighten", "load", "picture", "release", "scorecard", "whittle"]


def test_the_list_of_long_kinds_is_this():
    assert sorted(jobs.STUDIES) == LONG


@pytest.mark.parametrize("kind", LONG)
def test_each_long_kind_goes_to_the_studies_workers(kind):
    r = jobs.JobRunner()
    name = []
    j = r.submit(kind, lambda j: name.append(threading.current_thread().name))
    end = time.time() + 5
    while time.time() < end and not j.over:
        time.sleep(0.01)
    assert name[0].startswith("caliper-study")


@pytest.mark.parametrize("kind", ["chat", "clarify", "goals", "cutplan"])
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


def test_with_first_builds_waiting_a_chat_on_another_design_starts_straight_away(held):
    """Every new design starts with a first build, and a first build runs a strength check."""
    r = jobs.JobRunner()
    waiting = [r.submit("firstrun", _waits, lock=f"design:{i}") for i in range(8)]
    end = time.time() + 5
    while time.time() < end and not all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in waiting):
        time.sleep(0.02)
    began = threading.Event()
    r.submit("chat", lambda j: began.set(), lock="design:other")
    assert began.wait(2)
    _settle(r, held)


@pytest.mark.parametrize("kind,word", [("release", "the build package"), ("picture", "the picture"), ("cutplan", "the cut plan"),
                                       ("firstrun", "the first build"), ("chat", "the message before it"), ("frame", "another job")])
def test_a_chat_on_a_busy_design_says_what_it_s_waiting_for(kind, word):
    r = jobs.JobRunner()
    began, go = threading.Event(), threading.Event()

    def holds(j):
        began.set()
        go.wait(10)

    r.submit(kind, holds, lock="design:a")
    assert began.wait(5)
    chat = r.submit("chat", lambda j: None, lock="design:a")
    end = time.time() + 5
    while time.time() < end and not any(e.get("kind") == "waiting" for e in chat.since(0)):
        time.sleep(0.01)
    assert [e["text"] for e in chat.since(0) if e.get("kind") == "waiting"] == [f"Waiting for {word} on this design to finish."]
    assert chat.status == "queued"
    go.set()
    end = time.time() + 5
    while time.time() < end and not chat.over:
        time.sleep(0.01)
    assert chat.status == "done"


def test_a_chat_with_nothing_ahead_of_it_says_nothing_about_waiting():
    r = jobs.JobRunner()
    chat = r.submit("chat", lambda j: None, lock="design:a")
    end = time.time() + 5
    while time.time() < end and not chat.over:
        time.sleep(0.01)
    assert not [e for e in chat.since(0) if e.get("kind") == "waiting"]


def test_how_often_it_says_so():
    assert one_study.TELL_EVERY_S == 30.0


def test_the_count_leaves_out_the_one_asking(held, monkeypatch):
    monkeypatch.setattr(one_study, "TELL_EVERY_S", 0.02)
    said = []

    def stop():
        if len(said) >= 2:
            raise jobs.Cancelled()

    with pytest.raises(jobs.Cancelled):
        one_study.take_turn(lambda k, t="", **d: said.append(t), stop)
    assert "waiting too" not in said[1]                               # alone in the queue


def test_a_study_just_begun_doesn_t_read_0_min(monkeypatch):
    monkeypatch.setattr(one_study, "_since", time.monotonic() - 2)
    assert "under a minute" in one_study._how_long(0)



# --- the rest of #174: chats that wait hold no worker either ------------------------------------------------------------------
def _chat_waits_for_the_turn(job):
    """A chat that turns into a study (a carve, a picture) takes the turn inside the chat job, with no stop= passed."""
    one_study.take_turn(lambda k, t="", **d: job.emit(k, t, **d))
    one_study._TURN.release()


@pytest.mark.parametrize("n", [8, 12])
def test_with_chats_waiting_for_the_study_turn_another_chat_starts_straight_away(held, n):
    """The night shift's note on #174 (#205's review): eight chats each running a check still filled the chat workers."""
    r = jobs.JobRunner()
    waiting = [r.submit("chat", _chat_waits_for_the_turn, lock=f"design:{i}") for i in range(n)]
    end = time.time() + 5
    while time.time() < end and not all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in waiting):
        time.sleep(0.02)
    assert all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in waiting)
    began = threading.Event()
    r.submit("chat", lambda j: began.set(), lock="design:other")
    assert began.wait(2), "the chat waited behind chats waiting for the study turn"
    _settle(r, held)


def test_with_chats_queued_behind_their_design_another_design_s_chat_starts_straight_away():
    """A chat queued behind another job on its design waited on that design's lock while holding a worker."""
    r = jobs.JobRunner()
    go, began = threading.Event(), threading.Event()
    first = r.submit("chat", lambda j: go.wait(20), lock="design:a")
    queued = [r.submit("chat", lambda j: None, lock="design:a") for _ in range(10)]
    end = time.time() + 5
    while time.time() < end and not all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in queued):
        time.sleep(0.02)
    r.submit("chat", lambda j: began.set(), lock="design:b")
    try:
        assert began.wait(2), "the chat waited behind chats queued on another design"
    finally:
        go.set()
    end = time.time() + 10
    while time.time() < end and r.active():
        time.sleep(0.02)
    assert first.status == "done" and all(j.status == "done" for j in queued)


def test_running_chats_are_still_held_to_the_worker_count():
    """Waiting takes no worker; working does: at most `workers` chats run at once."""
    r, mu, now, peak, go = jobs.JobRunner(workers=3), threading.Lock(), [0], [0], threading.Event()

    def work(j):
        with mu:
            now[0] += 1
            peak[0] = max(peak[0], now[0])
        go.wait(0.3)
        with mu:
            now[0] -= 1

    js = [r.submit("chat", work, lock=f"design:{i}") for i in range(9)]
    end = time.time() + 10
    while time.time() < end and r.active():
        time.sleep(0.02)
    assert all(j.status == "done" for j in js) and peak[0] == 3, peak


def test_after_the_study_turn_a_chat_takes_its_worker_back(held):
    """#256 review: a parked job never took its worker back, so work after the turn ran uncounted (2 workers, 8 chats, peak 4)."""
    r, mu, now, peak = jobs.JobRunner(workers=2), threading.Lock(), [0], [0]

    def chat(j):
        one_study.take_turn(lambda k, t="", **d: j.emit(k, t, **d))
        one_study._TURN.release()
        with mu:
            now[0] += 1
            peak[0] = max(peak[0], now[0])
        time.sleep(0.6)                                   # its work after the turn: counted against the workers
        with mu:
            now[0] -= 1

    js = [r.submit("chat", chat, lock=f"design:{i}") for i in range(8)]
    end = time.time() + 5
    while time.time() < end and not all(any(e.get("kind") == "waiting" for e in j.since(0)) for j in js):
        time.sleep(0.02)
    held.set()                                            # the turn goes round, one at a time
    end = time.time() + 20
    while time.time() < end and r.active():
        time.sleep(0.02)
    assert all(j.status == "done" for j in js) and peak[0] == 2, peak


def test_a_chat_cancelled_while_it_waits_for_a_worker_leaves_at_once():
    r, gate, ran = jobs.JobRunner(workers=1), threading.Event(), []
    first = r.submit("chat", lambda j: gate.wait(10), lock="design:a")
    end = time.time() + 5
    while time.time() < end and first.status != "running":
        time.sleep(0.01)
    second = r.submit("chat", lambda j: ran.append(1), lock="design:b")
    time.sleep(0.3)                                       # past its design's lock, waiting for the one worker
    r.cancel(second.id)
    end = time.time() + 2
    while time.time() < end and not second.over:
        time.sleep(0.01)
    try:
        assert second.status == "cancelled" and ran == [], second.status
    finally:
        gate.set()
    end = time.time() + 5
    while time.time() < end and r.active():
        time.sleep(0.02)
    assert ran == [] and first.status == "done"


def test_a_chat_cancelled_after_its_turn_while_it_waits_for_a_worker_passes_the_turn_on(held):
    r, gate, ran = jobs.JobRunner(workers=1), threading.Event(), []

    def chat(j):
        one_study.take_turn(lambda k, t="", **d: j.emit(k, t, **d))
        try:
            ran.append("worked")
        finally:
            one_study._TURN.release()

    waiting = r.submit("chat", chat, lock="design:a")
    end = time.time() + 5
    while time.time() < end and not any(e.get("kind") == "waiting" for e in waiting.since(0)):
        time.sleep(0.01)
    busy = r.submit("chat", lambda j: gate.wait(10), lock="design:b")           # takes the one worker it gave back
    end = time.time() + 5
    while time.time() < end and busy.status != "running":
        time.sleep(0.01)
    held.set()                                            # its turn comes, and it waits for the worker
    time.sleep(0.4)
    r.cancel(waiting.id)
    end = time.time() + 3
    while time.time() < end and not waiting.over:
        time.sleep(0.01)
    try:
        assert waiting.status == "cancelled" and ran == [], (waiting.status, ran)
        assert one_study._TURN.acquire(timeout=2), "the turn wasn't passed on"
        one_study._TURN.release()
    finally:
        gate.set()
