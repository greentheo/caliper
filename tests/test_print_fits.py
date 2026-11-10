"""CALI-139 (#179) — never ok on a piece that doesn't fit the printer. The stool read "all of it" and "✓ your shop can make every
piece", measured, with three pieces that were each wider than the bed: the split cuts across the longest axis only."""

import pytest
import trimesh

from caliper import answers, design_api, making, printing, scorecard, shop
from caliper.design import DesignStore

pytest.importorskip("cadquery")

PRINTER = {"id": "printer", "kind": "printer", "volume_mm": [256, 256, 256], "materials": ["pla", "petg"]}


def _part(x, y, z):
    return f"""import cadquery as cq

def build(params):
    return cq.Workplane('XY').box({x}, {y}, {z}, centered=(True, True, False))

def construction(params, build=None):
    return [{{"name": "cone skirt", "kind": "printed", "material": "petg"}}]
"""


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    monkeypatch.setenv("CALIPER_SLICER", "")
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    return DesignStore.create("a stool", base=str(tmp_path / "designs"))


def test_a_wide_part_isn_t_ok_and_says_what_doesn_t_fit(store):
    store.write_part("stool", _part(583, 583, 737), intent="a wide stool")
    mk = making.plan(store, "stool", wait=False)
    assert mk["ok"] is False and mk["printed"] == []
    (m,) = mk["missing"]
    assert m["name"] == "cone skirt" and "one is still" in m["why"] and "your printer takes" in m["why"]


def test_the_card_names_it(store):
    store.write_part("stool", _part(583, 583, 737), intent="a wide stool")
    how = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "make")
    (line,) = [ln for ln in how["lines"] if ln["text"].startswith("Your shop can't make")]
    assert "cone skirt" in line["text"] and "your printer takes" in line["text"] and line["status"] == "bad"
    assert not [ln for ln in how["lines"] if ln["text"].startswith("Print it in")]


def test_the_scorecard_follows(store):
    store.write_part("stool", _part(583, 583, 737), intent="a wide stool")
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "make:shop"]
    assert check["status"] == "fail" and "your printer takes" in check["note"]
    assert "print.hours" not in card["metrics"]


def test_a_tall_narrow_part_still_splits_and_is_ok(store):
    store.write_part("stool", _part(100, 100, 600), intent="a tall post")
    mk = making.plan(store, "stool", wait=False)
    assert mk["ok"] is True and mk["printed"][0]["pieces"] > 1


def test_a_part_that_fits_is_one_piece_and_ok(store):
    store.write_part("stool", _part(100, 100, 100), intent="a block")
    mk = making.plan(store, "stool", wait=False)
    assert mk["ok"] is True and mk["printed"][0]["pieces"] == 1


def test_every_piece_is_checked_not_only_the_first():
    fits, wide = trimesh.creation.box((100, 100, 100)), trimesh.creation.box((400, 100, 100))
    assert printing.too_big([fits, wide], (256, 256, 256)) == [wide]
    assert printing.too_big([fits, fits], (256, 256, 256)) == []


def test_it_s_said_in_the_person_s_units(store):
    store.write_part("stool", _part(583, 583, 737), intent="a wide stool")
    store.design.display_units = "mm"
    store.save()
    assert "256 mm x 256 mm x 256 mm" in making.plan(store, "stool", wait=False)["missing"][0]["why"]
