"""CALI-130 (#160) — a part with one unsliced piece says so, and one slicer timeout doesn't stick. On Theo's stool the
card read "about 220.6 h (a rough guess; the slicer couldn't work it out: PrusaSlicer, default profile…)": the reason
was a success label from a piece that sliced, and a single timeout showed that rough number until the server restarted.
Stubbed: no slicer runs."""

import itertools
import threading
import time

import pytest
import trimesh

from caliper import answers, design_api, making, printing, shop
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
