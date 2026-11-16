"""CALI-190 (#301), #222 slice B: a hand check of each joint. Its geometry first: whose edge meets whose face, which way
a force crosses it, and what mode that makes it.

Theo, 2026-11-14: "let's do the joints as the same safety factor that the rest of the stool is checked at (just for
simplicity)" and "I like the hand check of each joint. So, yes".
"""

import numpy as np
import pytest

from caliper import joint_check as JC
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

#: A step resting on two side panels, with a rail under its front and back edges between the sides and a stringer
#: between the sides at the floor: step-stool-5 v7's arrangement, drawn here (never Theo's script in a test).
STEP_ON_SIDES = '''import cadquery as cq

PARAMS = {"w": 406.4, "d": 355.6, "h": 406.4, "rail": 152.4}
BUILD = {"t": 19.05}


def _boxes(p, t):
    w, d, h, r = p["w"], p["d"], p["h"], p["rail"]
    return {"left side": ((0, 0, 0), (t, d, h - t)), "right side": ((w - t, 0, 0), (w, d, h - t)),
            "step": ((0, 0, h - t), (w, d, h)),
            "front rail": ((t, 0, h - t - r), (w - t, t, h - t)), "back rail": ((t, d - t, h - t - r), (w - t, d, h - t)),
            "stringer": ((t, d / 2 - t / 2, 0), (w - t, d / 2 + t / 2, r))}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p, BUILD["t"]).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, r = BUILD["t"], p["w"], p["d"], p["h"], p["rail"]
    face = {"left side": [(0, 0, 0), (0, d, 0), (0, d, h - t), (0, 0, h - t)],
            "right side": [(w, 0, 0), (w, d, 0), (w, d, h - t), (w, 0, h - t)],
            "step": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)],
            "front rail": [(t, 0, h - t - r), (w - t, 0, h - t - r), (w - t, 0, h - t), (t, 0, h - t)],
            "back rail": [(t, d, h - t - r), (w - t, d, h - t - r), (w - t, d, h - t), (t, d, h - t)],
            "stringer": [(t, d / 2 - t / 2, 0), (w - t, d / 2 - t / 2, 0), (w - t, d / 2 - t / 2, r), (t, d / 2 - t / 2, r)]}
    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k, v in face.items()]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, h = p["w"], p["h"]
    return [{"name": "stepping on the front edge", "lb": 250, "factor": 2.0,
             "lo": (w / 2 - 50, 0, h - 2), "hi": (w / 2 + 50, 100, h)}]
'''


def _store(tmp_path, script, pid):
    store = DesignStore.create(f"a {pid}", base=str(tmp_path / "designs"))
    store.write_part(pid, script, intent=f"a {pid}")
    return store


def _by_pair(found):
    return {tuple(sorted((j["edge"], j["face"]))): j for j in found}


@pytest.fixture(scope="module")
def box(tmp_path_factory):
    store = _store(tmp_path_factory.mktemp("box"), BOX_STOOL, "stool")
    return store, JC.interfaces(store, "stool")


@pytest.fixture(scope="module")
def sides(tmp_path_factory):
    store = _store(tmp_path_factory.mktemp("sides"), STEP_ON_SIDES, "stool")
    return store, JC.interfaces(store, "stool")


def test_the_box_stool_s_top_sits_between_its_walls(box):
    """#222's "never holds" case: the top between the walls, its edges against their faces."""
    _, found = box
    got = _by_pair(found)
    for wall, out in (("left", (-1, 0, 0)), ("right", (1, 0, 0)), ("front", (0, -1, 0)), ("back", (0, 1, 0))):
        j = got[tuple(sorted(("top", wall)))]
        assert (j["edge"], j["face"]) == ("top", wall), j                              # the top's edge on the wall's face
        assert np.allclose(j["out"], out, atol=1e-6), j["out"]                          # from the top into the wall
        assert j["area_mm2"] == pytest.approx(j["length_mm"] * 19.05, rel=1e-6)
    assert got[("front", "left")]["edge"] == "front" and got[("front", "left")]["face"] == "left"


def test_the_step_rests_on_its_sides_and_rails_and_the_rails_hang_from_the_sides(sides):
    _, found = sides
    got = _by_pair(found)
    for side in ("left side", "right side"):
        j = got[tuple(sorted(("step", side)))]
        assert (j["edge"], j["face"]) == (side, "step"), j                             # the side's top edge under the step
        assert np.allclose(j["out"], (0, 0, 1), atol=1e-6)                             # from the side up into the step
        assert j["length_mm"] == pytest.approx(355.6, abs=1.0)
    for rail in ("front rail", "back rail"):
        assert (got[tuple(sorted(("step", rail)))]["edge"], got[tuple(sorted(("step", rail)))]["face"]) == (rail, "step")
        end = got[tuple(sorted((rail, "left side")))]
        assert (end["edge"], end["face"]) == (rail, "left side") and np.allclose(end["out"], (-1, 0, 0), atol=1e-6)
    assert len(found) == 10                                  # 2 step-side, 2 step-rail, 4 rail ends, 2 stringer ends


@pytest.mark.parametrize("force,loaded,mode", [
    ((0, 0, -1000), "step", "bearing"),                     # the step pressed down onto the side's top edge
    ((0, 0, 1000), "step", "withdrawal"),                   # lifted off it: pulled out of the side's edge
    ((0, 1000, 0), "step", "shear"),                        # slid along it
])
def test_a_force_across_an_edge_on_a_face_has_a_mode(sides, force, loaded, mode):
    _, found = sides
    j = _by_pair(found)[("left side", "step")]
    parts = JC.split(j, np.array(force, float), loaded)
    assert max(parts, key=parts.get) == mode, parts
    assert sum(v for v in parts.values()) == pytest.approx(1000.0)


def test_the_box_top_s_load_crosses_its_wall_joints_in_shear(box):
    _, found = box
    j = _by_pair(found)[("left", "top")]
    parts = JC.split(j, np.array((0, 0, -1000.0)), "top")
    assert parts["shear"] == pytest.approx(1000.0) and parts["bearing"] == 0 and parts["withdrawal"] == 0


# --- the statics -------------------------------------------------------------------------------------------------------
def _pieces(store):
    from caliper import construction as C
    from caliper import fasteners
    from caliper.consistency import _sides, shapes, tolerance

    mesh = store.part_geometry("stool").require_mesh()
    pieces = shapes(C.declared(store, "stool"))
    _sides(mesh, [pc for pc in pieces if pc["kind"] == "sheet"])
    fasteners.keys(pieces)
    return pieces, tolerance(mesh), [{"name": "the floor", "lo": mesh.bounds[0] - [1, 1, 1], "hi": [*mesh.bounds[1][:2] + 1, mesh.bounds[0][2] + 0.5]}]


def _load(store):
    from caliper import construction as C
    from caliper import load_study

    return load_study.parse_loads(C.declared(store, "stool")["loads"])[0]


def test_the_box_top_s_load_goes_a_quarter_to_each_wall_in_shear(box):
    store, found = box
    pieces, tol, held = _pieces(store)
    load = _load(store)
    got = JC.demands(found, pieces, load, held, tol)
    total = np.asarray(load["force"]) * load["factor"]
    assert set(got) == {tuple(sorted(("top", w))) for w in ("left", "right", "front", "back")}
    for key, d in got.items():
        assert d["from"] == "top" and np.allclose(d["force"], total / 4, rtol=1e-6), (key, d)   # centred: a quarter each


def test_the_step_s_load_goes_half_to_the_sides_and_half_through_the_rails(sides):
    store, found = sides
    pieces, tol, held = _pieces(store)
    load = _load(store)
    total = np.asarray(load["force"]) * load["factor"]
    got = JC.demands(found, pieces, load, held, tol, share="pairs")
    left, right = got[("left side", "step")], got[("right side", "step")]
    assert np.allclose(left["force"], total / 4, rtol=1e-6) and np.allclose(right["force"], total / 4, rtol=1e-6)
    front, back = got[("front rail", "step")]["force"], got[("back rail", "step")]["force"]
    assert np.allclose(front + back, total / 2, rtol=1e-6) and np.linalg.norm(front) > 5 * np.linalg.norm(back)
    ends = got[("front rail", "left side")], got[("front rail", "right side")]
    assert all(e["from"] == "front rail" for e in ends) and np.allclose(ends[0]["force"] + ends[1]["force"], front)
    assert ("left side", "stringer") not in got                                        # nothing reaches it


def test_with_the_ground_first_the_rails_carry_none_of_it(sides):
    store, found = sides
    pieces, tol, held = _pieces(store)
    load = _load(store)
    total = np.asarray(load["force"]) * load["factor"]
    got = JC.demands(found, pieces, load, held, tol, share="ground")
    assert set(got) == {("left side", "step"), ("right side", "step")}
    assert np.allclose(got[("left side", "step")]["force"] + got[("right side", "step")]["force"], total)


def test_a_load_with_nowhere_to_go_isn_t_a_simple_chain(sides):
    store, found = sides
    pieces, tol, _ = _pieces(store)
    with pytest.raises(JC.NotChain, match="isn't a simple chain"):
        JC.demands(found, pieces, _load(store), [{"name": "a hook", "lo": [-500, -500, 5000], "hi": [-400, -400, 5001]}], tol)


# --- the screw the list buys, and the credit it earns (#301 decision 1) -----------------------------------------------------
@pytest.mark.parametrize("t_in,length_in", [(0.75, 2.0), (0.5, 1.75), (0.25, 1.5)])
def test_an_edge_joint_s_screw_goes_an_inch_and_a_quarter_into_the_edge(t_in, length_in):
    """#8 × 2 in through 3/4 in plywood: 1 1/4 in of thread in the edge, past the 1 in APA E830 tested (#301)."""
    from caliper import fasteners

    pieces = [{"kind": "sheet", "material": "plywood", "thickness": t_in * 25.4}]
    assert fasteners.screw_length_mm(pieces) == pytest.approx(length_in * 25.4)


def test_the_check_credits_only_the_screw_bought_by_the_thread_in_the_edge():
    j = {"edge": "top", "face": "left", "fix": ["glue", "screws"], "screws": 2, "area_mm2": 216 * 19.05, "face_t": 19.05}
    short, bought = JC.capacity(j, 31.75), JC.capacity(j, 50.8)                       # 1 1/4 in, 2 in
    assert short["shear"] / JC.LBF == pytest.approx(2 * 90.0) and bought["shear"] / JC.LBF == pytest.approx(2 * 180.0)
    assert JC.capacity(j, 76.2)["shear"] == bought["shear"]                          # never past what E830 tested
    assert bought["withdrawal"] == 0.0                                               # pulled out of an edge: no credit
    assert JC.capacity({**j, "fix": ["glue"]}, 50.8)["shear"] == 0.0                 # glue alone on an edge: none


# --- in the strength check: it governs where it's lowest, and every reader says so (#301) -----------------------------------
#: The step lifted off its sides: pulled out of their edges.
LIFTED = STEP_ON_SIDES.replace('''    return [{"name": "stepping on the front edge", "lb": 250, "factor": 2.0,''',
                               '''    return [{"name": "lifted by its middle", "force": (0, 0, 2000), "factor": 2.0,''')


@pytest.fixture
def studied(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import load_study

    def run(script, min_safety=2.0, fine=False):
        if not fine:
            monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)                      # coarse: quick
        store = _store(tmp_path / f"s{len(list(tmp_path.iterdir()))}", script, "stool")
        return store, load_study.study(store, "stool", min_safety=min_safety)

    return run


@pytest.fixture
def short_screws(monkeypatch):
    """The list buying #8 × 1 1/4 in, as it did before #301: half an inch into an edge, 90 lb a screw in shear."""
    from caliper import fasteners

    monkeypatch.setattr(fasteners, "EDGE_THREAD_IN", 0.5)


def test_a_box_top_between_its_walls_fails_at_the_joint_and_names_it(studied, short_screws):
    from caliper import answers, load_study, verdicts

    store, rec = studied(BOX_STOOL)
    (c,) = rec["cases"]
    assert c["governs"] == "joint" and c["safety"] == pytest.approx(1.8, abs=0.02) and not c["holds"], c
    assert c["over"] in ("fea", "plate")                                             # what it took over from, kept
    assert load_study.judged_by(rec, c) == "joint"
    assert load_study.governing_words(c) in ("the joint between the top and the left", "the joint between the top and the right")
    assert c["joints"]["governing"]["said"] == "two #8 screws in shear into the top's edge"
    assert verdicts.case(rec, c)["kind"] == "fails"
    hedge = answers.fail_hedge(rec, c, verdicts.case(rec, c), True)
    assert "gives first: two #8 screws in shear into the top's edge, 0.9x of what it needs" in hedge, hedge


def test_the_need_is_the_run_s_least_safety_the_same_joint_flips_between(studied, short_screws):
    _, low = studied(BOX_STOOL, min_safety=1.3)
    _, high = studied(BOX_STOOL, min_safety=2.0)
    assert low["cases"][0]["governs"] == high["cases"][0]["governs"] == "joint"
    assert low["cases"][0]["holds"] and not high["cases"][0]["holds"]
    from caliper import load_study

    # a hand check that holds settles nothing the check it took over from couldn't (as buckling's, #229)
    assert load_study.judged_by(low, low["cases"][0]) == low["cases"][0]["over"] != "joint"
    assert load_study.judged_by(high, high["cases"][0]) == "joint"


def test_a_step_lifted_off_its_sides_is_pulled_out_of_their_edges_no_credit(studied):
    _, rec = studied(LIFTED)
    (c,) = rec["cases"]
    g = c["joints"]["governing"]
    assert c["governs"] == "joint" and c["safety"] == 0 and not c["holds"]
    assert g["mode"] == "withdrawal" and " #8 screws pulled out of the " in g["said"] and g["said"].endswith("'s edge"), g
    assert g["capacity_lb"] == {"withdrawal": 0.0}                                   # no credit (#301 decision 2)


def test_when_every_joint_is_checked_the_note_goes_and_one_it_can_t_keeps_it_named(studied):
    from caliper import verdicts

    _, rec = studied(BOX_STOOL)
    assert rec.get("joints_checked") and not rec.get("joints_unchecked")
    assert verdicts.wood_brace(rec) is None                                          # no "joints not checked" on it
    dado = BOX_STOOL + '\nJOINTS = [{"pieces": ["front", "left"], "kind": "dado", "fix": ["glue"]}]\n'
    _, said = studied(dado)
    assert said["joints_unchecked"] == ["the joint between the front and the left (a dado)"]
    assert not [r for r in said["cases"][0]["joints"]["rows"] if sorted(r["pieces"]) == ["front", "left"]]   # no number for it
    assert verdicts.brace_why(verdicts.wood_brace(said)) == "1 joint not checked by hand"   # the badge: short
    assert verdicts.wood_brace(said)["names"] == ["the joint between the front and the left (a dado)"]   # the line names it


def test_a_path_it_can_t_follow_keeps_the_note_and_never_a_tick_or_a_cross_from_it(studied, monkeypatch):
    def nowhere(*a, **k):
        raise JC.NotChain(JC.NOT_CHAIN)

    monkeypatch.setattr(JC, "demands", nowhere)
    _, rec = studied(BOX_STOOL)
    (c,) = rec["cases"]
    assert c["governs"] != "joint" and c["joints"]["chain"] is False
    assert rec["joints_unchained"] == [JC.NOT_CHAIN] and rec["joints_unchecked"] == []   # a reason, never a joint's name
    assert rec["wood_joints"] == 8                                                       # all its joints, unchecked


def test_a_lightening_step_s_judged_number_takes_the_joint_in():
    from caliper import lighten

    case = {"lb": 250, "factor": 2.0, "governs": "fea", "safety": 3.0,
            "joints": {"governing": {"safety": 1.6, "between": "the front rail and the left side"}}}
    got = lighten.judged(dict(case), 3.0, 2.0)
    assert got["governs"] == "joint" and got["safety"] == 1.6 and not got["holds"] and got["over"] == "fea-calibrated"


def test_the_card_says_the_wood_s_number_and_the_weakest_joint_s(studied):
    from caliper import answers

    _, rec = studied(BOX_STOOL, fine=True)                                          # settled: a pass to say
    (c,) = rec["cases"]
    assert c["governs"] != "joint"
    line = answers._case_line("stool", rec, c, None, False, True)["text"]
    assert "Its joints, by hand: the weakest, between the top and the left, " in line \
        or "Its joints, by hand: the weakest, between the top and the right, " in line, line
    assert "(two #8 screws in shear into the top's edge)" in line


def test_a_joint_it_couldn_t_check_is_named_where_the_card_says_so():
    from caliper import answers

    said = answers.joint_said({"wood": True, "joints_n": 1, "names": ["the joint between the front and the left (a dado)"]}, 2.0)
    assert said == "the joint between the front and the left (a dado) isn't checked by hand"


# --- the page ----------------------------------------------------------------------------------------------------------------
ROWS = {"chain": True, "unchecked": [],
        "governing": {"between": "the front rail and the left side", "mode": "shear", "safety": 1.64, "need": 2.0,
                      "said": "two #8 screws in shear into the front rail's edge", "demand_lb": {"shear": 110.0},
                      "capacity_lb": {"shear": 180.0}, "holds": False},
        "rows": [{"between": "the front rail and the left side", "mode": "shear", "safety": 1.64, "need": 2.0, "holds": False,
                  "said": "two #8 screws in shear into the front rail's edge", "demand_lb": {"shear": 110.0},
                  "capacity_lb": {"shear": 180.0}},
                 {"between": "the step and the left side", "mode": "bearing", "safety": 30.24, "need": 2.0, "holds": True,
                  "said": "the left side's edge bearing on the step", "demand_lb": {"bearing": 125.0},
                  "capacity_lb": {"bearing": 3780.0}},
                 {"between": "the left side and the stringer", "mode": None, "safety": None, "holds": True,
                  "said": "carries none of this load"}]}


def _page(extra):
    import json as _json
    import os

    from .test_carve_click import _page as page, _run

    return _run(page(["jointsTable", "jointsLine", "safetyNum"], consts=["esc", "sx", "verdictTone"],
                     extra=extra.replace("ROWS", _json.dumps(ROWS))))


def test_each_case_lists_its_joints_by_hand_the_governing_first():
    html = _page("out = jointsTable({joints: ROWS}, {min_safety: 2.0});").replace("&#39;", "'")
    assert "Joints, by hand" in html
    table = html[html.index("<table"):]
    assert table.index("the front rail and the left side") < table.index("the step and the left side") \
        < table.index("carries none of this load")                                 # the weakest first, unloaded last
    assert "two #8 screws in shear into the front rail's edge" in html and "1.6x" in html and "110 lb" in html
    assert "carries none of this load" in html
    assert _page("out = jointsTable({}, {min_safety: 2.0});") == ""


def test_a_joint_it_couldn_t_check_is_named_on_the_page():
    out = _page("""out = jointsLine({verdict: {joints: true, brace: {wood: true, joints_n: 1,
      names: ['the joint between the front and the left (a dado)']}}}, {min_safety: 2});""")
    assert "Joints not checked by hand:</b> the joint between the front and the left (a dado)" in out, out


def test_the_case_line_names_a_joint_that_governs():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "c.governs === 'joint' ? `the joint between ${esc(c.joints.governing.between)}: ${esc(c.joints.governing.said)}`" in src
    assert "${jointsTable(c, run)}" in src


def test_a_joint_loaded_two_ways_gives_by_the_weaker_of_them(sides):
    """Pressed down and pushed along at once: bearing it takes easily, the screws in shear give first."""
    store, _ = sides
    su = JC.setup(store, "stool")
    pieces, tol, held = _pieces(store)
    load = {**_load(store), "force": (0.0, 3000.0, -3000.0)}
    row = next(r for r in JC.check(su, load, held, 2.0)["rows"] if sorted(r["pieces"]) == ["left side", "step"])
    assert set(row["demand_lb"]) == {"bearing", "shear"}
    assert row["mode"] == "shear" and row["safety"] < row["capacity_lb"]["bearing"] / row["demand_lb"]["bearing"]


# --- #311 review --------------------------------------------------------------------------------------------------------
#: A step on splayed sides, 10° in toward the top, tied at the foot by a stringer between them.
SPLAYED = '''import math

import cadquery as cq

PARAMS = {"w": 406.4, "d": 300.0, "h": 400.0, "splay": 10.0, "z0": 30.0, "z1": 130.0}
BUILD = {"t": 19.05}
TIED = True


def _k(p):
    return math.tan(math.radians(p["splay"]))


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, k, z0, z1 = BUILD["t"], p["w"], p["d"], p["h"], _k(p), p["z0"], p["z1"]
    left = cq.Workplane("XZ").polyline([(0, 0), (t, 0), (t + h * k, h), (h * k, h)]).close().extrude(-d)
    right = cq.Workplane("XZ").polyline([(w, 0), (w - t, 0), (w - t - h * k, h), (w - h * k, h)]).close().extrude(-d)
    step = cq.Workplane().box(w - 2 * h * k, d, t, centered=False).translate((h * k, 0, h))
    out = left.union(right).union(step)
    if TIED:
        y0 = d / 2 - t / 2
        tie = cq.Workplane("XZ", origin=(0, y0, 0)).polyline(
            [(t + z0 * k, z0), (w - t - z0 * k, z0), (w - t - z1 * k, z1), (t + z1 * k, z1)]).close().extrude(-t)
        out = out.union(tie)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, k, z0, z1 = BUILD["t"], p["w"], p["d"], p["h"], _k(p), p["z0"], p["z1"]
    face = {"left side": [(0, 0, 0), (0, d, 0), (h * k, d, h), (h * k, 0, h)],
            "right side": [(w, 0, 0), (w, d, 0), (w - h * k, d, h), (w - h * k, 0, h)],
            "step": [(h * k, 0, h + t), (w - h * k, 0, h + t), (w - h * k, d, h + t), (h * k, d, h + t)]}
    if TIED:
        y0 = d / 2 - t / 2
        face["stringer"] = [(t + z0 * k, y0, z0), (w - t - z0 * k, y0, z0), (w - t - z1 * k, y0, z1), (t + z1 * k, y0, z1)]
    return [{"name": k_, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k_, v in face.items()]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h, t = p["w"], p["d"], p["h"], BUILD["t"]
    return [{"name": "standing on the step", "lb": 250, "factor": 2.0,
             "lo": (w / 2 - 50, d / 2 - 50, h + t - 2), "hi": (w / 2 + 50, d / 2 + 50, h + t)}]
'''
UNTIED = SPLAYED.replace("TIED = True", "TIED = False")

#: A shelf hung below a top from two hangers, screwed through the top and the shelf into the hangers' edges: a load on the
#: shelf pulls them out of their edges, and nothing bears it. A genuine withdrawal.
HUNG = '''import cadquery as cq

PARAMS = {"w": 406.4, "d": 300.0, "h": 400.0, "s": 200.0, "a": 60.0}
BUILD = {"t": 19.05}


def _boxes(p, t):
    w, d, h, s, a = p["w"], p["d"], p["h"], p["s"], p["a"]
    return {"left side": ((0, 0, 0), (t, d, h)), "right side": ((w - t, 0, 0), (w, d, h)),
            "top": ((0, 0, h), (w, d, h + t)),
            "front hanger": ((a, 60, s + t), (w - a, 60 + t, h)), "back hanger": ((a, d - 60 - t, s + t), (w - a, d - 60, h)),
            "shelf": ((a, 30, s), (w - a, d - 30, s + t))}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p, BUILD["t"]).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, s, a = BUILD["t"], p["w"], p["d"], p["h"], p["s"], p["a"]
    face = {"left side": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)],
            "right side": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)],
            "top": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)],
            "front hanger": [(a, 60, s + t), (w - a, 60, s + t), (w - a, 60, h), (a, 60, h)],
            "back hanger": [(a, d - 60, s + t), (w - a, d - 60, s + t), (w - a, d - 60, h), (a, d - 60, h)],
            "shelf": [(a, 30, s), (w - a, 30, s), (w - a, d - 30, s), (a, d - 30, s)]}
    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k, v in face.items()]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, s, t = p["w"], p["d"], p["s"], BUILD["t"]
    return [{"name": "a box of books on the shelf", "lb": 40, "factor": 2.0,
             "lo": (w / 2 - 50, d / 2 - 50, s + t - 2), "hi": (w / 2 + 50, d / 2 + 50, s + t)}]
'''


def _check(script, force=None, share=JC.SHARE, tmp=None):
    import tempfile

    store = _store(__import__("pathlib").Path(tmp or tempfile.mkdtemp()), script, "stool")
    pieces, tol, held = _pieces(store)
    load = _load(store)
    if force is not None:
        load = {**load, "force": tuple(force)}
    return JC.check(JC.setup(store, "stool"), load, held, 2.0, share)


def test_a_push_along_a_member_bears_where_it_pushes_never_pulls_the_other_end(sides):
    """#311 review item 1: 1% sideways read 0.0x, the rail's far end pulled out of its edge. It bears on the side it pushes."""
    store, _ = sides
    down = _check(STEP_ON_SIDES)
    f = np.asarray(_load(store)["force"], float)
    for share in (0.01, 0.10):
        tilted = _check(STEP_ON_SIDES, force=f + np.array([share * abs(f[2]), 0.0, 0.0]))
        assert tilted["governing"]["safety"] == pytest.approx(down["governing"]["safety"], rel=0.12), (share, tilted["governing"])
        assert all(r["mode"] != "withdrawal" for r in tilted["rows"]), [r for r in tilted["rows"] if r["mode"] == "withdrawal"]
    along = _check(STEP_ON_SIDES, force=f + np.array([0.10 * abs(f[2]), 0.0, 0.0]))
    rail_end = next(r for r in along["rows"] if sorted(r["pieces"]) == ["front rail", "right side"])
    assert "bearing" in rail_end["demand_lb"]                                          # the rail bears on the side it pushes


def test_a_shelf_hung_from_screws_in_edges_still_reads_a_cross():
    got = _check(HUNG)
    g = got["governing"]
    assert g["mode"] == "withdrawal" and g["safety"] == 0 and not g["holds"] and "pulled out of the" in g["said"], g


def test_a_splayed_side_s_foot_thrust_goes_into_its_tie():
    """#311 review item 2: load × tan(splay) at each foot, carried by the tie's joints."""
    got = _check(SPLAYED)
    ties = [r for r in got["rows"] if "stringer" in r["pieces"]]
    assert len(ties) == 2 and all(r["mode"] is not None for r in ties), ties          # never "carries none"
    load_lb = 250 * 2.0
    thrust = load_lb / 2 * np.tan(np.radians(10.0))                                   # about 44 lb a foot
    for r in ties:
        assert np.hypot(*r["demand_lb"].values()) == pytest.approx(thrust, rel=0.05), r    # its parts across the slant
        assert r["mode"] == "withdrawal" and r["safety"] == 0                         # a butt tie, pulled from its edge
    top = next(r for r in got["rows"] if sorted(r["pieces"]) == ["left side", "step"])
    # down the side's line, read against the step's face it bears on (#311 re-check B): 250 lb into it, 44 lb across it
    assert top["demand_lb"]["bearing"] == pytest.approx(load_lb / 2, rel=0.01)
    assert top["demand_lb"]["shear"] == pytest.approx(thrust, rel=0.05), top


def test_a_splayed_part_with_nothing_tying_its_feet_isn_t_checked_by_hand():
    got = _check(UNTIED)
    assert got["chain"] is False and got["unchecked"] == ["nothing ties its splayed sides"] and got["governing"] is None


@pytest.mark.parametrize("deg,lb", [(0.0, 180.0), (10.0, 180.0), (30.0, 135.0)])
def test_a_screw_into_a_bevel_is_credited_the_thread_that_stays_in_the_wood(deg, lb):
    """#311 review item 3: the 2 in screw comes out of a 30° bevel's edge piece after 3/4 in; the book says so too."""
    import math

    from caliper import marks

    sin = math.sin(math.radians(deg))
    j = {"edge": "rail", "face": "side", "fix": ["screws"], "screws": 1, "area_mm2": 1e4, "face_t": 19.05, "edge_t": 19.05,
         "sin": sin}
    assert JC.capacity(j, 50.8)["shear"] / JC.LBF == pytest.approx(lb, rel=0.01)
    assert marks.thread_in(19.05, 19.05, sin, 50.8) == pytest.approx(min(31.75, 9.525 / sin) if sin else 31.75)
    assert marks.comes_out(19.05, 19.05, sin, 50.8) == (deg == 30.0)                 # one rule for the book and the check


def test_holed_buckling_lets_a_joint_govern_when_its_walls_aren_t_checked(monkeypatch):
    """#311 review item 5: buckling governed, the holes leave no wall checked, and the joint is lower than what it took
    over from."""
    from caliper import lighten

    monkeypatch.setattr(lighten, "narrowest", lambda *a, **k: None)
    case = {"lb": 250, "factor": 2.0, "governs": "buckling", "over": "fea", "safety": 2.5,
            "fea": {"safety": 4.0}, "buckling": [{"piece": "left", "done": True, "safety": 2.5, "load_n": 1000.0}],
            "joints": {"governing": {"safety": 1.6, "between": "the front rail and the left side"}}}
    got = lighten.holed_buckling(case, [{"name": "left"}], {"left": [[[0, 0, 0]]]}, {"force": (0, 0, -1000)}, 2.0)
    assert got["governs"] == "joint" and got["safety"] == 1.6 and not got["holds"]


# --- #311 review item 4: the words, case by case ------------------------------------------------------------------------
def _brace_words(c, run=None):
    from caliper import answers, verdicts

    b = verdicts.wood_brace(run or {"wood_joints": 99}, c)
    return b, (verdicts.brace_why(b) if b else None), (answers.joint_said(b, 2.0) if b else None)


def test_a_case_whose_path_can_t_be_followed_counts_all_its_joints_and_says_why_once():
    c = {"joints": {"n": 8, "chain": False, "rows": [], "governing": None, "unchecked": [JC.NOT_CHAIN]}}
    b, badge, line = _brace_words(c)
    assert badge == "8 joints not checked by hand", badge
    assert line == "not checked by hand: its load path isn't a simple chain", line
    assert line.count("simple chain") == 1


def test_a_part_with_no_joint_it_can_place_keeps_today_s_words_exactly():
    c = {"joints": {"n": 8, "chain": True, "rows": [], "governing": None,
                    "unchecked": [f"the joint between the a{i} and the b{i} (a dado)" for i in range(8)]}}
    b, badge, line = _brace_words(c)
    assert badge == "joints not checked" and line == "the check takes its 8 joints as solid wood"


def test_the_badge_counts_what_that_case_left_unchecked():
    c = {"joints": {"n": 10, "chain": True, "rows": [{"safety": 3.3}], "governing": {"safety": 3.3},
                    "unchecked": ["the joint between the stringer and the left side (a notch)"]}}
    b, badge, line = _brace_words(c, {"wood_joints": 2, "joints_unchecked": ["x", "y"]})
    assert badge == "1 joint not checked by hand"                                    # this case's, not the run's 2
    assert line == "the joint between the stringer and the left side (a notch) isn't checked by hand"
    assert _brace_words({"joints": {"n": 4, "chain": True, "rows": [{"safety": 3.0}], "unchecked": []}})[0] is None


def test_the_station_bar_names_a_joint_that_decides_it():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    i = src.index("    const decided = c.governs === 'joint'")
    assert "`the joint between ${esc(c.joints.governing.between)}: ${esc(c.joints.governing.said)}`" in src[i:i + 300]


def test_the_page_says_a_path_it_can_t_follow_once():
    out = _page("""out = jointsLine({verdict: {joints: true, brace: {wood: true, joints_n: 8,
      unchained: "its load path isn't a simple chain"}}}, {min_safety: 2});""")
    assert out.count("simple chain") == 1 and "Joints not checked by hand:</b> its load path isn't a simple chain." in out, out


RUN = {"id": "r1", "part": "stool", "version": 1, "min_safety": 2.0, "safety": 3.1, "spacing_mm": 2.0,
       "thinnest_mm": 19.05, "across": 9.5, "finer": True, "wood_joints": 3,
       "joints_unchecked": ["the joint between the a and the b (a dado)", "the joint between the c and the d (a dado)",
                            "the joint between the e and the f (a dado)"]}


def test_a_case_s_verdict_says_its_own_unchecked_joints_not_the_run_s():
    from caliper import verdicts

    c = {"name": "an adult", "lb": 200, "factor": 2.0, "safety": 3.1, "governs": "fea", "holds": True,
         "joints": {"n": 10, "chain": True, "rows": [{"safety": 4.0}], "governing": {"safety": 4.0},
                    "unchecked": ["the joint between the a and the b (a dado)"]}}
    assert verdicts.case(RUN, c)["why"] == "1 joint not checked by hand"
    clean = {**c, "joints": {**c["joints"], "unchecked": []}}
    assert not verdicts.case(RUN, clean).get("joints")                                # every joint of it checked: no cap


def test_a_lightening_step_reads_its_cases_joints():
    from caliper import verdicts

    st = {"index": 3, "safety": 3.0, "holds": True, "removed": 0.2, "saved_lb": 1.0, "verdict": None,
          "cases": [{"safety": 3.0, "joints": {"n": 10, "chain": True, "rows": [{"safety": 4.0}], "unchecked": []}}]}
    assert not verdicts.lighten_step(st, None, RUN).get("joints")                    # its cases checked every joint
    st["cases"][0]["joints"]["unchecked"] = ["the joint between the a and the b (a dado)"]
    assert verdicts.lighten_step(st, None, RUN)["why"] == "1 joint not checked by hand"


def test_a_push_away_from_one_joint_slides_on_another_before_it_pulls():
    """A piece sitting on A, its other side butted against B's face, pushed away from B: A takes it across (shear); B,
    which it would only pull away from, takes none of it."""
    A = {"pieces": ["A", "P"], "edge": "P", "face": "A", "out": np.array([0.0, 0.0, -1.0]), "mid": np.array([50.0, 0.0, 0.0])}
    B = {"pieces": ["B", "P"], "edge": "P", "face": "B", "out": np.array([-1.0, 0.0, 0.0]), "mid": np.array([-50.0, 0.0, 50.0])}
    got = dict((tuple(j["pieces"]), f) for j, f in JC._route([A, B], "P", np.array([10.0, 0.0, -100.0]),
                                                                np.array([0.0, 0.0, 10.0]), "pairs"))
    assert np.allclose(got[("A", "P")], (10.0, 0.0, -100.0)) and np.allclose(got[("B", "P")], 0.0), got


# --- #311 re-check -----------------------------------------------------------------------------------------------------------
#: The splayed stool at 20°, and with a rail between the sides partway up, beside its stringer (#311 re-check D).
STEEP = SPLAYED.replace('"splay": 10.0', '"splay": 20.0')
RAILED = SPLAYED.replace('''    if TIED:
        y0 = d / 2 - t / 2
        tie = cq.Workplane("XZ", origin=(0, y0, 0))''', '''    y1 = d / 2 - t / 2
    rail = cq.Workplane("XZ", origin=(0, y1, 0)).polyline(
        [(t + 250 * k, 250), (w - t - 250 * k, 250), (w - t - 320 * k, 320), (t + 320 * k, 320)]).close().extrude(-t)
    out = out.union(rail)
    if TIED:
        y0 = d / 2 - t / 2
        tie = cq.Workplane("XZ", origin=(0, y0, 0))''').replace('''    if TIED:
        y0 = d / 2 - t / 2
        face["stringer"]''', '''    y1 = d / 2 - t / 2
    face["rail"] = [(t + 250 * k, y1, 250), (w - t - 250 * k, y1, 250), (w - t - 320 * k, y1, 320), (t + 320 * k, y1, 320)]
    if TIED:
        y0 = d / 2 - t / 2
        face["stringer"]''')
#: Its stringer run through notches in the sides instead of butted between them (v7's, #311 re-check C).
NOTCHED = SPLAYED.replace('''        tie = cq.Workplane("XZ", origin=(0, y0, 0)).polyline(
            [(t + z0 * k, z0), (w - t - z0 * k, z0), (w - t - z1 * k, z1), (t + z1 * k, z1)]).close().extrude(-t)''',
                          '''        tie = cq.Workplane("XZ", origin=(0, y0, 0)).polyline(
            [(0, z0), (w, z0), (w, z1), (0, z1)]).close().extrude(-t)''').replace(
    '''        face["stringer"] = [(t + z0 * k, y0, z0), (w - t - z0 * k, y0, z0), (w - t - z1 * k, y0, z1), (t + z1 * k, y0, z1)]''',
    '''        face["stringer"] = [(0, y0, z0), (w, y0, z0), (w, y0, z1), (0, y0, z1)]''')


def _check_at(script, dx):
    """``_check`` with the load moved ``dx`` mm along x."""
    import tempfile
    from pathlib import Path

    store = _store(Path(tempfile.mkdtemp()), script, "stool")
    pieces, tol, held = _pieces(store)
    load = _load(store)
    load = {**load, "lo": tuple(np.add(load["lo"], (dx, 0, 0))), "hi": tuple(np.add(load["hi"], (dx, 0, 0)))}
    return JC.check(JC.setup(store, "stool"), load, held, 2.0)


def test_a_tie_carries_one_tension_its_ends_the_larger():
    """#311 re-check A: off centre, toward the right foot, its two ends read 9 and 93 lb; a tie's ends pull together."""
    got = _check_at(SPLAYED, 120.0)
    ends = [r for r in got["rows"] if "stringer" in r["pieces"]]
    pulls = [np.hypot(*r["demand_lb"].values()) for r in ends]
    assert len(ends) == 2 and pulls[0] == pytest.approx(pulls[1], rel=1e-3), pulls
    load_lb, k = 500.0, np.tan(np.radians(10.0))
    right = load_lb * (0.5 + 120.0 / (406.4 - 2 * 400 * k)) * k                        # the nearer foot's share, × tan
    assert max(pulls) == pytest.approx(right, rel=0.1)


def test_a_splayed_side_s_top_is_read_against_the_face_it_bears_on():
    """#311 re-check B: at 20°, down the side's line is 250 lb against the step's face and 91 lb across it, in the
    screws, not 266 lb all in bearing."""
    top = next(r for r in _check(STEEP)["rows"] if sorted(r["pieces"]) == ["left side", "step"])
    assert top["demand_lb"]["bearing"] == pytest.approx(250.0, rel=0.01)
    assert top["demand_lb"]["shear"] == pytest.approx(250.0 * np.tan(np.radians(20.0)), rel=0.02), top


def test_a_tie_it_can_t_place_is_named_never_read_as_no_tie():
    got = _check(NOTCHED)
    assert got["chain"] is False
    assert got["unchecked"] == ["its tie, the stringer, isn't checked by hand: its joints are notches (CALI-192)"], got


def test_the_tie_nearest_the_foot_takes_the_thrust():
    """#311 re-check D: a stringer at the foot and a rail partway up: the stringer takes it."""
    got = _check(RAILED)
    stringer = [r for r in got["rows"] if "stringer" in r["pieces"]]
    rail = [r for r in got["rows"] if "rail" in r["pieces"] and "step" not in r["pieces"]]
    assert len(stringer) == 2 and all(r["mode"] for r in stringer), stringer
    assert rail and all(r["mode"] is None for r in rail), rail                       # carries none of it


# --- #311: the lever rule past its supports, and three in a row -------------------------------------------------------------
@pytest.mark.parametrize("x,shares", [(50.0, [0.5, 0.5]), (95.0, [0.05, 0.95]), (100.0, [0.0, 1.0]),
                                      (101.0, [-0.01, 1.01]), (110.0, [-0.1, 1.1])])
def test_two_supports_share_a_load_by_statics_overhang_and_all(x, shares):
    """Past its supports, the near one carries more than all of it and the far one is lifted (#311: it read 0.5 / 0.5)."""
    got = JC._lever([np.array([0.0, 0.0, 0.0]), np.array([100.0, 0.0, 0.0])], np.array([x, 0.0, 0.0]), "pairs")
    assert got == pytest.approx(shares, abs=1e-9)


def test_three_supports_in_a_row_aren_t_checked_by_hand():
    mids = [np.array([0.0, 0.0, 0.0]), np.array([100.0, 0.0, 0.0]), np.array([200.0, 0.0, 0.0])]
    with pytest.raises(JC.NotChain) as e:
        JC._lever(mids, np.array([190.0, 0.0, 0.0]), "pairs")
    assert e.value.why == "it rests on three or more supports in a row"


def test_a_load_past_a_splayed_top_lifts_the_far_side():
    """The 20° stool loaded just past its right side's top: the right top bears more than the whole load; the left one is
    lifted, a pull out of its edge, never read as pressed (#311: both read 250 lb at 0.98 of the span)."""
    import tempfile
    from pathlib import Path

    store = _store(Path(tempfile.mkdtemp()), STEEP, "stool")
    su = JC.setup(store, "stool")
    right = next(j for j in su["joints"] if sorted(j["pieces"]) == ["right side", "step"])
    load = _load(store)
    centre = (np.asarray(load["lo"]) + np.asarray(load["hi"])) / 2.0
    got = _check_at(STEEP, float(right["mid"][0]) + 2.0 - float(centre[0]))
    rows = {tuple(sorted(r["pieces"])): r for r in got["rows"]}
    assert rows[("right side", "step")]["demand_lb"]["bearing"] > 500.0
    assert rows[("left side", "step")]["mode"] == "withdrawal" and "bearing" not in rows[("left side", "step")]["demand_lb"]
