"""CALI-142 (#182) — the build book for a part that isn't a vehicle. A plywood-and-printed bar stool got "13.3 lb on the tongue",
fibreglass and "the first drive", no step for its printed cone, and a shopping list with no filament."""
import os

import pytest

from caliper import answers, construction, cutplan, design_api, release as R, shop
from caliper.design import DesignStore

from .test_mixed import MIXED

pytest.importorskip("cadquery")

PRINTER = {"id": "printer", "kind": "printer", "volume_mm": [400, 400, 400], "materials": ["pla", "petg"]}


@pytest.fixture(scope="module")
def stool(tmp_path_factory):
    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    tmp_path = tmp_path_factory.mktemp("book")
    mp = pytest.MonkeyPatch()
    mp.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    mp.setenv("CALIPER_SLICER", "")
    shop.write({"hand": ["drill", "jigsaw"], "machines": [PRINTER]})
    store = DesignStore.create("a side table", base=str(tmp_path / "designs"))
    store.write_part("table", MIXED, intent="a plywood top on printed sides")
    made = R.make(store, pdf=False)
    with open(os.path.join(R.releases_dir(store), made["id"], "index.html")) as f:
        yield store, made, f.read()
    mp.undo()


@pytest.mark.parametrize("word", ["tongue", "hitch", "first drive", "payload", "glass", "fibreglass", "under the floor"])
def test_the_book_has_no_vehicle_or_glass_words(stool, word):
    assert word not in stool[2].lower()


def test_a_printed_piece_has_its_own_step(stool):
    _, made, book = stool
    assert "Print and fit the sides" in [s["title"] for s in made["steps"]]
    assert "Print the sides in PETG: 1 piece, the STLs in printer/table/." in book
    assert "on the shopping list: add them" in book


def test_the_list_has_the_filament_and_agrees_with_what_do_i_buy(stool):
    store, _, book = stool
    g = construction.report(store, "table")["bom"]["printed"][0]
    grams = f"{g['filament_g']:.0f} g"
    assert f"<td>{grams}</td><td>PETG filament</td>" in book
    card = next(c for c in answers.part(store, design_api.design_state(store), "table") if c["key"] == "buy")
    assert f"{grams} of PETG filament" in card["lines"][0]["text"]


def test_the_book_says_why_the_slicer_s_grams_differ(stool):
    assert "The shopping list goes by the model's weight" in stool[2]


# --- a design on a hitch keeps its words ----------------------------------------------------------------------------------
def test_the_headlines_for_a_part_not_on_a_hitch():
    got = R._headlines({"weight.total_lb": {}, "hitch.tongue_lb": {}})
    assert ("weight.total_lb", "all up") in got and not [k for k, _ in got if k == "hitch.tongue_lb"]


def test_the_headlines_for_a_trailer():
    got = R._headlines({"weight.total_lb": {}, "hitch.tongue_lb": {}, "hitch.moment_lbin": {}})
    assert ("weight.total_lb", "all up, with the payload") in got and ("hitch.tongue_lb", "on the tongue") in got


@pytest.mark.parametrize("glass,paint,welded,hitched,first,last", [
    (False, 0, False, False, "Sand the edges smooth, and seal or paint it if you want to.", "Go over every fixing once more before anyone uses it."),
    (False, 0.5, False, False, "Paint it (0.50 gal of exterior paint in all).", "Go over every fixing once more before anyone uses it."),
    (True, 0.5, True, True, "Fill and fair the glass, then paint it: epoxy needs paint over it against the sun (0.50 gal of exterior paint in all).",
     "Go over every fixing and weld once more before the first drive."),
    (False, 0, True, False, "Sand the edges smooth, and seal or paint it if you want to.", "Go over every fixing and weld once more before anyone uses it."),
])
def test_the_finish_step_is_for_what_this_is(glass, paint, welded, hitched, first, last):
    assert R._finish_lines(glass, paint, welded, hitched) == [first, last]


GROUP = {"name": "cone_skirt", "material": "petg"}


def test_a_piece_in_sections_says_how_they_join():
    ctx = {"made": {"p": {"printed": [{"name": "cone_skirt", "pieces": 3, "pinned": True}]}}}
    got = R._print_lines("p", GROUP, ctx)
    assert got[0] == "Print the cone skirt in PETG: 3 pieces, the STLs in printer/p/." and "dowel pins" in got[1]


def test_a_piece_in_one_says_no_pins():
    got = R._print_lines("p", GROUP, {"made": {"p": {"printed": [{"name": "cone_skirt", "pieces": 1, "pinned": False}]}}})
    assert got[0].endswith("1 piece, the STLs in printer/p/.") and not any("dowel" in x for x in got)


def test_a_piece_the_shop_can_t_print_promises_no_files():
    got = R._print_lines("p", GROUP, {"made": {"p": {"printed": []}}})
    assert "can't be printed as it stands" in got[0] and not any("printer/" in x for x in got)
