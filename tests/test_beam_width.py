"""CALI-86 (#62, finding 1; rule 6) — a panel on two edges takes a foot over a limited width, not its whole width.

The reference is the Lévy series for a thin elastic plate, simply supported on two opposite edges and free on the
other two, under a uniform patch at its middle (Timoshenko & Woinowsky-Krieger, Theory of Plates and Shells, ch. 6,
the Lévy method). It's checked here against the two cases it must reduce to: a strip as narrow as the patch (a beam)
and a plate many spans wide (Roark 11.4, which ``load_study.plate`` uses). Isotropic, like the rest of the check:
plywood's grain is the across-grain factor's job.
"""

import math

import numpy as np
import pytest

from caliper import load_study as L

P, T = 2 * 200 * L.LB, 12.7                    # an adult stepping up on 1/2 in plywood
PLY = {"E": 8000.0, "strength": 15.0, "across": 0.5}
def _exp(al, y, y0, k):
    """Rows Y, Y', Y'', Y''' of g = e^{kz} and h = z e^{kz}, z = al (y - y0)."""
    z = al * (y - y0)
    e = math.exp(k * z)
    return np.array([[e, z * e],
                     [k * al * e, al * (1 + k * z) * e],
                     [al ** 2 * e, al ** 2 * (2 * k + z) * e],
                     [k * al ** 3 * e, al ** 3 * (3 + k * z) * e]])


def levy(a, b, t, P, u, v, E=8000.0, nu=0.3, terms=401):
    D = E * t ** 3 / (12 * (1 - nu ** 2))
    q0 = P / (u * v)
    c, h = v / 2, b / 2
    Mx = My = 0.0
    for m in range(1, terms + 1, 2):
        al = m * math.pi / a
        qm = q0 * 4 / (m * math.pi) * math.sin(m * math.pi / 2) * math.sin(al * u / 2)
        Yp = qm / (D * al ** 4)
        # inner |y| < c, symmetric, scaled by cosh(al c): cosh(al y), al y sinh(al y)
        def inner(y):
            ch, sh, z = math.cosh(al * y), math.sinh(al * y), al * y
            k = math.cosh(al * c)
            return np.array([[ch, z * sh],
                             [al * sh, al * (sh + z * ch)],
                             [al ** 2 * ch, al ** 2 * (2 * ch + z * sh)],
                             [al ** 3 * sh, al ** 3 * (3 * sh + z * ch)]]) / k
        # outer c < y < h: decaying from the patch's edge, and from the free edge
        def outer(y):
            return np.hstack([_exp(al, y, c, -1), _exp(al, y, h, +1)])
        M = np.zeros((6, 6))
        rhs = np.zeros(6)
        if h > c + 1e-9:
            M[:4, :2] = inner(c)
            M[:4, 2:] = -outer(c)
            rhs[0] = -Yp
            o = outer(h)
            M[4, 2:] = o[2] - nu * al ** 2 * o[0]            # My = 0 at the free edge
            M[5, 2:] = o[3] - (2 - nu) * al ** 2 * o[1]      # Vy = 0
        else:                                                 # the patch spans the width: free edges at y = c
            i = inner(c)
            M = np.vstack([i[2] - nu * al ** 2 * i[0], i[3] - (2 - nu) * al ** 2 * i[1]])
            rhs = np.array([nu * al ** 2 * Yp, 0.0])
        sol = np.linalg.solve(M, rhs)
        A, B = sol[:2] / math.cosh(al * c)
        Y0, Y0pp = Yp + A, al ** 2 * (A + 2 * B)
        sx = math.sin(al * a / 2)
        wxx, wyy = -al ** 2 * Y0 * sx, Y0pp * sx
        Mx += -D * (wxx + nu * wyy)
        My += -D * (wyy + nu * wxx)
    return 6 * Mx / t ** 2, 6 * My / t ** 2


def test_the_reference_is_a_beam_when_narrow_and_roarks_plate_when_wide():
    # a strip 100 wide, the load across all of it over 100 mm of a 300 mm span: M = P (L/4 - u/8)
    narrow, _ = levy(300, 100, T, P, 100, 100)
    assert narrow == pytest.approx(P * (300 / 4 - 100 / 8) / (100 * T ** 2 / 6), rel=0.02)
    wide, _ = levy(300, 1800, T, P, 100, 100)
    assert wide == pytest.approx(L.plate(1800, 300, T, P, 100 * 100, 8000)["stress_mpa"], rel=0.02)
    assert levy(300, 900, T, P, 100, 100, terms=81)[0] == pytest.approx(levy(300, 900, T, P, 100, 100)[0], rel=1e-3)


@pytest.mark.parametrize("width", [900, 450])
def test_a_wide_panel_on_two_edges_is_never_greener_than_the_plate(width):
    """The reviewer's 900 x 300 read 2.72x along the grain when the plate says about 1.1x; at 1.5 spans wide the
    whole-width beam was greener than the plate too."""
    ref, _ = levy(300, width, T, P, 100, 100)
    got = L.beam(300, width, T, P, PLY, footprint=100)
    assert got["stress_mpa"] >= ref                                # never greener than the reference
    if width == 900:
        assert got["stress_mpa"] <= 1.35 * ref                     # and not more than 35% on the safe side
    assert got["width_mm"] == pytest.approx(100 + 0.6 * 300) and "BS 8110" in got["why"]


def test_a_narrow_panel_is_a_beam_over_its_whole_width_as_before():
    got = L.beam(300, 220, T, P, PLY, footprint=100)               # test_mixed's top: 220 < 100 + 0.6 x 300
    assert got["width_mm"] == 220
    assert got["stress_mpa"] == pytest.approx(P * 300 / 4 / (220 * T ** 2 / 6), rel=1e-3)


#: A 1/2 in top 900 wide across 300 mm, on two plywood sides along its long edges: held on two edges, free at its
#: ends (x = 0 and x = 900). Each foot is a loads() box; where it is, and which way it's long, is the point.
TOP = '''import cadquery as cq

W, SPAN, T, S, H = 900.0, 300.0, 12.7, 19.05, 200.0
FEET = {"centred": ((400, 100), (500, 200)), "at the free end": ((0, 100), (100, 200)),
        "long across the span": ((450, 50), (550, 250)), "long along the edge": ((350, 100), (550, 200))}
FOOT = "centred"


def _boxes():
    return [((0, 0, H - T), (W, SPAN, H)), ((0, 0, 0), (W, S, H - T)), ((0, SPAN - S, 0), (W, SPAN, H - T))]


def build(params):
    out = None
    for lo, hi in _boxes():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": T,
             "outline": [(0, 0, H), (W, 0, H), (W, SPAN, H), (0, SPAN, H)]},
            {"name": "front", "kind": "sheet", "material": "plywood", "thickness": S,
             "outline": [(0, 0, 0), (W, 0, 0), (W, 0, H - T), (0, 0, H - T)]},
            {"name": "back", "kind": "sheet", "material": "plywood", "thickness": S,
             "outline": [(0, SPAN, 0), (W, SPAN, 0), (W, SPAN, H - T), (0, SPAN, H - T)]}]


def loads(params, build=None):
    (x0, y0), (x1, y1) = FEET[FOOT]
    return [{"name": "a foot", "lb": 200, "factor": 2.0, "lo": (x0, y0, H - 2), "hi": (x1, y1, H)}]
'''


def _beam_of(foot):
    """The plate check's verdict on the top for one foot, through the real path (no FEA needed for it)."""
    from caliper import consistency, sandbox

    run = sandbox.run_script(TOP.replace('FOOT = "centred"', f'FOOT = "{foot}"'), timeout=120)
    pieces = consistency.shapes(run.declared)
    mesh = run.geometry.require_mesh()
    consistency._sides(mesh, pieces)
    (load,) = L.parse_loads(run.declared["loads"])
    got = L.plate_check(pieces, load, PLY, consistency.tolerance(mesh))
    assert got and got["as"] == "beam" and got["edges_held"] == 2 and got["span_mm"] == pytest.approx(300, abs=1)
    return got


def _stress(width):
    return P * 300 / 4 / (width * T ** 2 / 6)


@pytest.mark.parametrize("foot,width", [
    ("centred", 100 + 0.6 * 300),                        # b_e: the foot's width along the edges + 0.6 of the span
    ("at the free end", 0.5 * (100 + 0.6 * 300) + 50),   # BS 8110 near an unsupported edge: 0.5 b_e + 50 = 190 mm
    ("long across the span", 100 + 0.6 * 300),           # 200 mm across the span, 100 along the edges: still 100
    ("long along the edge", 200 + 0.6 * 300),            # 200 mm along the edges
])
def test_the_plate_check_gives_the_beam_the_width_where_the_foot_is(foot, width):
    """CALI-86 (#69 rework, item 1; rule 6): the beam took the foot's width but not where it was, so a foot at a
    tread's free end got the same width as one in the middle (the reviewer: 17.7 MPa where it's about 26)."""
    got = _beam_of(foot)
    assert got["width_mm"] == pytest.approx(width, abs=1)
    assert got["stress_mpa"] == pytest.approx(_stress(width), rel=0.01)
    # the sag at the same width as the stress
    assert got["deflection_mm"] == pytest.approx(P * 300 ** 3 / (48 * PLY["E"] * width * T ** 3 / 12), rel=0.01)
