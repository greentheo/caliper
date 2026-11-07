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
