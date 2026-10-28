"""CALI-40 — sizing a tube frame with whittle's FrameStudy, from the tubes a part declares."""

import pytest

from caliper import aero, frame_study as fs
from caliper.design import DesignStore

pytest.importorskip("whittle")
from whittle import tube_size  # noqa: E402

# A shank held in a "receiver" (supports at x=0 and x=150) carrying a rail out to x=-1000.
FRAME = '''PARAMS = {
    "shank_w": 50.8,   # 2 in
    "shank_t": 3.175,  # 1/8 in
    "rail_w": 50.8,
    "rail_t": 3.175,
}


def members(params):
    p = {**PARAMS, **(params or {})}
    return [
        {"name": "shank", "group": "shank", "a": (150, 0, 0), "b": (0, 0, 0),
         "outer": p["shank_w"], "wall": p["shank_t"], "size_params": ["shank_w", "shank_t"]},
        {"name": "arm", "group": "shank", "a": (0, 0, 0), "b": (-300, 0, 0),
         "outer": p["shank_w"], "wall": p["shank_t"], "size_params": ["shank_w", "shank_t"]},
        {"name": "rail", "group": "rails", "a": (-300, 0, 0), "b": (-1000, 0, 0),
         "outer": p["rail_w"], "wall": p["rail_t"], "size_params": ["rail_w", "rail_t"]},
    ]


def supports(params):
    return [{"at": (0, 0, 0), "fix": ["ux", "uy", "uz", "rx"]}, {"at": (150, 0, 0), "fix": ["uy", "uz"]}]


def build(params):
    import cadquery as cq
    p = {**PARAMS, **(params or {})}
    return cq.Workplane("XY").box(1150, p["rail_w"], p["rail_w"]).translate((-425, 0, 0))
'''


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a cantilever", base=str(tmp_path / "designs"))
    s.write_part("frame", FRAME, intent="a shank and a rail")
    return s


def test_tube_sizes_map_to_the_catalog():
    assert fs.section_key(50.8, 3.175) == "2x2x1/8"
    assert fs.section_key(50.8, 25.4) == "2x2xsolid"
    with pytest.raises(ValueError, match="no catalog tube"):
        fs.section_key(51.0, 3.0)


def test_the_structure_is_read_from_the_part_in_its_own_process(store):
    fd = fs.frame_def(store, "frame")
    assert [m["name"] for m in fd["members"]] == ["shank", "arm", "rail"]
    assert len(fd["supports"]) == 2


def test_ends_that_meet_become_one_joint_and_the_load_goes_on_the_rails(store):
    built = fs.build_spec(fs.frame_def(store, "frame"), load_lb=100, factor=2.5)
    spec = built["spec"]
    assert len(spec["nodes"]) == 4                                  # 3 members, 4 distinct ends
    assert {s["node"] for s in spec["supports"]} == {0, 1}
    rail_loads = [ld for ld in spec["loads"] if ld["member"] == 2]
    assert {ld["case"] for ld in rail_loads} == {"standing", "driving"}
    assert rail_loads[0]["total"][2] == pytest.approx(-100 * fs.LB)
    assert spec["cases"]["driving"]["factor"] == 2.5


def test_a_study_reports_what_the_hitch_holds_and_sweeps_lighter(store):
    rec = fs.study(store, "frame", load_lb=100, factor=2.5, min_safety=2.0)
    d = rec["drawn"]
    # 100 lb spread from 300 to 1000 mm out: its moment about the mouth is 100 lb x 650 mm ≈ 2559 lb-in,
    # plus the tubes' own weight
    assert d["receiver"]["standing"]["moment_lbin"] > 100 * 650 / 25.4
    assert d["receiver"]["driving"]["moment_lbin"] == pytest.approx(
        2.5 * d["receiver"]["standing"]["moment_lbin"], rel=0.02)
    assert d["safety"] > 0 and d["deflection_mm"] > 0
    assert len(rec["stations"]) >= 2
    assert all(set(st["design"]) == {"shank", "rails"} for st in rec["stations"])
    assert store.history("frame")[-1]["action"] == "studied"


def test_the_shank_keeps_its_outer_size_so_it_still_fits_the_receiver(store):
    rec = fs.study(store, "frame", load_lb=100, factor=2.5, min_safety=2.0)
    assert all(tube_size(st["design"]["shank"])[0] == pytest.approx(50.8) for st in rec["stations"])


def test_using_a_design_writes_its_tubes_into_params(store):
    rec = fs.study(store, "frame", load_lb=100, factor=2.5, min_safety=2.0)
    last = rec["stations"][-1]
    got = fs.adopt(store, rec["id"], last["index"])
    now = aero.read_params(store.read_script("frame"))
    outer, wall = tube_size(last["design"]["rails"])
    assert now["rail_w"] == pytest.approx(outer, abs=1e-3)                       # scripts hold 0.001 mm
    assert now["rail_t"] == pytest.approx(min(wall, outer / 2), abs=1e-3)
    assert store.is_scripted("frame") and got["version"] == 2


def test_a_part_without_members_is_refused_with_a_reason(tmp_path):
    s = DesignStore.create("plain", base=str(tmp_path / "designs"))
    s.write_part("box", "PARAMS = {'w': 1.0}\n\ndef build(params):\n    import cadquery as cq\n"
                        "    return cq.Workplane().box(1, 1, 1)\n")
    with pytest.raises(ValueError, match="members"):
        fs.frame_def(s, "box")


def test_a_part_without_supports_is_refused_with_a_reason(store):
    store.write_part("frame", FRAME.replace("def supports(params):", "def _not_supports(params):"),
                     action="refine")
    with pytest.raises(ValueError, match="supports"):
        fs.frame_def(store, "frame")


def test_run_ids_cannot_escape_the_design(store):
    assert fs.load_run(store, "../../x") is None
    with pytest.raises(ValueError):
        fs.station_path(store, "../x", 0)


# --- CALI-43: carrying what the design is built from -----------------------------------------
CARGO = '''PARAMS = {"w": 100.0}


def build(params):
    import cadquery as cq
    return cq.Workplane("XY").box(100, 100, 100).translate((-650, 0, 100))


def construction(params, build=None):
    return [{"name": "cargo", "kind": "lump", "mass": 100 / 2.20462262, "at": (-650, 0, 100)}]
'''

LAYOUT = FRAME.replace('''def members(params):''', '''LAYOUTS = {"short": {"rail_w": 25.4}, "as is": {"rail_w": 50.8}}


def members(params):''')


def test_points_land_on_the_member_that_carries_them_and_keep_their_moment(store):
    fd = fs.frame_def(store, "frame")
    fd["members"][2]["carries"] = True                      # only the rail
    built = fs.build_spec(fd, points=[((-650.0, 40.0, 100.0), 10.0), ((-1000.0, 0.0, 0.0), 5.0)])
    spec = built["spec"]
    standing = [ld for ld in spec["loads"] if ld["case"] == "standing"]
    assert {ld["member"] for ld in standing} == {2}
    # the rail runs from x=-300 to x=-1000: the loads sit at 350/700 and the far end
    assert sorted(ld["at"] for ld in standing) == pytest.approx([0.5, 1.0])
    assert sum(ld["force"][2] for ld in standing) == pytest.approx(-15.0 * fs.GRAVITY)
    assert built["applied"]["lands"][0] == pytest.approx((10 * -650 + 5 * -1000) / 15)
    assert built["applied"]["reach_mm"] == pytest.approx(40, abs=1)           # the 40 mm sideways hop
    # members stay whole (whittle checks buckling over a member's own length): 3 members, 4 ends
    assert len(spec["members"]) == 3 and len(spec["nodes"]) == 4


def test_a_frame_carries_the_design_as_built(store):
    store.write_part("cargo", CARGO, intent="100 lb of cargo")
    rec = fs.study(store, "frame", from_design=True, payload_lb=0, min_safety=2.0)
    assert rec["carrying"]["mass_lb"] == pytest.approx(100, abs=0.1)
    assert rec["carrying"]["shift_in"] == pytest.approx(0, abs=0.05)
    flat = fs.study(store, "frame", load_lb=100, min_safety=2.0)
    # the same 100 lb whose centre is 650 mm out: the same moment on the hitch, give or take the cuts
    assert rec["drawn"]["receiver"]["standing"]["moment_lbin"] == pytest.approx(
        flat["drawn"]["receiver"]["standing"]["moment_lbin"], rel=0.01)


def test_a_frame_names_its_layouts_and_a_study_records_which_it_ran(tmp_path):
    s = DesignStore.create("layouts", base=str(tmp_path / "designs"))
    s.write_part("frame", LAYOUT, intent="a shank and a rail")
    assert fs.read_layouts(LAYOUT) == {"short": {"rail_w": 25.4}, "as is": {"rail_w": 50.8}}
    assert fs.layout_name(LAYOUT, None) == "as is"
    rec = fs.study(s, "frame", load_lb=50, min_safety=2.0, params={"rail_w": 25.4})
    assert rec["layout"] == "short" and rec["params"] == {"rail_w": 25.4}
    assert rec["drawn"]["mass_lb"] < fs.study(s, "frame", load_lb=50, min_safety=2.0)["drawn"]["mass_lb"]
    assert aero.shape_signature(LAYOUT) == aero.shape_signature(FRAME)


def test_the_hardest_joint_counts_welded_ends_not_a_tube_running_through(tmp_path):
    from whittle import FrameStudy
    # a 2 in spine out to x=-1000 with 1 in arms either side at x=-600: the arms are welded to it
    fd = {"members": [
        {"name": "shank", "group": "shank", "a": (150, 0, 0), "b": (0, 0, 0), "outer": 50.8, "wall": 6.35},
        {"name": "spine_a", "group": "spine", "a": (0, 0, 0), "b": (-600, 0, 0), "outer": 50.8, "wall": 3.175},
        {"name": "spine_b", "group": "spine", "a": (-600, 0, 0), "b": (-1000, 0, 0), "outer": 50.8, "wall": 3.175},
        {"name": "arm_l", "group": "x", "a": (-600, 0, 0), "b": (-600, 500, 0), "outer": 25.4, "wall": 2.108, "carries": True},
        {"name": "arm_r", "group": "x", "a": (-600, 0, 0), "b": (-600, -500, 0), "outer": 25.4, "wall": 2.108, "carries": True}],
        "supports": [{"at": (0, 0, 0), "fix": ["ux", "uy", "uz", "rx"]}, {"at": (150, 0, 0), "fix": ["uy", "uz"]}]}
    built = fs.build_spec(fd, points=[((-600, 450, 0), 5.0), ((-600, -450, 0), 5.0)])
    (joint,) = fs._joints(FrameStudy.from_dict(built["spec"]).analyze(), built)
    assert joint["worst_member"] in ("arm_l", "arm_r")           # not the spine passing through
    # 5 kg at 450 mm out on each arm, x2.5 on a bump, plus the arm's own weight
    assert joint["bending_lbin"] == pytest.approx(2.5 * 5 * 2.20462 * 450 / 25.4, rel=0.1)
