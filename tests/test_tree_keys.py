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
const S = { slug: 'x', design: D }; const TREE = { rename: null }; const moved = [], said = [], focused = [];
let settle = null, saves = true;                 // a save that lands when the test says so, or at once; and whether it saved
const moveInTree = (drag, target, zone) => { moved.push([drag, target, zone]);
  return settle ? new Promise((r) => { settle = () => { drawn = 'new'; r(saves); }; }) : Promise.resolve(saves); };
let drawn = 'old';                               // the redraw replaces the rows: a row looked up after it is a new one
const say = (t) => said.push(t);
const btn = (sel, key) => ({ dataset: { sel, ...(key != null ? { key } : {}) } });
const row = (sel, key, on) => { const b = btn(sel, key); const r = { querySelector: (q) => (q === 'button.tname[data-sel]' ? b : null) };
  const target = on === 'eye' ? { dataset: { eye: sel }, closest: (q) => (q === '.trow' ? r : null) } : { ...b, closest: (q) => (q === '.trow' ? r : null) };
  return target; };
const body = { id: 'body' }, chat = { id: 'msg' };
const document = { body, activeElement: body, querySelector: (q) => ({ focus() { focused.push([q, drawn]); } }) };
const CSS = { escape: (s) => s };
const key = (target, k, mods = {}) => ({ target, key: k, altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, ...mods,
  preventDefault() { this.stopped = true; } });
"""


def _keys(body, tree_=None):
    src = open(JS).read()
    return _run("".join(_fn(src, n) for n in ("treeSaid", "treeKey")) + body, tree_, extra=_KEYS)


@pytest.mark.parametrize("k,expect,words", [("ArrowUp", ["c", "b", "before"], "Moved C up, above B"),
                                            ("ArrowDown", ["c", "d", "after"], "Moved C down, below D"),
                                            ("ArrowRight", ["c", "b", "into"], "Moved C under B")])
def test_alt_arrows_on_a_part_row_move_it_say_so_and_keep_focus_on_it(k, expect, words):
    got = _keys(f"const e = key(row('c'), '{k}'); await treeKey(e); return {{ moved, said, stopped: !!e.stopped, focused }};")
    assert got["moved"] == [expect] and got["stopped"] and got["said"] == [words]
    assert 'data-sel="c"' in got["focused"][0][0] and ":not([data-key])" in got["focused"][0][0]


def test_in_says_the_part_it_went_under_not_the_row_it_went_after():
    """Into a part that already has some under it, the drop is after its last one: the words name the part, not that row."""
    got = _keys("await treeKey(key(row('d'), 'ArrowRight')); return { moved, said };", NESTED)
    assert got == {"moved": [["d", "b", "after"]], "said": ["Moved D under A"]}


def test_alt_left_takes_it_out_and_says_out_of_what():
    got = _keys("await treeKey(key(row('c'), 'ArrowLeft')); return { moved, said };", NESTED)
    assert got == {"moved": [["c", "b", "after"]], "said": ["Moved C out of B"]}


@pytest.mark.parametrize("pid,k,words", [("a", "ArrowUp", "A is already at the top"), ("e", "ArrowDown", "E is already at the bottom"),
                                         ("a", "ArrowRight", "A has no part above it to go under"), ("a", "ArrowLeft", "A isn't under another part")])
def test_where_it_can_t_go_it_says_so_and_still_takes_the_key(pid, k, words):
    got = _keys(f"const e = key(row('{pid}'), '{k}'); await treeKey(e); return {{ moved, said, stopped: !!e.stopped }};")
    assert got == {"moved": [], "said": [words], "stopped": True}


def test_the_part_s_eye_moves_it_too():
    got = _keys("const e = key(row('c', null, 'eye'), 'ArrowUp'); await treeKey(e); return { moved, stopped: !!e.stopped };")
    assert got == {"moved": [["c", "b", "before"]], "stopped": True}


@pytest.mark.parametrize("why,stopped", [("plain", False), ("piece", True), ("ctrl", False), ("meta", False), ("renaming", True),
                                         ("loading", True), ("off a row", False)])
def test_nothing_moves_without_alt_on_a_piece_or_off_a_row(why, stopped):
    body = {"plain": "const e = key(row('c'), 'ArrowUp', { altKey: false });",
            "piece": "const e = key(row('c', 'top'), 'ArrowLeft');",           # its row's Alt+← is the tree's: never Back
            "ctrl": "const e = key(row('c'), 'ArrowUp', { ctrlKey: true });",
            "meta": "const e = key(row('c'), 'ArrowUp', { metaKey: true });",
            "renaming": "TREE.rename = { part: 'c' }; const e = key(row('c'), 'ArrowUp');",
            "loading": "S.design = null; const e = key(row('c'), 'ArrowUp');",
            "off a row": "const e = key({ dataset: {}, closest: () => null }, 'ArrowLeft');"}[why]
    got = _keys(body + " await treeKey(e); return { moved, said, stopped: !!e.stopped };")
    assert got == {"moved": [], "said": [], "stopped": stopped}


def test_a_save_that_lands_after_the_person_moved_on_leaves_their_focus_be():
    """#360 review: the save took 28 s, and the row took the focus back out of a draft in the chat box."""
    got = _keys("""settle = true; const going = treeKey(key(row('c'), 'ArrowUp'));
                   document.activeElement = chat; settle(); await going; return { focused, said };""")
    assert got == {"focused": [], "said": ["Moved C up, above B"]}


def test_a_save_that_lands_with_the_focus_lost_puts_it_on_the_redrawn_row():
    """With the focus on <body> it goes to the row as drawn after the save, never the one the redraw removed (the await)."""
    got = _keys("""settle = true; const going = treeKey(key(row('c'), 'ArrowUp')); settle(); await going; return focused;""")
    assert len(got) == 1 and got[0][1] == "new"


def test_a_save_that_failed_says_nothing_and_moves_no_focus():
    got = _keys("saves = false; await treeKey(key(row('c'), 'ArrowUp')); return { said, focused };")
    assert got == {"said": [], "focused": []}


def test_the_rename_box_still_takes_enter_and_escape():
    got = _keys("""let saved = 0; const input = { dataset: { renameInput: '1' }, blur() {}, closest: () => null,
                      parentElement: { querySelector: () => ({ click() { saved += 1; } }) } };
                   const renderTree = () => {};
                   const e = key(input, 'Enter', { altKey: false }); await treeKey(e);
                   TREE.rename = { part: 'c' }; await treeKey(key(input, 'Escape', { altKey: false }));
                   return { saved, stopped: !!e.stopped, rename: TREE.rename, moved };""")
    assert got == {"saved": 1, "stopped": True, "rename": None, "moved": []}


def test_the_tree_listens_with_it_and_a_part_row_says_its_keys():
    src = open(JS).read()
    assert "$('tree').addEventListener('keydown', treeKey);" in src
    h = _tree_html("canDrag: true")
    assert h.count('aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft"') == 2


def test_the_tree_says_its_depth_not_only_draws_it():
    h = _tree_html("canDrag: true", {"parent": {"b": "a"}})
    assert '<div role="tree" aria-label="Parts">' in h
    assert re.search(r'role="treeitem" aria-level="1" aria-selected="false" data-sel="a"(?! data-key)', h)
    assert re.search(r'role="treeitem" aria-level="2" aria-selected="false" data-sel="a" data-key="top"', h)   # a's piece
    assert re.search(r'role="treeitem" aria-level="2" aria-selected="false" data-sel="b"(?! data-key)', h)     # b, under a
    assert 'aria-selected="true" data-sel="b"' in _tree_html("canDrag: true, scope: 'b'")


# --- the redraw keeps the focus --------------------------------------------------------------------------------------------
_REDRAW = """
const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => ''; const pieceId = (p, k) => `${p}/${k}`;
const CSS = { escape: (s) => s }; const noPieces = new Map(); let focused = null, drawn = 0;
const mk = (sel) => ({ dataset: { sel }, matches: (q) => q === 'button.tname[data-sel]', focus() { focused = [sel, this.n]; } });
let rows = { a: mk('a'), b: mk('b') };
const box = { hidden: false, set innerHTML(v) { drawn += 1; rows = { a: { ...mk('a'), n: drawn }, b: { ...mk('b'), n: drawn } }; },
  contains: (el) => Object.values(rows).includes(el) || el === OLD,
  querySelector: (q) => rows[/data-sel="([^"]+)"/.exec(q)[1]] };
const OLD = rows.b;
const $ = (id) => (id === 'tree' ? box : null);
const document = { activeElement: null };
const S = { slug: 'x', scope: null, piece: null, pick: false, design: D };
const TREE = { parts: new Set(), pieces: new Set(), open: true, oneBody: false, rename: null, saying: null };
const seen = () => TREE; const onPhone = () => false;
"""


def _redraw(body):
    src = open(JS).read()
    design = json.dumps({"parts": [{"id": "a", "version": 1}, {"id": "b", "version": 1}], "tree": {}})
    script = (f"const D = {design};\n" + _REDRAW + "".join(_fn(src, n) for n in ("treeRows", "underPart", "treeHtml", "renderTree"))
              + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_waiting_redraw_keeps_the_focus_on_the_row():
    """#360 review: the 600 ms "Waiting…" redraw replaced the rows and the focus fell to <body>."""
    assert _redraw("document.activeElement = OLD; renderTree(); return focused;") == ["b", 1]


def test_the_redraw_keeps_the_focus_on_the_same_row_not_another():
    assert _redraw("const was = rows.a; document.activeElement = was; renderTree(); return focused;") == ["a", 1]


def test_a_redraw_with_the_focus_elsewhere_takes_none():
    assert _redraw("document.activeElement = { matches: () => true, dataset: { sel: 'b' } }; renderTree(); return focused;") is None


def _tree_html(view, tree_=None):
    src = open(JS).read()
    head = "const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => ''; const pieceId = (p, k) => `${p}/${k}`;\nconst D = " + json.dumps(
        {"parts": [{"id": "a", "version": 1, "pieces": [{"key": "top", "name": "top", "material": "plywood", "color": "#fff"}]},
                   {"id": "b", "version": 1}], "tree": tree_ or {}}) + ";\n"
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
    names = ("seen", "keepTree", "underPart", "treeRows", "dropped", "nudge", "treeSaid", "menuItems", "treeMovesHtml", "menuDo")
    script = (_STUBS.replace("DESIGN", design) + _keys_const(src)
              + "const moved = []; const moveInTree = async (d, t, z) => { moved.push([d, t, z]); return true; }; let phone = false; const onPhone = () => phone;\n"
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


def test_choosing_one_moves_it_as_the_keys_do_and_says_so():
    got = _menu("S.menu = { pid: 'd', piece: null }; await menuDo('tmove:up'); return { moved, calls };", NESTED)
    assert got["moved"] == [["d", "a", "before"]] and "close" in got["calls"] and ["say", "Moved D up, above A"] in got["calls"]


def test_on_a_phone_the_submenu_has_no_keys():
    got = _menu("phone = true; calls.length = 0; S.menu = { pid: 'd', piece: null }; await menuDo('tmove'); return calls[0][1];", NESTED)
    assert "Move up" in got and "Alt+" not in got
