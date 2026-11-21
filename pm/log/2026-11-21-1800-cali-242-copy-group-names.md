### 2026-11-21 · CALI-242 (#17) · No part, copied or added, takes a group's name; slice E's contract branches pinned

#399's follow-up, from reviewer-3's re-check and the foreman's call. #399 made a new part avoid a group's name in the chat, the router and the first run, and `write_part` refuse one. #374's Copy… (merged after) didn't know about groups:
- `placing.free_id` picked `wall_2` over a group named `wall_2`;
- a mesh part's copy went through `write_mesh_part`, which had no guard.

- **`free_id`** treats the plan's group ids as taken: a copy of `wall` beside a group `wall_2` is `wall_3`.
- **`write_mesh_part`** refuses a new part named like a group, through the same check as `write_part` (`DesignStore._not_a_group`).
- **Pinned, three branches #399's contract had no test for:**
  - `store.group_geometry` over a name that's a part and a group;
  - `store.group_geometry` over a part that didn't build;
  - the first run's own part id avoiding a group's name.

**Tests:** 5 in `test_group_names.py`, no live call. 2 fail on main; 3 pin #399's branches. All 5 hand-made mutants are caught:
1. a copy takes a group's name;
2. a mesh part takes one;
3. a clash measured;
4. didn't-build unsaid;
5. the first run takes a group's name.

The files that read free_id, write_mesh_part, Copy…/Move…, the group geometry or the first part, plus group-rules and first-run, pass, 299.
