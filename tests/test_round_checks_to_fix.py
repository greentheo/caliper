"""CALI-235 (#406) — a check that fails in the designer's round on a built part is a Things to fix row.

Found by #1 slice D's end-to-end camper: a first build doesn't repair every round check, so a part can be written with
one failing (a sheet off its face, a wall beam off its wall, the mattress cut). The What is it? card said it; Things to
fix didn't list it, against Theo's rule that every red flows into Things to fix with a fix and a re-check. Stub designer
only: no live call."""

import pytest

from caliper import chat, consistency, design_api, fixes, fixing
from caliper.design import DesignStore
from caliper.evaluate import AssertionResult

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


def _fails(*rows):
    return lambda store, pid: [AssertionResult(i, "x", "fail", False, None, None, d) for i, d in rows]


@pytest.fixture
def stool(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL, intent="a box step stool")
    return s


def _rows(store):
    return [r for r in fixes.listed(store, design_api.design_state(store), "stool")["rows"] if r["id"].startswith("check:")]


def test_a_true_part_has_no_round_check_rows(stool):
    assert _rows(stool) == []


@pytest.mark.parametrize("check,detail,problem,fix", [
    ("construction_on_its_face", "the top's outline is 19 mm off the solid's face",
     "Its 3D shape and its pieces don't match: the top's outline is 19 mm off the solid's face", None),
    ("shell_in_walls", "wall_left lies in no wall the part is built from (9 of 9 points along it)",
     "wall_left lies in no wall the part is built from (9 of 9 points along it)",
     "Put each wall beam shell() gives in its wall, of that wall's core, thickness and skins"),
    ("keeps_clear", "the outside cuts 100 mm into the mattress", "The outside cuts 100 mm into the mattress",
     "Keep the outside out of what keeps() holds clear: move or shrink the shape, or move the box it keeps"),
])
def test_a_failing_round_check_is_a_row_with_the_card_s_words_and_a_fix(stool, monkeypatch, check, detail, problem, fix):
    monkeypatch.setattr(consistency, "checked", _fails((check, detail)))
    (row,) = _rows(stool)
    assert row["id"] == f"check:{check}" and row["problem"] == problem and row["measured"] is True, row
    assert row["choices"][0]["kind"] == fixes.DESIGNER
    if fix:
        assert row["choices"][0]["fix"] == fix


def test_a_warning_or_a_pass_is_no_row(stool, monkeypatch):
    monkeypatch.setattr(consistency, "checked", lambda store, pid: [
        AssertionResult("loads_edge", "x", "fail", False, None, None, "a top held on two sides…"),     # the edge row's
        AssertionResult("construction_inside", "x", "pass", True, None, None, "")])
    assert _rows(stool) == []


def test_fix_these_on_a_round_check_reads_fixed_when_it_passes_on_the_new_version(stool, monkeypatch):
    calls = {"n": 0}

    def checked(store, pid):
        calls["n"] += 1
        return [] if store.design.part(pid).version > 1 else _fails(("shell_in_walls", "wall_left lies in no wall"))(store, pid)
    monkeypatch.setattr(consistency, "checked", checked)

    def designer(store, pid, message, **kw):
        from caliper.chat import TurnResult

        v = store.write_part(pid, BOX_STOOL + "\n# beams in their walls\n", intent="a box step stool")
        return TurnResult(action="refine", reply="✓ revised", ok=True, part=pid, version=v)
    monkeypatch.setattr(chat, "refine_part", designer)
    got = fixing.apply(stool, "stool", [{"id": "check:shell_in_walls", "choice": 0}], check=False)
    assert [r["status"] for r in got["results"]] == ["fixed"], got["results"]


def test_a_check_a_strength_run_s_row_already_speaks_for_is_not_said_twice(stool, monkeypatch):
    monkeypatch.setattr(consistency, "checked", _fails(("construction_volume", "the solid is 3x its pieces")))
    assert fixes._round_rows(stool, "stool", "the stool", [{"id": "filled"}]) == []
    assert [r["id"] for r in fixes._round_rows(stool, "stool", "the stool", [])] == ["check:construction_volume"]
