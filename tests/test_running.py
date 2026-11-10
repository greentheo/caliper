"""CALI-138 (#178) — a running study stays on the page: the design's record says what's running, as ``carving`` does for a
carve, and the page draws from it on load and on every redraw. Stubbed: no FEA, no Claude."""

import json
import os
import subprocess
import threading
import time

import pytest

from caliper import jobs, lighten, load_study
from caliper.design import DesignStore

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
pytest.importorskip("cadquery")

BOX = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(40, 20, 10)\n"


def _wait(job, seconds=10):
    end = time.time() + seconds
    while time.time() < end and not job.over:
        time.sleep(0.02)
    assert job.over


@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import design_api as D
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.setattr(D, "_aero_available", lambda: True)
    monkeypatch.setattr(load_study, "blocked", lambda *a, **k: None)
    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    store.write_part("box", BOX, intent="a box")
    other = DesignStore.create("another", base=str(tmp_path / "designs"))
    other.write_part("box", BOX, intent="a box")
    gate, began = threading.Event(), threading.Event()

    def slow(store, part, *, emit=None, stop=None, **k):
        began.set()
        emit("step", "checking the first load", progress=0.25)
        gate.wait(10)
        return {"id": "x"}

    monkeypatch.setattr(load_study, "study", slow)
    monkeypatch.setattr(lighten, "study", slow)
    yield TestClient(create_app()), store.design.slug, other.design.slug, gate, began
    gate.set()
    for r in list(jobs.RUNNERS):
        for j in r.active():
            _wait(j)


def test_the_design_s_record_says_what_s_running(api):
    c, slug, other, gate, began = api
    jid = c.post(f"/api/designs/{slug}/load-study", json={"part": "box"}).json()["job_id"]
    began.wait(5)
    time.sleep(0.05)
    (r,) = c.get(f"/api/designs/{slug}").json()["running"]
    assert r == {"job": jid, "kind": "load", "part": "box", "text": "checking the first load", "waiting": False, "stopping": False}
    assert c.get(f"/api/designs/{other}").json()["running"] == []          # the same part id on another design isn't it
    gate.set()
    _wait(jobs.RUNNER.get(jid))
    assert c.get(f"/api/designs/{slug}").json()["running"] == []


@pytest.mark.parametrize("route,words", [("load-study", "A strength check of this part is already running."),
                                         ("lighten", "A Lighten of this part is already running.")])
def test_a_second_click_says_it_s_already_running(api, route, words):
    c, slug, other, gate, began = api
    first = c.post(f"/api/designs/{slug}/{route}", json={"part": "box"})
    assert first.status_code == 200
    second = c.post(f"/api/designs/{slug}/{route}", json={"part": "box"})
    assert second.status_code == 409 and second.json()["detail"] == words
    assert c.post(f"/api/designs/{other}/{route}", json={"part": "box"}).status_code == 200   # another design may
    gate.set()


def test_a_second_build_package_says_so(api, monkeypatch):
    from caliper import design_api as D
    from caliper import release

    c, slug, _, gate, _ = api
    monkeypatch.setattr(release, "make", lambda *a, **k: gate.wait(10))
    monkeypatch.setattr(D.cutplan, "available", lambda: None)
    first = c.post(f"/api/designs/{slug}/release")
    assert first.status_code == 200, first.json()
    assert c.get(f"/api/designs/{slug}").json()["running"][0]["kind"] == "release"
    second = c.post(f"/api/designs/{slug}/release")
    assert second.status_code == 409 and second.json()["detail"] == "A build package is already being made."
    gate.set()


def test_a_finished_job_may_run_again(api):
    c, slug, _, gate, _ = api
    gate.set()
    first = c.post(f"/api/designs/{slug}/load-study", json={"part": "box"}).json()["job_id"]
    _wait(jobs.RUNNER.get(first))
    assert c.post(f"/api/designs/{slug}/load-study", json={"part": "box"}).status_code == 200


def test_a_waiting_job_reads_as_waiting(api, monkeypatch):
    c, slug, _, gate, began = api

    def waits(store, part, *, emit=None, stop=None, **k):
        emit("waiting", "Waiting for another strength study on this server to finish.")
        began.set()
        gate.wait(10)

    monkeypatch.setattr(load_study, "study", waits)
    c.post(f"/api/designs/{slug}/load-study", json={"part": "box"})
    began.wait(5)
    time.sleep(0.05)
    assert c.get(f"/api/designs/{slug}").json()["running"][0]["waiting"] is True


HEAD = """
const S = { slug: 'a', scope: 'p', tracked: {}, design: { running: [] } };
const made = {};
const el = (id) => (made[id] = made[id] || { innerHTML: '', dataset: {}, disabled: false, title: '', id });
let onScreen = { jobNote: true, lProgress: true, lGo: true, relProgress: false, relGo: false, lightProgress: false, lightGo: false, lFiner: false };
const $ = (id) => (onScreen[id] ? el(id) : null);
const offers = [], asked = [];
const document = { querySelectorAll: (q) => { asked.push(q);
  return q.includes('[data-job]') ? Object.values(made).filter((m) => m.dataset.job)
    : q.includes('[data-job-off]') ? [...Object.values(made), ...offers].filter((m) => m.dataset.jobOff)
      : q.includes('data-better-action') ? offers : []; } };
const esc = (s) => String(s);
const JOB_NAME = { load: 'Strength check', lighten: 'Lighten', release: 'Build package' };
const JOB_BOX = { load: 'lProgress', lighten: 'lightProgress', release: 'relProgress' };
const JOB_GO = { load: 'lGo', lighten: 'lightGo', release: 'relGo' };
const jobsHere = () => Object.values(S.tracked).filter((t) => t.slug === S.slug);
const trackedFor = (kind, part) => jobsHere().find((t) => t.kind === kind && (t.part || null) === (part || null));
let events, finish, fail, follows = 0, refreshed = 0;
const follow = (id, on) => { follows += 1; events = on; return new Promise((r, x) => { finish = r; fail = x; }); };
let refreshFails = 0;
const refresh = () => { refreshed += 1; return refreshFails-- > 0 ? Promise.reject(new Error('Failed to fetch')) : Promise.resolve(); };
const posts = [];
let record = { running: [] }, apiFails = false;
const api = async (m, u) => { posts.push(`${m} ${u}`); if (apiFails) throw new Error('Failed to fetch'); return record; };
const showErr = () => {};
const tick = () => new Promise((r) => setImmediate(r));
"""


def _run(names, body):
    src = open(JS).read()
    script = HEAD + "".join(_fn(src, n) for n in names) + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


ALL = ("trackJob", "jobOver", "rereadWhenBack", "pollRunning", "syncRunning", "jobPart", "jobOff", "jobHtml", "paintJobs", "cancelJob")


def test_a_job_on_the_record_is_followed_once_however_often_it_redraws():
    got = _run(ALL, """S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'going', waiting: false }];
        syncRunning(); syncRunning();
        return { follows, tracked: Object.keys(S.tracked) };""")
    assert got == {"follows": 1, "tracked": ["j1"]}


def test_the_panel_shows_it_and_its_button_is_off():
    got = _run(ALL, """S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'step 2', waiting: false }];
        syncRunning(); paintJobs();
        return { box: el('lProgress').innerHTML, off: el('lGo').disabled, why: el('lGo').title };""")
    assert "step 2" in got["box"] and got["off"] is True and "running" in got["why"]


def test_with_its_panel_not_on_screen_it_says_so_at_the_top():
    got = _run(ALL, """onScreen.lProgress = false; onScreen.lGo = false;
        S.scope = null;
        S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'step 2', waiting: false }];
        syncRunning(); paintJobs();
        return { note: el('jobNote').innerHTML };""")
    assert "Strength check of p: step 2" in got["note"]


def test_cancel_shows_only_while_it_waits():
    got = _run(ALL, """const t = { job: 'j1', kind: 'load', part: 'p', text: 'x', waiting: true };
        const on = jobHtml(t, false); t.waiting = false;
        return { on: on.includes('data-job-cancel'), off: jobHtml(t, false).includes('data-job-cancel') };""")
    assert got == {"on": True, "off": False}


def test_a_job_s_events_move_the_line():
    got = _run(ALL, """trackJob('j1', { kind: 'load', part: 'p', text: 'starting' });
        events({ kind: 'waiting', text: 'waiting for its turn' });
        const waiting = el('lProgress').innerHTML;
        events({ kind: 'step', text: 'first load', progress: 0.5 });
        return { waiting: waiting.includes('Cancel'), now: el('lProgress').innerHTML };""")
    assert got["waiting"] is True and "first load" in got["now"] and "width:50%" in got["now"] and "Cancel" not in got["now"]


def test_when_it_ends_the_box_clears_and_the_design_redraws():
    got = _run(ALL, """S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'x', waiting: false }];
        syncRunning(); syncRunning(); paintJobs();              // a redraw before it ends mustn't refresh twice after
        finish(); await S.tracked.j1.done; await null;
        return { box: el('lProgress').innerHTML, refreshed, tracked: Object.keys(S.tracked) };""")
    assert got == {"box": "", "refreshed": 1, "tracked": []}


def test_ending_after_the_design_was_left_doesn_t_redraw_the_other():
    got = _run(ALL, """S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'x', waiting: false }];
        syncRunning();
        const t = S.tracked.j1;
        S.slug = 'b';
        finish(); await t.done; await null;
        return { refreshed };""")
    assert got == {"refreshed": 0}


def test_another_design_s_job_isn_t_drawn_here():
    got = _run(ALL, """S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'x', waiting: false }];
        syncRunning();
        S.slug = 'b'; paintJobs();
        return { note: el('jobNote').innerHTML, off: el('lGo').disabled };""")
    assert got["note"] == ""


def test_every_redraw_looks_again():
    src = open(JS).read()
    assert "syncRunning();" in _fn(src, "render") and "paintJobs();" in _fn(src, "renderInspector")


def test_the_numbers_panel_survives_a_design_being_left():
    """Found checking this in the browser: S.design is null while a design loads, and this ran on a timer."""
    src = open(JS).read()
    script = "const S = { design: null, params: null }; const api = () => { throw new Error('asked'); };\n" + _fn(src, "loadParams") + _fn(src, "paramView") + """
loadParams({ id: 'p', version: 1 }).then(() => console.log(paramView({ id: 'p', scripted: true }) === '' ? 'ok' : 'drew'), (e) => console.log(e.message));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.stdout.strip() == "ok", got.stderr


# --- the review of #186 ---------------------------------------------------------------------------------------------------
RUNNING = "S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'x', waiting: false }]; syncRunning(); paintJobs(); const t = S.tracked.j1;"


def test_the_cancel_button_asks_the_server():
    got = _run(ALL, """const b = { dataset: { jobCancel: 'j1' }, disabled: false };
        cancelJob({ target: { closest: () => b } });
        cancelJob({ target: { closest: () => null } });
        await tick();
        return { posts, off: b.disabled };""")
    assert got == {"posts": ["POST /api/jobs/j1/cancel"], "off": True}


def test_a_cancelled_job_gives_the_button_back_and_re_reads():
    got = _run(ALL, RUNNING + """const was = el('lGo').disabled;
        fail(new Error('cancelled')); await t.done.catch(() => {}); await tick();
        return { was, off: el('lGo').disabled, title: el('lGo').title, refreshed, tracked: Object.keys(S.tracked), record: S.design.running };""")
    assert got == {"was": True, "off": False, "title": "", "refreshed": 1, "tracked": [], "record": []}


def test_what_was_off_for_its_own_reasons_stays_off():
    got = _run(ALL, "el('lGo').disabled = true; " + RUNNING + """
        fail(new Error('x')); await t.done.catch(() => {}); await tick();
        return { off: el('lGo').disabled };""")
    assert got == {"off": True}


def test_finer_goes_off_and_comes_back():
    got = _run(ALL, "onScreen.lFiner = true; " + RUNNING + """const was = el('lFiner').disabled;
        finish(); await t.done; await tick();
        return { was, now: el('lFiner').disabled };""")
    assert got == {"was": True, "now": False}


def test_its_offer_on_the_card_goes_off_and_comes_back():
    got = _run(ALL, "const o = { dataset: {}, disabled: false, title: '' }; offers.push(o); " + RUNNING + """const was = o.disabled;
        const q = asked.find((x) => x.includes('data-better-action'));
        fail(new Error('x')); await t.done.catch(() => {}); await tick();
        return { was, now: o.disabled, q };""")
    assert got == {"was": True, "now": False, "q": '#inspector [data-better-action="load"][data-better-part="p"]'}


def test_an_offer_drawn_off_for_a_job_is_given_back_too():
    src = open(JS).read()
    assert """trackedFor(ln.action, ln.part) ? ' disabled data-job-off="1"' : ''""" in _fn(src, "betterLines")


def test_a_server_that_s_gone_is_no_red_bar_and_it_tries_again():
    # an unhandled rejection would end node with an error, and _run says so
    got = _run(ALL, "globalThis.setTimeout = (f) => f(); refreshFails = 2; " + RUNNING + """
        fail(new Error('Failed to fetch'));                     // nothing here catches it, so nothing but the page can
        for (let i = 0; i < 6; i += 1) await tick();
        return { refreshed, off: el('lGo').disabled };""")
    assert got == {"refreshed": 3, "off": False}


def test_it_stops_trying_when_the_design_is_left():
    got = _run(ALL, """globalThis.setTimeout = (f) => { S.slug = 'b'; f(); }; refreshFails = 5; """ + RUNNING + """
        fail(new Error('Failed to fetch')); await t.done.catch(() => {});
        for (let i = 0; i < 6; i += 1) await tick();
        return { refreshed };""")
    assert got == {"refreshed": 1}


def test_nothing_running_asks_the_server_nothing():
    assert _run(ALL, "await pollRunning(); return { posts };") == {"posts": []}


def test_the_poll_picks_up_a_job_from_another_tab():
    got = _run(ALL, RUNNING + """record = { running: [{ job: 'j1', kind: 'load', part: 'p', text: 'x' }, { job: 'j2', kind: 'lighten', part: 'p', text: 'y' }] };
        await pollRunning();
        return { posts, tracked: Object.keys(S.tracked) };""")
    assert got == {"posts": ["GET /api/designs/a/running"], "tracked": ["j1", "j2"]}


def test_a_job_the_record_has_lost_is_dropped_on_the_second_look():
    got = _run(ALL, RUNNING + """await pollRunning(); const once = Object.keys(S.tracked);
        await pollRunning(); await tick();
        return { once, twice: Object.keys(S.tracked), off: el('lGo').disabled, refreshed };""")
    assert got == {"once": ["j1"], "twice": [], "off": False, "refreshed": 1}


def test_a_job_seen_again_starts_the_count_over():
    got = _run(ALL, RUNNING + """await pollRunning();
        record = { running: [{ job: 'j1', kind: 'load', part: 'p', text: 'x' }] }; await pollRunning();
        record = { running: [] }; await pollRunning();
        return { tracked: Object.keys(S.tracked) };""")
    assert got == {"tracked": ["j1"]}


def test_a_poll_that_fails_leaves_the_job_to_its_follower():
    got = _run(ALL, RUNNING + "apiFails = true; await pollRunning(); await pollRunning(); return { tracked: Object.keys(S.tracked) };")
    assert got == {"tracked": ["j1"]}


def test_a_poll_answered_after_the_design_was_left_changes_nothing():
    got = _run(ALL, RUNNING + """const p = pollRunning(); S.slug = 'b'; await p;
        return { still: S.design.running.length, tracked: Object.keys(S.tracked) };""")
    assert got == {"still": 1, "tracked": ["j1"]}


def test_the_page_polls_on_a_timer():
    assert "setInterval(pollRunning, 5000);" in open(JS).read()


def test_the_cancel_button_is_listened_for():
    assert "$('inspector').addEventListener('click', cancelJob);" in open(JS).read()


def test_a_panel_folded_away_isn_t_on_screen_so_the_top_line_says_it():
    got = _run(ALL, """el('lProgress').closest = (q) => (q === 'details:not([open])' ? {} : null);
        S.design.running = [{ job: 'j1', kind: 'load', part: 'p', text: 'waiting', waiting: true }]; syncRunning(); paintJobs();
        return { note: el('jobNote').innerHTML, box: el('lProgress').innerHTML };""")
    assert "Strength check of p: waiting" in got["note"] and "data-job-cancel" in got["note"] and got["box"] == ""


def test_the_top_line_uses_the_part_s_name():
    got = _run(ALL, """S.design.parts = [{ id: 'p', name: 'seat top' }];
        return { h: jobHtml({ job: 'j', kind: 'load', part: 'p', text: 'x' }, true) };""")
    assert "Strength check of seat top: x" in got["h"]


# a check finishing with another design open, same part id
LOAD = """globalThis.loadRuns = () => [{ cases: [{ heat: 1, safety: 2 }] }];
globalThis.showHeat = () => { showed += 1; }; globalThis.clearStation = () => { cleared += 1; };
let showed = 0, cleared = 0; let end, die;
globalThis.trackJob = () => ({ done: new Promise((r, x) => { end = r; die = x; }) });
S.loadRun = {}; onScreen.lFiner = true; el('lSafety').value = 2; onScreen.lSafety = true; record = { job_id: 'j1' };
const go = startLoad({ id: 'p' }); await tick();
"""


def test_a_check_finishing_on_another_design_leaves_this_one_alone():
    got = _run(("startLoad",), LOAD + "S.slug = 'b'; end(); await go; return { showed, cleared, run: S.loadRun.p ?? null, refreshed };")
    assert got == {"showed": 0, "cleared": 0, "run": None, "refreshed": 0}


def test_a_check_finishing_here_shows_its_stress():
    got = _run(("startLoad",), LOAD + "end(); await go; return { showed, cleared, run: S.loadRun.p };")
    assert got == {"showed": 1, "cleared": 1, "run": 0}


def test_a_refused_check_re_reads_and_says_why():
    got = _run(("startLoad",), LOAD.replace("record = { job_id: 'j1' };", "apiFails = true;") + """await go;
        return { refreshed, said: el('lProgress').innerHTML, off: el('lGo').disabled };""")
    assert got["refreshed"] == 1 and "Failed to fetch" in got["said"] and got["off"] is False


def test_a_lighten_finishing_on_another_design_leaves_this_one_alone():
    got = _run(("startLighten",), """globalThis.lightenRuns = () => []; let cleared = 0; globalThis.clearStation = () => { cleared += 1; };
        globalThis.loadRuns = () => []; let end; globalThis.trackJob = () => ({ done: new Promise((r) => { end = r; }) });
        onScreen.lightProgress = true; onScreen.lightGo = true; record = { job_id: 'j1' };
        const go = startLighten({ id: 'p' }, false); await tick(); S.slug = 'b'; end(); await go;
        return { cleared, refreshed };""")
    assert got == {"cleared": 0, "refreshed": 0}


# --- a build package stops when it's asked to ---------------------------------------------------------------------------
def test_cancelling_a_waiting_build_package_stops_it(api, monkeypatch):
    from caliper import design_api as D
    from caliper import release

    c, slug, _, gate, _ = api
    wrote = []

    def make(store, *, emit=None, stop=None, **k):
        emit("waiting", "waiting for its turn")
        gate.wait(10)
        stop()
        wrote.append(1)

    monkeypatch.setattr(release, "make", make)
    monkeypatch.setattr(D.cutplan, "available", lambda: None)
    job = c.post(f"/api/designs/{slug}/release").json()["job_id"]
    c.post(f"/api/jobs/{job}/cancel")
    gate.set()
    end = time.time() + 10
    while time.time() < end and c.get(f"/api/jobs/{job}").json()["status"] not in ("cancelled", "done", "error"):
        time.sleep(0.02)
    assert c.get(f"/api/jobs/{job}").json()["status"] == "cancelled" and wrote == []


def _no_cut_plans(monkeypatch):
    from caliper import cutplan

    monkeypatch.setattr(cutplan, "available", lambda: None)
    monkeypatch.setattr(cutplan, "list_runs", lambda store, pid: [{"version": store.design.part(pid).version, "id": "x"}])


@pytest.fixture
def built(tmp_path):
    from .test_construction import BOX as BUILT

    store = DesignStore.create("a crate", base=str(tmp_path / "designs"))
    store.write_part("crate", BUILT, intent="an open crate")
    return store


def _nothing_released(store):
    from caliper import release

    return not os.path.isdir(release.releases_dir(store)) or not os.listdir(release.releases_dir(store))


def test_a_stop_while_scoring_writes_no_release(built, monkeypatch):
    from caliper import release, scorecard

    _no_cut_plans(monkeypatch)
    got = []

    def compute(store, emit=None, stop=None):
        got.append(stop)
        raise jobs.Cancelled()                                  # what a waiting check raises when it's told to stop

    monkeypatch.setattr(scorecard, "compute", compute)

    def stop():
        pass

    with pytest.raises(jobs.Cancelled):
        release.make(built, pdf=False, stop=stop)
    assert got == [stop] and _nothing_released(built)


def test_a_stop_after_the_score_still_writes_no_release(built, monkeypatch):
    from caliper import release, scorecard

    _no_cut_plans(monkeypatch)
    state = {"asked": False}

    def compute(store, emit=None, stop=None):
        state["asked"] = True                                   # the score's done, and the Cancel comes now
        return {"metrics": {}}

    def stop():
        if state["asked"]:
            raise jobs.Cancelled()

    monkeypatch.setattr(scorecard, "compute", compute)
    with pytest.raises(jobs.Cancelled):
        release.make(built, pdf=False, stop=stop)
    assert _nothing_released(built)


def test_a_stop_during_the_strength_check_isn_t_a_check_that_couldn_t_run(built, monkeypatch):
    from caliper import scorecard

    built.write_part("crate", built.read_script("crate") + "\ndef loads(params):\n    return []\n", intent="an open crate")

    def study(store, part, *, emit=None, stop=None, **k):
        stop()
        return {"cases": []}

    def stop():
        raise jobs.Cancelled()

    calls = []
    monkeypatch.setattr(load_study, "study", study)
    monkeypatch.setattr(load_study, "list_runs", lambda *a, **k: [])
    with pytest.raises(jobs.Cancelled):
        scorecard.compute(built, stop=lambda: calls.append(1) or stop())
    assert calls


@pytest.mark.parametrize("kind,word,number", [("unchecked", "not checked", False), ("unresolved", "not resolved", False), ("untrusted", "not trusted", False),
                                              ("holds", "it holds", True), ("fails", "it doesn't hold", True)])
def test_the_last_line_has_a_number_only_beside_a_result(kind, word, number):
    got = load_study.done_words(1, {"kind": kind, "word": "w"}, 2.67)
    assert word in got and ("2.67x" in got) is number


# --- what's running is by part, not by design ---------------------------------------------------------------------------
@pytest.mark.parametrize("route", ["load-study", "lighten"])
def test_a_second_part_of_the_same_design_may_run_beside_the_first(api, route):
    from caliper.design import DesignStore as Store

    c, slug, _, gate, began = api
    store = Store.load(os.path.join(os.environ["CALIPER_DESIGNS"], slug))
    store.write_part("lid", BOX, intent="a lid")
    first = c.post(f"/api/designs/{slug}/{route}", json={"part": "box", "min_safety": 2})
    second = c.post(f"/api/designs/{slug}/{route}", json={"part": "lid", "min_safety": 2})
    assert first.status_code == 200 and second.status_code == 200, second.json()
    gate.set()


def test_the_record_alone_can_be_asked_for(api):
    c, slug, _, gate, began = api
    assert c.get(f"/api/designs/{slug}/running").json() == {"running": []}
    c.post(f"/api/designs/{slug}/load-study", json={"part": "box", "min_safety": 2})
    began.wait(5)
    (r,) = c.get(f"/api/designs/{slug}/running").json()["running"]
    assert r["kind"] == "load" and r["part"] == "box"
    gate.set()
