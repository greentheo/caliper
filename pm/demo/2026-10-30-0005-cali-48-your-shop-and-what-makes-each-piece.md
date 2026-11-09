### 2026-10-30 · Your shop, and what makes each piece (CALI-48 #4)
1. **Shop** (header): tick your hand tools, add a router, plasma table or printer with their sizes, **Save**.
   Until you do, Caliper plans for a jigsaw, a drill and a circular saw.
2. Click the stool: **Built from → Made in your shop** says "jigsaw: left side panel, …". Add a router that's
   big enough and it says "router" instead.
3. A printed part (`{"kind": "printed", "material": "petg"}` in its construction): with a printer in your shop
   it's split to fit with pin holes, and costed in hours, grams and dollars (PrusaSlicer if it's installed).
4. **Score it**: "your shop can make every piece". **Make the build package**: a *Made in your shop* page and
   `printer/` with the STLs.
5. Offline: `python -m pytest tests/test_shop.py`.
