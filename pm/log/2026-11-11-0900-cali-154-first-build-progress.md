### 2026-11-11 · CALI-154 (#218) · A first build says what it's doing, and keeps saying it

Theo, on a first build: "running for nearly 3 minutes now, and still nothing". What the page did before this: the bubble in the chat did show, but a planned build's `plan` step wasn't one it knew, so it stayed on the step before; the timer was per step and restarted on a reload; and leaving the design lost the bubble for good, because coming back it thought it was still following. `GET …/running` was also empty during a first build.

Now the bubble names every step, gives the whole build's elapsed time from the job's own start, and says which try authoring is on ("writing the design: third try"). A reload replays it with the right time. Leaving the design lets it follow again on return and frees the other design's chat. A first build is on `/running`, with its text and elapsed seconds, so a build started in another tab appears too.

Seen in a real browser against a stubbed designer (no Claude): progress at 1 s, 7 s and 18 s, on after a reload with the right time, on after switching away and back, and the send button free on the other design. Tests: `tests/test_first_build_progress.py`, seven mutants caught. The whole suite is CI's.

Rework after the review: a build that crashes is written to the design's log, so a reload or coming back says it stopped and why; "Building it" loses its marker and the heading says the build stopped. The time comes from the server's elapsed seconds, not the browser's clock. Leaving a design frees Send only if a build held it, so a chat turn in flight keeps it off. Pressing Build it redraws the cards. The page's wiring is pinned on a stubbed page: which try, the ticking clock, another tab's pick-up, the two follow guards, leaving a design.

Second rework: the cards go by the build, so they're asked again when one starts or ends, in the tab that pressed it and one that picked it up. A crash after the part exists doesn't offer a button that isn't there. A failure on screen is read once, with its report link. The clock never steps back.
