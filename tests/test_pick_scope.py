"""A pick says what the message is about: not the piece that happened to be selected (#181)."""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
EDGE = "{ part: 'stool', kind: 'edge', id: 'e3', said: 'edge: the circle between two cones', local: [0, 0, 14.1] }"


def _page(body: str, extra: tuple = (), more: str = "") -> dict:
    src = open(JS).read()
    head = """
const els = {};
const $ = (id) => (els[id] = els[id] || { hidden: false, textContent: '', placeholder: '' });
const PICK = { mode: 'face', lit: null, turn: 0, overlay: null };
let trees = 0;
const renderTree = () => { trees += 1; };
const S = { slug: 'x', scope: 'stool', piece: 'seat', pick: null, design: { parts: [
  { id: 'stool', name: 'i_want', pieces: [{ key: 'seat', name: 'seat disk' }, { key: 'cone', name: 'cone skirt' }] }] } };
"""
    fns = "\n".join(_fn(src, n) for n in ("pieceInScope", "renderScope", "aboutPiece", "aboutPick", *extra))
    script = head + more + fns + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_selected_piece_is_what_the_chat_is_about():
    got = _page("renderScope(); return { m: aboutPiece('make it thicker'), chip: $('scopeChip').textContent, box: $('msg').placeholder };")
    assert got == {"m": "About the seat disk: make it thicker", "chip": "i_want · seat disk",
                   "box": "What should change about seat disk?"}


def test_with_a_pick_the_message_names_only_what_was_picked():
    got = _page(f"S.pick = {EDGE}; return {{ m: aboutPick(S.pick, aboutPiece('make this fillet bigger')) }};")
    assert got["m"].startswith("About this edge: the circle between two cones") and got["m"].endswith(": make this fillet bigger")
    assert "seat disk" not in got["m"]


def test_with_a_pick_the_chips_and_the_box_name_only_what_was_picked():
    got = _page(f"""S.pick = {EDGE}; renderScope();
                    return {{ chip: $('scopeChip').textContent, picked: $('pickChip').textContent, box: $('msg').placeholder }};""")
    assert got == {"chip": "i_want", "picked": "edge: the circle between two cones", "box": "What should change about i_want?"}


def test_clearing_the_pick_gives_the_piece_back():
    got = _page(f"""S.pick = {EDGE}; renderScope(); S.pick = null; renderScope();
                    return {{ chip: $('scopeChip').textContent, m: aboutPiece('thicker') }};""")
    assert got == {"chip": "i_want · seat disk", "m": "About the seat disk: thicker"}


def test_it_reads_the_part_in_scope_not_the_first_part():
    got = _page("""S.design.parts.unshift({ id: 'other', name: 'other', pieces: [{ key: 'seat', name: 'wrong seat' }] });
                   return { m: aboutPiece('thicker') };""")
    assert got == {"m": "About the seat disk: thicker"}


def test_the_tree_stops_lighting_the_piece_while_a_pick_is_the_subject():
    got = _page(f"""renderScope(); const was = trees; S.pick = {EDGE}; renderScope(); const on = PICK.lit, drew = trees - was;
                    renderScope(); const again = trees - was;
                    S.pick = null; renderScope();
                    return {{ on, drew, again, back: PICK.lit, after: trees - was }};""")
    assert got == {"on": None, "drew": 1, "again": 1, "back": "seat", "after": 2}


def test_the_tree_is_given_the_piece_only_without_a_pick():
    assert "piece: S.pick ? null : S.piece," in _fn(open(JS).read(), "renderTree")


# --- a click that misses --------------------------------------------------------------------------------------------------
_CHOOSE = """
const stub = { clone() { return {}; }, copy() {} };
const ray = { ray: stub }, camera = stub, renderer = { domElement: { getBoundingClientRect: () => ({}) } }, scene = { remove() {} };
const setScope = () => {}; const pickHint = () => {}; const plainly = (s) => s; const facePicked = () => null;
const HIT = { object: { userData: { partId: 'stool' } }, point: { x: 1, y: 2, z: 3 }, distance: 10 };
"""


@pytest.mark.parametrize("why,mode,features,hit", [("the features failed", "face", "async () => { throw new Error('x'); }", "HIT"),
                                                   ("the click was off the part", "face", "async () => ({ solidMesh: false })", "null"),
                                                   ("the click hit no face", "face", "async () => ({ solidMesh: false })", "HIT")])
def test_a_click_that_misses_redraws_so_the_chip_and_box_match_the_message(why, mode, features, hit):
    got = _page(f"""S.pick = {EDGE}; renderScope(); const before = $('pickChip').textContent;
                    PICK.mode = {mode!r}; globalThis.features = {features};
                    await choose({{}}, {hit}); await null;
                    return {{ before, hidden: $('pickChip').hidden, chip: $('scopeChip').textContent, box: $('msg').placeholder, m: aboutPick(S.pick, aboutPiece('x')) }};""",
                extra=("clearPick", "choose"), more=_CHOOSE)
    assert got["before"].startswith("edge:") and got["hidden"] is True
    assert got == {**got, "chip": "i_want · seat disk", "box": "What should change about seat disk?", "m": "About the seat disk: x"}


# --- what the designer is told, and what the person sees ------------------------------------------------------------------
def test_a_point_goes_to_the_designer_in_millimetres_whatever_the_page_shows():
    got = _page("""const p = { said: 'point on the surface: x 1.2 in, y 0 in, z 2 in', told: 'point on the surface: x 30.5 mm, y 0 mm, z 50.8 mm', local: null };
                   return { m: aboutPick(p, 'thicken here') };""")
    assert got["m"] == "About this point on the surface: x 30.5 mm, y 0 mm, z 50.8 mm: thicken here"


def test_the_point_told_is_in_millimetres():
    src = open(JS).read()
    assert "pointTold(point)" in _fn(src, "choose")
    i = src.index("const pointTold = ")
    script = src[i:src.index("\n", i)] + "\nconsole.log(pointTold([30.48, 0, 50.84]));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.stdout.strip() == "point on the surface: x 30.5 mm, y 0 mm, z 50.8 mm"


def test_the_person_s_bubble_is_kept_apart_from_what_the_designer_reads(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import design_api as D
    from caliper.design import DesignStore
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.setattr(D.chat, "turn", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no designer in this test")))
    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    c = TestClient(create_app())
    c.post(f"/api/designs/{store.design.slug}/chat", json={"message": "About this edge (at x 0 mm): round it", "shown": "About this edge: round it"})
    (e,) = [x for x in DesignStore.load(store.root).log() if x.get("kind") == "message"]
    assert e["text"] == "About this edge (at x 0 mm): round it" and e["shown"] == "About this edge: round it"


def test_the_page_draws_the_bubble_from_what_was_shown():
    src = open(JS).read()
    assert "md(e.shown || e.text)" in _fn(src, "renderThread") and "liveTurn(shown || text, scope)" in _fn(src, "send")
    assert "...(shown ? { shown } : {})" in _fn(src, "send")
    assert "const shown = S.pick ? `About this ${S.pick.said}: ${text}` : null;" in src


# --- a pick across a rebuild (#196) -----------------------------------------------------------------------------------------
_PICKED = _CHOOSE.replace("const facePicked = () => null;", "const facePicked = () => ({ id: 'f7', said: 'face: the cone', local: [0, 0, 1], verts: [], tris: [] });") + """
class Geom { setAttribute() {} setIndex() {} translate() { return this; } }
class Vec { constructor() {} }
const THREE = { BufferGeometry: Geom, Float32BufferAttribute: class {}, SphereGeometry: Geom, TubeGeometry: Geom, Vector3: Vec, CatmullRomCurve3: class {} };
let hint = ''; const drawPick = () => {};
stub.position = { distanceTo: () => 10 };
const edgePicked = () => ({ id: 'e3', said: 'edge: the circle', local: [0, 0, 2], centre: [0, 0, 0], points: [[0, 0, 0], [1, 1, 1]] });
const len = (v) => `${v} mm`;
"""


def _picked(body, mode="face", solid=False):
    head = f"""S.design.parts[0].version = 9; PICK.mode = '{mode}'; globalThis.features = async () => ({{ solidMesh: {str(solid).lower()}, version: 9 }});
              await choose({{}}, HIT);\n"""
    src = open(JS).read()
    point = "".join(src[src.index(f"const {n} = "):src.index("\n", src.index(f"const {n} = ")) + 1] for n in ("pointSaid", "pointTold"))
    return _page(head + body, extra=("clearPick", "choose", "pickPosted", "dropOldPick"),
                 more=_PICKED.replace("const pickHint = () => {};", "const pickHint = (t) => { hint = t; };") + point)


def test_a_pick_carries_the_version_it_was_made_on():
    assert _picked("return { v: S.pick.version, id: S.pick.id };") == {"v": 9, "id": "f7"}


def test_it_is_posted_with_that_version_even_if_the_design_has_moved_on():
    got = _picked("S.design.parts[0].version = 10; return { p: pickPosted('round it') };")["p"]
    assert got == {"kind": "face", "id": "f7", "version": 9, "text": "round it"}


def test_a_rebuild_drops_the_pick_and_says_so():
    got = _picked("S.design.parts[0].version = 10; dropOldPick(); renderScope(); return { pick: S.pick, hidden: $('pickChip').hidden, hint };")
    assert got == {"pick": None, "hidden": True, "hint": "Rebuilt: click it again"}


def test_a_redraw_at_the_same_version_keeps_it():
    got = _picked("dropOldPick(); return { id: S.pick.id, hint };")
    assert got == {"id": "f7", "hint": ""}


def test_a_part_that_s_gone_takes_its_pick_with_it():
    assert _picked("S.design.parts = []; dropOldPick(); return { pick: S.pick };") == {"pick": None}


def test_every_redraw_looks():
    assert "dropOldPick();" in _fn(open(JS).read(), "render")


def test_an_edge_carries_its_version_too():
    assert _picked("S.design.parts[0].version = 10; return { p: pickPosted('round it') };", mode="edge")["p"] == {
        "kind": "edge", "id": "e3", "version": 9, "text": "round it"}


def test_a_point_carries_its_version_too():
    got = _picked("return { v: S.pick.version, kind: S.pick.kind, p: pickPosted('x') };", mode="face", solid=True)
    assert got == {"v": 9, "kind": "point", "p": None}             # a point has no id: nothing for the landing check to read


def test_a_rebuild_drops_an_edge_and_a_point_too():
    for mode, solid in (("edge", False), ("face", True)):
        assert _picked("S.design.parts[0].version = 10; dropOldPick(); return { pick: S.pick };", mode=mode, solid=solid) == {"pick": None}


_OPEN = """
const showLoading = () => {}; const doneLoading = () => {}; const render = () => {}; const syncParts = async () => {}; const loadFailed = () => {};
const location = {}; const api = async () => ({ parts: [{ id: 'stool', version: 9 }] });
"""


def _opened(body):
    src = open(JS).read()
    point = "".join(src[src.index(f"const {n} = "):src.index("\n", src.index(f"const {n} = ")) + 1] for n in ("pointSaid", "pointTold"))
    head = """S.design.parts[0].version = 9; PICK.mode = 'face'; globalThis.features = async () => ({ solidMesh: false, version: 9 });
              await choose({}, HIT);\n"""
    return _page(head + body, extra=("clearPick", "choose", "pickPosted", "dropOldPick", "openDesign"),
                 more=_PICKED.replace("const pickHint = () => {};", "const pickHint = (t) => { hint = t; };") + point + _OPEN)


def test_opening_another_design_drops_the_pick_with_no_rebuilt_line():
    assert _opened("hint = 'Rebuilt: click it again'; await openDesign('another'); return { pick: S.pick, hint: hint === undefined ? 'reset' : hint };") == {
        "pick": None, "hint": "reset"}


def test_reopening_the_same_design_keeps_it():
    assert _opened("await openDesign('x'); return { id: S.pick.id, hint };") == {"id": "f7", "hint": ""}


def test_a_new_design_drops_the_pick_and_the_rebuilt_line():
    src = _fn(open(JS).read(), "startNew")
    assert "clearPick(); pickHint();" in src and src.index("clearPick();") < src.index("$('inspector').innerHTML")

