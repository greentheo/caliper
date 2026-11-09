### 2026-06-13 · CALI-27 · Hardening — fix the things Theo actually hit
- **Reported (Theo):** (1) confusing UI — "didn't know which options to click"; (2) "adding in new
  parts didn't seem to work"; (3) "the 'machine' generation only made part of the machine";
  (4) "I don't even remember where it's hosted."
- **Root cause of the partial machine (real bug):** `loadAssembly` fetched part STLs sequentially with
  **no `response.ok` check** — one slow/failed part threw out of the loop, leaving already-added parts
  on screen and never loading the rest. Fixed: parts load **in parallel**, each with its own error
  handling; the viewer renders everything that loaded and the error bar **names what broke and why**
  (status: "loaded 3/4 parts — see the error bar"). Progress text explains the first-load script builds.
- **Server tolerance:** new `assembly.load_parts_tolerant` — one broken part no longer sinks the whole
  assembly; `/api/assembly/{id}` returns `part_errors` per part and still measures what loaded. Build
  errors now surface the traceback's **last line** (the actual exception), not 300 chars of boilerplate.
  A stale error bar is cleared on each new load.
- **UI clarity:** a collapsible **"❓ How this works"** primer (build one part → refine → fit →
  assemblies/insert; which actions need the API key); intent label says **"describe one part"** (a
  machine = an assembly — likely the other reading of "generation only made part of the machine": `gen`
  authors ONE watertight part by design); tooltips on use-Claude/author/refine; the Insert hint now
  narrates each step ("left-click a part … 1 more … ready — Insert authors a part mating a ↔ b").
- **Where it runs:** README gains a top-level "▶ Run it" block — **`make serve` →
  `http://127.0.0.1:8000`, local only, not hosted anywhere**; TESTING.md opens with the same callout.
  README status/layout refreshed (was stale at "Phase 0").
- **Verified live in-browser (Preview MCP):** a deliberately-broken 2-part assembly renders the good
  part + names the broken one ("RuntimeError: demo: this part is intentionally broken"); the corner-leg
  machine still loads 4/4 ALL PASS; pick hints step through 0→1→2 correctly; error bar clears on the
  next load; zero console warnings.
- Tests: +2 (`load_parts_tolerant` names the broken part; `/api/assembly` returns `part_errors`, good
  part still serves, broken part 422s with a clear detail). **158 passed.**
  Commit: ab9db2c
