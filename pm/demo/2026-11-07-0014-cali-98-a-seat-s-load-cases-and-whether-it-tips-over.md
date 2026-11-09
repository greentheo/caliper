### 2026-11-07 · A seat's load cases, and whether it tips over (CALI-98 #86)
1. Open a seat whose script declares a tipping case (the guide's example: `"tip": True`, 600 N down 60 mm in from
   the front edge, 20 N forward at seat height): *Will it work?* says "Won't tip when someone sits on the front edge
   and leans, N times over" (or that it tips, and at what push), and that the pushes aren't yet checked by an engineer.
2. A seat that declares only "sitting" says "Not checked yet for a seat: leaning back …; sitting on the front edge;
   tipping over; buckling of the legs."
3. The designer's guide (`src/caliper/part_scripts.md`) has the load cases by kind of thing, each value cited.
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_tipping.py`.
