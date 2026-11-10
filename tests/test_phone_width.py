"""CALI-133 (#164) — at phone width the page's three fixed columns hid the cards, and `body` doesn't scroll. One pane at a time, with tabs,
and the part tree as a drawer. Layout is checked in a real browser; this pins that the pieces are there and what switching does."""
import json
import os
import re
import subprocess

from .test_carve_click import _fn, _node

WEB = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static")
JS, CSS, HTML = (os.path.join(WEB, n) for n in ("design.js", "design.css", "index.html"))


def _phone_css() -> str:
    css = open(CSS).read()
    return css[css.index("@media (max-width: 700px)"):]


def test_the_tabs_exist_only_at_phone_width():
    css = open(CSS).read()
    assert ".pane-tabs { display: none; }" in css and re.search(r"\.pane-tabs \{ display: flex;", _phone_css())


def test_the_page_has_a_tab_for_each_pane_and_the_tree():
    html = open(HTML).read()
    for tab in ('data-pane="view"', 'data-pane="chat"', 'data-pane="cards"', 'id="treeTab"'):
        assert tab in html


def test_each_pane_is_shown_by_its_tab():
    css = _phone_css()
    for sel in ('body[data-pane="chat"] .chat', 'body[data-pane="view"] .view', 'body[data-pane="cards"] .inspector'):
        assert sel in css


def test_the_tree_is_a_drawer_that_stays_clear_of_the_tabs():
    css = _phone_css()
    assert "body.tree-open .tree { transform: none; }" in css and "bottom: 56px" in css and "visibility: visible" in css


def test_the_studies_pages_cover_a_phone():
    assert ".studies-page { left: 0; }" in _phone_css()


def test_choosing_a_pane_marks_its_tab_and_shuts_the_drawer():
    head = """const tabs = ['view', 'chat', 'cards'].map((p) => ({ dataset: { pane: p }, on: false, classList: { toggle(c, v) { this.owner.on = v; } } }));
tabs.forEach((t) => { t.classList.owner = t; });
const cl = new Set(['tree-open']);
const document = { body: { dataset: {}, classList: { remove: (c) => cl.delete(c) } }, querySelectorAll: () => tabs };
"""
    script = head + _fn(open(JS).read(), "setPane") + """setPane('cards');
console.log(JSON.stringify({ pane: document.body.dataset.pane, on: tabs.filter((t) => t.on).map((t) => t.dataset.pane), open: cl.has('tree-open') }));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"pane": "cards", "on": ["cards"], "open": False}
