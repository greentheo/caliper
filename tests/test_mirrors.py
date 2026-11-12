"""CALI-161 (#239) — mirrored parts: one script, flipped.

Theo's step-stool-4 (2026-11-11): the sides weren't mirrors (walls 15 against 12 mm, another pocket depth, a boss
against a pad), and the designer spent a full try writing a part that's a flip. Stubbed models only: no live call."""

import pytest

from caliper import construction as C
from caliper import mirror
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: The right side of a stool 400 mm wide: a 19 mm panel at x 381..400, a pocket for the stretcher on its inner face, a
#: boss on its outer face (so a mirror that's wrong shows), and its panel declared.
RIGHT = '''import cadquery as cq

PARAMS = {"t": 19.0, "w": 400.0, "d": 300.0, "h": 400.0}
HOLES = [{"piece": "side panel", "normal": [1, 0, 0], "depth": 19.0,
          "polygons": [[[400, 140, 300], [400, 160, 300], [400, 160, 320], [400, 140, 320]]]}]


def build(params):
    p = {**PARAMS, **(params or {})}
    side = cq.Workplane("XY").box(p["t"], p["d"], p["h"]).translate((p["w"] - p["t"] / 2, p["d"] / 2, p["h"] / 2))
    pocket = cq.Workplane("XY").box(10, 19.6, 102.2).translate((p["w"] - p["t"] + 5, p["d"] / 2, 100))
    boss = cq.Workplane("XY").box(6, 40, 40).translate((p["w"] + 3, p["d"] / 2, 300))
    return side.cut(pocket).union(boss)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    x = p["w"]
    return [{"name": "side panel", "kind": "sheet", "material": "plywood", "thickness": p["t"],
             "outline": [(x, 0, 0), (x, p["d"], 0), (x, p["d"], p["h"]), (x, 0, p["h"])], "covers": ["paint", "paint"]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "a hand on the side", "lb": 20, "factor": 2.0, "lo": (p["w"] - 1, 100, 350), "hi": (p["w"], 200, 400)}]
'''
LEFT_V1 = RIGHT.replace('"w": 400.0', '"w": 19.0').replace("p[\"w\"] - p[\"t\"] / 2", "p[\"t\"] / 2")


@pytest.fixture
def stool(tmp_path):
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("side_right", RIGHT, intent="the right side")
    s.write_part("side_left", LEFT_V1, intent="the left side")
    return s


def _vol(store, pid):
    return float(abs(store.part_geometry(pid).require_mesh().volume))


def test_a_mirror_is_its_source_flipped_and_its_volume_agrees(stool):
    """Its shape is the source's in the YZ plane half way between them: the volume agrees to 0.1%, the boss is on the
    outside of each, and the pocket faces in."""
    mirror.make(stool, "side_left", "side_right")
    m = stool.part_geometry("side_left").require_mesh()
    assert abs(_vol(stool, "side_left") - _vol(stool, "side_right")) <= 0.001 * _vol(stool, "side_right")
    lo, hi = m.bounds
    # the panel at x 6..25 (381..400 mirrored in x = 203), the boss outside it at 0..6
    assert lo[0] == pytest.approx(0.0, abs=0.01) and hi[0] == pytest.approx(25.0, abs=0.01)
    got = mirror.of(stool.read_script("side_left"))
    assert got["source"] == "side_right" and got["plane"] == "YZ" and got["at"][0] == pytest.approx(203.0, abs=0.1)


def test_its_pieces_holes_and_loads_are_the_source_s_mirrored(stool):
    mirror.make(stool, "side_left", "side_right")
    d = C.declared(stool, "side_left")
    (panel,) = d["construction"]
    assert {round(q[0], 3) for q in panel["outline"]} == {6.0}       # 400 mirrored in x = 203
    assert panel["thickness"] == 19.0                                    # a size is never flipped
    assert d["holes"][0]["normal"] == [-1.0, 0.0, 0.0]
    assert {round(q[0], 3) for q in d["holes"][0]["polygons"][0]} == {6.0}
    (load,) = d["loads"]
    assert load["lo"][0] < load["hi"][0]                                  # still low to high
    assert (round(load["lo"][0], 3), round(load["hi"][0], 3)) == (6.0, 7.0)


def test_it_costs_no_designer_and_its_own_script_is_kept(stool):
    v = mirror.make(stool, "side_left", "side_right")
    assert v == 2 and stool.design.part("side_left").intent == "a mirror of side_right"
    assert open(stool.version_dir("side_left", 1) + "/part.py").read() == LEFT_V1


def test_a_mirror_follows_its_source(stool):
    mirror.make(stool, "side_left", "side_right")
    stool.write_part("side_right", RIGHT.replace('"h": 400.0', '"h": 450.0'), intent="the right side, taller")
    assert stool.design.part("side_left").version == 3
    assert stool.part_geometry("side_left").require_mesh().bounds[1][2] == pytest.approx(450.0, abs=0.01)
    assert mirror.mirrors_of(stool, "side_right") == ["side_left"]


def test_a_mirror_of_a_mirror_is_refused(stool):
    mirror.make(stool, "side_left", "side_right")
    stool.write_part("side_extra", LEFT_V1, intent="another")
    with pytest.raises(ValueError, match="itself a mirror"):
        mirror.make(stool, "side_extra", "side_left")


def test_breaking_a_mirror_keeps_its_shape_and_stops_following(stool):
    mirror.make(stool, "side_left", "side_right")
    before = _vol(stool, "side_left")
    mirror.unmirror(stool, "side_left")
    assert mirror.source_of(stool, "side_left") is None and _vol(stool, "side_left") == pytest.approx(before, rel=1e-6)
    stool.write_part("side_right", RIGHT.replace('"h": 400.0', '"h": 450.0'))
    assert stool.part_geometry("side_left").require_mesh().bounds[1][2] == pytest.approx(400.0, abs=0.01)


# --- in the chat -------------------------------------------------------------------------------------------------------
def _no_designer(spec, feedback, prior):
    raise AssertionError("a mirror costs no designer call")


@pytest.mark.parametrize("message", ["let's choose the right side (the one without the hole) to use for both sides",
                                     "use the right side for both", "make side_left a mirror of side_right",
                                     "mirror the right side onto the left side"])
def test_one_side_for_both_swaps_it_in_one_round(stool, message):
    """Theo's words on today's v1: side_left becomes side_right's mirror, with no designer, its own script kept."""
    from caliper import chat

    res = chat.turn(stool, message, use_llm=False, author=_no_designer)
    assert res.action == "mirror" and res.part == "side_left"
    assert mirror.source_of(stool, "side_left") == "side_right"
    assert res.reply.startswith("**side_left** is now a mirror of side_right (v2)") and "kept as v1" in res.reply
    assert "a change to either changes both" in res.reply


def test_an_edit_asked_of_the_mirror_goes_to_its_source(stool):
    from caliper import chat

    mirror.make(stool, "side_left", "side_right")
    taller = RIGHT.replace('"h": 400.0', '"h": 450.0')
    res = chat.turn(stool, "make it 50 mm taller", scope="side_left", use_llm=False,
                    author=lambda spec, feedback, prior: taller if prior == RIGHT else _no_designer(spec, feedback, prior))
    assert res.reply.startswith("side_left mirrors side_right: I changed side_right, and side_left follows it (v3).")
    assert stool.design.part("side_right").version == 2
    assert stool.part_geometry("side_left").require_mesh().bounds[1][2] == pytest.approx(450.0, abs=0.01)


@pytest.mark.parametrize("message", ["make the left one different", "stop mirroring the left side", "unmirror side_left"])
def test_breaking_the_mirror_in_words(stool, message):
    from caliper import chat

    mirror.make(stool, "side_left", "side_right")
    res = chat.turn(stool, message, use_llm=False, author=_no_designer)
    assert res.action == "mirror" and mirror.source_of(stool, "side_left") is None
    assert "its own part now" in res.reply and "no longer follows side_right" in res.reply


# --- in the plan --------------------------------------------------------------------------------------------------------
def test_the_plan_makes_a_mirror_by_flipping_it_after_its_source(tmp_path):
    """A plan's mirror is built from its source, after it, with no designer; the planner is told to set it."""
    from caliper import build_plan
    from caliper import plan as P

    assert "mirror_of that part" in P.SYSTEM
    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    plan = P.validate({"parts": [{"id": "side_left", "what": "the left side", "mirror_of": "side_right",
                                  "mirror_plane": "YZ", "mirror_at": [203, 0, 0]},
                                 {"id": "side_right", "what": "the right side"}]})
    assert P.order(plan) == ["side_right", "side_left"]
    P.save(store, plan, status="review")
    calls = []

    def author(spec, feedback, prior):
        calls.append(spec.part)
        return RIGHT
    got = build_plan.build(store, {}, lambda *a, **k: None, author=author, use_llm=False)
    assert calls == ["side_right"] and got["plan"] == "built"
    assert mirror.source_of(store, "side_left") == "side_right"
    assert store.part_geometry("side_left").require_mesh().bounds[0][0] == pytest.approx(0.0, abs=0.01)


@pytest.mark.parametrize("parts,why", [
    ([{"id": "a", "what": "x", "mirror_of": "nope"}], "isn't another part of the plan"),
    ([{"id": "a", "what": "x", "mirror_of": "a"}], "isn't another part of the plan"),
    ([{"id": "a", "what": "x"}, {"id": "b", "what": "x", "mirror_of": "a"}, {"id": "c", "what": "x", "mirror_of": "b"}],
     "which is itself a mirror"),
])
def test_a_plan_s_bad_mirror_is_refused(parts, why):
    from caliper import plan as P

    with pytest.raises(P.PlanError, match=why):
        P.validate({"parts": parts})


# --- what it says when it's made ---------------------------------------------------------------------------------------
def test_its_pattern_says_to_flip_the_template(stool):
    from caliper import patterns

    mirror.make(stool, "side_left", "side_right")
    (pc,) = patterns.pieces(stool, "side_left")
    assert pc["seen"].endswith("; a mirror of side_right: flip its template") and pc["mirror_of"] == "side_right"
    assert "a mirror of side_right: flip its template" in patterns.titles(pc)["full"]
    assert "mirror" not in patterns.pieces(stool, "side_right")[0]["seen"]


# --- #239 addendum: a mirror check measures the mirror -------------------------------------------------------------------
def test_mirrors_measures_the_mirror_not_the_bounding_boxes(stool):
    """Today's v1 sides have the same bounding-box sides but aren't mirrors (the boss is on the inner face of the left);
    a made mirror measures 0."""
    from caliper import measure

    off = measure.mirror_off(stool.part_geometry("side_left"), stool.part_geometry("side_right"))
    assert off > 5.0                                          # mm: the boss on the wrong face
    mirror.make(stool, "side_left", "side_right")
    assert measure.mirror_off(stool.part_geometry("side_left"), stool.part_geometry("side_right"), "yz") < measure.MIRROR_MM


def test_mirrors_is_an_expression_a_design_check_can_use(stool):
    from caliper.assembly import Assembly, evaluate_assembly
    from caliper.spec import Assertion

    asm = Assembly(name="s", parts=stool.assembly.parts, assertions=[
        Assertion(id="left_mirrors_right", expr='mirrors(side_left, side_right, "yz") <= 0.2')])
    (r,) = evaluate_assembly(asm, base_dir=stool.root).results
    assert r.status == "fail" and r.actual > 5.0
    mirror.make(stool, "side_left", "side_right")
    (r,) = evaluate_assembly(asm, base_dir=stool.root).results
    assert r.status == "pass"


@pytest.mark.parametrize("aid,expr,flagged", [
    ("side_left_mirrors_side_right", "-0.1 <= bbox(side_left).dx - bbox(side_right).dx <= 0.1", True),
    ("sides_symmetric", "bbox(side_left).dz == bbox(side_right).dz", True),
    ("left_identical_to_right", "bbox(side_left).dx >= 1", True),
    ("left_same_as_right", "bbox(side_left).dx >= 1", True),
    ("side_left_mirrors_side_right", 'mirrors(side_left, side_right, "yz") <= 0.2', False),
    ("side_left_same_size_as_side_right", "bbox(side_left).dx == bbox(side_right).dx", False),
    ("holes_match_bolt", "holes_aligned(side_left, side_right)", False),
])
def test_a_check_named_for_a_mirror_has_to_measure_one(aid, expr, flagged):
    from caliper import promote

    assert bool(promote.overclaims(aid, expr, ["side_left", "side_right"])) is flagged


def test_promote_never_offers_a_check_named_greener_than_it_measures(stool):
    from caliper import promote

    got = promote._candidate(stool, "side_left_mirrors_side_right",
                             "-0.1 <= bbox(side_left).dx - bbox(side_right).dx <= 0.1", "design", "side_left", "mirror it")
    assert got.proposal is None and "mirrors(a, b, plane) does" in got.reason
    assert 'mirrors(a, b, "yz")' in promote._DRAFT_SYSTEM and "never a comparison of" in promote._DRAFT_SYSTEM


def test_the_locked_check_stays_and_the_reply_says_what_it_measures(stool):
    """Theo's locked test is kept as he took it; the next reply that measures the design says what mirrors() says."""
    from caliper import chat
    from caliper.spec import Assertion

    stool.assembly.assertions.append(Assertion(
        id="side_left_mirrors_side_right",
        expr="-0.1 <= (bbox(side_left).dx + bbox(side_left).dy + bbox(side_left).dz) - "
             "(bbox(side_right).dx + bbox(side_right).dy + bbox(side_right).dz) <= 0.1"))
    stool.save()
    lines = chat._overclaimed(stool)
    assert len(lines) == 1 and lines[0].startswith("⚠ side_left_mirrors_side_right compares only overall size; "
                                                   "mirrors() says their surfaces are up to ")
    assert any(a.id == "side_left_mirrors_side_right" for a in stool.assembly.assertions)


def test_a_mirror_s_own_script_can_t_be_mirrored(stool):
    """Mutant 4: the script itself refuses a mirror of a mirror, not only make()."""
    mirror.make(stool, "side_left", "side_right")
    with pytest.raises(ValueError, match="itself a mirror"):
        mirror.script("side_left", stool.read_script("side_left"), "YZ", (0, 0, 0))


def test_the_plane_is_across_the_axis_the_two_are_apart_on(tmp_path):
    """Mutant 5: a front and a back panel are apart in y: the plane is XZ, half way between them."""
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    panel = ('import cadquery as cq\n\ndef build(params):\n    p = cq.Workplane("XY").box(300, 19, 200).translate((0, {y}, 100))\n'
             '    return p.union(cq.Workplane("XY").box(40, 6, 40).translate((100, {y} + {o}, 150)))\n')
    s.write_part("panel_front", panel.format(y=0, o=-12.5), intent="the front")
    s.write_part("panel_back", panel.format(y=400, o=12.5), intent="the back")
    mirror.make(s, "panel_back", "panel_front")
    got = mirror.of(s.read_script("panel_back"))
    assert got["plane"] == "XZ" and got["at"][1] == pytest.approx(200.0, abs=0.1)
    assert s.part_geometry("panel_back").require_mesh().bounds[1][1] == pytest.approx(415.5, abs=0.01)


def test_a_part_not_built_yet_isn_t_mirrored_in_the_chat(stool):
    """Mutant 9: under a plan's review the parts aren't built; the plan edit mirrors them, not this."""
    from caliper import chat

    stool.design.part("side_left").version = 0       # planned, not built
    stool.save()
    assert chat._mirror_said(stool, "use the right side for both", None) is None


# --- #246 review --------------------------------------------------------------------------------------------------------
def test_a_parameters_edit_on_a_mirror_goes_to_its_source_and_isn_t_lost(stool):
    """Item 1, seen on the page: side_left's leg width set by hand, then side_right changed, and side_left's edit was undone."""
    from caliper import params

    mirror.make(stool, "side_left", "side_right")
    got = params.set_values(stool, "side_left", [{"name": "h", "value": 450}])
    assert got["said"].startswith("side_left mirrors side_right: I changed side_right, and side_left follows it.")
    assert mirror.source_of(stool, "side_left") == "side_right"
    stool.write_part("side_right", stool.read_script("side_right").replace('"d": 300.0', '"d": 320.0'))
    top = stool.part_geometry("side_left").require_mesh().bounds[1][2]
    assert top == pytest.approx(450.0, abs=0.01)                # the edit stands: it was made on the source


def test_nothing_writes_a_mirror_s_own_script_but_its_source(stool):
    mirror.make(stool, "side_left", "side_right")
    edited = stool.read_script("side_left").replace('"h": 400.0', '"h": 300.0')
    with pytest.raises(ValueError, match="that would be undone the next time side_right changes: side_left mirrors "
                                         "side_right: change side_right and side_left follows it, or break the mirror first"):
        stool.write_part("side_left", edited, action="carve")


@pytest.mark.parametrize("how", ["carve", "picture"])
def test_a_carve_or_a_picture_on_a_mirror_is_refused_with_the_way_out(stool, how):
    from caliper import chat

    mirror.make(stool, "side_left", "side_right")
    res = (chat.carve_part(stool, "side_left") if how == "carve" else chat.picture_part(stool, "side_left", "heart"))
    assert not res.ok and "side_left mirrors side_right" in res.reply and "break the mirror first" in res.reply
    assert stool.design.part("side_left").version == 2


def test_no_mirror_of_a_mirror_from_the_source_s_end(stool):
    """Item 2: side_left mirrors side_right; side_right can't now become another part's mirror."""
    mirror.make(stool, "side_left", "side_right")
    stool.write_part("side_extra", RIGHT.replace('"w": 400.0', '"w": 600.0'), intent="another")
    with pytest.raises(ValueError, match="side_right has a mirror, side_left: break that first, or make side_left a "
                                         "mirror of side_extra too"):
        mirror.make(stool, "side_right", "side_extra")


def test_a_cycle_names_both_parts(stool):
    from caliper import plan as P

    mirror.make(stool, "side_left", "side_right")
    with pytest.raises(ValueError, match="side_right and side_left are already one script: side_left mirrors side_right"):
        mirror.make(stool, "side_right", "side_left")
    with pytest.raises(P.PlanError, match="'a' and 'b' each mirror the other: one of them has to be the source"):
        P.validate({"parts": [{"id": "a", "what": "x", "mirror_of": "b"}, {"id": "b", "what": "x", "mirror_of": "a"}]})


def test_asking_again_writes_nothing(stool):
    from caliper import chat

    mirror.make(stool, "side_left", "side_right")
    res = chat.turn(stool, "use the right side for both", use_llm=False, author=_no_designer)
    assert res.reply.startswith("**side_left** already mirrors side_right: nothing to change.")
    assert stool.design.part("side_left").version == 2


PANEL = 'import cadquery as cq\n\ndef build(params):\n    return cq.Workplane("XY").box({dx}, {dy}, {dz}).translate(({x}, {y}, {z}))\n'


@pytest.fixture
def box(tmp_path):
    """A box of five panels: top, bottom, left, right and back."""
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    for pid, dims in {"panel_top": (400, 300, 19, 0, 0, 300), "panel_bottom": (400, 300, 19, 0, 0, 0),
                      "panel_left": (19, 300, 300, -200, 0, 150), "panel_right": (19, 300, 300, 200, 0, 150),
                      "panel_back": (400, 19, 300, 0, 150, 150)}.items():
        s.write_part(pid, PANEL.format(dx=dims[0], dy=dims[1], dz=dims[2], x=dims[3], y=dims[4], z=dims[5]), intent=pid)
    return s


def test_for_all_of_them_asks_first_and_a_yes_does_it(box):
    """Item 3: "use the top panel for all of them" made four panels mirrors. Only its twin is offered, and asked."""
    from caliper import chat

    res = chat.turn(box, "use the top panel for all of them", use_llm=False, author=_no_designer)
    assert res.action == "ask" and res.reply.startswith("Make panel_bottom a mirror of panel_top?")
    assert not [p.id for p in box.design.parts if mirror.source_of(box, p.id)]
    res = chat.turn(box, "yes", use_llm=False, author=_no_designer)
    assert mirror.source_of(box, "panel_bottom") == "panel_top"
    assert [p.id for p in box.design.parts if mirror.source_of(box, p.id)] == ["panel_bottom"]


def test_both_takes_only_the_twin(box):
    from caliper import chat

    res = chat.turn(box, "use the left panel for both", use_llm=False, author=_no_designer)
    assert res.action == "mirror" and [p.id for p in box.design.parts if mirror.source_of(box, p.id)] == ["panel_right"]


def test_a_size_asked_for_all_isn_t_a_mirror(box):
    from caliper import chat

    assert chat._mirror_said(box, "pick the top panel thickness for all panels", None) is None


@pytest.mark.parametrize("aid,flagged", [("symmetric_load_ok", False), ("width_same_as_base", False),
                                         ("mirror_frame_wall", False), ("sides_match", True),
                                         ("side_left_same_width_as_side_right", False)])
def test_the_promote_guard_checks_claims_not_words(aid, flagged):
    """Item 4: a load, a size and one part pass; two parts said to match, with no mirrors(), are refused."""
    from caliper import promote

    ids = ["side_left", "side_right", "mirror_frame", "base"]
    assert bool(promote.overclaims(aid, "bbox(side_left).dx == bbox(side_right).dx", ids)) is flagged


def test_piece_and_hole_names_flip_with_the_part(tmp_path):
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    named = RIGHT.replace('"piece": "side panel"', '"piece": "right side panel"').replace(
        '"name": "side panel"', '"name": "right side panel"')
    s.write_part("side_right", named, intent="the right side")
    s.write_part("side_left", LEFT_V1, intent="the left side")
    mirror.make(s, "side_left", "side_right")
    d = C.declared(s, "side_left")
    assert d["construction"][0]["name"] == "left side panel" and d["holes"][0]["piece"] == "left side panel"
    assert C.declared(s, "side_right")["construction"][0]["name"] == "right side panel"


def test_the_tree_marks_a_mirror_and_offers_to_break_it(stool):
    from fastapi.testclient import TestClient

    from caliper import design_api
    from caliper.server import create_app

    from .test_small_words import _js

    mirror.make(stool, "side_left", "side_right")
    state = design_api.design_state(stool)
    p = next(x for x in state["parts"] if x["id"] == "side_left")
    assert p["mirror_of"] == "side_right"
    html = _js(["treeRows", "treeHtml", "renameRow"], "return treeHtml(%s, {parts: new Set(), pieces: new Set(), open: true, scope: null, canDrag: false});"
               % __import__("json").dumps({"parts": [p], "tree": {}}), "const EYE_ON = '', EYE_OFF = ''; const pieceId = (a, b) => a + '/' + b;")
    assert "a mirror of side_right" in html and 'data-unmirror="side_left"' in html
    import os
    os.environ["CALIPER_DESIGNS"] = os.path.dirname(stool.root)
    got = TestClient(create_app()).post(f"/api/designs/{stool.design.slug}/parts/side_left/unmirror").json()
    assert next(x for x in got["parts"] if x["id"] == "side_left")["mirror_of"] is None


def test_mirrors_is_in_mm_and_in_place(tmp_path):
    """Item 5: the largest gap between the surfaces, mm; a mirror moved 1 mm across the plane reads about 1 mm."""
    from caliper import measure
    from caliper.measure import Geometry
    import trimesh

    a = trimesh.creation.cone(radius=20, height=40, sections=64)
    a.apply_translation((100, 0, 0))
    b = a.copy()
    b.apply_transform(trimesh.transformations.reflection_matrix((0, 0, 0), (1, 0, 0)))
    assert measure.mirror_off(Geometry.from_mesh(a), Geometry.from_mesh(b), "yz") < measure.MIRROR_MM
    b.apply_translation((0, 1, 0))
    assert measure.mirror_off(Geometry.from_mesh(a), Geometry.from_mesh(b), "yz") == pytest.approx(1.0, abs=0.05)


def test_mirrors_takes_the_occt_lock(monkeypatch, stool):
    from caliper import measure, occt

    seen = []

    class Lock:
        def __enter__(self):
            seen.append("in")

        def __exit__(self, *a):
            seen.append("out")
    left, right = stool.part_geometry("side_left"), stool.part_geometry("side_right")   # built before, under the real lock
    monkeypatch.setattr(occt, "OCCT", Lock())
    measure.mirror_off(left, right)
    assert seen == ["in", "out"]
