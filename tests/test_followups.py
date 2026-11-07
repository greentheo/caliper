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
    assert err["said"] == "lip_ratio: min_wall / 0 >= 1, not measured: ZeroDivisionError: float division by zero"
    assert part_rules.failing([kept, err]) == [err]
    work = next(c for c in answers.part(store, design_api.design_state(store), "spool") if c["key"] == "work")
    assert work["lines"][0]["text"] == f"✗ Breaks its rule {err['said']}." and work["lines"][0]["status"] == "bad"
