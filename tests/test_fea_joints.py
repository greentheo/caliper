"""CALI-194 (#316) slice 2: each joint's force and moment read from the case's FEA, beside the hand rule.

- The reader is exact, by nodes: every piece's joints carry what reaches it, so the statics pin is left with the solve's
  own residual (0 on slice 1's stool), and a voxel no piece has, or one in two at once, shows up there.
- A stick is a flat-ended prism with its corners: a square leg's corners are the leg's, and its end doesn't reach into
  the top above it.
- A joint the FEA can't see, or one a load lands on, isn't read from it: the hand rule's stands, or it's not checked.
- Beside the hand rule, the lower safety governs; where the hand rule has none, the FEA's is the row's; a big
  disagreement is said."""

import numpy as np
import pytest

from caliper import fea_joints as FJ
from caliper import joint_check as JC

from .test_posts import LEGGED

# --- labelling ---------------------------------------------------------------------------------------------------------

LEG = {"key": "leg", "kind": "stick", "a": np.array([19.05, 19.05, 0.0]), "b": np.array([19.05, 19.05, 431.0]),
       "half": 19.05, "reach": 19.05 * 2 ** 0.5}


def _top():
    from caliper.consistency import _frame  # noqa: F401 — the sheet's frame, as shapes() makes it

    poly = np.array([(0, 0, 450.0), (400, 0, 450.0), (400, 400, 450.0), (0, 400, 450.0)])
    return {"key": "top", "kind": "sheet", "polys": [poly], "sides": [-1.0], "thickness": 19.0}


def test_a_square_leg_s_corners_are_the_leg_s_and_its_end_doesn_t_reach_the_top():
    h = 4.7625
    pts = np.array([[2.4, 2.4, 100.0],          # its corner: 4.4 mm outside a round leg's radius
                    [19.0, 19.0, 434.6],        # in the top, 3.6 mm over the leg's end: a round end would claim it
                    [19.0, 19.0, 200.0]])       # its middle
    got = FJ.labels(pts, [_top(), LEG], h)
    assert got.tolist() == [1, 0, 1]


def test_a_voxel_goes_to_the_nearest_piece_that_can_have_it():
    """Below an apron's bottom edge, in a leg's corner: the apron is nearer but can't claim it (2.7 mm past its edge);
    the leg can (4.5 mm out, within its corners). It went to neither, and the leg's forces leaked out through it."""
    apron = {"key": "apron", "kind": "sheet", "sides": [1.0], "thickness": 19.05,
             "polys": [np.array([(0, 38.1, 354.75), (0, 361.9, 354.75), (0, 361.9, 430.95), (0, 38.1, 430.95)])]}
    got = FJ.labels(np.array([[2.4, 35.7, 353.6]]), [apron, LEG], 4.7625)
    assert got.tolist() == [1]


def test_a_voxel_surely_inside_two_pieces_is_an_overlap_and_one_in_none_is_none():
    other = {**LEG, "key": "other", "a": LEG["a"] + [5.0, 0, 0], "b": LEG["b"] + [5.0, 0, 0]}
    got = FJ.labels(np.array([[20.0, 19.0, 100.0], [300.0, 300.0, 100.0]]), [LEG, other], 4.7625)
    assert got.tolist() == [FJ.OVERLAP, FJ.NONE]


# --- the moment, to the fixings ----------------------------------------------------------------------------------------

JOINT = {"pieces": ["apron", "top"], "edge": "apron", "face": "top", "kind": "butt", "out": np.array([0.0, 0.0, 1.0]),
         "normal": np.array([0.0, 0.0, 1.0]), "along": np.array([1.0, 0.0, 0.0]), "edge_t": 20.0, "length_mm": 300.0,
         "mid": np.zeros(3), "points": [], "screws": 0, "fix": ["glue", "screws"], "assumed": True, "face_t": 19.0,
         "area_mm2": 6000.0, "sin": 0.0}


def test_a_bonded_moment_is_a_pull_over_half_the_edge_or_half_its_length_and_a_turn_is_shear():
    zero = np.zeros(3)
    about_line, _ = FJ.demand(JOINT, zero, np.array([1000.0, 0, 0]))          # 1 N m about the joint's line
    assert about_line["withdrawal"] == pytest.approx(1000.0 / 10.0)               # over half the 20 mm edge
    across, _ = FJ.demand(JOINT, zero, np.array([0, 1500.0, 0]))
    assert across["withdrawal"] == pytest.approx(1500.0 / 150.0)                  # over half its 300 mm length
    turn, _ = FJ.demand(JOINT, zero, np.array([0, 0, 3000.0]))
    assert turn["shear"] == pytest.approx(3000.0 / 150.0) and turn["withdrawal"] == 0.0
    pushed, _ = FJ.demand(JOINT, np.array([0, 0, 500.0]), zero)
    assert pushed["bearing"] == pytest.approx(500.0) and pushed["withdrawal"] == 0.0


def test_declared_fixings_take_the_moment_at_the_farthest():
    """The foreman: where the joint's fixings are placed, the farthest takes M x / Σx² (here 100 mm and 50 mm out)."""
    j = {**JOINT, "points": [[-100.0, 0, 0], [-50.0, 0, 0], [50.0, 0, 0], [100.0, 0, 0]]}
    got, _ = FJ.demand(j, np.zeros(3), np.array([0, 1500.0, 0]))
    assert got["withdrawal"] == pytest.approx(1500.0 * 100.0 / (2 * 100.0 ** 2 + 2 * 50.0 ** 2))


def test_a_push_only_post_s_moment_pull_is_waived_and_its_lift_isn_t():
    post = {**JOINT, "post": True, "edge": "leg", "pieces": ["leg", "top"], "edge_t": 38.1, "length_mm": 38.1}
    got, waived = FJ.demand(post, np.array([0, 0, 300.0]), np.array([0, 2000.0, 0]))
    assert waived and got["withdrawal"] == 0.0 and got["bearing"] == pytest.approx(300.0)
    lifted, _ = FJ.demand(post, np.array([0, 0, -50.0]), np.array([0, 2000.0, 0]))
    assert lifted["withdrawal"] == pytest.approx(50.0)                           # the lift stays: ✗ as one
    said = FJ.row(post, {"force": np.array([0, 0, -50.0]), "moment": np.array([0, 2000.0, 0]), "nodes": 30}, 50.0, 2.0)
    assert said["safety"] == 0.0 and "the FEA lifts the leg off the top" in said["said"]


# --- beside the hand rule ----------------------------------------------------------------------------------------------

def _setup(*joints):
    return {"joints": list(joints), "pieces": [], "tol": 0.1, "screw_mm": 50.0}


def _hand(rows, chain=True, unchecked=()):
    gov = min((r for r in rows if r.get("safety") is not None), key=lambda r: r["safety"], default=None)
    return {"rows": rows, "governing": gov, "unchecked": list(unchecked), "chain": chain, "n": len(rows)}


SCREWED = {**JOINT, "screws": 4, "points": [[-100.0, 0, 0], [-50.0, 0, 0], [50.0, 0, 0], [100.0, 0, 0]]}


def _reading(force, moment=(0, 0, 0), residual=0.0, unbalanced=None, unread=None):
    got = {"unread": unread, "nodes": 40} if unread else {"force": np.asarray(force, float),
                                                          "moment": np.asarray(moment, float), "nodes": 40}
    return {"joints": {("apron", "top"): got}, "residual": residual, "unbalanced": unbalanced}


def test_the_lower_of_the_two_governs_and_a_big_disagreement_is_said():
    hand = _hand([{"pieces": ["apron", "top"], "between": "the apron and the top", "mode": "bearing", "safety": 9.0,
                   "need": 2.0, "holds": True, "said": "by hand", "demand_lb": {"bearing": 20.0}}])
    got = FJ.beside(hand, _reading([0, 0, 2000.0], [0, 1500.0, 0]), _setup(SCREWED), 2.0)
    r = got["rows"][0]
    assert r["by"] == "fea" and r["safety"] == r["fea"]["safety"] < 9.0 and got["governing"] is r
    assert FJ.BONDED in r["said"] and r["disagree"].startswith("the FEA puts ")
    calm = FJ.beside(hand, _reading([0, 0, 50.0]), _setup(SCREWED), 2.0)["rows"][0]
    assert calm["safety"] == 9.0 and "by" not in calm and "disagree" not in calm   # the hand's is lower: it stands


def test_where_the_hand_rule_has_none_the_fea_s_is_the_row():
    hand = _hand([], chain=False, unchecked=[JC.NOT_CHAIN])
    got = FJ.beside(hand, _reading([0, 0, 200.0]), _setup(SCREWED), 2.0)
    assert got["chain"] and got["unchecked"] == [] and got["by_hand"] == [JC.NOT_CHAIN]
    (r,) = got["rows"]
    assert r["by"] == "fea" and r["safety"] is not None and r["said"].startswith("not checked by hand; by the FEA")


def test_a_joint_the_fea_can_t_read_keeps_the_hand_s_or_stays_not_checked():
    hand = _hand([], chain=False, unchecked=[JC.NOT_CHAIN])
    got = FJ.beside(hand, _reading(None, unread=FJ.CANT_SEE.format(h=9.5)), _setup(SCREWED), 2.0)
    assert not got["chain"] and got["rows"] == [] and got["governing"] is None
    assert JC.NOT_CHAIN in got["unchecked"]
    assert "the joint between the apron and the top (the FEA can't see this joint at 9.5 mm voxels)" in got["unchecked"]
    rated = _hand([{"pieces": ["apron", "top"], "between": "the apron and the top", "mode": "bearing", "safety": 9.0,
                    "need": 2.0, "holds": True, "said": "by hand", "demand_lb": {"bearing": 20.0}}])
    kept = FJ.beside(rated, _reading(None, unread=FJ.LOADED_AT), _setup(SCREWED), 2.0)["rows"][0]
    assert kept["safety"] == 9.0 and kept["fea"] == {"unread": FJ.LOADED_AT}


def test_a_waived_pull_where_the_hand_rule_has_no_number_is_not_checked_never_ticked():
    """The foreman's limit 2: the load's only route is that joint, so the waiver can't tick it. What's left passing
    (a little shear) doesn't make it a number."""
    assert JC.capacity(JOINT, 50.0)["withdrawal"] == 0.0                         # glue on an edge, no screws: no pull
    hand = _hand([], chain=False, unchecked=[JC.NOT_CHAIN])
    got = FJ.beside(hand, _reading([0, 0, -200.0]), _setup(JOINT), 2.0)
    assert got["rows"] == [] and not got["chain"] and got["governing"] is None
    said = FJ.NO_PULL.format(edge="apron", face="top")
    assert f"the joint between the apron and the top ({said})" in got["unchecked"]
    sheared = FJ.beside(hand, _reading([5.0, 0, -200.0]), _setup(JOINT), 2.0)     # what's left fails: it still fails
    (r,) = sheared["rows"]
    assert r["safety"] == 0.0 and r["mode"] == "shear" and not r["holds"]


def test_one_joint_the_fea_didn_t_read_keeps_the_case_not_checked():
    other = {**SCREWED, "pieces": ["leg", "top"], "edge": "leg"}
    hand = _hand([], chain=False, unchecked=[JC.NOT_CHAIN])
    got = FJ.beside(hand, _reading([0, 0, 200.0]), _setup(SCREWED, other), 2.0)
    assert not got["chain"] and JC.NOT_CHAIN in got["unchecked"]


def test_forces_that_don_t_balance_read_nothing_from_the_fea():
    hand = _hand([], chain=False, unchecked=[JC.NOT_CHAIN])
    why = FJ.UNBALANCED.format(piece="top", pct=3.2)
    got = FJ.beside(hand, _reading([0, 0, 200.0], residual=0.032, unbalanced=why), _setup(SCREWED), 2.0)
    assert got["rows"] == [] and not got["chain"] and got["fea"]["unread"] == why


# --- on slice 1's stool: exact, balanced, and what it can't see --------------------------------------------------------

@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path_factory.mktemp("fea-joints") / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    ctx = L.prepare(store, "stool")
    ls, load = ctx["ls"], ctx["loads"][1]                                         # its rating, at the middle
    ls.loads = []
    ls.load(tuple(float(v) * load["factor"] for v in load["force"]), box=ctx["boxes"][1])
    solver = ls.solver()
    r = solver.solve(ls.solid)
    return ctx, solver, r, load


def _read(solved, **kw):
    from caliper import load_study as L

    ctx, solver, r, _ = solved
    return FJ.read(solver, r, ctx["ls"].grid, ctx["joints"]["pieces"], ctx["joints"]["joints"],
                   kw.get("through", L.VOXELS_THROUGH))


def test_every_piece_of_the_stool_balances(solved):
    got = _read(solved)
    assert got["unbalanced"] is None and got["residual"] < 1e-4, got["each"]
    assert set(got["each"]) == {pc["key"] for pc in solved[0]["joints"]["pieces"]}


def test_what_the_top_s_joints_carry_is_its_load(solved):
    """Statics, read off the joints: what the legs and aprons put up into the top is what's on it."""
    got = _read(solved)["joints"]
    up = sum(row["force"][2] for (a, b), row in got.items() if "top" in (a, b) and "force" in row)
    assert up == pytest.approx(solved[3]["lb"] * solved[3]["factor"] * 4.4482216, rel=1e-3)
    legs = [got[k]["force"][2] for k in got if "top" in k and "leg" in " ".join(k)]
    assert len(legs) == 4 and np.ptp(legs) < 1e-6 * max(legs)                    # the rating's in the middle: alike


def test_a_joint_too_thin_to_see_isn_t_read(solved):
    got = _read(solved, through=100)["joints"]
    assert got and all(row.get("unread") == FJ.CANT_SEE.format(h=solved[0]["spacing"]) for row in got.values())


def test_a_load_on_a_joint_s_own_nodes_isn_t_read_as_the_joint_s(solved):
    ctx, solver, r, load = solved
    first = _read(solved)["joints"]
    pair = next(k for k in first if "front left leg" in k and "top" in k)
    keep = solver.forces.copy()
    try:
        # a newton on one node the leg and the top share: their joint can't tell it from the leg's push
        flat = np.flatnonzero(np.asarray(r.solid).ravel())
        lab = FJ.labels(np.asarray(ctx["ls"].grid.origin) + ctx["spacing"] * np.stack(
            np.unravel_index(flat, ctx["ls"].grid.shape), axis=1), ctx["joints"]["pieces"], ctx["spacing"])
        keys = [pc["key"] for pc in ctx["joints"]["pieces"]]
        leg, top = keys.index("front left leg"), keys.index("top")
        node = np.intersect1d(solver._nodes[flat[lab == leg]].ravel(), solver._nodes[flat[lab == top]].ravel())[0]
        solver.forces[0, 3 * node + 2] += -1.0
        assert _read(solved)["joints"][pair] == {"unread": FJ.LOADED_AT, "nodes": first[pair]["nodes"]}
    finally:
        solver.forces[:] = keep


OVERLAPPED = LEGGED.replace('''    z0, z1 = h - t - a, h - t''', '''    z0, z1 = h - t - a, h - t + 6''')


def test_aprons_declared_up_into_the_top_don_t_balance_and_aren_t_read(tmp_path):
    """The foreman: pin an overlapping pair. Aprons declared 6 mm up into the top: the voxels in both are an overlap,
    no piece's, and what passes through them is no joint's, so the statics pin reads it and nothing is read."""
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", OVERLAPPED, intent="a four-legged stool with aprons")
    ctx = L.prepare(store, "stool")
    ls, load = ctx["ls"], ctx["loads"][1]
    ls.loads = []
    ls.load(tuple(float(v) * load["factor"] for v in load["force"]), box=ctx["boxes"][1])
    solver = ls.solver()
    r = solver.solve(ls.solid)
    got = FJ.read(solver, r, ls.grid, ctx["joints"]["pieces"], ctx["joints"]["joints"], L.VOXELS_THROUGH)
    assert got["residual"] > FJ.STATICS_TOL and got["unbalanced"].startswith("the FEA's forces don't balance on the ")


# --- the foreman's (iii): an edge joint's pull is the bonded model's; a post's lift and a raked leg's thrust aren't -----

def test_an_edge_joint_s_direct_pull_is_waived_past_the_rake_s_thrust_and_a_post_s_lift_isn_t():
    opened, waived = FJ.demand(JOINT, np.array([0, 0, -80.0]), np.zeros(3), pull_cap=0.0)
    assert waived and opened["withdrawal"] == 0.0                                     # no pull to give: it goes round
    tied, waived = FJ.demand(JOINT, np.array([0, 0, -80.0]), np.array([1000.0, 0, 0]), pull_cap=0.0, keep=30.0)
    assert waived and tied["withdrawal"] == pytest.approx(30.0)                       # the rake's thrust, kept
    held, waived = FJ.demand(JOINT, np.array([0, 0, -80.0]), np.zeros(3), pull_cap=500.0)
    assert not waived and held["withdrawal"] == pytest.approx(80.0)                   # a joint that holds a pull: asked
    post = {**JOINT, "post": True, "edge": "leg", "pieces": ["leg", "top"]}
    lifted, _ = FJ.demand(post, np.array([0, 0, -80.0]), np.zeros(3), pull_cap=0.0)
    assert lifted["withdrawal"] == pytest.approx(80.0)                                # a post's lift: ✗, as one


RAKED = '''import math
import cadquery as cq

PARAMS = {"w": 400.0, "d": 400.0, "h": 450.0, "rake": 10.0}
BUILD = {"t": 19.05, "leg": 38.1, "apron": 76.2}


def _legs(p):
    t, L = BUILD["t"], BUILD["leg"]
    w, d = p["w"], p["d"]
    return {"front left leg": (L / 2, L / 2, 1), "front right leg": (w - L / 2, L / 2, -1),
            "back left leg": (L / 2, d - L / 2, 1), "back right leg": (w - L / 2, d - L / 2, -1)}


def _end(p, z):
    """Where a front or back apron's left end meets the left legs' inner face, at height z."""
    t, L = BUILD["t"], BUILD["leg"]
    th = math.radians(p["rake"])
    return L / 2 + (L / 2 + math.sin(th) * (z - (p["h"] - t))) / math.cos(th)


def build(params):
    p = {**PARAMS, **(params or {})}
    t, L, a = BUILD["t"], BUILD["leg"], BUILD["apron"]
    w, d, h = p["w"], p["d"], p["h"]
    top = h - t
    out = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, top))
    for x, y, s in _legs(p).values():
        stick = (cq.Workplane().box(L, L, 2000).rotate((0, 0, 0), (0, 1, 0), s * p["rake"]).translate((x, y, top))
                 .intersect(cq.Workplane().box(w * 3, d * 3, top, centered=(True, True, False)).translate((w / 2, d / 2, 0))))
        out = out.union(stick)
    z0, z1 = top - a, top
    for y0 in (0.0, d - t):
        pts = [(_end(p, z0), z0), (w - _end(p, z0), z0), (w - _end(p, z1), z1), (_end(p, z1), z1)]
        out = out.union(cq.Workplane("XZ").polyline(pts).close().extrude(-t).translate((0, y0, 0)))
    for x0 in (0.0, w - t):
        out = out.union(cq.Workplane().box(t, d - 2 * L, a, centered=False).translate((x0, L, z0)))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, L, a = BUILD["t"], BUILD["leg"], BUILD["apron"]
    w, d, h = p["w"], p["d"], p["h"]
    top = h - t
    run = math.tan(math.radians(p["rake"])) * top
    items = [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]}]
    for n, (x, y, s) in _legs(p).items():
        items.append({"name": n, "kind": "stick", "material": "lumber", "size": "2x2",
                      "a": (x - s * run, y, 0), "b": (x, y, top)})
    z0, z1 = top - a, top
    for n, y in (("front apron", 0.0), ("back apron", d)):
        items.append({"name": n, "kind": "sheet", "material": "plywood", "thickness": t,
                      "outline": [(_end(p, z0), y, z0), (w - _end(p, z0), y, z0), (w - _end(p, z1), y, z1), (_end(p, z1), y, z1)]})
    items += [{"name": "left apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(0, L, z0), (0, d - L, z0), (0, d - L, z1), (0, L, z1)]},
              {"name": "right apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(w, L, z0), (w, d - L, z0), (w, d - L, z1), (w, L, z1)]}]
    return items


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h = p["w"], p["d"], p["h"]
    return [{"name": "its rating", "kg": 120, "factor": 1.0, "lo": (100, 100, h - 2), "hi": (w - 100, d - 100, h)}]
'''



def _study(tmp_path, script, name="stool"):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path / name / "designs"))
    store.write_part("stool", script, intent="a four-legged stool with aprons")
    return L.study(store, "stool")


def test_legs_raked_10_degrees_on_glue_only_aprons_read_x(tmp_path):
    """The foreman's guard: splayed legs under a vertical load push their tops out, H = R tan(rake), by statics, and the
    aprons are all that ties them. That pull is real, never waived as the bonded model's: glue on an end, 0 pull, ✗."""
    (c,) = _study(tmp_path, RAKED)["cases"]
    assert not c["holds"] and c["governs"] == "joint" and c["safety"] == 0.0
    assert not c["joints"]["unchecked"]          # every apron's end found on its leg, the side ones too (read beside it)
    tied = [r for r in c["joints"]["rows"] if "rake_n" in r and r["rake_n"] > 0]
    assert {r["between"] for r in tied} == {f"the {leg} and the {a} apron" for leg, a in (
        ("front left leg", "front"), ("front right leg", "front"), ("back left leg", "back"), ("back right leg", "back"))}
    for r in tied:
        assert r["safety"] == 0.0 and r["mode"] == "withdrawal" and "by" not in r
        assert r["said"].startswith(f"the legs splay and the {r['edge']} is all that ties them (it leans 10°)")


def test_an_upright_stool_s_top_bears_on_its_aprons_and_their_ends_shear_off_the_legs(tmp_path):
    """The foreman's (α): the top bears down on the aprons' top edges by contact, and contact is real, so what the aprons
    hand the legs through their ends' screws stands. The hand rule's "the legs carry it all" is the optimistic side: the
    corner case reads ✗ 0.5 at the front right leg's apron end, said so. The legs' own ends read the hand rule's, the
    lower there (limit 3: the bonded path takes load off them)."""
    rec = _study(tmp_path, LEGGED)
    corner = next(c for c in rec["cases"] if c["name"].startswith("sitting"))
    g = corner["joints"]["governing"]
    assert not corner["holds"] and corner["governs"] == "joint" and corner["safety"] == pytest.approx(0.5, abs=0.01)
    assert g["by"] == "fea" and g["mode"] == "shear" and set(g["pieces"]) == {"front right leg", "front apron"}
    assert ("the top bears on the front apron, and it hands 179 lb to the front right leg through one #8 screw in shear "
            "into the front apron's edge") in g["said"], g["said"]
    assert g["fix"] == ("3 more #8 screws at the front apron's end, 4 in all, would read 2×, past 2 (4 screws 0.75 in "
                        "apart in a 3 in joint: close enough to split the edge; consider a longer joint or a bigger "
                        "screw)")                                              # 179 lb × 2: no glue block (#344)
    from caliper import answers, verdicts

    hedge = answers.fail_hedge(rec, corner, verdicts.case(rec, corner), True)
    assert hedge.endswith(" 3 more #8 screws at the front apron's end, 4 in all, would read 2×, past 2 (4 screws 0.75 "
                          "in apart in a 3 in joint: close enough to split the edge; consider a longer joint or a "
                          "bigger screw)."), hedge
    leg = next(r for r in corner["joints"]["rows"] if r["between"] == "the top and the front right leg")
    assert leg["safety"] == pytest.approx(2.93, abs=0.01) and "by" not in leg and leg["fea"]["safety"] > leg["safety"]
    for c in rec["cases"]:
        assert not [r for r in c["joints"]["rows"] if "rake_n" in r]                 # upright: no rake


def _apron_pair(top_force, **top_joint):
    """An apron's end on a leg and its top edge on the top, as setup places them, and an FEA reading of each: the top
    joint by ``top_force`` (what the apron puts into the top), the end by 150 N of shear along the leg."""
    end = {**JOINT, "pieces": ["front apron", "leg"], "edge": "front apron", "face": "leg", "apron": True,
           "out": np.array([1.0, 0, 0]), "normal": np.array([1.0, 0, 0]), "along": np.array([0, 0, 1.0]), "screws": 1,
           "points": [], "edge_t": 19.05, "length_mm": 76.2}
    top = {**JOINT, "pieces": ["front apron", "top"], "edge": "front apron", "face": "top", **top_joint}
    reading = {"joints": {("front apron", "leg"): {"force": np.array([0, 0, -150.0]), "moment": np.zeros(3), "nodes": 30},
                          ("front apron", "top"): {"force": np.asarray(top_force, float), "moment": np.zeros(3),
                                                   "nodes": 90}},
               "residual": 0.0, "unbalanced": None}
    hand = _hand([{"pieces": ["front apron", "leg"], "between": "the leg and the front apron", "mode": None,
                   "safety": None, "holds": True, "said": "carries none of this load"},
                  {"pieces": ["front apron", "top"], "between": "the top and the front apron", "mode": None,
                   "safety": None, "holds": True, "said": "carries none of this load"}])
    return FJ.beside(hand, reading, _setup(end, top), 2.0)


def test_what_the_fea_can_see_and_when_it_balances_are_pinned_at_their_bars():
    """caliper-reviewer at #344: MIN_NODES, STATICS_TOL and DISAGREE pinned at their edges."""
    assert (FJ.MIN_NODES, FJ.STATICS_TOL, FJ.DISAGREE) == (4, 0.01, 0.25)
    assert FJ.sees(2.0, 2, 4) and not FJ.sees(2.0, 2, 3) and not FJ.sees(1.99, 2, 40)
    assert FJ.unbalanced_by(0.01, "top") is None
    assert FJ.unbalanced_by(0.0101, "top") == FJ.UNBALANCED.format(piece="top", pct=1.01)


@pytest.mark.parametrize("fea_lb, said", [(125.0, True), (124.9, False)])
def test_a_disagreement_is_said_from_a_quarter_more_than_the_hand_rule(fea_lb, said):
    hand = _hand([{"pieces": ["apron", "top"], "between": "the apron and the top", "mode": "bearing", "safety": 0.01,
                   "need": 2.0, "holds": False, "said": "by hand", "demand_lb": {"bearing": 100.0}}])
    r = FJ.beside(hand, _reading([0, 0, fea_lb * JC.LBF]), _setup(SCREWED), 2.0)["rows"][0]
    assert r["fea"]["demand_lb"] == {"bearing": fea_lb} and ("disagree" in r) is said
    if said:
        assert r["disagree"] == "the FEA puts 25% more on it than the hand rule"


def test_an_apron_end_s_shear_stands_where_the_top_bears_on_it_and_goes_round_where_it_hangs():
    pushed = next(r for r in _apron_pair([0, 0, 300.0])["rows"] if r["between"] == "the leg and the front apron")
    assert pushed["by"] == "fea" and pushed["mode"] == "shear" and pushed["safety"] is not None
    assert "the top bears on the front apron, and it hands 34 lb to the leg through" in pushed["said"]
    hung = next(r for r in _apron_pair([0, 0, -300.0])["rows"] if r["between"] == "the leg and the front apron")
    assert hung["safety"] is None and "by" not in hung and hung["fea"]["waived"]
    assert FJ.HUNG.format(apron="front apron", top="top", leg="leg", by="a glue line that gets no credit in a pull") \
        in hung["fea"]["said"]


def test_a_hung_apron_s_shear_stands_where_its_fixings_to_the_top_hold_a_pull(monkeypatch):
    """The foreman (#344): the waiver turns on the top joint's pull capacity, in code. Today an edge's screws hold no
    pull (WITHDRAW_EDGE_LB 0), so a screwed hang is waived; credited one, the hang is carried and the shear stands."""
    waived = next(r for r in _apron_pair([0, 0, -300.0], screws=2)["rows"] if r["between"] == "the leg and the front apron")
    assert waived["safety"] is None and waived["fea"]["waived"]
    assert "by two #8 screws and glue, so what it hands the leg goes round it" in waived["fea"]["said"]
    monkeypatch.setattr(JC, "WITHDRAW_EDGE_LB", 50.0)
    held = next(r for r in _apron_pair([0, 0, -300.0], screws=2)["rows"] if r["between"] == "the leg and the front apron")
    assert held["by"] == "fea" and held["mode"] == "shear" and held["safety"] is not None and not held["fea"]["waived"]
    assert ("the front apron hangs from the top by two #8 screws and glue, which hold a pull, and it hands 34 lb to the "
            "leg through") in held["said"], held["said"]


@pytest.mark.parametrize("fix, screws, by", [(["glue", "screws"], 2, "two #8 screws and glue"),
                                             (["screws"], 1, "one #8 screw"),
                                             (["glue"], 2, "a glue line that gets no credit in a pull"),
                                             ([], 0, "nothing that holds a pull")])
def test_a_hung_apron_s_words_name_what_holds_it_to_the_top(fix, screws, by):
    """caliper-reviewer at #344: "a glue line" was said of an apron screwed to the top."""
    assert FJ.held_by({"fix": fix, "screws": screws}) == by


def test_legs_short_of_the_top_don_t_come_out_ticked_through_the_waiver(tmp_path):
    """The foreman's limit 2: where the load's only way down is the aprons (legs 3 mm short), the hand rule's ✗ (an apron's
    end on a leg, 0.94) stands: the FEA's waiver can't make it ✓."""
    from .test_posts import BUILT, DECLARED

    short = LEGGED.replace(BUILT, BUILT.replace("h - t)", "h - t - 3)")).replace(DECLARED, DECLARED.replace("h - t)", "h - t - 3)"))
    corner = next(c for c in _study(tmp_path, short)["cases"] if c["name"].startswith("sitting"))
    assert not corner["holds"] and corner["safety"] <= 0.94
    assert corner["joints"]["path"] == "the legs stop short of the top: it rests on its aprons, then the legs"


def test_a_count_from_the_hand_rule_reads_the_fea_s_side_too_where_that_s_lower_then():
    """#344: the hand rule fails in shear (1.9) and the FEA's side passes in bearing (2.2), which screws don't move. The
    count is the hand's, 5; what it would read is the lower of the two there, the FEA's, never the hand's 2.37."""
    shear = JC.capacity(JC.screwed(SCREWED, 4), 50.0)["shear"] / 1.9
    hand = _hand([{"pieces": ["apron", "top"], "between": "the apron and the top", "mode": "shear", "safety": 1.9,
                   "need": 2.0, "holds": False, "said": "by hand",
                   "demands_n": [{"bearing": 0.0, "withdrawal": 0.0, "shear": shear}]}])
    push = JC.capacity(SCREWED, 50.0)["bearing"] / 2.2
    r = FJ.beside(hand, _reading([0, 0, push]), _setup(SCREWED), 2.0)["rows"][0]
    assert r["safety"] == 1.9 and "by" not in r and r["fea"]["safety"] >= 2.0 and r["fea"]["mode"] == "bearing"
    more = r["more_screws"]
    by_hand = JC._by_hand(SCREWED, hand["rows"][0]["demands_n"], 50.0)
    assert more["to"] == 5 and more["reads"] == r["fea"]["safety"] < by_hand(5)


def test_a_hand_number_with_no_demand_to_read_again_gets_no_count():
    """A guard: a row the hand rule numbered without saying its demand (none is built so) gets no count, rather than
    one only the FEA's side would pass."""
    hand = _hand([{"pieces": ["apron", "top"], "between": "the apron and the top", "mode": "shear", "safety": 1.0,
                   "need": 2.0, "holds": False, "said": "by hand"}])
    r = FJ.beside(hand, _reading([400.0, 0, 0]), _setup(SCREWED), 2.0)["rows"][0]
    assert r["safety"] == 1.0 and r["fea"]["safety"] > 1.0 and "more_screws" not in r and "fix" not in r
