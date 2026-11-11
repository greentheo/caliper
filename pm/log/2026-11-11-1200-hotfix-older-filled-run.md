### 2026-11-11 · Hotfix · The cards don't crash on an older run that was filled in

`step-stool-3`'s cards returned 500 on main: its newest strength run was recorded as filled in, the part has since been fixed so `filled()` is None, and the card line called `untrusted(pid, None)`. It now says the last check ran on a filled-in shape, on an older version, and to check it again. One test in `test_filled_verdict`.
