"""CALI-152 (#213): a safety rounded to two places before it was compared turned a fail into a pass: a true 1.995
against 2 was stored as 2.0 and read "holds". Every producer that makes a verdict now stores its safety cut toward
safe (verdicts.cut), so nothing compared with it afterwards is greener than the check."""

import os
import re

import numpy as np
import pytest

from caliper import verdicts

SRC = os.path.join(os.path.dirname(verdicts.__file__))


@pytest.mark.parametrize("x, got", [(1.995, 1.99), (1.9999, 1.99), (2.0, 2.0), (0.999, 0.99), (3.117, 3.11)])
def test_cut_never_raises_a_number(x, got):
    assert verdicts.cut(x) == got and verdicts.cut(x) <= x


def test_no_producer_rounds_a_safety():
    """Each safety a verdict is made from is cut, not rounded: "safety…": round(…) or safety… = round(…) anywhere is
    a fail that can read as a pass."""
    bad = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".py"):
            continue
        for i, line in enumerate(open(os.path.join(SRC, name)), 1):
            if re.search(r"""["'][a-z_]*safety[a-z_]*["']\s*:\s*round\(|\b[a-z_]*safety[a-z_]*\s*=\s*round\(""", line):
                bad.append(f"{name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_the_plate_checks_number_at_1_995_against_2_fails(tmp_path):
    """The beam check on #106's bench top, with the plywood's strength set so its number is 1.995 across the grain:
    stored 1.99, and the case it governs doesn't hold at 2."""
    from caliper import load_study as L
    from caliper.design import DesignStore

    from .test_beam_width import TOP

    store = DesignStore.create("a bench", base=str(tmp_path))
    store.write_part("bench", TOP, intent="a bench")
    ctx = L.prepare(store, "bench")
    (load,) = ctx["loads"]
    mat = dict(ctx.get("plate_mat") or ctx["mat"])
    first = L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))
    mat["strength"] = 1.995 * first["stress_mpa"] / mat["across"]
    got = L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))
    assert got["safety_across"] == 1.99, got["safety_across"]


def test_tipping_cuts_too():
    from caliper import tipping

    square = np.array([[-100.0, -100.0], [100.0, -100.0], [100.0, 100.0], [-100.0, 100.0]])
    # 1000 N at the middle, 100 mm from the edge it tips about: 100,000 N mm restoring; a push 1 m up giving
    # 100,000 / 1.995 N mm overturning is 1.995 times over, a fail at 2
    got = tipping.moments(square, [(1000.0, np.array([0.0, 0.0]))], 100000.0 / 1.995 / 1000.0, np.array([1.0, 0.0]), 1000.0)
    assert got["safety"] == 1.99, got


# --- #214 review: a behaviour test at 1.995 against 2 for every producer, whatever the spelling inside --------------

def test_the_fea_number_at_1_995_is_1_99():
    from caliper import load_study as L

    assert L.fea_safety(1 / 1.995) == 1.99 and L.fea_safety(1 / 2.0) == 2.0 and L.fea_safety(0.0) is None


def test_a_carve_steps_number_at_1_995_is_1_99_and_doesnt_hold():
    from caliper import carve

    got = carve.step_safety(0.50125)                     # the reviewer's 1/0.50125 = 1.99501: round() said 2.0
    assert got == 1.99 and not got >= 2.0


@pytest.mark.parametrize("raw, safety, holds", [(1.995, 1.99, False), (2.0, 2.0, True), (2.004, 2.0, True)])
def test_a_holed_panels_case_judged_at_1_995_doesnt_hold(raw, safety, holds):
    from caliper import lighten

    case = lighten.judged({"lb": 200.0, "factor": 2.0}, raw, 2.0)
    assert (case["safety"], case["holds"]) == (safety, holds)


def test_a_thinner_sheets_estimate_at_1_995_doesnt_hold():
    from caliper import lighten

    got = lighten.estimate_numbers(1.995, 2.0)
    assert got == {"safety": 1.99, "holds": False}


def test_a_frame_members_number_at_1_995_is_1_99():
    from caliper import frame_study

    assert frame_study.member_safety({"safety_factor": 1.995}) == 1.99


def test_a_frame_designs_number_at_1_995_is_1_99(monkeypatch):
    from types import SimpleNamespace

    from caliper import frame_study

    monkeypatch.setattr(frame_study, "_joints", lambda result, built: [])
    result = SimpleNamespace(mass=10.0, safety=1.995, governing=("bump", 0), deflection=1.0, notes=[], cases={})
    got = frame_study._summary(result, {"mouth": [0.0, 0.0, 0.0], "names": ["rail"], "steel": 1, "wall_checks": []})
    assert got["safety"] == 1.99


def test_a_frames_yield_at_1_995_doesnt_meet_2():
    from caliper import scorecard

    got = scorecard.yield_x({"safety": 1.33, "factor": 1.5})   # 1.995: round() met a goal of 2
    assert got == 1.99 and not got >= 2.0


def test_a_snow_stick_and_panel_at_1_995_are_1_99():
    from caliper import snow

    from .test_snow import ROOF

    w0 = 1.0
    s0 = snow.stick("rafter", "2x4", 3000.0, w0)["safety"]
    raw = snow.M.STICKS["lumber"]["mech"]["strength"] / (w0 * 3000.0 ** 2 / 8.0 / (38.1 * 88.9 ** 2 / 6.0))
    assert snow.stick("rafter", "2x4", 3000.0, w0 * raw / 1.9951)["safety"] == 1.99, s0   # just over: round says 2.0
    q0 = 0.002
    p0 = snow.panel(ROOF, 1000.0, q0)
    # a panel's stresses go with its load: at the load that makes it 1.995 (from an uncut first read), it stores 1.99
    hi = snow.panel(ROOF, 1000.0, q0 / 1000.0)["safety"]
    raw = hi / 1000.0                                     # 1000x the load, uncut to well past two places
    assert snow.panel(ROOF, 1000.0, q0 * raw / 1.9951)["safety"] == 1.99, p0       # just over 1.995: round says 2.0


def test_a_parked_floor_at_1_995_is_1_99(monkeypatch):
    from caliper import parked

    t, span, load, patch = 19.05, 600.0, 1000.0, 100.0
    b = patch + span / 2.0                                  # the strip, as floor_knee works it out
    stress = load * (span / 4.0 - patch / 8.0) / (b * t * t / 6.0)
    real = parked.M.sheet

    def sheet(name):
        got = real(name)
        return {**got, "mech": {**got["mech"], "strength": 1.9951 * stress}}   # just over 1.995: round says 2.0

    monkeypatch.setattr(parked.M, "sheet", sheet)
    assert parked.floor_knee("plywood", 19.05, 600.0, 1000.0, 100.0)["safety"] == 1.99


def test_the_sample_stools_plate_at_1_995_is_1_99(tmp_path):
    from caliper import load_study as L
    from caliper import samples

    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    ctx = L.prepare(store, "step_stool")
    (load,) = ctx["loads"]
    mat = dict(ctx.get("plate_mat") or ctx["mat"])
    first = L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))
    mat["strength"] = 1.995 * first["stress_mpa"] / mat["across"]
    assert L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))["safety_across"] == 1.99


# --- #214 review: a run from before this, sitting on its limit, says check again -----------------------------------

def _old(safety=2.0, cut=False):
    return {"min_safety": 2.0, "spacing_mm": 3.0, "safety": safety, **({"cut": True} if cut else {}),
            "cases": [{"name": "Dad stepping up", "lb": 200, "factor": 2, "safety": safety, "holds": safety >= 2.0,  # producer
                       "fea": {"supported": True, "safety": safety}, "governs": "fea"}]}


def test_an_old_run_on_its_limit_says_check_again_and_a_new_one_holds():
    old, new = _old(), _old(cut=True)
    v = verdicts.case(old, old["cases"][0])
    assert v["kind"] == "recheck" and v["word"] == "check it again" and not v["counts_as_pass"], v
    assert v["why"] == "made before a rounding fix, and it sits exactly on its limit"
    assert verdicts.case(new, new["cases"][0])["kind"] in ("holds", "close")
    assert verdicts.case(_old(2.4), _old(2.4)["cases"][0])["kind"] == "holds"       # off its limit: as it was
    assert verdicts.needs_recheck(old) and not verdicts.needs_recheck(new)


def test_an_old_carve_step_on_its_limit_says_check_again():
    run = {"min_safety": 2.0}
    st = {"index": 1, "safety": 2.0, "holds": True, "whole": 2.5, "whole_holds": True, "saved_g": 10}  # producer
    assert verdicts.carve_step(st, None, run)["kind"] == "recheck"
    assert verdicts.carve_step(st, None, {**run, "cut": True})["counts_as_pass"]


def test_a_build_package_doesnt_reuse_an_old_run_on_its_limit(tmp_path, monkeypatch):
    """#198's reuse of a stored run of the same version goes through the same read: an old one on its limit is
    checked again."""
    from caliper import load_study as L
    from caliper import scorecard
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    store = DesignStore.create("a stool", base=str(tmp_path))
    store.write_part("stool", BOX_STOOL, intent="a stool")
    v = store.design.part("stool").version
    monkeypatch.setattr(L, "list_runs", lambda s, pid=None: [{**_old(), "part": "stool", "version": v, "id": "old"}])
    ran = []
    monkeypatch.setattr(L, "study", lambda s, pid, **k: ran.append(pid) or {**_old(2.4, cut=True), "part": pid,
                                                                             "version": v, "id": "new"})
    try:
        scorecard._compute(store)
    except Exception:  # noqa: BLE001 — the rest of the scorecard isn't what's tested here
        pass
    assert ran == ["stool"]


# --- #214 review, round 2: every reader that gives a ✓ asks, and says why -----------------------------------------

def _old_stool(tmp_path):
    """The sample stool with its stored run edited to sit on 2.0, made before the fix (no marker): step-stool-2's."""
    import glob
    import json

    from caliper import load_study as L
    from caliper import samples

    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    (f,) = [p for p in glob.glob(os.path.join(L.runs_dir(store), "**", "*.json"), recursive=True)
            if json.load(open(p)).get("part") == "step_stool"][:1]
    rec = json.load(open(f))
    rec.pop("cut", None)
    rec["safety"] = 2.0
    for c in rec["cases"]:
        c.update({"safety": 2.0, "holds": True})            # producer: an edited old record
        if (c.get("plate") or {}).get("done"):
            c["plate"]["safety_across"] = 2.0
    json.dump(rec, open(f, "w"))
    return store


def test_an_old_run_on_its_limit_never_ticks_the_design_card_and_says_why(tmp_path):
    from caliper import answers, design_api, release, studies
    from caliper import load_study as L

    store = _old_stool(tmp_path)
    state = design_api.design_state(store)
    lines = [ln for c in answers.answers(store, state) for ln in c["lines"] if "Holds Dad" in ln["text"]]
    assert lines and not lines[0]["text"].startswith("✓") and lines[0]["status"] == "warn", lines
    assert "check it again, made before a rounding fix, and it sits exactly on its limit" in lines[0]["text"], lines
    part = [ln["text"] for ln in answers.answers(store, state, "step_stool")[1]["lines"] if ln.get("study") == "load"]
    assert part[0].endswith(": check it again, 2 times over: made before a rounding fix, and it sits exactly on its "
                            "limit."), part
    run = L.list_runs(store, "step_stool")[0]
    head = studies._headline("load", run)[0]
    assert head.startswith("check it again — weakest") and head.endswith(": " + verdicts.UNCUT), head
    assert answers.measured(store, state)["strength.recheck"] == verdicts.UNCUT        # the card's own flag, not only the goal's
    c = {**run["cases"][0], "verdict": verdicts.case(run, run["cases"][0])}
    assert release._safety_cell(c) == ("check it again: made before a rounding fix, and it sits exactly on its limit", "—")


def test_a_goals_own_limit_counts_and_a_breaking_load_within_its_rounding(tmp_path):
    assert verdicts.goal_on_limit(True, "strength.safety", 2.5, 2.5)
    assert not verdicts.goal_on_limit(False, "strength.safety", 2.5, 2.5)       # a new run on its limit is settled
    assert not verdicts.goal_on_limit(True, "strength.safety", 2.6, 2.5)
    assert verdicts.goal_on_limit(True, "strength.breaks_lb", 500, 500)
    assert verdicts.goal_on_limit(True, "strength.breaks_lb", 504.9, 500) and not verdicts.goal_on_limit(True, "strength.breaks_lb", 505, 500)
    assert verdicts.goal(True, recheck=verdicts.UNCUT)["kind"] == "recheck"
    assert verdicts.goal(False, recheck=verdicts.UNCUT)["kind"] == "fails"               # a ✗ stays a ✗


@pytest.mark.parametrize("x, got", [(496.0, 490.0), (500.0, 500.0), (509.9, 500.0), (1240.0, 1240.0)])
def test_a_breaking_load_is_cut_to_the_10_lb_below(x, got):
    assert verdicts.cut_lb(x) == got
