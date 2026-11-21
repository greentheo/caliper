"""CALI-185 (#296, slice B1): a part's load cases and supports on the 3D view while they're edited, and a row's box picked as a
face of the model.

Theo, 2026-11-14: "it should be identified similar to how the current stress loading is specified with the arrow ... or the
'fixed plane' (i.e. the bottom of the stool or the face that doesn't move)". Slice A (#312) made them rows of text. Here the
rows are drawn as they read, typed or not, and "Pick on the model" sets a row's box to a face clicked on the part. The rows
stay the source: a pick writes the same corners Save sends. No server change; the boxes are in the design's coordinates,
as slice A's are and as the check reads them."""
import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _js(names, body, head=""):
    src = open(JS).read()
    import re

    consts = "".join(re.search(rf"^const {c} = .*$", src, re.M).group(0) + "\n" for c in ("SCEN_N",))
    script = head + consts + "".join(_fn(src, n) for n in names) + \
        f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


GOT = {"scenarios": [
    {"name": "standing on the top", "amount": 250, "unit": "lb", "factor": 2, "direction": [0, 0, -1], "lo": [0, 0, 400], "hi": [300, 300, 402], "on": True},
    {"name": "a push from the side", "amount": 20, "unit": "kg", "factor": 1, "direction": [1, 0, 0], "lo": [0, 0, 0], "hi": [2, 300, 400], "on": False},
    {"name": "no box yet", "amount": 5, "unit": "N", "factor": 1}],
    "supports": [{"name": "the floor", "floor": True}, {"name": "held here", "lo": [0, 0, 0], "hi": [10, 10, 10]}]}
BBOX = {"min": [0, 0, 0], "max": [300, 300, 402], "size": [300, 300, 402]}


def test_every_row_with_a_box_is_drawn_loads_by_what_they_must_hold():
    got = _js(("scenMarksFor",), f"return scenMarksFor({json.dumps(GOT)}, {json.dumps(BBOX)});")
    loads = [m for m in got if m["kind"] == "load"]
    assert [m["i"] for m in loads] == [0, 1]                                    # the row with no box isn't drawn
    assert abs(loads[0]["n"] - 250 * 4.448222 * 2) < 0.01 and abs(loads[1]["n"] - 20 * 9.80665) < 0.01   # its margin in it
    assert loads[0]["on"] is True and loads[1]["on"] is False and loads[1]["dir"] == [1, 0, 0]
    assert {"kind": "floor", "i": 0, "lo": [0, 0, 0], "hi": [300, 300, 0]} in got   # the floor, under the part
    assert {"kind": "support", "i": 1, "lo": [0, 0, 0], "hi": [10, 10, 10]} in got


def test_with_no_box_known_the_floor_isn_t_guessed():
    got = _js(("scenMarksFor",), f"return scenMarksFor({json.dumps(GOT)}, null);")
    assert not [m for m in got if m["kind"] == "floor"]


def test_the_biggest_load_has_the_longest_arrow_and_none_is_a_dot():
    got = _js(("arrowLen",), "return [arrowLen(1000, 1000, 100), arrowLen(250, 1000, 100), arrowLen(0, 1000, 100)];")
    assert got[0] == 100 and got[2] == 35 and abs(got[1] - (35 + 65 * 0.5)) < 1e-9


def test_a_face_s_box_is_its_points_a_millimetre_out_each_way():
    got = _js(("faceBox",), "return faceBox([0, 0, 400, 300, 0, 400, 300, 300, 400.04, 0, 300, 400]);")
    assert got == {"lo": [-1, -1, 399], "hi": [301, 301, 401]}                # a flat face is 2 mm deep, so it touches


# --- Pick on the model -------------------------------------------------------------------------------------------------
_PICK = """
let hint = null, repainted = null;
const S = { scen: { stool: JSON.parse(JSON.stringify(GOT)) }, scenPick: null, design: { parts: [{ id: 'stool', name: 'Step stool' }, { id: 'rail', name: 'rail' }] } };
const pickHint = (t) => { hint = t ?? null; };
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {};
const plainly = (m) => m; const esc = (s) => String(s);
let saveShown = false; const said = { innerHTML: '' };
const $ = (id) => (id === 'scenSave' ? (saveShown ? {} : null) : id === 'scenSaid' ? said : null);
let typed = null; const readScenarios = (got) => typed || { scenarios: got.scenarios, supports: got.supports };
const repaintScen = (pid) => { repainted = pid; };
let DATA = { solidMesh: false }, FACE = { said: 'face: the top face, 12 in by 12 in', verts: [0, 0, 400, 300, 0, 400, 300, 300, 400] };
let slow = null;
const features = async (pid) => (slow ? slow : DATA);
const facePicked = () => FACE;
const hitOn = (pid) => ({ object: { userData: { partId: pid } } });
let phone = false; const panes = []; const onPhone = () => phone; const setPane = (p) => panes.push(p);
// the part's frame: a stand-in that moves x by the part's position (the real one is three.js, tested below)
const scenFrame = (p) => ({ dx: p && p.position ? p.position[0] : 0 });
const unposed = (v, f) => v.map((x, k) => (k % 3 === 0 ? x - f.dx : x));
"""


def _pick(body):
    return _js(("faceBox", "startScenPick", "stopScenPick", "pickScenarioFace"), body,
               head=f"const GOT = {json.dumps(GOT)};\n" + _PICK)


def test_a_load_s_box_becomes_the_face_clicked_and_the_rows_redraw():
    got = _pick("""startScenPick('stool', 'load', 0); const asked = hint;
                   const r = await pickScenarioFace(hitOn('stool'));
                   return { asked, r, row: S.scen.stool.scenarios[0], picking: S.scenPick, hint, repainted, said: said.innerHTML };""")
    assert got["asked"] == 'Click a face of Step stool for "standing on the top" (Esc stops)'
    assert got["r"] == "picked" and got["row"]["lo"] == [-1, -1, 399] and got["row"]["hi"] == [301, 301, 401]
    assert got["row"]["amount"] == 250 and got["row"]["direction"] == [0, 0, -1]          # what it is and which way: kept
    assert got["picking"] is None and got["hint"] == "Picked the top face, 12 in by 12 in" and got["repainted"] == "stool"
    assert "The box is now the top face, 12 in by 12 in. Save them to keep it." in got["said"]


def test_a_posed_part_s_picked_box_is_in_its_own_frame():
    """CALI-220 (#375): rows are in the part's own frame, as its script's loads() are; #109's faces are posed. A part moved
    500 mm along x: the face clicked at x 500..800 is the row's 0..300."""
    got = _pick("""S.design.parts[0].position = [500, 0, 0]; S.design.parts[0].rotation = [0, 0, 0];
                   FACE = { said: 'face: the top', verts: [500, 0, 400, 800, 0, 400, 800, 300, 400] };
                   startScenPick('stool', 'load', 0); await pickScenarioFace(hitOn('stool'));
                   return S.scen.stool.scenarios[0];""")
    assert got["lo"] == [-1, -1, 399] and got["hi"] == [301, 301, 401]


def test_the_frame_is_the_part_s_pose_and_unposing_undoes_it():
    """scenFrame and unposed with the page's own three.js: a part at (100, 0, 0) turned 90° about z."""
    src = open(JS).read()
    three = os.path.join(os.path.dirname(JS), "vendor", "three", "three.module.js")
    script = (f"import * as THREE from {json.dumps('file://' + three)};\n" + _fn(src, "scenFrame") + _fn(src, "unposed")
              + """const f = scenFrame({ position: [100, 0, 0], rotation: [0, 0, 90] });
const posed = new THREE.Vector3(10, 0, 0).applyMatrix4(f);
const back = unposed([posed.x, posed.y, posed.z], f);
const none = scenFrame({ id: 'p' }).equals(new THREE.Matrix4());
console.log(JSON.stringify({ posed: [posed.x, posed.y, posed.z].map((v) => Math.round(v * 1e6) / 1e6), back: back.map((v) => Math.round(v * 1e6) / 1e6), none }));""")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    out = json.loads(got.stdout)
    assert out["posed"] == [100, 10, 0] and out["back"] == [10, 0, 0] and out["none"] is True   # no pose said: the identity


def test_the_marks_are_drawn_in_the_part_s_frame():
    src = open(JS).read()
    assert "scenMarks.matrix.copy(scenMatrixOf(p));" in _fn(src, "drawScenarios")
    assert "const own = p && p.bbox ? localBox(p.bbox, scenMatrixOf(p)) : null;" in _fn(src, "drawScenarios")
    assert "scenMarks.matrixAutoUpdate = false;" in src
    assert "const box = faceBox(unposed(f.verts, scenFrame(partOf(pid))))" in _fn(src, "pickScenarioFace")


def test_a_support_s_box_becomes_the_face_clicked():
    got = _pick("startScenPick('stool', 'support', 1); await pickScenarioFace(hitOn('stool')); return S.scen.stool.supports[1];")
    assert got == {"name": "held here", "lo": [-1, -1, 399], "hi": [301, 301, 401]}


def test_what_s_typed_in_the_other_rows_is_kept_through_a_pick():
    got = _pick("""saveShown = true; typed = { scenarios: GOT.scenarios.map((s, i) => (i === 1 ? { ...s, amount: 99 } : s)), supports: GOT.supports };
                   startScenPick('stool', 'load', 0); await pickScenarioFace(hitOn('stool'));
                   return [S.scen.stool.scenarios[1].amount, S.scen.stool.scenarios[0].lo];""")
    assert got == [99, [-1, -1, 399]]


@pytest.mark.parametrize("case,result,words,still", [
    ("miss", "missed", "Not picked: no face there", False),
    ("other", "other", "That's rail: click Step stool (Esc stops)", True),
    ("mesh", "mesh", "Step stool has no faces to pick (it's a mesh): type its corners", False),
    ("noface", "missed", "Not picked: no face there", False)])
def test_a_pick_that_can_t_be_says_why_and_writes_nothing(case, result, words, still):
    setup = {"miss": "const h = null;", "other": "const h = hitOn('rail');", "mesh": "DATA = { solidMesh: true }; const h = hitOn('stool');",
             "noface": "FACE = null; const h = hitOn('stool');"}[case]
    got = _pick(setup + """ startScenPick('stool', 'load', 0); const r = await pickScenarioFace(h);
                            return { r, hint, still: !!S.scenPick, row: S.scen.stool.scenarios[0].lo };""")
    assert got == {"r": result, "hint": words, "still": still, "row": [0, 0, 400]}


def test_a_pick_stopped_while_its_faces_are_worked_out_writes_nothing():
    got = _pick("""let release; slow = new Promise((r) => { release = () => r({ solidMesh: false }); });
                   startScenPick('stool', 'load', 0); const going = pickScenarioFace(hitOn('stool'));
                   stopScenPick('Stopped picking'); release(); const r = await going;
                   return { r, row: S.scen.stool.scenarios[0].lo };""")
    assert got == {"r": "late", "row": [0, 0, 400]}


def test_with_no_pick_asked_a_click_is_the_view_s():
    assert _pick("return await pickScenarioFace(hitOn('stool'));") == "none"


# --- the wiring --------------------------------------------------------------------------------------------------------
def test_the_view_s_click_goes_to_the_pick_first_and_esc_stops_it():
    src = open(JS).read()
    up = src[src.index("renderer.domElement.addEventListener('pointerup'"):]
    up = up[:up.index("\n});")]
    assert "if (S.scenPick) { pickScenarioFace(scenHit(e)); return; }" in up
    assert up.index("pickScenarioFace") < up.index("choose(e, hit)")                 # before the chat's pick
    assert "if (e.key === 'Escape' && S.scenPick) { e.preventDefault(); stopScenPick('Stopped picking'); }" in src


def test_every_row_has_its_pick_and_a_support_says_it_doesn_t_move():
    src = open(JS).read()
    assert 'data-scen-pick="${i}"' in _fn(src, "scenarioRow")
    sup = _fn(src, "supportRow")
    assert 'data-sup-pick="${i}"' in sup and "doesn't move" in sup
    assert "if (s.floor) return" in sup and sup.index("if (s.floor) return") < sup.index("data-sup-pick")   # the floor has no box to pick


def test_the_picture_follows_the_rows_and_goes_with_the_editor():
    src = open(JS).read()
    rows = _fn(src, "wireScenarioRows")
    assert "body.oninput = () => drawScenarios();" in rows and "drawScenarios();" in rows
    assert "if (!box.open) { clearScenMarks(); if (S.scenPick) stopScenPick(); return; }" in _fn(src, "wireScenarios")
    assert "if (!scen || !scen.open) { clearScenMarks(); if (S.scenPick) stopScenPick(); }" in _fn(src, "renderInspector")
    draw = _fn(src, "drawScenarios")
    assert "readScenarios(got)" in draw and "if (!got || !box || !box.open || !S.design) return;" in draw


# --- #376 review -----------------------------------------------------------------------------------------------------------
def _three(body, names, head=""):
    src = open(JS).read()
    three = os.path.join(os.path.dirname(JS), "vendor", "three", "three.module.js")
    script = (f"import * as THREE from {json.dumps('file://' + three)};\n" + head + "".join(_fn(src, n) for n in names)
              + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_pick_finds_the_part_under_a_stress_map_that_hides_it():
    """Must-fix: with a check's stress map up only its picture is visible, and the pick said "no face there"."""
    got = _three("""const part = new THREE.Mesh(new THREE.BoxGeometry(100, 100, 100), new THREE.MeshBasicMaterial());
      part.userData = { partId: 'stool' }; part.visible = false; part.updateMatrixWorld(true);
      const meshes = new Map([['stool', part]]), pieces3d = new Map();
      globalThis.meshes = meshes; globalThis.pieces3d = pieces3d;
      const h = scenHit({ clientX: 100, clientY: 100 });
      return { part: h && h.object.userData.partId, x: h && Math.round(h.point.y) };""", ("scenHit",),
                 head="""const camera = new THREE.PerspectiveCamera(40, 1, 1, 10000); camera.position.set(0, -500, 0); camera.lookAt(0, 0, 0); camera.updateMatrixWorld();
const renderer = { domElement: { getBoundingClientRect: () => ({ left: 0, top: 0, width: 200, height: 200 }) } };
const ray = new THREE.Raycaster();
""")
    assert got == {"part": "stool", "x": -50}


def test_on_a_phone_a_pick_goes_to_the_model_and_back():
    got = _pick("""phone = true; startScenPick('stool', 'load', 0); const during = panes.slice();
                   await pickScenarioFace(hitOn('stool')); return { during, after: panes };""")
    assert got == {"during": ["view"], "after": ["view", "cards"]}
    assert _pick("startScenPick('stool', 'load', 0); await pickScenarioFace(hitOn('stool')); return panes;") == []   # a desktop stays


def test_a_reopened_editor_draws_again():
    """Should-fix 1: open 8 marks, closed 0, reopened 0 until a keystroke."""
    tog = _fn(open(JS).read(), "wireScenarios")
    assert "if ($('scenSave')) { drawScenarios(); return; }" in tog


def test_the_floor_is_in_the_part_s_own_frame_not_posed_twice():
    """Should-fix 3: the floor came from the posed bbox and was drawn under the pose again. A part moved 500 along x and
    turned 90° about z: its own box is back at the origin, and z is untouched."""
    got = _three("""const f = scenFrame({ position: [500, 0, 0], rotation: [0, 0, 90] });
      const posed = { min: [480, -40, 0], max: [520, 40, 10] };       // a 80 x 40 x 10 box, turned and moved
      return localBox(posed, f);""", ("scenFrame", "localBox"))
    assert got == {"min": [-40, -20, 0], "max": [40, 20, 10], "size": [80, 40, 10]}


def test_clearing_the_marks_lets_go_of_their_geometry_and_material():
    got = _three("""globalThis.scenMarks = new THREE.Group(); let g = 0, m = 0;
      for (let i = 0; i < 3; i++) { const geo = new THREE.BoxGeometry(1, 1, 1), mat = new THREE.MeshBasicMaterial();
        geo.dispose = () => { g += 1; }; mat.dispose = () => { m += 1; }; scenMarks.add(new THREE.Mesh(geo, mat)); }
      clearScenMarks(); return { g, m, left: scenMarks.children.length };""", ("clearScenMarks",))
    assert got == {"g": 3, "m": 3, "left": 0}
