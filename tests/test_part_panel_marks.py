"""CALI-197 (#331), reviewer-2's review at d708dc6: a mark or a button on the part panel says only what's so.

- Things to fix's mark is of the part's newest check, not the version alone, and "·" with no check of this version.
- Made in your shop is this design's plan, its header repainted when the plan lands; a part that doesn't build "can't
  plan it", never ✗.
- Make the cut plan is greyed where cut plans can't be made here, with the reason; its click never throws.
- The chain's first link wins; its safety is cut as the card cuts it; a running job says so on its button."""

import os

import pytest

from caliper import studies

from .test_carve_click import _fn, _page, _run
from .test_part_panel import BAR

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

FIX = """
const esc = (s) => String(s);
const fixMine = () => ({}), fixRow = () => '<div class="fixrow"></div>', fixGo = () => '';
const S = { slug: 's', fixes: {}, design: { parts: [{ id: 'stool', version: 3 }], load_runs: [] } };
const fixVersion = () => 3;
const loadRuns = (pid) => S.design.load_runs.filter((r) => r.part === pid);
const k = fixKey('stool');
function mark(runs, rows, stamp) {
  S.design.load_runs = runs;
  S.fixes[k] = { rows, limits: [], v: stamp === undefined ? fixStamp('stool') : stamp };
  const x = fixesSection('stool');
  return [x.tone, x.answer];
}
"""


def _fix(body):
    return _run(_page(["fixesSection", "fixFresh", "fixStamp", "fixChecked", "fixesView"],
                      consts=["fixKey"], extra=FIX + body))


def test_things_to_fix_is_never_a_tick_with_no_check_of_this_version():
    """The 500 lb copy, never checked: "✓ Things to fix · nothing measured wrong" beside "Will it hold? · not checked yet"."""
    got = _fix("""out = { never: mark([], []), older: mark([{ id: 'R1', part: 'stool', version: 2 }], []),
                          checked: mark([{ id: 'R1', part: 'stool', version: 3 }], []),
                          rows: mark([], [{ id: 'rule:b' }]) };""")
    assert got["never"] == ["info", "not checked yet"] and got["older"] == ["info", "not checked yet"]
    assert got["checked"] == ["ok", "nothing measured wrong"]
    assert got["rows"] == ["warn", "1 measured wrong"]                 # a rule row needs no check to be wrong


def test_things_to_fix_read_before_the_newest_check_isn_t_its_mark():
    """A check of the same version left "✓ nothing measured wrong" beside "✗ doesn't hold 1.0x" (and "! 3" beside 0)."""
    got = _fix("""const before = [{ id: '20261117-010000-check', part: 'stool', version: 3 }];
                  S.design.load_runs = before; const stamp = fixStamp('stool');
                  const now = [{ id: '20261117-020000-check', part: 'stool', version: 3 }, ...before];
                  out = { stale: mark(now, [], stamp), stale3: mark(now, [{ id: 'a' }, { id: 'b' }, { id: 'c' }], stamp),
                          fresh: mark(now, []) };""")
    assert got["stale"] == ["info", "measured, with what each would take"] and got["stale3"] == got["stale"]
    assert got["fresh"] == ["ok", "nothing measured wrong"]


def test_things_to_fix_reads_its_list_again_when_a_check_lands_open_or_not():
    src = open(JS).read()
    fn = _fn(src, "wireFixes")
    assert "if (!fresh()) loadFixes(part);" in fn and "getFixes" not in fn and "fixFresh(part)" in fn
    assert "got.v === fixStamp(part)" in _fn(src, "fixFresh")          # its stamp: the version and the newest check


SHOP = """
const esc = (s) => String(s);
const makingView = () => '';
const S = { slug: 'a', making: {}, shopKey: 0 };
const p = { id: 'step_stool', version: 12 };
function head(slug, data) {
  S.slug = 'b'; S.making[p.id] = { key: makingKey(p), data };      // another design's plan, a part of the same name
  S.slug = slug;
  const other = makingSection(p);
  S.making[p.id] = { key: makingKey(p), data };
  const mine = makingSection(p);
  return { other: [other.tone, other.answer], mine: [mine.tone, mine.answer] };
}
"""


def test_made_in_your_shop_is_this_design_s_plan_and_a_part_that_doesn_t_build_can_t_be_planned():
    """reviewer-2: the broken-build copy's "⚠ … ply_t must be positive" under the v12 copy, which builds; and a ✗ "not all
    of it" under ✓ How do I make it?"""
    got = _run(_page(["makingSection", "makingKey"], extra=SHOP + """
out = { bad: head('a', { ok: false, missing: [] }) };"""))
    assert got["bad"]["other"] == ["info", "planning…"] and got["bad"]["mine"] == ["bad", "not all of it"]


def test_made_in_your_shop_repaints_its_header_when_its_plan_lands():
    src = open(JS).read()
    load = _fn(src, "loadMaking")
    assert "makingSection(p)" in load and "querySelector('summary')" in load and "subHead(" in load
    assert "S.making[p.id] && S.making[p.id].data" not in src           # the header reads the plan through its key


def test_the_cut_plan_is_greyed_where_it_can_t_be_made_here():
    stool = {"id": "stool", "scripted": True, "built": True, "loads": False, "bbox": {"size": [1, 1, 1]}}
    why = "unfold-to-sheets isn't at /x (run `make tools`, or set CALIPER_UNFOLD_DIR)"
    got = {m["kind"]: m for m in studies.menu(stool, None, None, cut_off=why)}
    assert not got["cutplan"]["ready"] and got["cutplan"]["why"] == f"not here: {why}"
    assert {m["kind"]: m for m in studies.menu(stool, None, None)}["cutplan"]["ready"]


def test_the_page_s_menu_reads_whether_cut_plans_can_be_made_here(tmp_path, monkeypatch):
    from caliper import cutplan, design_api
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL, intent="a stool")
    monkeypatch.setattr(cutplan, "available", lambda: "node isn't installed (unfold-to-sheets runs on node)")
    state = design_api.design_state(s)
    item = {m["kind"]: m for m in state["studies"]["menu"]["stool"]}["cutplan"]
    assert not item["ready"] and item["why"] == "not here: node isn't installed (unfold-to-sheets runs on node)"
    assert state["cutplan_unavailable"] == "node isn't installed (unfold-to-sheets runs on node)"


def test_the_cut_plan_s_click_never_throws_where_it_has_no_progress_line():
    """reviewer-2: "TypeError: Cannot set properties of null (setting 'innerHTML')" at design.js:3317, the button left dead."""
    got = _run(_page(["wireCutplan"], extra="""
const els = { cpGo: { disabled: false }, pactsWhy: { textContent: '' } };
const $ = (id) => els[id] || null;
const document = { querySelectorAll: () => [] };
const wirePatterns = () => {}, wireMaking = () => {}, previewStep = () => {}, follow = async () => {}, refresh = async () => {};
const S = { slug: 's' };
const esc = (s) => String(s);
const api = async () => { throw new Error("node isn't installed"); };
wireCutplan({ id: 'stool' });
await els.cpGo.onclick();
out = { why: els.pactsWhy.textContent, disabled: els.cpGo.disabled };"""))
    assert got == {"why": "⚠ node isn't installed", "disabled": False}


def test_the_chain_s_first_link_wins():
    """On the broken build Lighten read its own "Check it holds first", not "it doesn't build yet"."""
    stool = {"id": "stool", "scripted": True, "built": True, "loads": True, "study": "lighten", "params": {"w": 1},
             "bbox": None, "blocked": {"lighten": "Check it holds first: a lightening starts from its strength check"}}
    got = {m["kind"]: m for m in studies.menu(stool, {"yes": True, "why": ""}, None)}
    assert got["lighten"]["why"] == "it doesn't build yet" and not got["lighten"]["ready"]


def test_the_chain_s_safety_is_cut_never_rounded_up_to_the_line():
    assert studies.chain({"bbox": {}, "loads": True}, {"ok": False, "safety": 1.996, "need": 2}) == \
        "it doesn't pass its loads yet: 1.99 where it needs 2"


def test_a_running_check_or_lighten_shows_on_its_button():
    html = _run(_page(["partActions", "runningLabel"], extra=BAR + """
S.design.studies.menu.stool[1] = { kind: 'lighten', ready: true, why: '' };
S.design.running = [{ job: 'j1', kind: 'lighten', part: 'stool' }, { job: 'j2', kind: 'load', part: 'other' }];
out = partActions(p);"""))
    assert '>Lightening…<' in html and 'id="lightGo" disabled' in html
    assert '>Check it again<' in html and 'id="lGo" disabled' not in html      # another part's check isn't this one's


#: a part whose script raises where it reads its numbers, as the broken-build copy's ply_t −1 did
BROKEN = """import cadquery as cq

PARAMS = {"ply_t": -1.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    if p["ply_t"] <= 0:
        raise ValueError("ply_t must be positive")
    return cq.Workplane().box(100, 100, p["ply_t"])


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    if p["ply_t"] <= 0:
        raise ValueError("ply_t must be positive")
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": p["ply_t"],
             "outline": [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]}]
"""

#: the page's own fetch, answering as the route did
FETCH = """
let answer;
globalThis.fetch = async () => ({ ok: answer.status < 400, status: answer.status, json: async () => answer.body });
const window = {};
"""


def _route(tmp_path, monkeypatch, script, path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.design import DesignStore
    from caliper.server import create_app

    s = DesignStore.create("a broken stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a stool")
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    got = TestClient(create_app()).get(f"/api/designs/{s.design.slug}/parts/stool/{path}")
    return {"status": got.status_code, "body": got.json()}


def test_made_in_your_shop_on_a_part_that_doesn_t_build_reads_can_t_plan_it(tmp_path, monkeypatch):
    """reviewer-2 at 09c753c: the route answers a part that doesn't build with a 422, never ``ok: null``, so the header
    sat at "planning…" over "⚠ couldn't read what 'step_stool' is built from: ValueError: ply_t must be positive"."""
    import json

    answer = _route(tmp_path, monkeypatch, BROKEN, "making")
    assert answer["status"] == 422 and "ply_t must be positive" in answer["body"]["detail"], answer
    got = _run(_page(["loadMaking", "makingSection", "makingKey", "api"], extra=FETCH + f"""
answer = {json.dumps(answer)};
const esc = (s) => String(s), makingView = () => '', $ = () => null;
const S = {{ slug: 'a', making: {{}}, shopKey: 0, scope: 'stool' }};
const p = {{ id: 'stool', version: 1 }};
await loadMaking(p, makingKey(p));
const broke = makingSection(p);
answer = {{ status: 500, body: {{ detail: 'Internal Server Error' }} }};
await loadMaking(p, makingKey(p));
const other = makingSection(p);
out = {{ broke: [broke.tone, broke.answer], other: [other.tone, other.answer] }};"""))
    assert got["broke"] == ["info", "can't plan it: it doesn't build"]
    assert got["other"] == ["info", "couldn't plan it"]                  # a failed read isn't the part's, nor a ✓ or ✗


FAILING = """
const esc = (s) => String(s), plainly = (s) => s;
const fixMine = () => ({}), fixRow = () => '<div class="fixrow"></div>', fixGo = () => '', paintFixes = () => {};
const paintFixAct = () => {};
const S = { slug: 's', fixes: {}, design: { parts: [{ id: 'stool', version: 3 }],
                                           load_runs: [{ id: '20261117-020000-check', part: 'stool', version: 3 }] } };
const fixVersion = () => 3;
const loadRuns = (pid) => S.design.load_runs.filter((r) => r.part === pid);
let asked = 0;
const read = globalThis.fetch;
globalThis.fetch = async (...a) => { asked += 1; return read(...a); };
"""


def test_a_failed_read_of_things_to_fix_says_so_and_is_read_again():
    """reviewer-2 at 09c753c: a 500 from /fixes beside "✗ Will it hold? · doesn't hold 1.0x" read "✓ Things to fix ·
    nothing measured wrong", and stayed ✓ once the server's list had 3 rows."""
    got = _run(_page(["loadFixes", "fixesSection", "fixFresh", "fixStamp", "fixChecked", "fixesView", "wireFixes", "api"],
                     consts=["fixKey"], extra=FETCH + FAILING + """
const box = { dataset: { fixPart: 'stool' }, open: false };
const $ = (id) => (id === 'fixBox' ? box : null);
answer = { status: 500, body: { detail: 'Internal Server Error' } };
await loadFixes('stool');
const failed = fixesSection('stool');
const stale = fixFresh('stool');
answer = { status: 200, body: { rows: [{ id: 'a' }, { id: 'b' }, { id: 'c' }], limits: [] } };
wireFixes();                                            // the next draw
await new Promise((r) => setTimeout(r, 0));
const again = fixesSection('stool');
out = { failed: [failed.tone, failed.answer], stale, again: [again.tone, again.answer], asked };"""))
    assert got["failed"] == ["info", "couldn't read them"] and got["stale"] is False
    assert got["again"] == ["warn", "3 measured wrong"] and got["asked"] == 2


def test_things_to_fix_repaints_its_header_when_its_list_lands():
    """reviewer-2's M10: without it the closed header kept "measured, with what each would take"."""
    got = _run(_page(["paintFixes"], extra="""
const head = { innerHTML: 'measured, with what each would take' };
const box = { dataset: { fixPart: 'stool' }, querySelector: (q) => (q === 'summary' ? head : null),
              classList: { toggle: () => {} } };
const els = { fixBody: { innerHTML: '' }, fixBox: box };
const $ = (id) => els[id] || null;
const S = { fixes: { k: { rows: [1, 2, 3] } } };
const fixKey = () => 'k', fixMine = () => ({}), fixesView = () => 'rows', wireFixRows = () => {}, ATTN = () => true;
const paintFixAct = () => {};
const fixesSection = () => ({ answer: '3 measured wrong' }), subHead = (x) => `· ${x.answer}`;
paintFixes('stool');
out = head.innerHTML;"""))
    assert got == "· 3 measured wrong"


def test_a_job_started_here_says_so_on_its_button_and_gives_it_back():
    """reviewer-2: "Lighten it" stayed, disabled, through 16 s of steps in the tab that pressed it."""
    got = _run(_page(["jobOff", "jobOn", "runningLabel"], extra="""
const b = { disabled: false, title: '', textContent: 'Lighten it', dataset: {} };
jobOff(b, runningLabel('lighten'));
const on = [b.textContent, b.disabled];
jobOn(b); jobOff(b, runningLabel('lighten'));            // drawn again while it runs
const again = b.textContent;
jobOn(b);
const drawn = { disabled: true, title: '', textContent: 'Lightening…', dataset: {} };   // drawn running by partActions
jobOff(drawn, runningLabel('lighten'));
out = { on, again, off: [b.textContent, b.disabled], drawn: drawn.textContent, other: runningLabel('release') };"""))
    assert got == {"on": ["Lightening…", True], "again": "Lightening…", "off": ["Lighten it", False], "drawn": "Lightening…",
                   "other": ""}
    assert "jobOff(go, runningLabel(t.kind))" in _fn(open(JS).read(), "paintJobs")


def test_the_cut_plan_section_says_not_here_where_it_can_t_be_made():
    """reviewer-2: the button read "not here", its section "· Cut plan · not made yet"."""
    part = _fn(open(JS).read(), "partView")
    assert "!cut ? (S.design.cutplan_unavailable ? 'not here' : 'not made yet')" in part
