"""CALI-223 (the tester's walk, 2026-11-21): small page fixes from walking step-stool-5 and the bar stool as Theo would.

1. Lighten's (or a carve's) Use it said nothing: the version number changed and that was all.
2. The part menu said "Check it holds" and "Lighten it" beside the bar's "Check it again" and "Lighten it again".
3. A piece renamed "tread" still read "step" in the strength panel's plate check: the run's record keeps the key it ran with.
4. Make the cut plan said nothing when it was done; its line can be in a card that's folded away."""
import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _js(names, body, head="", module=False):
    src = open(JS).read()
    script = head + "".join(_fn(src, n) for n in names) + \
        f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node()] + (["--input-type=module"] if module else []) + ["-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


# --- 1. Use it says what it did ------------------------------------------------------------------------------------------
_TAKE = """
const S = { slug: 'step-stool-5', design: { parts: [{ id: 'step_stool', name: 'Step stool', version: 16 }] } };
const STUDY_PATH = { lighten: 'lighten', carve: 'carve' };
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {};
const said = [], checked = [];
const $ = (id) => (id === 'lGo' ? {} : null);
const api = async () => ({}); const clearStation = () => {};
const refresh = async () => { S.design.parts[0].version = 17; };
const say = (t) => said.push(t); const runLoad = (p) => checked.push(p.id); const showErr = (m) => said.push('ERR ' + m);
"""


@pytest.mark.parametrize("kind,words", [
    ("lighten", "Used the Lighten's step 2: Step stool is v17 now. Checking it again: that number is the one to go by."),
    ("carve", "Used the carve's step 2: Step stool is v17 now. Checking it again: that number is the one to go by."),
    ("whittle", "Used its step 2: Step stool is v17 now.")])
def test_a_step_used_says_what_it_did(kind, words):
    got = _js(("takeStation",), f"await takeStation('step_stool', 'r1', 2, '{kind}'); return {{ said, checked }};", head=_TAKE)
    assert got["said"] == [words]
    assert got["checked"] == (["step_stool"] if kind in ("lighten", "carve") else [])


def test_a_refused_step_says_the_error_not_that_it_was_used():
    got = _js(("takeStation",), "await takeStation('step_stool', 'r1', 2, 'lighten'); return said;",
              head=_TAKE.replace("const api = async () => ({});", "const api = async () => { throw new Error('no'); };"))
    assert got == ["ERR no"]


# --- 2. the menu says what the bar says -----------------------------------------------------------------------------------
def _menu_labels(runs):
    from .test_part_menu import _STUBS

    src = open(JS).read()
    design = json.dumps({"parts": [{"id": "stool", "name": "stool", "role": "part", "version": 1, "study": "lighten", "pieces": []},
                                   {"id": "cone", "name": "cone", "role": "part", "version": 1, "study": "carve", "pieces": []}],
                         "tree": {}, **runs, "studies": {"menu": {pid: [{"kind": "load", "ready": True, "why": ""}, {"kind": "lighten", "ready": True, "why": ""},
                                                                         {"kind": "carve", "ready": True, "why": ""}] for pid in ("stool", "cone")}}})
    import re

    keys = re.search(r"^const TREE_KEYS = .*$", src, re.M)
    script = (_STUBS.replace("DESIGN", design) + (keys.group(0) + "\n" if keys else "")
              + "".join(_fn(src, n) for n in ("seen", "menuItems") + (("treeRows", "dropped", "nudge") if keys else ()))
              + "\nconsole.log(JSON.stringify({ stool: menuItems(S.design, 'stool', null).map((i) => i.label), cone: menuItems(S.design, 'cone', null).map((i) => i.label) }));")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_menu_says_again_where_it_has_been_as_the_bar_does():
    none = _menu_labels({})
    assert "Check it holds" in none["stool"] and "Lighten it" in none["stool"] and "Carve it" in none["cone"]
    ran = _menu_labels({"load_runs": [{"part": "stool"}, {"part": "cone"}], "lighten_runs": [{"part": "stool"}], "carve_runs": [{"part": "cone"}]})
    assert "Check it again" in ran["stool"] and "Lighten it again" in ran["stool"] and "Carve it again" in ran["cone"]
    other = _menu_labels({"load_runs": [{"part": "cone"}]})                  # another part's run isn't this one's
    assert "Check it holds" in other["stool"] and "Check it again" in other["cone"]


# --- 3. a renamed piece by its name -----------------------------------------------------------------------------------------
def test_a_renamed_piece_is_said_by_its_name_and_an_unnamed_one_by_its_key():
    got = _js(("pieceSaid",), """const p = { pieces: [{ key: 'step', name: 'tread' }, { key: 'rail', name: '' }] };
                                  return [pieceSaid(p, 'step'), pieceSaid(p, 'rail'), pieceSaid(p, 'gone'), pieceSaid(null, 'step')];""")
    assert got == ["tread", "rail", "gone", "step"]


def test_the_plate_and_beam_lines_and_the_stress_bar_say_it_by_its_name():
    src = open(JS).read()
    case = _fn(src, "loadCase")
    assert case.count("esc(piece(pl.piece))") == 4 and "esc(pl.piece)" not in case
    assert "const piece = (k) => (((p && p.pieces) || []).find((x) => x.key === k) || {}).name || k;" in case
    assert "the plate check on the ${esc(pieceSaid(partOf(pid), pl.piece))}" in _fn(src, "showHeat")


# --- 4. the cut plan says it's made ---------------------------------------------------------------------------------------------
_CUT = """
const els = { cpGo: { disabled: false }, cpProgress: PROGRESS, pactsWhy: { textContent: '' } };
const $ = (id) => els[id] || null;
const document = { querySelectorAll: () => [] };
const wirePatterns = () => {}, wireMaking = () => {}, previewStep = () => {}, follow = async () => {}, refresh = async () => {};
const S = { slug: 's' }; const api = async () => ({ job_id: 'j' });
const partOf = () => ({ name: '<b>x</b>' });
const footer = []; const say = (t) => footer.push(t);
"""
MADE = "Made the cut plan for <b>x</b>: it's under How do I make it? → Cut plan."


def _cut(progress):
    import re

    esc = re.search(r"^const esc = .*;$", open(JS).read(), re.M).group(0) + "\n"
    return _js(("wireCutplan",), "wireCutplan({ id: 'stool' }); await els.cpGo.onclick(); return { els, footer };",
               head=esc + _CUT.replace("PROGRESS", json.dumps(progress)))


def test_the_cut_plan_says_it_s_made_and_where_with_its_name_as_text():
    """#388 review: a local `say(html, text)` hid the page's own, so the line went into the progress line as HTML (a
    label `<b>x</b>` drew bold), and the page's foot never said it."""
    got = _cut({"innerHTML": ""})
    assert got["els"]["cpProgress"]["innerHTML"] == \
        "<div class=\"small muted\">Made the cut plan for &lt;b&gt;x&lt;/b&gt;: it's under How do I make it? → Cut plan.</div>"
    assert got["footer"] == [MADE]                     # say() escapes it in turn


def test_with_no_progress_line_it_s_said_under_the_buttons_as_text():
    assert _cut(None)["els"]["pactsWhy"]["textContent"] == MADE


def test_the_page_s_foot_says_a_name_as_text():
    import re

    esc = re.search(r"^const esc = .*;$", open(JS).read(), re.M).group(0) + "\n"
    got = _js(("say",), "say('Made the cut plan for <b>x</b>.'); return bar.innerHTML;", head=esc + """
const bar = { setAttribute() {}, hidden: true }; const $ = () => bar; const document = {};""")
    assert "<span>Made the cut plan for &lt;b&gt;x&lt;/b&gt;.</span>" in got
