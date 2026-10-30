PARAMS = {
    "shank_w": 50.8,           # 2 in square tube in the receiver
    "shank_t": 7.938,           # 5/16 in wall
    "riser_w": 50.8,           # 2 in: the same width as the shank and spine, so a cheek plate lies flat on all three
    "riser_t": 4.763,          # 1/8 in
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
        "thickness": 3.175,
        "count": 2,
        "mass_kg": 0.691,
        "safety": 6.03,
        "relief": 0.857,
        "offset": 26.99,
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
                -25.4
            ],
            [
                203.2,
                -25.4
            ],
            [
                203.2,
                25.4
            ],
            [
                25.4,
                177.8
            ]
        ],
        "holes": [
            [
                [
                    134.75,
                    46.39
                ],
                [
                    135.02,
                    45.68
                ],
                [
                    135.15,
                    44.97
                ],
                [
                    135.15,
                    44.25
                ],
                [
                    135.02,
                    43.54
                ],
                [
                    134.75,
                    42.82
                ],
                [
                    134.17,
                    41.93
                ],
                [
                    133.28,
                    40.86
                ],
                [
                    132.09,
                    39.61
                ],
                [
                    130.58,
                    38.18
                ],
                [
                    129.22,
                    37.03
                ],
                [
                    128.0,
                    36.15
                ],
                [
                    126.93,
                    35.55
                ],
                [
                    126.01,
                    35.23
                ],
                [
                    120.49,
                    34.98
                ],
                [
                    110.38,
                    34.81
                ],
                [
                    95.69,
                    34.7
                ],
                [
                    76.4,
                    34.67
                ],
                [
                    61.52,
                    34.73
                ],
                [
                    51.06,
                    34.89
                ],
                [
                    45.01,
                    35.15
                ],
                [
                    43.37,
                    35.5
                ],
                [
                    41.83,
                    36.07
                ],
                [
                    40.4,
                    36.86
                ],
                [
                    39.08,
                    37.86
                ],
                [
                    37.86,
                    39.08
                ],
                [
                    36.87,
                    40.23
                ],
                [
                    36.1,
                    41.3
                ],
                [
                    35.55,
                    42.3
                ],
                [
                    35.23,
                    43.22
                ],
                [
                    34.98,
                    47.84
                ],
                [
                    34.81,
                    56.16
                ],
                [
                    34.7,
                    68.18
                ],
                [
                    34.67,
                    83.9
                ],
                [
                    34.73,
                    96.1
                ],
                [
                    34.89,
                    104.77
                ],
                [
                    35.15,
                    109.93
                ],
                [
                    35.5,
                    111.57
                ],
                [
                    36.13,
                    113.07
                ],
                [
                    37.02,
                    114.44
                ],
                [
                    38.18,
                    115.67
                ],
                [
                    39.61,
                    116.77
                ],
                [
                    41.04,
                    117.48
                ],
                [
                    42.47,
                    117.82
                ],
                [
                    43.89,
                    117.78
                ],
                [
                    45.32,
                    117.35
                ],
                [
                    51.1,
                    113.42
                ],
                [
                    61.22,
                    105.98
                ],
                [
                    75.69,
                    95.04
                ],
                [
                    94.51,
                    80.58
                ],
                [
                    109.35,
                    69.02
                ],
                [
                    120.21,
                    60.37
                ],
                [
                    127.09,
                    54.61
                ],
                [
                    129.99,
                    51.75
                ],
                [
                    132.24,
                    49.43
                ],
                [
                    133.82,
                    47.64
                ]
            ]
        ],
        "notes": [
            "the plates run 100% of the way along riser: if the joint at its other end has plates too, cut each side as one plate over both",
            "the plates run 100% of the way along shank: if the joint at its other end has plates too, cut each side as one plate over both"
        ]
    },
    "jog_high": {
        "members": [
            "riser",
            "spine_0"
        ],
        "thickness": 3.175,
        "count": 2,
        "mass_kg": 0.645,
        "safety": 3.77,
        "relief": 0.8,
        "offset": 26.99,
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
                -25.4
            ],
            [
                203.2,
                -25.4
            ],
            [
                203.2,
                25.4
            ],
            [
                25.4,
                203.2
            ]
        ],
        "holes": [
            [
                [
                    171.9,
                    43.54
                ],
                [
                    172.17,
                    42.82
                ],
                [
                    172.3,
                    42.11
                ],
                [
                    172.3,
                    41.39
                ],
                [
                    172.16,
                    40.68
                ],
                [
                    171.88,
                    39.97
                ],
                [
                    171.25,
                    39.17
                ],
                [
                    170.26,
                    38.3
                ],
                [
                    168.9,
                    37.34
                ],
                [
                    167.19,
                    36.3
                ],
                [
                    158.59,
                    35.52
                ],
                [
                    143.08,
                    34.98
                ],
                [
                    120.69,
                    34.7
                ],
                [
                    91.4,
                    34.67
                ],
                [
                    69.08,
                    34.7
                ],
                [
                    53.72,
                    34.79
                ],
                [
                    45.32,
                    34.94
                ],
                [
                    43.89,
                    35.16
                ],
                [
                    42.64,
                    35.46
                ],
                [
                    41.57,
                    35.82
                ],
                [
                    40.68,
                    36.27
                ],
                [
                    39.97,
                    36.79
                ],
                [
                    39.22,
                    37.44
                ],
                [
                    38.43,
                    38.22
                ],
                [
                    37.62,
                    39.14
                ],
                [
                    36.77,
                    40.18
                ],
                [
                    36.07,
                    41.32
                ],
                [
                    35.54,
                    42.56
                ],
                [
                    35.16,
                    43.89
                ],
                [
                    34.94,
                    45.32
                ],
                [
                    34.78,
                    53.54
                ],
                [
                    34.67,
                    68.54
                ],
                [
                    34.62,
                    90.33
                ],
                [
                    34.62,
                    118.9
                ],
                [
                    34.67,
                    140.69
                ],
                [
                    34.78,
                    155.69
                ],
                [
                    34.95,
                    163.91
                ],
                [
                    35.16,
                    165.34
                ],
                [
                    35.46,
                    166.59
                ],
                [
                    35.84,
                    167.66
                ],
                [
                    36.31,
                    168.55
                ],
                [
                    36.85,
                    169.27
                ],
                [
                    37.51,
                    169.94
                ],
                [
                    38.29,
                    170.58
                ],
                [
                    39.2,
                    171.18
                ],
                [
                    40.22,
                    171.73
                ],
                [
                    41.34,
                    171.92
                ],
                [
                    42.57,
                    171.74
                ],
                [
                    43.89,
                    171.19
                ],
                [
                    45.32,
                    170.28
                ],
                [
                    54.15,
                    161.82
                ],
                [
                    70.36,
                    145.83
                ],
                [
                    93.98,
                    122.29
                ],
                [
                    124.98,
                    91.22
                ],
                [
                    148.3,
                    67.74
                ],
                [
                    163.94,
                    51.84
                ]
            ]
        ],
        "notes": [
            "the plates run 100% of the way along riser: if the joint at its other end has plates too, cut each side as one plate over both"
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
