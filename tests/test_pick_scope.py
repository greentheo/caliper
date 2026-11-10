"""A pick says what the message is about: not the piece that happened to be selected (#181)."""
from __future__ import annotations

import json
import os
import subprocess

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
EDGE = "{ part: 'stool', kind: 'edge', id: 'e3', said: 'edge: the circle between two cones', local: [0, 0, 14.1] }"


def _page(body: str) -> dict:
    src = open(JS).read()
    head = """
const els = {};
const $ = (id) => (els[id] = els[id] || { hidden: false, textContent: '', placeholder: '' });
const S = { slug: 'x', scope: 'stool', piece: 'seat', pick: null, design: { parts: [
  { id: 'stool', name: 'i_want', pieces: [{ key: 'seat', name: 'seat disk' }, { key: 'cone', name: 'cone skirt' }] }] } };
"""
    fns = "\n".join(_fn(src, n) for n in ("pieceInScope", "renderScope", "aboutPiece", "aboutPick"))
    script = head + fns + f"\nconst out = (() => {{ {body} }})();\nconsole.log(JSON.stringify(out));"
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
