### 2026-11-05 · CALI-103 (#95) · The app no longer crashes when the page and a study query one mesh at once
- **The owner's app died three times (exit 134/139) in libspatialindex:** two threads in one cached mesh's R-tree,
  once with no study running (just the page's burst after a revision).
- **`caliper/spatial.py` holds one lock for each trimesh spatial query** (`contains`, `closest_point`,
  `signed_distance`, `nearest`, `ray`, proximity), never across a loop or a study step. Every caller goes through
  it, and a guard test fails if any module queries a mesh another way.
- **Measured:**
  - a raw two-thread race died in 7 runs of 7; through the lock it survives;
  - a server on `main` died (exit 139, the same stack) 32 s into a page burst during a carve; the fixed server
    survived 6 minutes of it;
  - during a real carve, a card request took 0.99 s median and 2.58 s worst (97 requests), against about 1 s idle.
- **A crash eats less work:** a chat message is logged the moment it arrives, and a carve writes its run as it goes
  ("not finished: 1 of 3 steps checked").
- Commits: `6b0535f` (the lock), `2044258` (the message), `e3a5151` (the carve's progress).

---
