"""CALI-1 — the spec schema.

A spec is the executable contract derived from intent (design spec §3). Four parts:
parameters, references, assertions, and a machine stub. It is data — a typed pydantic
model that round-trips losslessly to/from YAML and JSON, and which a human can read and edit.

Parameter *kind* drives who controls it (design spec §3 note):
- ``continuous``  → the numeric optimizer tunes it (min/max/init).
- ``discrete``    → LLM/search picks from ``choices``.
- ``fixed``       → locked ``value``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ContinuousParam(_Base):
    """A continuous parameter the optimizer is allowed to tune within [min, max]."""

    type: Literal["continuous"] = "continuous"
    min: float
    max: float
    init: float
    unit: Optional[str] = None

    @model_validator(mode="after")
    def _check_range(self) -> "ContinuousParam":
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        if not (self.min <= self.init <= self.max):
            raise ValueError(f"init ({self.init}) must lie in [{self.min}, {self.max}]")
        return self


class DiscreteParam(_Base):
    """A discrete choice the LLM/search picks from."""

    type: Literal["discrete"] = "discrete"
    choices: list[Any]
    init: Any
    unit: Optional[str] = None

    @model_validator(mode="after")
    def _check_choice(self) -> "DiscreteParam":
        if not self.choices:
            raise ValueError("discrete parameter needs at least one choice")
        if self.init not in self.choices:
            raise ValueError(f"init ({self.init!r}) must be one of choices {self.choices!r}")
        return self


class FixedParam(_Base):
    """A locked value. Neither the optimizer nor the LLM may change it."""

    type: Literal["fixed"] = "fixed"
    value: Any
    unit: Optional[str] = None


Parameter = Annotated[
    Union[ContinuousParam, DiscreteParam, FixedParam],
    Field(discriminator="type"),
]


class Reference(_Base):
    """An imported fixed part (STL). Mate to it; never intersect it.

    ``position`` (mm) and ``rotation`` (degrees, three.js ``XYZ`` intrinsic euler) place the reference
    in the part's coordinate frame — the part is the datum at the origin, the reference is posed
    relative to it. The fit probes (``interference`` / ``min_clearance``) measure against the *posed*
    geometry, so the pose you set in the viewer is exactly what's measured (CALI-10).
    """

    id: str
    file: str
    role: Literal["fixed"] = "fixed"
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class Assertion(_Base):
    """A predicate over measurement outputs. ``expr`` is evaluated by the evaluator (CALI-3)."""

    id: str
    expr: str


class Spec(_Base):
    """The full spec — the human-confirmed contract the loop drives toward."""

    part: str
    intent: str = ""
    machine: Optional[str] = None  # profile is a stub for the MVP (design spec §7)
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    references: list[Reference] = Field(default_factory=list)
    # YAML/JSON use the key ``assert`` (a Python reserved word); expose it as ``assertions``.
    assertions: list[Assertion] = Field(default_factory=list, alias="assert")

    # --- (de)serialization -------------------------------------------------
    def to_dict(self) -> dict:
        """Plain dict using external field names (``assert``, not ``assertions``)."""
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "Spec":
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, text: str) -> "Spec":
        return cls.from_dict(yaml.safe_load(text))

    @classmethod
    def from_json(cls, text: str) -> "Spec":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str) -> "Spec":
        with open(path) as f:
            text = f.read()
        if path.endswith((".yaml", ".yml")):
            return cls.from_yaml(text)
        return cls.from_json(text)
