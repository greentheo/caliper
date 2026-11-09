### 2026-10-29 · CALI-60 (#5) · Open source, and the tracker moves to GitHub
- **Theo:** "let's move our issues onto GH … let's move this into open source, and start the work to get this
  into fighting shape". He picked Apache-2.0 for all three repos, and a push + PR for the M4–M6 branch.
- **Issues:** every open card, plus the V1 gaps found while planning the showcase video, filed as
  greentheo/caliper #1–#24 with milestones (V1, M6, M5) and labels (P0–P2, area, showcase, parked, blocked).
  `BOARD.md` and `TASKS.md` are frozen as history; the board maps each open card to its issue. The duplicate
  CALI-12 line is gone.
- **New V1 cards:** CALI-54 the designer writes the study inputs (`members()`, `construction()`, `shell()`…)
  from the chat — today it only keeps them, so a design started in chat gets no study, BOM or cut plan;
  CALI-55 goals from the conversation; CALI-57 the Mac app; CALI-58 App Store spike; CALI-59 first run;
  CALI-60 open-source readiness; CALI-61–63 showcase builds (the stool, a Savonius turbine, the camper
  redone through chat); CALI-64 end of life (Theo's furniture-that-composts vision); CALI-65 the video.
  CALI-35 (decomposition) and CALI-48 (the shop) moved into V1: the turbine needs both.
- **Licence:** Apache-2.0 (`LICENSE`, `NOTICE`, `license = "Apache-2.0"` in pyproject, setuptools ≥ 77).
  whittle was already MIT, so it's left as is; unfold-to-sheets gets Apache-2.0 in its own PR.
- **CI:** `.github/workflows/tests.yml` runs the suite on every PR and on main: micromamba CadQuery,
  pip for the rest, whittle from git, unfold-to-sheets cloned for the cut-plan tests, no PDF.
- Audit before pushing: no secrets in any branch's history (only `sk-ant-...` placeholders).
