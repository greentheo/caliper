### 2026-11-11 · CALI-157 (#223) · smaller edits, reworked

**Ask for a change that only touches a comment.** If the designer answers "make the top 20 thick" by editing the
comment `# the top`, the edit isn't taken as the revision. It goes back with: "those edits leave the code as it was
(only a comment or spacing changed, or each new is its old): change the code itself to do what's asked".

**A revision that never builds.** The design's log still gets a `revise` entry with `built: false`, and each try lists
its round, whether it was an edit, a failed edit (and why) or a rewrite, and how long it took.
