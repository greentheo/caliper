"""CALI-102 (#94, slice b) — drag a part in the tree to reorder it, or onto another part to sit under it. Display only: a move changes no
part's id, file, version or check. A piece moving into another part would change two scripts, so it isn't this (#3)."""
import hashlib
import json
import os
import subprocess

import pytest

from caliper import design_api, scorecard, tree
from caliper.design import DesignStore

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
pytest.importorskip("cadquery")

BOX = "import cadquery as cq\n\ndef build(params):\n    return cq.Workplane('XY').box(%d, 20, 10)\n"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("three parts", base=str(tmp_path / "designs"))
    for i, pid in enumerate(("a", "b", "c")):
        s.write_part(pid, BOX % (20 + i), intent=pid)
    return s


def _fingerprint(store):
    out = {}
    for here, _, files in os.walk(store.root):
        for f in files:
            if f == "design.yaml" or f.startswith(".") or "__pycache__" in here or f.endswith("log.jsonl"):
                continue
            with open(os.path.join(here, f), "rb") as fh:
                out[os.path.relpath(os.path.join(here, f), store.root)] = hashlib.sha1(fh.read()).hexdigest()
    return out


def test_with_no_moves_it_is_the_parts_in_their_own_order(store):
    assert tree.layout(store) == {"order": ["a", "b", "c"], "parent": {}}


def test_a_move_is_saved(store):
    tree.set_layout(store, ["c", "a", "b"], {"b": "a"})
    again = DesignStore.load(store.root)
    assert tree.layout(again) == {"order": ["c", "a", "b"], "parent": {"b": "a"}}


def test_a_move_changes_no_id_file_version_or_check(store):
    card = scorecard.compute(store)
    ids = [(p.id, p.version) for p in store.design.parts]
    before = _fingerprint(store)
    state_was = design_api.design_state(store)
    tree.set_layout(store, ["c", "a", "b"], {"b": "a"})
    again = DesignStore.load(store.root)
    assert [(p.id, p.version) for p in again.design.parts] == ids          # the design's own list, order and all
    assert _fingerprint(again) == before
    assert scorecard.list_cards(again, 1)[0]["versions"] == card["versions"] and not scorecard.list_cards(again, 1)[0].get("outdated")
    state = design_api.design_state(again)
    assert [p["id"] for p in state["parts"]] == [p["id"] for p in state_was["parts"]]
    assert state["tree"] == {"order": ["c", "a", "b"], "parent": {"b": "a"}}


@pytest.mark.parametrize("order,parent,word", [(["a", "b"], {}, "every part"), (["a", "b", "b"], {}, "every part"), (["a", "b", "z"], {}, "every part"),
                                               (["a", "b", "c"], {"a": "a"}, "inside itself"), (["a", "b", "c"], {"a": "b", "b": "a"}, "inside itself"),
                                               (["a", "b", "c"], {"a": "b", "b": "c", "c": "a"}, "inside itself"), (["a", "b", "c"], {"z": "a"}, "no part")])
def test_a_bad_move_is_refused(store, order, parent, word):
    with pytest.raises(ValueError, match=word):
        tree.set_layout(store, order, parent)
    assert tree.layout(store) == {"order": ["a", "b", "c"], "parent": {}}


def test_a_part_added_later_comes_last(store):
    tree.set_layout(store, ["c", "b", "a"], {})
    store.write_part("d", BOX % 30, intent="d")
    assert tree.layout(store)["order"] == ["c", "b", "a", "d"]


def test_a_part_removed_takes_its_place_with_it_and_what_sat_under_it_comes_up(store):
    from caliper import trash

    tree.set_layout(store, ["a", "b", "c"], {"b": "a", "c": "b"})
    trash.remove(store, "a")
    got = tree.layout(DesignStore.load(store.root))
    assert got["order"] == ["b", "c"] and got["parent"] == {"c": "b"}


def test_through_the_route(store):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    c = TestClient(create_app())
    slug = store.design.slug
    got = c.post(f"/api/designs/{slug}/tree", json={"order": ["b", "a", "c"], "parent": {"c": "b"}})
    assert got.status_code == 200 and got.json()["tree"] == {"order": ["b", "a", "c"], "parent": {"c": "b"}}
    assert c.post(f"/api/designs/{slug}/tree", json={"order": ["a"], "parent": {}}).status_code == 422


# --- the page ----------------------------------------------------------------------------------------------------------
def _page(body, tree_=None):
    src = open(JS).read()
    head = "const D = " + json.dumps({"parts": [{"id": i} for i in "abcd"], "tree": tree_ or {}}) + ";\n"
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "dropped", "dropZone")) + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _rows(tree_):
    return [[r[0], r[1]] for r in _page("return treeRows(D).map((r) => [r.p.id, r.depth]);", tree_)]


def test_an_old_design_shows_its_parts_in_order():
    assert _rows({}) == [["a", 0], ["b", 0], ["c", 0], ["d", 0]]


def test_what_sits_under_a_part_follows_it():
    assert _rows({"order": ["c", "a", "b", "d"], "parent": {"b": "c", "d": "b"}}) == [["c", 0], ["b", 1], ["d", 2], ["a", 0]]


@pytest.mark.parametrize("drag,target,zone,order,parent", [
    ("d", "a", "before", ["d", "a", "b", "c"], {}), ("a", "c", "after", ["b", "c", "a", "d"], {}),
    ("c", "a", "into", ["a", "c", "b", "d"], {"c": "a"})])
def test_where_a_drop_puts_a_part(drag, target, zone, order, parent):
    assert _page(f"return dropped(D, '{drag}', '{target}', '{zone}');") == {"order": order, "parent": parent}


def test_a_drop_beside_a_nested_part_joins_its_level():
    assert _page("return dropped(D, 'd', 'b', 'after');", {"order": list("abcd"), "parent": {"b": "a"}})["parent"] == {"b": "a", "d": "a"}


def test_a_drop_at_the_top_level_comes_out_of_its_parent():
    assert _page("return dropped(D, 'b', 'c', 'after');", {"order": list("abcd"), "parent": {"b": "a"}})["parent"] == {}


@pytest.mark.parametrize("drag,target", [("a", "a"), ("a", "b"), ("a", "c")])
def test_a_part_can_t_go_on_itself_or_inside_itself(drag, target):
    assert _page(f"return {{ r: dropped(D, '{drag}', '{target}', 'into') }};", {"order": list("abcd"), "parent": {"b": "a", "c": "b"}}) == {"r": None}


@pytest.mark.parametrize("y,zone", [(1, "before"), (10, "into"), (19, "after")])
def test_where_on_the_row_says_what_a_drop_does(y, zone):
    assert _page(f"return {{ z: dropZone({{ clientY: {y} }}, {{ getBoundingClientRect: () => ({{ top: 0, height: 20 }}) }}) }};")["z"] == zone


def test_a_part_s_eye_hides_what_sits_under_it():
    assert _page("return underPart(D, 'a');", {"parent": {"b": "a", "c": "b"}}) == ["b", "c"]
    assert "[id, ...underPart(S.design, d.eye)]" in open(JS).read()


# --- the review of #204 ---------------------------------------------------------------------------------------------------
def test_a_move_doesn_t_jump_the_design_to_the_top_of_the_picker(store):
    was = DesignStore.load(store.root).design.updated
    tree.set_layout(store, ["c", "a", "b"], {})
    assert DesignStore.load(store.root).design.updated == was


def test_a_real_change_still_counts_as_one(store):
    import time

    was = DesignStore.load(store.root).design.updated
    time.sleep(1.1)
    store.save()
    assert DesignStore.load(store.root).design.updated != was


def test_a_bad_move_through_the_route_is_a_422_and_changes_nothing(store):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    c = TestClient(create_app())
    got = c.post(f"/api/designs/{store.design.slug}/tree", json={"order": ["a", "b", "c"], "parent": {"a": "b", "b": "a"}})
    assert got.status_code == 422 and "inside itself" in got.json()["detail"]
    assert tree.layout(DesignStore.load(store.root)) == {"order": ["a", "b", "c"], "parent": {}}


def test_the_route_holds_the_design_s_lock():
    src = _fn_py("set_tree")
    assert "with RUNNER.locked(_lock(slug)):" in src


def _fn_py(name):
    src = open(design_api.__file__).read()
    i = src.index(f"def {name}(")
    return src[i:i + 500]


_HEAD = """
const made = {}; const classes = (el) => { el.classList = { set: new Set(), add(c) { this.set.add(c); }, remove(...c) { c.forEach((x) => this.set.delete(x)); } }; return el; };
const tpart = (id) => (made[id] = made[id] || classes({ id }));
const row = (id) => classes({ dataset: { drag: id }, getBoundingClientRect: () => ({ top: 0, height: 20 }) });
const shown = [];
const document = { querySelector: (q) => tpart(/"([^"]+)"/.exec(q)[1]), querySelectorAll: () => shown };
const CSS = { escape: (s) => s };
const TREE = { drag: null, rename: null, saying: null, parts: new Set(), waiting: new Set(), missed: {} };
let phone = false, posted = [], redraws = 0, trees = 0, errs = [], answer;
const onPhone = () => phone;
const S = { slug: 'x', design: DESIGN }; const WAITING = 'Waiting for the job on this design to finish…';
const seen = () => TREE; const keepTree = () => {}; const render = () => { redraws += 1; }; const renderTree = () => { trees += 1; };
const showErr = (m) => errs.push(m); const plainly = (s) => s;
const api = async (m, u, b) => { posted.push(b); if (answer) return answer(); return { ...S.design, tree: b }; };
const tick = () => new Promise((r) => setImmediate(r));
const ev = (el, y, extra) => ({ target: { closest: () => el }, clientY: y, preventDefault() { this.stopped = true; }, dataTransfer: { setData() {} }, ...extra });
"""
_NAMES = ("treeRows", "underPart", "dropped", "dropZone", "clearDrop", "moveInTree", "showDrop", "treeDragStart", "treeDragOver", "treeDrop",
          "sayMissed")


def _drag(body, tree_=None):
    src = open(JS).read()
    design = json.dumps({"parts": [{"id": i} for i in "abcd"], "tree": tree_ or {}})
    script = _HEAD.replace("DESIGN", design) + "".join(_fn(src, n) for n in _NAMES) + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_drop_posts_the_move_and_redraws():
    got = _drag("""const e = ev(row('a'), 1); TREE.drag = 'd'; treeDrop(e); await tick();
                   return { posted, redraws, stopped: !!e.stopped, drag: TREE.drag, now: S.design.tree };""")
    assert got["posted"] == [{"order": ["d", "a", "b", "c"], "parent": {}}] and got["redraws"] == 1 and got["stopped"] and got["drag"] is None
    assert got["now"] == got["posted"][0]                                 # the design as saved is the one shown


def test_on_a_phone_a_drag_doesn_t_start():
    got = _drag("phone = true; const e = ev(row('a'), 1); treeDragStart(e); return { stopped: !!e.stopped, drag: TREE.drag };")
    assert got == {"stopped": True, "drag": None}


def test_while_renaming_a_drag_doesn_t_start():
    got = _drag("TREE.rename = { part: 'a' }; const e = ev(row('a'), 1); treeDragStart(e); return { stopped: !!e.stopped, drag: TREE.drag };")
    assert got == {"stopped": True, "drag": None}


def test_a_row_can_t_be_dropped_on_itself_or_inside_itself():
    got = _drag("""TREE.drag = 'a'; const e = ev(row('b'), 10), f = ev(row('a'), 10); treeDragOver(e); treeDragOver(f);
                   return { a: !!e.stopped, b: !!f.stopped };""", {"parent": {"b": "a"}})
    assert got == {"a": False, "b": False}


def test_the_after_line_sits_below_everything_under_the_part():
    got = _drag("""const r = row('a'); showDrop(r, 'after');
                   return { row: [...r.classList.set], last: [...tpart('c').classList.set], parent: [...tpart('a').classList.set] };""",
                {"order": list("abcd"), "parent": {"b": "a", "c": "b"}})
    assert got == {"row": [], "last": ["drop-after"], "parent": []}


def test_with_nothing_under_it_the_line_sits_below_the_part():
    got = _drag("showDrop(row('d'), 'after'); return { d: [...tpart('d').classList.set] };")
    assert got == {"d": ["drop-after"]}


def test_before_and_into_mark_the_row():
    got = _drag("const r = row('a'), s = row('b'); showDrop(r, 'before'); showDrop(s, 'into'); return { r: [...r.classList.set], s: [...s.classList.set] };")
    assert got == {"r": ["drop-before"], "s": ["drop-into"]}


def test_dropped_under_a_hidden_part_it_is_hidden_with_what_sits_under_it():
    got = _drag("""TREE.parts.add('a'); answer = () => ({ ...S.design, tree: { order: ['a', 'c', 'b', 'd'], parent: { c: 'a', d: 'c' } } });
                   S.design = { ...S.design, tree: { parent: { d: 'c' } } };
                   await moveInTree('c', 'a', 'into'); return { hidden: [...TREE.parts].sort() };""")
    assert got == {"hidden": ["a", "c", "d"]}


def test_dropped_under_a_visible_part_it_keeps_its_own_state():
    got = _drag("await moveInTree('c', 'a', 'into'); return { hidden: [...TREE.parts] };")
    assert got == {"hidden": []}


def test_a_drop_that_has_to_wait_says_so_and_stops_saying_it():
    got = _drag("""globalThis.setTimeout = ((real) => (f, ms) => (ms === 600 ? (f(), 1) : real(f, ms)))(globalThis.setTimeout); globalThis.clearTimeout = () => {};
                   const during = []; answer = () => { during.push(TREE.saying); return S.design; };
                   await moveInTree('c', 'a', 'into'); return { during, after: TREE.saying, trees };""")
    assert got["during"] == ["Waiting for the job on this design to finish…"] and got["after"] is None and got["trees"] == 1


def test_a_refused_move_is_said():
    got = _drag("answer = () => { throw new Error('no'); }; await moveInTree('c', 'a', 'into'); return { errs, redraws };")
    assert got == {"errs": ["no"], "redraws": 1}


def _html(view):
    src = open(JS).read()
    head = "const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => '';\nconst D = " + json.dumps(
        {"parts": [{"id": "a", "version": 1}, {"id": "b", "version": 1}], "tree": {"parent": {"b": "a"}}}) + ";\n"
    view_ = "{ parts: new Set(), pieces: new Set(), open: true, " + view + " }"
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "treeHtml")) + f"\nconsole.log(treeHtml(D, {view_}));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return got.stdout


def test_on_a_desktop_rows_can_be_dragged_and_are_indented():
    h = _html("canDrag: true")
    assert h.count('draggable="true"') == 2 and "margin-left:18px" in h and "needs a wider window" not in h


def test_on_a_phone_rows_can_t_and_the_drawer_says_so():
    h = _html("canDrag: false")
    assert "draggable" not in h and "Moving parts needs a wider window" in h


def test_the_tree_says_what_it_s_waiting_for():
    assert "Waiting for the job" in _html("canDrag: true, saying: 'Waiting for the job on this design to finish…'")


def test_the_handlers_are_wired():
    src = open(JS).read()
    for name in ("dragstart', treeDragStart", "dragover', treeDragOver", "drop', treeDrop"):
        assert name in src



# --- CALI-150 (#206): the waiting line, the last row, and the wiring -----------------------------------------------------
def test_a_reply_that_comes_after_a_switch_doesn_t_land_on_the_other_design():
    """reviewer-2 on #204: the waiting line followed to another design for about 32 s, saying "this design"."""
    got = _drag("""const before = S.design; answer = () => { S.slug = 'y'; return { parts: [], tree: { order: ['z'] } }; };
                   await moveInTree('c', 'a', 'into'); return { same: S.design === before, saying: TREE.saying, redraws, errs };""")
    assert got == {"same": True, "saying": None, "redraws": 0, "errs": []}


def test_the_waiting_line_never_comes_up_on_another_design():
    got = _drag("""let late; globalThis.setTimeout = (f, ms) => { if (ms === 600) late = f; return 1; }; globalThis.clearTimeout = () => {};
                   let release; answer = () => new Promise((r) => { release = () => r(S.design); });
                   const going = moveInTree('c', 'a', 'into'); await tick();
                   S.slug = 'y'; late(); const shown = TREE.saying; release(); await going;
                   return { shown, trees };""")
    assert got == {"shown": None, "trees": 0}


def test_on_its_own_design_the_waiting_line_still_shows_and_goes():
    got = _drag("""let late; globalThis.setTimeout = (f, ms) => { if (ms === 600) late = f; return 1; }; globalThis.clearTimeout = () => {};
                   let release; answer = () => new Promise((r) => { release = () => r(S.design); });
                   const going = moveInTree('c', 'a', 'into'); await tick(); late(); const shown = TREE.saying; release(); await going;
                   return { shown, after: TREE.saying, redraws };""")
    assert got == {"shown": "Waiting for the job on this design to finish…", "after": None, "redraws": 1}


def test_a_switch_clears_the_waiting_line():
    src = open(JS).read()
    script = ("const S = { slug: 'x' }; const localStorage = { getItem: () => null }; const WAITING = 'Waiting for the job on this design to finish…';\n"
              "const TREE = { slug: 'x', saying: WAITING, drag: 'a', parts: new Set(), waiting: new Set(), missed: {} };\n"
              + _fn(src, "seen") + "\nS.slug = 'y'; seen(); console.log(JSON.stringify({ saying: TREE.saying, drag: TREE.drag }));")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"saying": None, "drag": None}


def _render(phone, saying="null"):
    src = open(JS).read()
    head = ("const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => '';\n"
            "const box = { hidden: false, innerHTML: '' }; const $ = (id) => (id === 'tree' ? box : null);\n"
            "const document = { activeElement: { id: 'body' } }; const noPieces = new Map();\n"
            "const S = { slug: 'x', scope: null, piece: null, pick: false, design: " + json.dumps(
                {"parts": [{"id": "a", "version": 1}, {"id": "b", "version": 1}], "tree": {}}) + " };\n"
            f"const TREE = {{ parts: new Set(), pieces: new Set(), open: true, oneBody: false, rename: null, saying: {saying} }};\n"
            f"const seen = () => TREE; const onPhone = () => {phone};\n")
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "treeHtml", "renderTree")) + "\nrenderTree(); console.log(box.innerHTML);"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return got.stdout


def test_the_real_tree_drags_on_a_desktop_and_not_on_a_phone():
    """reviewer-2 on #204: eight mutants on renderTree's wiring survived; it's run here, not its parts."""
    assert _render("false").count('draggable="true"') == 2 and "needs a wider window" not in _render("false")
    assert "draggable" not in _render("true") and "Moving parts needs a wider window" in _render("true")
    assert "Waiting for the job on this design" in _render("false", "'Waiting for the job on this design to finish…'")


def test_the_phone_is_the_css_phone_and_turning_it_redraws_the_tree():
    src, css = open(JS).read(), open(JS.replace("design.js", "design.css")).read()
    assert "const PHONE = window.matchMedia('(max-width: 700px)');" in src and "@media (max-width: 700px) {" in css
    assert "PHONE.addEventListener('change', () => renderTree());" in src


def test_the_waiting_line_stays_in_view_and_the_after_line_shows_over_a_chosen_last_row():
    """The header scrolled away with the tree; a chosen last row's background covered the part's inset line."""
    css = open(JS.replace("design.js", "design.css")).read()
    head = css[css.index(".tree-head {"):]
    assert "position: sticky" in head[:head.index("}")]
    after = css[css.index(".tpart.drop-after::after {"):]
    after = after[:after.index("}")]
    assert "position: absolute" in after and "bottom: 0" in after and "background: var(--accent)" in after
    assert ".tpart.drop-after {" not in css.replace(".tpart.drop-after::after", "")       # not an inset shadow under its rows


# --- #251 review: a switch empties the tree at once; a lost move is said; a wait comes back -----------------------------
def test_while_a_design_loads_nothing_in_the_tree_can_be_dragged_or_moved():
    """reviewer-2 on #251: dragging the old design's rows during the next one's load threw "Cannot read properties of null
    (reading 'tree')". With no design on screen, a drag doesn't start, a dragover isn't taken, and a drop or a move posts nothing."""
    got = _drag("""S.design = null; const r = row('a');
                   const s = ev(r, 1); treeDragStart(s);
                   TREE.drag = 'b'; const o = ev(r, 10); treeDragOver(o);
                   const d = ev(r, 10); treeDrop(d); await tick();
                   await moveInTree('b', 'a', 'into');
                   return { started: !s.stopped, taken: !!o.stopped, dropped: !!d.stopped, posted, errs, drag: TREE.drag };""")
    assert got == {"started": False, "taken": False, "dropped": False, "posted": [], "errs": [], "drag": None}


def test_while_a_design_loads_the_tree_says_so_with_no_rows():
    src = open(JS).read()
    head = ("const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => '';\n"
            "const box = { hidden: true, innerHTML: '<div data-drag=\"a\">a</div>' }; const $ = (id) => (id === 'tree' ? box : null);\n"
            "const document = { activeElement: { id: 'body' } }; const noPieces = new Map(); const pickedName = (s) => 'Stool B';\n"
            "const S = { slug: 'b', opening: 'b', design: null };\n"
            "const TREE = { parts: new Set(), pieces: new Set(), open: true, saying: 'Waiting for the job on this design to finish…' };\n"
            "const seen = () => TREE; const onPhone = () => false;\n")
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "treeHtml", "renderTree")) + \
        "\nrenderTree(); console.log(JSON.stringify({ hidden: box.hidden, html: box.innerHTML }));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    got = json.loads(got.stdout)
    assert got["hidden"] is False and "Loading Stool B…" in got["html"], got
    assert "data-drag" not in got["html"] and "Waiting" not in got["html"], got


def test_a_switch_draws_the_tree_at_once():
    src = open(JS).read()
    body = src[src.index("function showLoading("):]
    body = body[:body.index("\n}\n")]
    assert "TREE.saying = null;" in body and "renderTree();" in body and "$('tree').hidden = true;" not in body


def test_a_move_that_fails_on_another_design_is_said_back_on_it():
    got = _drag("""answer = () => { S.slug = 'y'; throw new Error('the design is locked'); };
                   await moveInTree('c', 'a', 'into'); const away = errs.slice();
                   S.slug = 'x'; sayMissed(); const back = errs.slice(); sayMissed();
                   return { away, back, again: errs.length, left: TREE.missed };""")
    assert got["away"] == [] and got["back"] == ["Your move of c in x didn't save: the design is locked"], got
    assert got["again"] == 1 and got["left"] == {}


def test_back_on_a_design_mid_wait_the_waiting_line_comes_back():
    src = open(JS).read()
    script = ("const S = { slug: 'x' }; const localStorage = { getItem: () => null }; const WAITING = 'Waiting for the job on this design to finish…';\n"
              "const TREE = { slug: 'x', saying: WAITING, drag: null, parts: new Set(), waiting: new Set(['x']), missed: {} };\n"
              + _fn(src, "seen") + "\nS.slug = 'y'; seen(); const away = TREE.saying; S.slug = 'x'; seen();"
              "\nconsole.log(JSON.stringify({ away, back: TREE.saying }));")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"away": None, "back": "Waiting for the job on this design to finish…"}


def test_a_move_is_waiting_from_its_slow_start_to_its_reply_on_whatever_design_is_open():
    got = _drag("""let late; globalThis.setTimeout = (f, ms) => { if (ms === 600) late = f; return 1; }; globalThis.clearTimeout = () => {};
                   let release; answer = () => new Promise((r) => { release = () => r(S.design); });
                   const going = moveInTree('c', 'a', 'into'); await tick();
                   S.slug = 'y'; late(); const during = [...TREE.waiting]; release(); await going;
                   return { during, after: [...TREE.waiting] };""")
    assert got == {"during": ["x"], "after": []}


def test_a_design_that_opens_says_a_move_it_lost():
    src = open(JS).read()
    body = src[src.index("async function openDesign("):]
    body = body[:body.index("\n}\n")]
    assert "  S.design = got;\n  doneLoading();\n  render();\n  sayMissed();" in body
