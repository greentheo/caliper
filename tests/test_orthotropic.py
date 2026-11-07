"""CALI-116 (#118; rule 6) — plywood's beam width isn't an isotropic slab's.

BS 8110 cl. 3.5.2.2(a)'s effective width, which ``beam()`` uses for a top resting on two edges, is for an isotropic
slab; (b) takes a smaller one where the panel is less stiff across the span than along it. Ply with its face grain
along the span is: (D_across / D_along)^(1/4), about 0.84. With the grain across the span the isotropic width is the
safe side. The verdict already took the grain the wrong way (half strength); the number it told you to cut it for,
"with its face grain running across the gap", read greener. NEEDS ENGINEER CHECK (#42)."""

import pytest

from caliper import load_study

PLY = {"E": 8000.0, "strength": 40.0, "across": 0.5}          # as material() gives plywood: half as strong across
SAME = {"E": 8000.0, "strength": 40.0, "across": 1.0}         # the same both ways (a printed or isotropic top)
#: a sheet much less stiff across its grain than its strength says (E_across given): the grain along governs
SOFT = {"E": 8000.0, "strength": 40.0, "across": 1.0, "E_across": 8000.0 * 0.2}

#: The test stool's top at its front edge (#106): 14 in between its sides, 10 in wide, a 4 in foot 1/2 in in.
EDGE = dict(span=355.6, width=254.0, t=19.05, force=2 * 200 * load_study.LB, footprint=101.6, edge=50.8)


def test_the_factor_is_the_quarter_power_of_the_two_stiffnesses():
    assert load_study.orthotropic(PLY) == pytest.approx(0.5 ** 0.25, abs=1e-3) == pytest.approx(0.841, abs=1e-3)
    assert load_study.orthotropic(SAME) == 1.0
    assert load_study.orthotropic(SOFT) == pytest.approx(0.2 ** 0.25)


def test_grain_along_the_span_carries_on_a_narrower_width_than_across():
    got = load_study.beam(mat=PLY, **EDGE)
    assert got["width_along_mm"] < got["width_mm"]
    assert got["width_along_mm"] == pytest.approx(0.841 * got["width_mm"], rel=0.02)   # (b): smaller, by the factor
    iso = load_study.beam(mat=SAME, **EDGE)
    assert iso["width_along_mm"] == iso["width_mm"] == got["width_mm"]                # isotropic: rule (a) as it was
    # the grain-along number is on the narrower width: less than the isotropic slab said
    assert got["safety"] < iso["safety"]
    assert got["safety"] == pytest.approx(iso["safety"] * got["width_along_mm"] / got["width_mm"], rel=0.01)


def test_in_the_middle_it_narrows_too_but_never_below_the_factor():
    """The middle foot spreads past the panel's width, so the panel caps rule (a); with the factor it's still narrower,
    by less than the factor (#118: the safe side, the whole effective width takes it)."""
    got = load_study.beam(mat=PLY, **{**EDGE, "edge": None})
    assert got["width_mm"] == 254.0
    assert 0.841 * 254.0 <= got["width_along_mm"] < 254.0


def test_with_the_grain_unknown_the_verdict_takes_the_worse_way():
    # ply: across the gap at half strength is still the worse (0.5 < 0.84): the verdict number is unchanged
    ply = load_study.beam(mat=PLY, **EDGE)
    assert ply["safety_across"] == pytest.approx(0.5 * ply["safety"] * ply["width_mm"] / ply["width_along_mm"], rel=0.02)
    assert ply["safety_across"] < ply["safety"]
    # a sheet far softer across its grain than weaker: the narrow width along the span is the worse, and it governs
    soft = load_study.beam(mat=SOFT, **EDGE)
    assert soft["safety_across"] == soft["safety"] < load_study.beam(mat=SAME, **EDGE)["safety"]


def test_by_thickness_says_the_same():
    got = load_study.beam(mat=PLY, **EDGE)
    (now,) = [b for b in got["by_thickness"] if b["thickness_mm"] == pytest.approx(19.05, abs=0.1)]
    assert now["safety"] == got["safety"] and now["safety_across"] == got["safety_across"]


def test_the_why_says_less_of_it_carries_the_load_with_the_grain_along():
    why = load_study.beam(mat=PLY, **EDGE)["why"]
    assert "with the grain along the span it's less stiff across, so less of it carries the load" in why
    assert "less stiff across" not in load_study.beam(mat=SAME, **EDGE)["why"]


def test_the_page_shows_a_beam_as_a_beam():
    """The panel's plate line said "held all round, edges free to turn" for a top resting on two sides."""
    import os
    import re

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    fn = re.search(r"^function loadCase\(.*?^}\n", src, re.S | re.M).group(0)
    assert "pl.as === 'beam'" in fn and "esc(pl.why)" in fn


def test_the_beam_check_s_number_takes_its_colour_and_word_from_its_verdict(tmp_path):
    """#122's merge with #132: the Beam check panel showed its number in plain bold, its own verdict worked out nowhere.
    The server gives the plate or beam check its verdict (its number against the run's need, only where the case is
    settled), and the panel colours it from that."""
    import json
    import os
    import re

    from caliper import design_api, verdicts
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    pytest.importorskip("cadquery")
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box stool")
    beam = {"done": True, "as": "beam", "piece": "top", "safety": 2.6, "safety_across": 1.7, "why": "a top on two sides"}
    case = {"name": "an adult stepping up", "lb": 200, "factor": 2.0, "safety": 1.7, "holds": False, "governs": "plate",
            "fea": {"supported": True, "safety": 3.0}, "plate": beam}
    run = {"id": "20261107-000000-beam", "part": "stool", "version": store.design.part("stool").version, "created": 1.0,
           "min_safety": 2, "safety": 1.7, "holds": False, "spacing_mm": 3.0, "cases": [case]}
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    (shown,) = design_api.design_state(store)["load_runs"]
    pl = shown["cases"][0]["plate"]
    assert pl["verdict"]["kind"] == "fails" and pl["verdict"] == verdicts.meets(1.7, 2)
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    fn = re.search(r"^function loadCase\(.*?^}\n", src, re.S | re.M).group(0)
    assert "const plNum = (n) => `<b style=\"color:var(--${verdictTone(pl.verdict)})\">${sx(n)}" in fn
    assert fn.count("${plNum(pl.safety_across)}") == 3           # the beam, the ring and the rectangle (#139 merged)



def _beam_run(store, *, version=None, thinnest=19.05, spacing=3.0, finer=True):
    beam = {"done": True, "as": "beam", "piece": "top", "safety": 3.4, "safety_across": 3.0,
            "why": "a top on two sides", "deflection_mm": 1.2}
    case = {"name": "an adult stepping up", "lb": 200, "factor": 2.0, "safety": 3.0, "holds": True, "governs": "fea",
            "fea": {"supported": True, "safety": 3.0}, "plate": beam}
    return {"id": "20261107-000001-beam", "part": "stool", "created": 1.0, "min_safety": 2, "safety": 3.0, "holds": True,
            "version": version or store.design.part("stool").version, "spacing_mm": spacing, "thinnest_mm": thinnest,
            "across": round(thinnest / spacing, 3), "resolved": thinnest / spacing >= 4, "cases": [case],
            **({"finer": {"spacing_mm": 1.0, "minutes": 3}} if finer and thinnest / spacing < 4 else {})}


@pytest.mark.parametrize("why", ["coarse", "stale"])
def test_no_green_plate_or_beam_number_on_a_case_that_isn_t_settled(tmp_path, why):
    """#122 review, the survivor: the plate or beam check's 3.0x (against 2x) is settled only where its case is. On a
    case too coarse to see its walls, or of an older version, it reads as its case does, never holds: dropping the
    guard fails this."""
    import json
    import os

    from caliper import design_api, verdicts
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    pytest.importorskip("cadquery")
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box stool")
    if why == "stale":
        run = _beam_run(store, version=store.design.part("stool").version)
        store.write_part("stool", BOX_STOOL + "\n", intent="a box stool")          # a new version: the run is older
    else:
        run = _beam_run(store, thinnest=2.0, spacing=4.0)                          # 0.5 voxels across: not resolved
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    (shown,) = design_api.design_state(store)["load_runs"]
    case = shown["cases"][0]
    assert verdicts.meets(3.0, 2)["kind"] == "holds"                                # unguarded, it would be green
    assert case["verdict"]["kind"] != "holds"
    assert case["plate"]["verdict"]["kind"] == case["verdict"]["kind"]
    assert not case["plate"]["verdict"]["counts_as_pass"] and case["plate"]["verdict"]["status"] != "ok"


def test_the_sag_beside_grain_unknown_is_the_worse_grain_s():
    """#122 review: the sag said beside "with the grain unknown" was the isotropic width's, not the worse grain's."""
    mat = {"strength": 30.0, "across": 0.5, "E": 8000.0}
    got = load_study.beam(300.0, 400.0, 19.05, 1000.0, mat, footprint=100.0)
    t, F, L, E = 19.05, 1000.0, 300.0, 8000.0

    def sag(b, e):
        return F * L ** 3 / (48 * e * b * t ** 3 / 12)

    along = sag(got["width_along_mm"], E)                     # the grain along the span: its own E, a narrower width
    across = sag(got["width_mm"], E * 0.5)                    # across: half as stiff, the whole width
    assert got["deflection_mm"] == pytest.approx(max(along, across), abs=1e-3)
    assert got["deflection_mm"] > sag(got["width_mm"], E)     # never the isotropic sag, which reads stiffer
    for b in got["by_thickness"]:
        if b["thickness_mm"] == 19.05:
            assert b["deflection_mm"] == pytest.approx(got["deflection_mm"], abs=1e-3)



def test_the_real_test_s_prediction_spans_both_grains_unless_one_is_declared(monkeypatch):
    """#122 review: the worse-grain sag is the top of the real test's predicted range. With the grain unknown the
    prediction spans both grains; with it declared ("grain": "along"/"across" on the plate), that grain's sag."""
    from caliper import trials

    mat = {"strength": 30.0, "across": 0.5, "E": 8000.0}
    beam = {**load_study.beam(300.0, 400.0, 19.05, 1000.0, mat, footprint=100.0), "piece": "top"}
    assert beam["deflection_mm"] == max(beam["deflection_along_mm"], beam["deflection_across_mm"])

    def predicted(plate):
        run = {"id": "r", "version": 1, "cases": [{"name": "a foot", "lb": 200, "factor": 2.0, "safety": 3.0,
                                                    "governs": "plate", "breaks_lb": 1200, "plate": plate,
                                                    "fea": {"supported": True, "deflection_mm": 0.1}}]}
        monkeypatch.setattr(trials, "_run", lambda store, pid: run)
        return trials.predict(None, "stool")["per_lb_mm"][1] * 400                # the top of the range, at 400 lb

    assert predicted(beam) == pytest.approx(beam["deflection_mm"], abs=1e-3)                       # unknown: worse
    assert predicted({**beam, "grain": "along"}) == pytest.approx(beam["deflection_along_mm"], abs=1e-3)
    assert predicted({**beam, "grain": "across"}) == pytest.approx(beam["deflection_across_mm"], abs=1e-3)


def test_an_unsettled_plate_number_says_its_word():
    """#122 review: plNum's "(word)" on a number its verdict doesn't settle (not resolved, older version), never on one
    that holds or fails. The line itself, run in node."""
    import os
    import re

    from .test_carve_click import _page, _run

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    line = re.search(r"^\s*const plNum = .*;$", src, re.M).group(0).strip()
    out = _run(_page([], consts=["esc", "verdictTone", "settled"], extra=(
        "function sx(v) { return v + 'x'; }\nlet pl;\n" + line + "\n"
        "pl = {verdict: {kind: 'unresolved', status: 'warn', word: 'not resolved'}}; const a = plNum(3.0);\n"
        "pl = {verdict: {kind: 'holds', status: 'ok', word: 'holds'}}; const b = plNum(3.0);\n"
        "pl = {verdict: {kind: 'fails', status: 'bad', word: \"doesn't hold\"}}; const c = plNum(1.2);\n"
        "out = [a, b, c];")))
    assert out[0] == '<b style="color:var(--warn)">3x (not resolved)</b>'
    assert out[1] == '<b style="color:var(--ok)">3x</b>' and out[2] == '<b style="color:var(--bad)">1.2x</b>'
