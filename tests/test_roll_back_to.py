"""CALI-188 (#299): go back to any version, and a plain roll-back that never redoes what it undid.

Theo, 2026-11-14: "roll it back worked, but is there a way to just select the version that i want to roll back to? Like
even v3?" And the trap: `revert_part` always restored the one before the last, so after step_stool's v6 (a copy of v4), a
second "roll it back" would have brought back v5, the printed-PLA stool (#295).

Theo's step_stool history as the shape of the fixture: v1..v5, v6 restored from v4, v7 a change on top. Synthetic scripts.
"""

import os
import time

import pytest

from caliper import chat
from caliper.design import DesignStore

from .test_chat import _box

pytest.importorskip("cadquery")

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _never(*a, **k):
    raise AssertionError("no model call: a roll-back is read by its words")


class _NoModel:
    """A client that fails the test if the model is asked anything."""
    def __getattr__(self, name):
        raise AssertionError("no model call: a roll-back is read by its words")


@pytest.fixture
def stool(tmp_path):
    """step_stool's history: v1..v5 (v5 the printed-PLA one), v6 restored from v4, v7 a change on top of it."""
    s = DesignStore.create("step-stool-5", base=str(tmp_path / "designs"))
    for dx in (100, 200, 300, 400, 500):
        s.write_part("step_stool", _box(dx=dx), intent="the stool")
    s.restore("step_stool", 4)
    s.write_part("step_stool", _box(dx=700), intent="the stool")
    return s


def _dx(s, v=None):
    script = s.read_script("step_stool") if v is None else open(os.path.join(s.version_dir("step_stool", v), "part.py")).read()
    return next(int(x) for x in (100, 200, 300, 400, 500, 700) if f"box({x}," in script)


def test_the_fixture_is_theo_s_shape(stool):
    assert stool.versions("step_stool") == [1, 2, 3, 4, 5, 6, 7] and _dx(stool, 6) == 400 and _dx(stool, 5) == 500


def test_plain_roll_backs_walk_back_and_never_redo_what_was_undone(stool):
    first = chat.revert_part(stool, "step_stool")                 # undo v7: back to v6, which is v4's
    assert first.reply.startswith("↩ rolled **step_stool** back to v6 (saved as v8)") and _dx(stool) == 400
    second = chat.revert_part(stool, "step_stool")                # undo v8 = v6 = v4: what was before v4, never v5
    assert second.reply.startswith("↩ rolled **step_stool** back to v3 (saved as v9)") and _dx(stool) == 300
    third = chat.revert_part(stool, "step_stool")
    assert third.reply.startswith("↩ rolled **step_stool** back to v2") and _dx(stool) == 200


def test_after_v6_a_plain_roll_back_goes_to_v3(tmp_path):
    """The issue's own words: after v6 (= v4), it goes to v3."""
    s = DesignStore.create("s", base=str(tmp_path / "designs"))
    for dx in (100, 200, 300, 400, 500):
        s.write_part("step_stool", _box(dx=dx), intent="the stool")
    s.restore("step_stool", 4)
    got = chat.revert_part(s, "step_stool")
    assert "back to v3 (saved as v7)" in got.reply and _dx(s) == 300


def test_the_first_version_has_nothing_before_it(tmp_path):
    s = DesignStore.create("s", base=str(tmp_path / "designs"))
    s.write_part("p", _box(dx=100), intent="a box")
    s.write_part("p", _box(dx=200), intent="a box")
    s.restore("p", 1)
    got = chat.revert_part(s, "p")                                  # v3 = v1: before v1, nothing
    assert not got.ok and got.reply == "p is back at its first version (v1): there's nothing before it to roll back to."


@pytest.mark.parametrize("words", ["roll it back to v3", "go back to version 3", "restore v3", "Roll back to V3 please",
                                   "revert to version 3"])
def test_roll_it_back_to_a_version_restores_that_one_without_the_model(stool, words):
    got = chat.turn(stool, words, scope="step_stool", use_llm=True, client=_NoModel(), classifier=_never)
    assert got.action == "revert" and got.ok, got.reply
    assert got.reply.startswith("↩ rolled **step_stool** back to v3 (saved as v8)") and _dx(stool) == 300


def test_a_plain_roll_back_needs_no_model_either(stool):
    got = chat.turn(stool, "roll it back", scope="step_stool", use_llm=True, client=_NoModel(), classifier=_never)
    assert got.action == "revert" and "back to v6 (saved as v8)" in got.reply


def test_a_version_that_isn_t_there_says_which_are(stool):
    got = chat.turn(stool, "roll it back to v12", scope="step_stool", use_llm=True, client=_NoModel(), classifier=_never)
    assert not got.ok and got.reply == "There's no v12 of step_stool: it has v1 to v7."
    assert stool.versions("step_stool")[-1] == 7


def test_the_reply_names_the_target_before_it_acts(stool):
    events = []
    chat.revert_part(stool, "step_stool", to=2, events=events)
    kinds = [(e.kind, e.text) for e in events]
    assert kinds[0] == ("reverting", "step_stool back to v2"), kinds
    assert [k for k, _ in kinds].index("reverting") < [k for k, _ in kinds].index("wrote")


# --- the panel: Go back to this, and its preview ----------------------------------------------------------------------
@pytest.fixture
def site(stool, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(str(stool.root)))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    return TestClient(create_app()), os.path.basename(str(stool.root)), stool


def test_go_back_to_this_makes_a_new_version_with_that_script(site):
    c, slug, s = site
    r = c.post(f"/api/designs/{slug}/parts/step_stool/restore", json={"version": 2})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["reply"].startswith("↩ rolled **step_stool** back to v2 (saved as v8)") and got["version"] == 8
    s = DesignStore.load(s.root)
    assert _dx(s) == 200 and s.versions("step_stool")[-1] == 8
    log = [e for e in s.log() if e.get("kind") in ("message", "reply")][-2:]
    assert [(e["kind"], e.get("text") or e.get("reply", "")[:40]) for e in log] == [
        ("message", "Go back to v2 of step_stool (from its history)"), ("reply", "↩ rolled **step_stool** back to v2 (save")]
    assert c.post(f"/api/designs/{slug}/parts/step_stool/restore", json={"version": 99}).status_code == 404


def test_a_version_s_shape_is_there_to_preview(site):
    c, slug, _ = site
    r = c.get(f"/api/designs/{slug}/parts/step_stool/versions/3.stl")
    assert r.status_code == 200 and len(r.content) > 84 and r.headers["content-type"] == "model/stl"
    assert c.get(f"/api/designs/{slug}/parts/step_stool/versions/99.stl").status_code == 404


def test_each_older_version_in_the_history_offers_a_preview_and_go_back():
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = _fn(src, "historyItem") + """
const esc = (s) => String(s), verdictTone = () => 'ok';
console.log(JSON.stringify({
  old: historyItem({ kind: 'revision', action: 'refine', version: 3, feedback: 'make it taller' }, 7),
  now: historyItem({ kind: 'revision', action: 'refine', version: 7 }, 7),
  back: historyItem({ kind: 'revision', action: 'restore', version: 6, restored_from: 4 }, 7) }));
"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    out = json.loads(got.stdout)
    assert 'data-preview-v="3"' in out["old"] and 'data-goback-v="3"' in out["old"] and ">Go back to this<" in out["old"]
    assert "data-goback-v" not in out["now"]                                          # it's what it is now
    assert 'data-goback-v="6"' in out["back"] and "rolled back to v4" in out["back"]
    assert "historyItem(h, p.version)" in src
    assert "`/api/designs/${S.slug}/parts/${pid}/versions/${v}.stl`" in src and "(preview)" in _fn(src, "showVersion")
    assert "/parts/${pid}/restore`, { version: v }" in _fn(src, "goBackTo")



def test_the_part_menu_s_versions_lists_each_other_version_and_previews_it():
    """#294's menu: Versions ▸ v6 … v1, each with what was asked of it; choosing one previews it, Go back in its bar."""
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = _fn(src, "versionsHtml") + """
const esc = (s) => String(s);
const p = { id: 'step_stool', label: 'Step stool', version: 7, versions: [1, 2, 3, 4, 5, 6, 7],
            history: [{ kind: 'revision', version: 3, feedback: 'set width to 16 in, height to 16 in by hand' },
                      { kind: 'revision', version: 6, action: 'restore', restored_from: 4 }] };
console.log(JSON.stringify(versionsHtml(p)));
"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    html = json.loads(got.stdout)
    assert [int(x) for x in __import__("re").findall(r'data-menu="ver:(\d+)"', html)] == [6, 5, 4, 3, 2, 1]
    assert "set width to 16 in" in html and 'data-menu="history"' in html and 'ver:7' not in html
    menu = _fn(src, "menuDo")
    assert "if (id === 'versions') return menuConfirm(versionsHtml(" in menu
    assert "if (id.startsWith('ver:')) { setScope(pid); return showVersion(pid, Number(id.slice(4))); }" in menu
