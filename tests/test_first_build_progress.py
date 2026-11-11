"""CALI-154 (#218) — a first build says what it's doing from the start, after a reload, and after a design switch."""

import os
import re
import threading
import time

import pytest

from caliper import authoring, chat, design_api, firstrun, jobs
from caliper.design import DesignStore

from .test_carve_click import JS, _fn, _run


@pytest.fixture
def building(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path))
    store = DesignStore.create("a step stool", base=str(tmp_path))
    slug = os.path.basename(store.root)
    monkeypatch.setattr(design_api, "RUNNER", jobs.JobRunner())
    go = threading.Event()

    def build(store, emit, **k):
        emit("step", "Building it", step="build", part="stool")
        emit("authoring", "authoring stool: third try", part="stool", round=3, rounds=4)
        go.wait(5)
        return {"ok": True}

    monkeypatch.setattr(firstrun, "build", build)
    job = design_api.first_build(slug)
    for _ in range(200):
        if any(e["kind"] == "authoring" for e in job.since(0)):
            break
        time.sleep(0.01)
    yield slug, job
    go.set()


def test_a_first_build_is_on_the_record_with_what_its_doing_and_how_long(building):
    slug, job = building
    (got,) = design_api._running(slug)
    assert got["job"] == job.id and got["kind"] == "firstrun" and got["text"] == "authoring stool: third try"
    assert got["elapsed_s"] >= 0


def test_a_first_build_is_only_on_its_own_designs_record(building):
    assert design_api._running("another-design") == []


class _Twice:
    """A designer whose first two scripts don't build."""

    def __init__(self):
        self.calls = 0

    def __call__(self, spec, feedback, prior):
        self.calls += 1
        if self.calls < 3:
            return "def build(params):\n    raise ValueError('no')\n"
        return "import cadquery as cq\n\n\ndef build(params):\n    return cq.Workplane().box(10, 10, 10)\n"


def test_each_authoring_round_after_the_first_is_said(tmp_path):
    pytest.importorskip("cadquery")
    store = DesignStore.create("a block", base=str(tmp_path))
    seen = []
    chat.author_part(store, "block", "a block", author=_Twice(), use_llm=False, on_event=seen.append, promote_feedback=False)
    rounds = [(e.data["round"], e.data["rounds"], e.text) for e in seen if e.kind == "authoring" and "round" in e.data]
    assert [r[0] for r in rounds] == [2, 3] and rounds[0][1] == 4
    assert "second try" in rounds[0][2] and "third try" in rounds[1][2]


def test_improve_says_each_round_it_starts():
    pytest.importorskip("cadquery")
    from caliper.spec import Spec

    got = []
    authoring.improve(Spec(part="b", intent="a block"), author=_Twice(), on_round=lambda n, most: got.append((n, most)))
    assert got == [(1, 4), (2, 4), (3, 4)]


def test_the_page_knows_every_step_a_first_build_emits():
    here = os.path.dirname(firstrun.__file__)
    steps = set()
    for name in ("firstrun.py", "build_plan.py"):
        with open(os.path.join(here, name)) as f:
            steps |= set(re.findall(r'step="(\w+)"', f.read()))
    src = open(JS).read()
    known = set(re.findall(r"(\w+): '", re.search(r"const BUILD_STEPS = \{(.*?)\};", src, re.S).group(1)))
    assert steps - {"done", "built"} <= known, steps - known


@pytest.mark.parametrize("s, said", [(3, "3 s"), (59, "59 s"), (60, "1 min 0 s"), (134, "2 min 14 s"), (-4, "0 s")])
def test_how_long_it_has_been_reads_plainly(s, said):
    assert _run(_fn(open(JS).read(), "elapsedText") + f"console.log(JSON.stringify(elapsedText({s})));") == said


@pytest.mark.parametrize("r, said", [(None, "writing the design"), (1, "writing the design"), (2, "writing the design: second try"),
                                     (3, "writing the design: third try"), (4, "writing the design: fourth try"),
                                     (7, "writing the design: try 7")])
def test_the_authoring_line_says_which_try(r, said):
    arg = "undefined" if r is None else r
    assert _run(_fn(open(JS).read(), "authoringWords") + f"console.log(JSON.stringify(authoringWords({arg})));") == said


def _drop(state):
    return _run(f"const S = {state};\nconst sent = {{disabled: true}};\nconst $ = () => sent;\n" + _fn(open(JS).read(), "dropBuildFollow")
                + "dropBuildFollow();\nconsole.log(JSON.stringify([S.following, S.buildFollow || 0, S.busy, S.buildBubble, sent.disabled]));")


def test_a_switch_of_design_lets_the_build_be_followed_again_and_frees_the_other_designs_chat():
    assert _drop("{following: 'j1', buildFollow: 1, busy: true, buildBubble: {}}") == [None, 2, False, None, False]


def test_a_chat_turn_in_flight_keeps_send_off_across_a_switch():
    assert _drop("{following: null, busy: true, buildBubble: null}") == [None, 0, True, None, True]


@pytest.mark.parametrize("fn", ["openDesign", "startNew"])
def test_leaving_a_design_lets_go_of_its_build(fn):
    assert "dropBuildFollow();" in _fn(open(JS).read(), fn)


#: followBuild on a page of stubs: enough DOM for it, a follow() the test finishes, and a clock and a timer it drives.
BUBBLE = r"""
const S = {busy: false, following: null};
const made = [];
function el() {
  const kids = {};
  const e = {className: '', innerHTML: '', isConnected: true, c: [], textContent: '', scrollTop: 0, scrollHeight: 0, dataset: {}, nows: [],
    classList: {add(x) { e.c.push(x); }, toggle() {}, remove(x) { e.removed = x; }, contains: (x) => e.c.includes(x)},
    append() {}, remove() {}, querySelector(q) { return kids[q] || (kids[q] = el()); },
    querySelectorAll(q) { return q === 'li.now' ? e.nows : []; }};
  return e;
}
const document = {createElement() { const e = el(); made.push(e); return e; }};
const thread = el(), sent = {disabled: false};
const $ = (id) => (id === 'thread' ? thread : sent);
const esc = (s) => s;
const reportLink = () => 'report';
let refreshed = 0;
const refresh = async () => { refreshed += 1; };
let ticks = [];
const setInterval = (f) => { ticks.push(f); return ticks.length; };
const clearInterval = () => {};
const running = [];
const follow = (id, on) => new Promise((resolve, reject) => running.push({id, on, resolve, reject}));
const realNow = Date.now; let now = 1000000;
Date.now = () => now;
const head = (i) => made[i].querySelector('.head').innerHTML;
"""


def _bubble(body):
    src = open(JS).read()
    fns = "".join(_fn(src, n) for n in ("elapsedText", "authoringWords", "buildRanFor", "followBuild"))
    steps = re.search(r"^const BUILD_STEPS = .*?;\n(?=\S)", src, re.M | re.S).group(0)
    return _run(f"{BUBBLE}\n{steps}\n{fns}\nconst out = await (async () => {{ {body} }})();\nconsole.log(JSON.stringify(out));")


def test_the_bubble_names_the_step_and_which_try():
    got = _bubble("""followBuild('j');
      running[0].on({kind: 'step', step: 'build', text: 'Building the seat'});
      running[0].on({kind: 'authoring', text: 'x', round: 3});
      return {head: head(0), detail: made[0].querySelector('li[data-step="build"] .detail').textContent, following: S.following, off: sent.disabled};""")
    assert "Building the seat" in got["head"]
    assert got["detail"] == " · writing the design: third try" and got["following"] == "j" and got["off"] is True


def test_the_clock_starts_from_what_the_server_says_and_keeps_ticking():
    got = _bubble("""followBuild('j', 125); const first = head(0); now += 10000; ticks[0](); return [first, head(0)];""")
    assert "2 min 5 s" in got[0] and "2 min 15 s" in got[1]


def test_an_earlier_follow_of_a_build_doesnt_end_a_later_one():
    got = _bubble("""followBuild('a'); followBuild('b'); running[0].resolve({}); await new Promise((r) => setTimeout(r, 0));
      const after = {busy: S.busy, following: S.following, refreshed};
      running[1].resolve({}); await new Promise((r) => setTimeout(r, 0));
      return [after, {busy: S.busy, following: S.following, refreshed, off: sent.disabled}];""")
    assert got[0] == {"busy": True, "following": "b", "refreshed": 0}
    assert got[1] == {"busy": False, "following": None, "refreshed": 1, "off": False}


def test_after_a_crash_the_step_stops_and_it_says_the_build_stopped():
    got = _bubble("""followBuild('j'); const li = el(); made[0].nows = [li];
      running[0].reject(new Error('the API fell over')); await new Promise((r) => setTimeout(r, 0));
      return {head: head(0), removed: li.removed, bad: made[0].c};""")
    assert got["head"].startswith("⚠ The build stopped: the API fell over") and got["removed"] == "now" and "bad" in got["bad"]


def _poll(running):
    src = open(JS).read()
    return _run("const S = {slug: 's', design: {running: []}, tracked: {}, following: 'mine'};\nconst document = {hidden: false};\n"
                f"const api = async () => ({{running: {running}}});\nconst called = [], anchored = [];\n"
                "const followBuild = (...a) => called.push(a); const buildRanFor = (s) => anchored.push(s);\n"
                "const syncRunning = () => {}; const jobsHere = () => [];\n" + _fn(src, "pollRunning")
                + "await pollRunning();\nconsole.log(JSON.stringify([called, anchored]));")


def test_a_build_started_in_another_tab_is_picked_up_at_its_time():
    assert _poll('[{"job": "other", "kind": "firstrun", "elapsed_s": 40}]') == [[["other", 40]], []]


def test_a_build_already_followed_keeps_to_the_servers_time():
    assert _poll('[{"job": "mine", "kind": "firstrun", "elapsed_s": 41}]') == [[], [41]]


def test_a_redraw_follows_a_build_at_its_time():
    assert "followBuild(d.building, ((d.running || []).find((r) => r.job === d.building) || {}).elapsed_s)" in open(JS).read()


def test_a_build_that_crashes_is_on_the_designs_record(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path))
    store = DesignStore.create("a step stool", base=str(tmp_path))
    monkeypatch.setattr(design_api, "RUNNER", jobs.JobRunner())

    def boom(store, emit, **k):
        raise RuntimeError("the API fell over")

    monkeypatch.setattr(firstrun, "build", boom)
    job = design_api.first_build(os.path.basename(store.root))
    for _ in range(300):
        if job.over:
            break
        time.sleep(0.01)
    assert job.status == "error"
    last = DesignStore.load(store.root).log()[-1]
    assert last["kind"] == "reply" and last["ok"] is False and "the API fell over" in last["reply"] and "Build it" in last["reply"]


def test_the_card_doesnt_say_press_build_it_during_a_build(tmp_path):
    from caliper import answers

    store = DesignStore.create("a step stool", base=str(tmp_path))
    state = design_api.design_state(store)
    said = lambda st: " ".join(ln["text"] for c in answers.answers(store, st, None) for ln in c["lines"])   # noqa: E731
    assert "press Build it" in said(state)
    assert "press Build it" not in said({**state, "building": "j1"}) and "Building it now" in said({**state, "building": "j1"})


def test_pressing_build_it_redraws_the_cards_so_they_stop_saying_press_build_it():
    src = open(JS).read()
    press = src[src.index("$('buildFirst').onclick"):src.index("if (typeof d.claude === 'boolean')")]
    assert press.index("followBuild(") < press.index("S.answers = null;") < press.index("refresh()")


def test_a_first_build_isnt_tracked_like_a_study():
    src = open(JS).read()
    got = _run("const S = {design: {running: [{job: 'a', kind: 'firstrun'}, {job: 'b', kind: 'load'}]}, tracked: {}};\nconst seen = [];\n"
               "function trackJob(id) { seen.push(id); return {done: Promise.resolve()}; }\n" + _fn(src, "syncRunning")
               + "syncRunning();\nconsole.log(JSON.stringify(seen));")
    assert got == ["b"]
