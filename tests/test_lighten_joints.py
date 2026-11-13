"""CALI-172 (#268), Theo's step-stool-5: Lighten cut holes through the wood where the bottom stringer passes through the sides.
The 1.5 in rim kept solid wood round each panel's outline only; a piece meeting a panel in its middle (a through-stringer, a
dado, a cleat, a rail on a face) had nothing. Every contact between pieces keeps the same rim. A synthetic stool, not Theo's."""

import numpy as np
import pytest

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

from caliper import lighten  # noqa: E402
from caliper import load_study as L  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

#: Two sides under a step, and a stringer 4 in tall passing through both sides 2 in off the floor (a through-mortise in each),
#: sticking out 1 in past each; a cleat glued on the left side's inside face, half way up, and a grip on its outside face.
THROUGH = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 406.4, "d": 304.8, "h": 457.2}


def _boxes(p):
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    return {"left side": ((0, 0, 0), (t, d, h)), "right side": ((w - t, 0, 0), (w, d, h)),
            "step": ((0, 0, h), (w, d, h + t)),
            "stringer": ((-25.4, d / 2 - t / 2, 50.8), (w + 25.4, d / 2 + t / 2, 50.8 + 101.6)),
            "cleat": ((t, 50.8, 228.6), (t + t, 50.8 + 76.2, 228.6 + 38.1)),
            "grip": ((-t, 203.2, 304.8), (0, 254.0, 342.9))}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    y0, z0 = d / 2 - t / 2, 50.8
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)]},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]},
            {"name": "stringer", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(-25.4, y0, z0), (w + 25.4, y0, z0), (w + 25.4, y0, z0 + 101.6), (-25.4, y0, z0 + 101.6)]},
            {"name": "cleat", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t + t, 50.8, 228.6), (t + t, 50.8 + 76.2, 228.6), (t + t, 50.8 + 76.2, 228.6 + 38.1),
                         (t + t, 50.8, 228.6 + 38.1)]},
            {"name": "grip", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(-t, 203.2, 304.8), (-t, 254.0, 304.8), (-t, 254.0, 342.9), (-t, 203.2, 342.9)]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h, t = p["w"], p["d"], p["h"], p["t"]
    return [{"name": "standing on the step", "lb": 250, "factor": 2.0,
             "lo": (w / 2 - 50, d / 2 - 50, h + t - 2), "hi": (w / 2 + 50, d / 2 + 50, h + t)}]
'''

T, D = 19.05, 304.8
#: Where the stringer and the cleat meet each side, in (y, z): the stringer's mortise, the cleat's face.
MORTISE = ((D / 2 - T / 2, 50.8), (D / 2 + T / 2, 50.8 + 101.6))
CLEAT = ((50.8, 228.6), (50.8 + 76.2, 228.6 + 38.1))
GRIP = ((203.2, 304.8), (254.0, 342.9))


@pytest.fixture(scope="module")
def sides(tmp_path_factory):
    s = DesignStore.create("a step stool", base=str(tmp_path_factory.mktemp("through") / "designs"))
    s.write_part("stool", THROUGH, intent="two sides, a step and a through-stringer")
    ctx = L.prepare(s, "stool")
    return ctx, {p["name"]: p for p in lighten.panels(ctx)}


def _cells_yz(ctx, p, mask):
    """A side panel's cells, as (y, z) in the stool."""
    s = ctx["spacing"]
    uv = (np.argwhere(mask) + 0.5) * s + p["lo"]
    xyz = p["o"] + uv[:, :1] * p["u"] + uv[:, 1:] * p["v"]
    return xyz[:, 1:]


def _gap(yz, box):
    (y0, z0), (y1, z1) = box
    dy = np.maximum(np.maximum(y0 - yz[:, 0], yz[:, 0] - y1), 0.0)
    dz = np.maximum(np.maximum(z0 - yz[:, 1], yz[:, 1] - z1), 0.0)
    return np.hypot(dy, dz)


@pytest.mark.parametrize("side", ["left side", "right side"])
def test_no_wood_free_to_cut_within_the_rim_of_the_stringer_s_mortise(sides, side):
    ctx, plist = sides
    p = plist[side]
    free = _cells_yz(ctx, p, p["free"])
    assert len(free), "the side has no wood free to cut at all"
    near = _gap(free, MORTISE)
    assert near.min() >= lighten.RIM_MM - ctx["spacing"], (side, near.min())


@pytest.mark.parametrize("zone", [CLEAT, GRIP], ids=["cleat inside", "grip outside"])
def test_a_piece_on_either_face_keeps_its_rim_too(sides, zone):
    ctx, plist = sides
    p = plist["left side"]
    assert _gap(_cells_yz(ctx, p, p["free"]), zone).min() >= lighten.RIM_MM - ctx["spacing"]


@pytest.mark.parametrize("side", ["left side", "right side"])
def test_the_holes_cut_stay_a_rim_away_from_every_joint(sides, side):
    """Asked to take out everything it can, the holes it cuts keep 1.5 in of wood round the mortise (and the cleat)."""
    from shapely.geometry import Polygon

    ctx, plist = sides
    p = plist[side]
    holes, covered = lighten.clean(p, p["free"].copy(), ctx["spacing"])
    assert holes, "nothing was cut: the test shows nothing"

    def uv_box(box):
        (y0, z0), (y1, z1) = box
        corners = np.array([[p["o"][0], y, z] for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1))])
        rel = corners - p["o"]
        return Polygon(np.stack([rel @ p["u"], rel @ p["v"]], axis=1))
    for box in (MORTISE,) + ((CLEAT,) if side == "left side" else ()):
        zone = uv_box(box)
        assert min(h.distance(zone) for h in holes) >= lighten.RIM_MM - 0.5, (side, box)


def test_the_holes_never_reach_a_joint_even_from_wood_marked_free(sides):
    """The rim is kept twice, as for the outline: the cells free to cut, and the room the cleaned holes are clipped to. Hand
    clean() every cell of the side as free: its holes still keep 1.5 in off the mortise."""
    from shapely.geometry import Polygon

    ctx, plist = sides
    p = plist["left side"]
    holes, _ = lighten.clean({**p, "free": p["inside"].copy()}, p["inside"].copy(), ctx["spacing"])
    (y0, z0), (y1, z1) = MORTISE
    rel = np.array([[p["o"][0], y, z] for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1))]) - p["o"]
    zone = Polygon(np.stack([rel @ p["u"], rel @ p["v"]], axis=1))
    assert holes and min(h.distance(zone) for h in holes) >= lighten.RIM_MM - 0.5


# --- 3. a holed wall's buckling: at its narrowest strip, the safe side ----------------------------------------------------
def _wall():
    """A 12 in wide, 18 in tall wall in the stool's x = 0 plane, as a panel and as its buckling row, carrying 1,112 N."""
    from caliper import buckling as B

    w, h, t, E = 304.8, 457.2, 19.05, 800.0
    p = {"name": "left side", "o": np.zeros(3), "u": np.array([0.0, 1.0, 0.0]), "v": np.array([0.0, 0.0, 1.0]),
         "flat": np.array([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])}
    sigma = B.critical_stress(E, t, h, w, 0)
    row = {"piece": "left side", "done": True, "down": True, "load_n": 1112.0, "edges_held": 0, "k": 0.0, "E_mpa": E,
           "height_mm": h, "width_mm": w, "thickness_mm": t, "sigma_cr_mpa": sigma, "p_cr_n": sigma * w * t,
           "safety": sigma * w * t / 1112.0}
    load = {"name": "standing", "force": np.array([0.0, 0.0, -1112.0]), "factor": 1.0}
    return p, row, load


def _case(row, safety=None):
    return {"name": "standing", "safety": safety if safety is not None else 9.0, "governs": "fea", "buckling": [row],
            "fea": {"safety": 9.0}, "lb": 125, "factor": 2.0, "holds": True}


def test_a_holed_wall_is_checked_at_its_narrowest_strip():
    from shapely.geometry import box

    p, row, load = _wall()
    holes = [box(50.8, 101.6, 152.4, 355.6), box(190.5, 152.4, 254.0, 304.8)]   # 4 in and 2.5 in across, overlapping in height
    got = lighten.holed_buckling(_case(row), [p], {"left side": holes}, load, 2.0)
    r = got["buckling"][0]
    assert r["narrowest_mm"] == pytest.approx(304.8 - 101.6 - 63.5, abs=0.5)        # the line through both holes
    assert r["safety"] == pytest.approx(lighten.V.cut(row["safety"] * r["narrowest_mm"] / 304.8), abs=0.01)
    assert r["holed"] is True and r["done"]
    assert got["governs"] == "buckling" and got["safety"] == r["safety"]       # lower than the FEA's 9: it governs


def test_a_wall_with_no_holes_this_step_is_as_it_was():
    p, row, load = _wall()
    got = lighten.holed_buckling(_case(row), [p], {"left side": []}, load, 2.0)
    assert got["buckling"][0] == row and got["governs"] == "fea"


def test_a_held_wall_with_holes_is_held_on_one_side_and_free_at_the_hole():
    """The foreman's call on #268, (a): where the solid wall had a held side, the strip beside the hole is held on that side and
    free at the hole, over the whole remaining width. With no held side, a column."""
    from shapely.geometry import box

    from caliper import buckling as B

    p, row, load = _wall()
    held = {**row, "edges_held": 2, "sigma_cr_mpa": B.critical_stress(800.0, 19.05, 457.2, 304.8, 2)}
    held["safety"] = held["sigma_cr_mpa"] * 304.8 * 19.05 / 1112.0
    got = lighten.holed_buckling(_case(held), [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]}, load, 2.0)
    r = got["buckling"][0]
    strip = B.critical_stress(800.0, 19.05, 457.2, 304.8 - 101.6, 1) * (304.8 - 101.6) * 19.05 / 1112.0
    assert r["safety"] == pytest.approx(lighten.V.cut(strip), abs=0.01) and r["edges_held"] == 1
    assert r["model"] == "the strip beside the hole, held on one side"
    free = lighten.holed_buckling(_case(row), [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]}, load, 2.0)["buckling"][0]
    assert free["edges_held"] == 0 and free["model"] == "a column of the strip beside the hole, its top free to sway"
    braced = lighten.holed_buckling(_case({**row, "braced_by": "step"}), [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]},
                                    load, 2.0)["buckling"][0]
    euler = B.critical_stress(800.0, 19.05, 457.2, 304.8 - 101.6, 0, braced=True) * (304.8 - 101.6) * 19.05 / 1112.0
    assert braced["model"] == "a column of the strip beside the hole, braced at its top"
    assert braced["safety"] == pytest.approx(lighten.V.cut(min(row["safety"], euler)), abs=0.01)
    assert braced["safety"] > free["safety"]


def test_the_box_stool_s_four_numbers_are_pinned():
    """The numbers the model was chosen on (the foreman's call on #268), so a later change to it is a visible change:
    test_lighten's box stool, its side wall with the first step's holes leaving a 125.4 mm strip of its 254. Chosen on 44.73
    solid, 16.26 used, and 1.53 and 90.38 the bounds not used, with each side wall taking the whole load; since #265 the two
    side walls under the top share it by the lever rule, half each, so each number is twice that."""
    from shapely.geometry import box

    from caliper import buckling as B

    from .test_load_study import BOX_STOOL

    import tempfile
    s = DesignStore.create("box", base=tempfile.mkdtemp())
    s.write_part("stool", BOX_STOOL, intent="a box step stool")
    ctx = L.prepare(s, "stool")
    load = ctx["loads"][0]
    (r,) = [x for x in B.check(ctx["pieces"], load, ctx.get("plate_mat") or ctx["mat"], ctx["tol"])
            if x["piece"] == "left" and x.get("done")]
    E, t, a, b, n = r["E_mpa"], r["thickness_mm"], r["height_mm"], r["width_mm"], r["load_n"]
    read = lambda held, w: B.critical_stress(E, t, a, w, held) * w * t / n          # noqa: E731
    assert r["share"] == 0.5 and r["edges_held"] == 2 and round(read(2, b), 2) == 89.47      # solid, as checked
    assert round(read(0, 125.4), 2) == 3.07 and round(read(2, 125.4), 2) == 180.78           # the bounds not used
    wall = {"name": "left", "o": np.zeros(3), "u": np.array([0.0, 1.0, 0.0]), "v": np.array([0.0, 0.0, 1.0]),
            "flat": np.array([[0.0, 0.0], [b, 0.0], [b, a], [0.0, a]])}
    hole = box((b - (b - 125.4)) / 2, 50.0, (b + (b - 125.4)) / 2, 150.0)
    got = lighten.holed_buckling(_case({**r, "safety": V_cut(r["safety"])}), [wall], {"left": [hole]}, load, 2.0)["buckling"][0]
    assert got["narrowest_mm"] == pytest.approx(125.4, abs=0.1) and got["safety"] == pytest.approx(32.53, abs=0.02)   # used


def V_cut(x):
    return lighten.V.cut(x)


def test_a_holed_wall_whose_strip_can_t_be_found_says_not_checked():
    from shapely.geometry import box

    p, row, load = _wall()
    sideways = {**load, "force": np.array([-1112.0, 0.0, 0.0])}               # square to the wall: no line across it
    got = lighten.holed_buckling(_case(row), [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]}, sideways, 2.0)
    r = got["buckling"][0]
    assert not r["done"] and r["why"].startswith("not checked: it has holes"), r


def test_the_run_says_each_step_checks_its_walls_buckling():
    import inspect

    src = inspect.getsource(lighten.study)
    assert "doesn't check buckling" not in src and "narrowest strip" in src


def test_what_governed_still_governs_where_it_s_lower():
    from shapely.geometry import box

    p, row, load = _wall()
    plate = {**_case(row, safety=0.5), "governs": "plate"}                    # the plate check at 0.5, under the holed wall's 0.99
    got = lighten.holed_buckling(plate, [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]}, load, 2.0)
    assert got["governs"] == "plate" and got["safety"] == 0.5 and not got["holds"]
    assert got["buckling"][0]["safety"] == pytest.approx(0.99, abs=0.01)
    # buckling governing already: the holed wall's lower number is the case's
    folded = {**_case(row, safety=row["safety"]), "governs": "buckling", "over": "fea"}
    got = lighten.holed_buckling(folded, [p], {"left side": [box(50.8, 101.6, 152.4, 355.6)]}, load, 2.0)
    assert got["governs"] == "buckling" and got["safety"] == got["buckling"][0]["safety"] < row["safety"]


def test_each_step_s_cases_go_through_the_holed_check(sides, monkeypatch, tmp_path):
    """Wired into the study: a step with holes in its walls has them checked (a real study of the synthetic stool, one step)."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    light = THROUGH.replace('"lb": 250', '"lb": 60')                        # light enough that a step holds and goes on
    assert light != THROUGH
    s.write_part("stool", light, intent="two sides, a step and a through-stringer")
    seen = []
    real = lighten.holed_buckling
    monkeypatch.setattr(lighten, "holed_buckling", lambda case, plist, holes, load, need: seen.append(
        {k: len(v) for k, v in holes.items() if v}) or real(case, plist, holes, load, need))
    lighten.study(s, "stool", steps=(0.3,))
    assert seen and any(h.get("left side") or h.get("right side") for h in seen), seen


# --- 2. a run on an older version stays findable, and a change under a running one is said --------------------------------
def _js(names, extra):
    from .test_carve_click import _page, _run

    stubs = ("const esc = (s) => String(s);\nlet S = {design: {parts: [{id: 'step_stool', name: 'Step stool', version: 4}]}};\n"
             "const lightenRuns = (pid) => (S.lightenRuns || []).filter((r) => r.part === pid);\n"
             "const lightenBlocked = (p) => (p.blocked && p.blocked.lighten) || '';\n"
             "const jobPart = (id) => 'Step stool';\n")
    return _run(stubs + _page(names, extra=extra).replace("let out;", "let out;", 1))


def test_a_part_that_turned_printed_keeps_its_lighten_run_on_show():
    """Theo's v4 put printed fillet strips in the stool: it read as printed, the page drew a printed part's carve panel, and
    the v3 Lighten run wasn't drawn anywhere."""
    out = _js(["lightenShown"], """
S.lightenRuns = [{part: 'step_stool', version: 3}];
out = [lightenShown({id: 'step_stool', printed: true}, []), lightenShown({id: 'step_stool', printed: false}, [{}]),
       lightenShown({id: 'other', printed: true}, [{}]), lightenShown({id: 'other', printed: false}, [])];""")
    assert out == [True, True, False, False]


def test_an_older_run_says_which_version_and_what_to_do():
    out = _js(["lightenChanged"], """
const run = {part: 'step_stool', version: 3};
out = [lightenChanged(run, {id: 'step_stool', version: 4}), lightenChanged(run, {id: 'step_stool', version: 3}),
       lightenChanged(run, {id: 'step_stool', version: 4, blocked: {lighten: 'it already fails'}})];""")
    assert out[0] == ("Lightened v3; you've changed it since (v4): Lighten it again, or look at v3's steps below (they can't be "
                      "cut into v4).")
    assert out[1] == "" and out[2].startswith("Lightened v3; you've changed it since (v4): it already fails, or look"), out


def test_a_running_lighten_says_when_its_part_changes_under_it():
    out = _js(["changedUnder"], """
out = [changedUnder({kind: 'lighten', part: 'step_stool', version: 3}), changedUnder({kind: 'lighten', part: 'step_stool', version: 4}),
       changedUnder({kind: 'load', part: 'step_stool', version: 3}), changedUnder({kind: 'release', part: 'step_stool', version: 3}),
       changedUnder({kind: 'lighten', part: 'step_stool'})];""")
    said = " ".join(out[0].split())
    assert "You've changed Step stool since this started (it was v3, it's v4 now): its steps will be of v3." in said, said
    assert "It's kept, under Make it lighter." in said
    assert out[1] == "" and "what it finds will be v3" in " ".join(out[2].split()) and out[3] == "" and out[4] == ""


def test_the_job_html_carries_the_change_and_the_record_carries_the_version():
    import inspect

    from caliper import design_api

    from .test_carve_click import _fn

    assert "${changedUnder(t)}" in _fn(open(lighten.__file__.replace("lighten.py", "web/static/design.js")).read(), "jobHtml")
    view = _fn(open(lighten.__file__.replace("lighten.py", "web/static/design.js")).read(), "loadView")
    assert "${lightenShown(p, runs) ? lightenView(p) : ''}" in view and ": (runs.length ? lightenView(p)" not in view
    src = inspect.getsource(design_api)
    assert src.count('"version": store.design.part(req.part).version}') == 2            # a load check's and a Lighten's
    assert '"version": j.meta.get("version")' in inspect.getsource(design_api._running)
