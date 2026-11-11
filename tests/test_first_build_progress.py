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


def test_a_switch_of_design_lets_the_build_be_followed_again_and_frees_the_other_designs_chat():
    src = open(JS).read()
    assert _fn(src, "dropBuildFollow") and "dropBuildFollow();" in re.search(r"async function openDesign.*?^}", src, re.S | re.M).group(0)
    drop = _fn(src, "dropBuildFollow")
    got = _run("const S = {following: 'j1', buildFollow: 1, busy: true, buildBubble: {}};\nconst sent = {disabled: true};\n"
               "const $ = () => sent;\n" + drop + "dropBuildFollow();\nconsole.log(JSON.stringify([S.following, S.buildFollow, S.busy, S.buildBubble, sent.disabled]));")
    assert got == [None, 2, False, None, False]


def test_a_first_build_isnt_tracked_like_a_study():
    src = open(JS).read()
    got = _run("const S = {design: {running: [{job: 'a', kind: 'firstrun'}, {job: 'b', kind: 'load'}]}, tracked: {}};\nconst seen = [];\n"
               "function trackJob(id) { seen.push(id); return {done: Promise.resolve()}; }\n" + _fn(src, "syncRunning")
               + "syncRunning();\nconsole.log(JSON.stringify(seen));")
    assert got == ["b"]
