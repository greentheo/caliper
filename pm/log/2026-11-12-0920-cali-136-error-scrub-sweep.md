### 2026-11-12 · CALI-136 (#174) · Everything an exception says goes out through one place

Before hosting, from #215's review: about 78 raw `str(e)` and `{e}` sites remained, on their way to a person (route details,
results, replies, notes). And `errors.scrub` missed a Bearer header, `https://user:pass@…` and `password=…` unless the
value was also in an environment variable.

- **`errors.scrub` takes secrets by their shape:**
  - a Bearer header (`Bearer <secret>`);
  - a URL's `user:password@` (`https://<secret>@…`);
  - a `password`, `passwd`, `pwd`, `secret`, `token`, `api_key` or `access_key` pair with `=` or `:`.

  Plain words stay ("the password field is required").
- **Every route's `HTTPException` detail goes out through one handler** (`server.py`), scrubbed, with its status and
  headers kept. That covers the ~45 route sites without touching each.
- **The 35 other sites** where an exception's text went toward a person now go through `errors.scrubbed`: assertion
  details, the scorecard's error metrics, the findings' "couldn't measure", tipping and weighing notes, carve and
  picture replies, the run history's "failed", the slicer's "no estimate", whittle's error, and the rest. The sandbox's
  error and traceback are scrubbed as they come back from its process, and so are the build worker's.
- **A guard test** fails on any new raw `str(e)`/`{e}` in `src/caliper`. It allows only:
  - a re-raise (whoever reads it next scrubs it);
  - a line printed to this server's own stderr;
  - the command line on your own machine (`cli.py`);
  - the sandbox's own processes (their parent scrubs what comes back);
  - `errors.py` itself.

**Tests:** 11 in `test_scrub_sweep.py`; 10 fail on main.

All 5 mutants are caught (each new secret shape, the route handler, an assertion's detail). The 26 around-files pass,
632.
