"""CALI-216 (#363): a running job is plain to see. The part's view and panel grey over, and the top right of the view shows
a large spinner, how long it's run, what's running on which part, its step in words and its bar.

Theo, 2026-11-20, after Fix these on step-stool-5: "the indicator is really pretty small and hard to see ... making the main
part screen grey and not working with some circle/timer indicator in the upper right corner ... some text below it to say
what it's currently doing". One overlay for every job (check, Fix these, Lighten, carve, cut plan, Shape for drag, a chat
turn), drawn from what the page follows. The chat and other designs stay usable. Stubbed: no FEA, no Claude."""

import json
import os
import re
import subprocess
import threading
import time

import pytest

from caliper import design_api, jobs
from caliper.design import DesignStore

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
CSS = JS.replace("design.js", "design.css")
HTML = JS.replace("design.js", "index.html")


def _consts(src):
    """The page's own STOPS (one line) and BUSY_DOING (to its closing brace)."""
    return (re.search(r"^const STOPS = .*$", src, re.M).group(0) + "\n"
            + re.search(r"^const BUSY_DOING = \{.*?\};$", src, re.M | re.S).group(0) + "\n")


def _run(body, names=("busyJobs", "busyTitle", "clock", "busyStep", "busyHtml"), head=""):
    src = open(JS).read()
    script = ("const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\"/g, '&quot;');\n"
              + _consts(src) + head + "".join(_fn(src, n) for n in names)
              + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


# --- what's shown, and which --------------------------------------------------------------------------------------------
def test_the_part_on_screen_s_job_is_the_big_one_and_the_rest_are_listed():
    got = _run("""const jobs = [{ job: 'a', kind: 'lighten', part: 'side' }, { job: 'b', kind: 'load', part: 'stool' },
                                { job: 'c', kind: 'firstrun', part: null }];
                  const r = busyJobs(jobs, 'stool'), none = busyJobs(jobs, null);
                  return { main: r.main.job, more: r.more.map((t) => t.job), unscoped: none.main.job, empty: busyJobs([], 'stool') };""")
    assert got == {"main": "b", "more": ["a"], "unscoped": "a", "empty": {"main": None, "more": []}}   # a first build has its bubble


@pytest.mark.parametrize("kind,part,words", [
    ("load", "Step stool", "Checking Step stool"), ("fix", "Step stool", "Fixing Step stool"),
    ("lighten", "Step stool", "Lightening Step stool"), ("carve", "cone", "Carving cone"),
    ("cutplan", "Step stool", "Making the cut plan for Step stool"), ("aero", "cargo box", "Shaping cargo box for drag"),
    ("chat", "Step stool", "Working on Step stool"), ("chat", None, "Working on your message"),
    ("release", None, "Making the build package"), ("mystery", "x", "Working on x")])
def test_it_says_what_s_running_on_which_part(kind, part, words):
    assert _run(f"return busyTitle({{ kind: '{kind}', part: {json.dumps(part)} }}, {json.dumps(part)});") == words


@pytest.mark.parametrize("s,shown", [(0, "0:00"), (7.9, "0:07"), (750, "12:30"), (3725, "1:02:05"), (-3, "0:00")])
def test_the_clock(s, shown):
    assert _run(f"return clock({s});") == shown


def test_the_overlay_has_the_spinner_clock_words_step_and_bar():
    got = _run("""return busyHtml({ job: 'j1', kind: 'load', part: 'step_stool', t0: 1000, text: 'stepping on the front edge: 500 lb × 2',
                                    progress: 0.4, stoppable: true }, [], 66000, () => 'Step stool');""")
    assert 'class="busy-spin"' in got and ">1:05<" in got and "Checking Step stool…" in got
    assert "stepping on the front edge: 500 lb × 2" in got
    assert 'role="progressbar"' in got and 'aria-valuenow="40"' in got and "width:40%" in got
    assert 'data-job-cancel="j1">Stop it<' in got
    assert "Step stool waits till it's done. The chat and your other designs still work." in got


def test_no_count_no_bar_and_only_a_job_that_can_stop_offers_to():
    got = _run("""const one = (x) => busyHtml({ job: 'j', kind: 'cutplan', part: 'p', t0: 0, ...x }, [], 0, (p) => p);
                  return { plain: one({}), waiting: one({ waiting: true }), stopping: one({ kind: 'load', stoppable: true, stopping: true }) };""")
    assert "progressbar" not in got["plain"] and "data-job-cancel" not in got["plain"] and "starting…" in got["plain"]
    assert ">Cancel<" in got["waiting"] and "waiting for another job on this design" in got["waiting"]    # a queued one cancels
    assert "data-job-cancel" not in got["stopping"] and "stopping at the next step…" in got["stopping"]


def test_the_others_running_are_said_under_it():
    got = _run("""return busyHtml({ job: 'a', kind: 'load', part: 'x', t0: 0 }, [{ job: 'b', kind: 'lighten', part: 'side_left', text: 'step 3 of 10' }],
                                  0, (p) => p);""")
    assert "and lightening side_left: step 3 of 10" in got


def test_a_design_wide_job_says_only_the_chat_and_other_designs():
    got = _run("return busyHtml({ job: 'a', kind: 'release', part: null, t0: 0 }, [], 0, (p) => p);")
    assert "Making the build package…" in got and "waits till" not in got and "The chat and your other designs still work." in got


# --- painting it -------------------------------------------------------------------------------------------------------
_DOM = """
let updates = 0; const busyUpdate = () => { updates += 1; };
const el = (id) => ({ id, hidden: true, innerHTML: '', textContent: '', inert: false, attrs: {}, cls: new Set(), dataset: {},
  classList: { toggle(c, on) { on ? this.o.cls.add(c) : this.o.cls.delete(c); } },
  setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } });
const els = Object.fromEntries(['busy', 'busyShade', 'busyLive', 'inspector'].map((k) => [k, el(k)]));
for (const e of Object.values(els)) e.classList.o = e;
const $ = (id) => els[id];
let tracked = [];
const S = { slug: 'step-stool-5', scope: null, design: { parts: [{ id: 'step_stool', name: 'Step stool' }] } };
const jobsHere = () => tracked;
const jobPart = (id) => ((S.design.parts.find((p) => p.id === id)) || {}).name || id;
const view = () => ({ shown: !els.busy.hidden, shade: !els.busyShade.hidden, grey: els.inspector.cls.has('is-busy'), inert: els.inspector.inert,
  busy: els.inspector.attrs['aria-busy'] || null, live: els.busyLive.textContent, html: els.busy.innerHTML });
"""


def _paint(body):
    return _run(body, names=("soleFor", "shownPart", "busyJobs", "busyTitle", "clock", "busyStep", "busyHtml", "paintBusy"), head=_DOM)


def test_the_part_on_screen_greys_and_can_t_be_acted_on_while_its_job_runs():
    got = _paint("""S.scope = 'step_stool'; tracked = [{ job: 'j', kind: 'fix', part: 'step_stool', t0: Date.now(), text: 'fixing 2 things' }];
                    paintBusy(); const on = view(); tracked = []; paintBusy(); return { on, off: view() };""")
    assert got["on"] == {"shown": True, "shade": True, "grey": True, "inert": True, "busy": "true",
                         "live": "Fixing Step stool: fixing 2 things", "html": got["on"]["html"]}
    assert got["off"] == {"shown": False, "shade": False, "grey": False, "inert": False, "busy": None, "live": "", "html": ""}


def test_another_part_s_job_shows_the_overlay_but_leaves_this_panel_usable():
    got = _paint("""S.scope = 'other'; tracked = [{ job: 'j', kind: 'load', part: 'step_stool', t0: Date.now() }];
                    paintBusy(); return view();""")
    assert got["shown"] and not got["grey"] and not got["inert"] and "Checking Step stool" in got["html"]


def test_the_design_view_isn_t_greyed_by_a_job():
    """"The whole design ▸" on a one-part design: the design's view, with nothing of the part's to act on."""
    got = _paint("S.scope = null; S.whole = true; tracked = [{ job: 'j', kind: 'load', part: 'step_stool', t0: Date.now() }]; paintBusy(); return view();")
    assert got["shown"] and not got["grey"]


def test_a_one_part_design_opened_unpicked_greys_its_part_s_view():
    """#364: step-stool-5 opens on its part's view with the chat unscoped (S.scope null). A job on that part greys what's
    on screen, as a picked part does: by shownPart(), not S.scope."""
    got = _paint("""S.scope = null; tracked = [{ job: 'j', kind: 'load', part: 'step_stool', t0: Date.now(), text: 'a' }];
                    paintBusy(); return view();""")
    assert got["grey"] and got["inert"] and got["busy"] == "true"


def test_a_two_part_design_with_nothing_picked_isn_t_greyed():
    got = _paint("""S.scope = null; S.design.parts.push({ id: 'bench', name: 'Bench' });
                    tracked = [{ job: 'j', kind: 'load', part: 'step_stool', t0: Date.now() }]; paintBusy(); return view();""")
    assert got["shown"] and not got["grey"]


def test_the_live_line_is_said_only_when_it_changes():
    got = _paint("""S.scope = 'step_stool'; const t = { job: 'j', kind: 'load', part: 'step_stool', t0: Date.now(), text: 'a' }; tracked = [t];
                    let sets = 0; let v = ''; Object.defineProperty(els.busyLive, 'textContent', { get: () => v, set: (x) => { sets += 1; v = x; } });
                    paintBusy(); paintBusy(); t.text = 'b'; paintBusy(); return { sets, v };""")
    assert got == {"sets": 2, "v": "Checking Step stool: b"}


# --- what feeds it -----------------------------------------------------------------------------------------------------
def test_a_job_keeps_when_it_began_and_whether_it_can_stop():
    src = open(JS).read()
    assert "t0: Date.now()," in _fn(src, "trackJob") and "stoppable: STOPS.has(info.kind)" in _fn(src, "trackJob")
    assert "if (ev.kind === 'stopping') t.stopping = true;" in _fn(src, "trackJob")
    sync = _fn(src, "syncRunning")
    assert "t0: Date.now() - (r.elapsed_s || 0) * 1000" in sync and "stopping: !!r.stopping" in sync   # a reload's clock is the job's


def test_every_part_job_the_page_starts_is_followed_for_the_overlay():
    src = open(JS).read()
    for kind in ("carve", "cutplan", "aero", "chat"):
        assert f"trackJob(job_id, {{ kind: '{kind}'" in src or f"trackJob(jobId, {{ kind: '{kind}'" in src, kind
    for already in ("load", "lighten", "fix", "release"):
        assert f"trackJob(job_id, {{ kind: '{already}'" in src, already


def test_the_small_lines_give_way_and_the_page_is_wired():
    src, css, html = open(JS).read(), open(CSS).read(), open(HTML).read()
    paint = _fn(src, "paintJobs")
    assert "else if (t.kind === 'release') lines.push(jobHtml(t, true));" in paint and paint.rstrip().endswith("paintBusy();\n}")
    assert ".inspector.is-busy :is(#lProgress, #lightProgress, #carveProgress, #aProgress, #cpProgress, #wProgress) { display: none; }" in css
    assert '<div id="busy" class="busy" hidden></div>' in html and 'id="busyLive" class="sr-only" role="status" aria-live="polite"' in html
    assert "$('busy').addEventListener('click', cancelJob);" in src
    assert "if (t) t.textContent = clock((Date.now() - Number(t.dataset.t0)) / 1000);" in src


def test_the_page_and_the_server_agree_on_what_can_stop():
    src = open(JS).read()
    page = set(re.search(r"const STOPS = new Set\(\[([^\]]*)\]\)", src).group(1).replace("'", "").replace(" ", "").split(","))
    assert page == set(design_api.STOPPABLE)
    code = open(design_api.__file__).read()
    for kind in page:                                       # each really stops at its next step
        i = code.index(f'RUNNER.submit("{kind}"')
        assert "stop=j.check" in code[max(0, i - 1500):i], kind


# --- the server's record ------------------------------------------------------------------------------------------------
@pytest.fixture
def held(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    gate = threading.Event()
    made = []

    def submit(kind, part):
        j = jobs.RUNNER.submit(kind, lambda job: (job.emit("step", f"{kind} step one", progress=0.5), gate.wait(10)),
                               label=kind, lock=f"t:{kind}:{store.design.slug}", meta=design_api._on_part(store.design.slug, part))
        made.append(j)
        return j

    yield store.design.slug, submit
    gate.set()
    for j in made:
        end = time.time() + 10
        while not j.over and time.time() < end:
            time.sleep(0.02)


def test_every_job_on_the_design_is_on_its_record_saying_whether_it_can_stop(held):
    slug, submit = held
    for kind in ("carve", "cutplan", "aero", "chat", "fix"):
        submit(kind, "box")
    end = time.time() + 5
    while time.time() < end and len([r for r in design_api._running(slug) if r["text"]]) < 5:
        time.sleep(0.05)
    got = {r["kind"]: r for r in design_api._running(slug)}
    assert set(got) == {"carve", "cutplan", "aero", "chat", "fix"}
    assert {k: r["stoppable"] for k, r in got.items()} == {"carve": True, "cutplan": False, "aero": False, "chat": False, "fix": True}
    assert got["cutplan"]["part"] == "box" and got["cutplan"]["text"] == "cutplan step one"
    assert design_api._running("another-design") == []


def test_a_chat_turn_says_the_part_it_s_on():
    src = open(design_api.__file__).read()
    assert 'RUNNER.submit("chat", work, label=req.message[:60], lock=_lock(slug), meta=_on_part(slug, req.scope or None))' in src


def test_the_panel_s_busy_state_isn_t_the_overlay_s_box():
    """Found on the walk: the panel took the overlay box's .busy rule (absolute, top right) and jumped across the page."""
    css = open(CSS).read()
    assert ".inspector.is-busy {" in css and ".inspector.busy" not in css
    assert "insp.classList.toggle('is-busy', grey);" in _fn(open(JS).read(), "paintBusy")


def test_stop_it_stays_the_same_button_while_the_job_reports():
    """Found on the walk: redrawn on every event, Stop it was replaced under the pointer and a click was lost. Its words and
    bar change in place; it's drawn again only when the job, its state or what else runs changes."""
    src = open(JS).read()
    paint = _fn(src, "paintBusy")
    assert "if (box.dataset.shape !== shape) { box.innerHTML = html; box.dataset.shape = shape; }" in paint
    got = _paint("""S.scope = 'step_stool'; const t = { job: 'j', kind: 'load', part: 'step_stool', t0: Date.now(), text: 'a', stoppable: true };
                    tracked = [t]; paintBusy(); const first = els.busy.innerHTML; els.busy.innerHTML = 'SAME';
                    t.text = 'b'; t.waiting = false; paintBusy(); const kept = els.busy.innerHTML;   // undefined to false isn't new
                    t.stopping = true; paintBusy();
                    return { first: first.includes('Stop it'), kept, updates, redrawn: els.busy.innerHTML.includes('stopping at the next step') };""")
    assert got == {"first": True, "kept": "SAME", "updates": 1, "redrawn": True}    # words in place; a new state, drawn again
    for kept in ("main.job", "!!main.stopping", "!!main.waiting", "!!main.stoppable", "typeof main.progress === 'number'"):
        assert kept in paint


def test_unpicked_the_one_part_s_own_job_is_the_one_shown_big():
    """With two jobs running, the part on screen's goes first, older or not: on a one-part design opened unpicked too."""
    got = _paint("""S.scope = null; tracked = [{ job: 'a', kind: 'load', part: 'bench', t0: Date.now() - 60000, text: 'older' },
                                          { job: 'b', kind: 'fix', part: 'step_stool', t0: Date.now(), text: 'fixing it' }];
                    paintBusy(); return view();""")
    assert got["live"] == "Fixing Step stool: fixing it"
