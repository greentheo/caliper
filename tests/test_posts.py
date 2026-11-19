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


def test_the_legs_reach_the_top_so_it_rests_on_them_and_a_lifted_leg_is_named(stool):
    """One path, from the geometry (#321): the legs' ends bear on the top's face, so the top shares among them by the
    rigid-top rule; the aprons carry none of a load on the top. The back left leg, which the top lifts off, says so."""
    store, su, held = stool
    corner = _cases(store)[0]
    got = JC.check(su, corner, held, 2.0)
    assert got["chain"] and not got["unchecked"], got["unchecked"]
    assert got["path"] == "the legs reach the top: the top rests on them, by statics (three legs)"
    rows = {r["between"]: r for r in got["rows"]}
    assert rows["the top and the back left leg"]["said"] == "the top lifts off it: the load is inside the other three legs"
    on_legs = [r for r in got["rows"] if r.get("path") and r["pieces"][0] in LEGS + ("top",) and "leg" in " ".join(r["pieces"])
               and not r["between"].endswith(", as a column") and r["mode"]]
    assert {tuple(sorted(r["pieces"])) for r in on_legs} >= {tuple(sorted(("top", leg))) for leg in LEGS if leg != "back left leg"}
    assert all(r["said"] == "carries none of this load" for r in got["rows"] if "apron" in " ".join(r["pieces"]))
    # the front right leg, nearest the load, by the rigid-top rule: its share of 250 lb × 2, the back left let go
    posts = JC.demands(su["joints"], su["pieces"], corner, held, su["tol"], path="posts")
    fr = posts[("front right leg", "top")]["force"]
    mids = [next(j for j in su["joints"] if j.get("post") and j["edge"] == leg)["mid"] for leg in LEGS]
    at = (np.asarray(corner["lo"]) + np.asarray(corner["hi"])) / 2
    shares = JC._rigid(mids, at)
    assert -fr[2] == pytest.approx(shares[1] * 500 * LBF, rel=1e-6) and shares.let_go == (LEGS.index("back left leg"),)


BUILT = "out[n] = ((x, y, 0), (x + L, y + L, h - t))"
DECLARED = '"b": (x + L / 2, y + L / 2, h - t)}'


#: A leg's top end, shaped (#321 re-check): a 10 mm hole 25 mm deep down its middle (a dowel's, a pilot's), a 24 mm bore
#: (a hollow print: every ray starts in it), a 15 mm or an 18 mm round on its edges, or a 10 mm dowel stub 3 mm long
#: (with the leg built 3 mm short: the stub reaches the top, the shoulder doesn't), or one corner notched 15 mm, 3 deep.
ENDS = {"hole": 'b = b.cut(cq.Workplane().circle(5).extrude(25).translate((lo[0] + L / 2, lo[1] + L / 2, hi[2] - 25)))',
        "bore": 'b = b.cut(cq.Workplane().circle(12).extrude(25).translate((lo[0] + L / 2, lo[1] + L / 2, hi[2] - 25)))',
        "round": 'b = b.faces(">Z").edges().fillet(15)', "round18": 'b = b.faces(">Z").edges().fillet(18)',
        "notch": 'b = b.cut(cq.Workplane().box(15, 15, 3, centered=False).translate((lo[0], lo[1], hi[2] - 3)))',
        "stub": 'b = b.union(cq.Workplane().circle(5).extrude(3).translate((lo[0] + L / 2, lo[1] + L / 2, hi[2])))',
        # a slot down one side of its end: the centre ray and the two on that side start in air, two in the solid
        "slot": 'b = b.cut(cq.Workplane().box(13, 20, 25, centered=False).translate((lo[0] + L / 2 - 3, lo[1] + L / 2 - 10, hi[2] - 25)))'}


def _gapped(tmp_path, built=0.0, declared=0.0, end=None):
    """The stool with its legs short of the top by ``built`` mm in its solid and ``declared`` mm in its pieces, each
    leg's top end shaped as :data:`ENDS` says."""
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    src = LEGGED.replace(BUILT, BUILT.replace("h - t)", f"h - t - {built})")) \
        .replace(DECLARED, DECLARED.replace("h - t)", f"h - t - {declared})"))
    if end:
        src = src.replace("    for lo, hi in _boxes(p).values():\n", "    L = BUILD['leg']\n    for n, (lo, hi) in _boxes(p).items():\n") \
            .replace("        out = b if out is None else out.union(b)",
                     f"        if n.endswith('leg'):\n            {ENDS[end]}\n        out = b if out is None else out.union(b)")
        assert ENDS[end] in src
    store = DesignStore.create("a stool", base=str(tmp_path / f"d{built}-{declared}-{end}" / "designs"))
    store.write_part("stool", src, intent="a four-legged stool with aprons")
    su = JC.setup(store, "stool")
    mesh = store.part_geometry("stool").require_mesh()
    held = [{"name": "the floor", "lo": list(mesh.bounds[0] - 1),
             "hi": [mesh.bounds[1][0] + 1, mesh.bounds[1][1] + 1, mesh.bounds[0][2] + 0.5]}]
    return store, su, held, JC.check(su, _cases(store)[0], held, 2.0)


def test_legs_that_stop_short_of_the_top_put_it_on_its_aprons(tmp_path):
    """The foreman's (b): 3 mm short, built and declared, the legs don't bear on the top, so it rests on its aprons,
    then the legs, and an apron's end on a leg governs: one #8 screw with 0.5 in in the apron's edge, 90 lb, at 0.94.
    Each leg's top says it stops short (#321 re-check), never as a joint not checked."""
    store, su, held, got = _gapped(tmp_path, built=3, declared=3)
    assert not [j for j in su["joints"] if j.get("post")]                       # no leg's end bears on the top
    assert got["path"] == "the legs stop short of the top: it rests on its aprons, then the legs"
    gov = got["governing"]
    assert "apron" in " ".join(gov["pieces"]) and gov["mode"] == "shear" and gov["safety"] == pytest.approx(0.94, abs=0.01)
    assert gov["capacity_lb"]["shear"] == pytest.approx(90.0, abs=0.5)
    short = [r["said"] for r in got["rows"] if "short of the top" in r["said"]]
    assert sorted(short) == sorted(f"the {leg} stops 3 mm short of the top: it doesn't bear" for leg in LEGS)
    assert not [u for u in got["unchecked"] if "leg" in u and "top" in u], got["unchecked"]


def test_a_leg_0_4_mm_short_still_bears(tmp_path):
    """Within BEARS_MM (0.5) in its pieces and in its solid: it bears, the legs' path."""
    _, su, _, got = _gapped(tmp_path, built=0.4, declared=0.4)
    assert len([j for j in su["joints"] if j.get("post")]) == 4
    assert got["path"].startswith("the legs reach the top")


@pytest.mark.parametrize("built, declared, said", [
    (3, 0, "the back left leg is declared flush with the top but built 3 mm short"),
    (0, 1, "the back left leg is declared 1 mm short of the top but built flush")])
def test_a_leg_declared_one_way_and_built_the_other_isn_t_checked_by_hand(tmp_path, built, declared, said):
    """The reviewer's two: built 3 mm short but declared flush read the legs bearing at 2.93 (a false green); flush but
    declared 1 mm short read the aprons at 0.94 (a false red). Neither side's number: not checked by hand, in words."""
    _, _, _, got = _gapped(tmp_path, built=built, declared=declared)
    assert not got["chain"] and got["rows"] == [] and got["unchecked"] == [said], got


def _rays(store, h=450.0, t=19.05, d=400.0, L=38.1):
    """The back left leg's five readings, mm short of the top: the centre, then the four toward its corners."""
    mesh = store.part_geometry("stool").require_mesh()
    return JC._built_gap(mesh, np.array([L / 2, d - L / 2, h - t]), np.array([0.0, 0.0, 1.0]), 0.0, L / 2,
                         np.array([1.0, 0.0, 0.0]))


@pytest.mark.parametrize("end, built, reads, rays", [
    ("hole", 0, "bears", [0, 0, 0, 0]),                      # the centre starts in the hole: not kept
    ("hole", 3, "short", [3, 3, 3, 3]),
    ("round", 0, "bears", [0, 0.1, 0.1, 0.1, 0.1]),
    ("round18", 0, "part", [0, 0.62, 0.62, 0.62, 0.62]),     # its corner rays drop down the round: only its middle
    ("round18", 3, "short", [3, 3.62, 3.62, 3.62, 3.62]),   # said by its least: "built 3 mm short"
    ("notch", 0, "bears", [0, 0, 0, 0, 3]),                  # all but one: it bears
    ("stub", 3, "part", [0, 3, 3, 3, 3])])                   # the foreman's: the stub touches, the shoulder's 3 short
def test_a_leg_s_end_is_read_across_it_not_down_its_middle(tmp_path, end, built, reads, rays):
    """The reviewer's re-check: a hole down the middle of a leg's end let the one ray up it and across a 3 mm gap, so a
    leg built short read as bearing (a false green). Five rays across the end, kept where they start in the solid. It
    bears where all of them but at most one touch; where some do, it touches at only part of its end, not checked by
    hand ("any" read a dowel stub with its shoulder 3 mm short as bearing, 2.93 where it's about 0.16)."""
    store, su, _, got = _gapped(tmp_path, built=built, declared=0, end=end)
    assert _rays(store) == pytest.approx(rays, abs=0.06)
    posts = [j for j in su["joints"] if j.get("post")]
    if reads == "bears":
        assert len(posts) == 4 and got["path"].startswith("the legs reach the top"), got["unchecked"]
        return
    assert not posts and not got["chain"]
    said = ("the back left leg is declared flush with the top but built 3 mm short" if reads == "short" else
            "the back left leg touches the top at only part of its end")
    assert said in got["unchecked"], got


def test_a_leg_end_no_ray_starts_inside_isn_t_measured(tmp_path):
    """A hollow leg, its bore wider than the rays: none starts in the solid, so its end isn't measured: not checked by
    hand, said so, never read as bearing or short."""
    _, su, _, got = _gapped(tmp_path, built=0, declared=0, end="bore")
    assert not [j for j in su["joints"] if j.get("post")] and not got["chain"]
    assert "the back left leg's built end at the top isn't measured: no ray across it starts inside the solid" \
        in got["unchecked"], got


def test_a_leg_end_only_two_rays_start_in_isn_t_measured(tmp_path):
    """caliper-reviewer on #321: with two or fewer rays kept, "all but one" falls back to "any", so a leg two rays read
    flush bore on the top. Too few to say it bears: not measured, the safe side (#316 slice 2)."""
    store, su, _, got = _gapped(tmp_path, built=0, declared=0, end="slot")
    assert _rays(store) == pytest.approx([0, 0], abs=0.06)                      # the two that start in the solid touch
    assert not [j for j in su["joints"] if j.get("post")] and not got["chain"]
    assert "the back left leg's built end at the top isn't measured: only two of its rays start inside the solid" \
        in got["unchecked"], got


def test_each_leg_is_a_column(stool):
    """2x2 SPF, 430.95 mm long, K = 1: Euler π²EI/L² = 84 kN (18,900 lb), crushing 9.7 MPa × 1451.6 mm² = 14.1 kN
    (3,165 lb): crushing governs. Its load is what comes down it."""
    store, su, held = stool
    corner = _cases(store)[0]
    got = JC.check(su, corner, held, 2.0)
    col = {r["pieces"][0]: r for r in got["rows"] if r["between"].endswith(", as a column")}
    assert set(col) == set(LEGS) - {"back left leg"}                      # the lifted one carries nothing down
    area = 38.1 ** 2
    assert col["front right leg"]["mode"] == "crushing"
    assert col["front right leg"]["capacity_lb"]["crushing"] == pytest.approx(9.7 * area / LBF, rel=1e-3)
    inertia = 38.1 ** 4 / 12
    euler = np.pi ** 2 * 9000 * inertia / 430.95 ** 2
    assert euler / LBF > col["front right leg"]["capacity_lb"]["crushing"]                 # Euler: 18,900 lb
    arr = {}
    JC.demands(su["joints"], su["pieces"], corner, held, su["tol"], arrivals=arr, path="posts")
    for leg in LEGS:
        if leg in col:
            assert col[leg]["demand_lb"]["crushing"] == pytest.approx(-float(arr[leg][2]) / LBF, abs=0.1), leg
    assert col["front right leg"]["said"].endswith("crushing along its grain (9.7 MPa)")   # Theo's, 2026-11-16


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



def test_a_slender_post_buckles_by_euler_at_k_1():
    """A 1x1 (19.05 mm) lumber post 1000 mm long: π²·9000·19.05⁴/12 / 1000² = 975 N; crushing 9.7 × 362.9 = 3520 N, so
    Euler governs; at K = 2 it would be a quarter of that."""
    post = {"key": "post", "kind": "stick", "material": "lumber", "a": np.array([0.0, 0.0, 0.0]),
            "b": np.array([0.0, 0.0, 1000.0]), "half": 19.05 / 2, "volume": 19.05 ** 2 * 1000.0}
    row = JC.column_row(post, 100.0, 2.0)
    euler = np.pi ** 2 * 9000 * 19.05 ** 4 / 12 / 1000.0 ** 2
    assert row["mode"] == "column" and row["capacity_lb"]["column"] == pytest.approx(euler / LBF, abs=0.1)
    assert row["safety"] == pytest.approx(euler / 100.0, abs=0.01) and "K = 1" in row["said"]



def test_four_pushing_posts_are_said_as_shared_as_a_rigid_top(stool):
    """The rating, centred: all four legs push, so their split is the stiff top's answer, and the row says so."""
    store, su, held = stool
    rating = _cases(store)[1]
    got = JC.check(su, rating, held, 2.0)
    assert got["path"] == "the legs reach the top: the top rests on them, shared as a rigid top"
    legs = [r for r in got["rows"] if "top" in r["pieces"] and r["mode"] and "leg" in " ".join(r["pieces"])]
    assert len(legs) == 4 and {r["path"] for r in legs} == {got["path"]}



def test_a_2x4_post_buckles_about_its_weak_axis():
    """A 2x4 (38.1 × 88.9 mm) 1500 mm long: about its weak axis, I = 88.9 × 38.1³ / 12 = 409,700 mm⁴, Euler 16.2 kN,
    under its crushing (9.7 × 3,387 = 32.9 kN), so it governs. About the strong axis it would read 5.4 times that."""
    post = {"key": "post", "kind": "stick", "material": "lumber", "a": np.array([0.0, 0.0, 0.0]),
            "b": np.array([0.0, 0.0, 1500.0]), "half": 38.1 / 2, "volume": 38.1 * 88.9 * 1500.0}
    row = JC.column_row(post, 1000.0, 2.0)
    weak = np.pi ** 2 * 9000 * (88.9 * 38.1 ** 3 / 12) / 1500.0 ** 2
    assert row["mode"] == "column" and row["capacity_lb"]["column"] == pytest.approx(weak / LBF, abs=0.5)
