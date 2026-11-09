### 2026-06-13 · Webapp insert UI + assembly viewer (CALI-21b / 20b) ✅ live in-browser
**New:** the insert headline is now **clickable in the browser**. Open the Assemblies panel, load an
assembly, **click two parts in the 3D view to pick the interfaces**, choose a fit + what to insert, hit
Insert → the LLM authors the bridging part and it drops into the scene (green), with the whole assembly
re-measured. No CLI needed.
**Try it** (needs `ANTHROPIC_API_KEY`):
```bash
make serve        # → http://127.0.0.1:8000
# In the browser: open "Assemblies" → click "two-posts" → click the left post, then the right post
#   → set fit = slip, "what to insert" = a cross-bar → Insert ▶
# The green cross-bar appears between the posts; the report shows both mates at ~0.21mm (slip), no collision.
```
Assemblies are any YAML under `examples/` (override with `CALIPER_ASSEMBLIES`). An insert saves
`<id>.inserted.yaml` so it reappears in the list — load it and insert again to keep building.
**Verified live (2026-06-13, Preview MCP):** loaded two-posts, picked both, Insert → cross-bar authored
in 1 round, 0.21mm/side, ALL PASS — rendered green in 3D, no console errors.
