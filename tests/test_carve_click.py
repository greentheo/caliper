"""CALI-101 (#93) — Carve it: one click, one carve; progress you can see; and a cancel.

On Theo's operator run (the bar stool, 2026-11-05), one click on Carve it sent two POST /carve 11 ms apart, so a
second hour-long carve queued behind the first. The panel sat at "starting…", the page threw in makingView, and
nothing could stop either job."""

import json
import os
import re
import shutil
import subprocess
import threading
import time

import pytest

from caliper import jobs

from .test_mixed import MIXED

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


# --- the runner: one at a time, and a cancel ------------------------------------------------------------------
def test_two_exclusive_submits_at_once_start_one_job():
    """Two requests 11 ms apart: a check-then-submit lets both through. The check and the queueing are one step."""
    runner, gate = jobs.JobRunner(), threading.Event()
    got, start = [], threading.Barrier(8)

    def ask():
        start.wait()
        try:
            got.append(runner.submit("carve", lambda j: gate.wait(10), lock="carve:x", exclusive=True))
        except jobs.Busy as e:
            got.append(e)

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    started = [g for g in got if isinstance(g, jobs.Job)]
    refused = [g for g in got if isinstance(g, jobs.Busy)]
    assert len(started) == 1 and len(refused) == 7
    assert all(b.job is started[0] for b in refused)          # it says which job is in the way
    gate.set()
    _wait(started[0])
    _wait(runner.submit("carve", lambda j: None, lock="carve:x", exclusive=True))   # once it's over, another may


def test_a_queued_job_cancelled_never_runs():
    runner, gate, ran = jobs.JobRunner(workers=1), threading.Event(), []
    first = runner.submit("carve", lambda j: gate.wait(10), lock="a")
    second = runner.submit("carve", lambda j: ran.append(1), lock="b")       # waiting for the one worker
    assert runner.cancel(second.id) is second and second.status == "cancelled"
    gate.set()
    _wait(first)
    time.sleep(0.2)
    assert not ran and second.status == "cancelled" and second.over
    assert [e["kind"] for e in second.events][-1] == "cancelled"


def test_a_running_job_stops_at_its_next_check():
    runner, steps = jobs.JobRunner(), []

    def work(j):
        for k in range(200):
            j.check()                                   # a step boundary
            steps.append(k)
            time.sleep(0.02)
        return "finished"

    job = runner.submit("carve", work)
    end = time.time() + 10
    while not steps and not job.over:
        assert time.time() < end
        time.sleep(0.01)
    assert steps, job.error
    runner.cancel(job.id)
    _wait(job)
    assert job.status == "cancelled" and job.result is None and len(steps) < 200
    assert job.events[-1]["kind"] == "cancelled" and job.over
    frames = list(jobs.stream(job, poll=0.01))
    assert json.loads(frames[-1].split("data: ", 1)[1])["status"] == "cancelled"
    assert runner.cancel("nope") is None
    assert runner.cancel(job.id) is job                  # cancelling one that's over changes nothing
    assert job.status == "cancelled"


def _wait(job, timeout=10):
    end = time.time() + timeout
    while not job.over:
        assert time.time() < end, "the job never ended"
        time.sleep(0.02)


# --- the API: a second carve is refused, and a carve can be cancelled ----------------------------------------
@pytest.fixture
def api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("whittle")
    from fastapi.testclient import TestClient

    from caliper import carve
    from caliper.design import DesignStore
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED, intent="a plywood top on printed sides")
    gate, began = threading.Event(), threading.Event()

    def slow(store, part_id, *, min_safety=None, emit=None, stop=None, **k):
        """A carve that takes as long as the test says, checking for a cancel at each step."""
        began.set()
        for k in range(500):
            if gate.is_set():
                return {"id": "x"}
            stop()
            emit("checking", f"step {k}", progress=k / 500)
            time.sleep(0.02)

    monkeypatch.setattr(carve, "study", slow)
    yield TestClient(create_app()), store.design.slug, gate, began
    gate.set()


def test_a_second_carve_of_one_design_is_refused_while_one_runs(api):
    c, slug, gate, began = api
    first = c.post(f"/api/designs/{slug}/carve", json={"part": "stool"})
    assert first.status_code == 200
    began.wait(10)
    second = c.post(f"/api/designs/{slug}/carve", json={"part": "stool"})
    assert second.status_code == 409
    assert second.json()["detail"].startswith("a carve is already running"), second.json()
    # the page finds it again after a redraw or a reload
    state = c.get(f"/api/designs/{slug}").json()
    assert state["carving"] == {"job": first.json()["job_id"], "part": "stool"}
    gate.set()
    _wait(jobs.RUNNER.get(first.json()["job_id"]))
    assert c.get(f"/api/designs/{slug}").json()["carving"] is None


def test_a_carve_can_be_cancelled_from_its_panel(api):
    c, slug, gate, began = api
    jid = c.post(f"/api/designs/{slug}/carve", json={"part": "stool"}).json()["job_id"]
    began.wait(10)
    got = c.post(f"/api/jobs/{jid}/cancel")
    assert got.status_code == 200 and got.json()["id"] == jid
    _wait(jobs.RUNNER.get(jid))
    assert c.get(f"/api/jobs/{jid}").json()["status"] == "cancelled"
    assert c.post("/api/jobs/nope/cancel").status_code == 404
    # and once it's stopped, a new one may start
    again = c.post(f"/api/designs/{slug}/carve", json={"part": "stool"})
    assert again.status_code == 200
    gate.set()
    _wait(jobs.RUNNER.get(again.json()["job_id"]))


# --- the carve: it stops at a step and keeps what it finished ----------------------------------------------
def test_a_cancelled_carve_keeps_the_steps_it_finished(tmp_path, monkeypatch):
    """Built on #99's record (on disk from the start and after every step): a cancel writes status "cancelled", with
    the steps it checked and the best of them, and the Studies row says so."""
    pytest.importorskip("whittle")
    from caliper import carve, load_study, studies
    from caliper.design import DesignStore

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED.replace('"lb": 200', '"lb": 60'), intent="kid")
    checked = []
    real = load_study.check_load

    def counts(ctx, i, min_safety, solid=None):
        checked.append(1)
        return real(ctx, i, min_safety, solid=solid)

    def stop():
        if len(checked) >= 2:                          # asked to stop after two steps were checked
            raise jobs.Cancelled()

    monkeypatch.setattr(load_study, "check_load", counts)
    with pytest.raises(jobs.Cancelled):
        carve.study(store, "stool", stations=4, remove_up_to=0.4, stop=stop)
    (rec,) = carve.list_runs(store)
    assert rec["status"] == "cancelled" and len(rec["stations"]) == 2 and rec["steps"] == 4
    holding = [s for s in rec["stations"] if s["holds"]]
    assert rec["best"] == (max(holding, key=lambda s: s["saved_g"])["index"] if holding else None)
    text, ok = studies._headline("carve", rec)
    assert text.startswith("cancelled after 2 of 4 steps") and ok is None


def test_a_cancel_during_the_sweep_stops_it_there(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import carve, load_study
    from caliper.design import DesignStore

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED.replace('"lb": 200', '"lb": 60'), intent="kid")
    calls = []

    def stop():
        calls.append(1)
        if len(calls) > 2:
            raise jobs.Cancelled()

    with pytest.raises(jobs.Cancelled):
        carve.study(store, "stool", stations=4, remove_up_to=0.4, stop=stop)
    (rec,) = carve.list_runs(store)
    assert rec["status"] == "cancelled" and rec["stations"] == []


# --- the page --------------------------------------------------------------------------------------------------
def _node():
    for n in (shutil.which("node"), os.path.expanduser("~/.nvm/versions/node/v22.17.1/bin/node")):
        if n and os.path.exists(n):
            return n
    pytest.skip("no node")


def _fn(src: str, name: str) -> str:
    """One top-level function of design.js, by name, as written."""
    m = re.search(rf"^(async )?function {name}\(.*?^}}\n", src, re.S | re.M)
    assert m, name
    return m.group(0)


def test_the_cards_redraw_while_the_shop_plan_is_loading():
    """The page error on Theo's run: makingView read m.data while its fetch was still out."""
    src = open(JS).read()
    script = _fn(src, "makingView") + """
const S = { making: {}, shopKey: 0 };
const esc = (s) => String(s);
let asked = 0;
function loadMaking(p, key) { asked += 1; S.making[p.id] = { key, loading: true }; }
const p = { id: 'stool', version: 3 };
const first = makingView(p);                 // asks for it
const again = makingView(p);                 // a redraw while it's out: the page threw here
console.log(JSON.stringify({ first, again, asked }));
"""
    out = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert "planning…" in got["again"] and got["asked"] == 1


def test_a_redraw_while_a_carve_runs_keeps_its_panel_and_the_button_stays_off():
    """#93 item 3: a redraw replaced the progress panel with an empty one, and the button came back enabled."""
    src = open(JS).read()
    per = re.search(r"^const CARVE_PER_CHECK = [\d.]+;", src, re.M).group(0)
    script = "\n".join([per] + [_fn(src, n) for n in ("carveView", "carveChart", "carveProgress", "carveTime")]) + """
const esc = (s) => String(s);
const S = { carveJob: {}, station: null };
const carveRuns = () => [];
const loadRuns = () => [{ seconds: 90 }];
const p = { id: 'stool', version: 3, carved: false };
const before = carveView(p);
S.carveJob.stool = { job: 'j1', text: 'step 2: 20% of the printed part carved away', step: 2, steps: 6, progress: 0.4,
                     t0: Date.now() - 600000, p0t: Date.now() - 300000, p0: 0.1 };
const during = carveView(p);
console.log(JSON.stringify({ before, during }));
"""
    out = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert "a few minutes" not in got["before"] and 'id="carveGo" >' in got["before"]
    assert "about " in got["before"] and "at this size" in got["before"]
    during = got["during"]
    assert 'id="carveGo" disabled' in during
    assert "step 2 of 6: 20% of the printed part carved away" in during and 'width:40%' in during
    assert "about 10 min left" in during                       # 0.3 of the way in 5 min: 0.6 to go, 10 min
    assert 'id="carveStop"' in during and ">Cancel<" in during
