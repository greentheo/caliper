"""CALI-197 (#325): the part panel, as Theo asked after taking step-stool-5 to its cutouts. Parameters on top; the four
questions as an accordion, one open, each header keeping its mark and its answer; the actions as small buttons top right,
greyed with the reason until the chain allows, from the same ready/why as the right-click menu. Layout only."""

import os

from .test_carve_click import _fn, _page, _run

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

CARDS = """
const esc = (s) => String(s);
const QUESTIONS = [['what', 'What is it?'], ['work', 'Will it work?'], ['buy', 'What do I buy?'], ['make', 'How do I make it?']];
const QMARK = { ok: '✓', warn: '!', bad: '✗', info: '·' };
const store = {};
const localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
const S = { slug: 's', scope: 'stool', focus: null, openCard: {} };
const answersKey = () => 'k';
const loadAnswers = () => {};
const picturePart = () => false;
const cardLines = (k, c) => `<div class="qline top">${k} line</div>`;
function cards(statuses) {
  S.answers = { key: 'k', cards: Object.entries(statuses).map(([key, status]) => ({ key, status })) };
  return cardsView({ what: 'W', work: 'K', buy: 'B', make: 'M' });
}
"""


def _cards(body):
    return _run(_page(["cardsView", "openCardFor"], consts=["cardStore"], extra=CARDS + body))


def _open(html):
    import re

    return re.findall(r'<section class="qcard[^"]*\bopen\b[^"]*" data-card="(\w+)"', html)


def test_one_card_is_open_the_first_that_fails_else_will_it_work():
    got = _cards("""out = { fine: cards({ what: 'ok', work: 'ok', buy: 'info', make: 'info' }),
                           bad: cards({ what: 'ok', work: 'ok', buy: 'bad', make: 'bad' }) };""")
    assert _open(got["fine"]) == ["work"] and _open(got["bad"]) == ["buy"]


def test_each_header_is_a_real_button_with_its_mark_and_its_answer_stays_in_view():
    html = _cards("out = cards({ what: 'ok', work: 'bad', buy: 'info', make: 'info' });")
    assert html.count('<button type="button" class="qtoggle"') == 4
    assert 'aria-expanded="true" aria-controls="qbody-work"' in html and 'aria-expanded="false" aria-controls="qbody-what"' in html
    assert '<span class="qmark">✗</span>' in html and '<span class="qmark">✓</span>' in html
    assert html.count('class="qline top"') == 4                                    # each answer line, open or not
    assert '<div class="qbody" id="qbody-what" role="region" aria-label="What is it?" hidden>W</div>' in html
    assert '<div class="qbody" id="qbody-work" role="region" aria-label="Will it work?">K</div>' in html


def test_the_open_card_is_remembered_per_part():
    got = _cards("""S.openCard[cardStore()] = 'make'; const a = cards({ what: 'ok', work: 'bad', buy: 'info', make: 'info' });
                    S.scope = 'other'; const b = cards({ what: 'ok', work: 'ok', buy: 'info', make: 'info' });
                    out = { a, b };""")
    assert _open(got["a"]) == ["make"] and _open(got["b"]) == ["work"]


BAR = """
const esc = (s) => String(s);
const S = { slug: 's', carveJob: {}, design: { in_air: { yes: false }, studies: { menu: { stool: [
  { kind: 'load', ready: true, why: '' },
  { kind: 'lighten', ready: false, why: "it doesn't pass its loads yet: 1.10 where it needs 1.3" },
  { kind: 'carve', ready: false, why: 'it has no printed piece' },
  { kind: 'aero', ready: false, why: 'not in air' },
  { kind: 'cutplan', ready: false, why: 'check it holds first' }] } } } };
const carveKey = (p) => p;
const loadRuns = () => [{ id: 'L1' }], lightenRuns = () => [], carveRuns = () => [], aeroRuns = () => [], runsFor = () => [];
const cutplanRun = () => null;
const p = { id: 'stool', study: 'lighten', built: true, loads: true, role: 'movable', framed: false };
"""


def test_the_actions_are_small_buttons_in_the_chain_s_order_greyed_with_the_menu_s_reason():
    html = _run(_page(["partActions"], extra=BAR + "out = partActions(p);"))
    order = [html.index(f'id="{i}"') for i in ("lGo", "lightGo", "cpGo")]
    assert order == sorted(order) and 'id="carveGo"' not in html and 'id="aGo"' not in html   # its study, in air only
    assert '>Check it again<' in html
    assert 'id="lightGo" aria-disabled="true" data-why="it doesn\'t pass its loads yet: 1.10 where it needs 1.3"' in html
    assert 'title="Not yet: check it holds first"' in html                           # on hover; on tap, below the bar
    assert 'id="lGo" aria-disabled' not in html
    assert 'role="toolbar"' in html and 'id="pactsWhy"' in html and 'aria-live="polite"' in html


def test_a_running_carve_shows_on_its_button():
    html = _run(_page(["partActions"], extra=BAR + """
S.design.studies.menu.stool[2] = { kind: 'carve', ready: true, why: '' }; p.study = 'carve';
S.carveJob.stool = { job: 'j1' };
out = partActions(p);"""))
    assert 'id="carveGo" disabled' in html


def test_a_greyed_button_says_why_and_never_runs():
    fn = _fn(open(JS).read(), "wirePartActions")
    assert "bar.addEventListener('click'" in fn and ", true);" in fn                     # caught before its own onclick
    assert "e.stopPropagation()" in fn and "why.textContent = b.dataset.why" in fn


def test_parameters_sit_at_the_top_and_the_in_card_buttons_are_gone():
    src = open(JS).read()
    part = _fn(src, "partView")
    assert part.index("partActions(p)") < part.index('<div id="paramBox">') < part.index("cardsView(")
    assert "groups.params" not in _fn(src, "cardsView")
    for view, gone in (("loadView", 'id="lGo"'), ("carveView", 'id="carveGo"'), ("lightenView", 'id="lightGo"'),
                       ("cutplanView", 'id="cpGo"'), ("aeroView", 'id="aGo"')):
        assert gone not in _fn(src, view), view                                     # each action has one place


def test_sections_inside_a_card_carry_their_mark_and_answer_and_the_one_that_needs_a_look_opens():
    """Theo's refinements (2): each section's header has its mark and its one-line answer; one open at a time; the one
    that needs attention first, else the first; the one kept, once one is."""
    got = _run(_page(["subKept", "subsOpen", "ssecs"], consts=["cardStore", "subKey", "ATTN", "subHead", "SUB_ONE"],
                     extra="""
const QMARK = { ok: '✓', warn: '!', bad: '✗', info: '·' };
const store = {}; const localStorage = { getItem: (k) => (k in store ? store[k] : null) };
const S = { slug: 's', scope: 'stool', subOpen: {} };
const list = [{ k: 'result', title: 'Will it hold?', tone: 'ok', answer: 'holds 2.2x', body: 'R' },
              { k: 'fix', title: 'Things to fix', tone: 'warn', answer: '3 measured wrong', body: 'F', attrs: ' id="fixBox"' },
              { k: 'trial', title: 'Test it', tone: 'info', answer: '', body: 'T' }];
const attn = ssecs('work', list);
const calm = ssecs('work', list.map((x) => ({ ...x, tone: 'info' })));
S.subOpen['s/stool/work'] = 'trial';
out = { attn, calm, kept: ssecs('work', list) };"""))
    import re

    def opened(html):
        return re.findall(r'data-ssec="(\w+)"[^>]*? open>', html)
    assert opened(got["attn"]) == ["fix"] and opened(got["calm"]) == ["result"] and opened(got["kept"]) == ["trial"]
    html = got["attn"]
    assert '<details class="ssec t-warn attn" data-ssec="fix" data-in="work" id="fixBox" open>' in html
    assert ('<summary><span class="qmark">!</span><span class="stitle">Things to fix</span><span class="sanswer">3 measured wrong'
            '</span></summary>') in html
    assert '<span class="qmark">✓</span><span class="stitle">Will it hold?</span>' in html


def test_one_open_at_a_time_is_a_single_switch():
    src = open(JS).read()
    assert "const SUB_ONE = true;" in src and src.count("SUB_ONE") >= 4
    keep = _fn(src, "keepSub")
    assert "if (SUB_ONE && dt.open) {" in keep                        # the others close only under the switch
    assert "if (!SUB_ONE) return new Set(" in _fn(src, "subsOpen")     # off: each by what it was left as


def test_a_problem_inside_shows_on_its_card_s_header():
    got = _cards("""out = cardsView({ what: 'W', work: '<details class="ssec t-bad attn" data-ssec="fix">', buy: 'B', make: 'M' });""")
    head = got.split('data-card="work"')[1].split("</h3>")[0]
    assert 'class="qinside" title="something inside needs a look"' in head
    assert "qinside" not in got.split('data-card="what"')[1].split("</h3>")[0]


def test_parameters_collapse_open_at_first_with_a_mark_where_something_needs_a_look():
    page = """
const loadRuns = () => runs; let runs = [];
const paramName = (e) => e.label, paramUnit = (e) => (e.name === 'n' ? '' : 'in');
const p = { id: 'stool', version: 12, loads: true };
const row = (name, label, value, shown, extra) => ({ e: { name, label, value, range: [0, 500] }, shown, problem: '', changed: false, ...extra });
const rows = [row('w', 'Side to side', 406, '16'), row('ply_t', 'Ply thickness', 19.05, '3/4')];
out = { fine: paramsHead(p, rows) };
runs = [{ version: 11 }]; out.since = paramsHead(p, rows);
out.dirty = paramsHead(p, [rows[0], { ...rows[1], changed: true }]);
out.bad = paramsHead(p, [rows[0], { ...rows[1], changed: true, problem: 'Must be 0 to 50 in.' }]);
runs = []; out.out = paramsHead(p, [row('w', 'Side to side', 600, '24'), rows[1]]);"""
    got = _run(_page(["paramsHead"], extra=page))
    assert got["fine"] == {"tone": "info", "answer": "2 numbers · Ply thickness 3/4 in"}
    assert got["since"] == {"tone": "warn", "answer": "2 numbers · Ply thickness 3/4 in · changed since its check"}
    assert got["dirty"]["tone"] == "warn" and got["dirty"]["answer"].endswith("1 changed, not rebuilt yet")
    assert got["bad"] == {"tone": "bad", "answer": "2 numbers · Ply thickness 3/4 in · 1 won't do"}
    assert got["out"]["answer"].endswith("Side to side is outside its range") and got["out"]["tone"] == "warn"
    src = open(JS).read()
    assert '<details class="params psec t-${head.tone}" id="paramSec"${paramsOpen() ? \' open\' : \'\'}>' in _fn(src, "paramsHtml")
    assert "localStorage.getItem('caliper.params.open') !== '0'" in _fn(src, "paramsOpen")       # open by default


def test_each_action_opens_the_section_it_feeds():
    src = open(JS).read()
    assert ("const GO_OPENS = { lGo: ['work', 'result'], lightGo: ['work', 'lighten'], carveGo: ['work', 'carve'], "
            "aGo: ['work', 'aero'],\n  cpGo: ['make', 'cutplan'] };") in src
    bar = _fn(src, "wirePartActions")
    assert bar.index("if (b && GO_OPENS[b.id]) showSection(...GO_OPENS[b.id]);") < bar.index("e.stopPropagation()")
    show = _fn(src, "showSection")
    assert "openCard(card)" in show and "dt.open = true; keepSub(dt);" in show


def test_lighten_carve_and_things_to_fix_are_sections_of_will_it_work():
    src = open(JS).read()
    load = _fn(src, "loadView")
    assert "lightenView(p)" not in load and "carveView(p)" not in load
    assert "fixesBox" not in src and "return qlines(c);" in _fn(src, "cardLines")
    part = _fn(src, "partView")
    for k in ("result", "lighten", "carve", "trial", "aero", "size", "rules", "history", "adv", "stock", "patterns",
              "cutplan"):
        assert f"k: '{k}'" in part, k
    assert "fixesSection(p.id)" in part and "makingSection(p)" in part and "k: 'shop'" in _fn(src, "makingSection")
    got = _run(_page(["fixesSection"], consts=["ATTN"], extra="""
const esc = (s) => String(s), fixKey = (p) => 's/' + p, fixMine = () => ({}), fixesView = () => 'LIST';
const fixStamp = () => '3|R1', fixChecked = () => true;     // the version and its newest check (#331 review)
const S = { fixes: {} };
const none = fixesSection('stool');
S.fixes['s/stool'] = { v: '3|R1', rows: [{}, {}] }; const two = fixesSection('stool');
S.fixes['s/stool'] = { v: '3|R1', rows: [] }; const zero = fixesSection('stool');
S.fixes['s/stool'] = { v: '2|R0', rows: [{}] }; const old = fixesSection('stool');
out = { none, two, zero, old };"""))
    assert (got["none"]["tone"], got["none"]["answer"]) == ("info", "measured, with what each would take")
    assert (got["two"]["tone"], got["two"]["answer"]) == ("warn", "2 measured wrong") and "LIST" in got["two"]["body"]
    assert (got["zero"]["tone"], got["zero"]["answer"]) == ("ok", "nothing measured wrong")
    assert got["old"]["tone"] == "info" and "reading them" in got["old"]["body"]          # another version's list isn't this one


def test_the_marks_arriving_keep_the_open_card_and_follow_the_first_that_fails():
    """Seen on 8016: the answers' repaint set each card's class afresh and dropped "open" (and "focus"); and a card drawn
    before its marks opened Will it work? where a later ✗ should have been the one."""
    fn = _fn(open(JS).read(), "loadAnswers")
    assert "${card.classList.contains('open') ? ' open' : ''}${card.classList.contains('focus') ? ' focus' : ''}" in fn
    assert fn.index("showOpen(openCardFor(S.answers));") < fn.index("wireCards();")


def test_a_link_to_a_panel_opens_its_card_and_every_block_it_sits_in():
    """A card line's link (goTo) opened "the numbers"; now it opens the card the panel's in, and each closed block around
    it, as History's link and the strength check's do."""
    fn = _fn(open(JS).read(), "goTo")
    assert "if (sec && !sec.classList.contains('open')) openCard(sec.dataset.card);" in fn
    assert "for (let dt = box.closest('details'); dt; dt = dt.parentElement && dt.parentElement.closest('details')) dt.open = true;" in fn
