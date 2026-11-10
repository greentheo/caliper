"""CALI-122 (#137) — the reviewer's pre-flight of Theo's bar stool: what its cards said wrong, one test each.

1. Its own locked rule failed (0.25 mm webs against ``min_wall >= 3.0 - 0.15``) and no card said so.
2. The strength answer didn't say where it fails, and its "seat top" was a mislabel: the hot voxel was in the printed
   cone's webs, named after the nearest wood (the foreman's correction on #137).
3. Carve was offered and run on a part that fails as drawn.
4. 9.5 minutes of a carve showed no time.
5. The weight goal never showed its 10 lb cap.
7. A disc resting on a ring got "no plate check: only 16 of its 16 edges rest", where Roark gives one.
"""

import json
import math
import os

import numpy as np
import pytest

from caliper import answers, carve, design_api, lighten, load_study, part_rules
from caliper.design import DesignStore
from caliper.spec import Assertion, Spec

from .test_carve_click import _page, _run
from .test_resolved import SPOOL, TUBE

pytest.importorskip("cadquery")

WALL_RULE = Assertion(id="shell_wall_thickness", expr="min_wall >= 3.0 - 0.15")     # the bar stool's, locked


def _with_rule(tmp_path, src=SPOOL, units="mm"):
    store = DesignStore.create("a printed spool", base=str(tmp_path / "designs"))
    store.design.display_units = units
    store.save()
    store.write_part("spool", src, intent="a printed spool",
                     spec=Spec(part="spool", intent="a printed spool", assertions=[WALL_RULE]))
    return store


# --- 1. its own rules, measured, with their verdicts ----------------------------------------------------------------

def test_a_broken_rule_of_its_own_leads_will_it_work(tmp_path):
    store = _with_rule(tmp_path)
    (r,) = part_rules.measured(store, "spool")
    assert r["status"] == "fail" and r["verdict"]["kind"] == "fails" and r["actual"] == pytest.approx(0.6, abs=0.05)
    assert r["said"].startswith("shell_wall_thickness: its thinnest walls are 0.") and "around z 2" in r["said"]
    assert r["said"].endswith("; it says at least 2.85 mm")
    state = design_api.design_state(store)
    assert state["parts"][0]["rules"][0]["verdict"]["kind"] == "fails"            # the page's rules list has it
    work = next(c for c in answers.part(store, state, "spool") if c["key"] == "work")
    assert work["lines"][0]["text"] == f"✗ Breaks its rule {r['said']}." and work["lines"][0]["status"] == "bad"
    design = next(c for c in answers.design(store, state) if c["key"] == "work")
    assert design["lines"][0]["text"] == work["lines"][0]["text"]                 # and the design's answer leads with it


def test_a_rule_it_keeps_holds_and_isn_t_said_as_broken(tmp_path):
    store = _with_rule(tmp_path, TUBE.replace('"wall": 4.0', '"wall": 4.0'))
    (r,) = part_rules.measured(store, "spool")
    assert r["verdict"]["kind"] == "holds"
    work = next(c for c in answers.part(store, design_api.design_state(store), "spool") if c["key"] == "work")
    assert not any(ln.get("study") == "rule" for ln in work["lines"])


def test_the_page_marks_each_rule_and_says_what_it_measured():
    rule = {"id": "shell_wall_thickness", "expr": "min_wall >= 3.0 - 0.15", "status": "fail",
            "said": "shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least 2.85 mm",
            "verdict": {"kind": "fails", "status": "bad", "word": "doesn't hold"}}
    ok = {**rule, "status": "pass", "verdict": {"kind": "holds", "status": "ok", "word": "holds"}}
    out = _run(_page(["ruleItem", "partChecks"], consts=["esc", "verdictTone", "verdictBadge"], extra=(
        f"out = [ruleItem({json.dumps(rule)}), ruleItem({json.dumps(ok)}), "
        f"partChecks({{parts: [{{rules: [{json.dumps(rule)}, {{id: 'x', expr: 'y'}}]}}]}})];")))
    assert "badge bad" in out[0] and "doesn&#39;t hold" in out[0] or "doesn't hold" in out[0]
    assert "its walls are 0.25 mm around z 16.1 in" in out[0]
    assert "badge ok" in out[1] and "its walls" not in out[1]                       # what it measured: only off a hold
    assert [r["id"] for r in out[2]["results"]] == ["shell_wall_thickness"]       # measured rules only


# --- 2. where it fails, and how sure ---------------------------------------------------------------------------------

def _run_rec(fea, **kw):
    return {"spacing_mm": 4.6, "min_safety": 2, "thinnest_mm": 0.25, "thinnest_where": {"at": [108.7, -129.8, 409.0]},
            "too_thin": True, "across": 0.054, "resolved": False, **kw,
            "cases": [{"name": "250 lb person seated", "lb": 250, "factor": 1.5, "safety": 0.53, "holds": False,
                       "governs": "fea", "fea": fea}]}


def test_a_fail_among_walls_the_voxels_can_t_see_says_where_and_how_sure():
    run = _run_rec({"at": [-46.0, 165.7, 389.0], "in": "cone", "wall_mm": 0.25, "safety": 0.53})
    text = answers._case_line("i_want", run, run["cases"][0], None, False, True)["text"]
    assert text == ("Doesn't hold 250 lb person seated: only 0.5 times over, and it needs 2. Its worst stress, in one "
                    "run at 4.6 mm voxels, is in the cone around z 15.3 in, where its wall is 0.25 mm, too thin for the "
                    "voxels to see: the fail may be the model's. A hand check or a printed test piece is the way to know.")


def test_a_fail_where_the_voxels_see_the_wall_says_the_thin_walls_apart():
    run = _run_rec({"at": [0.0, 0.0, 717.0], "in": "seat top", "wall_mm": 19.05, "safety": 0.53})
    text = answers._case_line("i_want", run, run["cases"][0], None, False, True)["text"]
    assert text.endswith("Its worst stress is in the seat top around z 28.2 in. Separately, its thinnest walls, "
                         "0.25 mm around z 16.1 in, are too thin for the voxels to see.")
    assert "the fail may be the model's" not in text


def test_an_older_run_without_its_wall_keeps_the_old_words():
    """An older run's ``in`` named the nearest wood even for a printed hot spot: it isn't repeated."""
    run = _run_rec({"at": [-46.0, 165.7, 389.0], "in": "seat top", "safety": 0.53})
    text = answers._case_line("i_want", run, run["cases"][0], None, False, True)["text"]
    assert "seat top" not in text and "the voxels can't see its thinnest walls, 0.25 mm around z 16.1 in" in text


def test_a_hot_voxel_in_the_printed_part_isn_t_named_after_the_nearest_wood():
    seat = {"name": "seat top", "kind": "stick", "a": np.array([0.0, 0.0, 717.0]), "b": np.array([1.0, 0.0, 717.0]),
            "half": 10.0}
    far = np.array([-46.0, 165.7, 389.0])
    assert load_study._nearest_piece(far, [seat]) == "seat top"                   # as it was
    assert load_study._nearest_piece(far, [seat], within=4.6, otherwise="cone") == "cone"
    assert load_study._nearest_piece(np.array([0.5, 0.0, 720.0]), [seat], within=4.6, otherwise="cone") == "seat top"


# --- 3. no carve, no lightening, on a part that fails as drawn --------------------------------------------------------

def _failed_check(store, pid):
    run = os.path.join(load_study.runs_dir(store), "20261106-000000-test")
    os.makedirs(run)
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({"id": "t", "part": pid, "version": store.design.part(pid).version, "created": 1.0,
                   "min_safety": 2, "safety": 0.53, "holds": False, "spacing_mm": 3.0, "thinnest_mm": 4.0,
                   "across": 1.333,                    # 3 mm voxels across a 4 mm wall: coarse (#139 review item 7)
                   "cases": [{"name": "a foot", "safety": 0.53, "holds": False, "governs": "fea",
                              "fea": {"at": [0, 0, 70.0], "in": "tube", "wall_mm": 4.0, "safety": 0.53}}]}, f)


def test_carve_and_lighten_refuse_a_part_that_already_fails(tmp_path):
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    _failed_check(store, "tube")
    with pytest.raises(ValueError) as e:
        carve.study(store, "tube", stations=2)
    assert str(e.value) == ("Can't carve it: its check says it fails (0.5 times over, a coarse run: the fail may be "
                            "the model's; in the tube around z 70 mm): make it hold first, then carve.")
    assert carve.list_runs(store) == []
    with pytest.raises(ValueError, match="^Can.t lighten it: its check says it fails .*a coarse run"):
        lighten.study(store, "tube")


def test_the_page_doesn_t_offer_carve_on_a_part_that_fails():
    from .test_wording import _checked

    check = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "safety": 0.53, "min_safety": 2, "thinnest_mm": 19.0,
             "cases": [{"name": "sitting", "safety": 0.53, "holds": False, "governs": "plate"}]}
    got = load_study.blocked(_checked([check]), "stool")
    out = _run(_page(["carveBlocked"], extra=f"out = carveBlocked({{id: 'stool', version: 7, blocked: {json.dumps(got)}}});"))
    assert out == "it already fails (0.5 times over): make it hold first, then carve"


# --- 4. a carve's time, from its start ---------------------------------------------------------------------------------

def test_the_carve_panel_says_how_long_it_has_run():
    out = _run(_page(["carveProgress"], consts=["esc", "minutesText", "ran"], extra=(
        "const carveKey = (pid) => pid; const S = {carveJob: {stool: {text: 'carving the printed PETG in 7 steps (as drawn, then 6 carved)', "
        "progress: 0.1, t0: Date.now() - 6 * 60000, job: 'j'}}};\nout = carveProgress('stool');")))
    assert "carving the printed PETG in 7 steps (as drawn, then 6 carved) · running for 6 min" in out


# --- 5. a goal's own limit, beside its number -------------------------------------------------------------------------

def test_a_goal_says_its_cap():
    cap = {"metric": "weight.total_lb", "op": "<=", "limit": 10}
    assert answers._against(cap, True) == ", over its 10 lb cap"
    assert answers._against(cap, False) == ", within its 10 lb cap"
    assert answers._against({"metric": "cost.usd", "op": ">=", "limit": 3}, True) == ", short of the $3 it needs"
    # unstubbed: goalLimit with the page's own helpers only (#139 review: a stub hid "num is not defined")
    out = _run(_page(["scoreNum"], consts=["esc", "goalLimit"], extra=(
        "out = [goalLimit({op: '<=', limit: 10, unit: 'lb'}), goalLimit({op: '>=', limit: 2, unit: '×'}), goalLimit({}),"
        " goalLimit({op: '<=', limit: 145, unit: '$'})];")))
    assert out == [" (cap 10 lb)", " (needs 2 ×)", "", " (cap $145)"]


# --- 7. a disc on a ring gets its own plate check ---------------------------------------------------------------------

def test_the_round_plate_is_roark_s_and_the_foreman_s_hand_check():
    """The foreman's hand check of the bar stool's seat: 1,668 N on a 4 in pad, 3/4 in ply, on a ring of r 130 mm:
    about 4.5 MPa. Roark case 16: 3W/(2πt²)·[(1+ν)ln(a/r0) + 1 − (1−ν)r0²/(4a²)]."""
    r0 = math.sqrt((4 * 25.4) ** 2 / math.pi)
    got = load_study.ring_plate(130.0, 19.05, 1668.0, (4 * 25.4) ** 2, 8000)
    hand = 3 * 1668 / (2 * math.pi * 19.05 ** 2) * (1.3 * math.log(130 / r0) + 1 - 0.7 * r0 ** 2 / (4 * 130 ** 2))
    assert got["stress_mpa"] == pytest.approx(hand, rel=1e-9) and 4.4 < got["stress_mpa"] < 4.6


def _disc(sides=16, r=142.0, z=736.6):
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    return {"name": "seat top", "kind": "sheet", "thickness": 19.05, "sides": [-1.0],
            "polys": [np.c_[r * np.cos(ang), r * np.sin(ang), np.full(sides, z)]]}


def _ring(lo, hi, top):
    def under(pts, tol=5.0):
        p = np.asarray(pts, float)
        rr = np.hypot(p[:, 0], p[:, 1])
        return (rr >= lo - tol) & (rr <= hi + tol) & (p[:, 2] <= top + tol) & (p[:, 2] >= top - 40)
    return under


def test_a_disc_on_a_ring_gets_a_plate_check_with_the_ring_it_rests_on():
    seat = _disc()
    sit = {"name": "sitting", "force": [0, 0, -1112.1], "factor": 1.5, "lo": [-50.8, -50.8, 734.6],
           "hi": [50.8, 50.8, 736.6]}
    mat = {"strength": 30.0, "across": 0.5, "E": 8000.0}
    pl = load_study.plate_check([seat], sit, mat, 5.0, under=_ring(127, 133, 736.6 - 19.05))
    assert pl["done"] and pl["support"] == "ring" and 264 <= pl["ring_mm"] <= 270
    want = load_study.ring_plate(pl["ring_mm"] / 2, 19.05, 1668.15, 101.6 ** 2, 8000)
    assert pl["stress_mpa"] == pytest.approx(want["stress_mpa"], abs=0.01)
    assert pl["safety_across"] == pytest.approx(30 * 0.5 / want["stress_mpa"], abs=0.01)
    # off its middle, the round-plate check doesn't cover it, and says so
    edge = {**sit, "lo": [-50.8, -130.0, 734.6], "hi": [50.8, -90.0, 736.6]}
    pl = load_study.plate_check([seat], edge, mat, 5.0, under=_ring(127, 133, 736.6 - 19.05))
    assert not pl["done"] and pl["why"].startswith("the load is off its middle")


def test_a_panel_held_all_round_never_reads_only_16_of_its_16():
    hexa = _disc(sides=6)
    sit = {"name": "sitting", "force": [0, 0, -1000.0], "factor": 1.0, "lo": [-20, -20, 734.6], "hi": [20, 20, 736.6]}
    full = lambda pts, tol=5.0: np.ones(len(pts), bool)                           # noqa: E731 — held everywhere
    pl = load_study.plate_check([hexa], sit, {"strength": 30.0, "across": 0.5, "E": 8000.0}, 5.0, under=full)
    assert not pl["done"] and "only 6 of its 6" not in pl["why"]
    assert pl["why"] == ("it's held all round, but its 6-sided outline isn't a rectangle or a disc, which the plate "
                         "check covers, so the FEA is the number for it")


def test_the_page_doesn_t_offer_lighten_on_a_part_that_fails_and_says_why():
    from .test_wording import _checked

    fails = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "safety": 0.53, "min_safety": 2, "thinnest_mm": 19.0,
             "cases": [{"name": "sitting", "safety": 0.53, "holds": False, "governs": "plate"}]}
    thin = {**fails, "safety": 3.0, "cases": [], "too_thin": True,
            "thin_said": "its 0.25 mm walls … check it by hand or with a test piece instead."}
    holds = {**fails, "safety": 3.0, "cases": [{"name": "sitting", "safety": 3.0, "holds": True, "governs": "plate"}]}
    out = []
    for check in (fails, thin, holds):
        got = load_study.blocked(_checked([check]), "stool")
        out.append(_run(_page(["lightenBlocked"], extra=(
            f"out = lightenBlocked({{id: 'stool', version: 7, blocked: {json.dumps(got)}}});"))))
    assert out == ["It already fails (0.5 times over): make it hold first, then lighten it",
                   "Can't lighten it by strength: its 0.25 mm walls … check it by hand or with a test piece instead.", ""]


def test_a_carved_step_that_doesn_t_close_up_is_an_amber_dot_not_a_red_one():
    """The reviewer's nit on #132: a step that holds but doesn't close up (``unchecked``) was drawn red, as a fail."""
    run = {"id": "r", "version": 7, "min_safety": 2, "best": 1, "stations": [
        {"index": 0, "removed": 0.0, "safety": 3.0, "verdict": {"kind": "holds", "status": "ok", "word": "holds"}},
        {"index": 1, "removed": 0.2, "safety": 2.5, "closed": False,
         "verdict": {"kind": "unchecked", "status": "warn", "word": "not checked"}},
        {"index": 2, "removed": 0.4, "safety": 1.2, "verdict": {"kind": "fails", "status": "bad", "word": "doesn't hold"}}]}
    out = _run(_page(["carveChart"], consts=["esc", "verdictTone"], extra=(
        "const S = {station: null}; function sx(v) { return v + 'x'; } function pct(v) { return v; }\n"
        "function carveShare() { return '40%'; }\n"
        f"const html = carveChart({{version: 7}}, {json.dumps(run)});\n"
        "out = [...html.matchAll(/<circle[^>]*data-carve=\"(\\d)\"\\s*class=\"(\\w+)/g)].map((m) => m[2]);")))
    assert out == ["ok", "warn", "bad"]


def test_an_old_run_s_seat_top_label_isn_t_shown_anywhere():
    """The foreman's re-pre-flight on main: Theo's v4 card says "works hardest in seat top", the old label, where the
    peak is in the cone. A piece is named only from a run that recorded the wall there (new runs)."""
    old = {"at": [133.5, 18.4, 706.7], "in": "seat top", "safety": 1.7}
    new = {**old, "in": "cone", "wall_mm": 6.0}
    assert load_study.peak_in(old) is None and load_study.peak_in(new) == "cone"
    out = _run(_page(["peakWhere"], extra=(
        "function len(mm) { return (mm / 25.4).toFixed(1) + ' in'; }\n"
        f"out = [peakWhere({json.dumps(old)}), peakWhere({json.dumps(new)}), peakWhere({{}})];")))
    assert out == ["around 27.8 in up", "in cone", "in the part"]



def test_a_refused_job_reads_without_the_exception_s_name():
    """#139 review: a carve refused by the server arrives as a failed job, and follow() rejected with its raw error, so
    the panel said "⚠ ValueError: Can't carve it…" on main since #136. follow() passes it through plainly()."""
    out = _run(_page(["follow"], consts=["plainly"], extra=(
        "async function api() { return {events: [], status: 'error', error_id: 'e1', "
        "error: \"ValueError: Can't carve it: it already fails (0.5 times over): make it hold first, then carve.\"}; }\n"
        "try { await follow('j1', () => {}); out = 'resolved'; } catch (e) { out = [e.message, e.errorId, e.status]; }")))
    assert out == ["Can't carve it: it already fails (0.5 times over): make it hold first, then carve.", "e1", "error"]


def test_the_score_panel_and_goal_limit_render_together_unstubbed():
    """The blocker as Theo would hit it: scoreView on a card with a numeric goal limit, with no stand-in for num."""
    card = {"created": 1, "versions": {"i_want": 1}, "summary": {"pass": 1, "fail": 1},
            "checks": [{"id": "w", "label": "keeps total weight down", "status": "fail", "value": 13.1, "unit": "lb",
                        "op": "<=", "limit": 10}],
            "objectives": [{"label": "weight", "value": 13.1, "unit": "lb"}], "notes": []}
    design = {"scorecards": [card], "parts": [{"id": "i_want", "version": 7}], "goals": {"checks": []},
              "has_goals": True}
    out = _run(_page(["scoreView", "scoreNum", "asOf", "scoreMark"], consts=["esc", "TRUST", "goalLimit"], extra=(
        f"out = scoreView({json.dumps(design)});")))
    assert "13.1 lb (cap 10 lb)" in out and "(as of v1)" in out           # with #140's stale card


def test_show_the_stress_names_no_old_label():
    src = open(__file__.replace("tests/test_preflight_bar_stool.py", "src/caliper/web/static/design.js")).read()
    assert "MPa ${esc(peakWhere(f))}" in src and "MPa in the ${esc(f.in" not in src



def test_a_coarse_fail_s_refusal_hedges_like_the_strength_line(tmp_path):
    """#139 review item 7: Carve's "it already fails" on a run too coarse to see its walls says the fail may be the
    model's, as the strength line does."""
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    _failed_check(store, "tube")                     # 3 mm voxels across a 4 mm wall: coarse
    said = load_study.already_fails(store, "tube")
    assert said.startswith("its check says it fails (0.5 times over, a coarse run: the fail may be the model's")
    assert said.endswith("): make it hold first")


def test_an_older_run_s_plate_words_are_rebuilt_from_its_numbers():
    """#139 review item 6: Theo's v4 run stored "only 16 of its 16 edges rest on another piece"."""
    old = {"done": False, "piece": "seat top", "edges": 16, "edges_held": 16,
           "why": "only 16 of its 16 edges rest on another piece; the plate check covers a panel held all round, so the "
                  "FEA is the number for it"}
    said = load_study.plate_why(old)
    assert "16 of its 16" not in said and said.startswith("it's held all round, but its 16-sided outline")
    real = {**old, "edges_held": 2, "why": "only 2 of its 4 edges rest on another piece; …"}
    assert load_study.plate_why(real) == real["why"]
