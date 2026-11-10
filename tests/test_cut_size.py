"""CALI-143 (#183) — the stool's cut list had a smaller, 16-sided seat than the model, and nothing said so: 11.18 in across, from a 12 in
round disk. The outline is what gets cut. Where a printed rest takes whatever the pieces aren't, the difference went to it unseen."""
import math

import pytest

from caliper import answers, consistency, construction, design_api, release, scorecard, shop
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


# --- the review of #193: an edge that's right can't outvote one that's short ---------------------------------------------
@pytest.mark.parametrize("why,outline,cut", [
    ("short in length only, 10 each end", "[(10, 0, 220), (290, 0, 220), (290, 220, 220), (10, 220, 220)]", [280, 220]),
    ("short in width only, 10 each side", "[(0, 10, 220), (300, 10, 220), (300, 210, 220), (0, 210, 220)]", [300, 200]),
    ("20 short at one end only", "[(0, 0, 220), (280, 0, 220), (280, 220, 220), (0, 220, 220)]", [280, 220]),
    ("20 short along one side only", "[(0, 0, 220), (300, 0, 220), (300, 200, 220), (0, 200, 220)]", [300, 200]),
])
def test_short_on_any_one_side_is_named(store, why, outline, cut):
    (got,) = _differs(store, _table(outline))
    assert sorted(round(v) for v in got["outline"]) == sorted(cut), why
    assert sorted(round(v) for v in got["solid"]) == [220, 300], why


def _shape(store, pts):
    wp = f"cq.Workplane().polyline({pts}).close().extrude(12.7).translate((0, 0, 207.3))"
    return _differs(store, _table(str([(x, y, 220) for x, y in pts]), top=wp))


L = [(0, 0), (300, 0), (300, 100), (100, 100), (100, 220), (0, 220)]
U = [(0, 0), (300, 0), (300, 220), (200, 220), (200, 80), (100, 80), (100, 220), (0, 220)]
PLUS = [(100, 0), (200, 0), (200, 70), (300, 70), (300, 150), (200, 150), (200, 220), (100, 220), (100, 150), (0, 150), (0, 70), (100, 70)]
COMB = [(0, 0), (300, 0), (300, 220), (250, 220), (250, 60), (200, 60), (200, 220), (150, 220), (150, 60), (100, 60), (100, 220), (0, 220)]
STAR = [(150 + (130 if i % 2 == 0 else 60) * math.cos(math.pi * i / 5), 110 + (100 if i % 2 == 0 else 50) * math.sin(math.pi * i / 5)) for i in range(10)]


@pytest.mark.parametrize("name,pts", [("L", L), ("U", U), ("plus", PLUS), ("comb", COMB), ("star", STAR)])
def test_a_panel_cut_to_a_matching_shape_says_nothing(store, name, pts):
    assert _shape(store, pts) == [], name


@pytest.mark.parametrize("n", [16, 48])
def test_a_true_polygon_of_a_round_seat_says_nothing(store, n):
    r = 200.0
    poly = [(150 + r * math.cos(2 * math.pi * i / n), 110 + r * math.sin(2 * math.pi * i / n), 220) for i in range(n)]
    top = f"cq.Workplane().circle({r}).extrude(12.7).translate((150, 110, 207.3))"
    assert _differs(store, _table(str(poly), top=top)) == []


def test_a_kerf_on_one_side_says_nothing(store):
    assert _differs(store, _table("[(0, 0, 220), (298, 0, 220), (298, 220, 220), (0, 220, 220)]")) == []


def test_a_notch_in_the_outline_isn_t_a_smaller_panel(store):
    """It's the same size overall, so there aren't two sizes to give."""
    pts = [(0, 0), (140, 0), (140, 10), (160, 10), (160, 0), (300, 0), (300, 220), (0, 220)]
    assert _differs(store, _table(str([(x, y, 220) for x, y in pts]))) == []


# --- the size it states --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,outline,cut", [("half size", "[(0, 0, 220), (150, 0, 220), (150, 110, 220), (0, 110, 220)]", [150, 110]),
                                              ("100 in all round", "[(100, 100, 220), (200, 100, 220), (200, 120, 220), (100, 120, 220)]", [100, 20])])
def test_a_big_shortfall_states_the_model_s_true_size(store, name, outline, cut):
    (got,) = _differs(store, _table(outline))
    assert sorted(round(v) for v in got["outline"]) == sorted(cut), name
    assert [round(v) for v in sorted(got["solid"])] == [220, 300], name


# --- wherever the sheet is used --------------------------------------------------------------------------------------------
def test_the_scorecard_carries_it_as_a_warning_and_it_stops_nothing(store):
    store.write_part("t", _table(INSET), intent="a table")
    card = scorecard.compute(store)
    (w,) = card["warnings"]
    assert "The top you'd cut is" in w
    assert not [c for c in card["checks"] if "you'd cut" in str(c)]
    assert [c["id"] for c in card["checks"] if c["status"] == "fail"] == ["make:shop"]       # this shop has no printer: nothing of ours


def test_a_matching_panel_has_no_warning(store):
    store.write_part("t", _table(FULL), intent="a table")
    assert scorecard.compute(store)["warnings"] == []


def test_the_page_draws_the_warning():
    import os

    js = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
    assert "(card.warnings || []).map(" in open(js).read()


def _book(cut_smaller, s=None):
    s = s or {"pass": 2, "fail": 0, "unknown": 0, "untrusted": 0, "unresolved": 0, "edge": 0, "proposed": 0}
    return release._status({"summary": s, "checks": [{}, {}]}, cut_smaller)


def test_the_book_can_t_say_ready_and_stay_quiet():
    assert "Ready to cut" in _book(1) and "but 1 panel is cut smaller than the model: see the cut lists" in _book(1)
    assert "but 2 panels are cut smaller" in _book(2)
    assert "smaller" not in _book(0)


def test_the_words_beside_the_cut_list():
    src = open(release.__file__).read()
    i = src.index("<h2 class='page'>Cut lists</h2>")
    assert 'rec.get("cut_smaller")' in src[i:i + 200] and "Before you cut:" in src[i:i + 260]


def test_the_release_works_it_out_for_itself_not_from_an_old_card():
    src = open(release.__file__).read()
    assert '"cut_smaller": consistency.cut_smaller(store, [p.id for p in built])' in src


def test_a_short_stretch_under_an_inch_isn_t_the_panel_s_size(store):
    """20 mm of one edge pulled in, at the outline's far side: a tab, not a smaller panel."""
    pts = [(0, 0), (300, 0), (300, 100), (290, 100), (290, 120), (300, 120), (300, 220), (0, 220)]
    assert _differs(store, _table(str([(x, y, 220) for x, y in pts]))) == []


def test_a_tab_on_the_model_under_an_inch_wide_isn_t_the_panel_s_size(store):
    """The model has a 20 mm wide tab the outline doesn't: its overall size differs, but it's a tab, not a smaller panel."""
    tab = "cq.Workplane().box(300, 220, 12.7, centered=False).translate((0, 0, 207.3)).union(cq.Workplane().box(10, 20, 12.7, centered=False).translate((300, 100, 207.3)))"
    assert _differs(store, _table(FULL, top=tab)) == []


@pytest.mark.parametrize("name,pts", [("L", L), ("U", U), ("comb", COMB)])
def test_an_outline_drawn_the_other_way_round_says_nothing_either(store, name, pts):
    assert _shape(store, pts[::-1]) == [], name


def test_an_outline_drawn_the_other_way_round_is_still_named_when_short(store):
    (got,) = _differs(store, _table("[(10, 220, 220), (290, 220, 220), (290, 0, 220), (10, 0, 220)]"))
    assert sorted(round(v) for v in got["solid"]) == [220, 300]

