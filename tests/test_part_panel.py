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


def test_long_blocks_sit_one_level_down_closed_with_what_s_in_them():
    part = _fn(open(JS).read(), "partView")
    for key, summary in (("size", "`Size"), ("rules", "`Rules on this part: "), ("trial", "'Test it "),
                         ("aero", "`Shape it for drag "), ("buy", "'Built from "),
                         ("patterns", "'Patterns for hand tools: "), ("cutplan", "`The cut plan: ")):
        assert f"sub('{key}', {summary}" in part, key
    assert '<details class="sub" data-sub="history" id="partHistory"' in part
    assert "<summary>History: ${revisions} version" in part
    got = _run(_page(["subOpen"], consts=["sub"], extra="""
const store = {}; const localStorage = { getItem: (k) => (k in store ? store[k] : null) };
const shut = sub('buy', 'Built from', 'B'); store['caliper.sub.buy'] = '1';
out = { shut, kept: sub('buy', 'Built from', 'B') };"""))
    assert got["shut"] == '<details class="sub" data-sub="buy"><summary>Built from</summary>B</details>'  # closed at first
    assert got["kept"] == '<details class="sub" data-sub="buy" open><summary>Built from</summary>B</details>'


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
