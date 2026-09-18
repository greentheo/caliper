"""CALI-28 — the **Design**: the container for "the thing I am building".

Until now Caliper's durable artifacts were a *snapshot of one part* (``runs/run_NNNN/``) and a
hand-written assembly YAML. Neither holds the things a conversation needs to stay coherent across
weeks: the root prompt, the requirements that were clarified once and shouldn't be re-asked, which
parts exist and why, and — per part — **the history of feedback and what it measured**.

A Design is that container (spec ``specs/caliper-conversational-spec.md`` §3)::

    designs/<slug>/
      design.yaml          # root prompt, requirements, units, machine, part index (provenance)
      assembly.yaml        # parts + mates + asserts — the EXISTING assembly.py format, unchanged
      log.jsonl            # design-level conversation (append-only)
      parts/<id>/
        part.py            # current geometry source (CadQuery, world coords)
        spec.yaml          # this part's parameters + assertions
        history.jsonl      # append-only: feedback -> change -> measurement -> accepted?
        versions/vNNN/     # part.py + spec.yaml + report.json snapshot of every revision

Three choices worth stating, because they're what keep this from becoming a second code path:

- **``assembly.yaml`` is the existing format.** A Design is an assembly *plus provenance*, so
  :func:`~caliper.assembly.evaluate_assembly`, ``caliper assemble`` and ``insert`` work against a
  design untouched. Part sources are written relative to the design root (``parts/<id>/part.py``),
  which :func:`~caliper.assembly._resolve_source` already handles.
- **A single-part design is a one-part assembly.** No special case — which is what makes it safe to
  prove the conversation on one part and grow into whole machines without a rewrite.
- **Append-only, snapshot every revision.** The same rhythm as ``pm/LOG.md``: nothing is overwritten
  in place, every prior state is recoverable, and the history *is* the artifact.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Literal, Optional

import yaml
from pydantic import Field

from .assembly import Assembly, Part
from .spec import Spec, _Base

DESIGNS_DIR_ENV = "CALIPER_DESIGNS"
_DEFAULT_DESIGNS_DIR = "designs"

_SLUG_OK = re.compile(r"[^a-z0-9]+")
_ID_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def designs_dir() -> str:
    """Where designs live. ``CALIPER_DESIGNS`` overrides the default ``designs/``."""
    return os.environ.get(DESIGNS_DIR_ENV) or _DEFAULT_DESIGNS_DIR


def slugify(text: str, fallback: str = "design") -> str:
    """A filesystem-safe slug from free text ('A 3D Printer Gantry!' -> 'a-3d-printer-gantry')."""
    s = _SLUG_OK.sub("-", (text or "").strip().lower()).strip("-")
    s = "-".join(s.split("-")[:6])  # keep directory names readable
    return s[:48] or fallback


def _write_atomic(path: str, text: str) -> None:
    """Write via a temp file + replace, so a crash mid-write can't truncate a design's state."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _append_jsonl(path: str, entry: dict) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn final line must not make the whole history unreadable
    return out


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
class Requirement(_Base):
    """One clarified requirement — asked once during intake, then permanent prompt context.

    ``source`` distinguishes an answer the human gave from an assumption Caliper proceeded on when
    the human said "just build it"; assumptions are worth re-surfacing later, answers are not.
    """

    question: str
    answer: str
    source: Literal["answered", "assumed"] = "answered"
    at: str = Field(default_factory=_now)


class DesignPart(_Base):
    """Provenance for one part. The *geometry* lives in ``assembly.yaml`` + ``parts/<id>/``.

    Kept separate on purpose: ``assembly.yaml`` stays a plain assembly that the existing engine can
    consume, while the design-level index carries the things only a conversation cares about — what
    this part is *for*, how many revisions it has had, and where it came from.
    """

    id: str
    intent: str = ""
    version: int = 0
    origin: Literal["authored", "adopted", "imported"] = "authored"
    created: str = Field(default_factory=_now)
    updated: str = Field(default_factory=_now)


class Design(_Base):
    """The root record: what we're building, what was clarified, and which parts exist."""

    slug: str
    name: str
    prompt: str = ""
    units: str = "mm"
    machine: Optional[str] = None
    requirements: list[Requirement] = Field(default_factory=list)
    parts: list[DesignPart] = Field(default_factory=list)
    created: str = Field(default_factory=_now)
    updated: str = Field(default_factory=_now)

    # --- (de)serialization (mirrors Spec/Assembly) -------------------------
    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "Design":
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, text: str) -> "Design":
        return cls.from_dict(yaml.safe_load(text))

    @classmethod
    def from_json(cls, text: str) -> "Design":
        return cls.from_dict(json.loads(text))

    def part(self, part_id: str) -> Optional[DesignPart]:
        return next((p for p in self.parts if p.id == part_id), None)


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------
class DesignStore:
    """The on-disk home of one design — and the only thing that writes inside it.

    Every geometry write goes through :meth:`write_part`, which snapshots a new version, updates both
    records (design index + assembly), and appends history in one step. That's deliberate: it's what
    guarantees the history can't drift out of sync with the geometry it describes.
    """

    def __init__(self, root: str, design: Design, assembly: Assembly):
        self.root = os.path.abspath(root)
        self.design = design
        self.assembly = assembly

    # --- paths -------------------------------------------------------------
    @property
    def design_path(self) -> str:
        return os.path.join(self.root, "design.yaml")

    @property
    def assembly_path(self) -> str:
        return os.path.join(self.root, "assembly.yaml")

    @property
    def log_path(self) -> str:
        return os.path.join(self.root, "log.jsonl")

    def part_dir(self, part_id: str) -> str:
        return os.path.join(self.root, "parts", part_id)

    def script_path(self, part_id: str) -> str:
        return os.path.join(self.part_dir(part_id), "part.py")

    def spec_path(self, part_id: str) -> str:
        return os.path.join(self.part_dir(part_id), "spec.yaml")

    def history_path(self, part_id: str) -> str:
        return os.path.join(self.part_dir(part_id), "history.jsonl")

    def version_dir(self, part_id: str, version: int) -> str:
        return os.path.join(self.part_dir(part_id), "versions", f"v{version:03d}")

    # --- lifecycle ---------------------------------------------------------
    @classmethod
    def create(cls, prompt: str, name: Optional[str] = None, slug: Optional[str] = None,
               base: Optional[str] = None, units: str = "mm",
               machine: Optional[str] = None) -> "DesignStore":
        """Start a new design from its root prompt. Slug collisions get a deterministic ``-2`` suffix."""
        base = base or designs_dir()
        name = name or (prompt.strip().splitlines()[0][:60] if prompt.strip() else "untitled design")
        slug = slugify(slug or name)
        os.makedirs(base, exist_ok=True)
        unique, n = slug, 1
        while os.path.exists(os.path.join(base, unique)):
            n += 1
            unique = f"{slug}-{n}"
        root = os.path.join(base, unique)
        os.makedirs(os.path.join(root, "parts"), exist_ok=True)
        design = Design(slug=unique, name=name, prompt=prompt, units=units, machine=machine)
        assembly = Assembly(name=unique, intent=prompt)
        store = cls(root, design, assembly)
        store.save()
        store.append_log({"kind": "created", "prompt": prompt})
        return store

    @classmethod
    def load(cls, slug_or_path: str, base: Optional[str] = None) -> "DesignStore":
        """Load by slug (under the designs dir) or by an explicit design directory path."""
        root = slug_or_path
        if not os.path.isdir(root):
            root = os.path.join(base or designs_dir(), slug_or_path)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"no design at {slug_or_path!r}")
        with open(os.path.join(root, "design.yaml")) as f:
            design = Design.from_yaml(f.read())
        assembly = Assembly.load(os.path.join(root, "assembly.yaml"))
        return cls(root, design, assembly)

    @classmethod
    def list_designs(cls, base: Optional[str] = None) -> list[dict]:
        """Summarise every design under ``base`` (newest first). Unreadable dirs are skipped, not fatal."""
        base = base or designs_dir()
        out = []
        if not os.path.isdir(base):
            return out
        for entry in sorted(os.listdir(base)):
            path = os.path.join(base, entry)
            if not os.path.isdir(path) or not os.path.exists(os.path.join(path, "design.yaml")):
                continue
            try:
                store = cls.load(path)
            except Exception:
                continue
            out.append({"slug": store.design.slug, "name": store.design.name,
                        "prompt": store.design.prompt, "parts": len(store.design.parts),
                        "updated": store.design.updated})
        return sorted(out, key=lambda d: d["updated"], reverse=True)

    def save(self) -> "DesignStore":
        self.design.updated = _now()
        os.makedirs(self.root, exist_ok=True)
        _write_atomic(self.design_path, self.design.to_yaml())
        _write_atomic(self.assembly_path, self.assembly.to_yaml())
        return self

    # --- requirements ------------------------------------------------------
    def add_requirement(self, question: str, answer: str,
                        source: str = "answered") -> Requirement:
        """Record a clarified requirement. Re-answering the same question updates it in place."""
        existing = next((r for r in self.design.requirements if r.question == question), None)
        if existing is not None:
            existing.answer, existing.source, existing.at = answer, source, _now()
            self.save()
            return existing
        req = Requirement(question=question, answer=answer, source=source)
        self.design.requirements.append(req)
        self.save()
        return req

    # --- parts -------------------------------------------------------------
    def write_part(self, part_id: str, script: str, *, intent: Optional[str] = None,
                   spec: Optional[Spec] = None, report: Optional[dict] = None,
                   feedback: Optional[str] = None, action: str = "author",
                   measured: Optional[dict] = None, extra: Optional[dict] = None) -> int:
        """Write a new revision of a part: snapshot, index, assembly entry, history — atomically-ish.

        Returns the new version number. The canonical ``part.py`` is what the assembly builds; the
        ``versions/vNNN/`` copy is the recoverable record of this exact revision.
        """
        if not _ID_OK.match(part_id):
            raise ValueError(f"part id {part_id!r} must be a valid identifier (letters/digits/_)")

        entry = self.design.part(part_id)
        version = (entry.version if entry else 0) + 1
        pdir = self.part_dir(part_id)
        os.makedirs(pdir, exist_ok=True)

        _write_atomic(self.script_path(part_id), script)
        if spec is not None:
            _write_atomic(self.spec_path(part_id), spec.to_yaml())

        # snapshot this revision before anything else can overwrite it
        vdir = self.version_dir(part_id, version)
        os.makedirs(vdir, exist_ok=True)
        _write_atomic(os.path.join(vdir, "part.py"), script)
        if spec is not None:
            _write_atomic(os.path.join(vdir, "spec.yaml"), spec.to_yaml())
        if report is not None:
            _write_atomic(os.path.join(vdir, "report.json"), json.dumps(report, indent=2, default=str))

        # the assembly's cache keys on (path, mtime); a same-tick rewrite could otherwise serve stale
        # geometry to the very re-measure that's meant to prove the change landed.
        _invalidate_build_cache(self.script_path(part_id))

        if entry is None:
            entry = DesignPart(id=part_id, intent=intent or "", version=version)
            self.design.parts.append(entry)
        else:
            entry.version = version
            entry.updated = _now()
            if intent:
                entry.intent = intent

        if not any(p.id == part_id for p in self.assembly.parts):
            self.assembly.parts.append(
                Part(id=part_id, source=os.path.join("parts", part_id, "part.py"))
            )
        self.save()

        self.append_history(part_id, {
            "kind": "revision", "action": action, "version": version,
            **({"feedback": feedback} if feedback else {}),
            **({"intent": intent} if intent else {}),
            **({"measured": measured} if measured else {}),
            **({"result": ("all_pass" if report.get("all_pass") else "fail")} if report else {}),
            **(extra or {}),
        })
        return version

    def adopt_run(self, run_dir: str, part_id: str, intent: str = "") -> int:
        """Bring an existing ``runs/run_NNNN/`` into this design as a part.

        An authored run has a ``part.py`` we can keep revising, so it's copied in and becomes a normal
        design part. A template run has only geometry, so the assembly references the run directory
        directly (``_resolve_source`` loads its ``part.stl``) and it's marked ``imported`` — honest
        about the fact that there's no script to revise.
        """
        run_dir = os.path.abspath(run_dir)
        script = os.path.join(run_dir, "part.py")
        if os.path.exists(script):
            with open(script) as f:
                text = f.read()
            spec = None
            spec_path = os.path.join(run_dir, "spec.yaml")
            if os.path.exists(spec_path):
                with open(spec_path) as f:
                    spec = Spec.from_yaml(f.read())
            version = self.write_part(part_id, text, intent=intent, spec=spec,
                                      action="adopt", extra={"run": run_dir})
            e = self.design.part(part_id)
            if e:
                e.origin = "adopted"
            self.save()
            return version

        if not os.path.exists(os.path.join(run_dir, "part.stl")):
            raise FileNotFoundError(f"run {run_dir} has neither part.py nor part.stl")
        os.makedirs(self.part_dir(part_id), exist_ok=True)
        entry = self.design.part(part_id)
        if entry is None:
            entry = DesignPart(id=part_id, intent=intent, version=1, origin="imported")
            self.design.parts.append(entry)
        else:
            entry.version += 1
            entry.origin = "imported"
            entry.updated = _now()
        if not any(p.id == part_id for p in self.assembly.parts):
            self.assembly.parts.append(Part(id=part_id, source=run_dir))
        self.save()
        self.append_history(part_id, {"kind": "revision", "action": "adopt",
                                      "version": entry.version, "run": run_dir,
                                      "note": "imported geometry only (no part.py to revise)"})
        return entry.version

    def read_script(self, part_id: str) -> str:
        with open(self.script_path(part_id)) as f:
            return f.read()

    def read_spec(self, part_id: str) -> Optional[Spec]:
        path = self.spec_path(part_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return Spec.from_yaml(f.read())

    def write_spec(self, part_id: str, spec: Spec) -> None:
        """Update a part's spec **without** cutting a geometry revision (CALI-30 promotes assertions here)."""
        os.makedirs(self.part_dir(part_id), exist_ok=True)
        _write_atomic(self.spec_path(part_id), spec.to_yaml())

    def versions(self, part_id: str) -> list[int]:
        vdir = os.path.join(self.part_dir(part_id), "versions")
        if not os.path.isdir(vdir):
            return []
        out = []
        for name in os.listdir(vdir):
            if name.startswith("v") and name[1:].isdigit():
                out.append(int(name[1:]))
        return sorted(out)

    def restore(self, part_id: str, version: int) -> int:
        """Roll a part back to an earlier snapshot — as a *new* revision, so the rollback is itself history."""
        src = os.path.join(self.version_dir(part_id, version), "part.py")
        if not os.path.exists(src):
            raise FileNotFoundError(f"{part_id} has no version v{version:03d}")
        with open(src) as f:
            script = f.read()
        return self.write_part(part_id, script, action="restore", extra={"restored_from": version})

    # --- history / log -----------------------------------------------------
    def append_history(self, part_id: str, entry: dict) -> dict:
        entry = {"ts": _now(), "part": part_id, **entry}
        return _append_jsonl(self.history_path(part_id), entry)

    def history(self, part_id: str) -> list[dict]:
        return _read_jsonl(self.history_path(part_id))

    def append_log(self, entry: dict) -> dict:
        entry = {"ts": _now(), **entry}
        return _append_jsonl(self.log_path, entry)

    def log(self) -> list[dict]:
        return _read_jsonl(self.log_path)

    # --- evaluation --------------------------------------------------------
    def evaluate(self, tolerant: bool = False):
        """Measure the whole design — every mate and every assembly-level assertion.

        This is the discipline that makes a design more than a folder of parts: a change to one part
        is re-measured against *all* of them, so a clearance broken three parts away gets named.
        """
        from .assembly import evaluate_assembly, load_parts_tolerant

        if not tolerant:
            return evaluate_assembly(self.assembly, base_dir=self.root)
        geoms, errors = load_parts_tolerant(self.assembly, base_dir=self.root)
        return evaluate_assembly(self.assembly, base_dir=self.root, parts=geoms), errors

    # --- prompt context ----------------------------------------------------
    def prompt_context(self, part_id: Optional[str] = None, history_limit: int = 8) -> str:
        """The permanent context a revision should see: what we're building, what was clarified,
        what else exists — and, for a scoped part, its distilled feedback history.

        Deliberately *distilled*, not a transcript: requirements and the enforced assertions carry the
        constraints, the history lines carry the narrative. That's what keeps this bounded as a design
        grows (conversational spec §2).
        """
        lines = [f"DESIGN: {self.design.name}", f"GOAL: {self.design.prompt}",
                 f"UNITS: {self.design.units}"]
        if self.design.machine:
            lines.append(f"MACHINE: {self.design.machine}")
        if self.design.requirements:
            lines.append("\nREQUIREMENTS (clarified with the human — treat as fixed):")
            for r in self.design.requirements:
                mark = "" if r.source == "answered" else "  [assumed]"
                lines.append(f"  - {r.question} -> {r.answer}{mark}")
        if self.design.parts:
            lines.append("\nPARTS IN THIS DESIGN:")
            for p in self.design.parts:
                mark = " <- the part in question" if p.id == part_id else ""
                lines.append(f"  - {p.id}: {p.intent or '(no stated intent)'} (v{p.version}){mark}")
        if self.assembly.mates:
            lines.append("\nMATES (measured relationships that must keep holding):")
            for m in self.assembly.mates:
                lines.append(f"  - {m.id}: {m.kind} between {m.between[0]} and {m.between[1]}")
        if part_id:
            spec = self.read_spec(part_id)
            if spec is not None and spec.assertions:
                lines.append(f"\nENFORCED ON {part_id} (these are tests — do not break them):")
                for a in spec.assertions:
                    lines.append(f"  - {a.id}: {a.expr}")
            hist = [h for h in self.history(part_id) if h.get("feedback")][-history_limit:]
            if hist:
                lines.append(f"\nFEEDBACK HISTORY FOR {part_id} (most recent last):")
                for h in hist:
                    lines.append(f"  - \"{h['feedback']}\" -> v{h.get('version', '?')} "
                                 f"({h.get('result', 'unknown')})")
        return "\n".join(lines)


def _invalidate_build_cache(script_path: str) -> None:
    """Drop any cached build of this script from the assembly part cache."""
    from . import assembly as _asm

    target = os.path.abspath(script_path)
    for key in [k for k in _asm._PART_CACHE if k[0] == target]:
        _asm._PART_CACHE.pop(key, None)
