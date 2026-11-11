"""CALI-157 (#223), part 2 — a first build shows the part as soon as one script builds, and the checks wait to be asked for."""

import pytest

from caliper import answers, design_api, firstrun, goals, load_study, patterns, scorecard
from caliper.design import DesignStore

from .test_carve_click import JS

pytest.importorskip("cadquery")

BOX = '''import cadquery as cq


def build(params):
    return cq.Workplane().box(100, 100, 100)
'''
BROKEN = "def build(params):\n    raise RuntimeError('no')\n"
#: A part with loads(), so its card has a strength line.
LOADED = '''import cadquery as cq


def build(params):
    return cq.Workplane().box(100, 100, 20, centered=(True, True, False))


def construction(params, build=None):
    return [{"name": "block", "kind": "printed", "material": "petg"}]


def loads(params, build=None):
    return [{"name": "a foot", "lb": 20, "factor": 2.0, "lo": (-10, -10, 18), "hi": (10, 10, 20)}]
'''


class Author:
    def __init__(self, *scripts):
        self.scripts, self.calls = list(scripts), 0

    def __call__(self, spec, feedback, prior):
        self.calls += 1
        return self.scripts[min(self.calls - 1, len(self.scripts) - 1)]


def _never(*a, **k):
    raise AssertionError("a first build must not start this")


@pytest.fixture
def quiet(monkeypatch):
    for module, name in ((load_study, "study"), (patterns, "make"), (scorecard, "compute"), (goals, "update")):
        monkeypatch.setattr(module, name, _never)


def _store(tmp_path):
    return DesignStore.create("a step stool", base=str(tmp_path / "designs"))


def test_the_part_is_written_as_soon_as_a_script_builds_and_nothing_else_starts(tmp_path, quiet):
    s, heard = _store(tmp_path), []
    author = Author(LOADED)
    got = firstrun.build(s, use_llm=False, author=author, emit=lambda k, t="", **d: heard.append(d.get("step")))
    assert got["version"] and author.calls == 1 and s.design.parts
    assert "strength" not in heard and "patterns" not in heard and "score" not in heard and "goals" not in heard


def test_a_script_that_wont_build_gets_one_repair(tmp_path, quiet):
    author = Author(BROKEN, BOX)
    got = firstrun.build(_store(tmp_path), use_llm=False, author=author)
    assert got["version"] and author.calls == 2


def test_two_tries_at_most(tmp_path, quiet):
    author = Author(BROKEN)
    got = firstrun.build(_store(tmp_path), use_llm=False, author=author)
    assert not got.get("version") and author.calls == 2


#: A solid that fails no build, and declares pieces that leave most of it out.
SHORT = '''import cadquery as cq


def build(params):
    a = cq.Workplane().box(300, 200, 19.05, centered=False).translate((0, 0, 100))
    b = cq.Workplane().box(19.05, 200, 100, centered=False)
    c = cq.Workplane().box(19.05, 200, 100, centered=False).translate((280.95, 0, 0))
    return a.union(b).union(c)


def construction(params, build=None):
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0, 0, 119.05), (300, 0, 119.05), (300, 200, 119.05), (0, 200, 119.05)]}]
'''


def test_pieces_that_dont_account_for_the_solid_get_the_one_repair(tmp_path, quiet):
    author = Author(SHORT, BOX)
    got = firstrun.build(_store(tmp_path), use_llm=False, author=author)
    assert got["version"] and author.calls == 2


def test_any_other_failing_check_is_told_not_retried():
    from caliper.spec import Assertion, Spec
    from caliper import authoring

    author = Author(BOX)
    spec = Spec(part="b", intent="a block", assertions=[Assertion(id="big", expr="bbox.dx >= 500")])
    got = authoring.improve(spec, author=author, max_rounds=firstrun.FIRST_ROUNDS, repair_only=firstrun.REPAIRS)
    assert author.calls == 1 and not got.ok and got.geometry is not None


def test_the_card_says_not_checked_yet_and_check_it_holds_is_there(tmp_path, quiet):
    s = _store(tmp_path)
    firstrun.build(s, use_llm=False, author=Author(LOADED))
    state = design_api.design_state(s)
    pid = s.design.parts[0].id
    lines = [ln for c in answers.answers(s, state, pid) for ln in c["lines"] if ln.get("study") == "load"]
    assert any(ln["text"] == "Not checked yet: check it when it looks right." and ln["status"] == "warn" for ln in lines)


def test_check_it_holds_starts_one_by_hand(tmp_path, quiet, monkeypatch):
    monkeypatch.undo()
    pytest.importorskip("whittle")
    s = _store(tmp_path)
    monkeypatch.setattr(goals, "update", _never)
    firstrun.build(s, use_llm=False, author=Author(LOADED))
    assert load_study.list_runs(s, s.design.parts[0].id) == []
    rec = load_study.study(s, s.design.parts[0].id)
    assert rec["cases"]


def test_the_steps_the_page_lists_are_the_ones_it_does():
    src = open(JS).read()
    import re

    known = set(re.findall(r"(\w+): '", re.search(r"const BUILD_STEPS = \{(.*?)\};", src, re.S).group(1)))
    assert known == {"plan", "build"}


def test_the_page_shows_the_part_as_soon_as_its_written():
    from .test_first_build_progress import _bubble

    got = _bubble("""followBuild('j'); const before = refreshed; running[0].on({kind: 'wrote', text: 'p -> v1'});
      await new Promise((r) => setTimeout(r, 0)); return [before, refreshed, S.following];""")
    assert got == [0, 1, "j"]                      # redrawn with the part while the build carries on


def test_a_mismatch_the_repair_couldnt_fix_is_said_first(tmp_path, quiet):
    got = firstrun.build(_store(tmp_path), use_llm=False, author=Author(SHORT, BROKEN))
    assert got["version"] and got["reply"].startswith("I built it, but its 3D shape and its pieces still don't match after one repair")


#: A block filled in, every face of it a declared panel: its surface is all on pieces, only its volume says it's wrong.
FILLED = '''import cadquery as cq


def build(params):
    return cq.Workplane().box(300, 200, 200, centered=False)


def construction(params, build=None):
    t = 19.05
    def sheet(name, o):
        return {"name": name, "kind": "sheet", "material": "plywood", "thickness": t, "outline": o}
    return [sheet("top", [(0, 0, 200), (300, 0, 200), (300, 200, 200), (0, 200, 200)]),
            sheet("bottom", [(0, 0, 0), (300, 0, 0), (300, 200, 0), (0, 200, 0)]),
            sheet("left", [(0, 0, 0), (0, 200, 0), (0, 200, 200), (0, 0, 200)]),
            sheet("right", [(300, 0, 0), (300, 200, 0), (300, 200, 200), (300, 0, 200)]),
            sheet("front", [(0, 0, 0), (300, 0, 0), (300, 0, 200), (0, 0, 200)]),
            sheet("back", [(0, 200, 0), (300, 200, 0), (300, 200, 200), (0, 200, 200)])]


def loads(params, build=None):
    return [{"name": "a foot", "lb": 100, "factor": 2.0, "lo": (100, 50, 198), "hi": (200, 150, 200)}]
'''


def test_a_filled_shape_gets_the_one_repair_too(tmp_path, quiet):
    from .test_load_study import BOX_STOOL

    author = Author(FILLED, BOX_STOOL)
    got = firstrun.build(_store(tmp_path), use_llm=False, author=author)
    assert got["version"] and author.calls == 2


def test_goals_ask_claude_with_no_lock_on_the_design(tmp_path, monkeypatch):
    import os
    import time

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from caliper import jobs

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    s = DesignStore.create("a step stool", base=str(tmp_path))
    s.write_part("p", BOX, intent="x")
    slug = os.path.basename(s.root)
    monkeypatch.setattr(design_api, "RUNNER", jobs.JobRunner())
    held = []

    def draft(store, said, data, client=None):
        held.append(design_api.RUNNER.locked(design_api._lock(slug)).locked())
        return {"checks": [], "objectives": []}

    monkeypatch.setattr(goals, "draft", draft)
    app = FastAPI()
    app.include_router(design_api.router())
    TestClient(app).get(f"/api/designs/{slug}/answers")
    for _ in range(300):
        if held:
            break
        time.sleep(0.01)
    assert held == [False]
