### 2026-11-12 · CALI-168 (#258) · "I need a bench" is a bench

From #250's review, also on main: "I need a bench" authored a part named `i_need`. `chat.part_id_from` took the message's
first words, after skipping only "add", "make me a" and the like.

The request's own words are now skipped too ("I need", "I want", "I'd like", "can you", "could you", "let's"), so a
new part is named for its noun: "I need a bench" is `bench`, "I want a shelf for my garage" is `shelf`, "make me a stool"
is `stool`, and "can you make a step stool" is `step_stool`.

**Tests:** 8 in `test_part_names.py`, 6 of which fail on main. The mutant (the request words dropped) is caught. The 10 router and chat files pass, 343. #250's
empty-design rule, which answers "I need it wider" with nothing built, is in #250; this names a part only where one is
asked for.

**Rework from reviewer-2's review: the request is skipped only as a leading phrase.** Added to `_LEAD_FILLER`, the
request words also ended names partway: "build a trash can enclosure" became `trash`, "add a can crusher" `crusher`,
"add an I-beam" `beam`, "add a D-ring" `ring`. Now they're a phrase of their own (`_REQUEST`), stripped once at the very
start ("I need", "I'd like", "we want", "can you", "could you please", "let's"), and never used to end a name. A "can"
at the start that isn't "can you" is the name's ("can opener mount" is `can_opener`).

Pinned: reviewer-2's six (trash can, watering can, soda can, can crusher, like button, I-beam) plus the D-ring, the
get-well card holder and the can opener; 20 cases in the file. Both mutants are caught (the strip dropped, and "you"
made optional). The 10 router and chat files pass, 355.

**The "want" case, here now that #250 is merged (the foreman's call).** #250's empty-design rule caught "I need it wider"
but not "I want it taller", which went to the designer. Both rules now read the one request phrase, `_REQUEST`, so they
can't drift: on an empty design, a request whose rest is about something already there ("it taller", "make them
smaller") has nothing to change, and answers (`_asks_of_it`). Pinned: "I want it taller", "I'd like it wider", "can you
make it shorter", "I need it wider", "I need them painted", "could you please make them smaller" and "let's make it
taller". "I want a bench" still authors. Main merged forward first, cleanly. Both mutants are caught; the router and
chat files pass, 341.
