"""CALI-102 (#94, slice a) — the part tree: every part and its pieces, named, coloured, shown or hidden. Names are labels:
the id that scripts, history, runs and files key on never changes. Stubbed: no FEA, no Claude."""

import json
import os
import subprocess

import pytest
import trimesh

from caliper import answers, design_api, firstrun, release, tree
from caliper.design import DesignStore

from .test_beam_width import TOP
from .test_mixed import MIXED
from .test_resolved import TUBE

pytest.importorskip("cadquery")


def _store(tmp_path, src=TOP, pid="bench"):
    s = DesignStore.create(f"a {pid}", base=str(tmp_path / "designs"))
    s.write_part(pid, src, intent=f"a {pid}")
    return s


def _load(data):
    import io

    return trimesh.load(io.BytesIO(data), file_type="stl")


# --- the pieces, their colours and the legend --------------------------------------------------------------------------

def test_a_part_s_pieces_come_with_their_material_and_colour(tmp_path):
    store = _store(tmp_path)
    got = tree.pieces(store, "bench")
    assert [p["key"] for p in got] == ["top", "front", "back"] and all(p["kind"] == "sheet" for p in got)
    assert got[0] == {"key": "top", "name": "top", "labelled": False, "kind": "sheet", "material": "softwood plywood",
                      "legend": "1/2 in softwood plywood", "color": tree.COLOURS["plywood"]}
    state = design_api.design_state(store)
    assert state["parts"][0]["pieces"] == got
    assert state["legend"] == [{"label": "1/2 in softwood plywood", "color": tree.COLOURS["plywood"], "count": 1},
                               {"label": "3/4 in softwood plywood", "color": tree.COLOURS["plywood"], "count": 2}]


def test_a_printed_part_is_one_piece_in_its_own_colour(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    (pc,) = tree.pieces(store, "tube")
    assert (pc["key"], pc["kind"], pc["material"], pc["color"]) == ("tube", "printed", "PETG", tree.COLOURS["petg"])


def test_two_pieces_with_one_name_keep_apart(tmp_path):
    src = TOP.replace('{"name": "back", "kind": "sheet"', '{"name": "front", "kind": "sheet"')
    store = _store(tmp_path, src)
    assert [p["key"] for p in tree.pieces(store, "bench")] == ["top", "front", "front 2"]


# --- each piece's solid, for the viewport ------------------------------------------------------------------------------

def test_each_piece_has_a_solid_where_it_sits(tmp_path):
    store = _store(tmp_path)
    top = tree.mesh(store, "bench", "top")
    (x0, y0, z0), (x1, y1, z1) = top.bounds
    assert (x1 - x0, y1 - y0) == pytest.approx((900, 300), abs=0.5) and z1 - z0 == pytest.approx(12.7, abs=0.01)
    assert z0 == pytest.approx(200 - 12.7, abs=0.5)                                   # the top's under its outside face


def test_the_printed_rest_is_the_part_less_its_sheets(tmp_path):
    store = _store(tmp_path, MIXED, "stool")
    keys = {p["kind"]: p["key"] for p in tree.pieces(store, "stool")}
    whole = store.part_geometry("stool").require_mesh()
    rest, sheet = tree.mesh(store, "stool", keys["printed"]), tree.mesh(store, "stool", keys["sheet"])
    assert rest.volume < whole.volume and rest.volume + sheet.volume == pytest.approx(whole.volume, rel=0.05)


def test_a_piece_goes_with_the_part_s_pose(tmp_path):
    store = _store(tmp_path)
    next(p for p in store.assembly.parts if p.id == "bench").position = (0.0, 0.0, 500.0)
    store.save()
    assert tree.mesh(store, "bench", "top").bounds[1][2] == pytest.approx(700, abs=0.5)


def test_the_route_serves_a_piece_or_says_it_has_none(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/bench/piece.stl", params={"key": "top"})
    assert got.status_code == 200 and _load(got.content).is_watertight
    assert c.get(f"/api/designs/{slug}/parts/bench/piece.stl", params={"key": "lid"}).status_code == 404


# --- names are labels, not ids -----------------------------------------------------------------------------------------

def test_a_rename_round_trips_and_the_id_stays(tmp_path):
    store = _store(tmp_path)
    script, folder = store.read_script("bench"), store.part_dir("bench")
    tree.set_label(store, "bench", "  Garden   bench ")
    tree.set_label(store, "bench", "seat", piece="top")
    store = DesignStore.load(store.root)
    assert store.design.part("bench").label == "Garden bench" and store.part_dir("bench") == folder
    assert store.read_script("bench") == script and store.design.part("bench").version == 1
    (p,) = design_api.design_state(store)["parts"]
    assert (p["id"], p["label"], p["name"]) == ("bench", "Garden bench", "Garden bench")
    assert [x["name"] for x in p["pieces"]] == ["seat", "front", "back"] and p["pieces"][0]["key"] == "top"
    tree.set_label(store, "bench", "")                                                # back to its id
    tree.set_label(store, "bench", "top", piece="top")
    (p,) = design_api.design_state(DesignStore.load(store.root))["parts"]
    assert (p["label"], p["name"]) == (None, "bench") and not p["pieces"][0]["labelled"]


def test_a_design_from_before_labels_reads_as_it_did(tmp_path):
    import yaml

    store = _store(tmp_path)
    path = os.path.join(store.root, "design.yaml")
    data = yaml.safe_load(open(path))
    data.pop("piece_labels", None)
    for p in data["parts"]:
        p.pop("label", None)
    yaml.safe_dump(data, open(path, "w"))
    store = DesignStore.load(store.root)
    (p,) = design_api.design_state(store)["parts"]
    assert p["name"] == "bench" and p["label"] is None and store.design.piece_labels == {}


@pytest.mark.parametrize("pid,label,piece,why", [
    ("nope", "x", None, "there's no part 'nope'"), ("bench", "x", "lid", "bench has no piece 'lid'"),
    ("bench", "y" * 61, None, "a name is at most 60 characters"),
])
def test_a_rename_that_can_t_be_is_refused(tmp_path, pid, label, piece, why):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match=f"^{why}$"):
        tree.set_label(store, pid, label, piece)


def test_a_reference_can_t_be_renamed(tmp_path):
    store = _store(tmp_path)
    next(p for p in store.assembly.parts if p.id == "bench").role = "fixed"
    store.save()
    with pytest.raises(ValueError, match="is a reference"):
        tree.set_label(store, "bench", "my car")


def test_the_route_renames(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.post(f"/api/designs/{slug}/parts/bench/label", json={"label": "Garden bench"})
    assert got.status_code == 200 and got.json()["parts"][0]["name"] == "Garden bench"
    assert c.post(f"/api/designs/{slug}/parts/bench/label", json={"label": "x", "piece": "lid"}).status_code == 422


def test_the_cards_and_the_build_book_read_the_label(tmp_path):
    store = _store(tmp_path, TUBE, "i_want")
    tree.set_label(store, "i_want", "Bar stool")
    state = design_api.design_state(store)
    assert answers.part_name(state["parts"][0]) == "Bar stool"
    store.write_part("other", TUBE, intent="other")
    state = design_api.design_state(store)
    design = next(c for c in answers.design(store, state) if c["key"] == "what")
    assert any(ln["text"] == "2 parts: Bar stool, other" for ln in design["lines"]), design["lines"]
    book = release.book({"id": "r1", "created": 0, "design": "a stool", "versions": {"i_want": 1},
                         "names": {"i_want": "Bar stool"}},
                        {"summary": {"pass": 0, "fail": 0, "unknown": 1}, "checks": [], "metrics": {}},
                        {"usd": 0, "groups": [], "basis": ""}, {}, [], [])
    assert "Bar stool v1" in book and "i_want v1" not in book


def test_a_one_part_design_s_part_is_called_what_the_design_is(tmp_path):
    from .test_chat import _author, _box

    store = DesignStore.create("I want to make a bar stool to hold 250 lb.", base=str(tmp_path / "designs"))
    assert store.design.name == "Bar stool"
    got = firstrun.build(store, use_llm=False, author=_author(_box()))
    assert got["ok"] and store.design.part(got["part"]).label == "Bar stool"


# --- the page --------------------------------------------------------------------------------------------------
JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
_PAGE = """
const S = { slug: 'x', scope: null, piece: null, design: DESIGN };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const calls = [];
const paint = () => calls.push('paint');
const setScope = (p, k) => { calls.push(['scope', p, k]); S.scope = p; S.piece = k; };
const store = {};
globalThis.localStorage = { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = v; } };
function renderTree() { calls.push('tree'); }
function saveTreeName(p, k) { calls.push(['save', p, k]); }
const TREE = { slug: undefined, parts: new Set(), pieces: new Set(), open: true, oneBody: false, rename: null, last: null,
  waiting: new Set(), missed: {} };
const WAITING = 'Waiting for the job on this design to finish…';
const pieceId = (pid, key) => `${pid}/${key}`;
const EYE_ON = 'EYE-ON', EYE_OFF = 'EYE-OFF';
const view = (over) => ({ parts: new Set(), pieces: new Set(), open: true, rename: null, scope: null, piece: null, oneBody: false, cant: null, ...over });
const btn = (dataset) => ({ dataset });
"""
_DESIGN = """{ parts: [
  { id: 'i_want', name: 'Bar stool', label: 'Bar stool', role: 'part', version: 7, pieces: [
    { key: 'seat top', name: 'seat top', material: 'softwood plywood', color: '#C98A4B' },
    { key: 'cone skirt', name: 'the <cone>', material: 'PETG', color: '#4F8FE8' } ] },
  { id: 'floor', name: 'floor', role: 'fixed', version: 1, pieces: [
    { key: 'slab', name: 'slab', material: 'steel tube', color: '#AAB6C3' } ] } ],
  legend: [{ label: 'PETG, printed', color: '#4F8FE8', count: 1 }, { label: 'plate', color: '#AAB6C3', count: 2 }] }"""


def _page(body: str) -> dict:
    from .test_carve_click import _fn, _node

    src = open(JS).read()
    names = ("seen", "keepTree", "isHidden", "renameRow", "treeRows", "underPart", "treeHtml", "treeClick")
    script = _PAGE.replace("DESIGN", _DESIGN) + "\n".join(_fn(src, n) for n in names) + f"\nconst out = (() => {{ {body} }})();\n" \
        "console.log(JSON.stringify(out));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_tree_shows_parts_their_pieces_and_the_legend():
    got = _page("const h = treeHtml(S.design, view()); return { h };")["h"]
    assert "Bar stool" in got and "seat top" in got and "softwood plywood" in got and "v7" in got
    assert "background:#4F8FE8" in got                       # the swatch is the legend's colour
    assert "PETG, printed · 1 piece" in got and "plate · 2 pieces" in got
    assert "the &lt;cone&gt;" in got and "the <cone>" not in got     # a name is the person's text


def test_the_tree_says_a_hidden_piece_is_still_checked():
    assert "hidden pieces are still checked" in _page("return { h: treeHtml(S.design, view()) };")["h"]


def test_a_reference_is_grey_and_says_so_with_no_version():
    got = _page("return { h: treeHtml(S.design, view()) };")["h"]
    row = got[got.index('data-sel="floor"') - 400:got.index('data-sel="floor"') + 80]
    assert " ref" in row and 'data-fixed="1"' in row and "reference" in got
    assert "background:#AAB6C3\"></span>\n        <button class=\"tname\" data-sel=\"floor\"" not in got
    assert "v1" not in got


def test_hiding_a_part_shows_its_pieces_hidden_too():
    got = _page("""const h = treeHtml(S.design, view({ parts: new Set(['i_want']) }));
                   return { n: (h.match(/EYE-OFF/g) || []).length };""")
    assert got["n"] == 3                                     # the part and both its pieces; the reference is still on


def test_folding_keeps_the_head_and_drops_the_rows():
    got = _page("return { h: treeHtml(S.design, view({ open: false })) };")["h"]
    assert "hidden pieces are still checked" in got and "seat top" not in got and 'aria-expanded="false"' in got


def test_the_selected_row_is_marked():
    got = _page("""const part = treeHtml(S.design, view({ scope: 'i_want' }));
                   const piece = treeHtml(S.design, view({ scope: 'i_want', piece: 'seat top' }));
                   const on = (h) => h.split('class="trow').filter((r) => r.startsWith(' part on') || r.includes(' on"') )
                     .map((r) => (r.match(/data-sel="[^"]+"( data-key="[^"]+")?/) || [''])[0]);
                   return { part: on(part), piece: on(piece) };""")
    assert got["part"] == ['data-sel="i_want"']
    assert got["piece"] == ['data-sel="i_want" data-key="seat top"']


def test_the_eye_is_kept_for_this_design_and_only_touches_the_viewer():
    got = _page("""const r = treeClick(btn({ eye: 'i_want', key: 'cone skirt' }), 0);
                   const was = isHidden('i_want', 'cone skirt'), seat = isHidden('i_want', 'seat top');
                   const kept = JSON.parse(store['caliper-tree:x']);
                   treeClick(btn({ eye: 'i_want', key: 'cone skirt' }), 10);
                   return { r, was, seat, kept, back: isHidden('i_want', 'cone skirt'), calls };""")
    assert got["r"] == "eye" and got["was"] and not got["seat"] and not got["back"]
    assert got["kept"]["pieces"] == ["i_want/cone skirt"]
    assert "paint" in got["calls"] and not [c for c in got["calls"] if isinstance(c, list)]    # no save, no scope


def test_a_hidden_whole_part_hides_every_piece():
    got = _page("""treeClick(btn({ eye: 'i_want' }), 0);
                   return { a: isHidden('i_want'), b: isHidden('i_want', 'seat top') };""")
    assert got == {"a": True, "b": True}


def test_what_is_hidden_comes_back_for_that_design_only():
    got = _page("""store['caliper-tree:x'] = JSON.stringify({ parts: [], pieces: ['i_want/seat top'], open: false });
                   const here = isHidden('i_want', 'seat top'), open = TREE.open;
                   S.slug = 'y';
                   return { here, open, there: isHidden('i_want', 'seat top') };""")
    assert got == {"here": True, "open": False, "there": False}


def test_one_click_selects_and_a_slow_second_click_selects_again():
    got = _page("""const a = treeClick(btn({ sel: 'i_want', key: 'seat top' }), 0);
                   const b = treeClick(btn({ sel: 'i_want', key: 'seat top' }), 900);
                   return { a, b, calls, rename: TREE.rename };""")
    assert got["a"] == got["b"] == "select" and got["rename"] is None
    assert got["calls"] == [["scope", "i_want", "seat top"]] * 2


def test_a_double_click_renames_starting_from_the_name_shown():
    got = _page("""treeClick(btn({ sel: 'i_want', key: 'cone skirt' }), 0);
                   const r = treeClick(btn({ sel: 'i_want', key: 'cone skirt' }), 200);
                   const piece = TREE.rename;
                   TREE.rename = null;
                   treeClick(btn({ sel: 'i_want' }), 1000);
                   treeClick(btn({ sel: 'i_want' }), 1100);
                   return { r, piece, part: TREE.rename, h: treeHtml(S.design, view({ rename: piece })) };""")
    assert got["r"] == "rename"
    assert got["piece"] == {"part": "i_want", "key": "cone skirt", "draft": "the <cone>"}
    assert got["part"] == {"part": "i_want", "key": None, "draft": "Bar stool"}
    assert 'id="treeName"' in got["h"] and 'value="the &lt;cone&gt;"' in got["h"]


def test_clicks_on_two_rows_are_not_a_double_click():
    got = _page("""treeClick(btn({ sel: 'i_want', key: 'seat top' }), 0);
                   return { r: treeClick(btn({ sel: 'i_want', key: 'cone skirt' }), 100), rename: TREE.rename };""")
    assert got == {"r": "select", "rename": None}


def test_a_reference_cannot_be_renamed_from_the_tree():
    got = _page("""treeClick(btn({ sel: 'floor', fixed: '1' }), 0);
                   return { r: treeClick(btn({ sel: 'floor', fixed: '1' }), 100), rename: TREE.rename };""")
    assert got == {"r": "select", "rename": None}


def test_the_save_button_saves_that_row_and_the_fold_is_kept():
    got = _page("""const a = treeClick(btn({ renameSave: '1', part: 'i_want', key: 'seat top' }), 0);
                   const b = treeClick(btn({ renameSave: '1', part: 'i_want' }), 0);
                   const c = treeClick(btn({ fold: '1' }), 0);
                   return { a, b, c, calls, kept: JSON.parse(store['caliper-tree:x']).open };""")
    assert got["a"] == "save" and got["b"] == "save" and got["c"] == "fold" and got["kept"] is False
    assert got["calls"][:2] == [["save", "i_want", "seat top"], ["save", "i_want", None]]


def test_nothing_about_hiding_reaches_the_server():
    """A hidden piece is still in every check: what's hidden is kept in the browser and the save goes nowhere else."""
    src = open(JS).read()
    for name in ("keepTree", "isHidden"):
        from .test_carve_click import _fn

        assert "api(" not in _fn(src, name) and "fetch(" not in _fn(src, name)


# --- #161 review: the tree doesn't offer what it can't do ------------------------------------------------------------
def test_a_part_that_can_t_be_drawn_as_pieces_says_why_and_its_eyes_are_off():
    got = _page("""const h = treeHtml(S.design, view({ pieces: new Set(['i_want/seat top']),
                     cant: (p) => (p === 'i_want' ? "its shape isn't closed near z 40 mm" : null) }));
                   return { h, off: (h.match(/trow piece[^"]* off/g) || []).length };""")
    assert "can't draw this part's pieces: its shape isn't closed near z 40 mm" in got["h"]
    assert 'data-eye="i_want" data-key=' not in got["h"] and got["off"] == 0   # no row says hidden about what's on screen
    assert 'data-eye="i_want">' in got["h"]                                 # the whole part's eye still works


def test_in_one_body_a_piece_eye_is_off_and_no_row_says_hidden():
    got = _page("""const h = treeHtml(S.design, view({ pieces: new Set(['i_want/seat top']), oneBody: true }));
                   return { h, off: (h.match(/trow piece[^"]* off/g) || []).length };""")
    assert "disabled" in got["h"] and 'data-eye="i_want" data-key=' not in got["h"] and got["off"] == 0
    assert "can't draw" not in got["h"]


def test_with_pieces_drawn_the_eyes_work():
    got = _page("""return { h: treeHtml(S.design, view()) };""")
    assert 'data-eye="i_want" data-key="seat top"' in got["h"] and "disabled" not in got["h"]


def test_a_part_s_name_is_escaped_in_the_tree():
    got = _page("""S.design.parts[0].name = '<b>x</b>';
                   return { h: treeHtml(S.design, view()) };""")
    assert "&lt;b&gt;x&lt;/b&gt;" in got["h"] and "<b>x</b>" not in got["h"]


def test_a_failed_piece_gives_the_route_s_words(tmp_path):
    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = """const S = { slug: 'x' };
function fetch() { return Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "its shape isn't closed" }) }); }
""" + _fn(src, "loadPieces") + """
loadPieces({ id: 'p', version: 1, pieces: [{ key: 'a' }] }).then(() => console.log('no'), (e) => console.log(e.message));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.stdout.strip() == "its shape isn't closed", got.stderr


def test_the_route_says_422_with_the_words_where_a_piece_can_t_be_cut(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    monkeypatch.setattr(tree, "mesh", lambda *a: (_ for _ in ()).throw(ValueError("its shape isn't closed near z 40 mm")))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/bench/piece.stl", params={"key": "top"})
    assert got.status_code == 422 and got.json()["detail"] == "its shape isn't closed near z 40 mm"


def test_the_cut_list_and_the_pattern_page_read_the_label():
    from caliper import cutplan, patterns

    text = cutplan.cutlist_text({"id": "r1", "part": "step_stool", "name": "Step stool", "sticks": [], "sheets": []})
    assert text.startswith("CUT LIST — Step stool (r1)")
    assert cutplan.cutlist_text({"id": "r1", "part": "old", "sticks": [], "sheets": []}).startswith("CUT LIST — old (r1)")
    assert "A stool: Step stool, for hand tools" in patterns.index_html("A stool", "Step stool", [], 0)


def test_another_design_s_part_of_the_same_name_is_drawn_again():
    """Found checking #161: two designs each with an i_want at v8 kept the first one's pieces."""
    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = """let S = { slug: 'a', design: null }, loads = 0, drops = [];
const pieces3d = new Map([['i_want', { version: 8, byKey: new Map() }]]), noPieces = new Map([['other', { version: 1, why: 'x' }]]);
const dropPieces = (p) => { pieces3d.delete(p); drops.push(p); }, scene = { add() {} }, plainly = (m) => m, renderTree = () => {};
let piecesOf = 'a';
async function loadPieces() { loads += 1; return new Map(); }
""" + _fn(src, "syncPieces") + """
const design = { parts: [{ id: 'i_want', version: 8, role: 'part', pieces: [{ key: 'a' }] }] };
S.design = design;
(async () => {
  await syncPieces(design); const same = loads;
  S.slug = 'b';
  await syncPieces(design);
  console.log(JSON.stringify({ same, after: loads, drops, stale: noPieces.size }));
})();"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    out = json.loads(got.stdout)
    assert out["same"] == 0 and out["after"] == 1 and out["drops"][0] == "i_want" and out["stale"] == 0


def test_a_part_that_can_t_be_drawn_as_pieces_falls_back_and_says_why():
    """#161 review: a rethrow in place of the fallback passed: nothing ran the catch itself."""
    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = """let S = { slug: 'a', design: null }, told = 0;
const pieces3d = new Map(), noPieces = new Map();
const dropPieces = (p) => pieces3d.delete(p), scene = { add() {} }, plainly = (m) => m, renderTree = () => { told += 1; };
let piecesOf = 'a';
async function loadPieces() { throw new Error("its shape isn't closed"); }
""" + _fn(src, "syncPieces") + """
const design = { parts: [{ id: 'p', version: 2, role: 'part', pieces: [{ key: 'a' }] }] };
S.design = design;
syncPieces(design).then(() => console.log(JSON.stringify({ why: noPieces.get('p'), told, drawn: pieces3d.size })),
                       (e) => console.log(JSON.stringify({ threw: e.message })));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"why": {"version": 2, "why": "its shape isn't closed"}, "told": 1, "drawn": 0}
