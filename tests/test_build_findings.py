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
    assert review._mirror_findings(v1) == ([], 0)          # not even measured: it's one by construction


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


def test_a_stated_number_nothing_reads_is_a_finding(v1):
    v1.design.skeleton = v1.design.skeleton + [{"name": "seat_height", "value": 9, "unit": "in", "source": "stated"}]
    v1.save()
    (f,) = [f for f in review.findings(v1)["findings"] if f["kind"] == "stated"]
    assert f["said"].startswith("you said seat height is ") and "no part reads it" in f["said"]


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
