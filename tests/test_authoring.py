"""CALI-16 — the LLM author + build-error self-heal, with the LLM call injected (no key needed)."""

import pytest

from caliper.authoring import AuthorResult, extract_code, generate_part, params_from_spec
from caliper.spec import Assertion, Spec


def _spec():
    return Spec(
        part="plate",
        intent="a 50x30x4 mounting plate with an 8mm hole",
        parameters={
            "w": {"type": "fixed", "value": 50.0, "unit": "mm"},
            "h": {"type": "fixed", "value": 30.0, "unit": "mm"},
            "t": {"type": "continuous", "min": 2.0, "max": 6.0, "init": 4.0, "unit": "mm"},
            "hole": {"type": "fixed", "value": 8.0, "unit": "mm"},
        },
        assertions=[Assertion(id="one_body", expr="body_count == 1 and is_watertight")],
    )


GOOD = """
def build(params):
    import cadquery as cq
    return cq.Workplane("XY").box(params["w"], params["h"], params["t"]) \
        .faces(">Z").workplane().hole(params["hole"])
"""
BAD = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(1, 1)\n"


def test_params_from_spec_resolves_init_and_value():
    p = params_from_spec(_spec())
    assert p == {"w": 50.0, "h": 30.0, "t": 4.0, "hole": 8.0}


def test_extract_code_strips_fences():
    assert extract_code("```python\ndef build(p):\n    return 1\n```") == "def build(p):\n    return 1"
    assert extract_code("def build(p):\n    return 1") == "def build(p):\n    return 1"


# --- the author/heal loop (needs OCCT to actually build) ------------------
def test_generates_a_part_first_try():
    pytest.importorskip("cadquery")
    res = generate_part(_spec(), author=lambda s, fb, prior: GOOD, max_attempts=3)
    assert res.ok and res.attempts == 1
    assert res.geometry is not None and res.script == GOOD


def test_self_heals_build_error_with_feedback():
    pytest.importorskip("cadquery")
    calls = {"n": 0}

    def flaky_author(spec, feedback, prior):
        calls["n"] += 1
        if calls["n"] == 1:
            assert feedback is None and prior is None       # first attempt: clean
            return BAD
        # retry: the author is handed the prior script + the build traceback
        assert prior == BAD and feedback and "TypeError" in feedback
        return GOOD

    res = generate_part(_spec(), author=flaky_author, max_attempts=3)
    assert res.ok and res.attempts == 2
    assert len(res.history) == 1 and "TypeError" in res.history[0]


def test_gives_up_after_max_attempts():
    pytest.importorskip("cadquery")
    res = generate_part(_spec(), author=lambda s, fb, prior: BAD, max_attempts=2)
    assert not res.ok and res.attempts == 2
    assert res.error and len(res.history) == 2


def test_author_result_dataclass_defaults():
    r = AuthorResult(ok=False)
    assert r.geometry is None and r.attempts == 0 and r.history == []
