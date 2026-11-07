"""CALI-124 (#145) — the questions read the shop, and an answer about the shop goes to the shop.

From Theo's bar stool run: the clarifying questions asked for the printer's bed size, which is the shop's. His answer
went into the design's requirements, so *How do I make it?* couldn't use it. Stubbed throughout: a fake asker or a
fake client writes the questions; the shop is a file in a temp folder (``CALIPER_SHOP``)."""

import json
import os

import pytest
import yaml

from caliper import clarify, shop
from caliper.clarify import Question
from caliper.design import DesignStore

BED = Question("bed_size", "What is your 3D printer's bed size?", "the cone is printed in pieces that fit it",
               "220 x 220 mm")
HEIGHT = Question("seat_height", "How tall is the seat?", "the stool's height", "29 in")
THEO = {"hand": ["jigsaw", "drill", "circular saw"],
        "machines": [{"id": "printer", "kind": "printer", "volume_mm": [256, 256, 256], "materials": ["pla", "petg"]}]}


@pytest.fixture
def no_shop(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop" / "shop.yaml"))
    return tmp_path / "shop" / "shop.yaml"


@pytest.fixture
def theos_shop(no_shop):
    shop.write(THEO)
    return no_shop


def test_with_theo_s_shop_no_question_asks_for_the_bed_size(theos_shop):
    qs, source = clarify.draft_questions("a bar stool", asker=lambda p: [BED, HEIGHT], shop=shop.read())
    bed, height = qs
    assert source == "injected" and bed.about == "shop:printer"
    assert "bed size" not in bed.question.lower() and "?" not in bed.question
    assert bed.question.startswith("Your printer: 256 × 256 × 256 mm build volume, PLA, PETG.")
    assert bed.default == "as your shop has it"
    assert height.question == HEIGHT.question and not height.about            # a design question, as asked


def test_claude_is_told_the_shop_so_it_doesn_t_ask(theos_shop):
    asked = []

    class Fake:
        class messages:  # noqa: N801 — the client's shape
            @staticmethod
            def create(**kw):
                asked.append(kw)
                block = type("B", (), {"type": "text", "text": json.dumps([HEIGHT.to_dict()])})
                return type("M", (), {"content": [block]})

    qs, source = clarify.draft_questions("a bar stool", client=Fake, shop=shop.read())
    said = asked[0]["messages"][0]["content"]
    assert source == "llm" and "Their shop (what they make things with; never ask about it):" in said
    assert "your printer: 256 × 256 × 256 mm build volume, PLA, PETG" in said
    assert "your hand tools: jigsaw, drill, circular saw" in said


def _asked(tmp_path, questions):
    store = DesignStore.create("a bar stool", base=str(tmp_path / "designs"))
    clarify.open_round(store, clarify.with_shop(questions, shop.read(), known=False), source="injected")
    return store


def test_with_no_shop_a_bed_size_answer_offers_to_add_it_and_a_yes_lands_in_shop_yaml(tmp_path, no_shop):
    store = _asked(tmp_path, [BED, HEIGHT])
    assert clarify.pending(store)[0].about == "shop:printer"                   # still asked: the shop doesn't know
    clarify.answer_round(store, {"bed_size": "256 x 256 x 256 mm, PETG", "seat_height": "29 in"})
    # an offer never removes an answer: both are kept (#146, the foreman's call)
    assert [(r.question, r.answer) for r in store.design.requirements] == [
        (BED.question, "256 x 256 x 256 mm, PETG"), (HEIGHT.question, "29 in")]
    (offer,) = clarify.offers(store)
    assert offer["text"] == "Add a printer with a 256 × 256 × 256 mm build volume, PETG, to your shop?"
    assert not os.path.exists(no_shop)                                         # nothing written until a yes
    clarify.take_offer(store, 0, add=True)
    on_disk = yaml.safe_load(open(no_shop))
    # only the machine offered: the default jigsaw, drill and saw are never written as yours (#146 review)
    assert on_disk == {"machines": [{"kind": "printer", "volume_mm": [256, 256, 256], "materials": ["petg"],
                                     "id": "printer"}]}
    have = shop.read()
    assert have["machines"][0]["volume_mm"] == [256, 256, 256] and have["hand_default"] is True
    assert clarify.offers(store) == []


def test_a_no_leaves_the_shop_alone(tmp_path, no_shop):
    store = _asked(tmp_path, [BED])
    clarify.answer_round(store, {"bed_size": "10 in"})
    (offer,) = clarify.offers(store)
    assert offer["machine"]["volume_mm"] == [254, 254, 254]                    # a bed said in inches, as mm
    clarify.take_offer(store, 0, add=False)
    assert not os.path.exists(no_shop) and clarify.offers(store) == []
    assert [r.answer for r in store.design.requirements] == ["10 in"]          # the answer kept all the same


def test_an_answer_that_says_nothing_the_shop_can_take_offers_nothing():
    assert clarify.shop_offer("printer", "") is None
    assert clarify.shop_offer("printer", "as your shop has it") is None
    assert clarify.shop_offer("printer", "a big one")["kind"] == "note"         # said, never dropped (#146)
    assert clarify.shop_offer("hand", "a jigsaw and a drill")["hand"] == ["jigsaw", "drill"]
    # no wrong machine (#146 review): only sizes said with their units, a bare 4x8 table in feet
    assert clarify.shop_offer("printer", "Bambu X1C")["kind"] == "note"
    assert clarify.shop_offer("printer", "0.4 nozzle, 256 bed")["kind"] == "note"
    assert clarify.shop_offer("printer", "0.4 mm nozzle, 256 x 256 x 256 mm bed")["machine"]["volume_mm"] == [256] * 3
    assert clarify.shop_offer("router", "150 x 150 mm")["machine"]["bed_in"] == [5.91, 5.91]   # mm, not inches
    assert clarify.shop_offer("router", "4x8")["text"] == "Add a router with a 48 × 96 in bed (4 × 8 ft) to your shop?"
    assert clarify.shop_offer("router", "4x8 table")["kind"] == "note"         # only a bare sheet size is feet
    assert clarify.shop_offer("router", "4 x 8 ft")["machine"]["bed_in"] == [48, 96]            # feet, as inches
    assert clarify.shop_offer("router", "48 x 96 in")["machine"]["bed_in"] == [48, 96]
    assert clarify.shop_offer("plasma", "1220 x 1220 mm")["machine"]["bed_in"] == [48.03, 48.03]


def test_a_shop_question_is_known_by_its_words():
    assert clarify.shop_topic(Question("q", "How big is your printer's build volume?")) == "printer"
    assert clarify.shop_topic(Question("q", "Do you have a CNC router?")) == "router"
    assert clarify.shop_topic(Question("q", "What tools do you have?")) == "hand"
    assert clarify.shop_topic(Question("q", "How tall is the seat?")) == ""
    assert clarify.shop_topic(Question("q", "What nozzle diameter should the hose fitting take?")) == ""
    # a question already tagged keeps its tag
    assert clarify.shop_topic(Question("q", "Anything else?", about="shop:plasma")) == "plasma"


def test_how_do_i_make_it_reads_the_shop_not_the_requirements():
    """#145 item 3: an old design's shop fact in its requirements is left alone; making reads the shop."""
    src = open(os.path.join(os.path.dirname(clarify.__file__), "making.py")).read()
    assert "shop = shop or S.read()" in src and "requirements" not in src


def test_the_page_offers_add_it_or_no():
    src = open(os.path.join(os.path.dirname(clarify.__file__), "web", "static", "design.js")).read()
    assert "data-shopoffer=\"${i}\" data-add=\"1\">Add it</button>" in src
    assert "`/api/designs/${S.slug}/shop-offer`" in src



# --- #146 review ---------------------------------------------------------------------------------------------------

PROBES = [Question("cart", "How tall is the plasma cutter the cart has to carry?"),
          Question("enclosure", "Should the enclosure fit a CNC router with its dust shoe?"),
          Question("hose", "What nozzle diameter should the hose fitting take?"),
          Question("bit", "Which router bit profile do you want on the edge?"),
          Question("bed", "What size is your printer bed?")]


def test_the_reviewer_s_five_probes_lose_no_answer(tmp_path, no_shop):
    """Only a question about your own machine is the shop's; a design question that names a machine keeps its answer."""
    store = _asked(tmp_path, PROBES)
    assert [q.about for q in clarify.pending(store)] == ["", "", "", "", "shop:printer"]
    clarify.answer_round(store, {"cart": "about 40 in", "enclosure": "yes, with the shoe", "hose": "3/4 in",
                                 "bit": "a 1/4 in roundover", "bed": "256 x 256 x 256 mm"})
    kept = {r.question: r.answer for r in store.design.requirements}
    assert kept == {PROBES[0].question: "about 40 in", PROBES[1].question: "yes, with the shoe",
                    PROBES[2].question: "3/4 in", PROBES[3].question: "a 1/4 in roundover",
                    PROBES[4].question: "256 x 256 x 256 mm"}                    # an offer never removes an answer
    (offer,) = clarify.offers(store)
    assert offer["machine"]["volume_mm"] == [256, 256, 256]                    # the bed went to the shop's offer


def test_a_shop_answer_that_offers_nothing_is_said_and_kept(tmp_path, no_shop):
    store = _asked(tmp_path, [BED])
    clarify.answer_round(store, {"bed_size": "Bambu X1C"})
    assert [(r.question, r.answer) for r in store.design.requirements] == [(BED.question, "Bambu X1C")]
    (note,) = clarify.offers(store)
    assert note == {"kind": "note", "about": "printer",
                    "text": "I couldn't read a printer from 'Bambu X1C': add it to your shop by hand, or give its build "
                            "volume with its units (\"256 x 256 x 256 mm\")."}
    clarify.take_offer(store, 0, add=True)                                     # a note is only seen: nothing written
    assert not os.path.exists(no_shop) and clarify.offers(store) == []


def test_tools_you_said_are_kept_when_a_machine_is_added(tmp_path, theos_shop):
    store = _asked(tmp_path, [Question("router", "Do you have a CNC router? Its bed size?")])
    clarify.answer_round(store, {"router": "4 x 8 ft"})
    clarify.take_offer(store, 0, add=True)
    have = shop.read()
    assert have["hand"] == ["jigsaw", "drill", "circular saw"] and "hand_default" not in have
    assert [m["kind"] for m in have["machines"]] == ["printer", "router"]



def test_an_offer_never_removes_an_answer(tmp_path, no_shop):
    """#146, the foreman's call on the reviewer's residual: a "your …" answer that becomes a shop offer is kept as a
    requirement too. The cart is sized by "your plasma cutter" whether or not it goes to the shop."""
    cart = Question("cutter", "How big is your plasma cutter's table?")
    store = _asked(tmp_path, [cart])
    clarify.answer_round(store, {"cutter": "4 x 8 ft"})
    (offer,) = clarify.offers(store)
    assert offer["machine"] == {"kind": "plasma", "bed_in": [48.0, 96.0]}
    assert [(r.question, r.answer) for r in store.design.requirements] == [(cart.question, "4 x 8 ft")]
    clarify.take_offer(store, 0, add=False)                                    # a no to the shop keeps it too
    assert [r.answer for r in store.design.requirements] == ["4 x 8 ft"]
