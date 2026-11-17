### 2026-11-17 · CALI-198 (#327) · say what a part must hold yourself, in the Scenarios editor

**A part whose script has no `loads()`.** Under *Will it work?*, "Will it hold?" now reads "It doesn't say what it must
hold yet: add a scenario below, or tell me…". *Say what it must hold* is still there (the designer's way), and so is
*Scenarios and supports*, with "Its script doesn't say what it must hold: add a scenario.".

**Add one.** Press *Add a scenario*. The words become "…: save yours to keep them.". Fill in what, how much, which way,
the margin and where (two corners, mm), then *Save them*. That's a new version, the same script. Then:
- *Check it holds* shows, and the card reads "Not checked yet: check it when it looks right.";
- the check runs on your case, and its results, *Check it again* and Lighten show as for a part whose script says them;
- a part built as a solid block round its pieces says so ("not trusted: a solid with more in it than its pieces"), as a
  part with `loads()` does.

*Back to its script's* takes the case out: the part says it has none again.

**Tried on** a scratch copy of the camper sample's cargo box, on 8016: "two people lying on the mattress, 400 lb × 2" on
the floor saved as v15 and checked.

**Offline:** `python -m pytest tests/test_scenarios_no_loads.py`.
