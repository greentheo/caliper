### 2026-06-11 · LLM path — robust JSON parsing
**Fixed:** `make refine-llm` failed with `JSONDecodeError` when Claude wrapped its reply in markdown.
The parser now strips code fences / prose and prefills `{` to force a clean object.
**Try (needs `ANTHROPIC_API_KEY`):**
```bash
make refine-llm SOURCE=runs/run_0000 INSTRUCTION="lighten it and round the outer corners"
# header should read "── changes (llm) ──"; if it says (offline), run CALIPER_DEBUG=1 make refine-llm ...
```
Note: the LLM can only set existing bracket params — variable bend angle (CALI-11) and threaded holes
(CALI-12) need generator work, not a prompt.
