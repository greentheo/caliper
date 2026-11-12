### 2026-11-12 · CALI-168 (#258) · "I need a bench" is a bench

From #250's review, also on main: "I need a bench" authored a part named `i_need`. `chat.part_id_from` took the message's
first words, after skipping only "add", "make me a" and the like.

The request's own words are now skipped too ("I need", "I want", "I'd like", "can you", "could you", "let's"), so a
new part is named for its noun: "I need a bench" is `bench`, "I want a shelf for my garage" is `shelf`, "make me a stool"
is `stool`, and "can you make a step stool" is `step_stool`.

**Tests:** 8 in `test_part_names.py`, 6 of which fail on main. The mutant (the request words dropped) is caught. The 10 router and chat files pass, 343. #250's
empty-design rule, which answers "I need it wider" with nothing built, is in #250; this names a part only where one is
asked for.
