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
    """Many at once start one. (This alone can't catch a check-then-queue split: the lock queues the threads in
    order, so the reviewer's split passed it 30 of 30. The next test can.)"""
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


def test_the_check_and_the_queueing_are_one_step():
    """#102 review: a test that fails on a split. A hook between the check and the queueing waits at a barrier for the
    other request. Split, both pass the check and meet there, and both queue. As one step under the runner's lock, the
    second can't reach its check while the first waits; the barrier times out, and the second is refused."""
    runner, gate, got = jobs.JobRunner(), threading.Event(), []
    meet = threading.Barrier(2, timeout=1.0)

    def between():
        try:
            meet.wait()
        except threading.BrokenBarrierError:
            pass

    runner._between = between

    def ask():
        try:
            got.append(runner.submit("carve", lambda j: gate.wait(10), lock="carve:x", exclusive=True))
        except jobs.Busy as e:
            got.append(e)

    threads = [threading.Thread(target=ask) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    gate.set()
    started = [g for g in got if isinstance(g, jobs.Job)]
    assert len(started) == 1 and len(got) == 2, got
    _wait(started[0])


def test_a_job_asked_to_stop_says_so_until_it_does():
    """#102 review: a reload while it was stopping drew the step it was on and an enabled Cancel."""
    from caliper import design_api

    release, ran = threading.Event(), []

    def work(j):
        ran.append(1)
        release.wait(10)                    # a long step: the stop lands at the next boundary
        j.check()

    job = jobs.RUNNER.submit("carve", work, label="carve · stool", lock="carve:spool-test")
    while not ran:
        time.sleep(0.01)
    assert not job.to_dict()["stopping"]
    jobs.RUNNER.cancel(job.id)
    assert job.to_dict()["stopping"] and job.status == "running"
    assert [e["kind"] for e in job.events][-1] == "stopping"
    assert design_api._carving("spool-test") == {"job": job.id, "part": "stool", "stopping": True}
    jobs.RUNNER.cancel(job.id)
    assert [e["kind"] for e in job.events].count("stopping") == 1       # said once
    release.set()
    _wait(job)
    assert job.status == "cancelled" and design_api._carving("spool-test") is None


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
            if k == 0:
                emit("carving", "carving the printed PETG in 7 steps (as drawn, then 6 carved)")
            emit("checking", f"step {k % 7}: {k}% of the printed part carved away", progress=k / 500)
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
    assert re.fullmatch(r"a carve is already running: step [1-7] of 7", second.json()["detail"]), second.json()
    # the page finds it again after a redraw or a reload
    state = c.get(f"/api/designs/{slug}").json()
    assert state["carving"] == {"job": first.json()["job_id"], "part": "stool", "stopping": False}
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
    said = []
    with pytest.raises(jobs.Cancelled):
        carve.study(store, "stool", stations=4, remove_up_to=0.4, stop=stop, emit=lambda k, t="", **d: said.append(t))
    (rec,) = carve.list_runs(store)
    assert rec["status"] == "cancelled" and len(rec["stations"]) == 2 and rec["steps"] == 4
    assert "carving the printed PETG (printed) in 4 steps (as drawn, then 3 carved)" in said
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
    out = _run(_page(["carveView", "carveChart", "carveProgress", "carveTime", "carveBlocked", "defaultCheck"],
                     ["CARVE_PER_CHECK_AT_LEAST", "minutesText", "verdictTone", "holdsHere"], """
const esc = (s) => String(s);
const S = { carveJob: {}, station: null };
const carveRuns = () => [];
const loadRuns = () => [{ version: 3, spacing_mm: 4.6, seconds: 90, cases: [{ fea: { supported: true } }] }];
const p = { id: 'stool', version: 3, carved: false };
const before = carveView(p);
S.carveJob.stool = { job: 'j1', text: 'step 2: 20% of the printed part carved away', step: 2, steps: 7, progress: 0.4,
                     t0: Date.now() - 600000, p0t: Date.now() - 300000, p0: 0.1 };
out = { before, during: carveView(p) };
"""))
    assert "a few minutes" not in out["before"] and 'id="carveGo" >' in out["before"]
    assert "at least about 68 min at this size" in out["before"]               # 90 s x 45
    during = out["during"]
    assert 'id="carveGo" disabled' in during
    assert "step 3 of 7: 20% of the printed part carved away" in during and 'width:40%' in during
    assert "about 10 min left" in during                       # 0.3 of the way in 5 min: 0.6 to go, 10 min
    assert 'id="carveStop"' in during and ">Cancel<" in during


def _page(names, consts=(), extra=""):
    """Those functions of design.js (and its ``const`` lines named in ``consts``), with ``extra`` after, as one node
    script; prints what the script leaves in ``out``."""
    src = open(JS).read()
    lines = [re.search(rf"^const {c} = .*?;\n(?=\S)", src, re.M | re.S).group(0) for c in consts]
    return "\n".join(lines + [_fn(src, n) for n in names]) + "\nlet out;\n" + extra + "\nconsole.log(JSON.stringify(out));"


def _run(script):
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_label_goes_by_this_version_s_default_check_and_never_promises_a_time():
    """#102 review, the blocker: "about 10 min" for a tube whose sweep alone took 30; "3 min" or "42 h" on the bar stool,
    from whichever check was latest. It goes by this version's default-voxel check (a finer one asked for is always
    finer), says "at least" until a carve has finished, and says nothing when the check didn't connect."""
    out = _run(_page(["carveTime", "carveBlocked", "defaultCheck"], ["CARVE_PER_CHECK_AT_LEAST", "minutesText"], """
const S = {};
const p = { id: 'stool', version: 3 };
let carves = [], checks = [];
const carveRuns = () => carves, loadRuns = () => checks;
const joined = [{ fea: { supported: true } }], cut = [{ fea: { supported: false } }];
out = {};
out.none = carveTime(p);
checks = [{ version: 3, spacing_mm: 2.3, seconds: 2350, cases: joined },        // a finer run, the latest
          { version: 3, spacing_mm: 4.6, seconds: 20, cases: joined },
          { version: 2, spacing_mm: 9.0, seconds: 1, cases: joined }];           // an older version
out.floor = carveTime(p);
checks[1].cases = cut;
out.cut = carveTime(p);
carves = [{ status: 'cancelled', seconds: 60 }, { status: 'done', seconds: 1800 }];
out.blocked = carveTime(p);                    // still not connected: why it can't run wins over a past carve's time
checks[1].cases = joined;
out.done = carveTime(p);
checks[1].too_thin = true;
out.thin = carveTime(p);
"""))
    assert out["none"] == "check it holds first: how long it takes comes from that"
    assert out["floor"] == "at least about 15 min at this size"                 # 20 s x 45, never 2350 s x anything
    assert out["cut"] == "its voxels don't connect the load to a support yet, so a carve can't run"
    assert out["done"] == "about 30 min at this size, as its last carve took"
    assert out["blocked"] == out["cut"]                                       # #102's note: the reason, not a time
    assert out["thin"] == "Its walls are too thin for the voxel check at this size, so it can't be carved by strength"


PANEL = ["runCarve", "followCarve", "carveProgress", "paintCarve", "wireCarve"]
STUBS = """
const S = { carveJob: {}, scope: 'stool', design: {} };
const esc = (s) => String(s), $ = () => null, showErr = () => {}, clearStation = () => {}, showStation = () => {};
const document = { querySelectorAll: () => [] };
const loadRuns = () => [], carveRuns = () => [];
let posts = 0, followed = [], refreshed = 0;
async function api(method, url) { if (url.endsWith('/carve')) posts += 1; return { job_id: 'j1' }; }
function follow(id, onEvent) { followed.push(id); S.onEvent = onEvent; return new Promise(() => {}); }
async function refresh() { refreshed += 1; }
const p = { id: 'stool', version: 3 };
"""


def test_a_second_click_while_the_first_is_in_flight_sends_nothing():
    """#93, the page's own guard: one click sent two POSTs 11 ms apart on Theo's run."""
    out = _run(_page(PANEL, extra=STUBS + """
runCarve(p); runCarve(p);                 // a double click: the second lands before the first's POST returns
await new Promise((r) => setTimeout(r, 20));
runCarve(p);
await new Promise((r) => setTimeout(r, 20));
out = { posts, followed };
"""))
    assert out == {"posts": 1, "followed": ["j1"]}


def test_after_a_reload_the_page_follows_the_running_carve_and_keeps_stopping():
    """#102 review: a reload while it was stopping drew the step it was on and an enabled Cancel."""
    out = _run(_page(PANEL, extra=STUBS + """
S.design.carving = { job: 'j9', part: 'stool', stopping: true };
wireCarve(p);                              // what a redraw after a reload does
const panel = carveProgress('stool');
S.carveJob = {};
S.design.carving = { job: 'j8', part: 'stool', stopping: false };
wireCarve(p);
S.onEvent({ kind: 'checking', text: 'step 2: 20% of the printed part carved away', progress: 0.5 });
S.onEvent({ kind: 'carving', text: 'carving the printed PETG in 7 steps (as drawn, then 6 carved)' });
const live = carveProgress('stool');
S.onEvent({ kind: 'stopping', text: 'stopping at the next step…' });
out = { followed, panel, live, after: carveProgress('stool') };
"""))
    assert out["followed"] == ["j9", "j8"]
    assert "stopping at the next step…" in out["panel"] and 'id="carveStop" disabled' in out["panel"]
    assert "step 3 of 7" in out["live"], out["live"]                              # one count: step 2 is the third of 7
    assert "stopping at the next step…" in out["after"] and 'id="carveStop" disabled' in out["after"]
