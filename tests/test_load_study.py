"""CALI-54 (#1) — will it hold? A part's own loads(), through whittle's FEA and a plate check."""

import math

import pytest

from caliper import consistency, load_study, sandbox
from caliper.design import DesignStore

from .test_consistency import STOOL

pytest.importorskip("cadquery")

#: The test stool with what it must carry: one foot in the middle of the top, and a shove on the top's
#: front edge (side-on to every panel, so there's no plate check for it).
LOADS = '''

def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    h, d = p["height"], p["depth"]
    return [{"name": "an adult stepping up", "lb": 200, "factor": 2.0,
             "lo": (-50, -50, h - 2), "hi": (50, 50, h)},
            {"name": "a shove from the front", "force": (0, 300, 0),
             "lo": (-40, -d / 2 - 2, h - 15), "hi": (40, -d / 2, h - 4)}]
'''


def test_the_plate_formula_is_timoshenkos_for_a_square_plate():
    # a square plate simply supported all round, a load on a small spot at its middle:
    # w = 0.01160 P a² / D, D = E t³ / 12(1 - ν²)  ->  0.1267 P a² / (E t³)
    got = load_study.plate(500, 500, 10, 1000, 1.0, 8000)
    assert got["deflection_mm"] == pytest.approx(0.1267 * 1000 * 500 ** 2 / (8000 * 1000), rel=1e-3)
    # and for the stool's top, 14.5 x 8.5 in of 3/4 in ply under one foot of 400 lb, by hand
    top = load_study.plate(368.3, 215.9, 19.05, 2 * 200 * load_study.LB, 100 * 100, 8000)
    r0 = math.sqrt(100 * 100 / math.pi)
    beta = 0.875 + (0.927 - 0.875) * (368.3 / 215.9 - 1.6) / 0.2
    hand = 3 * 1779.3 / (2 * math.pi * 19.05 ** 2) * (1.3 * math.log(2 * 215.9 / (math.pi * r0)) + beta)
    assert top["stress_mpa"] == pytest.approx(hand, rel=1e-3)
    assert 4.7 < top["stress_mpa"] < 4.9


def test_loads_say_how_much_and_where():
    got = load_study.parse_loads([{"name": "me", "lb": 200, "factor": 2, "lo": (0, 0, 10), "hi": (5, 5, 8)}])
    assert got[0]["force"] == pytest.approx([0, 0, -200 * load_study.LB])
    assert got[0]["lo"] == [0, 0, 8] and got[0]["hi"] == [5, 5, 10]     # corners in either order
    with pytest.raises(ValueError, match="'me' says where but not how much"):
        load_study.parse_loads([{"name": "me", "lo": (0, 0, 0), "hi": (1, 1, 1)}])
    with pytest.raises(ValueError, match="needs 'hi'"):
        load_study.parse_loads([{"name": "me", "kg": 5, "lo": (0, 0, 0)}])


def test_a_load_in_thin_air_fails_the_round():
    ok = sandbox.run_script(STOOL + LOADS, timeout=120)
    got = {r.id: r for r in consistency.check(ok.declared, ok.geometry)}
    assert got["loads_land"].passed

    floating = LOADS.replace("(-50, -50, h - 2), \"hi\": (50, 50, h)", "(-50, -50, h + 40), \"hi\": (50, 50, h + 42)")
    run = sandbox.run_script(STOOL + floating, timeout=120)
    got = {r.id: r for r in consistency.check(run.declared, run.geometry)}
    assert not got["loads_land"].passed
    assert "'an adult stepping up' acts on" in got["loads_land"].detail and "40 mm from the part" in got["loads_land"].detail


def test_the_stool_holds_and_says_which_check_governs(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: the numbers here are the plate's
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", STOOL + LOADS, intent="a step stool")
    events = []
    rec = load_study.study(store, "stool", emit=lambda k, t="", **d: events.append(k))
    step, shove = rec["cases"]
    # the top is 14 x 10 in and rests on its two sides (an inch in from its ends), not all round: a beam
    # across them (CALI-82), the safe side, and plywood across its grain. 3/4 in over 14 in under 400 lb isn't
    # 2 times over that way, and it says which way to cut it to get there.
    pl = step["plate"]
    assert pl["piece"] == "top" and pl["done"] and pl["as"] == "beam" and pl["edges_held"] == 2
    assert pl["span_mm"] == pytest.approx(355.6, abs=1)
    assert "face grain running across the gap" in pl["why"]
    assert step["governs"] == "plate" and step["safety"] == pl["safety_across"] < step["fea"]["safety"]
    assert not step["holds"] and pl["safety"] > 2               # grain along the span: it would
    assert shove["plate"] is None                                 # pushed side-on: no plate it lands face-on
    assert shove["fea"]["supported"] and shove["holds"]
    assert rec["material"]["key"] == "plywood" and rec["version"] == 1
    assert events[-1] == "done"
    assert (tmp_path / "designs").exists() and load_study.list_runs(store, "stool")[0]["id"] == rec["id"]
    assert store.history("stool")[-1]["kind"] == "load"
    with open(load_study.heat_path(store, rec["id"], 0)) as f:
        assert '"heat"' in f.read()


def test_a_panel_held_all_round_gets_the_plate_check(tmp_path, monkeypatch):
    """A box stool (the live one's shape): the top sits between four walls, so the plate check runs and,
    with the grain the wrong way, governs."""
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    rec = load_study.study(store, "stool")
    (case,) = rec["cases"]
    pl = case["plate"]
    assert pl["done"] and pl["edges_held"] == 4 and pl["piece"] == "top"
    assert pl["safety_across"] == pytest.approx(pl["safety"] / 2, rel=0.01)
    assert case["governs"] == "plate" and case["safety"] == pl["safety_across"]
    assert case["breaks_lb"] == pytest.approx(200 * 2 * case["safety"], abs=10)
    labels = [b["label"] for b in pl["by_thickness"]]
    assert "1/2 in" in labels and "3/4 in" in labels
    assert next(b for b in pl["by_thickness"] if b["label"] == "1/2 in")["safety_across"] < pl["safety_across"]


def test_no_loads_means_no_study(tmp_path):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", STOOL, intent="a step stool")
    with pytest.raises(ValueError, match="has no loads()"):
        load_study.study(store, "stool")


#: Five panels: four walls, and a top between them (as the live stool was drawn by the designer).
BOX_STOOL = '''import cadquery as cq

PARAMS = {"w": 406.4, "d": 254.0, "h": 228.6}
BUILD = {"t": 19.05}


def _boxes(p, t):
    w, d, h = p["w"], p["d"], p["h"]
    return {"left": ((0, 0, 0), (t, d, h)), "right": ((w - t, 0, 0), (w, d, h)),
            "front": ((t, 0, 0), (w - t, t, h)), "back": ((t, d - t, 0), (w - t, d, h)),
            "top": ((t, t, h - t), (w - t, d - t, h))}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p, BUILD["t"]).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = BUILD["t"], p["w"], p["d"], p["h"]
    face = {"left": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)],
            "right": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)],
            "front": [(t, 0, 0), (w - t, 0, 0), (w - t, 0, h), (t, 0, h)],
            "back": [(t, d, 0), (w - t, d, 0), (w - t, d, h), (t, d, h)],
            "top": [(t, t, h), (w - t, t, h), (w - t, d - t, h), (t, d - t, h)]}
    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k, v in face.items()]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    cx, cy, h = p["w"] / 2, p["d"] / 2, p["h"]
    return [{"name": "an adult stepping up", "lb": 200, "factor": 2.0,
             "lo": (cx - 50, cy - 50, h - 2), "hi": (cx + 50, cy + 50, h)}]
'''
