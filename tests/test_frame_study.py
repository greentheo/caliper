"""CALI-40 — sizing a tube frame with whittle's FrameStudy, from the tubes a part declares."""

import os

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


# --- CALI-44: walls that carry load ----------------------------------------------------------
def test_a_sandwich_wall_is_a_deep_beam_in_its_skins_material():
    w = {"name": "w", "depth": 1000.0, "skins": ["fiberglass"], "core": "xps", "core_t": 25.4}
    section, material, check = fs.wall_section(w, 1500.0)
    from caliper import materials as M
    sk, core = M.SKINS["fiberglass"], M.SHEETS["xps"]["mech"]
    t_eq = sk["t"] + 25.4 * core["E"] / sk["E"]
    assert section["iy"] == pytest.approx(t_eq * 1000.0 ** 3 / 12)
    # its shear stiffness is the layers' G·t, whatever material it's written in
    assert material["shear_modulus"] * section["shear_z"] == pytest.approx(1000.0 * (sk["t"] * sk["G"] + 25.4 * core["G"]))
    # a thin glass skin on foam wrinkles well before it breaks
    assert material["strength"] < sk["strength"] / 3
    assert section["mass_area"] == 0.0 and check["core_t"] == 25.4


SHELLED = CARGO.replace('''def construction(params, build=None):''', '''def shell(params, build=None):
    """a wall across the rail's far end, in two halves that meet over it"""
    w = {"depth": 300.0, "skins": ["pmf"], "core": "xps", "core_t": 25.4}
    return [dict(w, name="wall_a", a=(-1000, -500, 0), b=(-1000, 0, 0)),
            dict(w, name="wall_b", a=(-1000, 0, 0), b=(-1000, 500, 0))]


def construction(params, build=None):''')


def test_walls_carry_what_stands_on_them_and_are_fastened_to_the_frame(store):
    store.write_part("cargo", SHELLED.replace('"at": (-650, 0, 100)}]', '"at": (-1000, 400, 100)}]'), intent="cargo with a wall")
    from caliper import construction as C
    loads = C.design_loads(store, skip=("frame",), walls=True)
    assert [w["name"] for w in loads["shell"]] == ["wall_a", "wall_b"]
    assert all(via == "walls" for _, _, via in loads["points"])          # a lump, not a floor: via the wall
    rec = fs.study(store, "frame", from_design=True, payload_lb=0, min_safety=2.0)
    assert rec["walls"] and [w["name"] for w in rec["carrying"]["walls"]] == ["wall_a", "wall_b"]
    assert rec["carrying"]["fastened"] == [[-1000.0, 0.0, 0.0]]          # its middle sits on the rail's end
    d = rec["drawn"]
    assert all(w["skin_safety"] > 0 and w["foam_safety"] > 0 for w in d["walls"])
    assert d["fixing"]["force_lb"] == pytest.approx(100 * 2.5, rel=0.05)    # all of it, on a bump
    # the walls are what the box is built from: the sweep sizes only the tubes, the drawing shows only steel
    assert "walls" not in rec["catalogs"] and all("walls" not in st["design"] for st in rec["stations"])
    tubes = fs.study(store, "frame", from_design=True, payload_lb=0, min_safety=2.0, walls=False)
    assert not tubes["walls"] and "walls" not in tubes["drawn"]


# --- CALI-46: gusset plates ------------------------------------------------------------------
CORNERED = '''PARAMS = {"w": 50.8}

GUSSETS = {"jog": ("riser", "shank")}


def members(params):
    t = {"outer": 50.8, "wall": 3.175}
    return [
        {"name": "shank", "group": "shank", "a": (150, 0, 0), "b": (0, 0, 0), **t, "size_params": ["w", "w"]},
        {"name": "riser", "group": "riser", "a": (0, 0, 0), "b": (0, 0, 250), **t},
        {"name": "rail", "group": "rail", "a": (0, 0, 250), "b": (-800, 0, 250), **t, "carries": True},
    ]


def supports(params):
    return [{"at": (150, 0, 0), "fix": "all"}]


def construction(params, build=None):
    out = []
    for name, pl in (globals().get("PLATES") or {}).items():
        out.append({"name": f"gusset_{name}", "kind": "lump", "mass": pl["mass_kg"] * pl["count"],
                    "at": tuple(pl["placement"]["origin"])})
    return out


def build(params):
    import cadquery as cq
    return cq.Workplane("XY").box(50, 50, 50)
'''


def test_gusset_plates_are_sized_written_into_the_frame_and_weighed(tmp_path):
    from whittle import FrameStudy
    if not hasattr(FrameStudy, "gusset"):
        pytest.skip("whittle has no plate mode here")
    s = DesignStore.create("a corner", base=str(tmp_path / "designs"))
    s.write_part("frame", CORNERED, intent="a shank, a riser and a rail")
    s.write_part("cargo", CARGO.replace("(-650, 0, 100)", "(-600, 0, 300)"), intent="100 lb at the end of the rail")
    assert fs.read_gussets(CORNERED) == {"jog": ("riser", "shank")}
    rec = fs.gussets(s, "frame", thickness=4.7625, payload_lb=0, min_safety=2.0, resolution=30)
    (j,) = rec["joints"].values()
    assert j["members"] == ["riser", "shank"] and j["stations"]
    pick = j["stations"][j["pick"]]
    assert pick["safety"] >= 2.0 or pick["safety"] == max(st["safety"] for st in j["stations"])
    assert os.path.exists(os.path.join(fs.gussets_dir(s), rec["id"], "jog", "station_00.dxf"))
    from caliper import construction as C
    before = C.report(s, "frame")["mass_kg"]
    got = fs.adopt_gussets(s, rec["id"])
    script = s.read_script("frame")
    assert "PLATES = {" in script and got["version"] == 2
    assert aero.shape_signature(script) == aero.shape_signature(CORNERED)
    assert C.report(s, "frame")["mass_kg"] == pytest.approx(before + 2 * pick["mass_kg"], abs=0.01)
    assert fs.adopt_gussets(s, rec["id"])["version"] == 3            # adopting again replaces PLATES, once
    assert s.read_script("frame").count("PLATES = {") == 1
