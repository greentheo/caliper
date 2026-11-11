"""CALI-162 (#240) — sizes two parts share live in the plan, and fit is measured.

Theo's step-stool-4 (2026-11-11): the skeleton gave the stretcher's height but not its section, both sides were written
first, each guessed a 2×4 (38.1 × 88.9 mm) for its pocket, and the stretcher came out 3/4 in plywood 4 in tall
(19 × 101.6 mm). The touch rules couldn't see it. Stubbed models only: no live call."""

import numpy as np
import pytest
import trimesh

from caliper import build_plan, measure, skeleton
from caliper import plan as P
from caliper.assembly import Assembly, Mate, Part, evaluate_assembly
from caliper.measure import Geometry

pytest.importorskip("cadquery")

PLAN_SKELETON = [{"name": "stretcher_thickness", "value": 19, "unit": "mm", "why": "3/4 in plywood"},
                 {"name": "stretcher_height", "value": 101.6, "unit": "mm", "why": "4 in", "kind": "size"}]


def _side(pocket_y, pocket_z):
    """A side 19 mm thick (x), with a pocket through it for the stretcher, centred 100 mm up."""
    side = trimesh.creation.box(extents=(19, 300, 400))
    hole = trimesh.creation.box(extents=(40, pocket_y, pocket_z))
    hole.apply_translation((0, 0, 100))
    return Geometry.from_mesh(side.difference(hole))


def _stretcher(t=19, h=101.6):
    """The stretcher: 280 mm long in x, its end 5 mm into the side's pocket."""
    m = trimesh.creation.box(extents=(280, t, h))
    m.apply_translation((135, 0, 100))
    return Geometry.from_mesh(m)


# --- 1. the planner owns the sizes two parts share ---------------------------------------------------------------------
def test_the_plan_prompt_says_a_shared_size_lives_in_the_skeleton():
    assert "A number two parts must agree on lives in the skeleton, never in either part" in P.SYSTEM
    assert "fits_in mate" in P.SYSTEM


def test_a_plan_s_fits_in_mate_is_saved_as_one(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    plan = P.validate({"parts": [{"id": "side_left", "what": "a side"}, {"id": "stretcher", "what": "a stretcher"}],
                       "skeleton": PLAN_SKELETON,
                       "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in", "value": 0.3}]})
    P.save(store, plan)
    (m,) = [m for m in store.assembly.mates if m.kind == "fits_in"]
    assert m.between == ["stretcher", "side_left"] and m.value == 0.3
    assert P.load(store).mates[0].kind == "fits_in"


# --- 3. fit is measured --------------------------------------------------------------------------------------------------
def _fit(side, stretcher, clearance=0.3):
    asm = Assembly(name="stool", parts=[Part(id="stretcher", source="x.stl"), Part(id="side_left", source="y.stl")],
                   mates=[Mate(id="stretcher_in_left", between=["stretcher", "side_left"], kind="fits_in", value=clearance)])
    (r,) = evaluate_assembly(asm, parts={"stretcher": stretcher, "side_left": side}).results
    return r


def test_theo_s_v1_pocket_fails_and_names_the_play():
    """A 2×4's pocket (38.1 × 88.9 mm) round a 19 × 101.6 mm stretcher: 19.1 mm of play, and 12.7 mm too tall."""
    got = measure.pocket(_stretcher(), _side(38.1, 88.9))
    assert got["in"] and got["axis"] == "x"
    assert got["gaps"]["+y"] == pytest.approx(9.55, abs=0.05) and got["gaps"]["-y"] == pytest.approx(9.55, abs=0.05)
    assert got["gaps"]["+z"] == pytest.approx(-6.35, abs=0.05)
    r = _fit(_side(38.1, 88.9), _stretcher())
    assert r.status == "fail"
    assert r.detail == ("the stretcher has 19.1 mm of play in side_left's pocket, and is 12.7 mm too big for it the other "
                        "way, on the drawn sizes")


def test_a_pocket_cut_to_the_plan_s_size_fits():
    """19.6 × 102.2 mm: 0.3 mm a side."""
    r = _fit(_side(19.6, 102.2), _stretcher())
    assert r.status == "pass" and r.actual == pytest.approx(0.0, abs=0.01)
    assert r.detail == "the stretcher sits in side_left's pocket with 0.3–0.3 mm a side, on the drawn sizes"


@pytest.mark.parametrize("pocket,word", [((23, 102.2), "has 4.0 mm of play"), ((18.4, 102.2), "is 0.6 mm too big"),
                                         ((18.6, 102.2), "is 0.4 mm too big")])     # −0.2 a side: an overlap never passes
def test_loose_or_tight_by_more_than_half_a_millimetre_fails(pocket, word):
    r = _fit(_side(*pocket), _stretcher())
    assert r.status == "fail" and word in r.detail


def test_a_part_that_doesn_t_reach_the_pocket_is_no_pass():
    far = trimesh.creation.box(extents=(200, 19, 101.6))
    far.apply_translation((200, 0, 100))
    r = _fit(_side(19.6, 102.2), Geometry.from_mesh(far))
    assert r.status == "error" and "doesn't go into it" in r.detail


# --- 2. parts read a shared size, never restate it ----------------------------------------------------------------------
SIDE = 'import cadquery as cq\n\nPARAMS = {params}\n\n\ndef build(params):\n    return cq.Workplane().box(19, 300, 400)\n'


def test_a_part_that_sets_its_own_stretcher_size_fails_with_the_sentence():
    script = SIDE.format(params='{"side_h": 400, "stretcher_t": 38.1, "stretcher_height": 88.9}')
    r = skeleton.shadows("side_left", script, PLAN_SKELETON)
    assert r.status == "fail"
    assert "side_left sets its own stretcher thickness: 38.1 mm against the plan's 19 mm" in r.detail
    assert "side_left sets its own stretcher height: 88.9 mm against the plan's 101.6 mm" in r.detail


def test_the_same_name_with_another_value_fails_too():
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_thickness": 25}'), PLAN_SKELETON)
    assert r.status == "fail" and "stretcher thickness: 25 mm against the plan's 19 mm" in r.detail


@pytest.mark.parametrize("params", ['{"stretcher_thickness": 19.0, "stretcher_height": 101.6, "side_h": 400}',
                                    '{"stretcher_thickness": 0.748, "side_h": 15.75}', '{"side_h": 400}'])
def test_reading_the_plan_s_numbers_passes(params):
    """By its name, in mm or the same number in inches; a part's own size that the plan doesn't share is its own."""
    assert skeleton.shadows("side_left", SIDE.format(params=params), PLAN_SKELETON).status == "pass"


def test_restating_a_shared_size_under_another_name_is_a_note_not_a_fail():
    """#243 review: it builds right today; the note says to read the plan's name."""
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_t": 19.0}'), PLAN_SKELETON)
    assert r.status == "pass" and "restates the plan's stretcher thickness as stretcher_t" in r.detail


def test_a_shadowed_size_fails_the_round_and_the_designer_fixes_it(tmp_path):
    """It fails the part's round (a repair the first build makes), so round 2 reads the plan's number."""
    from caliper import chat
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    P.save(store, P.validate({"parts": [{"id": "side_left", "what": "a side"}], "skeleton": PLAN_SKELETON}))
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        guess = '{"stretcher_t": 38.1}' if feedback is None else '{"stretcher_thickness": 19}'
        return SIDE.format(params=guess)
    check = build_plan.interfaces(store, "side_left", {})
    res = chat.author_part(store, "side_left", "a side", author=author, use_llm=False, promote_feedback=False,
                           max_rounds=2, interfaces=check, repair_only=build_plan.REPAIRS)
    assert res.version and len(seen) == 2
    assert "side_left sets its own stretcher thickness: 38.1 mm against the plan's 19 mm" in seen[1]
    assert '"stretcher_thickness": 19' in store.read_script("side_left")


# --- 4. a part a pocket is cut to is built first when its size isn't planned ---------------------------------------------
def test_the_stretcher_is_built_first_and_measured_when_the_plan_lacks_its_size(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    plan = P.validate({"parts": [{"id": "side_left", "what": "a side"},
                                 {"id": "stretcher", "what": "a stretcher", "mounts_on": ["side_left"]}],
                       "skeleton": [{"name": "stretcher_z", "value": 100, "unit": "mm"}],
                       "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in"}]})
    P.save(store, plan)
    order, measure_ = build_plan.defined_first(store, P.load(store), P.order(plan))
    assert order == ["stretcher", "side_left"] and measure_ == {"stretcher"}
    got = build_plan.measure_section(store, "stretcher", _stretcher())
    assert [(g["name"], g["value"], g["source"]) for g in got] == [("stretcher_thickness", 19.0, "measured"),
                                                                  ("stretcher_height", 101.6, "measured")]
    assert {s["name"] for s in store.design.skeleton} >= {"stretcher_thickness", "stretcher_height"}


def test_a_planned_size_keeps_the_plan_s_order(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    plan = P.validate({"parts": [{"id": "side_left", "what": "a side"},
                                 {"id": "stretcher", "what": "a stretcher", "mounts_on": ["side_left"]}],
                       "skeleton": PLAN_SKELETON, "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in"}]})
    P.save(store, plan)
    assert build_plan.defined_first(store, P.load(store), P.order(plan)) == (["side_left", "stretcher"], set())


def test_a_part_whose_middle_is_in_the_host_s_solid_isn_t_in_a_pocket():
    """Run into a side with no pocket: no gaps to measure from inside the solid. Said, never a pass (mutant 0)."""
    solid = Geometry.from_mesh(trimesh.creation.box(extents=(19, 300, 400)))
    r = _fit(solid, _stretcher())
    assert r.status == "error" and "isn't in a pocket of it" in r.detail


def test_a_part_that_doesn_t_stick_out_has_no_way_in_to_measure():
    """A block wholly inside the side's bounds, in its pocket: no axis it goes in along. Said, never a pass (mutant 3)."""
    block = trimesh.creation.box(extents=(5, 19, 101.6))
    block.apply_translation((0, 0, 100))
    r = _fit(_side(19.6, 102.2), Geometry.from_mesh(block))
    assert r.status == "error" and "doesn't go into it" in r.detail


def test_a_near_name_is_matched_by_what_it_names_not_by_the_nearest_number():
    """stretcher_h is a height: against the plan's height, though 20 is nearer the thickness (mutant 7)."""
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_h": 20}'), PLAN_SKELETON)
    assert "side_left sets its own stretcher height: 20 mm against the plan's 101.6 mm" in r.detail



# --- #243 review --------------------------------------------------------------------------------------------------------
#: step-stool-4's skeleton and its four parts' PARAMS, as built (the numbers in the review on #243).
SS4 = [{"name": "top_height", "value": 16.0, "unit": "in", "why": "the top of the plywood sits 16 in above the floor"},
       {"name": "top_length", "value": 18.0, "unit": "in", "why": "plywood top is 18 in long (x)"},
       {"name": "top_width", "value": 24.0, "unit": "in", "why": "plywood top is 24 in wide (y)"},
       {"name": "ply_thickness", "value": 0.75, "unit": "in", "why": "3/4 in plywood top"},
       {"name": "bolt_dia", "value": 0.375, "unit": "in", "why": "3/8 in bolts through the flange and the top"},
       {"name": "bolt_spacing", "value": 6.0, "unit": "in", "why": "bolts are 6 in apart along each flange"},
       {"name": "bolts_per_flange", "value": 3.0, "unit": "count", "why": "3 bolts 6 in apart"},
       {"name": "flange_width", "value": 2.0, "unit": "in", "why": "enough flange under the plywood to fit a 3/8 in bolt"},
       {"name": "stretcher_height", "value": 3.0, "unit": "in", "why": "stretcher sits near the floor, low enough to keep it out of"},
       {"name": "design_load", "value": 300.0, "unit": "lb", "why": "a full adult standing on it, with some margin"}]
SS4_PARAMS = {
    "top": {"top_height": 406.4, "top_length": 457.2, "top_width": 609.6, "ply_thickness": 19.0, "bolt_dia": 9.5,
            "bolt_spacing": 152.4, "bolts_per_flange": 3.0, "flange_width": 50.8},
    "side_left": {"top_height": 406.4, "ply_thickness": 19.0, "bolt_dia": 9.5, "bolt_hole_dia": 10.3, "flange_width": 50.8,
                  "flange_t": 12.0, "wall_t": 12.0, "stretcher_height": 76.2, "stretcher_w": 19.0, "stretcher_h": 101.6,
                  "stretcher_len": 508.0, "pocket_depth": 15.0, "design_load_lb": 300.0},
    "side_right": {"top_height": 406.4, "ply_thickness": 19.0, "flange_width": 50.8, "flange_t": 15.0, "wall_t": 15.0,
                   "bolt_dia": 9.5, "bolt_clearance": 0.8, "stretcher_height": 76.2, "stretcher_w": 19.0,
                   "stretcher_h": 101.6, "pocket_depth": 25.4},
    "stretcher": {"stretcher_height": 76.2, "stretcher_rise": 101.6, "ply_t": 19.05}}


@pytest.mark.parametrize("pid", list(SS4_PARAMS))
def test_step_stool_4_s_parts_as_built_give_no_false_fail(pid):
    """#243 review: 3 of 4 failed, every side reason false (flange_t as the flange width, stretcher_len as its height,
    bolt_clearance as the bolt dia, and the board's stretcher_h against where the stretcher sits)."""
    r = skeleton.shadows(pid, SIDE.format(params=repr(SS4_PARAMS[pid])), SS4, list(SS4_PARAMS))
    assert r.status == "pass", r.detail
    if pid.startswith("side"):
        assert "the plan doesn't name the stretcher width" in r.detail     # what really went wrong: said, as a note
    if pid == "stretcher":
        assert r.detail == "stretcher restates the plan's ply thickness as ply_t: read ply_thickness instead"


@pytest.mark.parametrize("name,unit,why,kind", [
    ("stretcher_height", "in", "stretcher sits near the floor, low enough to keep it out of", "position"),
    ("top_height", "in", "the top of the plywood sits 16 in above the floor", "position"),
    ("top_length", "in", "plywood top is 18 in long (x)", "size"), ("ply_thickness", "in", "3/4 in plywood top", "size"),
    ("bolts_per_flange", "count", "", "count"), ("design_load", "lb", "", "load")])
def test_a_skeleton_number_s_kind(name, unit, why, kind):
    assert P.kind_of(P.SkeletonValue(name=name, value=1, unit=unit, why=why)) == kind
    if unit not in ("count", "lb"):                    # a count or a load is one by its unit
        assert P.kind_of(P.SkeletonValue(name=name, value=1, unit=unit, why=why, kind="position")) == (
            "size" if name.split("_")[-1] in ("length", "thickness") else "position")   # the size word, then the plan's


def test_a_position_is_never_compared_with_a_size():
    """The plan's stretcher_height is where it sits; a part's stretcher_h is how tall the board is."""
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_h": 101.6}'), SS4)
    assert r.status == "pass"


def test_a_part_s_own_size_is_its_own_unless_the_plan_shares_it():
    """top_t on the top is its own; against a plan's top_thickness it's compared (#243 re-check, item 2)."""
    assert skeleton.shadows("top", SIDE.format(params='{"top_t": 25}'), PLAN_SKELETON).status == "pass"
    shared = PLAN_SKELETON + [{"name": "top_thickness", "value": 19, "unit": "mm"}]
    assert skeleton.shadows("top", SIDE.format(params='{"top_t": 25}'), shared).status == "fail"


def test_a_pocket_narrowing_at_its_inner_face_fails():
    """Rays at one depth passed it: 0.26 mm a side at half depth, 18.6 mm at the inner face (#243 review)."""
    side = trimesh.creation.box(extents=(19, 300, 400))
    wide = trimesh.creation.box(extents=(14, 19.6, 102.2))
    wide.apply_translation((-7, 0, 100))
    narrow = trimesh.creation.box(extents=(10, 18.6, 102.2))
    narrow.apply_translation((7, 0, 100))
    host = Geometry.from_mesh(side.difference(wide).difference(narrow))
    r = _fit(host, _stretcher())
    assert r.status == "fail" and "too big" in r.detail


def test_a_tilted_peg_is_said_not_failed():
    peg = trimesh.creation.cylinder(radius=6, height=80, sections=48)
    peg.apply_transform(trimesh.transformations.rotation_matrix(np.radians(80), (0, 1, 0)))
    peg.apply_translation((30, 0, 100))
    r = _fit(_side(19.6, 102.2), Geometry.from_mesh(peg))
    assert r.status == "error" and "goes in at an angle: its fit isn't measured" in r.detail


def test_an_open_slot_says_which_sides_it_measured():
    side = trimesh.creation.box(extents=(19, 300, 400))
    slot = trimesh.creation.box(extents=(40, 19.6, 500))
    r = _fit(Geometry.from_mesh(side.difference(slot)), _stretcher())
    assert r.status == "pass" and "open on the top and bottom: measured on 2 sides" in r.detail


def test_a_section_is_written_only_for_a_board_square_to_the_axes(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    angle = trimesh.creation.box(extents=(280, 50, 3)).union(trimesh.creation.box(extents=(280, 3, 50)))
    assert build_plan.measure_section(store, "angle", Geometry.from_mesh(angle)) == []
    assert not store.design.skeleton


def test_a_measured_section_is_measured_again_when_its_part_changes(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    board = 'import cadquery as cq\n\ndef build(params):\n    return cq.Workplane("XY").box(280, {t}, 101.6)\n'
    store.write_part("stretcher", board.format(t=19.05), intent="the stretcher")
    build_plan.measure_section(store, "stretcher", store.part_geometry("stretcher"))
    store.write_part("stretcher", board.format(t=25.4), intent="the stretcher, thicker")
    got = {s["name"]: s["value"] for s in store.design.skeleton}
    assert got["stretcher_thickness"] == pytest.approx(25.4, abs=0.01) and len(store.design.skeleton) == 2


# --- #243 re-check ------------------------------------------------------------------------------------------------------
def test_on_step_stool_4_s_own_skeleton_the_stretcher_is_built_first(tmp_path):
    """Item 1: its stretcher_height is where it sits, so its section isn't planned: the stretcher comes before both sides,
    and its height goes in as stretcher_h, the name the plan's position doesn't use."""
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    plan = P.validate({"parts": [{"id": "top", "what": "the top"}, {"id": "side_left", "what": "a side", "mounts_on": ["top"]},
                                 {"id": "side_right", "what": "a side", "mounts_on": ["top"]},
                                 {"id": "stretcher", "what": "the stretcher", "mounts_on": ["side_left", "side_right"]}],
                       "skeleton": SS4, "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in"},
                                                  {"between": ["stretcher", "side_right"], "kind": "fits_in"}]})
    P.save(store, plan)
    order, measure_ = build_plan.defined_first(store, P.load(store), P.order(plan))
    assert order.index("stretcher") < order.index("side_left") and order.index("stretcher") < order.index("side_right")
    assert measure_ == {"stretcher"}
    got = build_plan.measure_section(store, "stretcher", _stretcher())
    assert [(g["name"], g["value"]) for g in got] == [("stretcher_thickness", 19.0), ("stretcher_h", 101.6)]
    assert next(s for s in store.design.skeleton if s["name"] == "stretcher_height")["value"] == 3.0   # the plan's, kept


def test_a_planned_section_named_as_sizes_keeps_the_plan_s_order(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    sizes = SS4 + [{"name": "stretcher_thickness", "value": 0.75, "unit": "in"}, {"name": "stretcher_h", "value": 4, "unit": "in", "kind": "size"}]
    plan = P.validate({"parts": [{"id": "side_left", "what": "a side"}, {"id": "stretcher", "what": "the stretcher", "mounts_on": ["side_left"]}],
                       "skeleton": sizes, "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in"}]})
    P.save(store, plan)
    assert build_plan.defined_first(store, P.load(store), P.order(plan)) == (["side_left", "stretcher"], set())


@pytest.mark.parametrize("pid,params", [("stretcher", '{"stretcher_t": 25}'), ("side_left", '{"side_t": 25}')])
def test_a_part_s_own_size_against_the_plan_s_shared_one_fails(pid, params):
    """Item 2: the stretcher built 25 thick against pockets cut for 19."""
    sk = PLAN_SKELETON + [{"name": "side_thickness", "value": 19, "unit": "mm"}]
    r = skeleton.shadows(pid, SIDE.format(params=params), sk)
    assert r.status == "fail" and "25 mm against the plan's 19 mm" in r.detail


@pytest.mark.parametrize("name,why", [("top_depth", "the top's depth from front to back"),
                                      ("flange_width", "flange width, at the top of each side"),
                                      ("stretcher_thickness", "the stretcher board, cut from the same sheet as the top"),
                                      ("leg_thickness", "the leg's thickness at the floor")])
def test_the_size_word_decides_before_the_why(name, why):
    """Item 3: the reviewer's four whys read as positions."""
    assert P.kind_of(P.SkeletonValue(name=name, value=1, unit="in", why=why)) == "size"


def test_a_height_with_no_why_and_no_kind_is_unclear_and_a_mismatch_is_a_note():
    """Item 3: with every why emptied, step-stool-4's sides failed again on the stretcher height."""
    bare = [{**s, "why": ""} for s in SS4]
    assert P.kind_of(P.SkeletonValue.model_validate(next(s for s in bare if s["name"] == "stretcher_height"))) == "unclear"
    for pid in ("side_left", "side_right"):
        r = skeleton.shadows(pid, SIDE.format(params=repr(SS4_PARAMS[pid])), bare, list(SS4_PARAMS))
        assert r.status == "pass", r.detail


def test_a_board_revised_into_an_angle_drops_its_section_and_says_so(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    board = 'import cadquery as cq\n\ndef build(params):\n    return cq.Workplane("XY").box(280, 19.05, 101.6)\n'
    angle = ('import cadquery as cq\n\ndef build(params):\n    a = cq.Workplane("XY").box(280, 50, 3)\n'
             '    return a.union(cq.Workplane("XY").box(280, 3, 50).translate((0, 23.5, 23.5)))\n')
    store.write_part("stretcher", board, intent="the stretcher")
    build_plan.measure_section(store, "stretcher", store.part_geometry("stretcher"))
    assert len(store.design.skeleton) == 2
    store.write_part("stretcher", angle, intent="an angle")
    assert not store.design.skeleton
    assert any("its measured section is dropped" in (h.get("said") or "") for h in store.history("stretcher"))


def test_a_part_standing_proud_in_an_open_slot_doesn_t_sit_in_it():
    """Item 4: 48 mm off the bottom of an open-top notch read as "sits … with 0.3–48.4 mm a side"."""
    side = trimesh.creation.box(extents=(19, 300, 400))
    notch = trimesh.creation.box(extents=(40, 19.6, 300))
    notch.apply_translation((0, 0, 200))                     # from z 50 up, open on top
    high = trimesh.creation.box(extents=(280, 19.05, 101.6))
    high.apply_translation((135, 0, 148.8))                  # its bottom 48 mm off the notch's
    r = _fit(Geometry.from_mesh(side.difference(notch)), Geometry.from_mesh(high))
    assert r.status == "fail"
    assert r.detail.startswith("the stretcher doesn't sit in side_left's slot: it's 48.0 mm off its bottom, open on the top")


def test_a_plan_naming_only_the_thickness_builds_first_and_measures_only_the_height(tmp_path):
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    sk = SS4 + [{"name": "stretcher_thickness", "value": 0.75, "unit": "in"}]
    plan = P.validate({"parts": [{"id": "side_left", "what": "a side"}, {"id": "stretcher", "what": "the stretcher", "mounts_on": ["side_left"]}],
                       "skeleton": sk, "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in"}]})
    P.save(store, plan)
    assert build_plan.defined_first(store, P.load(store), P.order(plan)) == (["stretcher", "side_left"], {"stretcher"})
    got = build_plan.measure_section(store, "stretcher", _stretcher())
    assert [g["name"] for g in got] == ["stretcher_h"]


def test_an_unclear_height_by_its_own_name_is_a_note_not_a_fail():
    bare = [{**s, "why": ""} for s in SS4]
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_height": 50}'), bare)
    assert r.status == "pass" and "the plan's stretcher height may be where something sits: side_left sets 50 mm" in r.detail
