"""CALI-111 (#112; rule 6) — an all-printed design gets a build package, and the book weighs what the card weighs.

1. ``cutplan.run`` wrote cutplan.json into a folder only made for sheets or plates: an all-printed part's release
   raised FileNotFoundError.
2. The bar stool's book said "✓ mesh cone keeps total weight down 1.6 lb" while its design card said ✗ 10.9 lb. The
   same card said weight.i_want 10.9 lb: the scorecard's total came from ``construction.balance()``, which left out
   every printed piece (``report()`` weighs them with ``with_printed()``). 10.9 was right."""

import json
import os

import pytest

from caliper import answers, construction, cutplan, design_api, release, scorecard
from caliper.design import DesignStore

from .test_mixed import MIXED
from .test_resolved import TUBE

pytest.importorskip("cadquery")

#: The stool's goal on weight, as the bar stool's conversation wrote it (a cap of 10 lb).
LIGHT = """written_by: caliper
checks:
- id: light
  label: keeps total weight down
  metric: weight.total_lb
  op: <=
  limit: 0.2
  source: assumed
"""


def _store(tmp_path, src, pid, name):
    store = DesignStore.create("a part", base=str(tmp_path / name))
    store.write_part(pid, src, intent="a part")
    return store


def _needs_cutplan():
    if cutplan.available() is not None:
        pytest.skip(cutplan.available())


def test_an_all_printed_part_makes_a_build_package_that_says_nothing_to_cut(tmp_path):
    _needs_cutplan()
    store = _store(tmp_path, TUBE, "tube", "tube")
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    assert os.path.exists(os.path.join(root, "index.html"))
    cut = open(os.path.join(root, "cutlist.txt")).read()
    assert "Nothing to cut: it's all printed." in cut, cut
    (plan,) = cutplan.list_runs(store, "tube")
    assert plan["sheets"] == [] and os.path.exists(os.path.join(cutplan.runs_dir(store), plan["id"], "cutplan.json"))


def test_the_total_weighs_printed_pieces_as_each_part_does(tmp_path):
    for src, pid in ((TUBE, "tube"), (MIXED, "stool")):
        store = _store(tmp_path, src, pid, pid)
        part = construction.report(store, pid)["mass_lb"]
        assert part > 0
        assert construction.balance(store)["mass_lb"] == pytest.approx(part, abs=0.05), pid
        card = scorecard.compute(store)
        assert card["metrics"]["weight.total_lb"]["value"] == pytest.approx(part, abs=0.05)


def test_the_book_s_numbers_are_the_card_s_for_the_same_version(tmp_path):
    """The accept: a release's scorecard values equal the live card's. A weight goal it fails is a ✗ in both."""
    _needs_cutplan()
    store = _store(tmp_path, MIXED, "stool", "mixed")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(LIGHT)
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    booked = json.load(open(os.path.join(root, "scorecard.json")))
    state = design_api.design_state(store)
    live = answers.measured(store, state)
    assert booked["versions"] == {p["id"]: p["version"] for p in state["parts"]}
    assert booked["metrics"]["weight.total_lb"]["value"] == pytest.approx(live["weight.total_lb"], abs=0.05)
    (light,) = [c for c in booked["checks"] if c["id"] == "light"]
    assert light["status"] == "fail" and not made["ready"]
    line = next(ln for ln in answers.held_to(state, live) if "eeps total weight down" in ln["text"])
    assert line["status"] == "bad", line


def test_a_card_scored_before_this_fix_is_out_of_date_and_the_release_scores_again(tmp_path):
    """A card on file from the old scorer (Theo's says 1.6 lb) matches the versions but not the weighing: it isn't
    reused, and the page says so."""
    _needs_cutplan()
    store = _store(tmp_path, MIXED, "stool", "old")
    card = scorecard.compute(store)
    old = {**card, "metrics": {**card["metrics"], "weight.total_lb": {**card["metrics"]["weight.total_lb"],
                                                                       "value": 0.1}}}
    old.pop("scorer")
    path = os.path.join(scorecard.cards_dir(store), "20000101-000000.json")
    for name in os.listdir(scorecard.cards_dir(store)):
        os.remove(os.path.join(scorecard.cards_dir(store), name))
    with open(path, "w") as f:
        json.dump(old, f)
    assert scorecard.list_cards(store, 1)[0]["outdated"] is True
    made = release.make(store, pdf=False)
    booked = json.load(open(os.path.join(release.releases_dir(store), made["id"], "scorecard.json")))
    assert booked["metrics"]["weight.total_lb"]["value"] == pytest.approx(card["metrics"]["weight.total_lb"]["value"])
    assert booked["scorer"] == scorecard.SCORER and not scorecard.list_cards(store, 1)[0].get("outdated")
