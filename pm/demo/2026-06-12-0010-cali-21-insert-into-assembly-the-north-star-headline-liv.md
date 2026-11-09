### 2026-06-12 · Insert-into-assembly — the north-star headline (CALI-21) ✅ live
**New:** point at an assembly, name **two existing parts**, and Caliper makes the LLM **author a new
part that mates to both at a target fit** — built in assembly coordinates, *measured* against the real
posed parts, then added back to the assembly and re-verified. This is "insert a support between the
wheel and the XYZ assembly," working end to end.
**Try it** (needs `ANTHROPIC_API_KEY` — your `.env` has it):
```bash
make insert        # bridges examples/insert_demo.yaml (two posts, 50mm gap) with a cross-bar
#   caliper insert examples/insert_demo.yaml --between post_left,post_right \
#       --as crossbar --intent "a cross-bar" --fit slip --save examples/inserted.yaml
caliper assemble examples/inserted.yaml    # re-measure the assembly WITH the inserted part
```
**Verified live (2026-06-12):** the LLM authored the cross-bar on the **first round**, landing **0.21 mm
clearance to each post** — dead centre of the slip band (0.12–0.30). It reasons from the interface
bounding boxes, applies the clearance, and places the bar in world coordinates. Try `--fit press` / `free`
or a wider gap to watch it re-size. Want it taller? `caliper refine runs/run_NNNN "make it 6mm taller in z"`.
