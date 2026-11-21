### 2026-11-20 · CALI-214 (#357) · Lighten's thinner rows scale the FEA's worst as a panel in bending

From #354's thickness-power audit; the foreman's call, as its own PR. `lighten._thinner` scaled the FEA's worst safety
by ratio (t/t0). That's right for a wall in compression, where stress goes as 1/t. But the FEA's number is the part's
worst, wherever it is, and for a panel in bending (a panel stood on) stress goes as 1/t². So the estimate read high.

**The fix:** ratio² for the FEA's worst, the safe side. Estimates only move down.

**Pinned** (`tests/test_thinner_fea.py`): a plate-governed case (its plate clear, at 50) whose FEA worst is 8.0, on the
synthetic two-stock part:
- at 1½ in it reads 4.5, not 6.0;
- at 1 in it reads 2.0, not 4.0.

**Fail first:** 6.0 against 4.5, on #354's head (c2184fe), before the rebuild onto main.

**Theo's step-stool-5**, on copies of today's part:
- As drawn it fails at once on #344's joints (✗ 1.5), so Lighten stops at its first step with no thinner row.
- So the copy took the strength check's own JOINTS fix-it from Things to fix: three #8s at each front rail end. It then
  holds at 2.15, governed by the plate check.

| | main (7d36438) | this |
|---|---|---|
| Lighten steps | 10, the lightest holding 4.92 lb | the same |
| thinner ⅝ in | ✗ 1.49, 5.78 lb | **the same** |

That one row is governed by the plate check at ⅝ in, not by the FEA's estimate, so nothing of Theo's moves. Copies
deleted.

Rebuilt on fresh main (7d36438) once #354 merged.

**Mutant:** the FEA's worst back at ratio¹, caught (the fail-first above).
**Area tests:** test_thinner_fea, test_lighten_own_material and test_lighten, green. **Full suite: CI**, under load (the
foreman's crew-wide rule, 11-20).
