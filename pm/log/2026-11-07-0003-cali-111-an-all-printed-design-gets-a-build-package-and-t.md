### 2026-11-07 · CALI-111 (#112) · An all-printed design gets a build package, and the book weighs what the card does
- **`cutplan.run`** makes its run folder whatever the materials. An all-printed part's cut list says "Nothing to cut:
  it's all printed." (The release raised FileNotFoundError on the tube.)
- **The 1.6 lb vs 10.9 lb:** the same card on the bar stool's copy said `weight.i_want` 10.9 lb and `weight.total_lb`
  1.6 lb. `construction.balance()` left out every printed piece; `report()` weighs them (`with_printed`). So the
  book's ✓ was wrong and the design card's ✗ 10.9 lb right. `balance()` now weighs printed pieces too.
- **A card from the old scorer is out of date:** cards carry `scorer: 2`. `list_cards` marks an older one `outdated`,
  the release scores again rather than reuse it, and the page and design card say "score it again". The camper
  sample's shipped card is re-scored (its verdicts the same; waste $90.30 → $90.24 from older drift).
- `tests/test_printed_release.py` (4; all fail on main): the tube's package, the total against each part's weight, the
  book's numbers equal to the live card's for the same version (a weight goal it fails is ✗ in both), and an old card
  re-scored. design.js v=61.
- **#125 review:** a printed piece whose solid can't be made (the bar stool v7's throw, #126) fails soft: `with_printed`
  marks it unweighed, and that part's weight, the total and the hitch's are **unknown**, never the rest's; the weight
  check reads "not checked: the printed part's shape isn't closed (…)", the design card and the page say so, and
  `/balance` answers 200 with the note. No `was`/change against a card from an older scorer ("scored differently
  since"). `compute` says to bump `SCORER` when a metric's meaning changes.
