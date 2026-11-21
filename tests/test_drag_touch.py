"""CALI-236: #378's two touch notes, and #395's page part.

1. **A cancelled touch ends the drag** (#378 review). A drag added pointermove and pointerup to the window, and only
   pointerup took them off. A cancel (the browser takes the gesture, a call, a palm) sends no pointerup, so the next hover or
   touch went on dragging the box.
2. **A finger grabs a handle from further** (#378 review): 14 px is about 4 mm on a phone; a touch reaches 28 px.
3. **Test it over an older check says "Check it again first"** (#395), as #394's Make it better does: "Check it holds
   first" read as never checked."""
import json
import subprocess

import pytest

from .test_carve_click import JS, _fn, _node

_PRESS = """
const S = { scenOpen: 'stool', scenPick: null }, on = {}, calls = [];
function addEventListener(k, f) { (on[k] = on[k] || new Set()).add(f); }
function removeEventListener(k, f) { if (on[k]) on[k].delete(f); }
const fire = (k, e) => [...(on[k] || [])].forEach((f) => f(e || {}));
const live = () => Object.fromEntries(Object.entries(on).map(([k, v]) => [k, v.size]));
let reach = null; const handleAt = (e, near) => { reach = near; return { scenHandle: 'move', i: 0 }; };
const startScenDrag = () => true, moveScenDrag = () => calls.push('move'), endScenDrag = () => calls.push('end');
const press = (type, id) => scenPress({ button: 0, pointerType: type, pointerId: id, clientX: 1, clientY: 1, stopPropagation() {}, preventDefault() {} });
"""


def _js(body):
    src = open(JS).read()
    grab = next(l for l in src.split("\n") if l.startswith("const GRAB = ")) + "\n"
    script = grab + _PRESS + _fn(src, "scenPress") + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@pytest.mark.parametrize("ending", ["pointercancel", "pointerup"])
def test_the_drag_ends_however_the_press_does_and_leaves_nothing_listening(ending):
    got = _js(f"""press('touch'); const during = live(); fire('pointermove'); fire('{ending}'); fire('pointermove'); fire('pointerup');
                  return {{ during, after: live(), calls }};""")
    assert got["during"] == {"pointermove": 1, "pointerup": 1, "pointercancel": 1}
    assert got["after"] == {"pointermove": 0, "pointerup": 0, "pointercancel": 0}
    assert got["calls"] == ["move", "end"]                                 # nothing moves after it, and it ends once


@pytest.mark.parametrize("kind,reach", [("touch", 28), ("mouse", 14), ("pen", 14), ("", 14)])
def test_a_finger_reaches_further_for_a_handle(kind, reach):
    assert _js(f"press('{kind}'); return reach;") == reach


def test_the_view_takes_the_press_before_its_orbit():
    assert "viewer.addEventListener('pointerdown', scenPress, true);" in open(JS).read()


# --- #395: Test it ------------------------------------------------------------------------------------------------------------
def _trial(runs):
    src = open(JS).read()
    head = f"""const S = {{ trial: {{ part: 'stool', key: 8, data: {{ prediction: null }} }}, design: {{ load_runs: {json.dumps(runs)} }} }};
const loadTrial = () => {{}};"""
    script = head + _fn(src, "loadRuns") + _fn(src, "trialView") + "\nconsole.log(JSON.stringify(trialView({ id: 'stool', version: 8 })));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_test_it_over_an_older_check_says_check_it_again_first():
    """The bar stool at v8, its last check of v4 (#387's walk): "Check it holds first" read as never checked."""
    got = _trial([{"part": "stool", "version": 4, "id": "r2"}, {"part": "stool", "version": 3, "id": "r1"}])
    assert got == '<div class="empty">Check it again first: its check is of v4: the test is set beside what that predicts.</div>'


def test_test_it_never_checked_still_says_check_it_holds_first():
    assert _trial([{"part": "other", "version": 1}]) == \
        '<div class="empty">Check it holds first: the test is set beside what that predicts.</div>'


def test_a_check_of_this_version_is_never_called_older():
    """Its newest check is of v8, this version: no "again", and never "its check is of v8"."""
    got = _trial([{"part": "stool", "version": 8, "id": "r3"}, {"part": "stool", "version": 4, "id": "r2"}])
    assert "of v8" not in got and "Check it again first: its check is of v4" in got


@pytest.mark.parametrize("ending", ["pointerup", "pointercancel"])
def test_a_second_finger_neither_moves_nor_ends_the_drag(ending):
    """#403 review: the drag follows the pointer that took the handle. A second finger on the screen (a pinch starting, a
    palm) moving or lifting is another gesture's."""
    got = _js(f"""press('touch', 1);
                  fire('pointermove', {{ pointerId: 2 }}); fire('{ending}', {{ pointerId: 2 }}); const after2 = live();
                  fire('pointermove', {{ pointerId: 1 }}); fire('{ending}', {{ pointerId: 1 }});
                  return {{ after2, after1: live(), calls }};""")
    assert got["after2"] == {"pointermove": 1, "pointerup": 1, "pointercancel": 1}          # still its own
    assert got["after1"] == {"pointermove": 0, "pointerup": 0, "pointercancel": 0}
    assert got["calls"] == ["move", "end"]                                                  # only the first finger's move
