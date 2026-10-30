"""CALI-52 — a roof under snow and the skeleton that holds it: napkin mechanics, searched."""

import pytest

from caliper import materials as M
from caliper import snow
from caliper.design import DesignStore

ROOF = {"length": 1000.0, "width": 1500.0, "core": "xps", "core_t": 25.4, "skins_out": ["fiberglass"],
        "skins_in": [], "beams": {"count": 0}, "rail_size": None, "rail_span": None}


def test_a_foam_roof_with_one_skin_cracks_underneath_and_a_second_skin_fixes_it():
    q = 20 * snow.PSF
    one = snow.panel(ROOF, 1000.0, q)
    two = snow.panel({**ROOF, "skins_in": ["fiberglass"]}, 1000.0, q)
    assert one["governs"] == "xps in tension" and one["safety"] < 1
    assert two["safety"] > 2 * one["safety"] and two["sag_mm"] < one["sag_mm"] / 5


def test_a_bare_board_bends_like_the_handbook_says():
    q, span, t = 0.001, 500.0, 25.4
    out = snow.panel({**ROOF, "skins_out": []}, span, q)
    m = q * span ** 2 / 8
    assert out["stress_mpa"] == pytest.approx(6 * m / t ** 2, abs=1e-3)


def test_a_stick_carries_its_strip_of_roof():
    w, span = 0.5, 1000.0                                 # N/mm along a 1 m 2x2
    b, h = M.STICKS["lumber"]["sizes"]["2x2"]
    out = snow.stick("beam", "2x2", span, w)
    assert out["stress_mpa"] == pytest.approx(w * span ** 2 / 8 / (b * h ** 2 / 6), abs=0.01)
    assert out["safety"] == pytest.approx(M.STICKS["lumber"]["mech"]["strength"] / out["stress_mpa"], rel=1e-2)


def test_beams_shorten_the_panels_span_and_carry_its_load():
    none = snow.check(ROOF, 20)
    across = snow.check({**ROOF, "beams": {"count": 3, "size": "2x2", "dir": "across"}}, 20)
    assert across["elements"][0]["span_mm"] == pytest.approx(1000 / 4)
    assert across["elements"][0]["safety"] > none["elements"][0]["safety"]
    assert any("roof beam" in e["element"] for e in across["elements"])


ROOFED = '''PARAMS = {"w": 1.0}

BUILD = {"roof_beams": 0, "skin_in": "none", "frame_posts": "2x2", "roof_beam": "2x2", "roof_beam_dir": "across"}


def build(params):
    import cadquery as cq
    return cq.Workplane().box(1, 1, 1)


def roof(params, build=None):
    b = {**BUILD, **(build or {})}
    return {"length": 1000.0, "width": 1500.0, "core": "xps", "core_t": 25.4, "skins_out": ["fiberglass"],
            "skins_in": [] if b["skin_in"] == "none" else [b["skin_in"]],
            "beams": {"count": b["roof_beams"], "size": b["roof_beam"], "dir": b["roof_beam_dir"]},
            "rail_size": b["frame_posts"], "rail_span": 1300.0}


def construction(params, build=None):
    b = {**BUILD, **(build or {})}
    out = [{"name": "roof", "kind": "sheet", "material": "xps", "thickness": 25.4,
            "outline": [(0, 0, 0), (1000, 0, 0), (1000, 1500, 0), (0, 1500, 0)],
            "covers": ["fiberglass"] + ([] if b["skin_in"] == "none" else [b["skin_in"]])}]
    for j in range(b["roof_beams"]):
        x = (j + 1) * 1000 / (b["roof_beams"] + 1)
        out.append({"name": f"beam_{j}", "kind": "stick", "material": "lumber", "size": b["roof_beam"],
                    "a": (x, 0, 0), "b": (x, 1500, 0)})
    return out
'''


def test_the_search_tries_every_combination_and_recommends_the_lightest_that_holds(tmp_path):
    s = DesignStore.create("a roof", base=str(tmp_path / "designs"))
    s.write_part("roof", ROOFED, intent="a roof")
    rec = snow.search(s, "roof", {"roof_beams": [0, 1, 3], "skin_in": ["none", "fiberglass"]}, psf=20)
    assert len(rec["rows"]) == 6
    best = next(r for r in rec["rows"] if r["build"] == rec["best"])
    assert best["holds"]
    assert all(r["mass_lb"] >= best["mass_lb"] for r in rec["rows"] if r["holds"])
    assert not next(r for r in rec["rows"] if r["build"] == {"roof_beams": 0, "skin_in": "none"})["holds"]
    assert s.history("roof")[-1]["kind"] == "search"
