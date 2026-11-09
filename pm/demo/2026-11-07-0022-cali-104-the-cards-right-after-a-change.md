### 2026-11-07 · The cards right after a change (CALI-104 #97)
1. Open the bar stool (a copy) and change something in the chat ("make the seat 2% wider"). The cards redraw in a few
   seconds, not twenty: *How do I make it?* says "Print it in PETG: 3 pieces; print time: working it out…", then
   fills in the hours on its own.
2. A print-time goal says "print time: working it out…" until then, never a number.
3. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_cards_speed.py`.
