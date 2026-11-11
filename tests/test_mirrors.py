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
    assert off > 0.01
    mirror.make(stool, "side_left", "side_right")
    assert measure.mirror_off(stool.part_geometry("side_left"), stool.part_geometry("side_right"), "yz") < 0.001


def test_mirrors_is_an_expression_a_design_check_can_use(stool):
    from caliper.assembly import Assembly, evaluate_assembly
    from caliper.spec import Assertion

    asm = Assembly(name="s", parts=stool.assembly.parts, assertions=[
        Assertion(id="left_mirrors_right", expr='mirrors(side_left, side_right, "yz") <= 0.001')])
    (r,) = evaluate_assembly(asm, base_dir=stool.root).results
    assert r.status == "fail" and r.actual > 0.01
    mirror.make(stool, "side_left", "side_right")
    (r,) = evaluate_assembly(asm, base_dir=stool.root).results
    assert r.status == "pass"


@pytest.mark.parametrize("aid,expr,flagged", [
    ("side_left_mirrors_side_right", "-0.1 <= bbox(side_left).dx - bbox(side_right).dx <= 0.1", True),
    ("sides_symmetric", "bbox(side_left).dz == bbox(side_right).dz", True),
    ("left_identical_to_right", "bbox(side_left).dx >= 1", True),
    ("left_same_as_right", "bbox(side_left).dx >= 1", True),
    ("side_left_mirrors_side_right", 'mirrors(side_left, side_right, "yz") <= 0.001', False),
    ("side_left_same_size_as_side_right", "bbox(side_left).dx == bbox(side_right).dx", False),
    ("holes_match_bolt", "holes_aligned(side_left, side_right)", False),
])
def test_a_check_named_for_a_mirror_has_to_measure_one(aid, expr, flagged):
    from caliper import promote

    assert bool(promote.overclaims(aid, expr)) is flagged


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
                                                   "mirrors() says they differ by ")
    assert any(a.id == "side_left_mirrors_side_right" for a in stool.assembly.assertions)
