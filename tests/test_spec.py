"""CALI-1 — spec schema: round-trip + validation."""

import os

import pytest

from caliper.spec import (
    Assertion,
    ContinuousParam,
    DiscreteParam,
    FixedParam,
    Spec,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "corner_bracket.yaml")


def test_loads_worked_example():
    spec = Spec.load(FIXTURE)
    assert spec.part == "corner_bracket"
    assert spec.machine == "ender3"
    assert len(spec.references) == 2
    assert spec.references[0].id == "ext_a"
    assert spec.references[0].role == "fixed"
    # parameter kinds parse to the right types
    assert isinstance(spec.parameters["wall"], ContinuousParam)
    assert isinstance(spec.parameters["rib_count"], DiscreteParam)
    assert isinstance(spec.parameters["bolt_circle"], FixedParam)
    assert spec.parameters["wall"].init == 3
    assert spec.parameters["bolt_circle"].value == 60
    # assertions land under the `assert` alias
    ids = {a.id for a in spec.assertions}
    assert {"fits_bed", "bolt_pattern", "mass_budget", "one_body"} <= ids


def test_yaml_round_trip_is_lossless():
    spec = Spec.load(FIXTURE)
    again = Spec.from_yaml(spec.to_yaml())
    assert again.to_dict() == spec.to_dict()


def test_json_round_trip_is_lossless():
    spec = Spec.load(FIXTURE)
    again = Spec.from_json(spec.to_json())
    assert again.to_dict() == spec.to_dict()


def test_to_dict_uses_assert_alias():
    spec = Spec(part="p", assertions=[Assertion(id="a", expr="bbox.dx <= 1")])
    d = spec.to_dict()
    assert "assert" in d and "assertions" not in d


def test_continuous_init_out_of_range_rejected():
    with pytest.raises(ValueError):
        ContinuousParam(min=2, max=6, init=10)


def test_continuous_min_gt_max_rejected():
    with pytest.raises(ValueError):
        ContinuousParam(min=6, max=2, init=4)


def test_discrete_init_not_in_choices_rejected():
    with pytest.raises(ValueError):
        DiscreteParam(choices=[0, 1, 2], init=5)


def test_unknown_field_rejected():
    with pytest.raises(ValueError):
        Spec.from_dict({"part": "p", "bogus": 1})
