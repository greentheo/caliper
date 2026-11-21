"""CALI-235 (#17's page part): the plan's groups as nodes in the part tree.

#369 (slice A) gave a plan groups, sub-assemblies inside one design ("a platform plus a box on top"), and
`Design.groups` as the tree's contract. The tree draws each group as a node above its parts:
- you can fold a group, and hide or show it as one;
- the person's own order and nesting (#94) apply inside a group;
- a move across groups is refused in words, since the plan says which group a part is in;
- a design without groups draws exactly as it did."""
import json
import re
import subprocess

import pytest

from .test_carve_click import JS, _fn, _node

HELP = ("groupOf", "treeOver", "crossesGroup", "groupName")
#: Theo's camper, stubbed: a platform (deck, joists), and a box on it (its floor, and its walls, a group inside it)
CAMPER = {
    "parts": [{"id": i, "name": i.replace("_", " "), "version": 1, "pieces": []}
              for i in ("deck", "joists", "box_floor", "left_wall", "right_wall", "ladder")],
    "groups": [{"id": "platform", "what": "the flatbed platform", "parts": ["deck", "joists"], "mounts_on": []},
               {"id": "box", "what": "the box on top", "parts": ["box_floor", "walls"], "mounts_on": ["platform"]},
               {"id": "walls", "what": "", "parts": ["left_wall", "right_wall"], "mounts_on": []}],
    "tree": {"order": ["joists", "deck", "right_wall", "left_wall", "box_floor", "ladder"], "parent": {}}}


def _js(body, design=None, names=(), head=""):
    src = open(JS).read()
    consts = "const esc = (s) => String(s); const EYE_ON = 'o', EYE_OFF = 'x'; const renameRow = () => ''; const pieceId = (p, k) => `${p}/${k}`;\n"
    script = (consts + f"const D = {json.dumps(design or CAMPER)};\n" + head
              + "".join(_fn(src, n) for n in HELP + ("treeRows", "underPart", "dropped", "nudge", "treeHtml") + tuple(names))
              + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _rows(design=None):
    return _js("return treeRows(D).map((r) => [r.g ? `group ${r.g.id}` : r.p.id, r.depth]);", design)


# --- the rows ---------------------------------------------------------------------------------------------------------------
def test_the_camper_s_groups_are_nodes_over_their_parts_in_the_person_s_order():
    assert _rows() == [["group platform", 0], ["joists", 1], ["deck", 1],
                       ["group box", 0], ["group walls", 1], ["right_wall", 2], ["left_wall", 2], ["box_floor", 1],
                       ["ladder", 0]]                                    # in no group: after the groups, as now


def test_a_part_nests_under_another_only_inside_its_group():
    nested = {**CAMPER, "tree": {**CAMPER["tree"], "parent": {"deck": "joists", "box_floor": "deck"}}}
    rows = _rows(nested)
    assert ["deck", 2] in rows                                           # under the joists: both the platform's
    assert ["box_floor", 1] in rows                                      # the box's own, never under the platform's deck


def test_a_design_without_groups_rows_as_it_always_did():
    flat = {**CAMPER, "groups": [], "tree": {"order": CAMPER["tree"]["order"], "parent": {"deck": "joists"}}}
    assert _rows(flat) == [["joists", 0], ["deck", 1], ["right_wall", 0], ["left_wall", 0], ["box_floor", 0], ["ladder", 0]]
    no_key = {k: v for k, v in flat.items() if k != "groups"}
    view = "{ parts: new Set(['ladder']), pieces: new Set(), open: true, scope: 'deck', canDrag: true }"
    assert _js(f"return treeHtml(D, {view});", flat) == _js(f"return treeHtml(D, {view});", no_key)


#: main's tree before groups (593d727-era treeHtml, run on this design and view): a design without groups draws exactly this
BEFORE = {"parts": [{"id": "step_stool", "name": "Step stool", "version": 3, "pieces": [{"key": "tread", "name": "tread", "material": "softwood plywood", "color": "#c98"}]}, {"id": "bench", "name": "Bench", "version": 1, "pieces": []}, {"id": "car", "name": "car", "role": "fixed", "version": 1, "pieces": []}], "tree": {"order": ["bench", "step_stool", "car"], "parent": {"step_stool": "bench"}}, "legend": [{"color": "#c98", "label": "softwood plywood", "count": 1}]}
BEFORE_HTML = "<div class=\"tree-head\"><button class=\"fold\" data-fold=\"1\" aria-expanded=\"true\">\u25be Parts</button>\n    <span class=\"note\">hidden pieces are still checked</span></div><div role=\"tree\" aria-label=\"Parts\"><div class=\"tpart\" data-tpart=\"bench\" style=\"margin-left:0px\"><div class=\"trow part on\" draggable=\"true\" data-drag=\"bench\">\n      <button class=\"eye\" aria-label=\"Show or hide the whole part\" data-eye=\"bench\">o</button>\n      <button class=\"tname\" role=\"treeitem\" aria-level=\"1\" aria-selected=\"true\" data-sel=\"bench\" aria-keyshortcuts=\"Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft\">Bench</button>\n      <span class=\"side\">v1</span></div></div><div class=\"tpart\" data-tpart=\"step_stool\" style=\"margin-left:18px\"><div class=\"trow part\" draggable=\"true\" data-drag=\"step_stool\">\n      <button class=\"eye\" aria-label=\"Show or hide the whole part\" data-eye=\"step_stool\">o</button>\n      <button class=\"tname\" role=\"treeitem\" aria-level=\"2\" aria-selected=\"false\" data-sel=\"step_stool\" aria-keyshortcuts=\"Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft\">Step stool</button>\n      <span class=\"side\">v3</span></div><div class=\"trow piece\">\n        <button class=\"eye\" aria-label=\"Show or hide this piece\" data-eye=\"step_stool\" data-key=\"tread\">o</button>\n        <span class=\"swatch\" aria-hidden=\"true\" style=\"background:#c98\"></span>\n        <button class=\"tname\" role=\"treeitem\" aria-level=\"3\" aria-selected=\"false\" data-sel=\"step_stool\" data-key=\"tread\">tread</button>\n        <span class=\"side\">softwood plywood</span></div></div><div class=\"tpart\" data-tpart=\"car\" style=\"margin-left:0px\"><div class=\"trow part ref off\" draggable=\"true\" data-drag=\"car\">\n      <button class=\"eye\" aria-label=\"Show or hide the whole part\" data-eye=\"car\">x</button>\n      <button class=\"tname\" role=\"treeitem\" aria-level=\"1\" aria-selected=\"false\" data-sel=\"car\" data-fixed=\"1\" aria-keyshortcuts=\"Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft\">car</button>\n      <span class=\"side\">reference</span></div></div></div><div class=\"tlegend\"><div class=\"tlegend-h\">Materials</div><div class=\"tlegend-r\"><span class=\"swatch\" aria-hidden=\"true\" style=\"background:#c98\"></span>softwood plywood \u00b7 1 piece</div></div>"


@pytest.mark.parametrize("groups", ["no key", []])
def test_a_design_without_groups_draws_byte_for_byte_as_before(groups):
    """The foreman's pin: the flat stool's tree, unchanged to the byte."""
    design = dict(BEFORE) if groups == "no key" else {**BEFORE, "groups": groups}
    src = open(JS).read()
    esc = re.search(r"^const esc = .*;$", src, re.M).group(0) + "\n"
    script = (esc + "const EYE_ON = 'o', EYE_OFF = 'x'; const pieceId = (p, k) => `${p}/${k}`;\n"
              + "".join(_fn(src, n) for n in HELP + ("renameRow", "treeRows", "treeHtml"))
              + f"\nconsole.log(JSON.stringify(treeHtml({json.dumps(design)}, {{ parts: new Set(['car']), pieces: new Set(), open: true, rename: null, "
              + "scope: 'bench', piece: null, canDrag: true, saying: null, oneBody: false })));")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == BEFORE_HTML


# --- the nodes --------------------------------------------------------------------------------------------------------------
def _html(view="", design=None):
    return _js(f"return treeHtml(D, {{ parts: new Set(), pieces: new Set(), open: true, scope: null, canDrag: true, {view} }});", design)


def test_a_group_node_folds_hides_and_says_how_many_parts():
    html = _html()
    box = re.search(r'<div class="tgroup" data-tgroup="box".*?</div></div>', html, re.S).group(0)
    assert 'data-gfold="box"' in box and 'aria-expanded="true"' in box and 'aria-level="1"' in box
    assert 'data-geye="box"' in box and "Box</button>" in box and "3 parts" in box and "the box on top" in box
    assert 'role="treeitem" aria-level="3"' in html                     # a wall: two groups down


def test_a_folded_group_hides_its_members_and_its_inner_groups():
    html = _html("folded: new Set(['box'])")
    assert 'data-gfold="box"' in html and 'aria-expanded="false"' in html
    for gone in ("walls", "left_wall", "right_wall", "box_floor"):
        assert f'"{gone}"' not in html, gone
    assert 'data-tpart="ladder"' in html and 'data-tpart="deck"' in html


def test_a_group_s_eye_is_off_only_when_every_part_in_it_is_hidden():
    some = _html("parts: new Set(['left_wall'])")
    allw = _html("parts: new Set(['left_wall', 'right_wall'])")
    walls = lambda h: re.search(r'<div class="tgroup" data-tgroup="walls".*?</div>', h, re.S).group(0)
    assert 'class="trow group"' in walls(some) and ">o</button>" in walls(some)
    assert 'class="trow group off"' in walls(allw) and ">x</button>" in walls(allw)


def test_the_group_s_eye_hides_then_shows_every_part_in_it_however_deep():
    head = """const S = { slug: 's', design: D }; let painted = 0; const paint = () => { painted += 1; }; const renderTree = () => {};
const TREE = { slug: 's', parts: new Set(['left_wall']), pieces: new Set() }; const seen = () => TREE; const keepTree = () => {};
"""
    got = _js("""toggleGroup('box'); const hid = [...TREE.parts].sort(); toggleGroup('box'); return { hid, after: [...TREE.parts], painted };""",
              names=("groupParts", "toggleGroup"), head=head)
    assert got == {"hid": ["box_floor", "left_wall", "right_wall"], "after": [], "painted": 2}


def test_a_group_s_fold_and_eye_are_its_clicks_and_kept_with_the_tree():
    src = open(JS).read()
    click = _fn(src, "treeClick")
    assert "if (d.gfold) { if (!t.folded.delete(d.gfold)) t.folded.add(d.gfold); keepTree(); renderTree(); return 'gfold'; }" in click
    assert "if (d.geye) { toggleGroup(d.geye); return 'geye'; }" in click
    assert "folded: [...TREE.folded]" in _fn(src, "keepTree") and "TREE.folded = new Set(kept.folded || []);" in _fn(src, "seen")
    assert "folded: t.folded" in _fn(src, "renderTree")


# --- moving a part ------------------------------------------------------------------------------------------------------------
def test_a_part_moves_within_its_group_by_its_keys():
    got = _js("""return { up: nudge(D, 'deck', 'up'), down: nudge(D, 'deck', 'down'), wallUp: nudge(D, 'left_wall', 'up'),
                         floorUp: nudge(D, 'box_floor', 'up'), out: nudge(D, 'joists', 'out'), into: nudge(D, 'deck', 'in') };""")
    assert got["up"] == ["joists", "before"] and got["down"] is None      # the platform's last: never past into the box
    assert got["wallUp"] == ["right_wall", "before"]
    assert got["floorUp"] is None                                        # the box's first part: its walls are a group, not a part
    assert got["out"] is None                                            # nothing over it but its group: it never leaves it
    assert got["into"] == ["joists", "into"]


def test_a_move_across_groups_is_refused_and_one_within_is_made():
    got = _js("""return { across: dropped(D, 'deck', 'box_floor', 'after'), into: dropped(D, 'ladder', 'deck', 'into'),
                         within: dropped(D, 'deck', 'joists', 'before') };""")
    assert got["across"] is None and got["into"] is None
    assert got["within"]["order"][:2] == ["deck", "joists"]


def test_a_move_across_groups_is_said_never_a_silent_no():
    head = """const S = { slug: 's', design: D }; const said = []; const say = (t) => said.push(t); let posted = 0;
const api = async () => { posted += 1; return D; };"""
    got = _js("await moveInTree('deck', 'box_floor', 'after'); await moveInTree('ladder', 'left_wall', 'into'); return { said, posted };",
              names=("groupRefusal", "moveInTree"), head=head)
    assert got == {"said": ["The platform's parts are the plan's: to move one into or out of it, say it in the chat.",
                            "The walls' parts are the plan's: to move one into or out of it, say it in the chat."], "posted": 0}


def test_a_drag_across_groups_is_taken_so_it_s_said():
    src = _fn(open(JS).read(), "treeDragOver")
    assert "crossesGroup(S.design, TREE.drag, row.dataset.drag)" in src and "e.preventDefault();" in src


# --- the server ---------------------------------------------------------------------------------------------------------------
pytest.importorskip("cadquery")


def test_the_design_s_state_carries_its_groups(tmp_path):
    from caliper import design_api
    from caliper.design import DesignStore

    s = DesignStore.create("a truck camper", base=str(tmp_path / "designs"))
    assert design_api.design_state(s)["groups"] == []
    s.design.plan = {**(s.design.plan or {}), "groups": CAMPER["groups"]}
    assert design_api.design_state(s)["groups"] == CAMPER["groups"]
