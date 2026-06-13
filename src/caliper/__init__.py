"""Caliper — spec-driven, measurement-grounded generation of manufacturable 3D parts."""

from .assembly import Assembly, Mate, Part
from .spec import (
    Spec,
    Parameter,
    ContinuousParam,
    DiscreteParam,
    FixedParam,
    Reference,
    Assertion,
)

__all__ = [
    "Spec",
    "Parameter",
    "ContinuousParam",
    "DiscreteParam",
    "FixedParam",
    "Reference",
    "Assertion",
    "Assembly",
    "Part",
    "Mate",
]

__version__ = "0.0.1"
