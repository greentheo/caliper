### 2026-11-10 · CALI-146 (#189) · A corner isn't a thin wall

**What was wrong.** The thinnest-wall probe casts a ray inward from each surface sample and takes the distance to what it hits. A ray launched right beside a near-square corner runs along the next face and meets it at a glance: that's the corner, not a wall. On a copy of the stool with its openings cut clean, five of 20,000 rays did it and the rule read 1.8 mm, against neighbouring rays reading 5.3 mm or more.

**The change.** A ray that meets the face it ends on within 5° of parallel is left out. A wall's far side is met nearly head on, however close to a corner the ray starts, so a real thin web beside a corner still reads thin. So does a tapering sliver, and so does a corner more than 5° from square. `SCORER` goes to 3, because the wall reading on a card can change.

**Before and after** (seed 0):

| design | part | 2,000 samples | 20,000 samples | rays left out of 20,000 | rule | why |
|---|---|---|---|---|---|---|
| camper sample | leaf_rear | 364.5 unchanged | 355.7 unchanged | 0 | no wall rule | |
| camper sample | frame | 1.35 unchanged | 1.35 unchanged | 0 | no wall rule | |
| camper sample | cargo_box | 191.4 → 312.0 | 176.8 → 229.5 | 63 | no wall rule | long rays that met a face at a glance inside a big foam box |
| step-stool sample | step_stool | 19.0 unchanged | 19.0 unchanged | 0 | no wall rule | |
| stool copy (as on the page) | i_want | 0.286 unchanged | 0.227 unchanged | 4 | fail, unchanged | real sliver |
| stool copy, 6 mm, as drawn | i_want | 0.246 unchanged | 0.222 unchanged | 1 | fail, unchanged | real sliver |
| stool copy, 6 mm, openings cut clean | i_want | 1.798 → 4.433 | 0.323 → 4.292 | 36 | **fail 1.798 → pass 4.433** | the only verdict that changes: the low readings were corner skims, and the next real wall is about 4.3 mm at the foot arc |

The camper sample's scorecard is re-scored, so it doesn't ship out of date: every check and metric came out the same as the old card.

**Not verified.** Stored strength runs keep the thinnest wall they recorded until they're run again; that errs thin. The whole suite is CI's.
