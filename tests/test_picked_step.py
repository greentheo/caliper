"""CALI-186 (#297), the page and its words: a picked Lighten step's action by the table, an estimate's Use that says what it
does, and a check that can't be called says why first, naming the check that made its number.

Theo, 2026-11-14: "when I select a 'lighten', i selected 16 … it doesn't appear that I can then make the relevant cut plan
… i then clicked the 'use' button". The step's action, Cut these holes, was in the bar under the 3D view; the table's only
button was an estimate's Use. And on step-stool-5 v6 a case read "not checked: the FEA read 2.2x, too coarse to see its
walls", where the number was the top's plate check and what wasn't seen was the fillet strips, which have no declared size.
"""

import json
import os
import re
import subprocess

from caliper import verdicts

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

#: Theo's step-stool-5 v6 run, as its first case and what it couldn't see (19.05 mm plywood at 4.76 mm voxels).
V6_RUN = {"min_safety": 2.0, "spacing_mm": 4.76, "thinnest_mm": 19.05, "across": 4.0, "resolved": False, "finer": None,
          "unsized": ["inside corner fillet strips"], "unseen": [{"mm": None, "piece": "inside corner fillet strips"}],
          "version": 6, "id": "v6", "cases": []}
V6_CASE = {"name": "stepping on the front edge of the top", "lb": 250, "factor": 2.0, "safety": 2.15, "holds": True,
           "governs": "plate", "unresolved": "unchecked",
           "plate": {"done": True, "piece": "top", "stress_mpa": 6.95, "safety": 4.31, "safety_across": 2.15},
           "fea": {"supported": True, "safety": 3.2, "peak_mpa": 4.1, "deflection_mm": 0.8}}


def _node():
    from .test_carve_click import _node as n

    return n()


def _fn(src, name):
    from .test_carve_click import _fn as f

    return f(src, name)


def _run(script):
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


STUBS = """
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const sx = (n) => (n == null ? '—' : `${Number(n).toFixed(2)}x`);
const lbs = (n) => `${n} lb`, pct = (x) => `${Math.round(x * 100)}%`, len = (x) => `${x} mm`, wallLen = len;
const fixed = (v, d) => Number(v).toFixed(d);
const verdictTone = () => 'ok', settled = (v) => v && (v.kind === 'holds' || v.kind === 'fails');
const caseBadge = () => '', untrustedBadge = () => '', jointsLine = () => '', peakWhere = () => 'here';
const foldedBy = () => 'the buckling check', beamGrain = () => '', grainKeep = () => '', holdsHere = (x) => !!x.holds;
const coarseWord = (c) => (c.unresolved === 'unchecked' ? 'not checked' : 'not resolved');
"""


def _case_line(case):
    src = open(JS).read()
    return _run(STUBS + _fn(src, "caseWhy") + _fn(src, "sheetUse") + _fn(src, "loadCase") + f"""
const S = {{ station: null }};
console.log(JSON.stringify(loadCase({{ id: 'step_stool', version: 6 }}, {json.dumps(V6_RUN)}, {json.dumps(case)}, 0)));
""")


def test_v6_s_case_line_names_the_plate_check_and_the_fillet_strips_not_the_fea():
    c = dict(V6_CASE, verdict=verdicts.case(V6_RUN, V6_CASE))
    assert c["verdict"]["kind"] == "unchecked" and "plate check" in c["verdict"]["why"], c["verdict"]
    html = _case_line(c)
    assert ("not checked: the top&#39;s plate check holds 2.15 times over; the inside corner fillet strips aren&#39;t "
            "checked: their size isn&#39;t declared") in html.replace("'", "&#39;"), html
    assert "the FEA read" not in html and "too coarse" not in html


def test_a_case_without_a_why_names_the_check_that_made_its_number():
    html = _case_line(dict(V6_CASE, verdict={"kind": "unchecked", "word": "not checked"}))
    assert "not checked: the plate check read 2.15x" in html and "the FEA read" not in html, html
    fea = _case_line(dict(V6_CASE, governs="fea", verdict={"kind": "unchecked", "word": "not checked"}))
    assert "The FEA read 2.15x" in fea and "too coarse to see its" in fea                 # the FEA's own number: its words


def test_the_station_bar_says_the_same():
    src = open(JS).read()
    assert "${caseWhy(c, run)}" in src
    assert "${coarseWord(c)}: the FEA read ${sx(c.safety, run.min_safety)}, too coarse to see its walls" not in \
        src.replace(_fn(src, "caseWhy"), "")                                             # only caseWhy says it, and only for the FEA


def test_an_unresolved_run_says_why_first():
    src = open(JS).read()
    out = _run(STUBS + _fn(src, "runReason") + """
console.log(JSON.stringify({
  why: runReason({ verdict: { kind: 'unchecked', word: 'not checked', why: "the inside corner fillet strips aren't checked: their size isn't declared" } }),
  holds: runReason({ verdict: { kind: 'holds', word: 'holds', why: 'joints not checked' } }) }));   // Theo's v7: a hold with a why
""")
    assert out["why"].startswith('<div class="small" data-reason="1"') and "not checked:</b> the inside corner fillet" in out["why"]
    assert out["holds"] == ""
    body = _fn(src, "loadResults")
    assert body.index("${runReason(run)}") < body.index("${run.cases.map((c, i) => loadCase(p, run, c, i)).join('')}")


# --- the picked step's action by the table, and an estimate's Use ------------------------------------------------------
RUN = {"id": "r1", "part": "step_stool", "version": 6, "min_safety": 2.0, "notes": [], "offer": None,
       "sheet": {"name": "softwood plywood", "param": "ply_t", "now": "3/4 in", "pieces": {}},
       "stations": [{"index": 0, "phase": "walls", "removed": 0, "saved_lb": 0, "safety": 2.1, "holds": True,
                     "verdict": {"kind": "holds"}},
                    {"index": 16, "phase": "top", "removed": 0.39, "top_holes": 12, "saved_lb": 5.0, "safety": 2.1,
                     "holds": True, "verdict": {"kind": "holds"}},
                    {"index": 15, "phase": "top", "removed": 0.41, "top_holes": 11, "saved_lb": 5.4, "safety": 1.0,
                     "holds": False, "verdict": {"kind": "fails", "word": "doesn't hold"}},
                    {"index": 17, "phase": "thinner", "estimate": True, "label": "5/8 in", "thickness_mm": 15.875,
                     "saved_lb": 6.6, "safety": 2.0, "holds": True, "verdict": {"kind": "estimate"}}]}


def _lighten(picked, version=6):
    src = open(JS).read()
    return _run(STUBS + _fn(src, "sheetUse") + _fn(src, "stepAction") + _fn(src, "lightenView") + f"""
const run = {json.dumps(RUN)};
const S = {{ station: {('{ run: "r1", index: %d }' % picked) if picked is not None else 'null'} }};
const lightenRuns = () => [run], lightenLeadLine = () => '', lightenBlocked = () => '', lightenLead = () => 'lead';
const lightenNone = () => '', lightenChanged = () => '';
console.log(JSON.stringify(lightenView({{ id: 'step_stool', version: {version} }})));
""")


def test_a_picked_step_s_action_sits_by_the_table():
    html = _lighten(16)
    assert ('<button class="primary" data-step-adopt="16">Cut step 16&#39;s holes into step_stool (makes v7)</button>'
            in html.replace("'", "&#39;")), html
    assert html.index("data-step-adopt") > html.index("</table>")                      # under the table, not in the bar
    assert "data-step-adopt" not in _lighten(None)                                      # nothing picked: nothing to cut
    assert "data-step-adopt" not in _lighten(0)                                         # step 0 is the part as it is
    stale = _lighten(16, version=7)                                                     # a run of an older version
    assert "data-step-adopt" not in stale and "lighten it again" in stale


def test_an_estimate_s_use_says_what_it_does_and_waits_while_a_step_is_picked():
    free, picked = _lighten(None), _lighten(16)
    assert ">Ask for 5/8 in sheet (redesigns it; checked again after)</button>" in free
    assert not re.search(r"<button[^>]*disabled[^>]*>Ask for 5/8 in sheet", free)
    assert re.search(r"<button[^>]*disabled[^>]*>Ask for 5/8 in sheet", picked), picked
    assert ">Use</button>" not in free and ">Use</button>" not in picked


def test_the_step_s_button_is_wired_to_the_same_adopt():
    src = open(JS).read()
    assert "document.querySelectorAll('#loadBox [data-step-adopt]')" in src
    assert "adoptStation(p.id, lightenRuns(p.id)[0].id, +b.dataset.stepAdopt, 'lighten')" in src



def test_a_step_that_doesn_t_hold_can_t_be_cut_in():
    html = _lighten(15).replace("'", "&#39;")
    assert re.search(r'<button class="primary" data-step-adopt="15" disabled title="It can&#39;t be used: doesn&#39;t hold">',
                     html), html
