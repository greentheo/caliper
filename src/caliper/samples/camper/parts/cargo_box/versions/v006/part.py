PARAMS = {
    "width":      1955.8,   # 77 in: a 75 in twin mattress plus a 1 in wall each side
    "depth":      1016.0,   # 40 in: a 38 in mattress plus a 1 in wall front and back
    "height":     1041.4,   # 41 in
    "x_front":    -457.2,   # -18 in  (front face x)
    "z_bottom":    457.2,   # 18 in   (floor z)
    "wall_h":      304.8,   # 12 in   (full-width side wall above the floor; the mattress must stay under it)
    "tumble":        0.0,   # roof edges drawn in from the full width, each side, the whole length (mm)
    "shoulder":      1.0,   # side from wall top to roof edge: 1 = straight, 2 = round
    "nose_len":      0.0,   # how far back from the front the front edges round off (mm); 0 = square
    "nose_pinch":    0.0,   # each side draws in this much more at the front face, above the walls (mm)
    "tail_len":      0.0,   # how much of the back tapers (mm); 0 = plain box
    "tail_drop":     0.0,   # top falls this much at the very back (mm)
    "tail_pinch":    0.0,   # each side draws in this much more at the very back, above the walls (mm)
    "tail_curve":    1.0,   # 1 = straight panels; 2 = teardrop curve
}

# How far a drag study may take each number. wall_h can't come down past the mattress (see keeps());
# the rest are as far as still makes a box.
RANGES = {
    "wall_h":     (170.0, 610.0),   # 6.7 to 24 in
    "tumble":     (0.0, 300.0),
    "shoulder":   (1.0, 2.5),
    "nose_len":   (0.0, 400.0),
    "nose_pinch": (0.0, 300.0),
    "tail_len":   (0.0, 800.0),
    "tail_drop":  (0.0, 400.0),
    "tail_pinch": (0.0, 300.0),
}

# The section is the same everywhere: a full-width base (floor to wall_h) that the mattress sits in, then
# the sides lean in to the roof. Along the length it rounds off at the front (nose_*) and tapers at the
# back (tail_*). build() lofts it; construction() cuts the same surfaces into panels.
_SHOULDER_PTS = 9          # points along each shoulder curve
_NOSE_STATIONS = 8
_TAIL_STATIONS = 8


def _stations(p):
    """x positions to put a section at, front to back."""
    import math

    xf, d = p["x_front"], p["depth"]
    xb = xf - d
    xs = {round(xf, 6), round(xb, 6)}
    nl, tl = min(p["nose_len"], d), min(p["tail_len"], d)
    if nl >= 1.0 and p["nose_pinch"] > 0:
        for i in range(1, _NOSE_STATIONS + 1):          # bunched toward the front, where it curves most
            xs.add(round(xf - nl * (1 - math.cos(i / _NOSE_STATIONS * math.pi / 2)), 6))
    if tl >= 1.0:
        for i in range(_TAIL_STATIONS):
            xs.add(round(xb + tl * i / _TAIL_STATIONS, 6))
    return sorted((x for x in xs if xb - 1e-6 <= x <= xf + 1e-6), reverse=True)


def _section(p, x):
    """(roof half-width, roof z) at world x: how far the shape has drawn in there."""
    import math

    hw, h, zb, xf, d = p["width"] / 2.0, p["height"], p["z_bottom"], p["x_front"], p["depth"]
    xb = xf - d
    inset, roof = p["tumble"], h
    nl = min(p["nose_len"], d)
    if nl >= 1.0 and xf - x < nl:
        u = 1.0 - (xf - x) / nl                        # 1 at the front face, 0 where the nose ends
        inset += p["nose_pinch"] * (1.0 - math.sqrt(max(0.0, 1.0 - u * u)))
    tl = min(p["tail_len"], d)
    if tl >= 1.0 and x < xb + tl:
        t = (xb + tl - x) / tl                         # 0 where the taper starts, 1 at the back
        inset += p["tail_pinch"] * t ** p["tail_curve"]
        roof -= p["tail_drop"] * t ** p["tail_curve"]
    roof = max(roof, p["wall_h"] + 25.4)
    return max(hw - inset, 0.25 * hw), zb + roof


def _shoulder(p, hr, zr):
    """Points up one side, from the top of the full-width wall to the roof edge (y >= 0)."""
    import math

    hw, zw, n = p["width"] / 2.0, p["z_bottom"] + p["wall_h"], max(p["shoulder"], 0.5)
    pts = []
    for i in range(_SHOULDER_PTS):
        th = i / (_SHOULDER_PTS - 1) * math.pi / 2
        c, s = max(math.cos(th), 0.0), max(math.sin(th), 0.0)
        pts.append((hr + (hw - hr) * c ** (2.0 / n), zw + (zr - zw) * s ** (2.0 / n)))
    pts[0], pts[-1] = (hw, zw), (hr, zr)
    return pts


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}
    hw, zb, zw = p["width"] / 2.0, p["z_bottom"], p["z_bottom"] + p["wall_h"]

    def wire(x):
        hr, zr = _section(p, x)
        right = _shoulder(p, hr, zr)
        left = [(-y, z) for y, z in reversed(right)]
        V = lambda y, z: cq.Vector(x, y, z)            # noqa: E731
        edges = [cq.Edge.makeLine(V(-hw, zb), V(hw, zb)),
                 cq.Edge.makeLine(V(hw, zb), V(hw, zw))]
        straight = abs(hw - hr) < 0.5 or abs(p["shoulder"] - 1.0) < 1e-6
        edges.append(cq.Edge.makeLine(V(*right[0]), V(*right[-1])) if straight
                     else cq.Edge.makeSpline([V(*q) for q in right]))
        edges.append(cq.Edge.makeLine(V(hr, zr), V(-hr, zr)))
        edges.append(cq.Edge.makeLine(V(*left[0]), V(*left[-1])) if straight
                     else cq.Edge.makeSpline([V(*q) for q in left]))
        edges.append(cq.Edge.makeLine(V(-hw, zw), V(-hw, zb)))
        return cq.Wire.assembleEdges(edges)

    wires = [wire(x) for x in _stations(p)]
    return cq.Workplane("XY").add(cq.Solid.makeLoft(wires, ruled=True))


# What the box has to hold, whatever its shape: a twin mattress (75 x 38 x 6 in) lying on the floor, inside
# the walls. A drag study keeps the outside of the box out of these boxes; Caliper checks them too.
MATTRESS = (1905.0, 965.2, 152.4)    # long (across the car), wide (fore and aft), thick — mm


def keeps(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    long_, wide, thick = MATTRESS
    wt, ft = b["walls_t"], b["floor_t"]
    xc, zb = p["x_front"] - p["depth"] / 2.0, p["z_bottom"]
    return [{"name": "mattress", "note": "a 75 x 38 x 6 in twin on the floor, and the 1 in walls around it",
             "lo": (xc - wide / 2 - wt, -long_ / 2 - wt, zb), "hi": (xc + wide / 2 + wt, long_ / 2 + wt, zb + ft + thick)}]


# How it's built — these change the weight and the bill of materials, not the shape (Caliper reads
# them with construction() below; a drag study of PARAMS still applies whatever they are).
BUILD = {
    "floor":       "plywood",  # the floor: one full-size panel, the walls stand on it
    "floor_t":       9.525,    # 3/8 in
    "floor_under": "paint",    # sealer under the floor ("none" to skip)
    "walls":       "xps",      # walls and roof
    "walls_t":      25.4,      # 1 in
    "skin_out":    "pmf",      # outside of the walls and roof: canvas + glue + paint
    "skin_in":     "none",     # inside of the walls and roof
    "posts":       "2x2",      # a post in each corner, inside the foam ("none" to leave out)
    "allowance":     1.4,      # kg (~3 lb): glue, screws, hinges and trim
}


def construction(params, build=None):
    """The pieces of the box: a plywood floor, foam walls standing on it, a foam shell over the top.

    Front and back are flat panels cut to the section there, inside the shell. The sides are flat,
    full-width strips from the floor to wall_h; above them the shoulders and roof are one shell, bent
    (kerfed, or laid up in strips) wherever the shape curves. Faces are on the outside surface, in world
    mm; Caliper weighs them and makes the bill of materials.
    """
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    hw, d, xf, zb = p["width"] / 2.0, p["depth"], p["x_front"], p["z_bottom"]
    xb, zw = xf - d, zb + p["wall_h"]
    ft, wt = b["floor_t"], b["walls_t"]
    z0 = zb + ft                               # walls stand on the floor
    skin = [s for s in (b["skin_out"], b["skin_in"]) if s != "none"]

    def foam(name, outline=None, facets=None):
        out = {"name": name, "kind": "sheet", "material": b["walls"], "thickness": wt, "covers": skin}
        out.update({"outline": outline} if outline else {"facets": facets})
        return out

    def right_side(x):                         # the shoulder at x, wall top to roof edge (y >= 0)
        return _shoulder(p, *_section(p, x))

    items = [{"name": "floor", "group": "floor", "kind": "sheet", "material": b["floor"], "thickness": ft,
              "outline": [(xf, -hw, zb), (xb, -hw, zb), (xb, hw, zb), (xf, hw, zb)],
              "covers": [b["floor_under"]]}]

    for name, x in (("front", xf), ("back", xb)):
        top = [(max(y - wt, 0.0), z - wt) for y, z in right_side(x)[1:]]      # in from the shell
        pts = [(x, -hw, z0), (x, hw, z0), (x, hw, zw)] + [(x, y, z) for y, z in top]
        pts += [(x, -y, z) for y, z in reversed(top)] + [(x, -hw, zw)]
        items.append(foam(name, pts))
    for side, s in (("left", 1.0), ("right", -1.0)):
        items.append(foam(f"side_{side}", [(xf - wt, s * hw, z0), (xb + wt, s * hw, z0),
                                           (xb + wt, s * hw, zw), (xf - wt, s * hw, zw)]))

    xs = _stations(p)
    shell = {"shoulder_left": [], "roof": [], "shoulder_right": []}
    for x0, x1 in zip(xs, xs[1:]):
        r0, r1 = right_side(x0), right_side(x1)
        for k in range(len(r0) - 1):
            a0, a1, c0, c1 = r0[k], r0[k + 1], r1[k], r1[k + 1]
            if max(abs(a0[0] - a1[0]), abs(a0[1] - a1[1]), abs(c0[0] - c1[0]), abs(c0[1] - c1[1])) < 1e-6:
                continue
            for name, s in (("shoulder_left", 1.0), ("shoulder_right", -1.0)):
                shell[name].append([(x0, s * a0[0], a0[1]), (x1, s * c0[0], c0[1]),
                                    (x1, s * c1[0], c1[1]), (x0, s * a1[0], a1[1])])
        (y0, zr0), (y1, zr1) = r0[-1], r1[-1]
        shell["roof"].append([(x0, -y0, zr0), (x0, y0, zr0), (x1, y1, zr1), (x1, -y1, zr1)])
    for name, quads in shell.items():
        items.append(foam(name, quads[0]) if len(quads) == 1 else foam(name, facets=quads))

    if b["posts"] != "none":
        half = 0.75 * 25.4
        c = wt + half                          # post centre: in from the outside by the foam + half a 2x2
        for name, x in (("front", xf - c), ("back", xb + c)):
            # a post's top is cut on a bevel to meet the shell: its centre reaches where the shell has
            # come in by half a post
            right, reach = right_side(x), hw - half
            top = right[-1][1] - wt
            for (ya, za), (yb, zb_) in zip(right, right[1:]):
                if yb < reach:
                    top = za + (zb_ - za) * (ya - reach) / max(ya - yb, 1e-9) if ya > reach else za
                    break
            for side, s in (("left", 1.0), ("right", -1.0)):
                items.append({"name": f"post_{name}_{side}", "kind": "stick", "material": "lumber",
                              "size": b["posts"], "a": (x, s * (hw - c), z0), "b": (x, s * (hw - c), top)})
    if b["allowance"]:
        items.append({"name": "glue, screws & hardware", "kind": "lump", "mass": b["allowance"],
                      "at": (xf - d / 2.0, 0.0, zb + p["height"] / 2.0)})
    return items
