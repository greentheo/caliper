"""CALI-130 (#160) — a part with one unsliced piece says so, and one slicer timeout doesn't stick. On Theo's stool the
card read "about 220.6 h (a rough guess; the slicer couldn't work it out: PrusaSlicer, default profile…)": the reason
was a success label from a piece that sliced, and a single timeout showed that rough number until the server restarted.
Stubbed: no slicer runs."""

import itertools
import threading
import time

import pytest
import trimesh

from caliper import answers, design_api, goals, making, printing, shop
from caliper.design import DesignStore

from .test_cards_speed import _sliced
from .test_shop import PRINTED, PRINTER

pytest.importorskip("cadquery")

GOOD = {"hours": 10.0, "filament_g": 300.0, "usd": 7.0, "trust": "model",
        "from": "PrusaSlicer, default profile at this printer's size"}
ROUGH = {"hours": 2.5, "filament_g": 60.0, "usd": 1.5, "trust": "rough",
         "from": "walls + infill at rough speeds (the slicer timed out)"}


@pytest.fixture
def bar(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "_GAVE_UP", {})
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    return store


def _pieces(monkeypatch, *results):
    it = itertools.cycle(results)
    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(next(it)))


def _line(store):
    how = next(c for c in answers.part(store, design_api.design_state(store), "bar") if c["key"] == "make")
    return next(ln["text"] for ln in how["lines"] if ln["text"].startswith("Print it in PETG"))


# --- 1. the reason comes from the piece that failed -------------------------------------------------------------------
@pytest.mark.parametrize("first,second", [(GOOD, {**ROUGH, "slicer_failed": True}),
                                          ({**ROUGH, "slicer_failed": True}, GOOD)])
def test_a_mixed_group_gives_the_failed_piece_s_reason_and_how_much_is_rough(bar, monkeypatch, first, second):
    _pieces(monkeypatch, first, second)
    (pr,) = making.plan(bar, "bar", wait=False)["printed"]
    assert pr["from"] == ROUGH["from"] and pr["trust"] == "rough" and pr["rough"] == 1 and pr["hours"] == 12.5
    assert _line(bar) == ("Print it in PETG: 2 pieces, about 12.5 h (1 of 2 pieces is a rough guess: "
                          "the slicer timed out).")


def test_a_caller_that_waits_gets_the_failed_piece_s_reason_too(bar, monkeypatch):
    """The build book prints ``from``: a waiting caller's rough piece has no ``slicer_failed`` mark, and is rough."""
    _pieces(monkeypatch, GOOD, ROUGH)
    (pr,) = making.plan(bar, "bar")["printed"]
    assert pr["from"] == ROUGH["from"] and pr["trust"] == "rough"


def test_every_piece_rough_reads_as_before(bar, monkeypatch):
    rough = {**ROUGH, "slicer_failed": True}
    _pieces(monkeypatch, rough)
    assert _line(bar) == ("Print it in PETG: 2 pieces, about 5 h (a rough guess; the slicer couldn't work it out: "
                          "the slicer timed out).")


def test_every_piece_sliced_says_nothing_about_a_guess(bar, monkeypatch):
    _pieces(monkeypatch, GOOD)
    (pr,) = making.plan(bar, "bar", wait=False)["printed"]
    assert pr["trust"] == "model" and pr["rough"] == 0 and not pr["slicer_failed"]
    assert _line(bar) == "Print it in PETG: 2 pieces, about 20 h."


# --- 2. a remembered failure expires ----------------------------------------------------------------------------------
@pytest.fixture
def slicing(tmp_path, monkeypatch):
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "_GAVE_UP", {})
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/prusa-slicer")
    calls, script = [], []

    def run(path, material, volume, infill, timeout=600.0):
        calls.append(timeout)
        return dict(script.pop(0) if script else {**ROUGH, "_retry": True})

    monkeypatch.setattr(printing, "_estimate", run)
    stl = tmp_path / "a.stl"
    stl.write_bytes(b"solid a\nendsolid a\n")
    return lambda: printing.estimate(str(stl), "petg", (220, 220, 250), wait=False), calls, script


def test_a_failure_is_ten_minutes_long():
    assert printing.RETRY_AFTER == 600.0


def test_a_failure_is_not_retried_before_it_expires(slicing):
    ask, calls, _ = slicing
    ask()
    _sliced(0)
    for _ in range(5):
        assert ask()["slicer_failed"]
    _sliced(0)
    assert len(calls) == 1


def test_a_failure_is_retried_after_it_expires_and_a_success_replaces_it(slicing, monkeypatch):
    ask, calls, script = slicing
    ask()
    _sliced(0)
    monkeypatch.setattr(printing, "RETRY_AFTER", -1.0)
    script.append(GOOD)
    during = ask()
    assert during["slicer_failed"] and during["hours"] == ROUGH["hours"] and not during.get("pending")   # it keeps it
    _sliced(0)
    assert len(calls) == 2
    now = ask()
    assert now["hours"] == GOOD["hours"] and not now.get("slicer_failed") and not printing._GAVE_UP


def test_a_retry_is_started_once_however_often_it_is_asked(slicing, monkeypatch):
    ask, calls, _ = slicing
    ask()
    _sliced(0)
    monkeypatch.setattr(printing, "RETRY_AFTER", -1.0)
    gate = threading.Event()
    real = printing._estimate

    def slow(*a, **k):
        gate.wait(5)
        return real(*a, **k)

    monkeypatch.setattr(printing, "_estimate", slow)
    for _ in range(5):
        ask()
    gate.set()
    _sliced(0)
    assert len(calls) == 2


def test_a_retry_that_fails_again_waits_again(slicing, monkeypatch):
    ask, calls, _ = slicing
    ask()
    _sliced(0)
    monkeypatch.setattr(printing, "RETRY_AFTER", -1.0)
    ask()
    _sliced(0)
    monkeypatch.setattr(printing, "RETRY_AFTER", 600.0)
    for _ in range(3):
        ask()
    _sliced(0)
    assert len(calls) == 2


# --- 3. what the limit is measured from -------------------------------------------------------------------------------
def test_a_queued_slice_isn_t_timed_out_by_its_wait(tmp_path, monkeypatch):
    """The limit starts when its slicer does: the second piece waits a whole slice behind the first and gets it all."""
    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "_GAVE_UP", {})
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/prusa-slicer")
    monkeypatch.setattr(printing, "BACKGROUND_TIMEOUT", 0.3)
    seen = []

    def run(cmd, capture_output, text, timeout):
        seen.append(timeout)
        time.sleep(0.5)                                     # longer than the limit, so a shared clock would run out

    monkeypatch.setattr(printing.subprocess, "run", run)
    monkeypatch.setattr(trimesh, "load", lambda *a, **k: trimesh.creation.box((10, 10, 10)))
    for name in ("a", "b"):
        stl = tmp_path / f"{name}.stl"
        stl.write_bytes(f"solid {name}\nendsolid {name}\n".encode())
        printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)
    _sliced(0)
    assert seen == [0.3, 0.3]


# --- #166 review: a guess is never a pass ---------------------------------------------------------------------------
@pytest.mark.parametrize("rough,pieces,said", [
    (1, 3, "1 of 3 pieces is a rough guess: the slicer timed out"),
    (2, 3, "2 of 3 pieces are a rough guess: the slicer timed out"),
    (3, 3, "a rough guess; the slicer couldn't work it out: the slicer timed out"),
    (0, 3, ""),
])
def test_how_much_is_a_guess_is_said_one_way(rough, pieces, said):
    assert making.rough_said(rough, pieces, ROUGH["from"]) == said


NO_SLICER = {**ROUGH, "from": "walls + infill at rough speeds (no slicer installed)"}


def _goal(store, limit):
    goals.write(store, {"checks": [{"id": "fast", "label": "prints in a day", "metric": "print.hours", "op": "<=",
                                    "limit": limit, "source": "answered"}]})
    state = design_api.design_state(store)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(store, state)) if "prints in a day" in ln["text"].lower()]
    return line


FAILED = {**ROUGH, "slicer_failed": True}


def test_a_print_time_goal_with_a_rough_piece_is_no_tick(bar, monkeypatch):
    _pieces(monkeypatch, GOOD, FAILED)
    line = _goal(bar, 100)
    assert line["status"] == "warn" and line["text"].startswith("! Prints in a day: ") and "✓" not in line["text"]
    assert "partly a guess (1 of 2 pieces is a rough guess: the slicer timed out)" in line["text"]


def test_every_piece_rough_is_a_guess_not_partly(bar, monkeypatch):
    _pieces(monkeypatch, FAILED)
    line = _goal(bar, 100)
    assert line["status"] == "warn" and ", a guess (" in line["text"] and "partly" not in line["text"]


def test_a_rough_time_over_its_limit_stays_a_cross(bar, monkeypatch):
    """The real number is higher still, so a ✗ on a guess is certain."""
    _pieces(monkeypatch, GOOD, FAILED)
    assert _goal(bar, 1)["text"].startswith("✗")


def test_a_sliced_time_gets_its_tick(bar, monkeypatch):
    _pieces(monkeypatch, GOOD)
    line = _goal(bar, 100)
    assert line["text"].startswith("✓") and line["status"] == "ok"


def test_with_no_slicer_the_card_says_it_s_a_guess_and_isn_t_green(bar, monkeypatch):
    _pieces(monkeypatch, NO_SLICER)
    how = next(c for c in answers.part(bar, design_api.design_state(bar), "bar") if c["key"] == "make")
    line = next(ln for ln in how["lines"] if ln["text"].startswith("Print it in PETG"))
    assert line["text"] == "Print it in PETG: 2 pieces, about 5 h (a rough guess: no slicer installed)."
    assert line["status"] == "warn"


def test_a_sliced_line_is_still_green(bar, monkeypatch):
    _pieces(monkeypatch, GOOD)
    how = next(c for c in answers.part(bar, design_api.design_state(bar), "bar") if c["key"] == "make")
    assert next(ln for ln in how["lines"] if ln["text"].startswith("Print it in PETG"))["status"] == "ok"


def _scored(store, monkeypatch, *results):
    from caliper import scorecard

    _pieces(monkeypatch, *results)
    return scorecard.compute(store)


def test_the_scorecard_says_rough_and_where_it_came_from(bar, monkeypatch):
    goals.write(bar, {"checks": [{"id": "fast", "label": "prints in a day", "metric": "print.hours", "op": "<=",
                                  "limit": 100, "source": "answered"}]})
    card = _scored(bar, monkeypatch, GOOD, FAILED)
    for name in ("print.hours", "print.filament_g"):
        assert card["metrics"][name]["trust"] == "rough"
        assert card["metrics"][name]["source"] == "1 of 2 pieces is a rough guess: the slicer timed out"
    (check,) = [c for c in card["checks"] if c.get("id") == "fast"]
    assert check["status"] != "pass" and check["trust"] == "rough" and "rough guess" in check["note"]


def test_the_scorecard_keeps_model_for_a_sliced_time(bar, monkeypatch):
    card = _scored(bar, monkeypatch, GOOD)
    assert card["metrics"]["print.hours"]["trust"] == "model" and card["metrics"]["print.hours"]["source"] == "slicer"


def test_the_build_book_and_the_panel_give_the_count():
    import os
    import re

    from caliper import release

    src = open(release.__file__).read()
    assert "pr.get('rough_said') or pr['from']" in src
    js = open(os.path.join(os.path.dirname(release.__file__), "web", "static", "design.js")).read()
    assert re.search(r"esc\(x\.rough_said \|\| x\.from\)", js)
