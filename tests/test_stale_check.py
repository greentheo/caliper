"""CALI-229 (#387): a check of an older version isn't "measured wrong", and Make it better says to check it again.

The tester's walk (11-21), the bar stool at v8, its last check of v4:
- Things to fix said "2 measured wrong", one of them "Its strength check is of v4, not this version" with a green
  measured badge;
- Make it better said "Check it holds first", as if it had never been checked.

Now:
- the stale row is out of date, not measured, and #368's counts put it in ``other``;
- Make it better says "Check it again first: its check is of v4";
- the header says each kind apart: "1 measured wrong · 2 of Claude's readings · 1 not measured"."""
import json

import pytest

from .test_carve_click import _page, _run


# --- the page's header ------------------------------------------------------------------------------------------------------
def _said(got):
    return _run(_page(["fixCounts", "fixesSaid"], extra=f"out = fixesSaid(fixCounts({json.dumps(got)}));"))


@pytest.mark.parametrize("counts,want", [
    ({"measured": 1, "readings": 2, "other": 0}, "1 measured wrong · 2 of Claude's readings"),
    ({"measured": 0, "readings": 2, "other": 0}, "2 of Claude's readings"),
    ({"measured": 0, "readings": 0, "other": 1}, "1 not measured"),
    ({"measured": 2, "readings": 0, "other": 1}, "2 measured wrong · 1 not measured")])
def test_the_header_says_each_kind_apart_from_the_server_s_counts(counts, want):
    assert _said({"rows": [{}] * 9, "counts": counts}) == want            # the counts, never the rows' length


def test_a_list_with_no_counts_is_counted_the_same_way():
    rows = [{"id": "stale", "measured": False, "badge": "out of date"}, {"id": "rule:b", "measured": True},
            {"id": "reading:1:a", "measured": False}]
    assert _said({"rows": rows}) == "1 measured wrong · 1 of Claude's readings · 1 not measured"


_FIX = """
const fixMine = () => ({}), fixRow = () => '', fixGo = () => '';
const S = { slug: 's', fixes: {}, design: { parts: [{ id: 'stool', version: 8 }], load_runs: [{ id: 'R1', part: 'stool', version: 8 }] } };
const fixVersion = () => 8;
const loadRuns = (pid) => S.design.load_runs.filter((r) => r.part === pid);
function mark(rows, counts) {
  S.fixes[fixKey('stool')] = { rows, counts, limits: [], v: fixStamp('stool') };
  const x = fixesSection('stool');
  return [x.tone, x.answer];
}
"""


def _mark(rows, counts):
    return _run(_page(["fixesSection", "fixFresh", "fixStamp", "fixChecked", "fixesView", "fixCounts", "fixesSaid"],
                      consts=["esc", "fixKey"], extra=_FIX + f"out = mark({json.dumps(rows)}, {json.dumps(counts)});"))


def test_the_bar_stool_s_out_of_date_check_is_no_warning_and_no_tick():
    """The walk's "2 measured wrong": one measured, one out of date."""
    assert _mark([{"id": "rule:b"}, {"id": "stale", "measured": False}], {"measured": 1, "readings": 0, "other": 1}) == \
        ["warn", "1 measured wrong · 1 not measured"]
    assert _mark([{"id": "stale", "measured": False}], {"measured": 0, "readings": 0, "other": 1}) == ["info", "1 not measured"]


def test_claude_s_readings_alone_are_a_warning_said_as_readings():
    assert _mark([{"id": "reading:1:a", "measured": False}], {"measured": 0, "readings": 1, "other": 0}) == \
        ["warn", "1 of Claude's readings"]


def test_the_stale_row_is_badged_out_of_date_not_measured():
    html = _run(_page(["fixRow", "fixTicked"], consts=["esc", "fixRowKey"], extra="""out = fixRow({ id: 'stale', problem: 'Its strength check is of v4, not this version',
      measured: false, badge: 'out of date', choices: [{ fix: 'Check it again', cost: 'a check, about 1 min' }] }, {});"""))
    assert '<span class="badge">out of date</span>' in html and "badge ok" not in html


# --- the server ---------------------------------------------------------------------------------------------------------------
pytest.importorskip("cadquery")


def test_the_stale_row_is_out_of_date_and_counted_apart(tmp_path):
    from caliper import fixes

    from .test_fix_list import _list
    from .test_load_study import BOX_STOOL
    from .test_make_it_better import _check, _plate, _store

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    store.write_part("stool", BOX_STOOL + "\n# again\n", intent="again")
    got = _list(store)
    (row,) = got["rows"]
    assert row["id"] == "stale" and row["measured"] is False and row["badge"] == "out of date"
    assert got["counts"] == {"measured": 0, "readings": 0, "other": 1}
    assert fixes.counts(got["rows"]) == got["counts"]


def test_make_it_better_says_check_it_again_where_its_check_is_of_an_older_version(tmp_path):
    from .test_load_study import BOX_STOOL
    from .test_make_it_better import _check, _offers, _store

    store = _store(tmp_path, BOX_STOOL, "stool")
    (never,) = _offers(store, "stool")
    assert never["text"] == "Check it holds first: what would make it better comes from that."
    _check(store, "stool", 3.1)
    store.write_part("stool", BOX_STOOL + "\n# again\n", intent="again")
    (line,) = _offers(store, "stool")
    assert line["text"] == "Check it again first: its check is of v1. What would make it better comes from one of this version."
    assert line["button"] == "Check it again" and line["action"] == "load" and line["part"] == "stool"
