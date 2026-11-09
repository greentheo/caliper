### 2026-06-12 · Multi-parameter optimizer — coupled fits (CALI-19b)
**New (loop-internal):** when a part has **two or more continuous dimensions** and a numeric check fails,
the decide step now tunes the **whole vector jointly** (`decide.tune_multi`) instead of one knob at a
time — so coupled fits (a clearance that depends on two dimensions, two mates sharing a wall) actually
converge. Coordinate descent does the cheap work; it **escalates to a global scipy search only when the
fits genuinely couple** (the case one-knob-at-a-time gets stuck on). No new command — `run`/`fit`/the
loop just solve harder fit problems now. Covered by `test_decide.py` (a coupled `W+D` / `W*D` problem).
