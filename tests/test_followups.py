"""CALI-125 (#148) — follow-ups from the 11/07 reviews: a rule whose probe errors reads as a fail (#140's survivor),
and the reply's log line logs its verdict's ``counts_as_pass`` (#135's nit). Stubbed throughout."""

import pytest

from caliper import answers, design_api, part_rules
from caliper.design import DesignStore
from caliper.spec import Assertion, Spec

from .test_preflight_bar_stool import WALL_RULE
from .test_resolved import TUBE

pytest.importorskip("cadquery")


def test_a_rule_whose_probe_errors_on_a_part_that_builds_reads_as_a_fail_with_its_reason(tmp_path):
    """#140's survivor: a part that builds, one rule measured and kept, one whose probe errors. The erroring one is a
    fail with what went wrong, never a pass or a blank (rule 6), and the card leads with it."""
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    broken = Assertion(id="lip_ratio", expr="min_wall / 0 >= 1")
    store.write_part("spool", TUBE, intent="a printed tube",
                     spec=Spec(part="spool", intent="a printed tube", assertions=[WALL_RULE, broken]))
    kept, err = part_rules.measured(store, "spool")
    assert kept["verdict"]["kind"] == "holds"
    assert err["status"] == "error" and err["verdict"]["kind"] == "fails" and not err["verdict"]["counts_as_pass"]
    assert err["said"] == "lip ratio: min_wall / 0 >= 1, not measured: ZeroDivisionError: float division by zero"
    assert part_rules.failing([kept, err]) == [err]
    work = next(c for c in answers.part(store, design_api.design_state(store), "spool") if c["key"] == "work")
    assert work["lines"][0]["text"] == f"✗ Breaks its rule {err['said']}." and work["lines"][0]["status"] == "bad"


# --- #106's two surviving mutants (the reviewer's) -------------------------------------------------------------------

def _older_middle_only(tmp_path, monkeypatch):
    """The reviewer's kid stool, its strength checked with the middle foot only (it holds: a middle-only ✓, stamped on
    its history line), then changed (v2, the same build): the run is now an older version's."""
    from .test_edge_foot import MIXED_CENTRED, _kid

    store, rec = _kid(tmp_path, monkeypatch, MIXED_CENTRED, "middle")
    script = store.read_script("stool")
    store.write_part("stool", script + "\n# v2: the same build\n", intent="kid")
    assert rec["version"] < store.design.part("stool").version
    return store, rec


def test_an_older_middle_only_run_says_so_on_the_design_card_end_to_end(tmp_path, monkeypatch):
    """#106's survivor 1: ``measured`` dropping ``strength.last.edge`` passed. From a real older middle-only run, the
    design card's "last checked on vN" line says it was checked in the middle only."""
    store, rec = _older_middle_only(tmp_path, monkeypatch)
    state = design_api.design_state(store)
    now = answers.measured(store, state)
    assert now["strength.last"]["version"] == rec["version"] and now["strength.last"]["edge"] is True
    (line,) = [ln for ln in answers.held_to(state, now) if "last checked on" in ln["text"]]
    assert ", checked in the middle only · v2 not checked yet." in line["text"] and line["status"] == "warn", line
    assert not line["text"].startswith("✓")


def test_middle_only_falls_back_to_the_part_as_it_is_for_a_run_with_no_stamp(tmp_path, monkeypatch):
    """#106's survivor 2: ``middle_only``'s ``bare_edge`` fallback, for an older run whose history line has no
    ``middle_only`` stamp (written before #106, or one that failed): the part as it is now decides."""
    from caliper import consistency

    from .test_mixed import MIXED

    store, rec = _older_middle_only(tmp_path, monkeypatch)
    (line,) = [h for h in store.history("stool") if h.get("action") == "studied" and h.get("run") == rec["id"]]
    assert line.get("middle_only") is True
    unstamped = [{k: v for k, v in line.items() if k != "middle_only"}]
    assert consistency.middle_only(store, "stool", rec, [line]) is True               # its stamp
    assert consistency.middle_only(store, "stool", rec, unstamped) is True            # the part still has no edge foot
    # the part now with its front-edge foot: the stamp still says what that run was; an unstamped one is judged by it
    store.write_part("stool", MIXED.replace('"lb": 200', '"lb": 60').replace("an adult", "a kid"), intent="kid")
    assert consistency.bare_edge(store, "stool") is None
    assert consistency.middle_only(store, "stool", rec, [line]) is True
    assert consistency.middle_only(store, "stool", rec, unstamped) is False
