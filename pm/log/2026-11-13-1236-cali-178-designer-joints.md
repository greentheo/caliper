### 2026-11-13 · CALI-178 (#284) · #222 slice D: the designer's joint rules, the shop's joint tools, and a pick that names a joint

The foreman asked for slice D on 2026-11-13. It needs nothing from Theo, and it's built on a fresh branch from main.

- **The shop's joint tools:** `table saw`, `pocket-hole jig` and `doweling jig` join `shop.HAND`. That's code only: no `shop.yaml` was touched. The app's shop panel and the clarifier read `HAND`, so they offer them.
  - `shop.JOINT_TOOLS` says what makes each joint:
    - bevel: a circular saw or a table saw;
    - mitre: those or a chop saw;
    - rabbet and dado: a table saw or a router;
    - pocket screw: a pocket-hole jig;
    - dowel: a doweling jig;
    - printed connector: a 3D printer;
    - through tenon and notch: a jigsaw or a router;
    - butt and glue block: nothing special.
  - `joint_needs` and `joint_kinds` read it.
- **The round fails a joint the shop can't make.** `joints.check` adds "JOINTS makes the side and the top a rabbet, which needs a table saw or a router, and your shop hasn't got one: choose a joint it can make, or say what it needs".
- **The designer:**
  - **The guide:** `part_scripts.md` gets "How its pieces join: JOINTS": the format from §1, and §3's rules in order (bearing first; sideways load through face glue; never pull a screw out of an edge; a splay or a rack needs a tie; the shop decides what's possible). Where the strong joint needs a missing tool, the designer is to say so: "a dado would carry this in glue; it needs a router or table saw".
  - **The prompt:** it ends with "Your shop": the tools, "Joints it can make: …", and "Not without another tool: rabbet and dado (a table saw or a router); …".
- **A pick names a joint (#177):**
  - **Naming:** `joints.namer(store, pid)` names the joint a point lies on, where it's within twice the tolerance of both pieces and they touch. A corner where three pieces meet is no one joint.
  - **The chip:** the features route says a seam's edge as "joint between the side and the top: the line …", so the chip and the request say it. An inside corner where one piece meets another is a real edge in the joined solid; a flush outside seam isn't one, so it can't be picked.
  - **The turn:** "make that a rabbet" on a picked seam tells the designer that pair's entry, kind and `at`.
  - **The check (`joints.landed`):**
    - **landed:** the entry has that kind, the pieces still touch, and a rabbet or dado shows as the step (`joints.sunk`: one piece's edge runs into the other's thickness);
    - **missed:** the entry is unchanged ("✗ The joint between the side and the top is still a butt (assumed): its JOINTS entry didn't change"), and the turn isn't a success;
    - **couldn't tell:** anything else, such as the entry saying rabbet with no step in the pieces.
- **Done-when**, on a synthetic corner (a side under a top): "About this joint between the side and the top: make that a rabbet" reaches the designer as that entry. The rabbet lands and is checked: "Checked: the joint between the side and the top is now a rabbet, 6 mm deep."

**Tests:** `tests/test_joint_picks.py`, 17 tests on synthetic parts (a corner, and one with a rail) and a scratch shop. They fail on main (no `joints.NOT_MEASURED`).
- One assertion was wrong in my first draft: it expected inches from a millimetre design.
- 16 mutants, all caught.
- **Around run:** the 56 test files around these changes pass.

**Not done:** a flush outside seam (two faces in one plane) isn't an edge to pick; picking it falls back to the face. The JOINTS rules are the designer's instructions; only the shop rule is checked by the round, and slice B checks the rest.
