"""CALI-177 (#222 slice C): the make side. What's marked on each flat piece to make it, read from the part's own geometry,
and said the same way on the patterns, the cut list, the build book and the kids' book.

1. Bevels from the geometry: a splayed side's level top and foot edges are 10° bevels, with the other face's line.
2. A sheet run through another is a mortise on the host's pattern, sized from the solid.
3. Screw marks along each joint line, 1 1/2 in from each end then no more than 6 in apart: one count everywhere.
4. Rabbet and dado lines with their depth; glue blocks on the cut list, weighed and bought.
Synthetic parts, never Theo's.
"""

import math
import os

import numpy as np
import pytest

from caliper import marks

IN = 25.4
T = 19.05

#: Two sides, a step on them, front and back rails under it, and a stringer through both sides (through tenons).
TENONED = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 400.0, "d": 300.0, "h": 420.0, "rail": 101.6, "str_h": 127.0, "str_z": 63.5}


def _boxes(p):
    t, w, d, h, r = p["t"], p["w"], p["d"], p["h"], p["rail"]
    ym = d / 2
    return {"step": ((0, 0, h - t), (w, d, h)),
            "front rail": ((t, 0, h - t - r), (w - t, t, h - t)),
            "back rail": ((t, d - t, h - t - r), (w - t, d, h - t)),
            "stringer": ((0, ym - t / 2, p["str_z"]), (w, ym + t / 2, p["str_z"] + p["str_h"]))}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    out = None
    for x0 in (0.0, w - t):
        b = cq.Workplane().box(t, d, h - t, centered=False).translate((x0, 0, 0))
        out = b if out is None else out.union(b)
    for lo, hi in _boxes(p).values():
        out = out.union(cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, r = p["t"], p["w"], p["d"], p["h"], p["rail"]
    ym, z0, z1 = d / 2, p["str_z"], p["str_z"] + p["str_h"]
    side = lambda x: [(x, 0, 0), (x, d, 0), (x, d, h - t), (x, 0, h - t)]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t, "outline": side(0.0)},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t, "outline": side(w)},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]},
            {"name": "front rail", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t, 0, h - t - r), (w - t, 0, h - t - r), (w - t, 0, h - t), (t, 0, h - t)]},
            {"name": "back rail", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t, d, h - t - r), (w - t, d, h - t - r), (w - t, d, h - t), (t, d, h - t)]},
            {"name": "stringer", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, ym - t / 2, z0), (w, ym - t / 2, z0), (w, ym - t / 2, z1), (0, ym - t / 2, z1)]}]
'''

#: A top on two sides that lean out 10°, their top and foot edges cut level: the outline is each side's outer face.
SPLAYED = '''import math

import cadquery as cq

PARAMS = {"t": 19.05, "w": 380.0, "d": 280.0, "h": 400.0, "splay": 10.0}


def _side(p, s):
    t, d, h = p["t"], p["d"], p["h"]
    run = (h - t) * math.tan(math.radians(p["splay"]))
    return [(s * (d / 2 - t), h - t), (s * d / 2, h - t), (s * (d / 2 + run), 0.0), (s * (d / 2 - t + run), 0.0)], run


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    out = cq.Workplane().box(w, d, t).translate((0, 0, h - t / 2))
    for s in (1, -1):
        prof, run = _side(p, s)
        out = out.union(cq.Workplane("YZ").workplane(offset=-w / 2).polyline(prof).close().extrude(w))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    run = (h - t) * math.tan(math.radians(p["splay"]))
    hw = w / 2
    out = [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
            "outline": [(-hw, -d / 2, h), (hw, -d / 2, h), (hw, d / 2, h), (-hw, d / 2, h)]}]
    for s, name in ((1, "back side"), (-1, "front side")):
        out.append({"name": name, "kind": "sheet", "material": "plywood", "thickness": t,
                    "outline": [(-hw, s * d / 2, h - t), (hw, s * d / 2, h - t), (hw, s * (d / 2 + run), 0.0),
                                (-hw, s * (d / 2 + run), 0.0)]})
    return out
'''

#: Two sides and a shelf set 1/4 in into each (dados), the shelf's ends inside the sides' thickness.
DADOED = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 400.0, "d": 250.0, "h": 500.0, "z": 250.0, "dado": 6.35}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, z, k = p["t"], p["w"], p["d"], p["h"], p["z"], p["dado"]
    out = cq.Workplane().box(t, d, h, centered=False)
    out = out.union(cq.Workplane().box(t, d, h, centered=False).translate((w - t, 0, 0)))
    return out.union(cq.Workplane().box(w - 2 * t + 2 * k, d, t, centered=False).translate((t - k, 0, z)))


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, z, k = p["t"], p["w"], p["d"], p["h"], p["z"], p["dado"]
    side = lambda x: [(x, 0, 0), (x, d, 0), (x, d, h), (x, 0, h)]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t, "outline": side(0.0)},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t, "outline": side(w)},
            {"name": "shelf", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t - k, 0, z), (w - t + k, 0, z), (w - t + k, d, z), (t - k, d, z)]}]
'''

SAID = '''

JOINTS = [
    {"pieces": ["front rail", "left side"], "kind": "glue block", "fix": ["glue", "screws"]},
    {"pieces": ["back rail", "step"], "kind": "rabbet", "fix": ["glue"]},
]
'''


def _store(tmp_path, script, name="a stool"):
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    s = DesignStore.create(name, base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent=name)
    return s


@pytest.fixture
def tenoned(tmp_path):
    return _store(tmp_path, TENONED)


@pytest.fixture
def splayed(tmp_path):
    return _store(tmp_path, SPLAYED)


# --- the screw rule --------------------------------------------------------------------------------------------------------
def test_screws_go_an_inch_and_a_half_from_each_end_then_no_more_than_six_inches_apart():
    assert np.allclose(marks.spots(12 * IN), [1.5 * IN, 6 * IN, 10.5 * IN])
    got = marks.spots(20 * IN)
    assert len(got) == 4 and np.isclose(got[0], 1.5 * IN) and np.isclose(got[-1], 18.5 * IN)
    assert max(np.diff(got)) <= 6 * IN + 1e-9
    assert np.allclose(marks.spots(4 * IN), [1.5 * IN, 2.5 * IN])
    assert marks.spots(2 * IN) == [IN]                                  # too short for two: one in the middle
    assert marks.count(9 * IN) == 2 and marks.count(9.01 * IN) == 3


# --- 1: bevels -------------------------------------------------------------------------------------------------------------
def test_a_splayed_side_s_level_edges_are_ten_degree_bevels(splayed):
    m = marks.of(splayed, "stool")
    assert set(m["bevels"]) == {"back side", "front side"}, m["bevels"]
    for side in ("back side", "front side"):
        got = sorted(m["bevels"][side], key=lambda b: str(b["meets"]))
        assert [b["meets"] for b in got] == ["the floor", "top"], got
        for b in got:
            assert abs(b["angle"] - 10.0) < 0.3 and abs(b["length_mm"] - 380.0) < 0.5, b
            assert abs(b["offsets"][0]) < 0.2 and abs(abs(b["offsets"][1]) - T * math.tan(math.radians(10))) < 0.3, b


def test_square_edges_aren_t_bevels(tenoned):
    assert marks.of(tenoned, "stool")["bevels"] == {}


# --- 2: mortises -----------------------------------------------------------------------------------------------------------
def test_the_stringer_through_both_sides_is_a_mortise_in_each(tenoned):
    m = marks.of(tenoned, "stool")
    assert set(m["cuts"]) == {"left side", "right side"}, m["cuts"]
    for side in ("left side", "right side"):
        (c,) = m["cuts"][side]
        assert c["kind"] == "mortise" and c["for"] == "stringer" and c["depth_mm"] is None, c
        box = np.ptp(np.asarray(c["corners"]), axis=0)
        assert abs(box[1] - T) < 0.3 and abs(box[2] - 127.0) < 0.5, box             # 3/4 x 5 in, from the solid
        assert abs(min(q[2] for q in c["corners"]) - 63.5) < 0.5


def test_a_hole_already_in_the_outline_isn_t_marked_again(tmp_path):
    script = TENONED.replace(
        '''"thickness": t, "outline": side(0.0)}''',
        '''"thickness": t, "outline": side(0.0),
             "holes": [[(0.0, ym - t / 2, z0), (0.0, ym + t / 2, z0), (0.0, ym + t / 2, z1), (0.0, ym - t / 2, z1)]]}''')
    assert script != TENONED
    m = marks.of(_store(tmp_path, script), "stool")
    assert "left side" not in m["cuts"] and len(m["cuts"]["right side"]) == 1, m["cuts"]


# --- 3: screws -------------------------------------------------------------------------------------------------------------
def test_screw_marks_along_each_joint_line(tenoned):
    m = marks.of(tenoned, "stool")
    sc = m["screws"]
    step = sc[("left side", "step")]
    assert step["on"] == "step" and step["into"] == "left side" and step["n"] == 3, step
    ys = sorted(float(p[1]) for p in step["points"])
    assert np.allclose(ys, [1.5 * IN, 150.0, 300 - 1.5 * IN], atol=1.0), ys          # along the side's top edge
    assert all(abs(float(p[0]) - T / 2) < 0.5 for p in step["points"])               # centred on the side's thickness
    rail = sc[("front rail", "left side")]
    assert rail["on"] == "left side" and rail["into"] == "front rail" and rail["n"] == 2, rail
    assert sc[("front rail", "step")]["n"] == 3 and sc[("front rail", "step")]["on"] == "step"
    for k in (("left side", "stringer"), ("right side", "stringer")):
        assert sc[k]["n"] == 0 and sc[k]["why"] == "glued in its mortise" and sc[k]["host"] != "stringer", sc[k]
    assert sum(c["n"] for c in sc.values()) == 20


def test_one_count_for_the_shopping_list(tenoned):
    from caliper import construction as C

    f = C.report(tenoned, "stool")["bom"]["fasteners"]
    assert f["screws"] == 20 and f["joints"] == 10, f
    assert "1 1/2 in from each end" in f["basis"]


def test_a_joint_said_without_screws_has_none_and_a_glue_block_is_screwed_into_both(tmp_path):
    m = marks.of(_store(tmp_path, TENONED + SAID), "stool")
    assert m["screws"][("back rail", "step")]["n"] == 0
    gb = m["screws"][("front rail", "left side")]
    assert gb["n"] == 2 * marks.count(101.6) and gb["on"] is None, gb


# --- 4: rabbets, dados, glue blocks ----------------------------------------------------------------------------------------
def test_a_shelf_set_into_the_sides_is_a_dado_its_depth_from_the_solid(tmp_path):
    m = marks.of(_store(tmp_path, DADOED, "a shelf"), "stool")
    for side in ("left side", "right side"):
        (c,) = m["cuts"][side]
        assert c["kind"] == "dado" and c["for"] == "shelf" and abs(c["depth_mm"] - 6.35) < 0.5, c
    sc = m["screws"]
    assert sc[("left side", "shelf")]["on"] == "left side" and sc[("left side", "shelf")]["n"] == marks.count(250.0), sc


def test_a_declared_rabbet_the_solid_doesn_t_show_is_marked_at_half_the_thickness(tmp_path):
    m = marks.of(_store(tmp_path, TENONED + SAID), "stool")
    (c,) = [c for c in m["cuts"].get("step", []) if c["for"] == "back rail"]
    assert c["kind"] == "rabbet" and c["declared"] and abs(c["depth_mm"] - T / 2) < 1e-6, c


def test_glue_blocks_are_weighed_bought_and_cut(tmp_path):
    from caliper import construction as C

    plain = C.report(_store(tmp_path / "a", TENONED), "stool")
    said = _store(tmp_path / "b", TENONED + SAID)
    items = marks.glue_block_items_of(said, "stool")
    assert len(items) == 1 and items[0]["size"] == "1x1" and items[0]["material"] == "lumber", items
    assert abs(math.dist(items[0]["a"], items[0]["b"]) - 101.6) < 2.0
    r = C.report(said, "stool")
    sticks = r["bom"]["sticks"]
    assert any("1x1" in g["label"] for g in sticks), sticks
    assert r["mass_kg"] > plain["mass_kg"]
    assert marks.glue_block_items_of(_store(tmp_path / "c", TENONED), "stool") == []


# --- the readers -----------------------------------------------------------------------------------------------------------
def test_the_patterns_show_the_marks(tenoned, splayed):
    from caliper import patterns

    pcs = {p["name"]: p for p in patterns.pieces(tenoned, "stool")}
    left = patterns._measure_lines(pcs["left side"])
    assert any(ln.startswith("M1: a mortise for the stringer: cut 5 in x 3/4 in") for ln in left), left
    (c,) = pcs["left side"]["cuts"]
    assert np.allclose(np.ptp(c["poly"], axis=0), [127.0, T], atol=0.5)
    assert sum(len(s["at"]) for s in pcs["left side"]["screws"]) == 4
    assert sum(len(s["at"]) for s in pcs["step"]["screws"]) == 12
    said = " ".join(patterns.marks_lines(pcs["step"]))
    assert "12 screws, marked +: drill a 3/16 in clearance hole" in said and "drive them from this face" in said, said
    assert not pcs["stringer"]["cuts"] and not pcs["stringer"]["screws"]
    side = {p["name"]: p for p in patterns.pieces(splayed, "stool")}["back side"]
    assert len(side["back"]) == 2 and [b["angle"] for b in side["bevels"]] == [10.0, 10.0]
    assert "Bevels: saw at 10°, this face up, along the 2 edges marked B." in " ".join(patterns.marks_lines(side))
    assert abs(float(np.ptp(side["outline"], axis=0).max()) - 380.95 / math.cos(math.radians(10))) < 0.5
    assert "stroke-dasharray" in patterns.project_svg(side)
    patterns.measure_page(side), patterns.tiles(pcs["left side"])                     # they draw


def test_the_patterns_index_counts_them(tenoned, tmp_path):
    from caliper import patterns

    rec = patterns.make(tenoned, "stool", out_dir=str(tmp_path / "hand"))
    by = {p["name"]: p for p in rec["pieces"]}
    assert by["left side"]["cuts"] == ["mortise"] and by["left side"]["screws"] == 4 and by["step"]["screws"] == 12
    page = open(os.path.join(tmp_path / "hand", "index.html")).read()
    assert "1 mortise · 4 screw holes" in page and "12 screw holes" in page, page


def test_the_cut_list_and_the_book_say_them(tenoned, splayed):
    from caliper import release

    m = marks.of(tenoned, "stool")
    lines = marks.cutlist_lines(m)
    assert "    left side: a mortise for the stringer, right through" in lines, lines
    assert any(ln.startswith("    step: 12 screw holes marked") for ln in lines), lines
    names = ["left side", "right side", "step", "front rail", "back rail", "stringer"]
    pcs = [{"name": n, "material": "plywood"} for n in names]
    _, do, _ = release._say_stage("stool", "panels", pcs, {"sheets": []}, {"marks": {"stool": m}})
    text = " ".join(do)
    assert "Cut the 2 mortises marked on the left side and the right side" in text, text
    assert "Drill the 20 screw holes marked + on the patterns" in text, text
    assert "Glue the stringer into its mortise in the left side: no screws." in text, text
    assert "a screw every 6 in" not in text
    s = marks.of(splayed, "stool")
    _, do, _ = release._say_stage("stool", "panels", [{"name": n, "material": "plywood"} for n in ("top", "back side", "front side")],
                                  {"sheets": []}, {"marks": {"stool": s}})
    assert "Set the saw to 10° for the 4 edges marked B on the back side and the front side" in " ".join(do), do
    html = "".join(release.marks_html({"marks": {"stool": marks.cutlist_lines(s)}}))
    assert "back side: bevel 10° along 14 15/16 in of edge" in html, html


def test_the_kids_book_counts_the_same_screws(tenoned, tmp_path):
    from caliper import kidbook

    root = str(tmp_path / "rel")
    os.makedirs(root)
    kidbook.make(tenoned, root, {"design": "a stool", "strength": {}}, ["stool"], {"groups": []})
    page = open(os.path.join(root, "kids.html")).read()
    import re

    said = [int(n) for n in re.findall(r"drives in (\d+) screws", page)]
    assert sum(said) == 20, said
    assert "push the stringer through" in page and "No screws here" in page


def test_a_screw_into_a_steep_bevel_would_come_out_of_the_face():
    """#222 §4: the length rule is checked at a bevel. Through 3/4 in into a 3/4 in edge, a 1 1/4 in screw has 1/2 in
    to go: square, or at 10° (step-stool-3's stretcher), it stays in; past about 49° it comes out."""
    assert not marks.comes_out(T, T, 0.0, 31.75)
    assert not marks.comes_out(T, T, math.sin(math.radians(10)), 31.75)
    assert marks.comes_out(T, T, math.sin(math.radians(60)), 31.75)
    m = {"screws": {("a", "b"): {"n": 3, "on": "a", "into": "b", "points": [], "comes_out": True}}}
    assert any("would come out of the b's face" in ln for ln in marks.book_lines(m)), marks.book_lines(m)


def test_the_cut_list_file_prints_them(tenoned):
    from caliper import cutplan

    lines = marks.cutlist_lines(marks.of(tenoned, "stool"))
    text = cutplan.cutlist_text({"id": "r", "part": "stool", "sticks": [], "sheets": [], "marks": lines})
    assert "  marks (on the hand patterns):\n    left side: a mortise for the stringer, right through\n" in text, text


#: The splayed stool again, each side's outline its inner face: the page still shows the outer face.
SPLAYED_IN = SPLAYED.replace('"outline": [(-hw, s * d / 2, h - t), (hw, s * d / 2, h - t), (hw, s * (d / 2 + run), 0.0),\n'
                             '                                (-hw, s * (d / 2 + run), 0.0)]})',
                             '"outline": [(-hw, s * (d / 2 - t), h - t), (hw, s * (d / 2 - t), h - t),\n'
                             '                                (hw, s * (d / 2 - t + run), 0.0), (-hw, s * (d / 2 - t + run), 0.0)]})')


def _on_segments(pts, segs, tol=0.6):
    def d(p, a, b):
        ab = b - a
        k = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
        return float(np.linalg.norm(p - (a + k * ab)))
    return all(min(d(np.asarray(p, float), np.asarray(a, float), np.asarray(b, float)) for a, b in segs) < tol for p in pts)


@pytest.mark.parametrize("script", [SPLAYED, SPLAYED_IN], ids=["outer face declared", "inner face declared"])
def test_the_page_draws_the_outer_face_solid_and_the_inner_face_dashed(script, tmp_path):
    """Whichever face the script declares, the page's solid line is the face it shows (the outer one) and the dashed line is
    the other face's, each where that face's edge really is."""
    from caliper import patterns

    assert script.count("d / 2 - t") == (0 if script is SPLAYED else 4) + SPLAYED.count("d / 2 - t")
    s = _store(tmp_path, script)
    side = {p["name"]: p for p in patterns.pieces(s, "stool")}["back side"]
    m = marks.of(s, "stool")
    pc = next(p for p in m["pieces"] if p["key"] == "back side")
    centre = np.array([0.0, 0.0, 200.0])
    out_face = 0 if float((pc["polys"][0].mean(axis=0) - centre)[1]) > float(
        (pc["polys"][0].mean(axis=0) + marks._geom(pc)[3] * T - centre)[1]) else 1
    k = len(side["outline"])
    solid = [(side["outline"][i], side["outline"][(i + 1) % k]) for i in range(k)]
    assert np.allclose(side["outline"].min(axis=0), 0.0, atol=1e-6)                 # its square corner at (0, 0)
    for b in m["bevels"]["back side"]:
        assert _on_segments(side["to_page"](np.asarray(b["lines"][out_face])), solid), b
        assert _on_segments(side["to_page"](np.asarray(b["lines"][1 - out_face])), side["back"]), (b, side["back"])


#: A panel whose top edge carries a 2x2 turned 45°: a ray out through its edge runs on through the stick.
DIAMOND = '''import cadquery as cq

PARAMS = {"t": 19.05}


def build(params):
    t = 19.05
    panel = cq.Workplane().box(300, t, 200, centered=False)
    stick = cq.Workplane().box(300, 38.1, 38.1).rotate((0, 0, 0), (1, 0, 0), 45).translate((150, t / 2 + 1, 200 + 26.94 - 3))
    return panel.union(stick)


def construction(params, build=None):
    t = 19.05
    return [{"name": "panel", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (300, 0, 0), (300, 0, 200), (0, 0, 200)]},
            {"name": "rail", "kind": "stick", "material": "lumber", "size": "2x2",
             "a": (0, t / 2 + 1, 223.94), "b": (300, t / 2 + 1, 223.94)}]
'''


def test_a_ray_that_runs_on_through_another_piece_isn_t_a_bevel(tmp_path):
    """The edge face is looked for near where the edge is: past it, the ray's way out of the stick's slanted face is no bevel."""
    m = marks.of(_store(tmp_path, DIAMOND, "a rail"), "stool")
    assert "panel" not in m["bevels"], m["bevels"]


# --- #283 review: a bevel is one plane across the whole thickness ---------------------------------------------------------
#: A 3/4 in board standing on its back edge, its free front edge (y = 0) cut one way or another; the outline its x = 0 face.
EDGED = '''import math

import cadquery as cq

PARAMS = {"t": 19.05, "d": 300.0, "h": 450.0}
EDGE = "EDGE"


def build(params):
    p = {**PARAMS, **(params or {})}
    t, d, h = p["t"], p["d"], p["h"]
    if EDGE.startswith("bevel"):                     # the whole edge one plane, leaning across the thickness
        k = t * math.tan(math.radians(float(EDGE[5:])))
        return cq.Workplane("XY").polyline([(0, 0), (t, k), (t, d), (0, d)]).close().extrude(h)
    if EDGE == "taper":                              # the edge slopes in the board's own plane: square to its faces
        return cq.Workplane("YZ").polyline([(0, 0), (d, 0), (d, h), (60, h)]).close().extrude(t)
    board = cq.Workplane().box(t, d, h, centered=False)
    edge = board.edges("|Z").edges(">X").edges("<Y")
    if EDGE.startswith("chamfer"):
        return edge.chamfer(float(EDGE[7:]))
    if EDGE.startswith("round"):
        return edge.fillet(float(EDGE[5:]))
    return board


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, d, h = p["t"], p["d"], p["h"]
    out = [(0.0, 0.0, 0.0), (0.0, d, 0.0), (0.0, d, h), (0.0, 0.0, h)]
    if EDGE == "taper":
        out = [(0.0, 0.0, 0.0), (0.0, d, 0.0), (0.0, d, h), (0.0, 60.0, h)]
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": t, "outline": out}]
'''


@pytest.mark.parametrize("edge", ["square", "chamfer3", "round10", "taper"])
def test_a_small_chamfer_a_round_over_or_a_taper_marks_nothing(edge, tmp_path):
    m = marks.of(_store(tmp_path, EDGED.replace('EDGE = "EDGE"', f'EDGE = "{edge}"'), "a board"), "stool")
    assert m["bevels"] == {} and m["chamfers"] == {}, (m["bevels"], m["chamfers"])


def test_a_chamfer_past_half_the_thickness_is_a_chamfer_never_a_saw_bevel(tmp_path):
    """#283 review: a 12 mm chamfer on a 3/4 in edge read as a 45° bevel, and the book said to saw the whole edge at 45°."""
    from caliper import patterns, release

    s = _store(tmp_path, EDGED.replace('EDGE = "EDGE"', 'EDGE = "chamfer12"'), "a board")
    m = marks.of(s, "stool")
    assert m["bevels"] == {}, m["bevels"]
    (c,) = m["chamfers"]["side"]
    assert abs(c["depth_mm"] - 12.0) < 0.5 and abs(c["angle"] - 45.0) < 1.0 and c["face"] == 1, c   # on the face away from x = 0
    book = " ".join(marks.book_lines(m))
    assert "Set the saw" not in book and "Chamfer the 1 edge marked C on the side, 12 mm (1/2 in), with a router or a " \
                                         "block plane" in book, book
    assert "    side: chamfer 12 mm (1/2 in) at 45° along 17 11/16 in of edge" in marks.cutlist_lines(m)
    (pc,) = patterns.pieces(s, "stool")
    said = " ".join(patterns.marks_lines(pc))
    assert "saw at" not in said and "Chamfer: 12 mm (1/2 in) along the edge marked C" in said, said
    _, do, _ = release._say_stage("stool", "panels", [{"name": "side", "material": "plywood"}, {"name": "x", "material": "plywood"}],
                                  {"sheets": []}, {"marks": {"stool": m}})
    assert "Set the saw" not in " ".join(do)


def test_a_true_bevel_is_still_one(tmp_path):
    m = marks.of(_store(tmp_path, EDGED.replace('EDGE = "EDGE"', 'EDGE = "bevel20"'), "a board"), "stool")
    (b,) = m["bevels"]["side"]
    assert abs(b["angle"] - 20.0) < 0.5 and m["chamfers"] == {}, b
