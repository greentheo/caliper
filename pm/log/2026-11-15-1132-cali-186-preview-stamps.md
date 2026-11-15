### 2026-11-15 · CALI-186 (#297) · #307 review: the stamp inside every preview file; Cancel; a lock of its own

reviewer-2's must-fix on #307: a cut-plan preview's machine files were only renamed. Nothing in the DXF, the sheet SVG, the 1:1 PDF, the OBJ or the TXT files said "preview", so a file renamed or sent on from a list said nothing. The foreman's rework adds two of reviewer-2's small asks: Cancel, and a lock of its own.

- **Inside every file** (`previews.stamp_file`, over every file a preview makes):
  - **DXF:** a `999` comment first, and a `TEXT` on the LABEL layer 25 mm above everything drawn, so it sits clear of every part. ezdxf 1.4.2 reads it: step 10's sheet has it at y = 1244 mm, over the 1219 mm sheet.
  - **SVG:** its `<title>` starts with the stamp, and a red line of text sits at the top of its drawing.
  - **OBJ and TXT:** a first line.
  - **JSON:** a `stamp` field.
  - **PNG:** a Comment text chunk.
- **The PDFs:**
  - The patterns PDFs carry it in their title. Each of their pages already said it across its top.
  - unfold-to-sheets' printable PDF is **left out** of a cut-plan preview: there's no PDF library in the env to stamp its pages. `preview.html` says so and points to the stamped sheet SVGs.
- **Cancel:** `previews.make` takes the job's check (`stop=j.check`) and calls it after the copy, after the build and before the landing. A cancel at any of the three keeps nothing.
- **Lock:** the job's lock is `preview:{slug}`, not the design's, so a chat turn doesn't queue behind it. A delete of its own part still waits for it, through the meta (`DOING`), and `WHOLE` has "preview".
  - **A write meanwhile:** with no design lock held, a write can land during the build. If the part's version changed, the preview is refused (`Stale`, "changed while step N was previewed") and nothing is kept.
- **Cache format:** the cache key includes a `FORMAT` (now 2), so a preview kept before this change is made again, not served unstamped.

**Tests:** in `tests/test_step_previews.py`:
- **Every file is stamped:** a real patterns preview and a real cut-plan preview are made, and every file they hold is read for "PREVIEW" (UTF-16 too: a PDF title). The test also checks the DXF's comment, and its TEXT's layer and height above every part, plus the SVG's title and red line, and the OBJ's and TXT's first lines.
- **Cancel:** at each of the three checks.
- **A part written meanwhile:** refused, with nothing kept.
- **The route:** its lock, its meta, and that its check is the job's.
- **An older format:** made again.
- **Mutants:** 17, all caught.
- **Around run:** 101 files. One failure was `test_scrub_sweep`'s guard, which read my `{e}` (the escaped stamp) as raw exception text. That was the code's fault: the name is now `words`, and the guard passes.
