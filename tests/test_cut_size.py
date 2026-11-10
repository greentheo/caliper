"""CALI-143 (#183) — the stool's cut list had a smaller, 16-sided seat than the model, and nothing said so: 11.18 in across, from a 12 in
round disk. The outline is what gets cut. Where a printed rest takes whatever the pieces aren't, the difference went to it unseen."""
import math

import pytest

from caliper import answers, consistency, construction, design_api, shop
from caliper.design import DesignStore

pytest.importorskip("cadquery")


def _table(outline: str, top: str = "cq.Workplane().box(300, 220, 12.7, centered=False).translate((0, 0, 207.3))", rest: bool = True) -> str:
    return f"""import cadquery as cq, math

def build(params):
    side = lambda x0: cq.Workplane().box(20, 220, 207.3, centered=False).translate((x0, 0, 0))
    return side(0).union(side(280)).union({top})

def construction(params, build=None):
    return [{{"name": "top", "kind": "sheet", "material": "plywood", "thickness": 12.7, "outline": {outline}}},
            {{"name": "sides", "kind": "printed", "material": "petg", "infill": 0.4{', "rest": True' if rest else ''}}}]
"""


FULL = "[(0, 0, 220), (300, 0, 220), (300, 220, 220), (0, 220, 220)]"
INSET = "[(10, 10, 220), (290, 10, 220), (290, 210, 220), (10, 210, 220)]"
NEAR = "[(1, 1, 220), (299, 1, 220), (299, 219, 220), (1, 219, 220)]"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    monkeypatch.setenv("CALIPER_SLICER", "")
    shop.write({"hand": ["drill", "jigsaw"], "machines": []})
    return DesignStore.create("a table", base=str(tmp_path / "designs"))


def _differs(store, src):
    store.write_part("t", src, intent="a table")
    return consistency.plan_differs(construction.declared(store, "t"), store.part_geometry("t"))


def test_a_panel_cut_smaller_than_the_model_is_named_with_both_sizes(store):
    (got,) = _differs(store, _table(INSET))
    assert got["name"] == "top"
    assert sorted(round(v) for v in got["outline"]) == [200, 280] and sorted(round(v) for v in got["solid"]) == [220, 300]


def test_an_outline_that_matches_says_nothing(store):
    assert _differs(store, _table(FULL)) == []


def test_within_a_kerf_says_nothing(store):
    assert _differs(store, _table(NEAR)) == []


def test_without_a_printed_rest_the_other_check_has_it(store):
    assert _differs(store, _table(INSET, rest=False)) == []


def test_a_round_seat_declared_as_a_smaller_polygon_like_the_stool(store):
    r = 152.4
    poly = [(150 + 0.95 * r * math.cos(2 * math.pi * i / 16), 110 + 0.95 * r * math.sin(2 * math.pi * i / 16), 220) for i in range(16)]
    top = "cq.Workplane().circle(152.4).extrude(12.7).translate((150, 110, 207.3))"
    (got,) = _differs(store, _table(str(poly), top=top))
    assert all(v / 25.4 == pytest.approx(11.2, abs=0.2) for v in got["outline"])
    assert all(v / 25.4 == pytest.approx(12.0, abs=0.15) for v in got["solid"])


def test_the_card_names_it_with_both_sizes(store):
    store.write_part("t", _table(INSET), intent="a table")
    store.design.display_units = "mm"
    store.save()
    what = next(c for c in answers.part(store, design_api.design_state(store), "t") if c["key"] == "what")
    (line,) = [ln for ln in what["lines"] if "you'd cut" in ln["text"]]
    assert "The top you'd cut is " in line["text"] and "280 mm x 200 mm" in line["text"] and "300 mm x 220 mm" in line["text"]
    assert line["status"] == "warn" and "follow the smaller outline" in line["text"]


def test_a_matching_panel_s_card_has_no_such_line(store):
    store.write_part("t", _table(FULL), intent="a table")
    what = next(c for c in answers.part(store, design_api.design_state(store), "t") if c["key"] == "what")
    assert not [ln for ln in what["lines"] if "you'd cut" in ln["text"]]


def test_other_pieces_round_it_are_not_taken_for_more_of_this_one(store):
    """A top inset 10 mm all round, with a rim piece of its own on each side: the solid runs on past its outline, but that's the rims."""
    rims = {"rim_a": [(0, 0), (300, 0), (300, 10), (0, 10)], "rim_b": [(0, 210), (300, 210), (300, 220), (0, 220)],
            "rim_c": [(0, 10), (10, 10), (10, 210), (0, 210)], "rim_d": [(290, 10), (300, 10), (300, 210), (290, 210)]}
    more = "".join(f'{{"name": "{k}", "kind": "sheet", "material": "plywood", "thickness": 12.7, '
                   f'"outline": {[(x, y, 220) for x, y in v]}}},\n            ' for k, v in rims.items())
    assert _differs(store, _table(INSET).replace('{"name": "sides"', more + '{"name": "sides"')) == []
