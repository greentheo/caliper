"""CALI-81 — a printed part's strength check, and saying why a check couldn't run."""

import pytest

from caliper import answers, design_api, load_study
from caliper import materials as M
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: A printed box, 4 mm walls, open underneath: stood on in the middle of its top.
PRINTED = '''import cadquery as cq

PARAMS = {"w": 120.0, "d": 100.0, "h": 80.0, "wall": 6.0}
BUILD = {"material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    outer = cq.Workplane().box(p["w"], p["d"], p["h"], centered=(True, True, False))
    inner = cq.Workplane().box(p["w"] - 2 * p["wall"], p["d"] - 2 * p["wall"], p["h"] - p["wall"],
                               centered=(True, True, False))
    return outer.cut(inner)


def construction(params, build=None):
    b = {**BUILD, **(build or {})}
    return [{"name": "box", "kind": "printed", "material": b["material"], "infill": b["infill"]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "a foot", "lb": 50, "factor": 2.0, "lo": (-20, -20, p["h"] - 2), "hi": (20, 20, p["h"])}]
'''


@pytest.fixture
def store(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    s = DesignStore.create("a printed box", base=str(tmp_path / "designs"))
    s.write_part("box", PRINTED, intent="a printed box")
    return s


def test_a_printed_part_is_checked_as_its_plastic_at_the_weaker_way(store):
    from whittle import MATERIALS

    rec = load_study.study(store, "box")
    mat = rec["material"]
    assert mat["printed"] and mat["name"] == M.printed("petg")["name"]
    solid = mat["solid"]
    assert 0.4 < solid < 1.0                                  # walls solid, the rest 40% infill
    assert mat["strength"] == pytest.approx(MATERIALS["petg"].strength * solid * load_study.LAYERS_ACROSS, rel=1e-3)
    assert mat["E"] == pytest.approx(MATERIALS["petg"].youngs_modulus * solid, rel=1e-3)
    (case,) = rec["cases"]
    assert case["governs"] == "fea" and case["safety"] and case["breaks_lb"]     # no plate check for a print
    assert any("Printed: a rough model on the safe side" in n for n in rec["notes"])
    # the voxels are sized from its walls, not from a sheet it hasn't got
    assert rec["spacing_mm"] <= 6.0


def test_a_check_that_cant_run_says_why_on_the_card(store):
    store.write_part("box", PRINTED.replace('"lo": (-20, -20, p["h"] - 2)', '"lo": (-20, -20, p["h"] + 30)')
                     .replace('"hi": (20, 20, p["h"])', '"hi": (20, 20, p["h"] + 40)'), intent="loaded in the air")
    with pytest.raises(ValueError, match="thin air"):
        load_study.study(store, "box")
    work = answers.answers(store, design_api.design_state(store), "box")[1]
    assert work["lines"][0]["text"].startswith("I couldn't check it holds: 'a foot' doesn't touch the part")


def test_a_printed_part_s_verdict_says_about(store, tmp_path, monkeypatch):
    """CALI-86 (#62, finding 9; rule 6): a printed part's strength model is rough, and its card said "Holds …, N
    times over" as plainly as a plywood one's."""
    from .test_load_study import BOX_STOOL

    # four voxels across its 6 mm walls (CALI-97): at the fixture's two, the ✓ is "not resolved yet". Seen at four,
    # the box under 50 lb reads ✗ 1.9x (it read ✓ 2.7x at two), so the ✓ here is under 40 lb
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 4)
    store.write_part("box", PRINTED.replace('"lb": 50', '"lb": 40'), intent="a printed box")
    load_study.study(store, "box")
    line = next(ln for ln in answers.answers(store, design_api.design_state(store), "box")[1]["lines"]
                if ln.get("study") == "load")
    # the reviewer's wording (#71 rework, item 6): "about" on the top line, the caveat one click down by the promise
    # with what it's against (#64 item 9), and, close to its limit, amber and says so (#64 item 2)
    import re

    assert re.fullmatch(r"Holds a foot, about [\d.]+ times over 80 lb \(40 lb, twice over\)(: close to the 2 it needs)?\.",
                        line["text"]), line["text"]
    work = answers.answers(store, design_api.design_state(store), "box")[1]
    assert "Printed parts are a rough model" in work["promise"]
    ply = DesignStore.create("a box stool", base=str(tmp_path / "ply"))
    ply.write_part("stool", BOX_STOOL, intent="a box stool")
    load_study.study(ply, "stool")
    line = next(ln for ln in answers.answers(ply, design_api.design_state(ply), "stool")[1]["lines"]
                if ln.get("study") == "load")
    assert "about" not in line["text"] and "rough" not in line["text"], line["text"]


def test_a_printed_part_that_doesnt_hold_says_about_too(store):
    """CALI-86 (#71 rework, item 5): the "Doesn't hold" branch."""
    store.write_part("box", PRINTED.replace('"lb": 50', '"lb": 900'), intent="a printed box, a heavy load")
    load_study.study(store, "box")
    line = next(ln for ln in answers.answers(store, design_api.design_state(store), "box")[1]["lines"]
                if ln.get("study") == "load")
    assert line["text"].startswith("Doesn't hold a foot: only about "), line["text"]


def test_a_mixed_part_governed_by_its_plywood_gets_plywoods_words(tmp_path, monkeypatch):
    """CALI-86 (#71 rework, item 5): the caveat follows what governs. test_mixed's top fails as a plywood beam."""
    pytest.importorskip("whittle")
    from .test_mixed import MIXED

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", MIXED, intent="a plywood top on printed sides")
    rec = load_study.study(s, "stool")
    assert rec["material"].get("printed") and rec["cases"][0]["governs"] == "plate"
    work = answers.answers(s, design_api.design_state(s), "stool")[1]
    line = next(ln for ln in work["lines"] if ln.get("study") == "load")
    assert "about" not in line["text"] and "rough" not in work.get("promise", ""), (line["text"], work.get("promise"))
