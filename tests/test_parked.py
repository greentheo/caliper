"""CALI-53 — parked on jacks with someone inside, and the floor under a knee."""

import pytest

from caliper import parked as P
from caliper.design import DesignStore

pytest.importorskip("whittle")


def test_a_knee_on_a_floor_strip_bends_it_like_the_handbook_says():
    span, t, load, patch = 500.0, 9.525, 667.0, 76.2
    out = P.floor_knee("plywood", t, span, load, patch)
    m = load * (span / 4 - patch / 8)
    b = patch + span / 2
    assert out["stress_mpa"] == pytest.approx(6 * m / (b * t * t), abs=0.01)
    spread = P.floor_knee("plywood", t, span, load, 254.0)        # on a mattress: spread wider, gentler
    assert spread["safety"] > out["safety"] and spread["sag_mm"] < out["sag_mm"]


FRAME = '''PARAMS = {"w": 50.8}


def members(params):
    t = {"outer": 50.8, "wall": 3.175, "group": "rail"}
    return [{"name": "shank", "a": (150, 0, 0), "b": (0, 0, 0), **t},
            {"name": "rail", "a": (0, 0, 0), "b": (-1000, 0, 0), **t, "carries": True},
            {"name": "cross_l", "a": (-1000, 0, 0), "b": (-1000, 400, 0), **t, "carries": True},
            {"name": "cross_r", "a": (-1000, 0, 0), "b": (-1000, -400, 0), **t, "carries": True}]


def supports(params):
    return [{"at": (0, 0, 0), "fix": ["ux", "uy", "uz", "rx"]}, {"at": (150, 0, 0), "fix": ["uy", "uz"]}]


def jacks(params):
    return [{"at": (-1000, 400, 0), "fix": ["uz"], "name": "jack_left"},
            {"at": (-1000, -400, 0), "fix": ["uz"], "name": "jack_right"}]


def build(params):
    import cadquery as cq
    return cq.Workplane().box(10, 10, 10)
'''

BOX = '''PARAMS = {"w": 1.0}


def build(params):
    import cadquery as cq
    return cq.Workplane().box(10, 10, 10)


def construction(params, build=None):
    return [{"name": "floor", "group": "floor", "kind": "sheet", "material": "plywood", "thickness": 9.525,
             "outline": [(0, -400, 30), (-1000, -400, 30), (-1000, 400, 30), (0, 400, 30)]}]
'''


def test_parked_the_jacks_take_their_share_and_one_that_would_pull_lifts_off(tmp_path):
    s = DesignStore.create("parked", base=str(tmp_path / "designs"))
    s.write_part("frame", FRAME, intent="a rail on a hitch with jacks")
    s.write_part("box", BOX, intent="a floor")
    r = P.run(s, "frame", person_lb=200, gear_lb=0, knee_lb=150, walls=False)
    lying = r["cases"][0]
    assert sum(lying["jacks_lb"]) > 0 and lying["hitch_lb"] > 0
    # standing still, the hitch and the jacks between them hold everything: 200 lb, the floor and the tubes
    assert 200 < lying["hitch_lb"] + sum(lying["jacks_lb"]) < 240
    # a jack only pushes: in no case does one pull, and one that would have lifted carries nothing
    for c in r["cases"]:
        assert all(f >= 0 for f in c["jacks_lb"])
        for name in c["lifted"]:
            assert c["jacks_lb"][["jack_left", "jack_right"].index(name)] == 0.0
    assert r["floor"]["on_mattress"]["safety"] > r["floor"]["bare"]["safety"]
    assert r["jacks_max_lb"] > 0
