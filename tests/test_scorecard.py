"""CALI-47 — the scorecard: requirements as measured checks and objectives, with how far to trust them."""

import os

import pytest

from caliper import materials as M
from caliper import scorecard as SC
from caliper.design import DesignStore

from .test_construction import BOX

GOALS = """settings:
  payload_lb: 20
checks:
  - {id: light, label: "under 40 lb", metric: weight.crate, op: "<=", limit: 40}
  - {id: heavy, label: "over 100 lb (fails)", metric: weight.crate, op: ">=", limit: 100}
  - {id: nothing, label: "a metric nobody computes", metric: nope.nothing, op: ">=", limit: 1}
objectives:
  - {id: weight, label: "total weight", metric: weight.total_lb, direction: min}
  - {id: cost, label: "stock", metric: cost.usd, direction: min}
"""


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a crate", base=str(tmp_path / "designs"))
    s.write_part("crate", BOX, intent="an open crate")
    with open(SC.goals_path(s), "w") as f:
        f.write(GOALS)
    return s


def test_a_card_checks_what_the_goals_say_and_tracks_the_objectives(store):
    card = SC.compute(store)
    by = {c["id"]: c for c in card["checks"]}
    assert by["light"]["status"] == "pass" and by["light"]["margin"] > 0
    assert by["heavy"]["status"] == "fail"
    assert by["nothing"]["status"] == "unknown"                       # said, not silently dropped
    (weight, cost) = card["objectives"]
    assert weight["value"] == pytest.approx(card["metrics"]["weight.crate"]["value"] + 20, abs=0.2)
    assert weight["trust"] == "model" and cost["trust"] == "guess"
    assert card["summary"] == {"pass": 1, "fail": 1, "unknown": 1, "proposed": 0}
    assert SC.list_cards(store)[0]["created"] == card["created"]


def test_stock_is_priced_from_the_bill_of_materials(store):
    card = SC.compute(store)
    lines = {l["item"]: l for l in card["cost"]["lines"]}
    ply = next(v for k, v in lines.items() if "plywood" in k)
    assert ply["usd"] == pytest.approx(M.PRICES["sheet"][("plywood", 12.7)])
    foam = next(v for k, v in lines.items() if "XPS" in k)
    assert foam["usd"] == pytest.approx(2 * M.PRICES["sheet"][("xps", 25.4)])        # two shelf-packed sheets
    assert 0 < card["cost"]["waste_usd"] < card["cost"]["usd"]
    assert card["cost"]["usd"] == pytest.approx(sum(l["usd"] for l in card["cost"]["lines"]), abs=0.05)


def test_the_next_card_says_what_changed(store):
    first = SC.compute(store)
    store.write_part("crate", BOX.replace('"floor_t": 12.7', '"floor_t": 6.35'), action="refine")
    second = SC.compute(store)
    w0, w1 = first["objectives"][0], second["objectives"][0]
    assert w1["was"] == w0["value"] and w1["change"] < 0               # a thinner floor: lighter
    assert len(os.listdir(SC.cards_dir(store))) == 2


def test_without_goals_only_the_design_checks_itself(tmp_path):
    s = DesignStore.create("bare", base=str(tmp_path / "designs"))
    s.write_part("crate", BOX, intent="an open crate")
    card = SC.compute(s)
    assert card["objectives"] == [] and all(c.get("auto") for c in card["checks"])
