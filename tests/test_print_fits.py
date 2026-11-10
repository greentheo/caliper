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
    assert m["name"] == "cone skirt" and "all " in m["why"] and "too big" in m["why"] and "your printer takes" in m["why"]


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
    assert card["metrics"]["print.hours"]["value"] is None and "doesn't fit your printer" in card["metrics"]["print.hours"]["note"]


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


# --- the review of #187 ------------------------------------------------------------------------------------------------
FAST = """written_by: caliper
checks:
- id: fast
  label: Prints in a day
  metric: print.hours
  op: <=
  limit: 24
  source: assumed
"""
WORD = "can't be worked out: the cone skirt doesn't fit your printer"


def _sliced(monkeypatch):
    monkeypatch.setattr(printing, "estimate", lambda *a, **k: {"hours": 2.0, "filament_g": 30.0, "usd": 1.0, "trust": "model",
                                                               "from": "the slicer"})


def _two(store):
    store.write_part("wide", _part(583, 583, 100), intent="a wide ring")
    store.write_part("block", _part(50, 50, 50), intent="a small block")
    with open(scorecard.goals_path(store), "w") as f:
        f.write(FAST)
    return design_api.design_state(store)


def test_a_refused_part_leaves_no_print_total_for_the_design(store, monkeypatch):
    _sliced(monkeypatch)
    now = answers.measured(store, _two(store))
    assert "print.hours" not in now and now["print.unknown"] == WORD


def test_a_goal_on_the_time_says_why_and_never_passes(store, monkeypatch):
    _sliced(monkeypatch)
    state = _two(store)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(store, state)) if "Prints in a day" in ln["text"]]
    assert WORD in line["text"] and line["status"] == "warn" and "Score it" not in line["text"] and "✓" not in line["text"]


def test_the_scorecard_gives_no_total_and_the_goal_says_why(store, monkeypatch):
    _sliced(monkeypatch)
    _two(store)
    card = scorecard.compute(store)
    assert card["metrics"]["print.hours"]["value"] is None and card["metrics"]["print.filament_g"]["value"] is None
    (goal,) = [c for c in card["checks"] if c["id"] == "fast"]
    assert goal["status"] == "unknown" and WORD in goal["note"]


def test_with_one_part_too_the_goal_says_why_not_score_it(store, monkeypatch):
    _sliced(monkeypatch)
    store.write_part("wide", _part(583, 583, 100), intent="a wide ring")
    with open(scorecard.goals_path(store), "w") as f:
        f.write(FAST)
    state = design_api.design_state(store)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(store, state)) if "Prints in a day" in ln["text"]]
    assert WORD in line["text"] and "Score it" not in line["text"]


def test_a_piece_with_no_printer_leaves_no_total_either(store, monkeypatch):
    _sliced(monkeypatch)
    _two(store)
    shop.write({"hand": ["drill"], "machines": []})
    got = making.no_print_total(making.plan(store, "wide", wait=False))
    assert got == "can't be worked out: your shop can't print the cone skirt"


def test_a_refusal_beats_a_part_still_slicing(store, monkeypatch):
    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(printing.WORKING))
    assert answers.measured(store, _two(store))["print.unknown"] == WORD


def test_the_design_s_card_names_the_part_that_doesn_t_fit(store, monkeypatch):
    _sliced(monkeypatch)
    how = next(c for c in answers.design(store, _two(store)) if c["key"] == "make")
    (line,) = [ln for ln in how["lines"] if ln["text"].startswith("Your shop can't make")]
    assert "wide" in line["text"] and "cone skirt" in line["text"] and "your printer takes" in line["text"] and line["status"] == "bad"
    assert "block" not in line["text"]


class _Piece:
    def __init__(self, *e):
        self.extents = e


def test_the_words_say_the_clearance_and_what_to_do():
    got = making._too_big_said(2, [_Piece(253, 126, 100), _Piece(253, 126, 100)], (256, 256, 256), False)
    assert got == ("cut into 2 pieces, all 2 are too big: the biggest is 253 mm x 126 mm x 100 mm, and your printer takes "
                   "256 mm x 256 mm x 256 mm, less 5 mm clearance: section it differently, in the chat, or use a bigger printer")


@pytest.mark.parametrize("over,said", [(1, "1 of the 3 is too big"), (2, "2 of the 3 are too big"), (3, "all 3 are too big")])
def test_how_many_are_too_big(over, said):
    assert said in making._too_big_said(3, [_Piece(300, 10, 10)] * over, (256, 256, 256), False)


def test_it_names_the_biggest_piece_not_the_first():
    got = making._too_big_said(3, [_Piece(300, 10, 10), _Piece(583, 20, 10), _Piece(400, 10, 10)], (256, 256, 256), False)
    assert "the biggest is 583 mm x 20 mm x 10 mm" in got


def test_the_words_in_inches():
    got = making._too_big_said(2, [_Piece(254, 127, 25.4)] * 2, (254, 254, 254), True)
    assert "the biggest is 10 in x 5 in x 1 in" in got and "your printer takes 10 in x 10 in x 10 in, less 0.2 in clearance" in got
