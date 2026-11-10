# Part scripts

A part is a Python file. Caliper runs it in its own process: `build(params)` makes the shape, and the
other names below say what studies, the bill of materials and the cut plan need to know about it. This
file is the reference for all of them, and the designer's prompt includes it word for word, so what
it says is what Claude is told.

All coordinates are millimetres, in the same frame as `build()` (the design's world frame, for a part
in a design with others). `cq` (cadquery) is available; use only it and the standard library, with no
file or network access.

## PARAMS and build(params) (required)

The first statement of the file, at module level and outside `build()`, is a dict of every key
dimension and shape choice, as finished numbers in mm. `build()` merges overrides into it:

```python
PARAMS = {
    "width": 406.4,    # 16 in
    "height": 304.8,   # 12 in
}

def build(params):
    p = {**PARAMS, **(params or {})}
    ...                # use p["..."] everywhere; never repeat those numbers inline
    return solid       # ONE watertight solid (a Workplane is fine)
```

Write `406.4`, not `16 * 25.4`, and put the inch value in a comment. A radius or chamfer of 0 means
"none" (skip the fillet). Every value in PARAMS must build: they are the part as it stands. Studies
search these numbers and write the ones they pick back into the script.

**No silent fallbacks.** A feature the person asked for either builds or raises with a clear message
(`raise ValueError("the 12.7 mm fillet doesn't fit a 14 mm flange")`): then the round fails and you fix
it, or say plainly why it can't be done. Never wrap a fillet, a cut or a union in `try/except` that
passes or hands back the shape without it, never return the input unchanged because a size came out
too small, and never clamp a requested size below what was asked (`min(p["fillet_r"], ...)`) without
raising. Caliper reads the script for each of these and fails the round, naming the line.

**A cone that runs to its apex** (`makeCone(r, 0, h)`, or a revolved profile that touches the axis) meshes with
one sliver of no area at the apex: the CAD's mesher fans the cone's triangles from it. Caliper leaves it out and
says so, but a cone that stops short of its point (a small top radius, or a flat cap) has none to leave out.

## What it's built from: BUILD and construction(params, build=None)

Write these for anything made from sheet goods, lumber or steel tube. They give the part its weight,
its centre of gravity, its bill of materials and its cut plan.

`BUILD` is a module-level dict of build choices: things that change the weight and the shopping list
but not the shape, such as a sheet's thickness (name those `*_t`) or which material the walls are.
`construction()` returns the pieces, one entry per piece someone cuts, named the way a builder would
say it ("left side", "top", "back rail"):

```python
BUILD = {"ply_t": 19.05}      # 3/4 in

def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    return [
        {"name": "top", "kind": "sheet", "material": "plywood", "thickness": b["ply_t"],
         "outline": [(x, y, z), ...], "covers": ["paint", "paint"]},
        {"name": "post", "kind": "stick", "material": "lumber", "size": "2x2", "a": (x, y, z), "b": (x, y, z)},
        {"name": "hinge", "kind": "lump", "mass": 0.3, "at": (x, y, z)},
    ]
```

- **sheet**: a panel cut from a sheet. `outline` is one face of the panel as it sits in the part, on
  the solid's surface, never its mid-plane: a flat polygon, its corners in order around the edge, with
  the panel's `thickness` behind it, going into the solid. A seat whose top is at z = H has its
  outline at z = H. A panel
  bent to a curve gives `facets` (a list of flat polygons) instead of `outline`. `covers` says what
  goes on its faces, one entry per face covered (`["paint"]` for the outside only).
- **stick**: a straight length from `a` to `b` along its centreline. Lumber by nominal `size`, or
  steel tube by `outer` (the square tube's outside width) and `wall`, with `"material": "steel"`.
- **covering**: a covering on its own, over an `outline` or `facets`, such as a patch.
- **printed**: the whole solid `build()` makes is 3D printed: `{"name": "blade", "kind": "printed",
  "material": "petg"}` (optional `"infill": 0.2`). Caliper weighs it from the solid (walls plus infill),
  fits it to the shop's printer (splitting it with pin holes if it's too big), and costs the filament.
  Give the solid as it prints: no separate pieces for a printed part.
  **Wood and printed in one part** (a plywood top on printed sides): list the sheets and sticks as usual,
  then one printed piece with `"rest": true`, such as `{"name": "sides", "kind": "printed", "material":
  "petg", "infill": 0.4, "rest": true}`. Everything in the solid that isn't a listed sheet or stick is
  printed: Caliper prints only that, weighs both, and checks the strength in both materials. Use it when
  the person asks for some parts printed and some cut from sheet; don't make the whole part printed.
- **lump**: anything else, by `mass` (kg) at a point `at`: hardware, glue, a battery.

The pieces are the part. After every revision Caliper builds the part and checks that what
`construction()` says matches what `build()` made, and a mismatch fails the round like any failing
measurement:

1. **Every piece lies in the solid.** A sheet's outline is on the solid's surface, a stick's centreline
   runs inside it. A sheet declared off its face is named and fails, because the solid left over it
   would otherwise be counted as printed.
2. **The pieces cover the solid.** Every part of the solid's surface is on some piece, so nothing in
   the shape is left out of the bill of materials.
3. **No more material than the shape holds.** The pieces' volume can't exceed the solid's by much (a
   wrong thickness or a piece listed twice).

With a printed `"rest"`, only the first applies: the printed piece is the rest of the solid by definition.

So model the shape as the pieces really are: a plywood stool's `build()` is its panels, each as thick
as the sheet; a foam-and-glass shell's `build()` is the shell.

## A welded tube frame: members(params) and supports(params)

A frame study sizes the tubes from these. `members()` lists every tube's centreline, split wherever
another tube joins it:

```python
def members(params):
    p = {**PARAMS, **(params or {})}
    return [{"name": "rail_left", "group": "rails", "a": (x, y, z), "b": (x, y, z),
             "outer": p["rail_w"], "wall": p["rail_t"], "size_params": ["rail_w", "rail_t"]}, ...]

def supports(params):
    return [{"at": (x, y, z), "fix": ["ux", "uy", "uz", "rx"]}, ...]
```

Ends closer than 1 mm are one joint. `group` is a set of tubes sized together; `size_params` are the
PARAMS a study writes a group's size into. A member with `"carries": True` takes the floor's load
(otherwise the `rails` group does). `supports()` are where it's held and what's held there
(`ux uy uz` displacements, `rx ry rz` rotations). `jacks(params)` lists jacks in the same form; a jack
only pushes. A frame is weighed from its members, so it needs no `construction()`.

Optional, at module level: `GUSSETS = {"corner": ("riser", "shank")}` names the joints that take
gusset plates (the two members meeting there); `LAYOUTS = {"X only": {"edges": 0}}` are what-if PARAMS
that change which tubes there are. Caliper writes `PLATES` itself when a plate study is adopted.

## What it must hold clear: keeps(params, build=None)

Boxes the shape must not cut into, like a mattress or the cargo:

```python
def keeps(params, build=None):
    return [{"name": "mattress", "note": "a queen, 60 x 80 in", "lo": (x, y, z), "hi": (x, y, z)}]
```

## What it must hold: loads(params, build=None) and held(params, build=None)

When the requirements say what it carries (a person standing on it, books on a shelf, a load it
lifts), declare it, and Caliper checks the part holds it (whittle's FEA, and a plate check for a
panel pushed on face-on):

```python
def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    cx, cy, top = p["width"] / 2, p["depth"] / 2, p["height"]
    return [{"name": "an adult stepping up", "lb": 200, "factor": 2.0,
             "lo": (cx - 50, cy - 50, top - 2), "hi": (cx + 50, cy + 50, top)}]
```

Each load is `name`; how much, as `lb` or `kg` (straight down) or `force` (`(fx, fy, fz)` in newtons);
`factor`, what it's multiplied by for the check (2 for someone stepping or jumping onto it, 1 for
a load that just sits there); and `lo`/`hi`, the corners of the box it pushes on, which must sit on
the part's surface (a box 2 mm deep on the face). Put a person's weight where it's hardest to carry:
one foot (about 4 x 4 in) in the middle of the widest span. A top or tread that rests on only two
sides (not held all round) is also stood on at its free front edge, where it's weakest: give it a
second load, "stepping on the front edge", the same foot mid-span with its edge on the free edge,
listed first (that's where people stand). A top held all round keeps the one centred foot. List more
than one when they're different situations (standing on the top, sitting on the edge); each is
checked on its own. Like
the pieces, the loads are checked after every revision: a load whose box doesn't touch the part fails
the round.

`held()` says where the part is held, as boxes of the same form (`name`, `lo`, `hi`). Leave it out for a
part that stands on the floor: Caliper holds it at its underside.

**The load cases, by kind of thing** (CALI-98). Declare every row that fits; each is checked on its own. Factor 2 for
stepping or jumping onto it, 1 for a load that just sits there; a standard's test load is already a test load, so it
takes 1. The values are as the engineering brief on Caliper's issue #42 cites them (NEEDS ENGINEER CHECK).

| kind | case | how to declare it |
|---|---|---|
| a step or tread | a foot at the centre | the person's `lb`, factor 2, a 4 x 4 in box mid-span |
| | a foot at the free front edge | the same foot with its edge on the free edge, factor 2 |
| a seat (stool, chair, bench) | sitting at the centre | the person's `lb`, factor 2 (sitting down drops onto it), a 4 x 4 in box at the middle |
| | sitting on the front edge | `force: (0, 0, -1300)` N, 100 mm in from the front edge, factor 1 (EN 12520 / EN 1728 seat static) |
| | leaning back | `force: (0, 400, -1000)` N front to back, or `(300, 0, -1000)` sideways, at seat level, factor 1 (EN 12520 / EN 1728 leg tests): a strength case |
| | climbing on | a foot on the seat: the person's `lb`, factor 2, at its edge |
| | tipping over | `"tip": True`, `force: (20, 0, -600)` N, 60 mm in from the seat's edge, at seat height, factor 1, one for each way it could go over (EN 1022:2005/2018, BIFMA X5.1 front stability) |
| a shelf or top | spread weight | what it holds, spread over it, factor 1 |
| | a point at the front edge | a hand's weight at the front edge, factor 2 |
| a step stool | its rating | EN 14183: 150 kg in all; its footprint at least the top plus 0.1 x its height each way |

A load with `"tip": True` isn't a strength case: Caliper checks it for tipping over, by statics, taking moments about
the edge of the footprint it would go over (the part's own weight and the downward push against the sideways one), and
the card says "Won't tip …, 1.6 times over" or that it will. Anything someone stands or sits on that's taller than its
base is wide gets one in each direction it could tip.

```python
def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    r, top = p["seat_d"] / 2, p["height"]
    return [{"name": "sitting", "lb": 250, "factor": 2.0, "lo": (-50, -50, top - 2), "hi": (50, 50, top)},
            {"name": "sitting on the front edge", "force": (0, 0, -1300), "factor": 1.0,
             "lo": (-50, -r + 50, top - 2), "hi": (50, -r + 150, top)},
            {"name": "leaning back", "force": (0, 400, -1000), "factor": 1.0,
             "lo": (-50, -50, top - 2), "hi": (50, 50, top)},
            {"name": "when someone sits on the front edge and leans", "tip": True, "force": (0, -20, -600),
             "factor": 1.0, "lo": (-10, -r + 50, top - 2), "hi": (10, -r + 70, top)}]
```

## Holes Caliper cuts: HOLES

When a lightening study is used, Caliper writes `HOLES` into the script: a list of holes cut all the way
through named panels, as data (`piece`, `normal`, `depth`, `polygons` on the panel's outline face). Caliper
cuts them from whatever `build()` returns and adds them to the named pieces, so don't cut them in `build()`
or list them in `construction()` yourself. Keep `HOLES` as it is. If you change a panel's size or move it,
say so in your reply: its holes were placed for the panel as it was, and the study should be run again.

## How far a search may go: RANGES

```python
RANGES = {"tail_len": (0.0, 900.0)}
```

The bounds a drag study may take each PARAMS number between. Numbers not listed are left alone.

## Walls and roofs that carry load: shell() and roof()

A part whose walls are structure (a foam core with skins) can describe them as deep beams for the
frame study, `shell(params, build=None)`, a list of
`{"name", "a", "b", "depth", "core", "core_t", "skins"}`, and its roof for the snow study,
`roof(params, build=None)`. Their fields are documented in `frame_study.wall_section` and `snow.py`.

## A picked face or edge

A request can begin "About this edge: … (at x, y, z mm in the script's coordinates): …". The person clicked that exact edge or
face, so change that one and no other.

For an edge, the point lies on it. Select it with `edge_at`, which is already in your script's namespace and measures true
distance to the edge:

```python
result = edge_at(result, (x, y, z)).fillet(r)
```

For a face, the point is its centre:

```python
result = result.faces(cq.selectors.NearestToPointSelector((x, y, z))).workplane(centerOption="CenterOfMass").hole(d)
```

Don't select an edge with `NearestToPointSelector` or a `">Z"`-style selector: concentric rings tie and it lands on another
edge. Do it at the step where that edge or face exists, after the bodies are joined and before anything removes it. `edge_at`
raises if no edge is at the point; let it.

## Keep them together

When you change `build()`, change the declarations with it. Move a panel or a tube in one and you
move it in the others; keep RANGES, keeps(), loads() and LAYOUTS true to the new shape.
