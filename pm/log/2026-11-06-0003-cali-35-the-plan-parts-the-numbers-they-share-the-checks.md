### 2026-11-06 · CALI-35 (#3a) · The plan: parts, the numbers they share, the checks between them, reviewed first
- **`plan.py`:** a plan is parts (what each is, how it's made, `role: fixed` for what the person has, what it mounts
  on), the skeleton (named numbers with a unit and why), mates, and rules over part ids and skeleton names.
  - **Validation refuses, with the reason:** a cycle ("base → mast → hub → rotor → base"), a part, mate or rule
    naming something the plan hasn't, a skeleton number with no unit or a unit Caliper doesn't measure in, a rule
    calling anything but the assembly's measures, two things with one name.
  - **The build order:** mounted-on first, the plan's own order otherwise.
- **The planner:** one Claude call with the plan's schema as its only tool. The system prompt carries the spec's rule:
  separate parts are made separately or move; pieces of one sheet or printed part stay one part.
- **The first run plans first** (with Claude):
  - a plan of several parts is saved and the run stops for review: "A wind turbine in 4 parts: the rotor (…), the
    hub, the mast (…) and the base (…)";
  - a one-part plan (the stool) builds as today;
  - a plan that can't be used is refused, and it builds as one part, saying why;
  - with no key it builds one part, as today, and says planning needs Claude.
- **Build it on a reviewed plan:** "The plan's saved: 4 parts. Building them one by one, in order, comes next (#3b)."
  Nothing is authored (the foreman's call: 3a builds nothing past today's one part).
- **Saved** in `assembly.yaml` (the planned parts at their script paths, the mates as `plan_*`, the rules) and
  `design.yaml` (`skeleton:`, and `plan:` with its parts, order and status).
  - Evaluation skips planned parts that aren't built yet, and a rule naming one is deferred: "waits for mast to be
    built". Every other part loads as ever.
  - A rule can read skeleton names (lengths in mm) and `abs`/`min`/`max`.
- **The review:** the plan on *What is it?*, and the parts in build order, the numbers in the person's units and the
  checks under *the numbers*.
- **The chat edits the plan during review,** never the geometry: "make the mast 10 ft" → "Changed the plan: mast top
  z: 7 ft → 10 ft." A question is still answered.
- **Not done: the live run** of the three sentences (turbine, camper, stool). It spends Theo's key, so it needs his
  word in the session that runs it.
- Tests: `tests/test_plan.py` (a stubbed client throughout).
