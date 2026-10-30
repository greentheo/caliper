PARAMS = {
    "width":      1955.8,   # 77 in: a 75 in twin mattress plus a 1 in wall each side
    "depth":      1016.0,   # 40 in: a 38 in mattress plus a 1 in wall front and back
    "height":     1041.4,   # 41 in
    "x_front":    -76.2,   # -3 in  (front face x: 3 in behind the bumper)
    "z_bottom":    457.2,   # 18 in   (floor z)
    "wall_h":      176.3,   # 12 in   (full-width side wall above the floor; the mattress must stay under it)
    "tumble":        51.8,   # roof edges drawn in from the full width, each side, the whole length (mm)
    "shoulder":      1.4,   # side from wall top to roof edge: 1 = straight, 2 = round
    "nose_len":      399.6,   # how far back from the front the front edges round off (mm); 0 = square
    "nose_pinch":    297.6,   # each side draws in this much more at the front face, above the walls (mm)
    "tail_len":      662.1,   # how much of the back tapers (mm); 0 = plain box
    "tail_drop":     159.4,   # top falls this much at the very back (mm)
    "tail_pinch":    228.3,   # each side draws in this much more at the very back, above the walls (mm)
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


def shell(params, build=None):
    """The walls as deep beams, for a frame study: the skins carry the bending, the foam the shear.

    The box is a foam sandwich glued to its floor, so it carries itself to wherever it's held. As beams
    along the floor's edges: front and back span across between the corners, the sides front to back.
    Near the corners the front and back are only as deep as the full-width wall (the shoulders curve in
    above it), so each is three beams — shallow ends, full height in the middle. Depths are floor to roof.
    """
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    hw, d, xf, zb, wall_h = p["width"] / 2.0, p["depth"], p["x_front"], p["z_bottom"], p["wall_h"]
    xb = xf - d
    skins = [s for s in (b["skin_out"], b["skin_in"]) if s != "none"]

    def beam(name, a, bb, depth):
        return {"name": name, "a": a, "b": bb, "depth": depth, "skins": skins,
                "core": b["walls"], "core_t": b["walls_t"]}

    out = []
    for name, x in (("front", xf), ("back", xb)):
        hr, zr = _section(p, x)
        full, haunch = zr - zb, hw - hr
        if haunch < 25.4:
            out.append(beam(f"wall_{name}", (x, -hw, zb), (x, hw, zb), full))
            continue
        end = (wall_h + full) / 2.0            # the shoulder's depth, on average, over its width
        corners = [beam(f"wall_{name}_right", (x, -hw, zb), (x, -hr, zb), end),
                   beam(f"wall_{name}_left", (x, hr, zb), (x, hw, zb), end)]
        if name == "front" and b["corner_patch"] != "none":
            for c in corners:
                c["skins"] = skins + [b["corner_patch"]]
        out += [corners[0], beam(f"wall_{name}", (x, -hr, zb), (x, hr, zb), full), corners[1]]
    xs = _stations(p)
    side = sum(_section(p, x)[1] - zb for x in xs) / len(xs)      # roof height along the side, on average
    for name, y in (("left", hw), ("right", -hw)):
        out.append(beam(f"wall_{name}", (xf, y, zb), (xb, y, zb), side))
    return out


# How it's built — these change the weight and the bill of materials, not the shape (Caliper reads
# them with construction() below; a drag study of PARAMS still applies whatever they are).
BUILD = {
    "floor":       "plywood",  # the floor: one full-size panel, the walls stand on it
    "floor_t":       9.525,    # 3/8 in
    "floor_under": "paint",    # sealer under the floor ("none" to skip)
    "walls":       "xps",      # walls and roof
    "walls_t":      25.4,      # 1 in
    "skin_out":    "fiberglass",      # outside of the walls and roof
    "skin_in":     "none",     # inside of the walls and roof
    "frame_posts": "1x2",      # the box inside the box: a frame at the front and back ("none" to leave out)
    "roof_beams":    3,        # beams under the roof, for snow (0 = none)
    "roof_beam":   "2x2",      # their size
    "roof_beam_dir": "across",   # front to back (rail to rail), or across (side to side)
    "corner_patch": "glass_patch",  # one more layer of glass over the front wall's corners, where it works hardest
    "allowance":     1.4,      # kg (~3 lb): glue, screws, hinges and trim
}

# Named choices for the entries Caliper can't guess.
BUILD_OPTIONS = {"roof_beams": [0, 1, 2, 3, 4], "roof_beam_dir": ["fore-aft", "across"],
                 "frame_posts": ["none", "2x2", "1x2"], "roof_beam": ["none", "2x2", "1x2", "2x3"],
                 "corner_patch": ["none", "glass_patch"]}


def roof(params, build=None):
    """How the roof is built, for a snow check: its plan inside the shell, its layers, what holds it up."""
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    wt, xf = b["walls_t"], p["x_front"]
    xb = xf - p["depth"]
    hd = {"2x2": 38.1, "1x2": 38.1, "2x3": 63.5, "2x4": 88.9}.get(b["frame_posts"], 38.1) / 2.0
    ys = sorted(_section(p, x)[0] - wt for x in _stations(p))
    ends = [_section(p, x)[0] - wt for x in (xf - wt - hd, xb + wt + hd)]
    framed = b["frame_posts"] != "none"
    return {"length": (xf - wt - hd) - (xb + wt + hd), "width": 2 * ys[len(ys) // 2],
            "rail_size": b["frame_posts"] if framed else None,
            "rail_span": 2 * (min(ends) - hd) if framed else None,
            "beams": {"count": int(b["roof_beams"]) if b["roof_beam"] != "none" else 0,
                      "size": b["roof_beam"], "dir": b["roof_beam_dir"]},
            "skins_out": [b["skin_out"]] if b["skin_out"] != "none" else [],
            "skins_in": [b["skin_in"]] if b["skin_in"] != "none" else [],
            "core": b["walls"], "core_t": wt}


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

    def skeleton(p, b):
        """The box inside the box: at the front and back, a bottom rail on the floor, two posts where the
        end panel is flat, and a top rail under the roof's edge; and the roof beams between them."""
        if b["frame_posts"] == "none":
            return []
        lumber = {"2x2": 38.1, "1x2": 38.1, "2x3": 63.5, "2x4": 88.9}       # depth on edge, mm
        hd = lumber[b["frame_posts"]] / 2.0
        out = []

        def stick(name, size, a, bb):
            out.append({"name": name, "kind": "stick", "material": "lumber", "size": size, "a": a, "b": bb})

        ends = {}
        for name, x in (("front", xf - wt - hd), ("back", xb + wt + hd)):
            hr, zr = _section(p, x)
            yu, zu = hr - wt, zr - wt                  # inside the shell: the roof's underside
            ends[name] = (x, yu, zu)
            stick(f"rail_{name}_bottom", b["frame_posts"], (x, -(hw - wt), z0 + hd), (x, hw - wt, z0 + hd))
            stick(f"rail_{name}_top", b["frame_posts"], (x, -yu, zu - hd), (x, yu, zu - hd))
            for side, s in (("left", 1.0), ("right", -1.0)):
                stick(f"post_{name}_{side}", b["frame_posts"], (x, s * (yu - hd), z0 + 2 * hd),
                      (x, s * (yu - hd), zu - 2 * hd))
        n = int(b["roof_beams"]) if b["roof_beam"] != "none" else 0
        bd = lumber.get(b["roof_beam"], 38.1) / 2.0
        (xa, ya, za), (xz, yz, zz) = ends["front"], ends["back"]
        if n and b["roof_beam_dir"] == "fore-aft":
            lim = min(ya, yz) - hd
            xt = xb + p["tail_len"] if p["tail_len"] >= 25.4 else xz          # where the roof starts to drop
            for j in range(n):
                y = -lim + (j + 1) * 2 * lim / (n + 1)
                if xz + 1.0 < xt < xa - 1.0:
                    zt = _section(p, xt)[1] - wt
                    stick(f"beam_{j + 1}", b["roof_beam"], (xa, y, za - bd), (xt, y, zt - bd))
                    stick(f"beam_{j + 1}_tail", b["roof_beam"], (xt, y, zt - bd), (xz, y, zz - bd))
                else:
                    stick(f"beam_{j + 1}", b["roof_beam"], (xa, y, za - bd), (xz, y, zz - bd))
        elif n:
            for j in range(n):
                x = xa + (j + 1) * (xz - xa) / (n + 1)
                hr, zr = _section(p, x)
                stick(f"beam_{j + 1}", b["roof_beam"], (x, -(hr - wt), zr - wt - bd), (x, hr - wt, zr - wt - bd))
        return out

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
    # The shoulders are cut in bands that run front to back, one per facet of the shoulder curve, glued
    # edge to edge like a strip-built hull: each band bends only along its length, so it lays flat for
    # cutting. The roof is one panel.
    shell = {}
    for x0, x1 in zip(xs, xs[1:]):
        r0, r1 = right_side(x0), right_side(x1)
        for k in range(len(r0) - 1):
            a0, a1, c0, c1 = r0[k], r0[k + 1], r1[k], r1[k + 1]
            if max(abs(a0[0] - a1[0]), abs(a0[1] - a1[1]), abs(c0[0] - c1[0]), abs(c0[1] - c1[1])) < 1e-6:
                continue
            for side, s in (("left", 1.0), ("right", -1.0)):
                shell.setdefault(f"band_{side}_{k + 1}", []).append(
                    [(x0, s * a0[0], a0[1]), (x1, s * c0[0], c0[1]), (x1, s * c1[0], c1[1]), (x0, s * a1[0], a1[1])])
        (y0, zr0), (y1, zr1) = r0[-1], r1[-1]
        shell.setdefault("roof", []).append([(x0, -y0, zr0), (x0, y0, zr0), (x1, y1, zr1), (x1, -y1, zr1)])
    for name, quads in shell.items():
        items.append(foam(name, quads[0]) if len(quads) == 1 else foam(name, facets=quads))

    items += skeleton(p, b)
    if b["corner_patch"] != "none":
        hr, zr = _section(p, xf)
        top = zb + (p["wall_h"] + zr - zb) / 2.0
        for side, s in (("left", 1.0), ("right", -1.0)):
            y0, y1 = s * (hr - 4 * 25.4), s * hw
            items.append({"name": f"patch_front_{side}", "kind": "covering", "material": b["corner_patch"],
                          "outline": [(xf, y0, zb), (xf, y1, zb), (xf, y1, top), (xf, y0, top)]})
    if b["allowance"]:
        items.append({"name": "glue, screws & hardware", "kind": "lump", "mass": b["allowance"],
                      "at": (xf - d / 2.0, 0.0, zb + p["height"] / 2.0)})
    return items
