### 2026-11-09 · CALI-131 (#162) · A sheet's outline is a face of the panel; one declared off it is named
Found drawing the part tree's pieces: the stool's seat read blue from above, because its outline sat at mid-thickness.
The checks built the plywood slab 9.5 mm low, and the top of the seat counted as printed PETG with nothing to say so.
- **One convention, said once in the guide:** an outline is a face of the panel, on the solid's surface, never its
  mid-plane. `wood_solids` already built it that way; the guide's "inside the solid or on its surface" allowed the mistake.
- **A check names it** (`construction_on_its_face`): solid beyond the outline, away from the panel, that no other piece
  accounts for. On a copy of the stool: "seat top: declared 9.5 mm below where the part has it". It fails, so it shows
  on the card. Stacked sheets, the samples and a small tessellation offset aren't flagged.
- Theo's script isn't touched. The card names it and he decides.
- **Measured on a copy of the stool** (6 mm wall, slicer real): 13.1 → 12.5 lb, 9.68 → 9.14 L printed, 5,062 → 4,841 g,
  234 → 221 h, 0.53x → 0.54x. About 0.6 lb, not the 2 lb first estimated.
- Tests: tests/test_sheet_face.py (12, the samples included).
