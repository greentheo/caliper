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
