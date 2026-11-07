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
    # the design keeps its own fact, and only that
    assert [(r.question, r.answer) for r in store.design.requirements] == [(HEIGHT.question, "29 in")]
    (offer,) = clarify.offers(store)
    assert offer["text"] == "Add a 256 × 256 × 256 mm printer (PETG) to your shop?"
    assert not os.path.exists(no_shop)                                         # nothing written until a yes
    clarify.take_offer(store, 0, add=True)
    on_disk = yaml.safe_load(open(no_shop))
    assert {"kind": "printer", "volume_mm": [256, 256, 256], "materials": ["petg"], "id": "printer"} in on_disk["machines"]
    assert shop.machine(shop.read(), "printer")["volume_mm"] == [256, 256, 256]
    assert clarify.offers(store) == []


def test_a_no_leaves_the_shop_alone(tmp_path, no_shop):
    store = _asked(tmp_path, [BED])
    clarify.answer_round(store, {"bed_size": "10 in"})
    (offer,) = clarify.offers(store)
    assert offer["machine"]["volume_mm"] == [254, 254, 254]                    # a bed said in inches, as mm
    clarify.take_offer(store, 0, add=False)
    assert not os.path.exists(no_shop) and clarify.offers(store) == []
    assert store.design.requirements == []                                     # never a design fact


def test_an_answer_that_says_nothing_the_shop_can_take_offers_nothing():
    assert clarify.shop_offer("printer", "") is None
    assert clarify.shop_offer("printer", "as your shop has it") is None
    assert clarify.shop_offer("printer", "a big one") is None
    assert clarify.shop_offer("hand", "a jigsaw and a drill")["hand"] == ["jigsaw", "drill"]
    assert clarify.shop_offer("router", "4 x 8 ft")["machine"]["bed_in"] == [48, 96]            # feet, as inches
    assert clarify.shop_offer("router", "48 x 96 in")["machine"]["bed_in"] == [48, 96]
    assert clarify.shop_offer("plasma", "1220 x 1220 mm")["machine"]["bed_in"] == [48.03, 48.03]


def test_a_shop_question_is_known_by_its_words():
    assert clarify.shop_topic(Question("q", "How big is your printer's build volume?")) == "printer"
    assert clarify.shop_topic(Question("q", "Do you have a CNC router?")) == "router"
    assert clarify.shop_topic(Question("q", "What tools do you have?")) == "hand"
    assert clarify.shop_topic(Question("q", "How tall is the seat?")) == ""
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
