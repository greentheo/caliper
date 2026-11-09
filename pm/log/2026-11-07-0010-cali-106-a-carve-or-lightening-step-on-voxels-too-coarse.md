### 2026-11-07 · CALI-106 (#101) · A carve or lightening step on voxels too coarse to see the wall is no "holds"
- **Carve and lighten record whether their voxels see the walls** (`load_study.resolution`, from the same set-up the
  strength check uses): `thinnest_mm`, `across`, `resolved`, and unresolved, `finer` or `too_thin`.
- **A step that holds on a run that doesn't see its walls is "not resolved"** (or "not checked" where no run a study
  may make could see them), through `verdicts.station`/`carve_step`/`lighten_step` (stacked on #132's one verdict);
  a fail stays a fail, not trusted still ranks above it. Every reader: the chart's dots (amber), "the lightest step
  where the printed part holds" line, the station bar and its **Carve it like this** / **Cut these holes** (off, with
  why), the Studies rows, the carve's chat reply and its closing message.
- **Where no run can see the walls it isn't carved:** `carve.study` stops before carving, "Its walls are too thin for
  the voxel check at this size, so it can't be carved by strength", and the page's Carve and Lighten buttons are off
  with that line. Also off, with its reason, where the default check's voxels don't connect (#102's note). Theo's
  bar stool v7 (a copy): a 0.25 mm wall at 4.6 mm voxels, too thin, so Carve isn't offered.
- `tests/test_coarse_steps.py`: the thin printed tube carved at one voxel through reads not resolved at every step that
  holds (and in the page's state, Studies and the chat), at four it reads as its safety says; `resolution` on the bar
  stool's numbers; a too-thin part isn't carved; lightening's coarse steps; the page's buttons.
