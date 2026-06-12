"""CALI-5 — intake: deterministic offline drafting + clarify gate + LLM fallback."""

from caliper import intake
from caliper.spec import ContinuousParam, FixedParam


def test_offline_parses_the_mvp_intent():
    res = intake.offline_draft(
        "a 60 mm corner bracket for 2020 extrusion with four M5 holes"
    )
    spec = res.spec
    assert spec.part == "corner_bracket"
    assert isinstance(spec.parameters["bolt_circle"], FixedParam)
    assert spec.parameters["bolt_circle"].value == 60.0
    # four M5 holes → holes_matching(diameter=5.2, count=4)
    bolt = next(a for a in spec.assertions if a.id == "bolt_pattern")
    assert "5.2" in bolt.expr and "count=4" in bolt.expr


def test_offline_no_cable_by_default():
    res = intake.offline_draft("a 60 mm corner bracket with four M5 holes")
    assert "cable_bore" not in res.spec.parameters
    assert all(a.id != "cable_fits" for a in res.spec.assertions)


def test_offline_detects_cable_passthrough():
    res = intake.offline_draft(
        "a 60 mm corner bracket with four M5 holes and a cable pass-through"
    )
    assert isinstance(res.spec.parameters["cable_bore"], ContinuousParam)
    assert any(a.id == "cable_fits" for a in res.spec.assertions)


def test_extrusion_width_parsing():
    res = intake.offline_draft("a 80 mm corner bracket for 3030 extrusion with two M6 holes")
    bolt = next(a for a in res.spec.assertions if a.id == "bolt_pattern")
    assert "count=2" in bolt.expr
    assert "6.6" in bolt.expr  # M6 clearance


def test_clarify_gate_is_active():
    res = intake.offline_draft("a 60 mm bracket")
    assert res.needs_confirmation
    assert any("material" in q or "mass" in q for q in res.questions)


def test_draft_spec_no_llm_uses_offline():
    res = intake.draft_spec("a 60 mm bracket with four M5 holes", use_llm=False)
    assert res.source == "offline"


def test_llm_failure_falls_back_to_offline():
    class Boom:
        class messages:
            @staticmethod
            def create(**_):
                raise RuntimeError("no network")

    res = intake.draft_spec("a 60 mm bracket", use_llm=True, client=Boom())
    assert res.source == "offline"
    assert res.spec.part == "corner_bracket"
