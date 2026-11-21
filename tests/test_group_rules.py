"""CALI-36 (#17) slice B — a plan's rules and mates may name a group, measured as the group's built parts together.

"The box sits on the platform": ``bbox(box).min_z >= bbox(platform).max_z - 1`` and a touch mate between box and platform,
over two parts each. A group with a part not built yet waits for it; one whose part didn't build isn't measured, and says
which; a failing group check names the group's parts. A design without groups measures exactly as it did."""

import pytest

from caliper import plan as P
from caliper import review
from caliper.assembly import GroupGeometry, build_context, evaluate_assembly
from caliper.design import DesignStore

pytest.importorskip("cadquery")


def _box(x, y, z, at_z):
    return ("def build(params):\n    import cadquery as cq\n"
            f"    return cq.Workplane('XY').box({x}, {y}, {z}, centered=False).translate((0, 0, {at_z}))\n")


#: the platform: legs 300 tall, a 19 mm deck on them; the box: a floor on the deck, a wall on the floor
LEGS, DECK = _box(40, 40, 300, 0), _box(1000, 600, 19, 300)
FLOOR, WALL = _box(1000, 600, 12, 319), _box(12, 600, 500, 331)

PLAN = {
    "parts": [{"id": "legs", "what": "legs", "made": "lumber"},
              {"id": "deck", "what": "the deck", "made": "sheet", "mounts_on": ["legs"]},
              {"id": "floor", "what": "the box's floor", "made": "sheet"},     # made: else it's what it stands on (#117)
              {"id": "wall", "what": "a wall", "made": "sheet", "mounts_on": ["floor"]}],
    "groups": [{"id": "platform", "what": "the platform", "parts": ["legs", "deck"]},
               {"id": "box", "what": "the box", "parts": ["floor", "wall"], "mounts_on": ["platform"]}],
    "mates": [{"between": ["box", "platform"], "kind": "touch"}, {"between": ["floor", "deck"], "kind": "touch"}],
    "rules": [{"id": "box_on_platform", "expr": "bbox(box).min_z >= bbox(platform).max_z - 1", "source": "stated"}],
}


def _camper(tmp_path, floor=FLOOR, wall=WALL, build=("legs", "deck", "floor", "wall")):
    s = DesignStore.create("a truck camper: a platform and a box on it", base=str(tmp_path / "designs"))
    P.save(s, P.validate(PLAN))
    for pid, src in (("legs", LEGS), ("deck", DECK), ("floor", floor), ("wall", wall)):
        if pid in build:
            s.write_part(pid, src, intent=pid)
    return s


def _results(store):
    report, errors = store.evaluate(tolerant=True)
    return {r.id: r for r in report.results}, errors


def test_a_rule_and_a_mate_over_groups_are_measured_off_their_parts_together(tmp_path):
    got, errors = _results(_camper(tmp_path))
    assert errors == {}
    assert got["box_on_platform"].status == "pass", got["box_on_platform"]
    assert got["plan_box_platform_touch"].status == "pass", got["plan_box_platform_touch"]
    assert got["plan_floor_deck_touch"].status == "pass"


def test_a_box_that_floats_fails_both_and_the_finding_names_the_group_s_parts(tmp_path):
    store = _camper(tmp_path, floor=_box(1000, 600, 12, 400), wall=_box(12, 600, 500, 412))   # 81 mm up off the deck
    got, _ = _results(store)
    assert got["plan_box_platform_touch"].status == "fail"
    assert got["plan_box_platform_touch"].actual == pytest.approx(81, abs=0.5)
    assert got["box_on_platform"].status == "pass"                      # above it is above it: the touch says it's off
    found = review.findings(store)
    (touch,) = [f for f in found["findings"] if f.get("id") == "plan_box_platform_touch"]
    assert touch["parts"] == ["floor", "wall", "legs", "deck"], touch
    assert touch["said"] == "the box doesn't meet platform: 81.0 mm apart", touch["said"]


def test_a_box_sunk_into_the_deck_fails_the_rule(tmp_path):
    got, _ = _results(_camper(tmp_path, floor=_box(1000, 600, 12, 290)))
    assert got["box_on_platform"].status == "fail"


def test_a_group_with_a_part_not_built_waits_for_it(tmp_path):
    got, _ = _results(_camper(tmp_path, build=("legs", "deck", "floor")))
    assert got["box_on_platform"].status == "deferred" and got["box_on_platform"].detail == "waits for wall to be built"
    assert got["plan_box_platform_touch"].status == "deferred"
    assert got["plan_floor_deck_touch"].status == "pass"                 # between parts: as it was


def test_a_group_whose_part_didn_t_build_isn_t_measured_and_says_which(tmp_path):
    store = _camper(tmp_path)
    from caliper.assembly import load_parts

    parts = load_parts(store.assembly, store.root)
    parts.pop("wall")
    got = {r.id: r for r in evaluate_assembly(store.assembly, base_dir=store.root, parts=parts,
                                              groups=store.design.groups).results}
    assert got["box_on_platform"].status == "error"
    assert got["box_on_platform"].detail == "box isn't measured: wall didn't build"


def test_the_mates_over_groups_are_kept_with_the_plan_and_read_back(tmp_path):
    store = _camper(tmp_path)
    assert [m.id for m in store.assembly.mates] == ["plan_floor_deck_touch"]       # the assembly's mates: parts only
    assert "plan_box_platform_touch" in {a.id for a in store.assembly.assertions}
    again = P.load(DesignStore.load(store.design.slug, base=str(tmp_path / "designs")))
    assert [(m.between, m.kind) for m in again.mates] == [(["floor", "deck"], "touch"), (["box", "platform"], "touch")]
    P.save(store, again)                                             # saved again, nothing doubled
    assert [a.id for a in store.assembly.assertions].count("plan_box_platform_touch") == 1


def test_a_mate_between_a_group_and_a_part_in_it_is_refused():
    bad = {**PLAN, "mates": [{"between": ["deck", "platform"], "kind": "touch"}]}
    with pytest.raises(P.PlanError, match="a mate between 'platform' and 'deck', which is in it"):
        P.validate(bad)


def test_the_group_binding_is_the_parts_together_and_a_design_without_groups_binds_as_it_did(tmp_path):
    store = _camper(tmp_path)
    from caliper.assembly import load_parts

    parts = load_parts(store.assembly, store.root)
    ctx = build_context(store.assembly, parts, store.design.groups)
    b = ctx["bbox"](ctx["box"])
    assert (b.min_z, b.max_z) == (pytest.approx(319), pytest.approx(831))
    assert P.group_parts(store.design.groups, "box") == ["floor", "wall"] and P.group_parts(store.design.groups, "x") == []
    flat = build_context(store.assembly, parts)
    assert set(flat) == set(build_context(store.assembly, parts, None)) == set(build_context(store.assembly, parts, []))
    assert "box" not in flat and "platform" not in flat
    same = evaluate_assembly(store.assembly, base_dir=store.root, parts=parts)
    assert same.to_dict() == evaluate_assembly(store.assembly, base_dir=store.root, parts=parts, groups=[]).to_dict()



# --- #399 review (reviewer-3) -----------------------------------------------------------------------------------------
def test_a_new_part_never_takes_a_group_s_name(tmp_path):
    """"add a platform" on the camper got the id platform, the group's, and its rules then measured the group."""
    from caliper import chat

    store = _camper(tmp_path)
    got = chat.offline_classify(store, "add a platform for the ladder")
    assert got.action == "author" and got.part not in ("platform", "box"), got
    client = __import__("tests.test_chat", fromlist=["_StubClient"])._StubClient(
        '{"action": "author", "part": "box", "intent": "a box for tools"}')
    assert chat.llm_classify(store, "add a box for tools", client=client).part not in ("box", "platform")
    with pytest.raises(ValueError, match="'platform' is a group of this design's plan"):
        store.write_part("platform", _box(100, 100, 20, 2000), intent="a shelf")


def test_a_name_that_is_both_a_part_and_a_group_is_an_error_never_a_measurement(tmp_path):
    """reviewer-3's case: a part called platform at 2000-2020 mm, and bbox(platform).max_z <= 400 read the group's 319."""
    from caliper.assembly import Assembly, Part, load_parts
    from caliper.spec import Assertion

    store = _camper(tmp_path)
    parts = load_parts(store.assembly, store.root)
    from caliper.measure import Geometry
    import cadquery as cq

    parts["platform"] = Geometry.from_cadquery(cq.Workplane("XY").box(100, 100, 20, centered=False).translate((0, 0, 2000)))
    asm = Assembly(name="camper", parts=list(store.assembly.parts) + [Part(id="platform", source="x.stl")],
                   assertions=[Assertion(id="low", expr="bbox(platform).max_z <= 400")])
    (r,) = [x for x in evaluate_assembly(asm, base_dir=store.root, parts=parts, groups=store.design.groups).results
            if x.id == "low"]
    assert r.status == "error" and r.detail == "platform names both a part and a group: rename the part", r
    assert build_context(asm, parts, store.design.groups)["platform"] is parts["platform"]   # never the group over it


def test_a_group_with_a_part_missing_isn_t_bound(tmp_path):
    from caliper.assembly import load_parts

    store = _camper(tmp_path)
    parts = load_parts(store.assembly, store.root)
    parts.pop("deck")
    ctx = build_context(store.assembly, parts, store.design.groups)
    assert "platform" not in ctx and "box" in ctx


def test_a_group_s_geometry_keeps_its_parts_apart_for_slice_e(tmp_path):
    store = _camper(tmp_path)
    g, why = store.group_geometry("box")
    assert why == "" and isinstance(g, GroupGeometry) and list(g.members) == ["floor", "wall"]
    a, b = g.faces_of["floor"], g.faces_of["wall"]
    assert a[0] == 0 and a[1] == b[0] and b[1] == len(g.mesh.faces)
    assert len(g.members["wall"].mesh.faces) == b[1] - b[0]
    assert store.group_geometry("nope") == (None, "there's no group 'nope' in this design's plan")
    half = _camper(tmp_path / "half", build=("legs", "deck", "floor"))
    assert half.group_geometry("box") == (None, "waits for wall to be built")


def test_a_hole_probe_over_a_group_says_to_name_a_part(tmp_path):
    from caliper.assembly import load_parts

    store = _camper(tmp_path)
    ctx = build_context(store.assembly, load_parts(store.assembly, store.root), store.design.groups)
    with pytest.raises(ValueError, match="a group has no holes to find: name a part"):
        ctx["hole_misalignment"](ctx["box"], ctx["platform"])


def test_the_assembly_s_own_measures_are_reserved_names():
    assert {"fit_off", "mirrors"} <= P.FUNCTIONS
    with pytest.raises(P.PlanError, match="'mirrors' names two things"):
        P.validate({**PLAN, "groups": PLAN["groups"] + [{"id": "mirrors", "what": "x", "parts": ["legs"]}]})
