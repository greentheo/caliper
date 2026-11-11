### 2026-11-11 · CALI-157 (#223) · smaller edits, reworked

PR #232, after the review of 92d91b2.

- **One rule, one cache.** The shared system rule now says to output only the script's code, unless asked for edits,
  and then only the JSON asked for. The write and the edit still send the same system prompt, so its cache holds.
- **An edit has to change the code.** If the script's AST is the same after the edits (a comment, spacing, or an `old`
  equal to its `new`), it's a `NoEdit` with that reason and goes round again.
- **Edits don't chain.** Every `old` is looked up in the script as given, and overlapping edits are refused. The request
  says so.
- **JSON** is parsed with `strict=False`, so raw newlines in strings are read. A reply that still won't parse puts the
  real parse error in the retry.
- **The log.** Every revision's tries go on the design's log, each with its round, with `built` true or false, including
  a revision that never builds or raises.
- **The spec.** The edit request has the parameters and measured assertions the rewrite has (`_the_spec`).
- **Pinned:** a failed build's error reaches the next edit request, and a cut-off reply is a failed edit. All 12 mutants
  are caught.
