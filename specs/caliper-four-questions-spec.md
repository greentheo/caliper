# Caliper V1 — four questions, two depths

*Companion to [`caliper-conversational-spec.md`](caliper-conversational-spec.md), which made the screen a
viewport and a conversation. This one reorganises what sits beside them: the right-hand side stops being
a shelf of tools and becomes the answers to four questions.*

---

## 1. Why

Theo, after walking through the strength check: *"the whole interface is a bit complicated (then again,
this is a complicated activity you know?) But I'm wondering about how we can organize things in such a
way that even my 6 year old can make something while still being useful for a real mechanical
engineer."*

Today the inspector is organised by **what Caliper can do**. Its sections are Size, Rules, Will it hold?,
Built from, Shape it for drag, whittle carving, Size the frame, Gusset plates, Cut plan, Scorecard,
Build package and History. Each is a tool with its own form, its own vocabulary (voxels, stations,
`construction()`) and its own idea of what the person wants. The Studies page (CALI-70) made them
findable, but it's still a list of tools.

A kid and an engineer don't want different things. They ask the same four questions, in the same order:

0. **What is it?**
1. **Will it work?**
2. **What do I buy?**
3. **How do I make it?**

They want the answers at different depths. The kid wants "it holds Dad, three times over". The engineer
wants to know that this is the top panel as a simply supported plate under a 4 in patch load, read as
4.8 MPa against 15 MPa across the grain, and that the voxel FEA agrees to within its noise. Both are
true, and the second is the first opened up.

**So: four questions, each answered in one line anyone can read, each opening into the engineer's layer
beneath it. The two readers see the same data at two depths. There are no modes.**

**Non-goals:**
- A kids' version. There's one interface; the top line is written so a kid can read it.
- Hiding the engine. Every number stays one click away, and the chat can always ask why.
- New studies. This is how the existing ones are reached and read.

---

## 2. The screen

```
┌ chat ───────────┬ viewport ───────────────────────┬ the four questions ─────────────┐
│                 │                                 │ step stool · v3                 │
│ the conversation│   the part, and whatever the    │                                 │
│ (unchanged)     │   open question is about:       │ ◉ What is it?                   │
│                 │   stress for "will it work",    │   A one-platform step stool,    │
│                 │   pieces for "what do I buy",   │   16 × 10 × 9 in, plywood.      │
│                 │   steps for "how do I make it"  │                                 │
│                 │                                 │ ✓ Will it work?                 │
│                 │                                 │   Holds Dad, 3 times over.      │
│                 │                                 │   Reaches the sink: 9 in up.    │
│                 │                                 │   ▸ the numbers                 │
│                 │                                 │                                 │
│                 │                                 │ $ What do I buy?                │
│                 │                                 │   1 sheet of 3/4 in plywood,    │
│                 │                                 │   glue, screws, paint · ~$45    │
│                 │                                 │   ▸ the numbers                 │
│                 │                                 │                                 │
│                 │                                 │ ✂ How do I make it?             │
│                 │                                 │   With a jigsaw and a drill:    │
│                 │                                 │   5 pieces, 9 steps, ~2 hours.  │
│                 │                                 │   [Print the patterns]          │
└─────────────────┴─────────────────────────────────┴─────────────────────────────────┘
```

*(The figures in the sketch are illustrative. Today the stool's shopping list is the plywood and the paint;
see "What do I buy?".)*

- **The right side is four cards,** always in this order, for whatever is selected: the whole design or
  one part. A card's **top line** is the answer: a verdict and the one or two numbers that carry it, in
  the person's units. A card with nothing to say yet says what to tell Caliper to fill it ("Not checked
  yet: say what it has to hold").
- **"▸ the numbers"** opens the engineer's layer under that card: today's panels, moved under the question
  they answer (§4). Once someone opens it, it stays open for them on every part and design, remembered in
  the browser. An engineer opens it once and lives there; a kid never has to.
- **The viewport follows the open card** (§5).
- **The chat is the steering wheel,** as now. Every top line is something you can ask about ("why only
  three times?"), and every "not yet" tells you what to say.

---

## 3. The four questions

Each question below lists its **top line** (anyone), **the numbers** (the engineer's layer), and
**where it comes from** today.

### What is it?
- **Top line:** the part's description (kept current after every revision, CALI-69), its size, and what
  it's made of. "A one-platform step stool, 16 × 10 × 9 in, from 3/4 in plywood."
- **The numbers:** the size box, its PARAMS (the dimensions you can change, with ranges), the requirements
  (stated or assumed), the rules locked in, the script and spec, every version and the history.
- **From:** Size, Requirements, Rules on this part, History, Advanced.

### Will it work?
One line per thing it has to do, each a verdict:
- "Holds Dad, 3 times over."
- "Reaches the sink: the top is 9 in up."
- "Clears the car by 2.1 in."

Green when it passes with room, amber when it passes close to the line, red when it fails. A requirement
nobody has checked yet says so and how to check it. The design-level card is the scorecard's checks.
- **The numbers:**
  - Each verdict opens into the study that made it: the plate check and the FEA (Will it hold?), the frame
    sizing, the drag study, the assertions behind "reaches the sink".
  - Each number carries how far to trust it, from the scorecard's trust tags: measured, a model on the
    safe side, rough, or a guess.
  - The Studies page (CALI-70) is this card's engineer layer for the whole design: every run, and what
    else could be checked.
- **Make it better** lives here as suggestions with a cost, not as tools. For example: "5/8 in plywood
  would also hold (2.2 times) and saves 1.4 lb" (from the plate check's thicknesses), "Lighten the sides:
  40% less plywood, still holds 2.6 times" (CALI-71), or "Cut drag 12% by tapering the tail" (the drag
  search, only for a design that moves through air, CALI-67). Picking one is a revision, through the chat.
- **From:** Will it hold?, Size the frame, Gusset plates, Shape it for drag, whittle carving, Design checks,
  the scorecard's checks, the Studies page.

### What do I buy?
- **Top line:** the shopping list in one or two lines, and what it costs: "1 sheet of 3/4 in plywood, wood
  glue, 24 × 1¼ in screws, a quart of paint — about $45." Also the weight, when it matters ("8.9 lb, easy
  for a kid to carry").
- **A gap today:** the list has the plywood and the paint but not the glue or the screws. `construction()`
  can list them as lumps, but the designer doesn't think to, and "glued and screwed" should come with a
  count of screws and how much glue. The prices are rough guesses too ($29 for a sheet of 3/4 in plywood);
  they're editable, and the numbers layer says where each came from.
- **The numbers:** every piece and what it weighs, the materials with their basis, the centre of gravity
  (and the hitch moment, when there's a hitch), offcuts and waste, the prices and where they came from, and
  the what-if pickers (another thickness, another material).
- **From:** Built from, Weight & balance, the scorecard's cost.

### How do I make it?
- **Top line:** made **with your tools.** The design knows what you have (CALI-48: a jigsaw and a drill,
  or a CNC router, or a plasma table), so the answer reads like this:

  > With a jigsaw and a drill: 5 pieces, 9 steps, about 2 hours.
  > [Print the patterns] [Project them] [Open the build book]

- **Every pattern comes in three forms for hand tools** (CALI-48, §6):
  1. **Measure and mark:** each piece drawn with its dimensions from two straight edges, so a ruler and a
     square lay it out on the board.
  2. **Print and tape:** the pieces at full size, tiled across letter or A4 pages with overlap marks, page
     numbers and a scale check printed on each page.
  3. **Project and trace:** a full-size pattern for a projector on the board, with a calibration square you
     size to the ruler before tracing.

  The CNC files (DXF and SVG) are the engineer's layer, not the front door.
- **The numbers:** the nesting and sheets used, kerf and tolerances, joint fits, tube end cuts, the assembly
  order with its pictures, and the release (build package) for this exact version.
- **From:** the cut plan, the build package, and the build book.

---

## 4. Where today's panels go

| Today | Becomes |
|---|---|
| Size, Requirements, Rules, History, Advanced | What is it? › the numbers |
| Will it hold? | Will it work? › "Holds Dad…" › the numbers |
| Size the frame, Gusset plates | Will it work? › "The frame holds…" › the numbers |
| Shape it for drag, whittle carving | Will it work? › make it better (only for a design that moves through air) |
| Design checks, Scorecard checks | Will it work? (the design's card) |
| Studies page | Will it work? › the numbers, for the whole design |
| Built from, Weight & balance, the scorecard's cost | What do I buy? |
| Cut plan, Build package | How do I make it? |

Nothing is deleted. Every panel keeps working and moves under the question it answers.

---

## 5. The viewport follows the question

| Open card | The viewport shows |
|---|---|
| What is it? | The part as built, with its dimensions on hover |
| Will it work? | Whatever made the verdict: the stress picture with the load and its arrow, the frame's tubes by safety, the clearance to the car in red or green |
| What do I buy? | The pieces, coloured by the sheet or stick each is cut from (today's "Show how it's built") |
| How do I make it? | The assembly steps, one at a time, as the build book draws them |

---

## 6. The words

- **Verdict first, numbers second.** "Holds Dad, 3 times over", not "safety factor 3.1".
- **The person's things, not ours.** "Dad", "the sink" and "the car" come from the requirements. Never
  "voxels", "construction()", "station" or "PARAMS" in a top line.
- **Their units:** inches and pounds, or millimetres and kilograms, as the design is set.
- **Honest about how sure.** A top line resting on a rough model says so in a word ("about"); the
  numbers layer says why.
- **One line, a sentence a 6-year-old can follow read aloud.** If it needs a second line, it's two
  verdicts.

---

## 7. How it's built

- **The server writes the top lines** (`answers.py`: `answers(store, part=None)` → four cards, each
  `{status, lines[], actions[], empty_hint}`), so the app, the CLI (`caliper answers`) and the build book
  say the same thing, and they can be tested without a browser.
- **The engineer layers are today's panels,** re-homed. `design.js` renders a card shell and drops the
  existing view functions (`loadView`, `buildView`, `cutplanView`…) inside "the numbers".
- **Verdicts come from what's already measured:** the scorecard's checks and trust tags, the strength runs,
  the frame runs, the BOM and costs, the cut plans. A card never runs a study to draw itself. A stale
  verdict says it's stale (the part has changed since) and offers to re-check.

---

## 8. Steps

1. **`answers.py` and the four cards,** each with its top line and "▸ the numbers" holding today's panels.
   Fasteners and glue join the shopping list. Done when the stool and the camper read right
   top-line-first, with nothing removed.
2. **Will it work? from the requirements** (CALI-55, #2): what the conversation says it must do becomes the
   lines of that card, including the ones not checked yet.
3. **How do I make it? with your tools** (CALI-48, #4): the hand-tool patterns of §3 (measure and mark, print
   and tape, project and trace).
4. **The viewport follows the card.**
5. **First run (CALI-59, #8)** lands on the four questions: one sentence in, four answers out.

---

## 9. Open questions for Theo

- **Who sets the tools?** The design ("this one's for the jigsaw") or the person ("I have a jigsaw and a
  drill")? Probably the person, with a per-design override.
- **Where prices come from:** today they're editable defaults in the scorecard's basis. Fine for V1?
- **Amber:** what counts as "close to the line"? Proposed: within 25% of the limit (a safety of 2 to 2.5
  when 2 is required).
- **The kid's reading level:** is "3 times over" right, or "it could hold three Dads"?
