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

- **sheet**: a panel cut from a sheet. `outline` is one face of the panel as it sits in the part: a
  flat polygon, its corners in order around the edge, with the panel's `thickness` behind it. A panel
  bent to a curve gives `facets` (a list of flat polygons) instead of `outline`. `covers` says what
  goes on its faces, one entry per face covered (`["paint"]` for the outside only).
- **stick**: a straight length from `a` to `b` along its centreline. Lumber by nominal `size`, or
  steel tube by `outer` (the square tube's outside width) and `wall`, with `"material": "steel"`.
- **covering**: a covering on its own, over an `outline` or `facets`, such as a patch.
- **lump**: anything else, by `mass` (kg) at a point `at`: hardware, glue, a battery.

The pieces are the part. After every revision Caliper builds the part and checks that what
`construction()` says matches what `build()` made, and a mismatch fails the round like any failing
measurement:

1. **Every piece lies in the solid.** A sheet's outline sits inside the solid or on its surface; a
   stick's centreline runs inside it.
2. **The pieces cover the solid.** Every part of the solid's surface is on some piece, so nothing in
   the shape is left out of the bill of materials.
3. **No more material than the shape holds.** The pieces' volume can't exceed the solid's by much (a
   wrong thickness or a piece listed twice).

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
one foot (about 4 x 4 in) in the middle of the widest span. List more than one when they're
different situations (standing on the top, sitting on the edge); each is checked on its own. Like
the pieces, the loads are checked after every revision: a load whose box doesn't touch the part fails
the round.

`held()` says where the part is held, as boxes of the same form (`name`, `lo`, `hi`). Leave it out for a
part that stands on the floor: Caliper holds it at its underside.

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

## Keep them together

When you change `build()`, change the declarations with it. Move a panel or a tube in one and you
move it in the others; keep RANGES, keeps(), loads() and LAYOUTS true to the new shape.
