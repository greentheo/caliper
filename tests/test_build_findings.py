"""CALI-160 (#238), slice A — after a plan's build, what's measured wrong, as a list, with no model call.

step-stool-4's v1: both sides' pockets were cut for a 2×4 (38.1 × 88.9 mm) round a 19 × 101.6 mm plywood stretcher,
the sides weren't mirrors (walls 15 and 12 mm), and the stretcher missed the left side. Stubbed models only."""

import pytest

from caliper import plan as P
from caliper import review
from caliper.design import DesignStore

pytest.importorskip("cadquery")

SIDE = '''import cadquery as cq

PARAMS = {{"wall": {wall}, "x0": {x0}, "stretcher_w": 38.1, "stretcher_h": 88.9, "stretcher_z": 100}}


def build(params):
    p = {{**PARAMS, **(params or {{}})}}
    side = cq.Workplane("XY").box(p["wall"], 300, 400).translate((p["x0"] + p["wall"] / 2, 150, 200))
    pocket = cq.Workplane("XY").box(p["wall"] + 2, p["stretcher_w"], p["stretcher_h"]).translate(
        (p["x0"] + p["wall"] / 2, 150, p["stretcher_z"]))
    return side.cut(pocket)
'''
STRETCHER = '''import cadquery as cq

PARAMS = {"t": 19.05, "h": 101.6, "stretcher_z": 100}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane("XY").box(384, p["t"], p["h"]).translate((200, 150, p["stretcher_z"]))
'''
PLAN = {"parts": [{"id": "side_left", "what": "the left side"},
                  {"id": "side_right", "what": "the right side, a mirror of side_left"},
                  {"id": "stretcher", "what": "a 3/4 in plywood stretcher", "mounts_on": ["side_left", "side_right"]}],
        "skeleton": [{"name": "stretcher_z", "value": 100, "unit": "mm", "why": "its height off the floor", "source": "stated"}],
        "mates": [{"between": ["stretcher", "side_left"], "kind": "fits_in", "value": 0.3},
                  {"between": ["stretcher", "side_right"], "kind": "fits_in", "value": 0.3},
                  {"between": ["stretcher", "side_left"], "kind": "touch"}]}


@pytest.fixture
def v1(tmp_path):
    """step-stool-4 as it came out of its first build."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN), status="built")
    s.write_part("side_left", SIDE.format(wall=15, x0=0), intent="the left side")
    s.write_part("side_right", SIDE.format(wall=12, x0=388), intent="the right side")
    s.write_part("stretcher", STRETCHER, intent="the stretcher")
    return s


def test_v1_lists_both_pocket_misfits_the_mirror_and_the_left_side_miss(v1):
    rec = review.findings(v1)
    said = {(f["kind"], tuple(f["parts"])): f for f in rec["findings"]}
    left = said[("rule", ("stretcher", "side_left"))]
    assert any(f["said"].startswith("the stretcher has 19.1 mm of play in side_left's pocket") for f in rec["findings"])
    assert any(f["said"].startswith("the stretcher has 19.1 mm of play in side_right's pocket") for f in rec["findings"])
    assert left["fix"] in ("Size side_left's pocket to the stretcher: 0.3 mm a side.", "Move the stretcher or side_left so they meet.")
    assert any(f["said"].startswith("the stretcher doesn't meet side_left: ") for f in rec["findings"])
    mirror = said[("mirror", ("side_right", "side_left"))]
    assert "the plan says side_right mirrors side_left, but their surfaces are up to " in mirror["said"]
    assert mirror["fix"] == "Make side_right the mirror of side_left."
    assert all(f["measured"] for f in rec["findings"]) and rec["checks"] >= 4


def test_the_list_reads_measured_first_and_never_as_right(v1):
    text = review.said(review.findings(v1))
    assert text.startswith("Measured after the build: ") and "no model reading yet" in text
    assert "- The stretcher has 19.1 mm of play in side_left's pocket" in text
    assert review.said({"findings": [], "checks": 7}) == ("Measured after the build: nothing found in 7 checks. That's "
                                                         "what the checks see, not that it's right: look at it.")


def test_a_mirror_made_by_flipping_isn_t_a_finding(v1):
    from caliper import mirror

    mirror.make(v1, "side_right", "side_left")
    assert not [f for f in review.findings(v1)["findings"] if f["kind"] == "mirror"]
    got = review._mirror_findings(v1)
    assert not got["findings"] and got["measured"] == 0   # not even measured: it's one by construction


def test_a_part_restating_a_shared_size_is_a_finding(v1):
    """Same subject and size word only (#243): the sides' stretcher_w and stretcher_h against the plan's width and its
    board height, a size."""
    v1.design.skeleton = v1.design.skeleton + [{"name": "stretcher_width", "value": 19.05, "unit": "mm"},
                                               {"name": "stretcher_height", "value": 101.6, "unit": "mm", "kind": "size"}]
    v1.save()
    shadows = [f for f in review.findings(v1)["findings"] if f["kind"] == "shadow"]
    assert {f["parts"][0] for f in shadows} == {"side_left", "side_right"}
    said = next(f for f in shadows if f["parts"] == ["side_left"])["said"]
    assert "side_left sets its own stretcher width: 38.1 mm against the plan's 19.05 mm" in said
    assert "side_left sets its own stretcher height: 88.9 mm against the plan's 101.6 mm" in said


def test_a_stated_number_nothing_measures_is_a_note_not_a_check(v1):
    """#247 review: named, not measured. Only a rule reads it on the solid; nothing does, so it's a note, not one of the N."""
    before = review.findings(v1)["checks"]
    v1.design.skeleton = v1.design.skeleton + [{"name": "seat_height", "value": 9, "unit": "in", "source": "stated"}]
    v1.save()
    rec = review.findings(v1)
    assert not [f for f in rec["findings"] if f["kind"] == "stated"] and rec["checks"] == before
    assert any(n.startswith("you said seat height is ") and n.endswith("no check measures it") for n in rec["notes"])


def test_the_build_s_reply_ends_with_the_list_and_makes_no_model_call(tmp_path):
    """A plan's build, stubbed, says the measured list. The stub designer is the only "model" (no client, no key), so
    the list costs no model call."""
    from caliper import build_plan

    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN), status="review")
    scripts = {"side_left": SIDE.format(wall=15, x0=0), "side_right": SIDE.format(wall=12, x0=388), "stretcher": STRETCHER}
    calls = []

    def author(spec, feedback, prior):
        calls.append(spec.part)
        return scripts[spec.part]
    got = build_plan.build(s, {}, lambda *a, **k: None, author=author, use_llm=False)
    assert set(calls) == {"side_left", "side_right", "stretcher"}
    assert "Measured after the build: " in got["reply"] and got["findings"]
    assert any(f["kind"] == "mirror" for f in got["findings"])



# --- #247 review ---------------------------------------------------------------------------------------------------------
PRE_243 = {**PLAN, "mates": [{"between": ["stretcher", "side_left"], "kind": "touch"}]}     # no fits_in: before #243
FLUSH = STRETCHER.replace("box(384,", "box(373,").replace("translate((200,", "translate((201.5,")   # ends at each inner face


@pytest.fixture
def v1_unplanned(tmp_path):
    """step-stool-4's v1 as its plan really was: written before #243, so no fits_in mate; the stretcher ends flush with
    each side's inner face, at its pocket's mouth."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PRE_243), status="built")
    s.write_part("side_left", SIDE.format(wall=15, x0=0), intent="the left side")
    s.write_part("side_right", SIDE.format(wall=12, x0=388), intent="the right side")
    s.write_part("stretcher", FLUSH, intent="the stretcher")
    return s


def test_a_plan_with_no_fit_still_gets_its_pockets_measured(v1_unplanned):
    """Item 1: every mounted or touching pair gets a fit check, planned or not; both pockets are listed, with the play."""
    fits = [f for f in review.findings(v1_unplanned)["findings"] if f["kind"] == "fit"]
    assert {f["parts"][1] for f in fits} == {"side_left", "side_right"}
    for f in fits:
        assert "has 19.1 mm of play in" in f["said"] and "measured at the pocket's mouth (it ends flush with it, not in it)" in f["said"]
        assert f["fix"].startswith("Size side_") and f["measured"]


def test_a_part_that_sits_on_another_has_no_fit_listed(tmp_path):
    """Neither goes into the other: nothing is listed, and nothing is said not measured."""
    s = DesignStore.create("a shelf", base=str(tmp_path / "designs"))
    P.save(s, P.validate({"parts": [{"id": "top", "what": "a top"}, {"id": "leg", "what": "a leg", "mounts_on": ["top"]}]}), status="built")
    s.write_part("top", 'import cadquery as cq\n\ndef build(params):\n    return cq.Workplane("XY").box(400, 300, 19).translate((0, 0, 409.5))\n', intent="top")
    s.write_part("leg", 'import cadquery as cq\n\ndef build(params):\n    return cq.Workplane("XY").box(40, 40, 400).translate((0, 0, 200))\n', intent="leg")
    rec = review.findings(s)
    assert not [f for f in rec["findings"] if f["kind"] == "fit"] and not rec["unmeasured"]


def test_a_fit_that_errors_is_said_apart_and_not_counted(v1):
    """Item 2: "couldn't measure", in words, with no exception's name, no fix, and out of N."""
    v1.write_part("stretcher", STRETCHER.replace("p[\"stretcher_z\"]))", "p[\"stretcher_z\"] + 200))"), intent="up in the walls")
    rec = review.findings(v1)
    assert any(u.startswith("couldn't measure whether the stretcher fits side_left's pocket: ") and "Error" not in u
               for u in rec["unmeasured"])
    assert not [f for f in rec["findings"] if f["kind"] == "rule" and "fits" in f.get("id", "")]
    text = review.said(rec)
    assert f"checks measured" in text and "Not measured:" in text


def test_a_part_off_its_slot_is_told_to_move():
    assert review._fit_fix("the stretcher doesn't sit in side_left's slot: it's 90.5 mm off its front", "stretcher", "side_left", 0.3) \
        == "Move the stretcher down into side_left's slot."
    assert review._fit_fix("the stretcher has 19.1 mm of play in side_left's pocket", "stretcher", "side_left", 0.3) \
        == "Size side_left's pocket to the stretcher: 0.3 mm a side."


def test_a_stated_number_a_rule_reads_counts_and_one_a_part_names_is_a_note(v1):
    """Item 3: stretcher_z is read only by the parts' PARAMS: a note; with a rule over it, a measured check."""
    rec = review.findings(v1)
    assert any("stretcher z" in n and "names it, but no check measures it" in n for n in rec["notes"])
    plan = {**PLAN, "rules": [{"id": "low", "expr": "abs(bbox(stretcher).min_z + 50.8 - stretcher_z) <= 1", "source": "stated"}]}
    P.save(v1, P.validate(plan), status="built")
    assert not any("stretcher z" in n for n in review.findings(v1)["notes"])


def test_a_stated_length_is_measured_on_its_part(v1):
    v1.design.skeleton = v1.design.skeleton + [{"name": "stretcher_length", "value": 20, "unit": "in", "source": "stated"}]
    v1.write_part("stretcher", STRETCHER.replace('PARAMS = {', 'PARAMS = {"stretcher_length": 508, '), intent="the stretcher")
    v1.save()
    (f,) = [f for f in review.findings(v1)["findings"] if f["kind"] == "stated"]
    assert f["said"] == "you said stretcher length is 508 mm, and the stretcher is 384 mm long"    # 20 in, in mm
    assert f["fix"].startswith("Make the stretcher 508 mm long")


@pytest.mark.parametrize("what", ["the right side, mirrors side_left", "the right side, a mirror image of the left side"])
def test_more_ways_to_say_mirror(v1, what):
    plan = {**PLAN, "parts": [PLAN["parts"][0], {"id": "side_right", "what": what}, PLAN["parts"][2]]}
    P.save(v1, P.validate(plan), status="built")
    assert review.mirrored_pairs(v1)[0] == [("side_right", "side_left")]


def test_a_mirror_said_of_nothing_is_a_note(v1):
    plan = {**PLAN, "parts": [PLAN["parts"][0], {"id": "side_right", "what": "the right side, mirrored"}, PLAN["parts"][2]]}
    P.save(v1, P.validate(plan), status="built")
    assert "the plan says side_right is a mirror, but not of which part: it isn't compared" in review.findings(v1)["notes"]
