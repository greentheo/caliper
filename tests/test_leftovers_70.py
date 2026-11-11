"""CALI-92 (#70) — the leftovers: the items main still had after the triage of 2026-11-10."""
import json
import os
import re
import subprocess

import pytest

from .test_carve_click import _fn, _node
from .test_small_words import _js

#: partView's neighbours, stubbed: only its heading and its Advanced line are under test.
STUBS = """const S = { design: { rules: [], in_air: { yes: false } } };
const len = (x) => String(x);
const ruleItem = () => '', historyItem = () => '', loadView = () => '', trialView = () => '', frameView = () => '',
  aeroView = () => '', whittleView = () => '', aeroRuns = () => [], runsFor = () => [], buildView = () => '',
  makingView = () => '', patternView = () => '', cutplanView = () => '', paramView = () => '';
function cardsView(c) { return c.what; }
"""


def _part(**kw):
    return {"id": "step_stool", "name": "Step stool", "version": 3, "scripted": True, "origin": None, "rules": [],
            "history": [], "bbox": None, "role": "design", **kw}


@pytest.mark.parametrize("kw,word", [({}, "parametric"), ({"scripted": False}, "imported"),
                                     ({"origin": "whittled"}, "whittled mesh")])
def test_the_part_view_heading_is_the_part_s_own_name(kw, word):
    """Item 21: no internal id or `parametric` badge in the top line; both are one click down, under Advanced."""
    html = _js(["partView"], f"return partView({_part(**kw)!r});".replace("None", "null").replace("True", "true")
               .replace("False", "false"), STUBS)
    heading = re.search(r"<h2>(.*?)</h2>", html, re.S).group(1)
    assert heading.strip() == "Step stool"
    advanced = re.search(r"<summary>(.*?)</summary>", html, re.S).group(1)
    assert "step_stool" in advanced and word in advanced


def _bar(kind, run_v, part_v, index=2):
    head = f"""const S = {{ design: {{ parts: [{{ id: 'stool', version: {part_v} }}] }} }};
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {{}};
const holdsHere = () => true;
"""
    return _js(["stationAction"], f"return stationAction('stool', {{ kind: '{kind}', version: {run_v} }}, {index}, {{}});", head)


@pytest.mark.parametrize("kind,again", [("lighten", "lighten it again"), ("carve", "carve it again")])
def test_a_stale_run_s_preview_doesn_t_offer_the_cut(kind, again):
    """Item 24: a Lighten of v3 previewed on v4 offered "Cut these holes", which the server then refused."""
    html = _bar(kind, 3, 4)
    assert "adoptBtn" not in html and again in html and "v3" in html and "v4" in html
    assert "adoptBtn" in _bar(kind, 4, 4)                      # the current version's step is still offered


def test_a_study_the_server_doesn_t_version_still_offers_its_step():
    assert "adoptBtn" in _bar("parametric", 3, 4) and "adoptBtn" in _bar("frame", 3, 4)


API = """globalThis.window = {};
globalThis.fetch = async (url) => ({ ok: false, status: +url, json: async () => ({ detail: 'said ' + url }) });
"""


def test_a_409_is_marked_a_refusal_and_a_500_isn_t():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    script = API + _fn(src, "api") + """
(async () => {
  const out = {};
  for (const code of [409, 500]) { try { await api('POST', String(code)); } catch (e) { out[code] = !!e.refused; } }
  out.marked = Object.keys(window.__refused || {});
  console.log(JSON.stringify(out));
})();"""
    got = json.loads(subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30).stdout)
    assert got == {"409": True, "500": False, "marked": ["said 409"]}


def _errbar(msg, refused):
    html = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "index.html")).read()
    show = re.search(r"function showErr\(msg\) \{.*?\n    \}\n", html, re.S).group(0)
    script = """class El { constructor() { this.children = []; this.dataset = {}; this.classList = { on: new Set(),
  toggle: (c, v) => (v ? this.classList.on.add(c) : this.classList.on.delete(c)) }; }
  append(c) { this.children.push(c); } }
const bar = new El();
globalThis.window = globalThis; window.__err = []; globalThis.__err = window.__err;
globalThis.document = { getElementById: () => bar, createElement: () => new El() };
""" + f"window.__refused = {json.dumps({msg: True} if refused else {})};\n" + show + f"""
showErr({json.dumps(msg)});
console.log(JSON.stringify({{ text: bar.textContent, plain: bar.classList.on.has('plain'),
  report: bar.children.some((c) => c.textContent === 'Report it…') }}));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_refusal_shows_as_a_plain_line_with_no_report_link():
    """Item 24: the 409 went to the red bar with **Report it…**, as if it were a crash."""
    said = "this lightening is of version 3 and the part is at version 4: lighten it again"
    assert _errbar(said, True) == {"text": said + " ", "plain": True, "report": False}
    assert _errbar("boom", False) == {"text": "⚠ boom ", "plain": False, "report": True}
