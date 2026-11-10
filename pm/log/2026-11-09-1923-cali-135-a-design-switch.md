### 2026-11-09 · CALI-135 (#168) · Choosing another design while the first is loading
Found re-checking #161: a slow first design landed last and overwrote the state, so one page showed one design's tree and
heading and sent messages to the other.
- **`S.design` only holds the open design:** an answer for one no longer open is dropped, whichever call brought it, a
  chat's rename or a POST as well as an open or refresh. `openDesign` and `refresh` stop there, drawing nothing.
- **What arrives late isn't drawn:** a part's mesh and its pieces landing after the switch are dropped. That's the pieces
  race from #161's review (two designs can share a part's id and version).
- Tests: tests/test_design_switch.py (9). Five mutants each fail. In the browser, on two scratch designs with the first held
  back 3 s: the page ended on the second, heading and dropdown agreeing.
- **#173 review:** while a design loads the page isn't the old one: the new name at once, the model, tree and thread gone, "loading…", and the chat off until it lands, so a message can't go to a design other than the one on screen.
