# Caliper M4 — the design session

*Companion to [`caliper-design-spec.md`](caliper-design-spec.md). That document specifies the **engine**
(intent → spec → geometry → measurement → revision). This one specifies the **interface**: how a human
drives that engine by talking to a design instead of operating a control panel.*

---

## 1. Why

M0–M3 built a measurement-grounded engine that works: an LLM authors CadQuery, the geometry is measured
exactly, failures route to either a structural edit or a numeric optimizer, and parts mate into assemblies
with asserted fits. `caliper assemble examples/machine.yaml` proves a four-part corner leg green, bolt
alignment included.

The webapp, however, is a **control panel for that engine**. It asks the user to know things that are
Caliper's business, not theirs: LLM vs. offline intake, "author any part" vs. the bracket template, a run
vs. an assembly, which two parts to pick before `Insert` un-greys. Every toggle is an internal seam
leaking into the user's job, and the result is an interaction-heavy tool that you *operate* rather than
one you *design with*.

M4 inverts it. The screen becomes a **viewport and a conversation**. You state what you're building, answer
a few clarifying questions, and watch parts appear. You click a part and talk about *that part*. The
machinery — which model authored it, whether the optimizer or the LLM made the last move — recedes into a
drawer you open only when something is wrong.

**Non-goal:** replacing the engine, the CLI, or the measurement vocabulary. M4 adds a shell and one new
durable object. Everything underneath is reused.

---

## 2. The one new idea: feedback becomes assertions

A conversational CAD tool that only ever *edits* accumulates drift. You say "make the wheel mount 5 mm
wider," it happens, and nothing stops revision #14 from quietly undoing it. The history grows into a
transcript nobody can re-read and the model starts dropping earlier decisions.

Caliper has a better option available to it than any chat-with-CAD toy, because measurement is already the
source of truth: **feedback that can be measured is promoted into the spec's `assert` block.**

> "the wheel needs to clear the rail" → `wheel_clears_rail: min_clearance(rail) >= 1.0`

Now it is a test. It is checked on every subsequent revision of that part *and* every re-measure of the
whole design, forever, by machinery that already exists (§4 of the design spec, `evaluate.py`).

This splits the per-part history cleanly into two things with different jobs:

| | holds | used for |
|---|---|---|
| `history.jsonl` | the narrative — what was asked, what changed, what it measured, whether it stuck | context for future decisions; the audit trail; "why is this 43 mm?" |
| `spec.assert` | the enforceable residue | regression-proofing, on every build |

Prompts are then built from *requirements + current script + distilled constraints*, not from a raw
transcript that grows without bound.

**Promotion is proposed, never silent.** Caliper drafts the assertion, shows it, and the human accepts or
declines inline. An over-constrained spec fails in confusing ways; the user must know what rules exist.
Feedback that isn't measurable ("make it look less chunky") stays a plain edit in the log — honestly
labelled as unenforceable rather than faked into a number.

---

## 3. The new object: a Design

Today the durable artifacts are `runs/run_NNNN/` (a snapshot of one part) and a hand-written
`examples/*.yaml` assembly. There is no container for "the thing I am building" — no root prompt, no
requirements, no per-part history. That container is the M4 spine.

```
designs/<slug>/
  design.yaml            # root prompt, clarified requirements, units, machine profile, part index
  assembly.yaml          # parts + mates + asserts — the EXISTING assembly.py format, unchanged
  log.jsonl              # design-level conversation (append-only)
  parts/
    <part_id>/
      part.py            # current geometry source (CadQuery, world coords)
      spec.yaml          # this part's parameters + assertions (existing Spec format)
      history.jsonl      # append-only: feedback → change → measurement → accepted?
      versions/
        v003/            # part.py + report.json snapshot, so any revision is recoverable
```

Deliberate choices:

- **`assembly.yaml` is the existing format.** A Design is an assembly plus provenance. `assemble`,
  `evaluate_assembly`, mates, and `insert` keep working against it untouched.
- **A single-part design is just a one-part assembly.** No special case, no second code path — which is
  what makes it safe to start v1 with one part and grow into machines without a rewrite.
- **Append-only logs, snapshot versions.** The same rhythm as `pm/LOG.md`: nothing is overwritten, every
  state is recoverable, the history *is* the artifact.
- **`runs/` is untouched.** Existing runs stay browsable; a design may adopt a run as a part.

### history.jsonl entry

```json
{"ts": "...", "kind": "feedback", "text": "the mount needs to clear the rail",
 "scope": "carriage", "action": "refine", "version": "v004",
 "changed": {"script": "+12 -4 lines", "params": {"mount_w": [38.0, 43.0]}},
 "measured": {"min_clearance(rail)": {"before": 0.4, "after": 1.6}},
 "assertion_proposed": "wheel_clears_rail: min_clearance(rail) >= 1.0",
 "assertion_accepted": true, "result": "all_pass"}
```

Enough to reconstruct *what was asked, what moved, what it measured, and what became permanent* — which is
exactly the context a later revision of that part needs.

---

## 4. The interaction

**Three surfaces, and only three:** the viewport, the chat, and a collapsed Advanced drawer.

1. **Start.** One prompt box: *"a 3D printer gantry, 300 × 300 × 400 build volume."*
2. **Clarify.** Caliper asks a bounded round of questions that actually change the geometry (extrusion
   profile? belt or leadscrew? rail type? print process for the parts?). Answers are stored as
   **requirements** in `design.yaml` and are permanent context — asked once, never re-asked.
3. **Build.** Parts appear in the viewport as they are authored and measured, narrated in the chat
   ("authoring `carriage`… measured… revising 2/3… all pass").
4. **Talk to a part.** Click it in the viewport; the chat scopes to that part (shown as a chip you can
   dismiss to return to design scope). Type feedback. Caliper revises *that part*, re-measures **the whole
   design**, and reports anything the change broke.
5. **Lock it in.** Measurable feedback gets an assertion proposed inline; accept and it is enforced forever.

### Scope is the selection

An unscoped message is about the design; a scoped message is about the clicked part. That single rule
replaces most of the current panel — no mode toggles, no "pick 1 / pick 2" ceremony. `insert` keeps its
two-part pick, but as a *conversation* ("put a bracket between these two") with the picks as context.

### Re-measure the whole design, always

The critical discipline, and the thing that distinguishes this from a chat wrapper around a CAD kernel:
**a change to one part re-measures every mate and every assembly-level assertion.** Widening the carriage
may break a clearance three parts away. Caliper's job is to say so, in the chat, in the same turn.

### Selection granularity — what's honest

Part-level picking works today (raycast → `part_id`, CALI-21b). **Feature-level** picking (this hole, this
face) is materially harder: the B-rep → STL tessellation discards face identity, so it needs per-face group
export and an id round-trip through the mesh. M4 therefore ships:

- **part-level selection**, plus
- **nested sub-assemblies** — a "roller carriage" is itself a design you can descend into, which covers most
  of the "zoom into components" ask, and
- **named features in language** — click the part, say "the 5 mm hole on the top face." The model holds the
  script; it knows which hole. This is the cheap 80 % of feature selection and it needs no new geometry
  plumbing.

True face picking is deferred (CALI-37) and should not block M4.

---

## 5. What this requires that doesn't exist

Named plainly, because M4 is more than a reskin:

1. **The Design object and its store** (§3). New. Everything else hangs off it.
2. **A chat turn handler.** Message + optional scope → classify → act (clarify / author / refine / promote /
   answer) → re-measure → respond + append history. New, but every *action* it dispatches to already exists.
3. **Refine a part that lives inside an assembly.** `refine_authored` today operates on a single-part run;
   assembly members are static `.py` files with no revision path. The core M4 interaction — click a part,
   give feedback, watch it change — has **no code path today**. This is the single most important gap.
4. **Streaming.** Authoring is many LLM round-trips over tens of seconds; the server is synchronous POST. A
   chat that sits dead for 90 s reads as broken. Needs a job + SSE so the chat can narrate.
5. **Decomposition** (M5). Nothing turns "a gantry" into a part list with interfaces — `machine.yaml` and its
   four `.py` files were written by hand. This is the highest-value and least-proven new capability, which is
   why it lands *after* the interaction is proven on one part, not alongside it.

Reused unchanged: the assembly model and mates, `insert_part`, `improve`/`refine_authored`, the measurement
vocabulary, fit classes and the optimizer, raycast picking, run persistence, the sandbox.

---

## 6. Risks

- **Decomposition quality (M5, high).** An LLM part breakdown is a *plan*, and plans get trusted when they
  shouldn't be. Mitigation: the plan is emitted as an assembly skeleton with mates and assertions — i.e. as
  something measurable — and is reviewed before any geometry is authored.
- **Context growth (medium).** Mitigated by §2: distilled constraints and assertions, not raw transcript.
- **Latency (medium).** Authoring a multi-part machine is minutes. Mitigated by streaming, per-part progress,
  and building parts in dependency order so the viewport fills early.
- **Silent regression across parts (medium).** Mitigated by always re-measuring the whole design.
- **Losing the escape hatch (low).** Mitigated by keeping the current panel as the Advanced drawer: spec YAML,
  `part.py`, raw report.

---

## 7. Milestones

**M4 — the design session** (interaction proven, single part → few parts)

| id | task |
|---|---|
| CALI-28 | Design object + store (`designs/<slug>/`, part tree, history, versions) |
| CALI-29 | Chat turn handler — scope-aware; author/refine a design part; re-measure the whole design |
| CALI-30 | Feedback → assertion promotion (propose, validate, confirm, append) |
| CALI-31 | Job + SSE streaming so the chat narrates long authoring runs |
| CALI-32 | Front end: viewport + chat as the default; old panel demoted to an Advanced drawer |
| CALI-33 | Clarify round on a new design → stored requirements (permanent context) |

**M5 — whole machines from one prompt**

| id | task |
|---|---|
| CALI-35 | Decomposition planner: root prompt → assembly skeleton (parts + interfaces + asserts), reviewed |
| CALI-36 | Nested sub-assemblies (descend into a part that is itself a design) |
| CALI-37 | Feature-level selection (per-face export + id round-trip) |

The north star is unchanged: **AI-driven design of whole machines with correct fits and tolerances, built
from small well-fit parts.** M4 is the change that makes it usable by a human who isn't holding the
engine's internals in their head.
