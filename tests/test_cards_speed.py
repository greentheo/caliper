"""CALI-104 (#97) — the cards right after a revision don't build the part again.

Measured on a copy of Theo's bar stool (v7) at main: warm cards take 1.3–1.5 s, but right after a revision they took
9.6 s, 6 of it building the part again, which the revision had just built in its own sandbox. Now a revision offers its
own successful build for the version it wrote, keyed by that file (its path and this write's time) and checked
against the script's hash, so it can't serve another version's shape. Stubbed: no Claude call."""

import numpy as np
import pytest

from caliper import assembly, chat, sandbox
from caliper.design import DesignStore

from .test_chat import _author, _box

pytest.importorskip("cadquery")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", _box(), intent="a box")
    return s


def _counted(monkeypatch):
    """Count the sandbox builds from here on."""
    n = {"builds": 0}
    real = sandbox.run_script

    def run(script, params=None, *a, **k):
        n["builds"] += 1
        return real(script, params, *a, **k)

    monkeypatch.setattr(sandbox, "run_script", run)
    return n


def _same(a, b):
    ma, mb = a.require_mesh(), b.require_mesh()
    assert np.array_equal(ma.vertices, mb.vertices) and np.array_equal(ma.faces, mb.faces)
    assert ma.metadata.get("strays") == mb.metadata.get("strays")


def test_a_revision_s_own_build_is_the_cards_and_the_same_mesh_a_fresh_build_gives(store, monkeypatch):
    script = _box(dx=60)
    built = sandbox.run_script(script, {})
    store.write_part("box", script, intent="wider", built=(script, {}, built.geometry))
    n = _counted(monkeypatch)
    got = store.part_geometry("box")
    assert n["builds"] == 0 and got.solid is built.geometry.solid          # not built again: the revision's own
    assembly._PART_CACHE.clear()                                          # a fresh build of the same version
    fresh = store.part_geometry("box")
    assert n["builds"] == 1
    _same(got, fresh)                                                     # the mesh every reader sees is the same


def test_an_offer_never_serves_another_version_s_shape(store, monkeypatch):
    wide = _box(dx=60)
    built = sandbox.run_script(wide, {})
    store.write_part("box", wide, intent="wider", built=(wide, {}, built.geometry))
    store.write_part("box", _box(dx=90), intent="wider still")            # a later version, written without one
    got = store.part_geometry("box")
    assert got.solid is not built.geometry.solid
    assert got.require_mesh().bounds[1][0] - got.require_mesh().bounds[0][0] == pytest.approx(90, abs=0.01)


@pytest.mark.parametrize("why,built", [
    ("a failed revision", lambda s: (s, {}, None)),
    ("built with params the cards don't use", lambda s: (s, {"w": 5}, sandbox.run_script(s, {}).geometry)),
    ("another script than the one written", lambda s: (s + "\n# other\n", {}, sandbox.run_script(s, {}).geometry)),
])
def test_nothing_is_kept_but_a_good_build_of_the_exact_script(store, why, built):
    assembly._OFFERED.clear()
    script = _box(dx=70)
    store.write_part("box", script, intent=why, built=built(script))
    assert assembly._OFFERED == {}, why


def test_a_refine_builds_its_part_once(store, monkeypatch):
    """The chat's revision builds it; its own measure after, and the cards, use that build."""
    store.part_geometry("box")                                            # v1, as the page already has it
    n = _counted(monkeypatch)
    got = chat.turn(store, "make the box 50 mm wide", scope="box", author=_author(_box(dx=50)), use_llm=False)
    assert got.ok and got.action == "refine"
    builds = n["builds"]
    from caliper import answers, design_api

    answers.answers(store, design_api.design_state(store), "box")
    assert n["builds"] == builds == 1, n


# --- the slicer off the card's path: "working it out", then the number; never a stale or rough one as final ----------

@pytest.fixture
def slow_slicer(monkeypatch):
    """A slicer that answers only when let go, as PrusaSlicer takes 10 s of the bar stool's card."""
    import threading

    from caliper import printing

    go, calls = threading.Event(), []

    def estimate(path, material, volume, infill, timeout=600.0):
        calls.append(path)
        go.wait(10)
        return {"hours": 3.5, "filament_g": 120.0, "usd": 3.0, "trust": "model", "from": "PrusaSlicer"}

    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/prusa-slicer")
    monkeypatch.setattr(printing, "_estimate", estimate)
    return go, calls


def _sliced(key_count, timeout=5.0):
    import time

    from caliper import printing

    t = time.time()
    while (len(printing._SLICED) < key_count or printing._PENDING) and time.time() - t < timeout:
        time.sleep(0.02)


def test_a_card_never_waits_for_the_slicer_and_says_it_s_working(tmp_path, slow_slicer):
    from caliper import printing

    go, calls = slow_slicer
    stl = tmp_path / "a.stl"
    stl.write_bytes(b"solid a\nendsolid a\n")
    first = printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)
    assert first == printing.WORKING and first["hours"] is None                      # no number, said so
    assert printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)["pending"]
    go.set()
    _sliced(1)
    assert len(calls) == 1                                                            # sliced once, not per ask
    assert printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)["hours"] == 3.5


def test_the_cards_say_print_time_working_it_out_and_a_print_goal_waits(tmp_path, slow_slicer):
    from caliper import answers, design_api, goals, making, shop

    from .test_shop import PRINTED, PRINTER

    go, _ = slow_slicer
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    goals.write(store, {"checks": [{"id": "fast", "label": "prints in a day", "metric": "print.hours", "op": "<=",
                                    "limit": 24, "source": "answered"}]})
    mk = making.plan(store, "bar", wait=False)
    (pr,) = mk["printed"]
    assert mk["pending"] and pr["pending"] and pr["hours"] is None and pr["usd"] is None
    state = design_api.design_state(store)
    how = next(c for c in answers.part(store, state, "bar") if c["key"] == "make")
    (line,) = [ln for ln in how["lines"] if ln["text"].startswith("Print it in PETG")]
    assert line["text"] == "Print it in PETG: 2 pieces; print time: working it out…" and line["working"]
    now = answers.measured(store, state)
    assert "print.hours" not in now and now["print.pending"] == "print time: working it out…"
    (goal,) = [ln for ln in answers.held_to(state, now) if "prints in a day" in ln["text"].lower()]
    assert goal["text"] == "Prints in a day: print time: working it out…" and goal["status"] == "info"
    go.set()
    _sliced(2)
    now = answers.measured(store, design_api.design_state(store))
    assert now["print.hours"] == 7.0 and "print.pending" not in now                    # two pieces, 3.5 h each
    # the scorecard, the release and the making panel wait for the real number: never "working"
    assert making.plan(store, "bar")["printed"][0]["hours"] == 7.0


def test_the_page_asks_again_while_a_print_time_is_worked_out():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    body = src[src.index("async function loadAnswers()"):src.index("function wireCards()")]
    assert "ln.working" in body and "setTimeout" in body and "S.answers.key === key" in body


def test_a_slicer_that_fails_or_hangs_is_said_once_and_not_asked_again(tmp_path, monkeypatch):
    """#152 review: a timed-out slice isn't remembered (#140), so the card said "working it out" forever and sliced
    again on each ask. In the background, a failed slice gives the card its rough number, said as rough and why."""
    from caliper import answers, design_api, making, printing, shop

    from .test_shop import PRINTED, PRINTER

    calls = []

    def hung(path, material, volume, infill, timeout=600.0):
        calls.append(path)
        return {"hours": 9.9, "filament_g": 300.0, "usd": 7.0, "trust": "rough",
                "from": "walls + infill at rough speeds (the slicer timed out)", "_retry": True}

    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "_GAVE_UP", {})
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/prusa-slicer")
    monkeypatch.setattr(printing, "_estimate", hung)
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    assert making.plan(store, "bar", wait=False)["pending"]
    _sliced(0)
    first = len(calls)
    mk = making.plan(store, "bar", wait=False)
    (pr,) = mk["printed"]
    assert not mk["pending"] and pr["slicer_failed"] and pr["trust"] == "rough" and pr["hours"] == 19.8
    how = next(c for c in answers.part(store, design_api.design_state(store), "bar") if c["key"] == "make")
    (line,) = [ln for ln in how["lines"] if ln["text"].startswith("Print it in PETG")]
    assert line["text"] == ("Print it in PETG: 2 pieces, about 19.8 h (a rough guess; the slicer couldn't work it "
                            "out: the slicer timed out).")
    assert not line.get("working")                                          # the page stops asking
    assert len(calls) == first == 2                                         # not sliced again per ask
    making.plan(store, "bar")                                               # a caller that waits still tries again
    assert len(calls) == 4


def _failing(monkeypatch, fail):
    from caliper import printing

    calls, live, most = [], [0], [0]

    def run(path, material, volume, infill, timeout=600.0):
        import time

        calls.append(timeout)
        live[0] += 1
        most[0] = max(most[0], live[0])
        time.sleep(0.05)
        live[0] -= 1
        return fail()

    monkeypatch.setattr(printing, "_SLICED", {})
    monkeypatch.setattr(printing, "_PENDING", set())
    monkeypatch.setattr(printing, "_GAVE_UP", {})
    monkeypatch.setattr(printing, "slicer", lambda: "/usr/bin/prusa-slicer")
    monkeypatch.setattr(printing, "_estimate", run)
    return calls, most


def test_a_failing_slicer_starts_once_however_often_the_page_asks(tmp_path, monkeypatch):
    """#152 review, blocking: each 4 s re-ask started PrusaSlicer again (5 asks, 5 starts) and never said it couldn't."""
    import time

    from caliper import printing

    calls, _ = _failing(monkeypatch, lambda: {"hours": 2.0, "filament_g": 50.0, "usd": 1.0, "trust": "rough",
                                              "from": "walls + infill at rough speeds (the slicer gave no estimate)",
                                              "_retry": True})
    stl = tmp_path / "a.stl"
    stl.write_bytes(b"solid a\nendsolid a\n")
    for _ in range(5):
        got = printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)
        time.sleep(0.1)
    assert len(calls) == 1 and calls[0] == printing.BACKGROUND_TIMEOUT          # once, with the hang's own timeout
    assert got["slicer_failed"] and got["hours"] == 2.0 and not got.get("pending")


def test_a_slice_that_crashes_is_said_and_never_restarted(tmp_path, monkeypatch):
    import time

    from caliper import answers, design_api, making, shop

    from .test_shop import PRINTED, PRINTER

    def boom():
        raise RuntimeError("the STL wouldn't load")

    calls, _ = _failing(monkeypatch, boom)
    shop.write({"hand": ["drill"], "machines": [PRINTER]})
    store = DesignStore.create("a bar", base=str(tmp_path / "designs"))
    store.write_part("bar", PRINTED, intent="a printed bar")
    making.plan(store, "bar", wait=False)
    time.sleep(0.5)
    state = design_api.design_state(store)
    how = next(c for c in answers.part(store, state, "bar") if c["key"] == "make")
    (line,) = [ln for ln in how["lines"] if ln["text"].startswith("Print it in PETG")]
    assert line["text"] == "Print it in PETG: 2 pieces; print time: the slicer couldn't work it out: the STL wouldn't load."
    assert not line.get("working") and line["status"] == "warn"
    now = answers.measured(store, state)
    assert "print.hours" not in now and now["print.unknown"].startswith("print time: the slicer couldn't work it out")
    making.plan(store, "bar", wait=False)
    assert len(calls) == 2                                                       # two pieces, each once


def test_one_slicer_at_a_time(tmp_path, monkeypatch):
    """A three-piece part's slices run in turn, never three PrusaSlicers at once."""
    import time

    from caliper import printing

    calls, most = _failing(monkeypatch, lambda: {"hours": 1.0, "filament_g": 1.0, "usd": 1.0, "trust": "model",
                                                 "from": "PrusaSlicer"})
    for i in range(3):
        stl = tmp_path / f"p{i}.stl"
        stl.write_bytes(f"solid {i}\nendsolid {i}\n".encode())
        printing.estimate(str(stl), "petg", (220, 220, 250), wait=False)
    t = time.time()
    while len(printing._SLICED) < 3 and time.time() - t < 5:
        time.sleep(0.02)
    assert len(calls) == 3 and most[0] == 1


def test_a_same_mtime_rewrite_with_other_text_misses_the_offer(store):
    """An offer is checked against the file's text, not only its path and time: a rewrite in the same tick builds."""
    import os

    wide = _box(dx=60)
    built = sandbox.run_script(wide, {})
    store.write_part("box", wide, intent="wider", built=(wide, {}, built.geometry))
    path = store.script_path("box")
    st = os.stat(path)
    with open(path, "w") as f:
        f.write(_box(dx=90))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))                         # the same mtime, other text
    assert (os.path.abspath(path), os.path.getmtime(path)) in assembly._OFFERED
    got = store.part_geometry("box")
    assert got.solid is not built.geometry.solid
    assert got.require_mesh().bounds[1][0] - got.require_mesh().bounds[0][0] == pytest.approx(90, abs=0.01)
