PARAMS = {
    "shank_w": 50.8,           # 2 in square tube in the receiver
    "shank_t": 6.35,           # 1/4 in wall
    "riser_w": 50.8,           # 2 in
    "riser_t": 3.175,          # 1/8 in
    "spine_w": 50.8,           # 2 in: the main beam, under the middle of the floor
    "spine_t": 3.175,          # 1/8 in
    "x_w": 25.4,               # 1 in: the X, from the floor's corners to the middle of the spine
    "x_t": 2.108,              # 0.083 in
    "edge_w": 25.4,            # 1 in: edges under the walls (see "edges")
    "edge_t": 1.5875,          # 1/16 in
    "shank_x_front": 228.6,    # 9 in: 6 in inside the receiver
    "receiver_mouth_x": 76.2,  # 3 in: the receiver's mouth, 3 in ahead of the bumper (the hitch pin is near it)
    "riser_x": -177.8,         # -7 in: the riser, just behind the bumper
    "floor_x_front": -457.2,   # -18 in: the box's front face
    "floor_x_back": -1473.2,   # -58 in: its back (40 in deep)
    "floor_half_w": 977.9,     # 38.5 in: half the floor's 77 in width
    "corner_in": 25.4,         # 1 in: the X's ends stop this far in from the floor's corners
    "shank_z_ctr": 228.6,      # 9 in: receiver centreline
    "floor_z": 457.2,          # 18 in: the underside of the floor = the tops of the spine, X and edges
    "edges": 1,                # 0: no edges; 1: front and back edges; 2: all four sides
    "spine_back": 1,           # 1: the spine runs to the back of the floor; 0: it stops under the X's middle
    "gusset_t": 4.7625,        # 3/16 in plate under the X's middle, slotted round the spine (0 = none)
    "gusset_l": 152.4,         # 6 in fore and aft
    "gusset_w": 304.8,         # 12 in across: it reaches out under the X's arms
}

# What-if layouts for a frame study: which tubes there are, not their sizes.
LAYOUTS = {
    "X + front/back edges, spine to the back": {"edges": 1, "spine_back": 1},
    "X only, spine to the middle": {"edges": 0, "spine_back": 0},
    "X + front/back edges, spine to the middle": {"edges": 1, "spine_back": 0},
    "X + all four edges, spine to the back": {"edges": 2, "spine_back": 1},
}

# The floor sits on the tops of the spine, the X and the edges, which are all flush with it. The X's
# four arms meet over the spine at the middle of the floor and are welded to its sides there, with a
# plate under them; the edges meet the spine the same way. The plywood floor and the foam walls bonded to
# it make a stiff tub of their own — the frame study leaves that out, so what it says is on the safe side.
#
# Members meet where the frame analysis needs them to: every end below sits on another member's
# centreline, joined by short stubs where tubes of different sizes meet flush at the top. Each member
# names the PARAMS that size it (so a frame study's chosen tube can be written back) and says whether
# the floor rests on it ("carries").


def _layout(p):
    top = p["floor_z"]
    z_s = top - p["spine_w"] / 2.0             # spine centreline
    z_p = top - p["x_w"] / 2.0                 # the X's centreline; the edges share it
    xf = p["floor_x_front"] - p["corner_in"]
    xb = p["floor_x_back"] + p["corner_in"]
    xc = (p["floor_x_front"] + p["floor_x_back"]) / 2.0
    yc = p["floor_half_w"] - p["corner_in"]
    return z_s, z_p, xf, xb, xc, yc


def _gusset_halves(p):
    """The gusset plate's two halves across the floor (y ranges), with the spine's slot between them."""
    slot, half = p["spine_w"] / 2.0 + 0.5, p["gusset_w"] / 2.0
    return [(-half, -slot), (slot, half)]


def members(params):
    p = {**PARAMS, **(params or {})}
    z_s, z_p, xf, xb, xc, yc = _layout(p)
    zs, xr = p["shank_z_ctr"], p["riser_x"]
    edges, to_back = int(round(p["edges"])), p["spine_back"] >= 0.5
    prefix = {"shank": "shank", "riser": "riser", "spine": "spine", "x": "x", "edges": "edge"}

    def m(name, group, a, b, carries=False):
        k = prefix[group]
        return {"name": name, "group": group, "a": a, "b": b, "outer": p[f"{k}_w"], "wall": p[f"{k}_t"],
                "size_params": [f"{k}_w", f"{k}_t"], "carries": carries}

    def stub(name, x):                          # spine centreline up to the 1 in tubes' centreline
        return [m(name, "spine", (x, 0.0, z_s), (x, 0.0, z_p))] if z_s < z_p - 1.0 else []

    mouth = (p["receiver_mouth_x"], 0.0, zs)
    out = [
        m("shank_in_receiver", "shank", (p["shank_x_front"], 0.0, zs), mouth),
        m("shank_out", "shank", mouth, (xr, 0.0, zs)),
        m("riser", "riser", (xr, 0.0, zs), (xr, 0.0, z_s)),
    ]
    # the spine: riser -> under the front edge -> under the X's middle -> under the back edge
    stops = [xr] + ([xf] if edges else []) + [xc] + ([xb] if to_back else [])
    for i, (x0, x1) in enumerate(zip(stops, stops[1:])):
        out.append(m(f"spine_{i}", "spine", (x0, 0.0, z_s), (x1, 0.0, z_s), carries=x1 < p["floor_x_front"]))
    out += stub("stub_middle", xc)
    for corner, (x, s) in {"front_left": (xf, 1.0), "front_right": (xf, -1.0),
                           "back_left": (xb, 1.0), "back_right": (xb, -1.0)}.items():
        out.append(m(f"x_{corner}", "x", (xc, 0.0, z_p), (x, s * yc, z_p), carries=True))
    if edges:
        for end, x in (("front", xf), ("back", xb)):
            if end == "back" and not to_back:   # no spine under it: the back edge runs corner to corner
                out.append(m("edge_back", "edges", (x, -yc, z_p), (x, yc, z_p), carries=True))
                continue
            out += stub(f"stub_{end}", x)
            for side, s in (("left", 1.0), ("right", -1.0)):
                out.append(m(f"edge_{end}_{side}", "edges", (x, 0.0, z_p), (x, s * yc, z_p), carries=True))
    if edges >= 2:
        for side, s in (("left", 1.0), ("right", -1.0)):
            out.append(m(f"edge_{side}", "edges", (xf, s * yc, z_p), (xb, s * yc, z_p), carries=True))
    return out


def supports(params):
    """The receiver holds the shank like a socket: at its mouth (the pin stops it sliding, and it can't
    twist) and at the shank's inner end (it can't move sideways or up/down there)."""
    p = {**PARAMS, **(params or {})}
    zs = p["shank_z_ctr"]
    return [{"at": (p["receiver_mouth_x"], 0.0, zs), "fix": ["ux", "uy", "uz", "rx"]},
            {"at": (p["shank_x_front"], 0.0, zs), "fix": ["uy", "uz"]}]


def build(params):
    import math

    import cadquery as cq

    p = {**PARAMS, **(params or {})}
    z_s, z_p, xf, xb, xc, yc = _layout(p)
    zs, xr, top = p["shank_z_ctr"], p["riser_x"], p["floor_z"]

    def tube(a, b, w, t, extend=(0.0, 0.0)):
        """A square tube from a to b (a horizontal or vertical run), open at both ends, hollowed on its own."""
        a, b = cq.Vector(*a), cq.Vector(*b)
        d = b - a
        length = d.Length
        u = d.normalized()
        a, length = a - u * extend[0], length + extend[0] + extend[1]
        outer = cq.Workplane("XY").box(length, w, w).translate((length / 2.0, 0, 0))
        if 2 * t < w - 0.01:
            outer = outer.cut(cq.Workplane("XY").box(length + 2, w - 2 * t, w - 2 * t).translate((length / 2.0, 0, 0)))
        solid = outer.val()
        if abs(u.z) > 0.99:                                     # vertical
            solid = solid.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90 if u.z > 0 else 90)
        else:
            solid = solid.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), math.degrees(math.atan2(u.y, u.x)))
        return cq.Workplane("XY").add(solid.translate(a))

    sw, st, rw, rt = p["shank_w"], p["shank_t"], p["riser_w"], p["riser_t"]
    pw, pt, xw, xt, ew, et = p["spine_w"], p["spine_t"], p["x_w"], p["x_t"], p["edge_w"], p["edge_t"]
    edges, to_back = int(round(p["edges"])), p["spine_back"] >= 0.5
    spine_end = (xb - ew / 2.0) if to_back else (xc - pw / 2.0)

    # Each tube runs INTO whatever it meets, so the solids overlap and fuse into one body.
    parts = [
        tube((p["shank_x_front"], 0, zs), (xr - rw / 2.0, 0, zs), sw, st),                        # lower shank
        tube((xr, 0, zs - sw / 2.0), (xr, 0, z_s + pw / 2.0), rw, rt),                            # riser
        tube((xr + rw / 2.0, 0, z_s), (spine_end, 0, z_s), pw, pt),                               # spine
    ]
    for x, s in ((xf, 1.0), (xf, -1.0), (xb, 1.0), (xb, -1.0)):                                   # the X
        parts.append(tube((xc, 0, z_p), (x, s * yc, z_p), xw, xt, extend=(0.0, xw / 2.0)))
    if edges:
        for x in (xf, xb):
            parts.append(tube((x, -yc, z_p), (x, yc, z_p), ew, et, extend=(ew / 2.0, ew / 2.0)))
    if edges >= 2:
        for s in (1.0, -1.0):
            parts.append(tube((xf, s * yc, z_p), (xb, s * yc, z_p), ew, et, extend=(ew / 2.0, ew / 2.0)))
    if p["gusset_t"] > 0:
        # under the X's middle, against the bottoms of the arms: two halves, either side of the spine
        for y0, y1 in _gusset_halves(p):
            parts.append(cq.Workplane("XY").box(p["gusset_l"], y1 - y0, p["gusset_t"])
                         .translate((xc, (y0 + y1) / 2.0, top - xw - p["gusset_t"] / 2.0)))

    frame = parts[0]
    for piece in parts[1:]:
        frame = frame.union(piece)
    return frame


def construction(params, build=None):
    """What the frame is made of besides its tubes (Caliper weighs those from members()): the gusset."""
    p = {**PARAMS, **(params or {})}
    items = []
    if p["gusset_t"] > 0:
        xc, gl, z = _layout(p)[4], p["gusset_l"], p["floor_z"] - p["x_w"] - p["gusset_t"] / 2.0
        for i, (y0, y1) in enumerate(_gusset_halves(p)):
            items.append({"name": f"gusset_{'right' if i == 0 else 'left'}", "kind": "sheet", "material": "steel",
                          "thickness": p["gusset_t"],
                          "outline": [(xc + gl / 2, y0, z), (xc + gl / 2, y1, z), (xc - gl / 2, y1, z), (xc - gl / 2, y0, z)]})
    return items
