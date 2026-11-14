"""CALI-181 (#290): a chamfer wider across the face than down the edge is marked too. From #289's review (reviewer-2): a
chamfer drawn 6 down x 15 across, 4 x 12, or 14 x 30 gave no C mark, no cut-list line and no book line: #283's reader
found only the ones that run further down the edge than across. Either way, one reaching past half the board's thickness
is a chamfer for a router or a block plane; a small one (3 x 3, 3 x 8) is still left to the drawing.

Drawn explicitly, so neither distance comes from CadQuery's argument order. Synthetic boards, no Claude call."""

import pytest

from caliper import marks

from .test_make_marks import _store

T = 19.05

#: A 3/4 in board standing on its back edge, the outline its x = 0 face; its free front edge (y = 0) chamfered on the
#: far face (x = t): DOWN mm down the edge (across the thickness) and ACROSS mm in across the face.
BOARD = '''import cadquery as cq

PARAMS = {"t": 19.05, "d": 300.0, "h": 450.0}
DOWN, ACROSS = SIZES


def build(params):
    p = {**PARAMS, **(params or {})}
    t, d, h = p["t"], p["d"], p["h"]
    if not DOWN:
        return cq.Workplane().box(t, d, h, centered=False)
    prof = [(0, 0), (t - DOWN, 0), (t, ACROSS), (t, d), (0, d)]
    return cq.Workplane("XY").polyline(prof).close().extrude(h)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, d, h = p["t"], p["d"], p["h"]
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0.0, 0.0, 0.0), (0.0, d, 0.0), (0.0, d, h), (0.0, 0.0, h)]}]
'''


def _marks(tmp_path, down, across):
    return marks.of(_store(tmp_path, BOARD.replace("SIZES", f"{down}, {across}"), "a board"), "stool")


@pytest.mark.parametrize("down,across,said", [
    (6.0, 15.0, "6 × 15 mm (1/4 × 9/16 in)"),
    (4.0, 12.0, "4 × 12 mm ("),
    (14.0, 30.0, "14 × 30 mm ("),                                                    # past half the thickness, both ways
])
def test_a_chamfer_wider_across_the_face_is_marked(down, across, said, tmp_path):
    m = _marks(tmp_path, down, across)
    assert m["bevels"] == {}, m["bevels"]                                            # never a saw bevel
    (c,) = m["chamfers"]["side"]
    assert abs(c["depth_mm"] - down) < 0.5 and abs(c["setback_mm"] - across) < 0.5 and c["face"] == 1, c
    lines = marks.cutlist_lines(m)
    assert any(ln.startswith(f"    side: chamfer {said}") and "°" not in ln for ln in lines), lines
    book = " ".join(marks.book_lines(m))
    assert f"Chamfer the 1 edge marked C on the side, {said}" in book and "Set the saw" not in book, book


def test_the_page_says_which_distance_is_which(tmp_path):
    from caliper import patterns

    s = _store(tmp_path, BOARD.replace("SIZES", "6.0, 15.0"), "a board")
    (pc,) = patterns.pieces(s, "stool")
    said = " ".join(patterns.marks_lines(pc))
    assert ("Chamfer: 6 × 15 mm (1/4 × 9/16 in) along the edge marked C, on the other face: 6 mm down the edge and 15 mm "
            "in across the face.") in said, said


@pytest.mark.parametrize("down,across", [(15.0, 6.0), (12.0, 12.0)])
def test_the_ones_already_read_read_the_same(down, across, tmp_path):
    (c,) = _marks(tmp_path, down, across)["chamfers"]["side"]
    assert abs(c["depth_mm"] - down) < 0.5 and abs(c["setback_mm"] - across) < 0.5 and c["face"] == 1, c


@pytest.mark.parametrize("down,across", [(3.0, 3.0), (3.0, 8.0), (8.0, 3.0), (0, 0)])
def test_a_small_chamfer_or_a_square_edge_marks_nothing(down, across, tmp_path):
    m = _marks(tmp_path, down, across)
    assert m["chamfers"] == {} and m["bevels"] == {}, (m["chamfers"], m["bevels"])


#: The same board, its far front corner shaped some other way: SHAPE.
OTHER = '''import math

import cadquery as cq

PARAMS = {"t": 19.05, "d": 300.0, "h": 450.0}
SHAPE = "SHAPE"


def build(params):
    t, d, h = 19.05, 300.0, 450.0
    if SHAPE == "round17":                           # a deep round-over: past half the thickness, but not flat
        return cq.Workplane().box(t, d, h, centered=False).edges("|Z").edges(">X").edges("<Y").fillet(17.0)
    if SHAPE == "widening":                          # one flat slant, 4 x 10 at the foot and 8 x 20 at the top
        low = [(0, 0), (t - 4, 0), (t, 10), (t, d), (0, d)]
        high = [(0, 0), (t - 8, 0), (t, 20), (t, d), (0, d)]
        return cq.Workplane("XY").polyline(low).close().workplane(offset=h).polyline(high).close().loft(ruled=True)
    if SHAPE == "rebate":                            # a step 10 down and 40 across: square corners, no slant
        return cq.Workplane("XY").polyline([(0, 0), (t - 10, 0), (t - 10, 40), (t, 40), (t, d), (0, d)]).close().extrude(h)
    k = t * math.tan(math.radians(70.0))             # the whole thickness at 70°: no saw setting, no chamfer
    return cq.Workplane("XY").polyline([(0, 0), (t, k), (t, d), (0, d)]).close().extrude(h)


def construction(params, build=None):
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0.0, 0.0, 0.0), (0.0, 300.0, 0.0), (0.0, 300.0, 450.0), (0.0, 0.0, 450.0)]}]
'''


@pytest.mark.parametrize("shape", ["round17", "widening", "slant70", "rebate"])
def test_a_deep_round_over_a_widening_chamfer_or_a_steep_slant_isn_t_a_chamfer(shape, tmp_path):
    """And a free-edge rebate (#291 review): its rays meet a face square on, which the square-corner check stops before
    any division by its slope; read as nothing, never an error."""
    m = marks.of(_store(tmp_path, OTHER.replace('SHAPE = "SHAPE"', f'SHAPE = "{shape}"'), "a board"), "stool")
    assert m["chamfers"] == {}, m["chamfers"]
