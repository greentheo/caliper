PARAMS = {
    "shank_w": 50.8,           # 2 in square tube in the receiver
    "shank_t": 7.938,           # 5/16 in wall
    "riser_w": 63.5,           # 2 in
    "riser_t": 3.175,          # 1/8 in
    "spine_w": 50.8,           # 2 in: the main beam, under the middle of the floor
    "spine_t": 3.175,          # 1/8 in
    "x_w": 25.4,               # 1 in: the X, from the floor's corners to the middle of the spine
    "x_t": 1.587,              # 0.083 in
    "edge_w": 25.4,            # 1 in: edges under the walls (see "edges")
    "edge_t": 1.5875,          # 1/16 in
    "shank_x_front": 228.6,    # 9 in: 6 in inside the receiver
    "receiver_mouth_x": 76.2,  # 3 in: the receiver's mouth, 3 in ahead of the bumper (the hitch pin is near it)
    "riser_x": -101.6,         # -4 in: the riser, under the box's front wall (it's fastened there)
    "floor_x_front": -76.2,    # -3 in: the box's front face, 3 in behind the bumper
    "floor_x_back": -1092.2,   # -43 in: its back (40 in deep)
    "floor_half_w": 977.9,     # 38.5 in: half the floor's 77 in width
    "corner_in": 25.4,         # 1 in: the X's ends stop this far in from the floor's corners
    "shank_z_ctr": 228.6,      # 9 in: receiver centreline
    "floor_z": 457.2,          # 18 in: the underside of the floor = the tops of the spine, X and edges
    "edges": 0,                # 0: no edges; 1: front and back edges; 2: all four sides
    "spine_back": 1,           # 1: the spine runs to the back of the floor; 0: it stops under the X's middle
    "gusset_t": 0,             # plate under the X's middle (0 = none: with the box fastened to the spine it carries ~235 lb-in)
    "gusset_l": 152.4,         # 6 in fore and aft
    "gusset_w": 304.8,         # 12 in across: it reaches out under the X's arms
}

# What-if layouts for a frame study: which tubes there are, not their sizes.
LAYOUTS = {
    "X + front/back edges, spine to the back": {"edges": 1, "spine_back": 1},
    "X only, spine to the middle": {"edges": 0, "spine_back": 0},
    "X + front/back edges, spine to the middle": {"edges": 1, "spine_back": 0},
    "X + all four edges, spine to the back": {"edges": 2, "spine_back": 1},
    "X only, spine to the back": {"edges": 0, "spine_back": 1},
}

# Joints that take gusset plates (whittle's plate mode sizes them; Caliper writes PLATES below): the riser's
# two corners, where the hitch's moment turns. The first member is the one the plate's u runs along.
GUSSETS = {
    "jog_low": ("riser", "shank_out"),
    "jog_high": ("riser", "spine_0"),
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


# Gusset plates, as sized by whittle's plate mode (Caliper writes this).
PLATES = {
    "jog_low": {
        "members": [
            "riser",
            "shank_out"
        ],
        "thickness": 4.7625,
        "count": 2,
        "mass_kg": 1.017,
        "safety": 5.71,
        "relief": 0.836,
        "offset": 34.13,
        "placement": {
            "origin": [
                -101.6,
                0.0,
                228.6
            ],
            "u": [
                0.0,
                0.0,
                1.0
            ],
            "v": [
                1.0,
                0.0,
                0.0
            ],
            "normal": [
                0.0,
                1.0,
                0.0
            ]
        },
        "outline": [
            [
                -25.4,
                177.8
            ],
            [
                -25.4,
                -31.75
            ],
            [
                203.2,
                -31.75
            ],
            [
                203.2,
                31.75
            ],
            [
                25.4,
                177.8
            ]
        ],
        "holes": [
            [
                [
                    160.47,
                    48.62
                ],
                [
                    160.74,
                    47.9
                ],
                [
                    160.87,
                    47.19
                ],
                [
                    160.87,
                    46.47
                ],
                [
                    160.73,
                    45.76
                ],
                [
                    160.45,
                    45.05
                ],
                [
                    159.82,
                    44.25
                ],
                [
                    158.83,
                    43.38
                ],
                [
                    157.47,
                    42.42
                ],
                [
                    155.76,
                    41.38
                ],
                [
                    147.87,
                    40.6
                ],
                [
                    133.8,
                    40.06
                ],
                [
                    113.55,
                    39.78
                ],
                [
                    87.11,
                    39.75
                ],
                [
                    66.88,
                    39.81
                ],
                [
                    52.84,
                    39.97
                ],
                [
                    45.01,
                    40.23
                ],
                [
                    43.37,
                    40.58
                ],
                [
                    41.83,
                    41.15
                ],
                [
                    40.4,
                    41.94
                ],
                [
                    39.08,
                    42.94
                ],
                [
                    37.86,
                    44.16
                ],
                [
                    36.87,
                    45.31
                ],
                [
                    36.1,
                    46.38
                ],
                [
                    35.55,
                    47.38
                ],
                [
                    35.23,
                    48.3
                ],
                [
                    34.98,
                    54.35
                ],
                [
                    34.81,
                    65.53
                ],
                [
                    34.7,
                    81.84
                ],
                [
                    34.67,
                    103.27
                ],
                [
                    34.73,
                    119.75
                ],
                [
                    34.89,
                    131.28
                ],
                [
                    35.15,
                    137.87
                ],
                [
                    35.5,
                    139.51
                ],
                [
                    36.13,
                    141.0
                ],
                [
                    37.02,
                    142.35
                ],
                [
                    38.18,
                    143.56
                ],
                [
                    39.61,
                    144.63
                ],
                [
                    41.28,
                    145.11
                ],
                [
                    43.18,
                    145.0
                ],
                [
                    45.33,
                    144.31
                ],
                [
                    47.72,
                    143.04
                ],
                [
                    51.23,
                    140.57
                ],
                [
                    55.87,
                    136.91
                ],
                [
                    61.65,
                    132.05
                ],
                [
                    68.55,
                    126.0
                ],
                [
                    78.19,
                    117.88
                ],
                [
                    90.57,
                    107.69
                ],
                [
                    105.69,
                    95.43
                ],
                [
                    123.55,
                    81.1
                ],
                [
                    137.55,
                    69.74
                ],
                [
                    147.7,
                    61.33
                ],
                [
                    153.98,
                    55.89
                ],
                [
                    156.42,
                    53.41
                ],
                [
                    158.31,
                    51.37
                ],
                [
                    159.66,
                    49.77
                ]
            ]
        ],
        "notes": [
            "the plates run 100% of the way along riser: if the joint at its other end has plates too, cut each side as one plate over both",
            "the plates run 100% of the way along shank: if the joint at its other end has plates too, cut each side as one plate over both",
            "the tubes are 63.5 and 50.8 mm across: a flat plate on each side needs a 6.4 mm spacer on shank, or tubes the same width"
        ]
    },
    "jog_high": {
        "members": [
            "riser",
            "spine_0"
        ],
        "thickness": 4.7625,
        "count": 2,
        "mass_kg": 1.086,
        "safety": 7.3,
        "relief": 0.89,
        "offset": 34.13,
        "placement": {
            "origin": [
                -101.6,
                0.0,
                431.8
            ],
            "u": [
                0.0,
                0.0,
                -1.0
            ],
            "v": [
                -1.0,
                0.0,
                0.0
            ],
            "normal": [
                0.0,
                1.0,
                0.0
            ]
        },
        "outline": [
            [
                -25.4,
                203.2
            ],
            [
                -25.4,
                -31.75
            ],
            [
                203.2,
                -31.75
            ],
            [
                203.2,
                31.75
            ],
            [
                25.4,
                203.2
            ]
        ],
        "holes": [
            [
                [
                    165.62,
                    50.85
                ],
                [
                    165.9,
                    50.12
                ],
                [
                    166.04,
                    49.38
                ],
                [
                    166.04,
                    48.65
                ],
                [
                    165.9,
                    47.91
                ],
                [
                    165.62,
                    47.18
                ],
                [
                    164.97,
                    46.36
                ],
                [
                    163.95,
                    45.46
                ],
                [
                    162.55,
                    44.48
                ],
                [
                    160.79,
                    43.42
                ],
                [
                    152.5,
                    42.61
                ],
                [
                    137.67,
                    42.06
                ],
                [
                    116.3,
                    41.77
                ],
                [
                    88.4,
                    41.73
                ],
                [
                    67.11,
                    41.76
                ],
                [
                    52.43,
                    41.86
                ],
                [
                    44.35,
                    42.02
                ],
                [
                    42.88,
                    42.24
                ],
                [
                    41.6,
                    42.54
                ],
                [
                    40.5,
                    42.92
                ],
                [
                    39.58,
                    43.38
                ],
                [
                    38.84,
                    43.91
                ],
                [
                    38.07,
                    44.58
                ],
                [
                    37.27,
                    45.39
                ],
                [
                    36.43,
                    46.33
                ],
                [
                    35.56,
                    47.4
                ],
                [
                    34.84,
                    48.58
                ],
                [
                    34.29,
                    49.85
                ],
                [
                    33.91,
                    51.22
                ],
                [
                    33.68,
                    52.69
                ],
                [
                    33.52,
                    60.21
                ],
                [
                    33.4,
                    73.79
                ],
                [
                    33.35,
                    93.43
                ],
                [
                    33.35,
                    119.13
                ],
                [
                    33.4,
                    138.77
                ],
                [
                    33.52,
                    152.36
                ],
                [
                    33.69,
                    159.88
                ],
                [
                    33.91,
                    161.35
                ],
                [
                    34.22,
                    162.63
                ],
                [
                    34.61,
                    163.74
                ],
                [
                    35.08,
                    164.65
                ],
                [
                    35.64,
                    165.39
                ],
                [
                    36.32,
                    166.08
                ],
                [
                    37.13,
                    166.74
                ],
                [
                    38.05,
                    167.35
                ],
                [
                    39.1,
                    167.92
                ],
                [
                    40.16,
                    168.21
                ],
                [
                    41.22,
                    168.21
                ],
                [
                    42.29,
                    167.92
                ],
                [
                    43.36,
                    167.35
                ],
                [
                    45.92,
                    165.18
                ],
                [
                    49.96,
                    161.42
                ],
                [
                    55.48,
                    156.06
                ],
                [
                    62.48,
                    149.1
                ],
                [
                    68.37,
                    143.42
                ],
                [
                    73.16,
                    139.02
                ],
                [
                    76.83,
                    135.89
                ],
                [
                    79.4,
                    134.03
                ],
                [
                    85.82,
                    128.15
                ],
                [
                    96.1,
                    118.23
                ],
                [
                    110.24,
                    104.29
                ],
                [
                    128.23,
                    86.33
                ],
                [
                    142.35,
                    72.39
                ],
                [
                    152.59,
                    62.47
                ],
                [
                    158.96,
                    56.59
                ],
                [
                    161.45,
                    54.73
                ],
                [
                    163.4,
                    53.16
                ],
                [
                    164.78,
                    51.86
                ]
            ]
        ],
        "notes": [
            "the plates run 100% of the way along riser: if the joint at its other end has plates too, cut each side as one plate over both",
            "the tubes are 63.5 and 50.8 mm across: a flat plate on each side needs a 6.4 mm spacer on spine, or tubes the same width"
        ]
    }
}


def construction(params, build=None):
    """What the frame is made of besides its tubes (Caliper weighs those from members()): the gusset
    plates — the X's middle one if gusset_t > 0, and the riser's corner plates in PLATES once sized."""
    p = {**PARAMS, **(params or {})}
    items = []
    for name, pl in (globals().get("PLATES") or {}).items():
        items.append({"name": f"gusset_{name}", "kind": "lump", "label": "steel plate (gussets)",
                      "mass": pl["mass_kg"] * pl["count"], "at": tuple(pl["placement"]["origin"])})
    if p["gusset_t"] > 0:
        xc, gl, z = _layout(p)[4], p["gusset_l"], p["floor_z"] - p["x_w"] - p["gusset_t"] / 2.0
        for i, (y0, y1) in enumerate(_gusset_halves(p)):
            items.append({"name": f"gusset_{'right' if i == 0 else 'left'}", "kind": "sheet", "material": "steel",
                          "thickness": p["gusset_t"],
                          "outline": [(xc + gl / 2, y0, z), (xc + gl / 2, y1, z), (xc - gl / 2, y1, z), (xc - gl / 2, y0, z)]})
    return items
