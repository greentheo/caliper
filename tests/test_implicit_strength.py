"""CALI-113 (#115; rule 6) — a part that says what it must hold is held to it, goal or none.

A design with loads() but no strength goal in its scorecard.yaml released "ready to cut" on a strength ✗: only "your
shop can make it" was scored. The first run writes goals, so this hit designs made without them (no key, older ones,
a hand-made scorecard.yaml)."""

import os

import pytest

from caliper import load_study, release, scorecard
from caliper.design import DesignStore

from .test_consistency import STOOL
from .test_load_study import LOADS

pytest.importorskip("cadquery")

#: The test stool as it is: 200 lb, its 3/4 in top on two sides, ✗ 1.46x by the plate check.
HEAVY = STOOL + LOADS
#: Under a light load every case holds.
LIGHT = STOOL + LOADS.replace('"lb": 200', '"lb": 40').replace('"force": (0, 300, 0)', '"force": (0, 100, 0)')


def _goalless(tmp_path, monkeypatch, src, name):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 4)
    store = DesignStore.create("a stool", base=str(tmp_path / name))
    store.write_part("stool", src, intent="a step stool")
    assert not os.path.exists(os.path.join(store.root, "scorecard.yaml"))      # no goals at all
    return store, load_study.study(store, "stool")


def test_with_no_goal_a_strength_fail_isn_t_ready(tmp_path, monkeypatch):
    store, rec = _goalless(tmp_path, monkeypatch, HEAVY, "heavy")
    assert not rec["holds"]
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_loads"]
    assert check["label"] == "holds what its loads say, at its factor (from its loads)"
    assert check["status"] == "fail" and check["limit"] == rec["min_safety"] and check["source"] == "implicit"
    assert "1 check(s) fail" in release._status(card)


def test_with_no_goal_a_strength_pass_is_counted_as_one(tmp_path, monkeypatch):
    store, rec = _goalless(tmp_path, monkeypatch, LIGHT, "light")
    assert rec["holds"] and not any(load_study.unresolved(rec, c) for c in rec["cases"])
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_loads"]
    assert check["status"] == "pass"


def test_the_book_is_not_ready_and_says_why(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, _ = _goalless(tmp_path, monkeypatch, HEAVY, "book")
    made = release.make(store, pdf=False)
    assert not made["ready"]
    page = open(os.path.join(release.releases_dir(store), made["id"], "index.html")).read()
    assert "Not ready — 1 check(s) fail" in page and "Ready to cut" not in page
    assert "holds what its loads say, at its factor (from its loads)" in page


def test_seen_holding_with_no_goal_the_book_is_ready(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, _ = _goalless(tmp_path, monkeypatch, LIGHT, "ready")
    assert release.make(store, pdf=False)["ready"]


def test_a_stated_strength_goal_isn_t_doubled(tmp_path, monkeypatch):
    store, _ = _goalless(tmp_path, monkeypatch, LIGHT, "goal")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write("written_by: caliper\nchecks:\n- id: strength_step\n  label: holds a step\n"
                "  metric: strength.safety\n  op: '>='\n  limit: 2.0\n  source: assumed\n")
    card = scorecard.compute(store)
    assert not [c for c in card["checks"] if c["id"] == "strength_loads"]
    assert [c["id"] for c in card["checks"] if c.get("metric") == "strength.safety"] == ["strength_step"]


def test_a_goal_only_proposed_doesn_t_stand_in_for_one(tmp_path, monkeypatch):
    """#120 review, a surviving mutant (#72): a proposed strength goal binds nothing until it's kept, so the part is
    still held to its loads. Dropping the "proposed" test let it stand in for the implicit check."""
    store, _ = _goalless(tmp_path, monkeypatch, HEAVY, "proposed")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write("written_by: caliper\nchecks:\n- id: strength_step\n  label: holds a step\n"
                "  metric: strength.safety\n  op: '>='\n  limit: 2.0\n  source: proposed\n")
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_loads"]
    assert check["status"] == "fail" and check["source"] == "implicit"


def test_several_parts_are_held_to_the_strictest_s_safety(tmp_path, monkeypatch):
    """#120 review, a surviving mutant (#72): the limit is the strictest part's ``min_safety``, never the laxest's."""
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 4)
    store = DesignStore.create("two stools", base=str(tmp_path / "two"))
    store.write_part("low", LIGHT, intent="a step stool")
    store.write_part("tall", LIGHT, intent="a step stool")
    load_study.study(store, "low", min_safety=1.5)
    load_study.study(store, "tall", min_safety=3.0)
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_loads"]
    assert check["limit"] == 3.0
