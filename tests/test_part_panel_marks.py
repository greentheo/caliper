"""CALI-197 (#331), reviewer-2's review at d708dc6: a mark or a button on the part panel says only what's so.

- Things to fix's mark is of the part's newest check, not the version alone, and "·" with no check of this version.
- Made in your shop is this design's plan, its header repainted when the plan lands; a part that doesn't build "can't
  plan it", never ✗.
- Make the cut plan is greyed where cut plans can't be made here, with the reason; its click never throws.
- The chain's first link wins; its safety is cut as the card cuts it; a running job says so on its button."""

import os

from caliper import studies

from .test_carve_click import _fn, _page, _run
from .test_part_panel import BAR

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

FIX = """
const esc = (s) => String(s);
const fixMine = () => ({}), fixRow = () => '<div class="fixrow"></div>';
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
    return _run(_page(["fixesSection", "fixStamp", "fixChecked", "fixesView"],
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
    fn = _fn(open(JS).read(), "wireFixes")
    assert "if (!fresh()) loadFixes(part);" in fn and "getFixes" not in fn
    assert "got.v === fixStamp(part)" in fn                             # its stamp: the version and the newest check


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
out = { bad: head('a', { ok: false, missing: [] }), none: head('a', { ok: null, missing: [] }) };"""))
    assert got["bad"]["other"] == ["info", "planning…"] and got["bad"]["mine"] == ["bad", "not all of it"]
    assert got["none"]["mine"] == ["info", "can't plan it: it doesn't build"]


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
    html = _run(_page(["partActions"], extra=BAR + """
S.design.studies.menu.stool[1] = { kind: 'lighten', ready: true, why: '' };
S.design.running = [{ job: 'j1', kind: 'lighten', part: 'stool' }, { job: 'j2', kind: 'load', part: 'other' }];
out = partActions(p);"""))
    assert '>Lightening…<' in html and 'id="lightGo" disabled' in html
    assert '>Check it again<' in html and 'id="lGo" disabled' not in html      # another part's check isn't this one's
