### 2026-09-18 · CALI-28 · The Design object — a container for "the thing I am building"
- **Why (Theo, picking the project back up):** the engine works, but the webapp is a *control panel for
  the engine* — it asks the user to know LLM-vs-offline, run-vs-assembly, "author any part", and which
  two parts to pick before Insert un-greys. Every toggle is an internal seam leaking into the user's
  job. The new direction: the product is a **viewport + a conversation**; you state what you're
  building, click a part, and talk about that part. Written up as **M4** in
  `specs/caliper-conversational-spec.md`, with M5 (decomposition) behind it.
- **Decisions taken up front:** chat-first on a **single part** before decomposition (don't debug a new
  planner and a new UI at once) · the old panel is **demoted to an Advanced drawer**, not deleted (the
  escape hatch matters when the loop misbehaves) · assertion promotion is **proposed and confirmed**,
  never silent.
- **The idea that makes the history worth keeping:** measurable feedback is **promoted into the spec's
  `assert` block**. "The wheel must clear the rail" becomes `min_clearance(rail) >= 1.0` — a test the
  existing evaluator enforces on every later revision. The history then splits cleanly: `history.jsonl`
  holds the narrative, `spec.assert` holds the enforceable residue. That's what keeps prompt context
  bounded as a design grows, instead of stuffing an ever-growing transcript into every revision.
- **Shipped — `src/caliper/design.py`:** `Design` / `DesignPart` / `Requirement` (pydantic, YAML+JSON
  round-trip) and `DesignStore`, the only thing that writes inside a design:
  `designs/<slug>/{design.yaml, assembly.yaml, log.jsonl, parts/<id>/{part.py, spec.yaml,
  history.jsonl, versions/vNNN/}}`.
  - **`assembly.yaml` is the existing format** — part sources are written relative to the design root
    (`parts/<id>/part.py`), which `_resolve_source` already handles, so `evaluate_assembly`/`assemble`/
    `insert` consume a design untouched. **A single-part design is a one-part assembly** — no second
    code path, which is what makes "prove it on one part, grow into machines" safe.
  - **Append-only, snapshot every revision.** `write_part` writes the canonical `part.py`, snapshots
    `versions/vNNN/` (part.py + spec + report), updates both records, and appends history **in one
    step** — so the history can't drift out of sync with the geometry it describes. `restore` rolls
    back as a *new* revision, so the rollback is itself history.
  - **Cache invalidation (subtle, would have bitten):** `assembly._PART_CACHE` keys on (path, mtime); a
    same-tick rewrite could serve **stale geometry to the very re-measure meant to prove the change
    landed**. `write_part` now evicts the entry. Covered by a test that widens a part and re-measures.
  - `adopt_run` brings an existing `runs/run_NNNN/` in: an authored run keeps its `part.py` and stays
    revisable; a template run has only geometry, so it's marked `imported` and the assembly points at
    the run dir — honest that there's nothing to revise.
  - `prompt_context(part_id)` builds the **distilled** context a revision should see: goal,
    requirements, sibling parts, mates that must keep holding, enforced assertions, and a bounded tail
    of feedback — not a transcript.
- **CLI:** `caliper design new|list|show` — `show` prints requirements, the part tree with each part's
  feedback narrative, and then **measures the whole design** (tolerant: names a broken part instead of
  sinking the rest, inheriting CALI-27's discipline).
- **Tests:** +26 (23 `tests/test_design.py`, 3 `tests/test_cli.py`) — round-trip, slug collisions,
  versioning/snapshots, torn-history-line recovery, id validation (rejects `../escape`), requirement
  upsert, bounded prompt context, run adoption both ways, and OCCT-gated proof that a design measures
  through `evaluate_assembly` and that a revision is measured rather than cached. **184 passed.**
- **Verified by hand:** created a gantry design, seeded two parts + a refine + requirements,
  `caliper design show` printed the tree, the feedback narrative, and `ALL PASS`.
- `designs/` gitignored (user artifacts, like `runs/`).
- Commit: `658c52e`

---
