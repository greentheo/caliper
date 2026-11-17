"""CALI-197 (#331) item 6: Fix these is the part's, top right with its other actions (#325), now that #322 is in.

- It's on the bar where the list, read for this version and its newest check, has rows: last, after the cut plan.
- Greyed, with why, while nothing's ticked; "Fixing…" while it runs; none where the list isn't read, is stale, failed or
  is empty.
- Pressing it opens Things to fix and asks the plan there: its cost is said before anything runs.
- The list's own big button is gone: each action has one place."""

import json
import os

from .test_carve_click import _fn, _page, _run
from .test_part_panel import BAR_ONLY

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
FIXES = ["fixAct", "fixFresh", "fixStamp", "fixPicked", "fixTicked", "fixMine"]
ROW = {"id": "plate:top", "problem": "The top fails", "part": "stool", "measured": True,
       "choices": [{"fix": "Make the top from 5/8 in", "kind": "number", "cost": "x"}]}
KEY = "plate:top|The top fails"

LIST = """
S.design.parts = [{ id: 'stool', version: 3 }];
const fixVersion = () => 3;
const list = (rows, more) => { S.fixes = { 's/stool': { rows, limits: [], v: fixStamp('stool'), ...(more || {}) } }; };
"""


def _bar(body):
    return _run(_page(["partActions", "runningLabel"] + FIXES, consts=["fixKey", "fixRowKey"],
                      extra=BAR_ONLY + LIST + body))


def _fix_go(html):
    """The bar's Fix these button, or None."""
    if 'id="fixGo"' not in html:
        return None
    return html.split('id="fixGo"', 1)[1].split("</button>", 1)[0]


def test_fix_these_is_last_on_the_bar_where_the_list_has_ticked_rows():
    html = _bar(f"list([{json.dumps(ROW)}]); out = partActions(p);")
    order = [html.index(f'id="{i}"') for i in ("lGo", "lightGo", "cpGo", "fixGo")]
    assert order == sorted(order)                                      # the chain's order, Fix these last (#325)
    b = _fix_go(html)
    assert b.endswith(">Fix these") and "aria-disabled" not in b and " disabled" not in b


def test_no_fix_these_where_the_list_isn_t_read_is_stale_failed_or_empty():
    got = _bar(f"""
out = {{}};
out.unread = partActions(p);
list([{json.dumps(ROW)}], {{ v: 'stale|' }}); out.stale = partActions(p);
list([{json.dumps(ROW)}], {{ error: 'Internal Server Error' }}); out.failed = partActions(p);
list([]); out.empty = partActions(p);""")
    assert {k: _fix_go(v) for k, v in got.items()} == {"unread": None, "stale": None, "failed": None, "empty": None}


def test_fix_these_is_greyed_with_why_while_nothing_s_ticked():
    got = _bar(f"""
list([{json.dumps(ROW)}]);
fixMine('stool').untick = ['{KEY}'];
out = {{ none: partActions(p) }};
fixMine('stool').own = [{{ fix: 'round the corners' }}];             // your own words ticked: something to fix
out.own = partActions(p);""")
    none = _fix_go(got["none"])
    assert 'aria-disabled="true" data-why="nothing\'s ticked in Things to fix"' in none
    assert 'title="Not yet: nothing\'s ticked in Things to fix"' in none
    assert "aria-disabled" not in _fix_go(got["own"])


def test_an_open_question_left_unticked_is_nothing_to_fix():
    """#318: a question starts unticked; alone, there's nothing to fix until the person ticks it."""
    q = {**ROW, "id": "asked:x", "problem": "You'd edited x", "ticked": False}
    got = _bar(f"""
list([{json.dumps(q)}]);
out = {{ before: partActions(p) }};
fixMine('stool').tick = ["asked:x|You'd edited x"];
out.after = partActions(p);""")
    assert "aria-disabled" in _fix_go(got["before"]) and "aria-disabled" not in _fix_go(got["after"])


def test_fix_these_says_fixing_while_it_runs():
    b = _fix_go(_bar(f"list([{json.dumps(ROW)}]); fixMine('stool').running = true; out = partActions(p);"))
    assert b.endswith(">Fixing…") and " disabled" in b


def test_pressing_it_opens_things_to_fix():
    got = _run(_page([], consts=["GO_OPENS"], extra="out = GO_OPENS.fixGo;"))
    assert got == ["work", "fix"]


PRESS = """
const esc = (s) => String(s), plainly = (s) => s;
const S = { slug: 's', scope: 'stool', fixes: {}, design: { parts: [{ id: 'stool', version: 3 }] } };
const fixVersion = () => 3, loadRuns = () => [];
const els = {};
const bar = { n: 0, insertAdjacentHTML: (_, html) => {
  bar.n += 1;
  els.fixGo = { html, disabled: false, remove() { bar.n -= 1; delete els.fixGo; } };
} };
els.pacts = bar;
const $ = (id) => els[id] || null;
let painted = 0;
const paintFixes = () => { painted += 1; };
const posted = [];
let answer = { said: '1 number change, at once; then a check, about 1 min' };
const api = async (method, url, body) => { posted.push([method, url, body]); if (answer instanceof Error) throw answer; return answer; };
S.fixes['s/stool'] = { rows: [ROW], limits: [], v: fixStamp('stool') };
"""


def _press(body):
    return _run(_page(["paintFixAct", "fixPlan"] + FIXES, consts=["fixKey", "fixRowKey"],
                      extra=f"const ROW = {json.dumps(ROW)};" + PRESS + body))


def test_pressing_fix_these_asks_the_plan_for_what_s_ticked_and_says_it_in_the_list():
    got = _press("""
paintFixAct('stool');
const drawn = els.fixGo.html;
await els.fixGo.onclick();
out = { drawn, posted, plan: fixMine('stool').plan, painted };""")
    assert got["drawn"].endswith(">Fix these</button>")
    assert got["posted"] == [["POST", "/api/designs/s/parts/stool/fixes/plan",
                              {"picked": [{"id": "plate:top", "choice": 0}], "own": []}]]
    assert got["plan"] == {"said": "1 number change, at once; then a check, about 1 min"} and got["painted"] == 1


def test_a_refused_plan_says_why_in_the_list_and_the_button_comes_back():
    got = _press("""
answer = new Error('stool is being checked: wait for it, or stop that first.');
paintFixAct('stool');
const b = els.fixGo;
await b.onclick();
out = { error: fixMine('stool').error, plan: fixMine('stool').plan || null, disabled: b.disabled };""")
    assert got == {"error": "stool is being checked: wait for it, or stop that first.", "plan": None, "disabled": False}


def test_the_bar_s_button_is_drawn_again_alone_and_only_for_the_part_in_view():
    got = _press("""
paintFixAct('stool');
const first = !!els.fixGo;
fixMine('stool').untick = ['plate:top|The top fails'];
paintFixAct('stool');                                   // a tick changed: drawn again, greyed, one of it
const greyed = els.fixGo.html, one = bar.n;
S.scope = 'other';
delete els.fixGo;
paintFixAct('stool');                                   // another part in view: its bar isn't this list's
out = { first, greyed, one, other: !!els.fixGo };""")
    assert got["first"] and 'aria-disabled="true"' in got["greyed"] and got["one"] == 1 and got["other"] is False


def test_the_list_repaints_draws_and_ticks_keep_the_bar_s_button_true():
    src = open(JS).read()
    assert "paintFixAct(part);" in _fn(src, "paintFixes")             # the list lands: the button with it
    assert "paintFixAct(part);" in _fn(src, "wireFixes")              # a draw wires the one partActions drew
    rows = _fn(src, "wireFixRows")
    assert rows.count("paintFixAct(part);") == 2                      # a row's tick, your own row's tick
    assert "data-fix-plan" not in rows and "fixAct(p.id)" in _fn(src, "partActions")


def test_the_list_has_no_fix_these_of_its_own():
    """#325: each action has one place. The list keeps the plan's cost, Go ahead, and what the last fix did."""
    html = _run(_page(["fixesView", "fixRow", "fixGo", "fixTicked"], consts=["esc", "fixRowKey"],
                      extra=f"out = fixesView({json.dumps({'part': 'stool', 'rows': [ROW], 'limits': []})}, {{}});"))
    assert "data-fix-plan" not in html and "Fix these" not in html and "fixrow" in html
