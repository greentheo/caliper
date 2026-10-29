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
    assert set(got) == {"construction_inside", "construction_covers", "construction_volume"}
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
