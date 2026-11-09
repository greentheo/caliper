### 2026-10-29 · Will it hold Dad? And every study on one page (CALI-54 #1, CALI-70 #31)
1. `make serve`, open **A step stool so my 6-year-old…**, click the stool, and say *"It has to hold me too:
   200 lb, stepping up onto the top."* It comes back as a revision (v3) with what it must hold, and the reply
   says it's checked under **Will it hold?**.
2. In the stool's panel, **Will it hold? → Check it holds** (about 15 s; whittle needs only to be installed,
   not running). It holds at **3.1x**: the plate check on the top, with the grain the wrong way (6.2x the right
   way), and where the FEA says it works hardest. The viewport shows the stress, red under the foot, with
   the load's box and an arrow. **Other thicknesses** says 5/8 in would still hold and 1/2 in wouldn't.
3. **Studies** (header): what each part can run and why the rest can't yet, and every run so far. **Open** on
   the strength row goes straight back to the stress picture.
4. Offline: `python -m pytest tests/test_load_study.py tests/test_studies.py`.
