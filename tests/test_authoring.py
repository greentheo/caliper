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


# --- CALI-17: the structural-edit loop (heal failing MEASUREMENTS, not just builds) ---------
from caliper import authoring  # noqa: E402

_SMALL = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(20, 20, 4)\n"
_GOOD41 = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(41, 20, 4)\n"


def _width_spec():
    return Spec(
        part="plate", intent="a ~41mm-wide plate",
        parameters={"x": {"type": "fixed", "value": 41.0, "unit": "mm"}},
        assertions=[
            Assertion(id="width", expr="40 <= bbox.dx <= 42"),
            Assertion(id="solid", expr="is_watertight"),
        ],
    )


def test_improve_passes_first_try():
    pytest.importorskip("cadquery")
    res = authoring.improve(_width_spec(), author=lambda s, fb, prior: _GOOD41, max_rounds=3)
    assert res.ok and res.rounds == 1 and res.report.all_pass


def test_improve_heals_a_failing_measurement():
    pytest.importorskip("cadquery")
    calls = {"n": 0}

    def author(spec, feedback, prior):
        calls["n"] += 1
        if calls["n"] == 1:
            assert feedback is None
            return _SMALL                       # builds, but fails the width check (dx=20)
        # the revision is handed the FAILING ASSERTION (id + actual), not a traceback
        assert prior == _SMALL and feedback and "width" in feedback and "actual" in feedback
        return _GOOD41

    res = authoring.improve(_width_spec(), author=author, max_rounds=4)
    assert res.ok and res.rounds == 2 and res.report.all_pass
    assert any(kind == "measurement_fail" for kind, _ in res.history)


def test_improve_heals_build_error_then_measurement():
    pytest.importorskip("cadquery")
    seq = [BAD, _SMALL, _GOOD41]
    i = {"n": 0}

    def author(spec, feedback, prior):
        s = seq[i["n"]]
        i["n"] += 1
        if s is _SMALL:  # came after a build error
            assert feedback and ("error" in feedback.lower() or "build" in feedback.lower())
        return s

    res = authoring.improve(_width_spec(), author=author, max_rounds=5)
    assert res.ok and res.rounds == 3
    kinds = [k for k, _ in res.history]
    assert kinds[0] == "build_error" and "measurement_fail" in kinds


def test_improve_stops_on_oscillation():
    pytest.importorskip("cadquery")
    res = authoring.improve(_width_spec(), author=lambda s, fb, prior: _SMALL, max_rounds=6)
    assert not res.ok
    assert res.report is not None and not res.report.all_pass  # returns the best (last) attempt


# --- CALI-22: author-loop fit & refine (seed the loop with an existing part) ----------------
def test_improve_seed_primes_round_one():
    pytest.importorskip("cadquery")
    seen = {}

    def author(spec, feedback, prior):
        seen["feedback"], seen["prior"] = feedback, prior
        return _GOOD41

    authoring.improve(_width_spec(), author=author, max_rounds=1,
                      seed_script="SEED-SCRIPT", seed_feedback="apply this change")
    assert seen["prior"] == "SEED-SCRIPT" and seen["feedback"] == "apply this change"


def test_refit_authored_drives_part_to_clear_reference(tmp_path):
    pytest.importorskip("cadquery")
    import trimesh

    from caliper.fit import attach_reference

    ref = tmp_path / "ref.stl"
    m = trimesh.creation.box(extents=(20, 20, 20)); m.apply_translation([30, 0, 0]); m.export(str(ref))
    spec = Spec(part="block", parameters={}, assertions=[])
    attach_reference(spec, "ref", str(ref), no_overlap=True)  # → interference(ref) <= 0

    wide = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(60, 20, 4)\n"
    narrow = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(30, 20, 4)\n"
    calls = {"n": 0}

    def author(spec, feedback, prior):
        calls["n"] += 1
        if calls["n"] == 1:                                  # seeded with the part + the fit feedback
            assert prior == wide and feedback and "FIT" in feedback
            return wide                                      # x∈[-30,30] still overlaps the ref → fails
        assert feedback and "interference" in feedback       # fed the failing fit measurement
        return narrow                                        # x∈[-15,15] clears

    res = authoring.refit_authored(spec, wide, max_rounds=4, author=author)
    assert res.ok and res.rounds == 2 and res.report.all_pass


def test_refine_authored_folds_instruction_into_intent():
    pytest.importorskip("cadquery")
    spec = _width_spec()
    res = authoring.refine_authored(spec, _GOOD41, "make it 41mm wide", max_rounds=1,
                                    author=lambda s, fb, prior: _GOOD41)
    assert "make it 41mm wide" in spec.intent  # persists across revision rounds
    assert res.ok and res.report.all_pass
