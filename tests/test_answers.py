"""The four questions, answered in a line anyone can read (specs/caliper-four-questions-spec.md, step 1)."""

import json
import os

import pytest

from caliper import answers, design_api, fasteners, load_study
from caliper import construction as C
from caliper.consistency import _sides, shapes, tolerance
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("A step stool so my kid can reach the sink. It has to hold me too (200 lb).",
                           base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL, intent="A one-platform step stool from 3/4 in plywood. Glued and screwed.")
    s.design.display_units = "in"
    s.save()
    return s


def test_a_box_of_five_panels_has_eight_joints_and_the_screws_and_glue_for_them(store):
    d = C.declared(store, "stool")
    pcs, mesh = shapes(d), store.part_geometry("stool").require_mesh()
    _sides(mesh, pcs)
    got = fasteners.estimate(pcs, tolerance(mesh))
    assert got["joints"] == 8                      # four corners, and the top to each wall
    assert got["screws"] >= 16 and got["screw"] == "#8 × 1 1/4 in wood screws"
    assert got["glue"] == "an 8 oz bottle of wood glue"
    assert C.report(store, "stool")["bom"]["fasteners"]["screws"] == got["screws"]


def test_the_four_cards_read_top_line_first(store):
    cards = {c["key"]: c for c in answers.answers(store, design_api.design_state(store), "stool")}
    assert [c["q"] for c in cards.values()] == ["What is it?", "Will it work?", "What do I buy?", "How do I make it?"]
    assert cards["what"]["lines"][0]["text"] == "A one-platform step stool from 3/4 in plywood."
    assert cards["what"]["lines"][1]["text"].startswith("16 × 10 in, 9 in tall")
    # it says what it must hold but nobody's checked: a warning that says what to do
    assert cards["work"]["status"] == "warn" and "Check it holds" in cards["work"]["lines"][0]["text"]
    buy = cards["buy"]["lines"][0]["text"]
    assert "1 sheet of 3/4 in softwood plywood" in buy and "screws and wood glue" in buy and "about $" in buy
    assert cards["make"]["lines"][0]["text"] == "With your jigsaw: 5 pieces."
    assert any("say what's in your shop" in ln["text"] for ln in cards["make"]["lines"])
    # no internal names in a top line
    assert not any(w in ln["text"] for c in cards.values() for ln in c["lines"]
                   for w in ("construction()", "voxel", "PARAMS", "station"))


def test_a_strength_check_becomes_a_verdict_and_an_older_one_says_so(store):
    run = os.path.join(load_study.runs_dir(store), "20261030-000000-test")
    os.makedirs(run)
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({"id": "t", "part": "stool", "version": 1, "created": 1.0, "min_safety": 2, "holds": True,
                   "cases": [{"name": "An adult stepping up", "safety": 3.11, "holds": True}]}, f)
    work = answers.answers(store, design_api.design_state(store), "stool")[1]
    assert work["status"] == "ok" and work["lines"][0]["text"] == "Holds an adult stepping up, 3.1 times over."
    store.write_part("stool", BOX_STOOL, intent="a stool")                  # v2: the check is now older
    work = answers.answers(store, design_api.design_state(store), "stool")[1]
    assert work["status"] == "warn" and "older version" in work["lines"][0]["text"]


def test_the_design_card_says_what_isnt_done_yet(store):
    cards = {c["key"]: c for c in answers.answers(store, design_api.design_state(store))}
    assert cards["what"]["lines"][0]["text"] == "A step stool so my kid can reach the sink."
    assert cards["work"]["status"] == "warn" and "say what it must do" in cards["work"]["lines"][0]["text"]
    # one part: the design answers with that part's list and plan (CALI-59), then offers the build package
    assert cards["make"]["lines"][0]["text"] == "With your jigsaw: 5 pieces."
    assert "build package" in cards["make"]["lines"][-1]["text"]
    assert "1 sheet of 3/4 in softwood plywood" in cards["buy"]["lines"][0]["text"]
    assert cards["what"]["lines"][1]["text"].startswith("16 × 10 in, 9 in tall")


def test_will_it_work_lists_what_the_design_is_held_to(store):
    """Spec step 2: the conversation's checks are the card's lines: a verdict from what's measured, or what it
    needs to be checked, and proposals to keep or drop."""
    from caliper import goals

    goals.write(store, {"checks": [
        {"id": "holds", "label": "holds Dad (200 lb), 2 times over", "metric": "strength.safety", "op": ">=",
         "limit": 2, "source": "assumed"},
        {"id": "light", "label": "light enough for a kid to carry", "metric": "weight.total_lb", "op": "<=",
         "limit": 10, "source": "stated"},
        {"id": "cheap", "label": "under $5", "metric": "cost.usd", "op": "<=", "limit": 5, "source": "stated"},
        {"id": "pretty", "label": "fits on one sheet", "metric": "make.sheets", "op": "<=", "limit": 1,
         "source": "proposed"}]})
    work = {c["key"]: c for c in answers.answers(store, design_api.design_state(store))}["work"]
    text = [ln["text"] for ln in work["lines"]]
    assert text[0] == "Holds Dad (200 lb), 2 times over (assumed): not checked yet. Check it holds."
    assert text[1].startswith("✓ Light enough for a kid to carry:") and text[1].endswith(" lb.")
    assert text[2].startswith("✗ Under $5: $") and work["status"] == "bad"
    assert text[3] == "Proposed: Fits on one sheet. Keep or drop it under the numbers."
    # a part alone in its design answers for the design too, after its own strength line
    part = {c["key"]: c for c in answers.answers(store, design_api.design_state(store), "stool")}["work"]
    assert any(t["text"].startswith("✗ Under $5") for t in part["lines"])
