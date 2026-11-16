"""CALI-194 (#316) slice 1: posts. Theo, on #301's decision 5: "we will often use posts, and we need to be able to model
them". A top on posts shares its load by the rigid-top rule (the top stiff, the posts alike): each post's share is
1/N plus the load's lever about the posts' centroid, R_i = P/N + Mx·y_i/Σy² + My·x_i/Σx², exact for three posts, the
textbook answer for a stiff top; four or more is indeterminate, and this is its closed form (C, with the FEA's joint
forces beside it in slice 2). Synthetic fixtures only."""

import numpy as np
import pytest

from caliper import joint_check as JC

#: Four posts at ±100 (a diamond), as #311's ring.
RING = [np.array([100.0, 0.0, 0.0]), np.array([-100.0, 0.0, 0.0]), np.array([0.0, 100.0, 0.0]), np.array([0.0, -100.0, 0.0])]
SHORT = [(38.1, 400.0)] * 4                                  # each a post: its joint 38 mm of a 400 mm top


def _moments(mids, at, shares):
    """The shares' sum and their moment about the load: 1 and 0 for any statically sound split."""
    P = np.array([m[:2] for m in mids])
    s = np.asarray(shares)
    return float(s.sum()), (s[:, None] * (P - np.asarray(at[:2]))).sum(axis=0)


def test_a_ring_of_posts_shares_by_the_rigid_top_rule_and_lets_a_lifted_post_go():
    """#311 read this "its supports are short", not checked. The plane over all four: Σx² = 2·100², so the near post
    1/4 + 90·100/20000 = 0.70, the far one 1/4 − 0.45 = −0.20, a pull. A post holds no pull (its screws are in its end
    grain: #301 decision 2), so the far one is let go and the three that stay share it exactly: the near one
    90/100 = 0.9, the two beside 0.05 each, as #311 said statics needs ("0.9 or more")."""
    got = JC._lever(RING, np.array([90.0, 0.0, 0.0]), "pairs", spans=SHORT)
    assert got == pytest.approx([0.9, 0.0, 0.05, 0.05])
    total, moment = _moments(RING, np.array([90.0, 0.0, 0.0]), got)
    assert total == pytest.approx(1.0) and moment == pytest.approx([0.0, 0.0], abs=1e-9)


def test_a_load_inside_the_posts_lifts_none_and_takes_the_plane_as_it_is():
    """The load at (30, 0): 1/4 ± 30·100/20000 = 0.40 and 0.10, the two beside 1/4: none lifted."""
    got = JC._lever(RING, np.array([30.0, 0.0, 0.0]), "pairs", spans=SHORT)
    assert got == pytest.approx([0.40, 0.10, 0.25, 0.25])


def test_a_load_past_the_posts_tips_not_a_joint_s_to_hold():
    with pytest.raises(JC.NotChain) as e:
        JC._lever(RING, np.array([150.0, 0.0, 0.0]), "pairs", spans=SHORT)
    assert e.value.why == JC.TIPS


def test_four_legs_at_a_stool_s_corners():
    """Legs at (±180, ±180), the load toward the front right corner at (130, −130). The plane over all four puts the
    back left leg at 1/4 − 2·130/720 = −0.11: lifted, so let go; the other three share it exactly."""
    legs = [np.array([x, y, 0.0]) for x, y in ((-180, -180), (180, -180), (-180, 180), (180, 180))]
    at = np.array([130.0, -130.0, 0.0])
    got = JC._lever(legs, at, "pairs", spans=SHORT)
    three = [legs[0], legs[1], legs[3]]
    exact = np.linalg.solve(np.vstack([np.ones(3), [p[0] for p in three], [p[1] for p in three]]), [1.0, 130.0, -130.0])
    assert got == pytest.approx([exact[0], exact[1], 0.0, exact[2]])
    assert got[1] == pytest.approx(0.25 + 130 / 360 + 0.111111, abs=1e-6)          # the front right leg: 0.72
    total, moment = _moments(legs, at, got)
    assert total == pytest.approx(1.0) and moment == pytest.approx([0.0, 0.0], abs=1e-9)


def test_three_posts_are_exact_and_an_uneven_layout_keeps_its_cross_term():
    tripod = [np.array([0.0, 0.0, 0.0]), np.array([300.0, 0.0, 0.0]), np.array([50.0, 250.0, 0.0])]
    at = np.array([120.0, 60.0, 0.0])
    got = JC._lever(tripod, at, "pairs", spans=[(38.1, 400.0)] * 3)
    total, moment = _moments(tripod, at, got)
    assert total == pytest.approx(1.0) and moment == pytest.approx([0.0, 0.0], abs=1e-9)   # statics, by itself
    exact = np.linalg.solve(np.vstack([np.ones(3), [p[0] for p in tripod], [p[1] for p in tripod]]), [1.0, at[0], at[1]])
    assert got == pytest.approx(exact.tolist())


def test_posts_in_a_line_are_still_in_a_row():
    row = [np.array([0.0, 0.0, 0.0]), np.array([100.0, 0.0, 0.0]), np.array([200.0, 0.0, 0.0])]
    with pytest.raises(JC.NotChain) as e:
        JC._lever(row, np.array([90.0, 30.0, 0.0]), "pairs", spans=[(38.1, 400.0)] * 3)
    assert e.value.why == JC.IN_A_ROW


def test_two_posts_off_their_line_are_still_short_and_long_supports_still_pair():
    posts = [np.array([0.0, 0.0, 0.0]), np.array([100.0, 0.0, 0.0])]
    with pytest.raises(JC.NotChain) as e:
        JC._lever(posts, np.array([50.0, 20.0, 0.0]), "pairs", spans=[(20.0, 200.0)] * 2)
    assert e.value.why == JC.SHORT
    assert JC._lever(RING, np.array([90.0, 0.0, 0.0]), "pairs", spans=[(190.0, 200.0)] * 4) == pytest.approx(
        [0.475, 0.025, 0.25, 0.25])                                                         # #311's pairs, unchanged



# --- the scripted four-legged stool with aprons (Theo's test piece) ------------------------------------------------------

#: 2x2 lumber legs at the corners, a 3/4 in plywood top on them, and 3/4 in plywood aprons between the legs under it.
LEGGED = '''import cadquery as cq

PARAMS = {"w": 400.0, "d": 400.0, "h": 450.0}
BUILD = {"t": 19.05, "leg": 38.1, "apron": 76.2}


def _boxes(p):
    t, L, a = BUILD["t"], BUILD["leg"], BUILD["apron"]
    w, d, h = p["w"], p["d"], p["h"]
    out = {"top": ((0, 0, h - t), (w, d, h))}
    for n, (x, y) in {"front left leg": (0, 0), "front right leg": (w - L, 0), "back left leg": (0, d - L),
                      "back right leg": (w - L, d - L)}.items():
        out[n] = ((x, y, 0), (x + L, y + L, h - t))
    out["front apron"] = ((L, 0, h - t - a), (w - L, t, h - t))
    out["back apron"] = ((L, d - t, h - t - a), (w - L, d, h - t))
    out["left apron"] = ((0, L, h - t - a), (t, d - L, h - t))
    out["right apron"] = ((w - t, L, h - t - a), (w, d - L, h - t))
    return out


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, L, a = BUILD["t"], BUILD["leg"], BUILD["apron"]
    w, d, h = p["w"], p["d"], p["h"]
    items = [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]}]
    for n, (x, y) in {"front left leg": (0, 0), "front right leg": (w - L, 0), "back left leg": (0, d - L),
                      "back right leg": (w - L, d - L)}.items():
        items.append({"name": n, "kind": "stick", "material": "lumber", "size": "2x2",
                      "a": (x + L / 2, y + L / 2, 0), "b": (x + L / 2, y + L / 2, h - t)})
    z0, z1 = h - t - a, h - t
    items += [{"name": "front apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(L, 0, z0), (w - L, 0, z0), (w - L, 0, z1), (L, 0, z1)]},
              {"name": "back apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(L, d, z0), (w - L, d, z0), (w - L, d, z1), (L, d, z1)]},
              {"name": "left apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(0, L, z0), (0, d - L, z0), (0, d - L, z1), (0, L, z1)]},
              {"name": "right apron", "kind": "sheet", "material": "plywood", "thickness": t,
               "outline": [(w, L, z0), (w, d - L, z0), (w, d - L, z1), (w, L, z1)]}]
    return items


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h = p["w"], p["d"], p["h"]
    return [{"name": "sitting toward the front right corner", "lb": 250, "factor": 2.0,
             "lo": (w - 150, 50, h - 2), "hi": (w - 50, 150, h)},
            {"name": "its rating", "kg": 120, "factor": 1.0, "lo": (100, 100, h - 2), "hi": (w - 100, d - 100, h)}]
'''


LBF = 4.4482216


@pytest.fixture(scope="module")
def stool(tmp_path_factory):
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path_factory.mktemp("legs") / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    su = JC.setup(store, "stool")
    mesh = store.part_geometry("stool").require_mesh()
    held = [{"name": "the floor", "lo": list(mesh.bounds[0] - 1),
             "hi": [mesh.bounds[1][0] + 1, mesh.bounds[1][1] + 1, mesh.bounds[0][2] + 0.5]}]
    return store, su, held


def _cases(store):
    from caliper import construction as C
    from caliper import load_study as L

    return L.parse_loads([x for x in C.declared(store, "stool")["loads"] if not x.get("tip")])


LEGS = ("front left leg", "front right leg", "back left leg", "back right leg")
APRONS = ("front apron", "back apron", "left apron", "right apron")


def test_every_joint_of_the_stool_is_placed(stool):
    """Each leg's end bearing up into the top, each apron's edge under the top, each apron's end on a leg: placed,
    none named as not."""
    _, su, _ = stool
    joints = su["joints"]
    assert not [j for j in joints if "unplaced" in j], [j for j in joints if "unplaced" in j]
    posts = {j["edge"] for j in joints if j.get("post")}
    aprons = {(j["edge"], j["face"]) for j in joints if j.get("apron")}
    assert posts == set(LEGS) and len(aprons) == 8 and len(joints) == 16
    post = next(j for j in joints if j.get("post"))
    assert post["face"] == "top" and post["normal"] == pytest.approx([0, 0, 1])           # from the leg up into the top
    assert post["area_mm2"] == pytest.approx(38.1 ** 2, rel=1e-3)


def test_a_post_bears_at_360_psi_on_its_end_and_holds_no_pull(stool):
    _, su, _ = stool
    post = next(j for j in su["joints"] if j.get("post"))
    cap = JC.capacity(post, su["screw_mm"])
    assert cap["bearing"] / LBF == pytest.approx(JC.BEARING_PSI * 1.5 * 1.5, rel=1e-3)     # 810 lb on a 2x2's end
    assert cap["withdrawal"] == 0.0                                                     # end grain: no credit
    assert cap["shear"] / LBF == pytest.approx(post["screws"] * JC.SHEAR_FACE_LB * 0.67, rel=1e-6) if post["screws"]         else cap["shear"] == 0.0                                                         # NDS 12.5.2.2's Ceg
    assert cap["why"]["bearing"].endswith("leg's end bearing on the top")


def test_both_paths_each_joint_its_own_and_the_case_says_which_governs(stool):
    store, su, held = stool
    corner = _cases(store)[0]
    got = JC.check(su, corner, held, 2.0)
    assert got["chain"] and not got["unchecked"], got["unchecked"]
    rows = {r["between"]: r for r in got["rows"]}
    on_legs = [r for r in got["rows"] if str(r.get("path")).startswith("the top on its legs")]
    # the back left leg let go, three push: statics alone (the foreman's condition: say which)
    assert {r["path"] for r in on_legs} == {"the top on its legs, by statics (three posts)"}
    on_aprons = [r for r in got["rows"] if r.get("path") == JC.PATH_SAID["frame"]]
    # three legs carry it by the rigid-top rule; the back left one, which the top would lift off, carries none
    assert {tuple(sorted(r["pieces"])) for r in on_legs} == {tuple(sorted(("top", leg))) for leg in LEGS if leg != "back left leg"}
    assert rows["the top and the back left leg"]["said"] == "carries none of this load"
    assert len(on_aprons) == 12                                                          # 4 on the top, 8 on the legs
    assert got["path"] == got["governing"]["path"]
    # the front right leg, nearest the load, by the rigid-top rule: its share of 250 lb × 2, the back left let go
    posts = JC.demands(su["joints"], su["pieces"], corner, held, su["tol"], path="posts")
    fr = posts[("front right leg", "top")]["force"]
    mids = [next(j for j in su["joints"] if j.get("post") and j["edge"] == leg)["mid"] for leg in LEGS]
    at = (np.asarray(corner["lo"]) + np.asarray(corner["hi"])) / 2
    share = JC._rigid(mids, at)[1]
    assert -fr[2] == pytest.approx(share * 500 * LBF, rel=1e-6)
    assert ("back left leg", "top") not in posts or abs(posts[("back left leg", "top")]["force"][2]) < 1e-6   # let go


def test_each_leg_is_a_column_on_the_larger_of_the_two_paths(stool):
    """2x2 SPF, 430.95 mm long, K = 1: Euler π²EI/L² = 84 kN (18,900 lb), crushing 9.7 MPa × 1451.6 mm² = 14.1 kN
    (3,165 lb): crushing governs. Its load is the more of the top on its legs and the top on its aprons."""
    store, su, held = stool
    corner = _cases(store)[0]
    got = JC.check(su, corner, held, 2.0)
    col = {r["pieces"][0]: r for r in got["rows"] if r["between"].endswith(", as a column")}
    assert set(col) == set(LEGS)
    area = 38.1 ** 2
    assert col["front right leg"]["mode"] == "crushing"
    assert col["front right leg"]["capacity_lb"]["crushing"] == pytest.approx(9.7 * area / LBF, rel=1e-3)
    inertia = 38.1 ** 4 / 12
    euler = np.pi ** 2 * 9000 * inertia / 430.95 ** 2
    assert euler / LBF > col["front right leg"]["capacity_lb"]["crushing"]                 # Euler: 18,900 lb
    arrs = []
    for pth in ("posts", "frame"):
        arr = {}
        JC.demands(su["joints"], su["pieces"], corner, held, su["tol"], arrivals=arr, path=pth)
        arrs.append(arr)
    for leg in LEGS:                                     # each its more of the two, whichever path that is
        most = max(-float(arr[leg][2]) if leg in arr else 0.0 for arr in arrs)
        assert col[leg]["demand_lb"]["crushing"] == pytest.approx(most / LBF, abs=0.1), leg
    assert any(-float(arrs[1].get(leg, [0, 0, 0])[2]) > -float(arrs[0].get(leg, [0, 0, 0])[2]) for leg in LEGS)
    assert "pending Theo" in col["front right leg"]["said"]


def test_a_sideways_case_says_the_columns_racking_isn_t_checked(stool):
    store, su, held = stool
    corner = _cases(store)[0]
    f = np.asarray(corner["force"], float)
    side = {**corner, "force": (f + np.array([0.1 * np.linalg.norm(f), 0, 0])).tolist()}
    got = JC.check(su, side, held, 2.0)
    col = [r for r in got["rows"] if r["between"].endswith(", as a column")]
    assert col and all(JC.COLUMN_RACKING in r["said"] for r in col)
    assert any("as a column" in u and "racking" in u for u in got["unchecked"])
    assert JC.COLUMN_RACKING == "racking isn't checked (interim, #317)"


def test_a_seat_whose_legs_were_checked_as_columns_no_longer_says_their_buckling_isn_t(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import answers, design_api, tipping
    from caliper import load_study as L
    from caliper.design import DesignStore

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool to sit on")

    def seat_line():
        work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
        return next((ln["text"] for ln in work["lines"] if ln["text"].startswith("Not checked yet for a seat")), "")

    assert tipping.LEGS_BUCKLING in seat_line()                       # before a check: nothing checked them
    L.study(store, "stool")
    assert tipping.LEGS_BUCKLING not in seat_line(), seat_line()        # its legs, checked as columns



def test_each_joint_takes_the_larger_of_its_two_paths():
    small, big = {"from": "top", "force": np.array([0.0, 0.0, -100.0])}, {"from": "top", "force": np.array([0.0, 0.0, -300.0])}
    got, which = JC._larger({"posts": {("a", "b"): small, ("c", "d"): big}, "frame": {("a", "b"): big, ("c", "d"): small}})
    assert got[("a", "b")] is big and which[("a", "b")] == "frame"
    assert got[("c", "d")] is big and which[("c", "d")] == "posts"


def test_a_slender_post_buckles_by_euler_at_k_1():
    """A 1x1 (19.05 mm) lumber post 1000 mm long: π²·9000·19.05⁴/12 / 1000² = 975 N; crushing 9.7 × 362.9 = 3520 N, so
    Euler governs; at K = 2 it would be a quarter of that."""
    post = {"key": "post", "kind": "stick", "material": "lumber", "a": np.array([0.0, 0.0, 0.0]),
            "b": np.array([0.0, 0.0, 1000.0]), "half": 19.05 / 2, "volume": 19.05 ** 2 * 1000.0}
    row = JC.column_row(post, 100.0, 2.0)
    euler = np.pi ** 2 * 9000 * 19.05 ** 4 / 12 / 1000.0 ** 2
    assert row["mode"] == "column" and row["capacity_lb"]["column"] == pytest.approx(euler / LBF, abs=0.1)
    assert row["safety"] == pytest.approx(euler / 100.0, abs=0.01) and "K = 1" in row["said"]



def test_a_post_a_fixing_holds_in_a_pull_keeps_its_pull_share():
    """The foreman's condition: only a post with no pull credit is let go. The far one held: the plane, as it is."""
    got = JC._lever(RING, np.array([90.0, 0.0, 0.0]), "pairs", spans=SHORT, pulls=[False, True, False, False])
    assert got == pytest.approx([0.70, -0.20, 0.25, 0.25])


def test_a_stool_s_posts_hold_no_pull_today(stool):
    """Its fixings go into the legs' end grain (glue, screws): no pull credit, so a lifted leg is let go."""
    _, su, _ = stool
    assert [j["pull"] for j in su["joints"] if j.get("post")] == [False] * 4


def test_four_pushing_posts_are_said_as_shared_as_a_rigid_top(stool):
    """The rating, centred: all four legs push, so their split is the stiff top's answer, and the row says so."""
    store, su, held = stool
    rating = _cases(store)[1]
    got = JC.check(su, rating, held, 2.0)
    legs = [r for r in got["rows"] if str(r.get("path")).startswith("the top on its legs")]
    assert len(legs) == 4 and {r["path"] for r in legs} == {"the top on its legs, shared as a rigid top"}
