"""CALI-182 (#292): a slant past what a saw tilts to, and a rebate on a free edge, are said, never drawn as a square edge.
From #291's review: a full-thickness slant at 50, 60 or 70°, and a free-edge rebate (10 down x 40 across), read as
nothing, so the patterns, the cut list and the book showed a square edge, and it would have been cut square.

- A slant past 45°: marked S, "cut at 60°, past what a saw tilts to (45°): plane or router it, or cut it at 30° from the
  other face". S, not D: D1, D2 already name the dados on the same pages.
- A rebate on a free edge: marked R, its wall a dashed line, "rebate 10 x 40 mm along the edge marked R, with a router or
  table saw", as #283 says a joint's rabbet.

Boards drawn with explicit polylines. Synthetic, no Claude call."""

import math

import numpy as np
import pytest

from caliper import marks

from .test_make_marks import _store

T = 19.05

#: A 3/4 in board standing on its back edge, the outline its x = 0 face; its free front edge (y = 0) cut SHAPE.
BOARD = '''import math

import cadquery as cq

PARAMS = {"t": 19.05, "d": 300.0, "h": 450.0}
SHAPE, A, B = "SHAPE", 0.0, 0.0


def build(params):
    t, d, h = 19.05, 300.0, 450.0
    if SHAPE == "slant":                             # the whole thickness at A°, the far face (x = t) set back
        k = t * math.tan(math.radians(A))
        prof = [(0, 0), (t, k), (t, d), (0, d)]
    elif SHAPE == "rebate":                          # a step A down from the far face and B in across it
        prof = [(0, 0), (t - A, 0), (t - A, B), (t, B), (t, d), (0, d)]
    else:                                            # the same step in the outline's own face (x = 0)
        prof = [(A, 0), (t, 0), (t, d), (0, d), (0, B), (A, B)]
    return cq.Workplane("XY").polyline(prof).close().extrude(h)


def construction(params, build=None):
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0.0, 0.0, 0.0), (0.0, 300.0, 0.0), (0.0, 300.0, 450.0), (0.0, 0.0, 450.0)]}]
'''


def _board(tmp_path, shape, a, b=0.0):
    return _store(tmp_path, BOARD.replace('SHAPE, A, B = "SHAPE", 0.0, 0.0', f'SHAPE, A, B = "{shape}", {a}, {b}'),
                  "a board")


# --- a slant past 45° ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("angle", [50.0, 60.0, 70.0])
def test_a_slant_past_what_a_saw_tilts_to_is_said(angle, tmp_path):
    from caliper import patterns

    s = _board(tmp_path, "slant", angle)
    m = marks.of(s, "stool")
    assert m["bevels"] == {} and m["chamfers"] == {}, (m["bevels"], m["chamfers"])
    (sl,) = m["slants"]["side"]
    assert abs(sl["angle"] - angle) < 0.5, sl
    a, other = f"{angle:.0f}", f"{90 - angle:.0f}"
    assert f"    side: slant {a}° along 17 11/16 in of edge, past what a saw tilts to (45°)" in marks.cutlist_lines(m)
    book = " ".join(marks.book_lines(m))
    assert "Set the saw" not in book and (f"The 1 edge marked S on the side is cut at {a}°, past what a saw tilts to "
                                          f"(45°): plane or router it, or cut it at {other}° from the other face.") in book, book
    (pc,) = patterns.pieces(s, "stool")
    said = " ".join(patterns.marks_lines(pc))
    assert "saw at" not in said and (f"Slant: the edge marked S is cut at {a}°, past what a saw tilts to (45°): plane or "
                                     f"router it, or cut it at {other}° from the other face.") in said, said
    assert len(pc["back"]) == 1                                                      # its other face's line, dashed
    assert ">S<" in patterns.project_svg(pc) and ">B<" not in patterns.project_svg(pc)
    patterns.measure_page(pc), patterns.tiles(pc)                                    # they draw


@pytest.mark.parametrize("angle", [20.0, 40.0, 45.0])
def test_a_slant_a_saw_tilts_to_is_still_a_bevel(angle, tmp_path):
    m = marks.of(_board(tmp_path, "slant", angle), "stool")
    (b,) = m["bevels"]["side"]
    assert abs(b["angle"] - angle) < 0.5 and m["slants"] == {}, (m["bevels"], m["slants"])


# --- a rebate on a free edge -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("shape,down,across,face", [
    ("rebate", 10.0, 40.0, 1), ("rebate", 10.0, 5.0, 1), ("rebate", 6.0, 12.0, 1), ("front", 9.0, 20.0, 0)])
def test_a_free_edge_rebate_is_marked(shape, down, across, face, tmp_path):
    m = marks.of(_board(tmp_path, shape, down, across), "stool")
    assert m["chamfers"] == {} and m["bevels"] == {} and m["slants"] == {}, m
    (r,) = m["rebates"]["side"]
    assert abs(r["depth_mm"] - down) < 0.3 and abs(r["width_mm"] - across) < 0.3 and r["face"] == face, r


def test_a_free_edge_rebate_is_said_and_drawn(tmp_path):
    from caliper import patterns

    s = _board(tmp_path, "rebate", 10.0, 40.0)
    m = marks.of(s, "stool")
    assert "    side: rebate 10 × 40 mm (3/8 × 1 9/16 in) along 17 11/16 in of edge" in marks.cutlist_lines(m)
    book = " ".join(marks.book_lines(m))
    assert ("Cut the rebate along the 1 edge marked R on the side, 10 × 40 mm (3/8 × 1 9/16 in), with a router or "
            "table saw.") in book, book
    (pc,) = patterns.pieces(s, "stool")
    said = " ".join(patterns.marks_lines(pc))
    assert ("Rebate: 10 × 40 mm (3/8 × 1 9/16 in) along the edge marked R, on the other face, with a router or table "
            "saw: 10 mm down the edge and 40 mm in across the face; the dashed line is its wall.") in said, said
    (r,) = pc["rebates"]
    a, b = (np.asarray(x, float) for x in r["line"])
    assert abs(float(np.linalg.norm(b - a)) - 450.0) < 0.5                           # the wall's line, the edge's length
    svg = patterns.project_svg(pc)
    assert ">R<" in svg and "stroke-dasharray" in svg
    patterns.measure_page(pc), patterns.tiles(pc)


@pytest.mark.parametrize("shape,a,b", [("slant", 0.0, 0.0), ("rebate", 0.0, 0.0)])
def test_a_square_edge_is_still_nothing(shape, a, b, tmp_path):
    m = marks.of(_board(tmp_path, "rebate", 0.0, 0.0) if shape == "rebate" else _board(tmp_path, shape, 0.0), "stool")
    assert m["slants"] == {} and m["rebates"] == {} and m["bevels"] == {} and m["chamfers"] == {}, m


def test_a_steep_bevel_at_a_joint_is_still_that_joint_s_bevel(tmp_path):
    """A side splayed 48°: its top edge, cut to sit on the top, is past a saw's 45° now, so a slant; the joint check still
    reads it as that joint's bevel."""
    from tests.test_joint_picks import _land, _with
    from tests.test_make_marks import SPLAYED

    steep = SPLAYED.replace('"splay": 10.0', '"splay": 48.0')
    m = marks.of(_store(tmp_path / "m", steep, "steep"), "stool")
    assert any(sl.get("meets") == "top" for sl in m["slants"].get("back side", [])), (m["slants"], m["bevels"])
    pair = ("back side", "top")
    got = _land(tmp_path, _with(steep, pair, "bevel"), pair, "bevel", before=steep)
    assert got == {"said": "Checked: the joint between the back side and the top is now a bevel, 48° on the back side's "
                           "edge.", "landed": True}, got


def test_an_edge_in_two_slants_isn_t_said_as_one(tmp_path):
    """50° for half its length and 70° for the rest: no one setting, so neither slant is said for the whole edge."""
    script = BOARD.replace('''    if SHAPE == "slant":''', '''    if SHAPE == "two":
        low = cq.Workplane("XY").polyline([(0, 0), (t, t * math.tan(math.radians(50))), (t, d), (0, d)]).close()
        high = cq.Workplane("XY").workplane(offset=h / 2).polyline(
            [(0, 0), (t, t * math.tan(math.radians(70))), (t, d), (0, d)]).close()
        return low.extrude(h / 2).union(high.extrude(h / 2))
    if SHAPE == "slant":''').replace('SHAPE, A, B = "SHAPE", 0.0, 0.0', 'SHAPE, A, B = "two", 0.0, 0.0')
    m = marks.of(_store(tmp_path, script, "a board"), "stool")
    assert m["slants"] == {} and m["bevels"] == {}, (m["slants"], m["bevels"])
