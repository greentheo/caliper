### 2026-06-12 · LLM-authored generator — `caliper gen` (any part)
**New:** the LLM writes the CadQuery script itself, so you're no longer limited to the bracket family.
It runs the script **sandboxed**, measures it, and **self-heals build errors** (feeds the traceback
back and retries). **Try (needs `ANTHROPIC_API_KEY`):**
```bash
make gen INTENT="a cylindrical desk cable grommet: 40mm outer diameter, 30mm inner bore, 25mm tall, with a 5mm flange lip at the top"
# or non-bracket things like:
make gen INTENT="a phone stand for an 8mm-thick phone, angled back 65 degrees"
make gen INTENT="a 60mm-tall hexagonal pen cup with 3mm walls"
```
Expect: a drafted spec (the LLM also asks good clarifying questions), then **"✓ built on attempt N"**,
a measurement report, and a run dir with **`part.py`** (the script it wrote — open it, it's real
readable CadQuery) + `part.stl`. The grommet test produced a clean hollow tube + flange union, 7/8
asserts passing. **Note:** today it self-heals *build* errors but doesn't yet iterate to fix failing
*measurements* (that's CALI-17). The bracket path (`run`/`refine`/`fit`) is unchanged.
> **Also fixed:** LLM intake/refine were silently falling back to the offline bracket on your model
> (`claude-sonnet-4-6`) — an assistant-prefill the model rejects, plus schema mismatches. So
> `make run-llm` / `make refine-llm` now actually use Claude too, not just `gen`.
