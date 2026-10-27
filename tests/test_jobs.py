"""CALI-31 — background jobs and their event stream."""

import json
import threading
import time

from caliper.jobs import JobRunner, stream


def _data(frames):
    """The JSON payload of every frame that carries one (event frames lead with an `id:` line)."""
    out = []
    for f in frames:
        for line in f.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[len("data: "):]))
    return out


def _wait(job, timeout=5.0):
    end = time.time() + timeout
    while not job.over and time.time() < end:
        time.sleep(0.01)
    assert job.over, "job never finished"


def test_a_job_runs_in_the_background_and_keeps_its_result():
    runner = JobRunner()
    job = runner.submit("demo", lambda j: 42, label="answer")
    _wait(job)
    assert (job.status, job.result) == ("done", 42)
    assert [e["kind"] for e in job.events] == ["started", "finished"]
    assert runner.get(job.id) is job


def test_progress_events_arrive_in_order_with_sequence_numbers():
    def work(j):
        for i in range(3):
            j.emit("step", f"step {i}", i=i)
        return "ok"

    job = JobRunner().submit("demo", work)
    _wait(job)
    kinds = [e["kind"] for e in job.events]
    assert kinds == ["started", "step", "step", "step", "finished"]
    assert [e["seq"] for e in job.events] == list(range(5))
    assert job.since(2)[0]["i"] == 1          # a reconnecting reader picks up where it left off


def test_a_failure_is_named_with_the_real_exception():
    def boom(j):
        raise ValueError("the box contains none of the part")

    job = JobRunner().submit("demo", boom)
    _wait(job)
    assert job.status == "error"
    assert job.error == "ValueError: the box contains none of the part"
    assert job.events[-1]["kind"] == "error"


def test_jobs_sharing_a_lock_never_overlap():
    """Two writes to one design must not interleave — DesignStore is single-writer."""
    runner, active, peak, mu = JobRunner(workers=4), [0], [0], threading.Lock()

    def work(j):
        with mu:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with mu:
            active[0] -= 1

    jobs = [runner.submit("demo", work, lock="design:gantry") for _ in range(4)]
    for j in jobs:
        _wait(j)
    assert peak[0] == 1


def test_jobs_with_different_locks_run_side_by_side():
    """A whittle sweep waiting on whittle must not block a chat about something else."""
    runner, gate = JobRunner(workers=4), threading.Event()
    slow = runner.submit("whittle", lambda j: gate.wait(2.0), lock="whittle:gantry")
    quick = runner.submit("chat", lambda j: "answered", lock="design:gantry")
    _wait(quick, timeout=1.0)
    assert quick.result == "answered" and not slow.over
    gate.set()
    _wait(slow)


def test_the_stream_replays_every_event_then_ends_with_the_result():
    def work(j):
        j.emit("step", "half way")
        return {"reply": "done"}

    job = JobRunner().submit("demo", work)
    payloads = _data(stream(job, poll=0.01))
    assert [p["kind"] for p in payloads] == ["started", "step", "finished", "end"]
    assert payloads[-1]["result"] == {"reply": "done"} and payloads[-1]["status"] == "done"


def test_the_stream_resumes_after_a_given_event():
    job = JobRunner().submit("demo", lambda j: j.emit("step", "x") and None)
    _wait(job)
    assert [p["kind"] for p in _data(stream(job, after=2, poll=0.01))] == ["finished", "end"]


def test_a_quiet_stream_sends_heartbeats():
    gate = threading.Event()
    job = JobRunner().submit("demo", lambda j: gate.wait(1.0))
    gen = stream(job, poll=0.01, heartbeat=0.05)
    seen = []
    for frame in gen:
        seen.append(frame)
        if any(f.startswith(": keep-alive") for f in seen):
            gate.set()
        if '"kind": "end"' in frame:
            break
    assert any(f.startswith(": keep-alive") for f in seen)


def test_a_synchronous_write_waits_for_a_running_job_on_the_same_key():
    """The lost-update guard: a quick settings write can't slip in under a chat turn's save."""
    runner, order, gate = JobRunner(), [], threading.Event()

    def turn(j):
        gate.set()
        time.sleep(0.1)
        order.append("job saved")

    job = runner.submit("chat", turn, lock="design:gantry")
    gate.wait(1.0)
    with runner.locked("design:gantry"):
        order.append("setting written")
    _wait(job)
    assert order == ["job saved", "setting written"]
