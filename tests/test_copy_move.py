"""CALI-183 (#294, Theo's addition): Copy… and Move… on a part's menu, placed by a typed form.

Theo, 2026-11-14: "maybe a copy and move or specify a location to put the copy on". A move writes the part's pose in the
assembly and keeps where it was; a copy is a new part of its own from the part's script. Both are measured afterwards
against every other part. Real CadQuery boxes, no Claude call.
"""

import hashlib
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from caliper import follows, mirror, placing, tree, trash
from caliper.design import DesignStore

from .test_chat import _box
from .test_follows import STOOL, STRIP

pytest.importorskip("cadquery")


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from caliper.server import create_app

    s = DesignStore.create("two boxes", base=str(tmp_path / "designs"))
    s.write_part("a", _box(dx=40, dy=20), intent="box a")             # x -20..20, y -10..10, z -5..5
    s.write_part("b", _box(dx=40, dy=20, x=200), intent="box b")      # x 180..220
    return TestClient(create_app()), os.path.basename(str(s.root)), s


def _bounds(slug, pid):
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    return s.part_geometry(pid).require_mesh().bounds


def _post(c, slug, pid, what, body):
    return c.post(f"/api/designs/{slug}/parts/{pid}/{what}", json=body)


# --- Move… ----------------------------------------------------------------------------------------------------------------
def test_an_offset_moves_it_and_keeps_where_it_was(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", {"offset": [0, 50, 10]})
    assert r.status_code == 200, r.text
    lo, hi = _bounds(slug, "a")
    assert np.allclose(lo, [-20, 40, 5]) and np.allclose(hi, [20, 60, 15])
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    assert placing.pose(s, "a") == {"position": [0.0, 50.0, 10.0], "rotation": [0.0, 0.0, 0.0]}
    last = s.history("a")[-1]
    assert last["kind"] == "pose" and last["from"] == {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}
    assert s.design.part("a").version == 1                  # its script is as it was: no new version
    assert r.json()["said"].startswith("Moved a: 50 mm along y, 10 mm along z.")


def test_a_quarter_turn_turns_it_in_place(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", {"turn": {"axis": "z", "deg": 90}})
    assert r.status_code == 200, r.text
    lo, hi = _bounds(slug, "a")
    assert np.allclose(lo, [-10, -20, -5], atol=1e-6) and np.allclose(hi, [10, 20, 5], atol=1e-6)   # 20 by 40 now
    assert r.json()["to"]["rotation"] == [0.0, 0.0, 90.0]


def test_a_turn_about_its_middle_when_it_isn_t_at_the_origin(site):
    c, slug, _ = site
    _post(c, slug, "b", "move", {"turn": {"axis": "z", "deg": 90}})
    lo, hi = _bounds(slug, "b")
    assert np.allclose((lo + hi) / 2, [200, 0, 0], atol=1e-6) and np.allclose(hi - lo, [20, 40, 10], atol=1e-6)


def test_a_second_turn_is_about_the_design_s_axes_not_the_part_s(site):
    """Turned 90° about x (40 × 10 × 20), then 90° about z: about the design's z it's 10 × 40 × 20. About the part's own z
    (now the design's y) it would be 20 × 10 × 40."""
    c, slug, _ = site
    _post(c, slug, "a", "move", {"turn": {"axis": "x", "deg": 90}})
    _post(c, slug, "a", "move", {"turn": {"axis": "z", "deg": 90}})
    lo, hi = _bounds(slug, "a")
    assert np.allclose(hi - lo, [10, 40, 20], atol=1e-6) and np.allclose((lo + hi) / 2, [0, 0, 0], atol=1e-6)


def test_at_puts_the_middle_of_a_part_away_from_the_origin_there(site):
    c, slug, _ = site
    _post(c, slug, "b", "move", {"at": [0, 100, 50]})                 # b's middle starts at x 200
    lo, hi = _bounds(slug, "b")
    assert np.allclose((lo + hi) / 2, [0, 100, 50])


def test_at_puts_its_middle_there(site):
    c, slug, _ = site
    _post(c, slug, "a", "move", {"at": [100, 100, 100]})
    lo, hi = _bounds(slug, "a")
    assert np.allclose((lo + hi) / 2, [100, 100, 100])


def test_beside_puts_it_touching_on_that_side_and_says_so(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", {"beside": {"part": "b", "side": "+x"}})
    assert r.status_code == 200, r.text
    lo, hi = _bounds(slug, "a")
    assert np.isclose(lo[0], 220) and np.allclose([lo[1], lo[2]], [-10, -5])        # the other two stay
    assert [n["part"] for n in r.json()["near"]] == ["b"] and r.json()["near"][0]["kind"] == "touch"
    assert "Measured where it sits: it touches b." in r.json()["said"]


def test_beside_on_the_other_side_and_a_turn_together(site):
    c, slug, _ = site
    _post(c, slug, "a", "move", {"beside": {"part": "b", "side": "-x"}, "turn": {"axis": "z", "deg": 90}})
    lo, hi = _bounds(slug, "a")
    assert np.isclose(hi[0], 180) and np.isclose(hi[0] - lo[0], 20)


def test_an_overlap_is_said_with_its_size(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", {"offset": [190, 0, 0]})         # a: 170..210, over b's 180..220
    near = r.json()["near"]
    assert near[0]["kind"] == "overlap" and near[0]["part"] == "b" and abs(near[0]["mm3"] - 30 * 20 * 10) < 5
    assert "it overlaps b by 6.0 cm³" in r.json()["said"]


def test_far_from_everything_it_says_nothing_met(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", {"offset": [0, 500, 0]})
    assert r.json()["near"] == [] and "it doesn't touch or overlap another part" in r.json()["said"]


def test_put_it_back_returns_it(site):
    c, slug, _ = site
    was = _post(c, slug, "a", "move", {"offset": [0, 50, 0], "turn": {"axis": "x", "deg": 180}}).json()["from"]
    r = _post(c, slug, "a", "move", {"to": was})
    assert r.status_code == 200 and r.json()["said"].startswith("Put a back where it was.")
    lo, hi = _bounds(slug, "a")
    assert np.allclose(lo, [-20, -10, -5]) and np.allclose(hi, [20, 10, 5])
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    assert [h["action"] for h in s.history("a") if h["kind"] == "pose"] == ["move", "put back"]


def test_the_words_are_in_the_design_s_units(site):
    c, slug, s = site
    c.patch(f"/api/designs/{slug}", json={"display_units": "in"})
    r = _post(c, slug, "a", "move", {"offset": [25.4, 0, 0]})
    assert r.json()["said"].startswith("Moved a: 1 in along x.")


@pytest.mark.parametrize("body,word", [
    ({}, "leaves it where it is"), ({"offset": [0, 0, 0]}, "leaves it where it is"),
    ({"turn": {"axis": "z", "deg": 0}}, "leaves it where it is"), ({"offset": [1, 2]}, "three numbers"),
    ({"offset": [1, 0, 0], "at": [0, 0, 0]}, "one of where"), ({"at": [0, 0, 1e9]}, "100 m"),
    ({"beside": {"part": "b", "side": "up"}}, "+x, -x"), ({"beside": {"part": "zz", "side": "+x"}}, "no part 'zz'"),
    ({"beside": {"part": "a", "side": "+x"}}, "beside itself"), ({"turn": {"axis": "z", "deg": 45}}, "0, 90, 180 or 270"),
    ({"turn": {"axis": "w", "deg": 90}}, "x, y or z")])
def test_a_placement_that_can_t_be_is_refused_in_words_and_moves_nothing(site, body, word):
    c, slug, _ = site
    r = _post(c, slug, "a", "move", body)
    assert r.status_code == 422 and word in r.json()["detail"], r.text
    lo, _ = _bounds(slug, "a")
    assert np.allclose(lo, [-20, -10, -5])


def test_a_mirror_and_its_source_aren_t_moved_alone(site):
    c, slug, s = site
    mirror.make(s, "a", "b")
    for pid, word in (("a", "it mirrors b"), ("b", "a mirrors it")):
        r = _post(c, slug, pid, "move", {"offset": [0, 10, 0]})
        assert r.status_code == 409 and word in r.json()["detail"] and "break the mirror" in r.json()["detail"].lower()


def test_a_move_while_a_job_works_on_it_is_refused(site, monkeypatch):
    from caliper import design_api

    c, slug, _ = site
    monkeypatch.setattr(design_api, "_refuse_while_busy", lambda slug, parts: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(409, f"{parts[0]} is being checked: wait for it, or stop that first.")))
    for what in ("move", "copy"):
        r = _post(c, slug, "a", what, {"offset": [0, 10, 0]})
        assert r.status_code == 409 and "being checked" in r.json()["detail"]


def test_an_unknown_part_is_a_404(site):
    c, slug, _ = site
    assert _post(c, slug, "zz", "move", {"offset": [1, 0, 0]}).status_code == 404
    assert _post(c, slug, "zz", "copy", {}).status_code == 404


def test_the_chat_log_says_both(site):
    c, slug, s = site
    _post(c, slug, "a", "move", {"offset": [0, 50, 0]})
    _post(c, slug, "a", "copy", {})
    log = [e for e in DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"]).log() if e.get("routed_by") == "menu"
           or e.get("action") in ("move", "copy")]
    said = [(e["kind"], e.get("text") or e.get("reply")) for e in log]
    assert ("message", "Move a: 50 mm along y (from its menu)") in said and ("message", "Copy a (from its menu)") in said
    assert any(k == "reply" and t.startswith("Copied a as a_2") for k, t in said)


# --- Copy… ----------------------------------------------------------------------------------------------------------------
def _hash(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def test_a_copy_is_a_new_part_beside_the_original_and_the_original_is_untouched(site):
    c, slug, s = site
    before = _hash(s.script_path("a"))
    r = _post(c, slug, "a", "copy", {})
    assert r.status_code == 200, r.text
    assert r.json()["part"] == "a_2"
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    assert s.read_script("a_2") == s.read_script("a") and _hash(s.script_path("a")) == before
    assert s.design.part("a").version == 1 and s.design.part("a_2").version == 1
    lo, _ = _bounds(slug, "a_2")
    assert np.isclose(lo[0], 20)                            # beside a on +x, touching
    assert tree.layout(s)["order"] == ["a", "a_2", "b"]     # in the tree beside its original
    h = s.history("a_2")[-1]
    assert h["action"] == "copy" and h["copied_from"] == "a"
    assert "It's a part of its own: say \"make a_2 a mirror of a\"" in r.json()["said"]


def test_a_copy_of_a_copy_takes_the_next_number_and_one_in_the_trash_keeps_its_own(site):
    c, slug, s = site
    _post(c, slug, "a", "copy", {})
    trash.remove(DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"]), "a_2")
    assert _post(c, slug, "a", "copy", {"offset": [0, 100, 0]}).json()["part"] == "a_3"
    assert _post(c, slug, "a_3", "copy", {"offset": [0, 200, 0]}).json()["part"] == "a_4"


def test_a_named_part_s_copy_is_named_too_and_an_unnamed_one_reads_its_id(site):
    _, _, s = site
    s.design.part("a").label = "Step stool"
    s.save()
    assert s.design.part(placing.copy(s, "a", {})["part"]).label == "Step stool 2"
    assert s.design.part(placing.copy(s, "b", {})["part"]).label is None


def test_a_copy_placed_and_turned(site):
    c, slug, _ = site
    r = _post(c, slug, "a", "copy", {"at": [0, 300, 0], "turn": {"axis": "z", "deg": 90}})
    lo, hi = _bounds(slug, r.json()["part"])
    assert np.allclose((lo + hi) / 2, [0, 300, 0]) and np.allclose(hi - lo, [20, 40, 10], atol=1e-6)
    assert r.json()["near"] == []


def test_a_bad_placement_writes_no_copy(site):
    c, slug, s = site
    r = _post(c, slug, "a", "copy", {"beside": {"part": "zz", "side": "+x"}})
    assert r.status_code == 422
    assert [p.id for p in DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"]).design.parts] == ["a", "b"]


def test_a_copy_of_a_mirror_is_its_own_shape_and_mirrors_nothing(site):
    c, slug, s = site
    mirror.make(s, "a", "b")
    r = _post(c, slug, "a", "copy", {"offset": [0, 300, 0]})
    assert r.status_code == 200, r.text
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    assert mirror.source_of(s, "a_2") is None and mirror.mirrors_of(s, "b") == ["a"]
    copied, orig = _bounds(slug, "a_2"), _bounds(slug, "a")
    assert np.allclose(copied[0] - [0, 300, 0], orig[0]) and np.allclose(copied[1] - [0, 300, 0], orig[1])   # a's shape


def test_a_copy_follows_nothing_and_keeps_its_numbers(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", STOOL, intent="a side and a step")
    s.write_part("inside_fillets", STRIP, intent="fillet strips under the step")
    got = placing.copy(s, "inside_fillets", {"offset": [0, 300, 0]})
    assert follows.declared(s.read_script(got["part"])) == {}
    assert "PARAMS = {\"r\": 5.0, \"stool_h\": 406.4, \"ply_t\": 19.05}" in s.read_script(got["part"])
    assert follows.followers_of(s, "stool") == ["inside_fillets"]


def test_a_copy_keeps_the_loads_as_edited_and_its_piece_names(site):
    _, _, s = site
    s.design.scenarios["a"] = {"scenarios": [{"name": "a person", "force_n": 1000}]}
    s.design.piece_labels["a"] = {"top": "lid"}
    s.save()
    new = placing.copy(s, "a", {})["part"]
    s.design.scenarios["a"]["scenarios"][0]["force_n"] = 5                  # its own copy, not the original's, in memory
    s.design.piece_labels["a"]["top"] = "changed"
    assert s.design.scenarios[new]["scenarios"][0]["force_n"] == 1000 and s.design.piece_labels[new] == {"top": "lid"}
    s.design.scenarios["a"]["scenarios"][0]["force_n"] = 1000
    s.design.piece_labels["a"]["top"] = "lid"
    s.save()
    s = DesignStore.load(s.root)
    assert s.design.scenarios[new] == {"scenarios": [{"name": "a person", "force_n": 1000}]}
    assert s.design.piece_labels[new] == {"top": "lid"}
    assert s.design.scenarios[new]["scenarios"][0]["force_n"] == 1000


def test_a_reference_s_copy_is_a_reference(site):
    c, slug, s = site
    c.patch(f"/api/designs/{slug}/parts/b", json={"role": "fixed"})
    r = _post(c, slug, "b", "copy", {"offset": [0, 300, 0]})
    s = DesignStore.load(slug, base=os.environ["CALIPER_DESIGNS"])
    assert next(p for p in s.assembly.parts if p.id == r.json()["part"]).role == "fixed"


def test_own_script_drops_follows_and_a_mirror_s_mark():
    assert "FOLLOWS = {}" in placing.own_script(STRIP) and follows.declared(placing.own_script(STRIP)) == {}
    flipped = mirror.script("b", _box(), "YZ", (0, 0, 0), "a")
    assert mirror.of(placing.own_script(flipped)) is None


# --- the page: Copy… and Move… on the menu, and their form ------------------------------------------------------------------
JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

_FORM = """
const IN = 25.4; let inch = false; const inches = () => inch;
function el(attrs, value) { return { value, ...attrs }; }
function form(way, vals) {                // a stand-in for the form: the boxes as placeHtml names them
  const said = { textContent: '' }, go = { disabled: false };
  const boxes = { 'data-off': (vals.off || [0, 0, 0]).map((v) => el({}, String(v))), 'data-at': (vals.at || [0, 0, 0]).map((v) => el({}, String(v))) };
  const one = { '[data-beside]': el({}, vals.part || 'a'), '[data-side]': el({}, vals.side || '+x'), '[data-deg]': el({}, String(vals.deg || 0)),
    '[data-axis]': el({}, vals.axis || 'z'), 'input[name="way"]:checked': el({}, way), '[data-place-said]': said, 'button[type="submit"]': go };
  return { dataset: { place: vals.kind || 'move' }, said, go,
    querySelector: (q) => one[q], querySelectorAll: (q) => boxes[/\\[(.*)\\]/.exec(q)[1]] };
}
"""


def _page(body, design=None):
    import json
    import re
    import subprocess

    from .test_carve_click import _fn, _node
    from .test_part_menu import _DESIGN, _STUBS

    src = open(JS).read()
    names = ("seen", "keepTree", "underPart", "treeRows", "nudge", "menuItems", "placeHtml", "placeBody", "place")   # Move in the tree ▸ (#360)
    extra = "".join(re.search(rf"^const {c} = .*$", src, re.M).group(0) + "\n" for c in ("SIDES", "TREE_KEYS"))
    script = (_STUBS.replace("DESIGN", design or _DESIGN) + _FORM + extra + "\n".join(_fn(src, n) for n in names)
              + f"\nconst out = await (async () => {{ {body} }})();\nconsole.log(JSON.stringify(out));")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_menu_has_copy_and_move_and_a_mirror_s_move_is_greyed_with_why():
    got = _page("""const ids = (pid) => menuItems(S.design, pid, null);
                   S.design.parts.push({ id: 'side_right', name: 'side_right', role: 'part', version: 1, pieces: [] });
                   return { stool: ids('step_stool'), mirror: ids('side_left'), source: ids('side_right'), piece: menuItems(S.design, 'step_stool', 'top') };""")
    ids = [i["id"] for i in got["stool"]]
    assert ids.index("copy") + 1 == ids.index("move") and ids.index("move") < ids.index("versions")
    assert not next(i for i in got["stool"] if i["id"] == "move").get("off")
    mv = next(i for i in got["mirror"] if i["id"] == "move")
    assert mv["off"] and mv["why"] == "it mirrors side_right: move that, or break the mirror first"
    src = next(i for i in got["source"] if i["id"] == "move")
    assert src["off"] and src["why"] == "side_left mirrors it and wouldn't follow: break the mirror first"
    assert "copy" in [i["id"] for i in got["mirror"]]                    # a copy of a mirror is its own part
    assert not {"copy", "move"} & {i["id"] for i in got["piece"]}


def test_the_form_starts_beside_the_original_for_a_copy_and_along_for_a_move():
    got = _page("""S.design.parts[0].bbox = { min: [0, 0, 0], max: [254, 50.8, 25.4] }; inch = true;
                   return { copy: placeHtml(S.design, 'step_stool', 'copy'), move: placeHtml(S.design, 'step_stool', 'move') };""")
    assert 'aria-label="Along x, in inches"' in got["move"] and ">Cancel<" in got["move"]
    assert 'value="beside" checked' in got["copy"] and "Step stool (the original)" in got["copy"] and "Copy it" in got["copy"]
    assert 'value="offset" checked' in got["move"] and "(the original)" not in got["move"] and "Move it" in got["move"]
    assert "Where, in in" in got["move"] and 'data-at="0" value="5"' in got["move"] and 'data-at="2" value="0.5"' in got["move"]
    assert "<option value=\"-z\">below (−z)</option>" in got["move"] and "270°" in got["move"]


@pytest.mark.parametrize("way,vals,inch,body", [
    ("offset", {"off": [1, 0, 2]}, "true", {"offset": [25.4, 0, 50.8]}),
    ("offset", {"off": [10, "", 0]}, "false", {"offset": [10, 0, 0]}),
    ("at", {"at": [0, 300, 5]}, "false", {"at": [0, 300, 5]}),
    ("beside", {"part": "car", "side": "-y"}, "false", {"beside": {"part": "car", "side": "-y"}}),
    ("offset", {"off": [0, 50, 0], "deg": 90, "axis": "x"}, "false", {"offset": [0, 50, 0], "turn": {"axis": "x", "deg": 90}})])
def test_the_form_is_sent_in_mm(way, vals, inch, body):
    import json

    assert _page(f"inch = {inch}; return placeBody(form('{way}', {json.dumps(vals)}));") == body


def test_a_box_that_isn_t_a_number_is_said_in_the_form_and_nothing_is_sent():
    got = _page("""const f = form('offset', { off: ['two', 0, 0] }); const b = placeBody(f); await place(f);
                   return { b, said: f.said.textContent, posted };""")
    assert got == {"b": None, "said": "x, y and z are numbers.", "posted": []}


def test_while_it_works_the_form_says_so():
    got = _page("""S.menu = { pid: 'step_stool' }; let saw; answer = new Error('no');
                   const f = form('offset', { off: [0, 5, 0] }); const going = place(f); saw = f.said.textContent; await going;
                   return { saw };""")
    assert got["saw"] == "Moving, then measuring where it lands…"


def test_a_move_posts_closes_and_offers_put_back_and_a_refusal_stays_in_the_form():
    got = _page("""S.menu = { pid: 'step_stool' };
                   answer = { said: 'Moved step_stool: 50 mm along y.', from: { position: [0, 0, 0], rotation: [0, 0, 0] }, state: S.design };
                   const f = form('offset', { off: [0, 50, 0] });
                   await place(f);
                   const did = calls.slice(); calls.length = 0;
                   S.menu = { pid: 'step_stool' }; answer = new Error("I can't move step_stool on its own: …"); const g = form('offset', { off: [0, 5, 0] });
                   await place(g);
                   return { posted, did, refused: g.said.textContent, again: g.go.disabled, after: calls };""")
    assert got["posted"][0] == ["POST", "/api/designs/step-stool-5/parts/step_stool/move", {"offset": [0, 50, 0]}]
    assert "close" in got["did"] and "render" in got["did"] and ["say", "Moved step_stool: 50 mm along y."] in got["did"]
    assert "sync" in got["did"]
    assert got["refused"] == "I can't move step_stool on its own: …" and got["again"] is False and "close" not in got["after"]


def test_a_copy_selects_the_new_part():
    got = _page("""S.menu = { pid: 'step_stool' }; answer = { part: 'step_stool_2', said: 'Copied step_stool as step_stool_2, beside it.', state: S.design };
                   const f = form('beside', { kind: 'copy', part: 'step_stool' }); await place(f); return { posted, calls };""")
    assert got["posted"][0][1].endswith("/parts/step_stool/copy") and got["posted"][0][2] == {"beside": {"part": "step_stool", "side": "+x"}}
    assert ["scope", "step_stool_2", None] in got["calls"]


def test_the_form_is_wired_and_its_boxes_keep_their_arrow_keys():
    src = open(JS).read()
    assert "box.addEventListener('submit', (e) => { e.preventDefault(); place(e.target); });" in src
    assert "if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !field)" in src
    assert "if (id === 'copy' || id === 'move') {" in src


def test_a_moved_part_is_drawn_again_though_its_version_is_the_same(site):
    c, slug, _ = site
    before = c.get(f"/api/designs/{slug}").json()["parts"][0]
    _post(c, slug, "a", "move", {"offset": [0, 50, 0]})
    after = c.get(f"/api/designs/{slug}").json()["parts"][0]
    assert before["version"] == after["version"] and before["drawn"] != after["drawn"] and before["stl_url"] != after["stl_url"]
    # one pose, #389's two keys: the overlays (partPose) and Move… read the same place (#374 folded onto #375's keys)
    assert (after["position"], after["rotation"]) == ([0.0, 50.0, 0.0], [0.0, 0.0, 0.0]) and "pose" not in after
    assert before["drawn"] == "1"                          # a part never moved keys as it always did
    src = open(JS).read()
    assert "have.userData.drawn === (p.drawn ?? p.version)" in src
    assert "(want.get(pid).drawn ?? want.get(pid).version) !== (s.drawn ?? s.version)" in src


def test_a_pick_from_before_a_move_is_dropped_and_its_faces_asked_again():
    """A Move… keeps the version, so the pick's cache and the old pick key on where it sits too."""
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    head = ("let hint = null, cleared = 0; const pickHint = (t) => { hint = t; }; const clearPick = () => { cleared += 1; S.pick = null; };\n"
            "const S = { design: { parts: [{ id: 'a', version: 3, drawn: '3-abc' }] }, pick: { part: 'a', version: 3, drawn: '3' } };\n")
    body = ("dropOldPick(); const moved = { hint, cleared };"
            "S.pick = { part: 'a', version: 3, drawn: '3-abc' }; hint = null; dropOldPick(); const same = { hint, kept: !!S.pick };"
            "S.pick = { part: 'a', version: 2, drawn: '2' }; dropOldPick(); console.log(JSON.stringify({ moved, same, rebuilt: hint }));")
    got = subprocess.run([_node(), "-e", head + _fn(src, "dropOldPick") + body], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"moved": {"hint": "Moved: click it again", "cleared": 1}, "same": {"hint": None, "kept": True},
                                      "rebuilt": "Rebuilt: click it again"}
    assert "key = `${pickKey(pid, part.drawn ?? part.version)}/${S.design.display_units}`" in src


def test_a_moved_part_s_pieces_are_drawn_again_and_an_unmoved_one_s_aren_t():
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = """let S = { slug: 'a', design: null }, loads = 0, drops = [];
const pieces3d = new Map([['p', { version: 3, drawn: '3', byKey: new Map() }], ['q', { version: 2, drawn: '2', byKey: new Map() }]]), noPieces = new Map();
const dropPieces = (p) => { pieces3d.delete(p); drops.push(p); }, scene = { add() {} }, plainly = (m) => m, renderTree = () => {};
let piecesOf = 'a';
async function loadPieces() { loads += 1; return new Map(); }
""" + _fn(src, "syncPieces") + """
const design = { parts: [{ id: 'p', version: 3, drawn: '3-abc', role: 'part', pieces: [{ key: 'a' }] },
                         { id: 'q', version: 2, drawn: '2', role: 'part', pieces: [{ key: 'a' }] }] };
S.design = design;
(async () => { await syncPieces(design); console.log(JSON.stringify({ loads, drops, now: pieces3d.get('p').drawn })); })();"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"loads": 1, "drops": ["p", "p"], "now": "3-abc"}
