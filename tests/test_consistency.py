"""CALI-54 — what a part says it's built from is checked against the solid it builds."""

import pytest

from caliper import authoring, consistency, sandbox
from caliper.spec import Assertion, Spec

pytest.importorskip("cadquery")

#: A step stool in 3/4 in plywood: a top on two sides, a stretcher between them. build() is the panels,
#: and construction() lists the same panels by one face each.
STOOL = '''PARAMS = {
    "width": 355.6,    # 14 in
    "depth": 254.0,    # 10 in
    "height": 254.0,   # 10 in
    "inset": 25.4,     # 1 in: the sides in from the top's ends
    "rail_lo": 101.6,  # 4 in
    "rail_hi": 177.8,  # 7 in
}

BUILD = {"ply_t": 19.05}   # 3/4 in


def _panels(p, t):
    """Each panel as (name, its outer face's corners, which way its thickness goes)."""
    w, d, h = p["width"], p["depth"], p["height"]
    xo = w / 2 - p["inset"]
    top = [(-w / 2, -d / 2, h), (w / 2, -d / 2, h), (w / 2, d / 2, h), (-w / 2, d / 2, h)]
    sides = [[(s * xo, -d / 2 + 12.7, 0), (s * xo, d / 2 - 12.7, 0), (s * xo, d / 2 - 12.7, h - t),
              (s * xo, -d / 2 + 12.7, h - t)] for s in (-1, 1)]
    xi = xo - t
    rail = [(-xi, -t / 2, p["rail_lo"]), (xi, -t / 2, p["rail_lo"]), (xi, -t / 2, p["rail_hi"]),
            (-xi, -t / 2, p["rail_hi"])]
    return [("top", top, (0, 0, -1)), ("left side", sides[0], (1, 0, 0)),
            ("right side", sides[1], (-1, 0, 0)), ("rail", rail, (0, 1, 0))]


def build(params):
    import cadquery as cq
    p = {**PARAMS, **(params or {})}
    t = BUILD["ply_t"]
    out = None
    for _, face, (nx, ny, nz) in _panels(p, t):
        xs, ys, zs = zip(*face)
        lo = [min(xs) + min(nx * t, 0), min(ys) + min(ny * t, 0), min(zs) + min(nz * t, 0)]
        hi = [max(xs) + max(nx * t, 0), max(ys) + max(ny * t, 0), max(zs) + max(nz * t, 0)]
        box = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(tuple(lo))
        out = box if out is None else out.union(box)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    return [{"name": name, "kind": "sheet", "material": "plywood", "thickness": b["ply_t"], "outline": face,
             "covers": ["paint", "paint"]} for name, face, _ in _panels(p, BUILD["ply_t"])]
'''


def _checked(script):
    run = sandbox.run_script(script, {})
    assert run.ok, run.feedback
    return {r.id: r for r in consistency.check(run.declared, run.geometry)}


def test_a_part_built_from_what_it_says_passes():
    got = _checked(STOOL)
    assert set(got) == {"construction_inside", "construction_on_its_face", "construction_covers", "construction_volume"}
    assert all(r.status == "pass" for r in got.values()), [r.detail for r in got.values()]
    assert got["construction_volume"].actual == pytest.approx(1.0, abs=0.02)
    assert got["construction_covers"].actual > 0.99


def test_a_panel_left_where_it_isnt_is_named_with_where():
    moved = STOOL.replace('"outline": face,', '"outline": [(x, y + (300 if name == "rail" else 0), z) for x, y, z in face],')
    got = _checked(moved)
    inside = got["construction_inside"]
    assert inside.status == "fail" and inside.detail.startswith("rail: 100% of it is outside the solid")
    assert "left side" not in inside.detail
    assert got["construction_covers"].status == "fail"          # and the rail in the solid is on no piece now


def test_a_piece_left_out_of_the_list_shows_up_as_uncovered_solid():
    got = _checked(STOOL.replace('for name, face, _ in _panels(p, BUILD["ply_t"])]',
                                 'for name, face, _ in _panels(p, BUILD["ply_t"]) if name != "right side"]'))
    assert got["construction_inside"].status == "pass"
    covers = got["construction_covers"]
    assert covers.status == "fail" and covers.actual < 0.9
    assert "within x 133..152," in covers.detail             # the right side, 3/4 in thick at x = 152.4


def test_a_panel_built_thicker_than_its_sheet_is_left_uncovered():
    # seen live: the designer's stool had a riser two sheets thick in build(), and one in construction()
    thick = STOOL.replace("for _, face, (nx, ny, nz) in _panels(p, t):",
                          "for name, face, (nx, ny, nz) in _panels(p, t):\n        k = 2 if name == 'rail' else 1")
    thick = thick.replace("nx * t", "nx * t * k").replace("ny * t", "ny * t * k").replace("nz * t", "nz * t * k")
    got = _checked(thick)
    assert got["construction_inside"].status == "pass" and got["construction_volume"].status == "pass"
    covers = got["construction_covers"]
    assert covers.status == "fail" and "y 12..29," in covers.detail       # the rail's far face, a sheet behind it


def test_a_sheet_listed_thicker_than_it_is_built_fails_on_volume():
    got = _checked(STOOL.replace('"thickness": b["ply_t"]', '"thickness": 2 * b["ply_t"]'))
    vol = got["construction_volume"]
    assert vol.status == "fail" and vol.actual == pytest.approx(2.0, abs=0.05)
    assert "thickness" in vol.detail and "top" in vol.detail


def test_a_declaration_that_raises_or_names_an_unknown_material_says_so():
    (r,) = consistency.check({"error": "construction() raised KeyError: 'ply'"}, None)
    assert r.id == "construction_reads" and r.status == "error" and "KeyError" in r.detail
    got = _checked(STOOL.replace('"material": "plywood"', '"material": "balsa"'))
    assert got["construction_reads"].status == "fail"
    assert "unknown sheet material 'balsa'" in got["construction_reads"].detail
    run = sandbox.run_script(STOOL.replace('b = {**BUILD', 'b = {**BUILDS'), {})
    assert run.ok and "NameError" in run.declared["error"]


def test_a_part_that_declares_nothing_has_nothing_to_check():
    run = sandbox.run_script("def build(params):\n    import cadquery as cq\n    return cq.Workplane().box(1, 1, 1)\n")
    assert run.ok and run.declared is None
    assert consistency.check(run.declared, run.geometry) == []


def test_a_tube_frame_is_checked_by_its_centrelines_even_when_the_tubes_are_hollow():
    frame = '''PARAMS = {"w": 50.8, "t": 3.175}


def members(params):
    p = {**PARAMS, **(params or {})}
    return [{"name": "rail", "group": "rails", "a": (0, 0, 0), "b": (-1000, 0, 0), "outer": p["w"], "wall": p["t"]}]


def build(params):
    import cadquery as cq
    p = {**PARAMS, **(params or {})}
    tube = cq.Workplane("YZ").rect(p["w"], p["w"]).rect(p["w"] - 2 * p["t"], p["w"] - 2 * p["t"]).extrude(1000)
    return tube.translate((-1000, 0, 0))
'''
    got = _checked(frame)
    assert all(r.status == "pass" for r in got.values()), [r.detail for r in got.values()]
    assert _checked(frame.replace('"b": (-1000, 0, 0)', '"b": (1000, 0, 0)'))["construction_inside"].status == "fail"


def test_a_mismatch_fails_the_round_and_the_designer_is_told_what_to_fix():
    broken = STOOL.replace('"outline": face,', '"outline": [(x, y, z + 500) for x, y, z in face],')
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return broken if len(seen) == 1 else STOOL

    spec = Spec(part="stool", intent="a step stool", assertions=[Assertion(id="one_body", expr="body_count == 1")])
    res = authoring.improve(spec, author=author, max_rounds=3)
    assert res.ok and res.rounds == 2
    assert "construction_inside" in seen[1] and "top: 100% of it is outside the solid" in seen[1]
    assert {r.id for r in res.report.results} >= {"one_body", "construction_inside", "construction_covers"}


def test_the_prompt_carries_the_reference_and_every_material():
    from caliper import materials

    prompt = authoring.system_prompt()
    with open(authoring.REFERENCE) as f:
        assert f.read() in prompt
    for key in (*materials.SHEETS, *materials.STICKS, *materials.COVERINGS):
        assert f"  - {key}: " in prompt


def test_a_filled_box_round_its_panels_fails_when_its_strength_is_checked_in_3d():
    """CALI-83: Theo's stool came out as a solid block while construction() listed its panels. Every panel lies in
    the block and covers its surface, so only the volume shows it; with loads() the strength check analyses the
    solid, so it fails. Without loads() (the camper's lofted box, kept for drag) it's left alone."""
    pytest.importorskip("cadquery")
    from caliper import sandbox

    from .test_load_study import BOX_STOOL

    filled = BOX_STOOL.replace('''    out = None
    for lo, hi in _boxes(p, BUILD["t"]).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out''', '''    return cq.Workplane().box(p["w"], p["d"], p["h"], centered=False)''')
    assert filled != BOX_STOOL
    run = sandbox.run_script(filled, timeout=120)
    got = {r.id: r for r in consistency.check(run.declared, run.geometry)}
    assert got["construction_inside"].passed                  # (its bare underside fails covers too: no bottom panel)
    vol = got["construction_volume"]
    assert not vol.passed and vol.actual < 0.67 and "build() is filled in" in vol.detail
    # either cause, said (#64 item 12): the box stool's undeclared solid legs read as "filled in" alone
    assert "build() is filled in or a piece isn't in construction()" in vol.detail and "add the missing piece" in vol.detail
    assert "the solid has more in it than its pieces" not in vol.detail          # said once, not three times (#209)
    # the same block without loads(): a shape kept for its outside, weighed from its pieces
    run = sandbox.run_script(filled.split("def loads(")[0], timeout=120)
    assert {r.id: r for r in consistency.check(run.declared, run.geometry)}["construction_volume"].passed


#: A 4 in cube from six 3/4 in panels, with what it must hold: built hollow, as it would be, or filled solid.
CUBE = '''import cadquery as cq

S, T = 101.6, 19.05
FILLED = False


def build(params):
    out = cq.Workplane().box(S, S, S, centered=False)
    if not FILLED:
        out = out.cut(cq.Workplane().box(S - 2 * T, S - 2 * T, S - 2 * T, centered=False).translate((T, T, T)))
    return out


def construction(params, build=None):
    # butt joints: the top and bottom whole, the sides between them, the front and back between the sides
    a, b = T, S - T
    faces = {"bottom": [(0, 0, 0), (S, 0, 0), (S, S, 0), (0, S, 0)], "top": [(0, 0, S), (S, 0, S), (S, S, S), (0, S, S)],
             "left": [(0, 0, a), (0, S, a), (0, S, b), (0, 0, b)], "right": [(S, 0, a), (S, S, a), (S, S, b), (S, 0, b)],
             "front": [(a, 0, a), (b, 0, a), (b, 0, b), (a, 0, b)], "back": [(a, S, a), (b, S, a), (b, S, b), (a, S, b)]}
    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": T, "outline": v} for k, v in faces.items()]


def loads(params, build=None):
    return [{"name": "a foot", "lb": 50, "lo": (30, 30, S - 2), "hi": (70, 70, S)}]
'''


def test_a_small_filled_box_is_caught_like_a_big_one():
    """CALI-87 (#63, finding 11): a 4 in box's panels are most of its volume, so a filled one passed the volume
    floor. What's filled is solid that's in no piece at all."""
    hollow = sandbox.run_script(CUBE, timeout=120)
    got = {r.id: r for r in consistency.check(hollow.declared, hollow.geometry)}
    assert got["construction_volume"].passed, got["construction_volume"].detail
    filled = sandbox.run_script(CUBE.replace("FILLED = False", "FILLED = True"), timeout=120)
    got = {r.id: r for r in consistency.check(filled.declared, filled.geometry)}
    assert not got["construction_volume"].passed and "filled in" in got["construction_volume"].detail


def test_a_small_filled_box_reports_the_share_it_fails_on():
    """CALI-87 (#75 rework, item 4): the core share failed the cube, but the result reported the volume ratio's
    margin (which passes)."""
    filled = sandbox.run_script(CUBE.replace("FILLED = False", "FILLED = True"), timeout=120)
    got = {r.id: r for r in consistency.check(filled.declared, filled.geometry)}["construction_volume"]
    assert not got.passed and "10%" in got.expr
    assert got.actual == pytest.approx(0.187, abs=0.02) and got.margin == pytest.approx(0.1 - got.actual, abs=1e-3)
    assert "19% of it is in no piece" in got.detail or "18% of it is in no piece" in got.detail
