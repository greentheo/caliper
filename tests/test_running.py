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
const document = { querySelectorAll: (q) => (q.includes('[data-job]') ? Object.values(made).filter((m) => m.dataset.job) : []) };
const esc = (s) => String(s);
const JOB_NAME = { load: 'Strength check', lighten: 'Lighten', release: 'Build package' };
const JOB_BOX = { load: 'lProgress', lighten: 'lightProgress', release: 'relProgress' };
const JOB_GO = { load: 'lGo', lighten: 'lightGo', release: 'relGo' };
const jobsHere = () => Object.values(S.tracked).filter((t) => t.slug === S.slug);
const trackedFor = (kind, part) => jobsHere().find((t) => t.kind === kind && (t.part || null) === (part || null));
let events, finish, fail, follows = 0, refreshed = 0;
const follow = (id, on) => { follows += 1; events = on; return new Promise((r, x) => { finish = r; fail = x; }); };
const refresh = () => { refreshed += 1; };
"""


def _run(names, body):
    src = open(JS).read()
    script = HEAD + "".join(_fn(src, n) for n in names) + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


ALL = ("trackJob", "syncRunning", "jobHtml", "paintJobs")


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
