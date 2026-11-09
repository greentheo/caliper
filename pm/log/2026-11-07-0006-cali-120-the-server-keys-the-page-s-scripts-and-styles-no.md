### 2026-11-07 · CALI-120 (#128) · The server keys the page's scripts and styles; no PR bumps ?v= again
- **`server.keyed_page`** serves `/`, `/index.html` and `/classic` with every `?v=` on the page's own `.js` and
  `.css` set to a 10-character hash of that file (`cache_key`), read per request: a changed `design.js` is a new key on
  reload, an unchanged one the same. The page itself is `no-store`. The pages keep `?v=dev` and never change for it
  again. The vendored three.js is imported by version-pinned path through the importmap, so it needs no key.
- **Why:** each merge to `main` made every other open PR conflict on `design.js?v=N` (tonight #122, #124 and #125
  each merged `main` again only for it, a full CI run each).
- CONTRIBUTING.md and firm/NIGHT_SHIFT.md: no bump step; the server does it.
- `tests/test_cache_key.py` (3): the key follows the file and only the file; the served pages are keyed and
  `no-store`; the pages keep the placeholder.
