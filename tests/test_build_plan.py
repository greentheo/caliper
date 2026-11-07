"""CALI-35 (#3b) — a reviewed plan's parts are built one by one, in order, each seeing the skeleton and what's built.

#3a stopped at "Building them one by one, in order, comes next (#3b)". Now Build it on a reviewed plan authors each
part to be made in its build order: its designer gets the skeleton's numbers and the parts already built (world
bounding boxes), a rule between it and a built part fails its round like any failing measurement, and a part that
won't build leaves the ones before it, the reply naming it and why. Stub authors only: no live Claude."""

import copy
import json

import pytest

from caliper import firstrun
from caliper import plan as P
from caliper.design import DesignStore

from .test_plan_live import fake

pytest.importorskip("cadquery")

SAID = "A wind turbine on a 7 ft mast, staked on a plywood base, for a generator I already have."
MAST_TOP = 7 * 304.8
#: The turbine cut down: a base, a mast on it, a hub on the mast, and the generator the person has.
TURBINE = {
    "parts": [
        {"id": "hub", "what": "a printed hub on the mast top", "made": "printed", "mounts_on": ["mast"]},
        {"id": "mast", "what": "a welded 7 ft steel mast", "made": "welded tube", "mounts_on": ["base"]},
        {"id": "base", "what": "a plywood base", "made": "sheet"},
        {"id": "generator", "what": "the generator I already have", "role": "fixed", "mounts_on": ["mast"]},
    ],
    "skeleton": [{"name": "mast_top_z", "value": 7, "unit": "ft", "why": "the mast's top"},
                 {"name": "base_t", "value": 20, "unit": "mm", "why": "the base's thickness"}],
    "mates": [{"between": ["mast", "base"], "kind": "touch"}, {"between": ["hub", "mast"], "kind": "touch"}],
    "rules": [{"id": "mast_height", "expr": "abs(bbox(mast).max_z - mast_top_z) <= 1"}],
}
#: Each part as a box in world coordinates (x, y sizes; z from, z to): the mast stands on the base, the hub on it.
BOXES = {"base": (300, 300, 0, 20), "mast": (50, 50, 20, MAST_TOP), "hub": (80, 80, MAST_TOP, MAST_TOP + 60)}


def box_script(pid, z1=None):
    w, d, z0, top = BOXES[pid]
    z1 = top if z1 is None else z1
    return (f'import cadquery as cq\n\nPARAMS = {{"w": {w}, "d": {d}, "z0": {z0}, "z1": {z1}}}\n\n\n'
            f'def build(params):\n    p = {{**PARAMS, **(params or {{}})}}\n'
            f'    return cq.Workplane().box(p["w"], p["d"], p["z1"] - p["z0"]).translate((0, 0, (p["z0"] + p["z1"]) / 2))\n')


class Stub:
    """A designer that builds each part as its box; ``short`` parts come out 100 mm short first time."""

    def __init__(self, short=(), fails=()):
        self.short, self.fails, self.calls = set(short), set(fails), []

    def __call__(self, spec, feedback, prior):
        self.calls.append((spec.part, spec.intent, feedback))
        if spec.part in self.fails:
            return "def build(params):\n    raise ValueError('the hub won\\'t fit the shaft')\n"
        if spec.part in self.short and feedback is None:
            w, d, z0, top = BOXES[spec.part]
            return box_script(spec.part, top - 100)
        return box_script(spec.part)

    def order(self):
        return list(dict.fromkeys(p for p, _, _ in self.calls))


def _reviewed(tmp_path):
    store = DesignStore.create(SAID, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=Stub(fails={"base", "mast", "hub"}),
                         strength=False)
    assert got["plan"] == "review" and not store.design.parts
    return store


def test_build_it_builds_the_parts_in_order_and_every_interface_holds(tmp_path):
    store = _reviewed(tmp_path)
    stub = Stub()
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=stub, strength=False)
    assert stub.order() == ["base", "mast", "hub"]                       # mounted-on first; the generator is his
    assert got["ok"] and got["plan"] == "built", got
    assert [p.id for p in store.design.parts if p.version] == ["base", "mast", "hub"]
    report, errors = store.evaluate(tolerant=True)
    assert not errors and report.all_pass and not report.waiting, report.said()
    assert {r.id for r in report.results} >= {"mast_height", "plan_mast_base_touch", "plan_hub_mast_touch"}
    reply = got["reply"]
    assert reply.startswith("I built the plan's 3 parts, in order:"), reply
    assert "- the base: built\n" in reply                            # nothing measured on it yet: no mark (#135)
    assert "- the mast: built ✓ (" in reply and "mast_height ✓" in reply and "plan_mast_base_touch ✓" in reply
    assert "- the hub: built ✓ (plan_hub_mast_touch ✓)" in reply
    assert "the generator: yours, not designed" in reply
    assert "The design checks: all design checks pass." in reply
    assert "Not checked yet: the scorecard. Run *Will it work?* next." in reply           # never "all pass" alone
    assert stub.calls and len(stub.calls) <= 3 * 4                                     # the cost said, kept
    assert store.design.plan["status"] == "built"


def test_a_mast_100_mm_short_fails_its_round_naming_the_rule_and_the_retry_fixes_it(tmp_path):
    store = _reviewed(tmp_path)
    stub = Stub(short={"mast"})
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=stub, strength=False)
    fed = [f for p, _, f in stub.calls if p == "mast" and f]
    assert fed and "mast_height" in fed[0] and "abs(bbox(mast).max_z - mast_top_z) <= 1" in fed[0], fed
    assert got["ok"] and store.evaluate(tolerant=True)[0].all_pass


def test_each_designer_sees_the_skeleton_and_what_s_already_built(tmp_path):
    store = _reviewed(tmp_path)
    stub = Stub()
    firstrun.build(store, use_llm=True, client=fake(TURBINE), author=stub, strength=False)
    said = {p: intent for p, intent, _ in stub.calls}
    assert "SKELETON (the numbers the parts share, in mm" in said["base"]
    assert "mast_top_z = 2133.6 mm (7 ft: the mast's top)" in said["base"]
    assert "ALREADY BUILT" not in said["base"]
    hub = said["hub"]
    assert "ALREADY BUILT (world coordinates, mm" in hub
    assert "base: x -150 to 150, y -150 to 150, z 0 to 20" in hub
    assert "mast: x -25 to 25, y -25 to 25, z 20 to 2133.6" in hub
    assert "touch between hub and mast" in hub and "mast_height: abs(bbox(mast).max_z - mast_top_z) <= 1" in hub


def test_a_part_that_won_t_build_leaves_the_ones_before_it_and_says_which_and_why(tmp_path):
    store = _reviewed(tmp_path)
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=Stub(fails={"hub"}), strength=False)
    assert not got["ok"] and got["plan"] == "stopped" and got["part"] == "hub"
    assert [p.id for p in store.design.parts if p.version] == ["base", "mast"]
    assert "I couldn't build the hub" in got["reply"] and "the hub won't fit the shaft" in got["reply"]
    assert "Build it again to retry it" in got["reply"]
    # retried, it goes on from the hub: the base and mast aren't designed again
    stub = Stub()
    again = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=stub, strength=False)
    assert stub.order() == ["hub"] and again["ok"]


# --- #103's review, for when parts get built: nothing that waits reads green --------------------------------------
def test_a_revision_with_a_check_still_waiting_isn_t_a_green_passed_in_its_history(tmp_path):
    from caliper.evaluate import AssertionResult, Report

    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    rep = Report([AssertionResult("a", "x > 0", "pass", 1), AssertionResult("b", "y > 0", "deferred", None)])
    assert rep.all_pass                                              # the authoring loop may finish on it
    store.write_part("box", box_script("base"), intent="a box", report=rep.to_dict())
    h = store.history("box")[-1]
    assert h["result"] == "waiting" and h["said"] == "1 design check pass, 1 not checked yet"


def test_the_chat_says_the_design_measures_green_only_when_every_check_ran():
    from caliper import chat
    from caliper.evaluate import AssertionResult, Report

    waiting = Report([AssertionResult("a", "x > 0", "pass", 1), AssertionResult("b", "y > 0", "deferred", None)])
    green = Report([AssertionResult("a", "x > 0", "pass", 1)])
    assert chat._design_line(waiting) == "The whole design: 1 design check pass, 1 not checked yet."
    assert chat._design_line(green) == "The whole design measures green."
    assert chat._design_line(None) == ""


@pytest.mark.parametrize("expr,why", [
    ("1" + " <= 1" * 2500, "too big to measure"),               # flat: a long chain, not a deep one
    ("2 ** 9 > 0", "a power above"),
    ("'ab' * 3 == 'ababab'", "repeating a string"),
    ("(2 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * "
     "(10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) * "
     "(10 ** 4) * (10 ** 4) * (10 ** 4) * (10 ** 4) > 0", "a number too big"),
])
def test_each_evaluator_guard_alone(expr, why):
    """#103's review: each of the four guards, pinned on its own (the string repeat had no test of its own)."""
    from caliper.evaluate import SafeEvalError, safe_eval

    with pytest.raises(SafeEvalError, match=why):
        safe_eval(expr, {})



# --- #135 review -----------------------------------------------------------------------------------------------------
def _with_generator_rule(tmp_path):
    """The plan with a rule over the generator the person has, kept, and an assumed rule shown to the designer."""
    plan = json.loads(json.dumps(TURBINE))
    plan["rules"] += [{"id": "clear_of_generator", "expr": "min_clearance(hub, generator) >= 5"},
                      {"id": "hub_size", "expr": "bbox(hub).dx <= 100"}]
    store = DesignStore.create(SAID, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=True, client=fake(plan), author=Stub(fails={"base", "mast", "hub"}),
                         strength=False)
    assert "3 parts to make, up to 4 designer tries each (at most 12)" in got["reply"]      # the cost, before Build
    P.keep(store, "clear_of_generator")
    return store, plan


def test_a_rule_over_the_part_you_have_asks_for_its_size_and_ok_stays_false(tmp_path):
    store, plan = _with_generator_rule(tmp_path)
    stub = Stub()
    got = firstrun.build(store, use_llm=True, client=fake(plan), author=stub, strength=False)
    report, _ = store.evaluate(tolerant=True)
    (waits,) = [r for r in report.results if r.id == "clear_of_generator"]
    assert waits.status == "deferred" and waits.detail == "needs the generator's size: say it, or keep it off"
    assert not got["ok"] and "1 not checked yet" in got["reply"]                     # never ok while a rule waits
    hub = next(intent for p, intent, _ in stub.calls if p == "hub")
    assert "YOURS (not designed; build against it as stated):" in hub and "generator: the generator I already have" in hub
    assert "hub_size: bbox(hub).dx <= 100  [assumed: shown, not enforced]" in hub        # the mark the mutant dropped


def test_a_rule_over_a_part_not_built_yet_isn_t_measured_in_the_round(tmp_path):
    """The mast is built before the hub: a rule over both waits, never a false ✗ or · on the mast."""
    plan = json.loads(json.dumps(TURBINE))
    plan["rules"].append({"id": "hub_over_mast", "expr": "bbox(hub).min_z >= bbox(mast).max_z - 1"})
    store = DesignStore.create(SAID, base=str(tmp_path / "designs"))
    firstrun.build(store, use_llm=True, client=fake(plan), author=Stub(fails={"base", "mast", "hub"}), strength=False)
    P.keep(store, "hub_over_mast")
    got = firstrun.build(store, use_llm=True, client=fake(plan), author=Stub(), strength=False)
    mast = next(ln for ln in got["reply"].splitlines() if ln.startswith("- the mast"))
    assert "hub_over_mast" not in mast and mast.startswith("- the mast: built ✓"), mast
    hub = next(ln for ln in got["reply"].splitlines() if ln.startswith("- the hub"))
    assert "hub_over_mast ✓" in hub


def test_the_stop_says_the_reason_never_a_traceback(tmp_path):
    store = _reviewed(tmp_path)
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=Stub(fails={"hub"}), strength=False)
    assert got["reply"].startswith("I couldn't build the hub: the hub won't fit the shaft.")
    assert "Traceback" not in got["reply"] and "/" not in got["reply"].split(".")[0]
    assert any("Traceback" in (e.get("error") or "") for e in store.log() if e.get("action") == "failed")


def test_the_build_s_marks_come_from_the_one_verdict():
    """Merged with #132: a rule that waits is "·", an error a "✗", and the part's mark is its report's verdict."""
    from caliper import build_plan, verdicts

    assert [build_plan._mark(verdicts.check(s)) for s in ("pass", "fail", "deferred", "unknown")] == ["✓", "✗", "·", "·"]
    head = lambda *st: build_plan._mark(verdicts.report({"results": [{"status": s} for s in st]}))   # noqa: E731
    assert head("pass", "pass") == "✓" and head("pass", "deferred") == "·" and head("pass", "error") == "✗"
    assert head("deferred") == "·"                                                # nothing measured yet: never red



def test_the_build_s_own_marks_an_error_is_a_fail_and_a_waiting_rule_a_dot():
    """#135 review: the marks test rebuilt the head with its own lambda, so build()'s head and its error→fail mapping
    went untested. _marks is what build() uses."""
    from types import SimpleNamespace as R

    from caliper import build_plan

    assert build_plan._marks([R(id="a", status="pass"), R(id="b", status="pass")]) == ("a ✓, b ✓", "✓")
    assert build_plan._marks([R(id="a", status="pass"), R(id="b", status="error")]) == ("a ✓, b ✗", "✗")
    assert build_plan._marks([R(id="a", status="fail"), R(id="b", status="deferred")]) == ("a ✗, b ·", "✗")
    assert build_plan._marks([R(id="a", status="pass"), R(id="b", status="deferred")]) == ("a ✓, b ·", "·")
    assert build_plan._marks([]) == ("", "")


def test_a_design_whose_measurement_throws_is_not_checked_never_ok(tmp_path, monkeypatch):
    """#135 review, rule 6: _measure_design returns (None, {"<design>": …}) when evaluate throws, and build() read
    report None as ok."""
    from caliper import chat

    store = _reviewed(tmp_path)
    monkeypatch.setattr(chat, "_measure_design", lambda s: (None, {"<design>": "ValueError: the rotor's mesh broke"}))
    got = firstrun.build(store, use_llm=True, client=fake(TURBINE), author=Stub(), strength=False)
    assert got["plan"] == "built" and got["ok"] is False
    assert "The design checks: not checked: the rotor's mesh broke." in got["reply"]
