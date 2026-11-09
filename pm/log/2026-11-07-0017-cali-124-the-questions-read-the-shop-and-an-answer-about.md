### 2026-11-07 · CALI-124 (#145) · The questions read the shop, and an answer about the shop goes to the shop
From Theo's bar stool run: the questions asked for the printer's bed size, which is the shop's, and his answer went
into the design's requirements, where *How do I make it?* couldn't use it.
- **The questions read the shop first** (`clarify.draft_questions(…, shop=)`): Claude is told the shop ("never ask
  about it"), and any question about a machine the shop knows states it instead (`with_shop`): "Your printer: 256 ×
  256 × 256 mm build volume, PLA, PETG. If this one's to be made on something else, say what." A question about the
  shop is tagged (`about: shop:printer`, from its words where Claude doesn't tag it).
- **A shop answer goes to the shop, on a yes** (`shop_offer`, `offers`, `take_offer`): it's never a design
  requirement; an answer the shop can take ("256 x 256 x 256 mm, PETG", "10 in", "4 x 8 ft", "a jigsaw and a drill")
  is offered under *Requirements*: "Add a 256 × 256 × 256 mm printer (PETG) to your shop?" with Add it / No. A yes
  writes `shop.yaml` through `shop.write` (the shop's own path; the same kind of machine is replaced); a no leaves the
  shop alone.
- **The design's requirements keep only design facts.** An old design's shop fact is left where it is; *How do I make
  it?* already reads the shop (`making.plan` → `shop.read()`), never the requirements.
- Tests: tests/test_shop_questions.py (8, stubbed: a fake asker or client, the shop a file in a temp folder; 7 fail
  without this).
- **#146 review:** only a question about *your* machine is the shop's ("your printer", "do you have a CNC router",
  "what tools do you have"), the machine it names first; a design question that names one ("How tall is the plasma
  cutter the cart carries?", "What nozzle diameter should the hose fitting take?", "Which router bit profile?") keeps
  its answer as a requirement: the reviewer's 5 probes, none lost. A shop answer that offers nothing is said ("I
  couldn't read a printer from 'Bambu X1C': add it to your shop by hand, or give its build volume with its units"),
  its answer kept as a requirement, and the note only dismissed. Only sizes said with their units make an offer ("X1C",
  "0.4 nozzle, 256 bed" don't; "150 x 150 mm" is mm, not inches); a bare "4x8" table is feet; the offer says its
  numbers and units. The first yes with no shop.yaml writes only the machine offered: the hand tools stay unsaid
  (`shop.read` assumes the default for a file with no `hand`, `hand_default`), never written as yours.
- **#146 review, round 2 (the foreman's call):** an offer never removes an answer. A "your …" answer that becomes a shop offer is kept as a requirement too ("your plasma cutter" still sizes the cart), and a no to the shop keeps it.
