### 2026-11-11 · CALI-157 (#223) part 3 · Smaller edits

A revision now sends the current script and asks for targeted replacements, applied exactly, each `old` found exactly once. If an edit doesn't apply, it's tried once more with the error, then the part is rewritten whole. A one-line change leaves the rest of the script byte for byte the same. A refusal isn't turned into a rewrite. Each revision writes its tries and seconds to the design's log (`kind: revise`). Stubbed designer only; the gain in time is for Theo's real run to show. The whole suite is CI's.
