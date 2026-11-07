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


# --- #125 review ---------------------------------------------------------------------------------------------------
def _open_print(monkeypatch):
    """The bar stool v7's throw (#126): the printed solid can't be made."""
    def throws(*a, **k):
        raise ValueError("Not all meshes are volumes!")
    monkeypatch.setattr(construction, "printed_solid", throws)


def test_a_printed_piece_that_can_t_be_weighed_makes_the_weight_unknown_never_lower(tmp_path, monkeypatch):
    store = _store(tmp_path, MIXED, "stool", "open")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(LIGHT.replace("limit: 0.2", "limit: 10.0"))     # the bar stool's cap: the ply alone would pass it
    _open_print(monkeypatch)
    rep = construction.report(store, "stool")
    assert rep["mass_lb"] is None and rep["unweighed"].startswith(construction.UNWEIGHED)
    bal = construction.balance(store)
    assert bal["mass_lb"] is None and any("The total isn't known" in n for n in bal["notes"])
    card = scorecard.compute(store)
    assert card["metrics"]["weight.total_lb"]["value"] is None
    (light,) = [c for c in card["checks"] if c["id"] == "light"]
    assert light["status"] == "unknown" and light["note"].startswith("stool: " + construction.UNWEIGHED)
    state = design_api.design_state(store)
    live = answers.measured(store, state)
    assert live["weight.total_lb"] is None and live["weight.unweighed"].startswith(construction.UNWEIGHED)
    line = next(ln for ln in answers.held_to(state, live) if "eeps total weight down" in ln["text"])
    assert line["status"] == "warn" and "not checked: the printed part's shape isn't closed" in line["text"]
    assert "✓" not in line["text"]


def test_balance_answers_with_the_note_not_an_error(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = _store(tmp_path, MIXED, "stool", "designs")
    _open_print(monkeypatch)
    got = TestClient(create_app()).post(f"/api/designs/{store.design.slug}/balance", json={})
    assert got.status_code == 200, got.text
    assert got.json()["mass_lb"] is None and got.json()["unweighed"]


def test_no_change_is_set_against_a_card_from_an_older_scorer(tmp_path):
    store = _store(tmp_path, TUBE, "tube", "was")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write("written_by: caliper\nchecks: []\nobjectives:\n- id: light\n  label: as light as it can be\n"
                "  metric: weight.total_lb\n  direction: min\n")
    first = scorecard.compute(store)
    path = sorted(os.listdir(scorecard.cards_dir(store)))[-1]
    old = {**first, "metrics": {**first["metrics"], "weight.total_lb": {**first["metrics"]["weight.total_lb"],
                                                                       "value": 0.01}}}
    old.pop("scorer")
    with open(os.path.join(scorecard.cards_dir(store), path), "w") as f:
        json.dump(old, f)
    (o,) = scorecard.compute(store)["objectives"]
    assert o["was"] is None and o["change"] is None and o["note"] == "scored differently since"
    (o,) = scorecard.compute(store)["objectives"]                  # against a card of its own scorer: a change
    assert o["was"] == o["value"] and o["change"] == 0 and "note" not in o
