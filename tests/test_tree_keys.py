"""CALI-102 (#94): moving a part in the tree without a mouse. #204 left no keyboard way to move a part, and none at all at
phone width, where rows can't be dragged. A focused part row moves with Alt+arrows, and the part menu has *Move in the tree ▸*
(a long-press on a phone). Each is a drop the drag already makes (``dropped``), so it saves ``part_tree`` and nothing else."""
import json
import os
import re
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

# a, with b under it and c under b; then d and e at the top level
NESTED = {"order": list("abcde"), "parent": {"b": "a", "c": "b"}}


def _keys_const(src):
    """The page's own TREE_KEYS: which arrow moves which way."""
    return re.search(r"^const TREE_KEYS = .*$", src, re.M).group(0) + "\n"


def _run(body, tree_=None, extra=""):
    src = open(JS).read()
    design = json.dumps({"parts": [{"id": i, "name": i, "label": i.upper(), "version": 1, "role": "part", "pieces": []} for i in "abcde"],
                         "tree": tree_ or {}})
    head = f"const D = {design};\n" + _keys_const(src) + extra
    names = ("treeRows", "underPart", "dropped", "nudge")
    script = head + "".join(_fn(src, n) for n in names) + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _moved(pid, way, tree_=None):
    """Where the part ends up: the tree's rows as [id, depth] after the move, or None where it can't go."""
    return _run(f"""const to = nudge(D, '{pid}', '{way}'); if (!to) return null;
                    const next = dropped(D, '{pid}', to[0], to[1]); return treeRows({{ ...D, tree: next }}).map((r) => [r.p.id, r.depth]);""", tree_)


def test_up_and_down_pass_the_part_beside_it():
    assert _moved("c", "up") == [["a", 0], ["c", 0], ["b", 0], ["d", 0], ["e", 0]]
    assert _moved("c", "down") == [["a", 0], ["b", 0], ["d", 0], ["c", 0], ["e", 0]]


def test_at_either_end_there_is_nowhere_to_go():
    assert _moved("a", "up") is None and _moved("e", "down") is None


def test_up_and_down_stay_at_the_part_s_own_level_and_take_what_sits_under_it_along():
    assert _moved("d", "up", NESTED) == [["d", 0], ["a", 0], ["b", 1], ["c", 2], ["e", 0]]        # past a and all of a's
    assert _moved("a", "down", NESTED) == [["d", 0], ["a", 0], ["b", 1], ["c", 2], ["e", 0]]
    assert _moved("b", "up", NESTED) is None and _moved("b", "down", NESTED) is None             # b is a's only part


def test_in_puts_it_under_the_part_above_as_its_last():
    assert _moved("b", "in") == [["a", 0], ["b", 1], ["c", 0], ["d", 0], ["e", 0]]
    assert _moved("d", "in", NESTED) == [["a", 0], ["b", 1], ["c", 2], ["d", 1], ["e", 0]]      # after b, a's last
    assert _moved("a", "in") is None                                                             # nothing above it


def test_out_takes_it_out_of_its_part_to_just_after_it():
    assert _moved("c", "out", NESTED) == [["a", 0], ["b", 1], ["c", 1], ["d", 0], ["e", 0]]
    assert _moved("b", "out", NESTED) == [["a", 0], ["b", 0], ["c", 1], ["d", 0], ["e", 0]]      # its own come with it
    assert _moved("a", "out", NESTED) is None


def test_a_parent_that_s_gone_doesn_t_count():
    assert _moved("b", "out", {"order": list("abcde"), "parent": {"b": "zz"}}) is None


# --- the keyboard ----------------------------------------------------------------------------------------------------------
_KEYS = """
const S = { slug: 'x', design: D }; const TREE = { rename: null }; const moved = []; let focused = null;
const moveInTree = async (drag, target, zone) => { moved.push([drag, target, zone]); };
const renderTree = () => {};
const row = (sel, key) => ({ dataset: { sel, ...(key != null ? { key } : {}) }, closest(q) { return q.includes('tname') ? this : null; } });
const document = { querySelector: (q) => ({ focus() { focused = q; } }) };
const CSS = { escape: (s) => s };
const key = (target, k, mods = {}) => ({ target, key: k, altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, ...mods,
  preventDefault() { this.stopped = true; } });
"""


def _keys(body, tree_=None):
    src = open(JS).read()
    return _run(_fn(src, "treeKey") + body, tree_, extra=_KEYS)


@pytest.mark.parametrize("k,expect", [("ArrowUp", ["c", "b", "before"]), ("ArrowDown", ["c", "d", "after"]),
                                      ("ArrowRight", ["c", "b", "into"])])
def test_alt_arrows_on_a_part_row_move_it_and_keep_focus_on_it(k, expect):
    got = _keys(f"const e = key(row('c'), '{k}'); await treeKey(e); return {{ moved, stopped: !!e.stopped, focused }};")
    assert got["moved"] == [expect] and got["stopped"]
    assert 'data-sel="c"' in got["focused"] and ":not([data-key])" in got["focused"]


def test_alt_left_takes_it_out():
    got = _keys("await treeKey(key(row('c'), 'ArrowLeft')); return moved;", NESTED)
    assert got == [["c", "b", "after"]]


@pytest.mark.parametrize("why", ["plain", "piece", "ctrl", "meta", "nowhere", "renaming", "loading"])
def test_nothing_moves_without_alt_on_a_piece_or_where_it_can_t_go(why):
    body = {"plain": "const e = key(row('c'), 'ArrowUp', { altKey: false });",
            "piece": "const e = key(row('c', 'top'), 'ArrowUp');",
            "ctrl": "const e = key(row('c'), 'ArrowUp', { ctrlKey: true });",
            "meta": "const e = key(row('c'), 'ArrowUp', { metaKey: true });",
            "nowhere": "const e = key(row('a'), 'ArrowUp');",
            "renaming": "TREE.rename = { part: 'c' }; const e = key(row('c'), 'ArrowUp');",
            "loading": "S.design = null; const e = key(row('c'), 'ArrowUp');"}[why]
    got = _keys(body + " await treeKey(e); return { moved, stopped: !!e.stopped };")
    assert got["moved"] == []
    assert got["stopped"] == (why == "nowhere")          # where it can't go the key is still the tree's, not the page's scroll


def test_the_rename_box_still_takes_enter_and_escape():
    got = _keys("""let saved = 0; const input = { dataset: { renameInput: '1' }, blur() {}, closest: () => null,
                      parentElement: { querySelector: () => ({ click() { saved += 1; } }) } };
                   const e = key(input, 'Enter', { altKey: false }); await treeKey(e);
                   TREE.rename = { part: 'c' }; await treeKey(key(input, 'Escape', { altKey: false }));
                   return { saved, stopped: !!e.stopped, rename: TREE.rename, moved };""")
    assert got == {"saved": 1, "stopped": True, "rename": None, "moved": []}


def test_the_tree_listens_with_it_and_a_part_row_says_its_keys():
    src = open(JS).read()
    assert "$('tree').addEventListener('keydown', treeKey);" in src
    h = _tree_html("canDrag: true")
    assert h.count('aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft"') == 2


def _tree_html(view):
    src = open(JS).read()
    head = "const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => ''; const pieceId = (p, k) => `${p}/${k}`;\nconst D = " + json.dumps(
        {"parts": [{"id": "a", "version": 1, "pieces": [{"key": "top", "name": "top", "material": "plywood", "color": "#fff"}]},
                   {"id": "b", "version": 1}], "tree": {}}) + ";\n"
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "treeHtml")) + \
        f"\nconsole.log(treeHtml(D, {{ parts: new Set(), pieces: new Set(), open: true, {view} }}));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return got.stdout


def test_on_a_phone_the_drawer_says_how_to_move_a_part():
    h = _tree_html("canDrag: false")
    assert "Hold a part to move it" in h and "needs a wider window" not in h
    assert "Hold a part" not in _tree_html("canDrag: true")


# --- the part menu ---------------------------------------------------------------------------------------------------------
def _menu(body, tree_=None):
    from .test_part_menu import _STUBS

    src = open(JS).read()
    design = json.dumps({"parts": [{"id": i, "name": i, "label": i.upper(), "version": 1, "role": "part", "pieces": [{"key": "top", "name": "top"}]}
                                   for i in "abcde"], "tree": tree_ or {}, "studies": {"menu": {}}})
    names = ("seen", "keepTree", "underPart", "treeRows", "dropped", "nudge", "menuItems", "treeMovesHtml", "menuDo")
    script = (_STUBS.replace("DESIGN", design) + _keys_const(src) + "const moved = []; const moveInTree = async (d, t, z) => moved.push([d, t, z]);\n"
              + "\n".join(_fn(src, n) for n in names) + f"\nconst out = await (async () => {{ {body} }})();\nconsole.log(JSON.stringify(out));")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_menu_offers_moving_a_part_but_not_a_piece():
    got = _menu("return { part: menuItems(S.design, 'c', null).map((i) => i.id), piece: menuItems(S.design, 'c', 'top').map((i) => i.id) };")
    assert "tmove" in got["part"] and got["part"].index("tmove") == got["part"].index("versions") - 1
    assert "tmove" not in got["piece"]


def test_a_design_with_one_part_has_nowhere_to_move_it():
    got = _menu("S.design = { ...S.design, parts: S.design.parts.slice(0, 1) }; return menuItems(S.design, 'a', null).map((i) => i.id);")
    assert "tmove" not in got


def test_move_in_the_tree_lists_only_where_it_can_go_by_name_with_its_keys():
    got = _menu("calls.length = 0; S.menu = { pid: 'c', piece: null }; await menuDo('tmove'); return calls;", NESTED)
    html = got[0][1]
    assert 'data-menu="tmove:out"' in html and "Take it out of B" in html and "Alt+←" in html
    assert not {'data-menu="tmove:up"', 'data-menu="tmove:down"', 'data-menu="tmove:in"'} & {x for x in html.split() if "tmove" in x}  # b's only part
    top = _menu("calls.length = 0; S.menu = { pid: 'd', piece: null }; await menuDo('tmove'); return calls[0][1];", NESTED)
    assert 'data-menu="tmove:up"' in top and "Move up" in top and "Alt+↑" in top and 'data-menu="tmove:down"' in top
    assert 'data-menu="tmove:in"' in top and "Put it under A" in top and "Alt+→" in top                 # a, the part above it
    assert 'data-menu="tmove:out"' not in top


def test_choosing_one_moves_it_as_the_keys_do():
    got = _menu("S.menu = { pid: 'd', piece: null }; await menuDo('tmove:up'); return { moved, calls };", NESTED)
    assert got["moved"] == [["d", "a", "before"]] and "close" in got["calls"]
