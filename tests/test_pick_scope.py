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
