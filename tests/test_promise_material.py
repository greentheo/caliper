"""CALI-88 (#64 item 14): what a strength verdict promises is worded for what the part is made of. An all-printed
box's promise began "Real wood varies"."""

import pytest

from caliper import answers
from caliper import construction as C
from caliper.design import DesignStore

PLY = [{"kind": "sheet", "name": "top", "material": "plywood"}, {"kind": "sheet", "name": "side", "material": "plywood"}]
PRINT = [{"kind": "printed", "name": "box", "material": "petg"}]
MIXED = [{"kind": "sheet", "name": "seat", "material": "plywood"}, {"kind": "printed", "name": "sides", "material": "petg"}]
STEEL = [{"kind": "tube", "name": "leg", "material": "steel"}]


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = DesignStore.create("a stool", base=str(tmp_path))
    for pid in ("ply", "print", "mixed", "steel"):
        s.write_part(pid, "def build(params):\n    return None\n", intent="x")
    built = {"ply": PLY, "print": PRINT, "mixed": MIXED, "steel": STEEL}
    monkeypatch.setattr(C, "declared", lambda store, pid, *a, **k: {"construction": built[pid]})
    return s


def test_a_plywood_parts_promise_is_about_wood(store):
    said = answers.promise(store, ["ply"])
    assert said == answers.PROMISE and "Real wood varies" in said and "print" not in said


def test_a_printed_boxs_promise_is_about_the_print(store):
    said = answers.promise(store, ["print"])
    assert "wood" not in said.lower() and "print" in said and said.startswith("A prediction, not a certificate")


def test_the_mixed_stools_promise_names_both(store):
    said = answers.promise(store, ["mixed"])
    assert "Real wood varies" in said and "print" in said
    assert answers.promise(store, ["ply", "print"]) == said          # a design of one of each reads the same
    assert "rough" not in said          # said where a verdict is rough, not here: plywood may govern it (CALI-97)


def test_wood_with_something_else_names_both(store):
    said = answers.promise(store, ["ply", "steel"])
    assert "textbook strengths for the materials" in said and "Real wood varies, and so do the other materials and joints" in said


def test_anything_else_says_the_material(store):
    said = answers.promise(store, ["steel"])
    assert "wood" not in said.lower() and "print" not in said and "material" in said
