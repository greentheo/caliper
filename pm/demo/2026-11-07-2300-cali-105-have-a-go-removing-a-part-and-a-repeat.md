### 2026-11-07 · "Have a go", removing a part, and a repeat (CALI-105 #98)
1. Accept a proposed rule that doesn't hold yet: the reply ends "Tell me to have a go." Type **have a go**: it revises
   that part to meet the rule, never builds a new one.
2. Type **remove the carriage**: "Remove carriage? Its files go to the design's trash, so it can be put back." Say
   **yes**: it's gone from the design and the cards. Type **put back carriage**: it's back as it was.
3. Send the same change twice ("make the carriage 10 mm wider"): the second time it asks "v2 already did that … Do it
   again, on top of v2?".
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_have_a_go.py`.
