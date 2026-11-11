"""CALI-162 (#240) — sizes two parts share live in the plan, and fit is measured.

Theo's step-stool-4 (2026-11-11): the skeleton gave the stretcher's height but not its section, both sides were written
first, each guessed a 2×4 (38.1 × 88.9 mm) for its pocket, and the stretcher came out 3/4 in plywood 4 in tall
(19 × 101.6 mm). The touch rules couldn't see it. Stubbed models only: no live call."""

import pytest
import trimesh

from caliper import build_plan, measure, skeleton
from caliper import plan as P
from caliper.assembly import Assembly, Mate, Part, evaluate_assembly
from caliper.measure import Geometry

pytest.importorskip("cadquery")

PLAN_SKELETON = [{"name": "stretcher_thickness", "value": 19, "unit": "mm", "why": "3/4 in plywood"},
                 {"name": "stretcher_height", "value": 101.6, "unit": "mm", "why": "4 in"}]


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
    assert r.detail == "the stretcher has 19.1 mm of play in side_left's pocket, and is 12.7 mm too big for it the other way"


def test_a_pocket_cut_to_the_plan_s_size_fits():
    """19.6 × 102.2 mm: 0.3 mm a side."""
    r = _fit(_side(19.6, 102.2), _stretcher())
    assert r.status == "pass" and r.actual == pytest.approx(0.0, abs=0.01)
    assert r.detail == "the stretcher sits in side_left's pocket with 0.3–0.3 mm a side"


@pytest.mark.parametrize("pocket,word", [((23, 102.2), "has 4.0 mm of play"), ((18.4, 102.2), "is 0.6 mm too big")])
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
    script = SIDE.format(params='{"side_h": 400, "stretcher_w": 38.1, "stretcher_h": 88.9}')
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


def test_restating_a_shared_size_under_another_name_fails_even_at_the_same_value():
    r = skeleton.shadows("side_left", SIDE.format(params='{"stretcher_w": 19.0}'), PLAN_SKELETON)
    assert r.status == "fail" and "restates the plan's stretcher thickness as stretcher_w" in r.detail


def test_a_shadowed_size_fails_the_round_and_the_designer_fixes_it(tmp_path):
    """It fails the part's round (a repair the first build makes), so round 2 reads the plan's number."""
    from caliper import chat
    from caliper.design import DesignStore

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    P.save(store, P.validate({"parts": [{"id": "side_left", "what": "a side"}], "skeleton": PLAN_SKELETON}))
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        guess = '{"stretcher_w": 38.1}' if feedback is None else '{"stretcher_thickness": 19}'
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
