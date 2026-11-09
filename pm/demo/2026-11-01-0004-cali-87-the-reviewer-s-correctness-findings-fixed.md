### 2026-11-01 · The reviewer's correctness findings, fixed (CALI-87 #63)
1. **A carved part:** adopt a BUILD what-if, a frame design or a drag station, and the reply and History say
   the carve came off. "Put a T-rex on it" says it's carved, and what to do first.
2. **"Put a T-rex on the right side":** it goes on the right.
3. **The CNC sheet for a stool with a lightening hole:** the hole is the first cut in the SVG and the DXF.
4. **A build package for a crate with XPS in it:** the book doesn't list a kids' book.
5. Offline: `PYTHONPATH=src CALIPER_UNFOLD_DIR=<unfold-to-sheets> python -m pytest tests/test_carve_dropped.py
   tests/test_carve_stale.py tests/test_printed_cache.py tests/test_cutplan.py tests/test_consistency.py
   tests/test_kidbook.py tests/test_pictures.py tests/test_promote.py -rs`.
