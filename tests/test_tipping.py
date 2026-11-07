"""CALI-98 (#86) — will it tip over? Statics about the footprint's edge, the bar stool and a narrow one by hand.

The pushes are EN 1022 / BIFMA X5.1's (600 N placed 60 mm in from the seat's edge, 20 N sideways at seat height), as
the engineering brief on #42 cites them. NEEDS ENGINEER CHECK: these tests check the arithmetic, not the standard."""

from types import SimpleNamespace

import numpy as np
import pytest
import trimesh

from caliper import construction as C
from caliper import tipping

IN = 25.4
OWN = 10 * tipping.LB                     # a 10 lb stool, in N


def _stool(base_in: float, seat_in: float, seat_d_in: float = 14.0):
    """Four 1 in legs at the corners of a square base, and a round seat on top: the bar stool's shape."""
    half, leg = base_in * IN / 2, IN
    legs = [trimesh.creation.box((leg, leg, seat_in * IN), trimesh.transformations.translation_matrix(
        (sx * (half - leg / 2), sy * (half - leg / 2), seat_in * IN / 2))) for sx in (-1, 1) for sy in (-1, 1)]
    seat = trimesh.creation.cylinder(seat_d_in * IN / 2, 25, transform=trimesh.transformations.translation_matrix(
        (0, 0, seat_in * IN + 12.5)))
    return trimesh.util.concatenate(legs + [seat])


def _front_edge_case(seat_in: float, seat_d_in: float = 14.0) -> dict:
    """EN 1022's front stability push as the guide declares it: 600 N down 60 mm in from the seat's front edge, 20 N
    forward at seat height (box centred at seat height)."""
    y, z = -(seat_d_in * IN / 2 - 60), seat_in * IN
    return {"name": "When someone sits on the front edge and leans", "tip": True, "force": (0, -20, -600),
            "factor": 1.0, "lo": (-10, y - 10, z - 1), "hi": (10, y + 10, z + 1)}


def _checked(monkeypatch, mesh, loads, own_lb=10.0):
    """tipping.check on a stubbed store: this mesh, these loads, a stool of ``own_lb`` with its weight at the middle."""
    monkeypatch.setattr(C, "declared", lambda store, pid: {"loads": loads})
    monkeypatch.setattr(C, "report", lambda store, pid: {"mass_kg": own_lb * tipping.LB / tipping.GRAVITY,
                                                         "cog": [0.0, 0.0, 400.0]})
    store = SimpleNamespace(part_geometry=lambda pid: SimpleNamespace(require_mesh=lambda: mesh))
    return tipping.check(store, "stool")


def test_the_bar_stool_by_hand():
    """18 in square base, seat 29 in up, 14 in across, 10 lb. Tipping forward about the front edge (y = -228.6):
    restoring = 10 lb x 228.6 + 600 N x (228.6 - 117.8) = 10,168.7 + 66,480 = 76,648.7 N·mm;
    overturning = 20 N x 736.6 = 14,732 N·mm; 5.2 times over; it goes over at 76,648.7 / 736.6 = 104 N (23 lb)."""
    half = 9 * IN
    square = np.array([(-half, -half), (half, -half), (half, half), (-half, half)])
    m = tipping.moments(square, [(OWN, (0, 0)), (600.0, (0, -117.8))], 20.0, (0, -1), 29 * IN)
    assert m["edge_mm"] == pytest.approx(228.6)
    assert m["restoring_nmm"] == pytest.approx(76648.7, abs=0.2)
    assert m["overturning_nmm"] == pytest.approx(14732.0, abs=0.1)
    assert m["safety"] == 5.2
    assert m["tips_at_n"] == pytest.approx(104.1, abs=0.1)


def test_a_narrow_stool_by_hand_tips_with_the_load_alone():
    """8 in base, seat 30 in up, the same 14 in seat: the front-edge load lands 16.2 mm outside the base's edge.
    restoring = 10 lb x 101.6 = 4,519.4; overturning = 600 x 16.2 + 20 x 762 = 9,720 + 15,240 = 24,960; 0.18."""
    half = 4 * IN
    square = np.array([(-half, -half), (half, -half), (half, half), (-half, half)])
    m = tipping.moments(square, [(OWN, (0, 0)), (600.0, (0, -117.8))], 20.0, (0, -1), 30 * IN)
    assert m["restoring_nmm"] == pytest.approx(4519.4, abs=0.2)
    assert m["overturning_nmm"] == pytest.approx(24960.0, abs=0.2)
    assert m["safety"] == 0.18
    assert m["tips_at_n"] == 0.0                       # no push needed: sitting on the edge tips it


def test_the_footprint_is_where_the_legs_meet_the_floor():
    poly = tipping.footprint(_stool(18, 29))
    assert poly.min(axis=0) == pytest.approx((-9 * IN, -9 * IN), abs=0.01)
    assert poly.max(axis=0) == pytest.approx((9 * IN, 9 * IN), abs=0.01)
    with pytest.raises(ValueError, match="no base to tip about"):
        tipping.footprint(trimesh.Trimesh([(0, 0, 0), (10, 0, 0), (5, 0, 10)], [(0, 1, 2)], process=False))


def test_a_declared_case_on_the_built_stool_holds_and_says_so(monkeypatch):
    (case,) = _checked(monkeypatch, _stool(18, 29), [_front_edge_case(29)])
    assert case["checked"] and case["safety"] == 5.2
    assert case["verdict"]["kind"] == "holds" and case["verdict"]["counts_as_pass"]     # one verdict (#132)
    assert case["tips_at_lb"] == 23
    assert tipping.line(case) == ("Won't tip when someone sits on the front edge and leans, 5.2 times over "
                                  f"({tipping.CAVEAT}).", "ok")                    # the caveat on the line (#141)


def test_the_narrow_stool_tips_and_says_it_needs_no_push(monkeypatch):
    (case,) = _checked(monkeypatch, _stool(8, 30), [_front_edge_case(30)])
    assert case["safety"] == 0.18 and case["verdict"]["kind"] == "fails"
    assert tipping.line(case) == ("Tips when someone sits on the front edge and leans: only 0.18 times over, and it "
                                  f"needs 1 ({tipping.CAVEAT}); the load alone tips it, before any push.", "bad")


def test_a_case_that_can_t_be_checked_is_waiting_never_a_pass(monkeypatch):
    monkeypatch.setattr(C, "report", lambda store, pid: {"mass_kg": None, "cog": None, "unweighed": "no material"})
    monkeypatch.setattr(C, "declared", lambda store, pid: {"loads": [_front_edge_case(29)]})
    mesh = _stool(18, 29)
    (case,) = tipping.check(SimpleNamespace(part_geometry=lambda pid: SimpleNamespace(require_mesh=lambda: mesh)),
                            "stool")
    assert not case["checked"] and not case["verdict"]["counts_as_pass"]
    text, status = tipping.line(case)
    assert text == "Tipping when someone sits on the front edge and leans: not checked: no material." \
        and status == "unknown"
    # and a tipping case with no sideways push isn't one
    down = {**_front_edge_case(29), "force": (0, 0, -600)}
    (case,) = _checked(monkeypatch, mesh, [down])
    assert not case["checked"] and "pushes sideways" in case["why"]


def test_a_seat_says_what_it_doesn_t_declare():
    sitting = {"name": "sitting", "lb": 250, "factor": 2.0, "lo": (0, 0, 0), "hi": (1, 1, 1)}
    assert tipping.unchecked({"loads": [sitting]}, "a bar stool") == [
        "leaning back (a sideways push at seat height)", "sitting on the front edge", "tipping over",
        "buckling of the legs"]
    every = [sitting, {"name": "sitting on the front edge", "force": (0, 0, -1300), "lo": (0, 0, 0), "hi": (1, 1, 1)},
             {"name": "leaning back", "force": (0, 400, -1000), "lo": (0, 0, 0), "hi": (1, 1, 1)},
             _front_edge_case(29)]
    assert tipping.unchecked({"loads": every}, "a bar stool") == ["buckling of the legs"]     # nothing checks it yet
    books = {**sitting, "name": "a row of books"}
    assert tipping.unchecked({"loads": [books]}, "a bookshelf") == []
    assert tipping.unchecked({"loads": [sitting]}, "a box") != []        # someone sits on it: it's a seat
    step = {**sitting, "name": "an adult stepping up"}
    assert tipping.unchecked({"loads": [step]}, "A one-platform step stool") == []          # stood on, not sat on


# --- the real part: the FEA leaves a tipping case out, and the card says it -------------------------------------

def _box_stool(cases: str) -> str:
    from .test_load_study import BOX_STOOL

    return BOX_STOOL.split("\ndef loads(")[0] + '''
def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    cx, cy, h = p["w"] / 2, p["d"] / 2, p["h"]
    sit = {"name": "sitting", "lb": 250, "factor": 2.0, "lo": (cx - 50, cy - 50, h - 2), "hi": (cx + 50, cy + 50, h)}
    tip = {"name": "when someone sits on the front edge and leans", "tip": True, "force": (0, -20, -600),
           "factor": 1.0, "lo": (cx - 10, 50, h - 2), "hi": (cx + 10, 70, h)}
    return ''' + cases + "\n"


def test_the_strength_check_leaves_a_tipping_case_out(tmp_path):
    pytest.importorskip("cadquery")
    from caliper import load_study
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", _box_stool("[tip]"), intent="a step stool to sit on")
    with pytest.raises(ValueError, match="'stool' only says how it might tip, not what it must hold"):
        load_study.prepare(store, "stool")


def test_the_card_says_whether_it_tips_and_where_the_pushes_come_from(tmp_path):
    pytest.importorskip("cadquery")
    from caliper import answers, design_api
    from caliper.design import DesignStore

    store = DesignStore.create("a stool to sit on", base=str(tmp_path / "designs"))
    store.write_part("stool", _box_stool("[sit, tip]"), intent="A box stool to sit on, from 3/4 in plywood.")
    work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
    lines = [ln for ln in work["lines"] if ln.get("study") == "tip"]
    texts = [ln["text"] for ln in lines]
    # about the front edge (y = 0): the load 60 mm in, its own weight at 127 mm in, against 20 N at 227.6 mm up
    rep = C.report(store, "stool")
    own = rep["mass_kg"] * tipping.GRAVITY
    want = round((600 * 60 + own * rep["cog"][1]) / (20 * 227.6), 2)
    assert texts[0] == (f"Won't tip when someone sits on the front edge and leans, {want:g} times over "
                        f"({tipping.CAVEAT}).")
    assert lines[0]["status"] == "ok" and "not yet checked by an engineer" in texts[0]
    # its base is wider side to side (16 in) than front to back (10 in): pushed forward, sideways isn't said
    assert texts[1] == ("Not checked yet for a seat: leaning back (a sideways push at seat height); sitting on the "
                        "front edge; buckling of the legs.") and lines[1]["status"] == "warn"
    assert len(texts) == 2


#: A bar stool as the guide says to write one (part_scripts.md, "The load cases, by kind of thing"): a 16 in plywood
#: seat 29 in up on four 2x2 legs, and the seat's four cases, the tipping one EN 1022's front stability push.
BAR_STOOL = '''import cadquery as cq

PARAMS = {"seat": 406.4, "height": 736.6}
BUILD = {"t": 19.05, "leg": 38.1}


def build(params):
    p = {**PARAMS, **(params or {})}
    s, h, t, leg = p["seat"], p["height"], BUILD["t"], BUILD["leg"]
    out = cq.Workplane().box(s, s, t).translate((0, 0, h - t / 2))
    for x in (-1, 1):
        for y in (-1, 1):
            c = (x * (s / 2 - leg / 2), y * (s / 2 - leg / 2), (h - t) / 2)
            out = out.union(cq.Workplane().box(leg, leg, h - t).translate(c))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    s, h, t, leg = p["seat"], p["height"], BUILD["t"], BUILD["leg"]
    r, at = s / 2, s / 2 - leg / 2
    out = [{"name": "seat", "kind": "sheet", "material": "plywood", "thickness": t,
            "outline": [(-r, -r, h), (r, -r, h), (r, r, h), (-r, r, h)]}]
    for i, (x, y) in enumerate([(-at, -at), (at, -at), (at, at), (-at, at)]):
        out.append({"name": f"leg {i + 1}", "kind": "stick", "material": "lumber", "size": "2x2",
                    "a": (x, y, 0), "b": (x, y, h - t)})
    return out


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    r, top = p["seat"] / 2, p["height"]
    return [{"name": "sitting", "lb": 250, "factor": 2.0, "lo": (-50, -50, top - 2), "hi": (50, 50, top)},
            {"name": "sitting on the front edge", "force": (0, 0, -1300), "factor": 1.0,
             "lo": (-50, -r + 50, top - 2), "hi": (50, -r + 150, top)},
            {"name": "leaning back", "force": (0, 400, -1000), "factor": 1.0,
             "lo": (-50, -50, top - 2), "hi": (50, 50, top)},
            {"name": "when someone sits on the front edge and leans", "tip": True, "force": (0, -20, -600),
             "factor": 1.0, "lo": (-10, -r + 50, top - 2), "hi": (10, -r + 70, top)}]
'''


def test_a_bar_stool_written_to_the_guide_declares_the_seat_cases(tmp_path):
    """#86's accept: the designer stubbed with a script that follows the guide. Its four cases are declared, the
    card checks the tipping one, and what's left unchecked is only what nothing checks yet (buckling)."""
    pytest.importorskip("cadquery")
    from caliper import answers, chat, design_api
    from caliper.design import DesignStore

    store = DesignStore.create("a bar stool, 29 in tall", base=str(tmp_path / "designs"))
    res = chat.author_part(store, "stool", "A bar stool, 29 in tall, to sit on.",
                           author=lambda spec, fb, prior: BAR_STOOL, max_rounds=1, promote_feedback=False)
    assert res.version, res.error
    names = [ld["name"] for ld in C.declared(store, "stool")["loads"]]
    assert names == ["sitting", "sitting on the front edge", "leaning back",
                     "when someone sits on the front edge and leans"]
    work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
    tip = [ln for ln in work["lines"] if ln.get("study") == "tip"]
    # by hand about the front edge (y = -203.2): the push 60 mm in, its own weight at the middle, 20 N at 735.6 mm
    rep = C.report(store, "stool")
    want = round((600 * 60 + rep["mass_kg"] * tipping.GRAVITY * (203.2 + rep["cog"][1])) / (20 * 735.6), 2)
    assert 2 < want < 4
    # a square base pushed only forward: sideways is said, not passed over (#141 review)
    assert [ln["text"] for ln in tip] == [
        f"Won't tip when someone sits on the front edge and leans, {want:g} times over ({tipping.CAVEAT}).",
        "Not checked yet: tipping sideways (no push is declared that way, and its base is no wider that way).",
        "Not checked yet for a seat: buckling of the legs."]



# --- #141 review: the two survivors -------------------------------------------------------------------------------------

def test_point_eight_against_a_factor_of_one_tips():
    from caliper import verdicts

    case = {"name": "A push", "factor": 1.0, "safety": 0.8, "checked": True, "tips_at_lb": 12,
            "verdict": verdicts.meets(0.8, 1.0)}
    text, status = tipping.line(case)
    assert text.startswith("Tips a push: only 0.8 times over, and it needs 1") and status == "bad"
    assert tipping.line({**case, "safety": 1.0, "verdict": verdicts.meets(1.0, 1.0)})[0].startswith("Won't tip")


def test_a_stool_raised_50_mm_gives_the_same_answer(monkeypatch):
    """The floor is where the part stands, not z 0: the same stool, its loads with it, 50 mm up, tips the same."""
    case = _front_edge_case(29)
    (flat,) = _checked(monkeypatch, _stool(18, 29), [case])
    raised_mesh = _stool(18, 29)
    raised_mesh.apply_translation((0, 0, 50))
    up = {**case, "lo": tuple(v + (50 if i == 2 else 0) for i, v in enumerate(case["lo"])),
          "hi": tuple(v + (50 if i == 2 else 0) for i, v in enumerate(case["hi"]))}
    (raised,) = _checked(monkeypatch, raised_mesh, [up])
    assert raised["safety"] == flat["safety"] == 5.2 and raised["tips_at_lb"] == flat["tips_at_lb"]
