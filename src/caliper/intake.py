"""CALI-5 — intake: intent → draft spec, with a clarify gate.

The intake step reads a loose natural-language intent and drafts a :class:`~caliper.spec.Spec`,
formalizing every requirement it can into typed parameters and assertions (design spec §5 step 1).
The hard rule is **ask-don't-assume** (§3, §10): ambiguities are surfaced as questions and the loop
**stops** for human confirmation before any build — intake never invents acceptance criteria silently.

Two paths:
- ``offline`` — a deterministic, network-free template for the corner-bracket family. Parses simple
  cues (size, hole spec, extrusion width, cable) from the intent. This is what tests and the
  ``--no-llm`` demo use, so M0 is reproducible.
- ``llm`` — a Claude call that drafts the spec and proposes clarifying questions. Best-effort; falls
  back to ``offline`` if the SDK/key/network is unavailable so the loop never hard-fails on intake.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_MODEL = os.environ.get("CALIPER_MODEL", "claude-opus-4-8")

from .spec import Assertion, Spec

# M-bolt nominal → clearance hole diameter (mm), close fit.
_M_CLEARANCE = {2: 2.4, 2.5: 2.9, 3: 3.4, 4: 4.5, 5: 5.2, 6: 6.6, 8: 9.0}
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


@dataclass
class IntakeResult:
    spec: Spec
    questions: list[str] = field(default_factory=list)
    source: str = "offline"  # "offline" | "llm"

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.questions)


# ---------------------------------------------------------------------------
# Offline (deterministic) intake — corner-bracket family
# ---------------------------------------------------------------------------
def _parse_size(intent: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm", intent)
    return float(m.group(1)) if m else 60.0


def _parse_extrusion_width(intent: str) -> float:
    # "2020 extrusion" → 20 mm; "3030" → 30; default 20.
    m = re.search(r"\b(\d{2})\1\b", intent.replace(" ", ""))
    if m:
        return float(m.group(1))
    return 20.0


def _parse_holes(intent: str) -> tuple[int, float]:
    """Return (count, diameter) for an 'N [Msize] holes' phrase. Defaults to 4×Ø5.2.

    The count is anchored on the word "holes" (≤2 filler words before it) and limited to a 1–2 digit
    number or a word-number — so an extrusion size like "2020" can't be misread as the hole count.
    """
    count = 4
    cm = re.search(
        r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:[\w-]+\s+){0,2}?holes?\b",
        intent, re.I,
    )
    if cm:
        tok = cm.group(1).lower()
        count = int(tok) if tok.isdigit() else _WORD_NUM.get(tok, 4)
    count = max(1, min(12, count))  # sanity clamp
    mm = re.search(r"\bm(\d+(?:\.\d+)?)\b", intent, re.I)
    nominal = float(mm.group(1)) if mm else 5.0
    diameter = _M_CLEARANCE.get(nominal, round(nominal + 0.2, 1))
    return count, diameter


def offline_draft(intent: str, machine: Optional[str] = None) -> IntakeResult:
    size = _parse_size(intent)
    width = _parse_extrusion_width(intent)
    hole_count, hole_d = _parse_holes(intent)
    wants_cable = bool(re.search(r"cable|wire|bore|pass.?through", intent, re.I))

    parameters = {
        "wall": {"type": "continuous", "min": 2.4, "max": 6, "init": 3, "unit": "mm"},
        "rib_count": {"type": "discrete", "choices": [0, 1, 2], "init": 0},
        "bolt_circle": {"type": "fixed", "value": size, "unit": "mm"},
        # hole geometry is parameterised so refinements (M1) flow through to the mesh, not just the assert
        "hole_d": {"type": "fixed", "value": hole_d, "unit": "mm"},
        "hole_count": {"type": "fixed", "value": hole_count},
    }
    if wants_cable:
        parameters["cable_bore"] = {
            "type": "continuous", "min": 6, "max": 14, "init": 10, "unit": "mm",
        }

    assertions = [
        Assertion(id="fits_bed", expr="bbox.dx <= 220 and bbox.dy <= 220 and bbox.dz <= 250"),
        Assertion(id="walls_printable", expr="min_wall >= 2 * machine.nozzle"),
        Assertion(id="bolt_pattern", expr=f"holes_matching(diameter={hole_d}, count={hole_count})"),
        Assertion(id="mass_budget", expr="mass(density=1.24) <= 80"),
        Assertion(id="one_body", expr="body_count == 1 and is_watertight"),
    ]
    if wants_cable:
        assertions.append(Assertion(id="cable_fits", expr="largest_through_bore >= 8"))

    spec = Spec(
        part="corner_bracket",
        intent=intent,
        machine=machine or "generic",
        parameters=parameters,
        assertions=assertions,
    )

    # Ask-don't-assume: the mass budget / material was inferred, not stated. Confirm before building.
    questions = [
        "I assumed PLA with an 80 g mass budget. What material and max mass should the bracket meet?",
    ]
    return IntakeResult(spec=spec, questions=questions, source="offline")


# ---------------------------------------------------------------------------
# LLM intake — Claude drafts the spec + clarifying questions (best-effort)
# ---------------------------------------------------------------------------
def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply that may be fenced or wrapped in prose.

    Models often answer ```json ...``` or add a sentence before the object; raw ``json.loads`` then
    fails at char 0. Strip code fences, else take the outermost ``{...}``.
    """
    import json
    import re as _re

    t = text.strip()
    fence = _re.search(r"```(?:json)?\s*(.*?)```", t, _re.S)
    if fence:
        t = fence.group(1).strip()
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j > i:
            t = t[i : j + 1]
    return json.loads(t)


_SYSTEM = """You are Caliper's intake step. Convert a loose part request into a Caliper spec.
Formalize every requirement you can into typed parameters and assertion expressions over the
measurement API (bbox, mass(density), min_wall, holes_matching, body_count, is_watertight, ...).
HARD RULE: never invent acceptance criteria. If a requirement (load, material, mass, fit) is
ambiguous or unstated, add a clarifying question instead of guessing.
Output ONLY a raw JSON object (no markdown, no prose):
{"spec": <spec-as-dict-with-`assert`-key>, "questions": [<string>, ...]}."""


def llm_draft(intent: str, machine: Optional[str] = None, client=None, model: Optional[str] = None) -> IntakeResult:
    model = model or DEFAULT_MODEL
    if client is None:
        from anthropic import Anthropic  # lazy; may be absent

        client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[
            {"role": "user", "content": f"machine: {machine or 'generic'}\nintent: {intent}"},
            {"role": "assistant", "content": "{"},  # prefill → forces a JSON object
        ],
    )
    text = "{" + "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = extract_json(text)
    spec = Spec.from_dict(data["spec"])
    return IntakeResult(spec=spec, questions=list(data.get("questions", [])), source="llm")


def draft_spec(
    intent: str,
    machine: Optional[str] = None,
    use_llm: bool = True,
    client=None,
) -> IntakeResult:
    """Draft a spec from intent. Uses Claude when available, else the deterministic offline path."""
    if use_llm:
        try:
            return llm_draft(intent, machine=machine, client=client)
        except Exception as e:  # SDK/key/network unavailable or bad response → deterministic fallback
            if os.environ.get("CALIPER_DEBUG"):
                print(f"[intake] LLM path failed → offline: {type(e).__name__}: {e}", file=sys.stderr)
    return offline_draft(intent, machine=machine)
