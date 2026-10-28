"""CALI-41 — what a part is built from: its weight, centre of gravity, and bill of materials."""

import pytest

from caliper import aero, construction as C, materials as M
from caliper.design import DesignStore

IN = 25.4

# A 48 x 24 x 24 in open-top box: a 1/2 in plywood floor, four 1 in foam walls with PMF outside, two
# 2x2 posts and a lump of hardware. Numbers chosen so the hand arithmetic below stays readable.
BOX = '''PARAMS = {
    "w": 1219.2,   # 48 in
    "d": 609.6,    # 24 in
    "h": 609.6,    # 24 in
}


def build(params):
    import cadquery as cq
    p = {**PARAMS, **(params or {})}
    return cq.Workplane("XY").box(p["d"], p["w"], p["h"]).translate((-p["d"] / 2, 0, p["h"] / 2))


# How it's built
BUILD = {
    "floor_t": 12.7,     # 1/2 in
    "walls": "xps",
    "skin": "pmf",       # outside of the walls
    "posts": "2x2",
    "hardware": 1.0,     # kg
}


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    w, d, h = p["w"], p["d"], p["h"]
    hw = w / 2
    items = [{"name": "floor", "group": "floor", "kind": "sheet", "material": "plywood",
              "thickness": b["floor_t"], "outline": [(0, -hw, 0), (-d, -hw, 0), (-d, hw, 0), (0, hw, 0)]}]
    for name, x in (("front", 0.0), ("back", -d)):
        items.append({"name": name, "kind": "sheet", "material": b["walls"], "thickness": 25.4,
                      "outline": [(x, -hw, 0), (x, hw, 0), (x, hw, h), (x, -hw, h)], "covers": [b["skin"]]})
    for name, y in (("left", hw), ("right", -hw)):
        items.append({"name": name, "kind": "sheet", "material": b["walls"], "thickness": 25.4,
                      "outline": [(0, y, 0), (-d, y, 0), (-d, y, h), (0, y, h)], "covers": [b["skin"]]})
    if b["posts"] != "none":
        for x, y in ((-20, hw - 20), (-(d - 20), -(hw - 20))):          # opposite corners
            items.append({"name": "post", "kind": "stick", "material": "lumber", "size": b["posts"],
                          "a": (x, y, 0), "b": (x, y, h)})
    items.append({"name": "hardware", "kind": "lump", "mass": b["hardware"], "at": (-d / 2, 0, h / 2)})
    return items


def members(params):
    return [{"name": "shank", "group": "shank", "a": (300, 0, 0), "b": (0, 0, 0), "outer": 50.8, "wall": 3.175}]


def supports(params):
    return [{"at": (100, 0, 0), "fix": ["ux", "uy", "uz", "rx"]}]
'''


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a crate", base=str(tmp_path / "designs"))
    s.write_part("crate", BOX, intent="an open crate")
    return s


def _expected_lb(floor_t=12.7, posts=True, skin=True):
    ft2 = lambda w, h: w * h / 144.0                                        # noqa: E731
    floor = ft2(48, 24) * floor_t / IN / 12 * M.SHEETS["plywood"]["density"] / 16.0185
    walls = 2 * ft2(48, 24) + 2 * ft2(24, 24)
    foam = walls / 12 * M.SHEETS["xps"]["density"] / 16.0185
    pmf = walls * M.COVERINGS["pmf"]["areal"] * M.LB_KG / 10.7639 if skin else 0
    post = 2 * (24 / 12) * (1.5 * 1.5 / 144) * M.STICKS["lumber"]["density"] / 16.0185 if posts else 0
    return floor + foam + pmf + post + 1.0 * M.LB_KG


# --- geometry ------------------------------------------------------------------
def test_a_polygons_area_centroid_and_normal():
    area, c, n = C.polygon([(0, 0, 0), (100, 0, 0), (100, 50, 0), (0, 50, 0)])
    assert area == pytest.approx(5000) and c == pytest.approx((50, 25, 0)) and n == pytest.approx((0, 0, 1))
    # an L (concave): the centroid is pulled toward the long leg
    area, c, _ = C.polygon([(0, 0, 0), (100, 0, 0), (100, 10, 0), (10, 10, 0), (10, 100, 0), (0, 100, 0)])
    assert area == pytest.approx(1900)
    assert c[0] == pytest.approx(c[1]) and c[0] < 30


def test_a_tilted_panel_flattens_to_its_true_size():
    # a 1000 x 500 panel leaning back at 30 degrees
    import math
    z, x = 500 * math.cos(math.radians(30)), 500 * math.sin(math.radians(30))
    pts = [(0, 0, 0), (0, 1000, 0), (-x, 1000, z), (-x, 0, z)]
    assert C.polygon(pts)[0] == pytest.approx(500_000)
    assert C.min_rect(C.flatten(pts)) == pytest.approx((1000, 500))


def test_nominal_thickness_names():
    assert M.nominal(9.525) == "3/8 in" and M.nominal(25.4) == "1 in" and M.nominal(38.1) == "1 1/2 in"


# --- a part's take-off ---------------------------------------------------------
def test_a_part_is_weighed_from_what_it_declares(store):
    r = C.report(store, "crate")
    assert r["source"] == "construction"
    assert r["mass_lb"] == pytest.approx(_expected_lb(), rel=0.005)
    labels = {m["label"] for m in r["materials"]}
    assert {"1/2 in softwood plywood", "1 in XPS foam board", "poor man's fiberglass",
            "2x2 SPF lumber", "hardware"} <= labels
    # the heavy floor at z=0 pulls the centre of gravity below the middle of the walls
    assert 0 < r["cog"][2] < 609.6 / 2
    assert r["cog"][1] == pytest.approx(0, abs=1e-6)


def test_the_bill_of_materials_counts_sheets_sticks_and_coverings(store):
    bom = C.report(store, "crate")["bom"]
    sheets = {g["material"]: g for g in bom["sheets"]}
    assert sheets["plywood"]["count"] == 1
    # 48x24, 48x24, 24x24, 24x24 of foam fit on one 4x8 sheet... except for kerf: two rows of 48+24
    assert sheets["xps"]["count"] == 2
    assert sheets["xps"]["area_ft2"] == pytest.approx(24.0, abs=0.1)
    (posts,) = bom["sticks"]
    assert posts["label"] == "2x2 SPF lumber" and posts["count"] == 1 and len(posts["cuts"]) == 2
    (pmf,) = bom["coverings"]
    assert pmf["area_ft2"] == pytest.approx(24.0, abs=0.1)
    assert pmf["canvas_yd"] == pytest.approx(24 * 1.1 / 5 / 3, abs=0.1)
    assert pmf["glue_gal"] > 0 and pmf["paint_gal"] > 0
    assert bom["lumps"] == [{"name": "hardware", "mass_kg": 1.0}]


def test_a_what_if_changes_the_weight_without_touching_the_script(store):
    before = store.read_script("crate")
    r = C.report(store, "crate", {"floor_t": 6.35, "posts": "none"})
    assert r["mass_lb"] == pytest.approx(_expected_lb(floor_t=6.35, posts=False), rel=0.005)
    assert r["changed"] == {"floor_t": 6.35, "posts": "none"}
    assert store.read_script("crate") == before and store.design.part("crate").version == 1


def test_using_choices_writes_build_and_keeps_everything_else(store):
    got = C.adopt(store, "crate", {"floor_t": 9.525, "skin": "none"})
    assert got["version"] == 2 and got["changed"] == {"floor_t": 9.525, "skin": "none"}
    script = store.read_script("crate")
    assert '"floor_t": 9.525,     # 1/2 in' in script                # comment kept (now stale, but kept)
    assert '"skin": "none",' in script
    assert C.read_build(script)["skin"] == "none"
    assert aero.read_params(script) == aero.read_params(BOX)
    assert C.report(store, "crate")["mass_lb"] == pytest.approx(
        _expected_lb(floor_t=9.525, skin=False), rel=0.005)
    assert store.history("crate")[-1]["action"] == "build"


def test_using_the_same_choices_is_not_a_revision(store):
    assert C.adopt(store, "crate", {"floor_t": 12.7})["changed"] == {}
    assert store.design.part("crate").version == 1


def test_choices_offer_materials_sizes_and_thicknesses():
    ch = C.choices({"walls": "xps", "posts": "2x2", "skin_in": "none", "floor_t": 9.525, "hardware": 1.0})
    assert "eps" in ch["walls"]["options"]
    assert "none" in ch["posts"]["options"] and "2x4" in ch["posts"]["options"]
    assert "pmf" in ch["skin_in"]["options"]
    assert 12.7 in ch["floor_t"]["options"] and ch["floor_t"]["labels"][9.525] == "3/8 in"
    assert ch["hardware"]["kind"] == "number"


def test_a_shape_study_still_applies_after_the_construction_changes(store):
    sig = aero.shape_signature(BOX)
    assert sig == aero.shape_signature(C.write_build(BOX, {"floor_t": 6.35, "walls": "eps"}))
    start = BOX.index("\n\n# How it's built")
    assert sig == aero.shape_signature(BOX[:start])                  # as if it had never been declared
    assert sig != aero.shape_signature(BOX.replace('p["h"] / 2))', 'p["h"]))'))


# --- the design together ---------------------------------------------------------
def test_a_frame_is_weighed_from_its_tubes():
    rows = C.takeoff(C.from_members([{"name": "t", "a": (0, 0, 0), "b": (304.8, 0, 0),
                                      "outer": 50.8, "wall": 3.175}]))
    # 2x2x1/8 with rounded corners: a catalog says 3.05 lb/ft
    assert rows[0]["mass_kg"] * M.LB_KG == pytest.approx(3.05, rel=0.02)
    assert rows[0]["label"] == "2x2x1/8 steel tube"
    assert C.tube_label(50.8, 25.4) == "2x2 solid steel bar"


def test_the_balance_takes_the_moment_about_the_first_support(store):
    b = C.balance(store)
    (crate,) = b["parts"]
    assert b["hitch"] == [100.0, 0.0, 0.0]
    # the crate's centre of gravity is 12 in behind its front (x=0), which is 100 mm behind the hitch
    assert crate["arm_in"] == pytest.approx((100 + 304.8) / IN, abs=0.1)
    assert b["moment_lbin"] == pytest.approx(b["mass_lb"] * b["arm_in"], rel=0.01)


def test_a_payload_sits_on_the_floor(store):
    empty = C.balance(store)
    loaded = C.balance(store, payload_lb=100)
    assert loaded["mass_lb"] == pytest.approx(empty["mass_lb"] + 100, abs=0.2)
    assert loaded["parts"][-1]["part"] == "payload"
    assert loaded["parts"][-1]["cog"][2] == pytest.approx(0, abs=0.5)      # on the floor
    assert loaded["moment_lbin"] > empty["moment_lbin"]


def test_what_ifs_reach_the_balance(store):
    light = C.balance(store, {"crate": {"floor_t": 6.35}})
    assert light["mass_lb"] < C.balance(store)["mass_lb"]


# --- refusals -------------------------------------------------------------------
def test_a_part_that_doesnt_say_what_its_built_from_is_refused(tmp_path):
    s = DesignStore.create("plain", base=str(tmp_path / "designs"))
    s.write_part("box", "PARAMS = {'w': 1.0}\n\ndef build(params):\n    import cadquery as cq\n"
                        "    return cq.Workplane().box(1, 1, 1)\n")
    with pytest.raises(ValueError, match="construction"):
        C.report(s, "box")
    assert C.balance(s)["parts"] == []


def test_an_unknown_material_is_named(store):
    with pytest.raises(ValueError, match="unknown sheet material 'balsa'"):
        C.report(store, "crate", {"walls": "balsa"})


def test_a_construction_that_raises_reports_why(store):
    store.write_part("crate", BOX.replace("hw = w / 2", "hw = w / 0"), action="refine")
    with pytest.raises(ValueError, match="ZeroDivisionError"):
        C.report(store, "crate")


def test_writing_an_entry_build_doesnt_have_is_refused():
    with pytest.raises(KeyError, match="'glitter'"):
        C.write_build(BOX, {"glitter": 1})
