# Caliper work log

Append-only. Newest first. One entry per shipped task or notable decision.
Format: `### YYYY-MM-DD · CALI-N · title` then what changed, tests, and the commit hash.

---

### 2026-06-11 · CALI-0 · Project scaffolding
- Initialized local git repo. Created `src/caliper/` package layout, `tests/`, `pm/`, `nightshift/`.
- Conda env `caliper` from `environment.yml` (CadQuery/OCCT + trimesh + manifold3d + scipy + pydantic).
- Stood up the .md PM system: `BOARD.md`, `TASKS.md`, `LOG.md`, `pm/README.md`.
- Adopted ai-night-shift conventions locally (loop/review/test guard) without cron — see `nightshift/`.
- Decisions: conda for the env; nightshift conventions-only (no autonomous cron yet); start M0 core this session.
- Commit: _pending_
