### 2026-11-11 · CALI-154 (#218) · A first build says what it's doing, and keeps saying it

Theo, on a first build: "running for nearly 3 minutes now, and still nothing". What the page did before this: the bubble in the chat did show, but a planned build's `plan` step wasn't one it knew, so it stayed on the step before; the timer was per step and restarted on a reload; and leaving the design lost the bubble for good, because coming back it thought it was still following. `GET …/running` was also empty during a first build.

Now the bubble names every step, gives the whole build's elapsed time from the job's own start, and says which try authoring is on ("writing the design: third try"). A reload replays it with the right time. Leaving the design lets it follow again on return and frees the other design's chat. A first build is on `/running`, with its text and elapsed seconds, so a build started in another tab appears too.

Seen in a real browser against a stubbed designer (no Claude): progress at 1 s, 7 s and 18 s, on after a reload with the right time, on after switching away and back, and the send button free on the other design. Tests: `tests/test_first_build_progress.py`, seven mutants caught. The whole suite is CI's.
