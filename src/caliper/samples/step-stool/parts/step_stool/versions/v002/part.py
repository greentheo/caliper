import cadquery as cq

PARAMS = {
    "stool_width":  406.4,   # 16 in
    "stool_height": 228.6,   # 9 in
    "stool_depth":  254.0,   # 10 in
    "ply_t":         19.05,  # 3/4 in plywood thickness
}

BUILD = {
    "ply_t": 19.05,  # 3/4 in plywood
}


def build(params):
    p = {**PARAMS, **(params or {})}

    t = p["ply_t"]
    W = p["stool_width"]
    H = p["stool_height"]
    D = p["stool_depth"]

    # Build as a hollow rectangular box (open bottom) by starting with a solid
    # box and subtracting the interior, leaving t-thick walls on all five sides
    # (four sides + top), open on the bottom.
    # To keep it watertight as a solid, model the shell solid:
    # outer box minus inner void (the inner void doesn't go all the way to z=0,
    # so the bottom is open — wait, that would leave an open face).
    #
    # For a watertight solid: model it as a closed box (six sides).
    # The stool sits on the floor; the "bottom" is just the floor edge of the
    # side panels — there's no separate bottom panel, but to be watertight
    # we model the solid as its actual material volume.
    #
    # Actual pieces: left side, right side, front, back, top tread.
    # Union of these five panels forms a closed, watertight solid.

    inner_w = W - 2 * t  # interior width
    inner_d = D - 2 * t  # interior depth (front and back panels consume t each)

    # Left side panel: x=0..t, y=0..D, z=0..H
    left = (cq.Workplane("XY")
            .box(t, D, H)
            .translate((t / 2, D / 2, H / 2)))

    # Right side panel: x=W-t..W, y=0..D, z=0..H
    right = (cq.Workplane("XY")
             .box(t, D, H)
             .translate((W - t / 2, D / 2, H / 2)))

    # Front panel: x=t..W-t, y=0..t, z=0..H
    front = (cq.Workplane("XY")
             .box(inner_w, t, H)
             .translate((t + inner_w / 2, t / 2, H / 2)))

    # Back panel: x=t..W-t, y=D-t..D, z=0..H
    back = (cq.Workplane("XY")
            .box(inner_w, t, H)
            .translate((t + inner_w / 2, D - t / 2, H / 2)))

    # Top tread: x=t..W-t, y=t..D-t, z=H-t..H
    top = (cq.Workplane("XY")
           .box(inner_w, inner_d, t)
           .translate((t + inner_w / 2, t + inner_d / 2, H - t / 2)))

    # Union all panels
    stool = (left.union(right)
                 .union(front)
                 .union(back)
                 .union(top))

    return stool


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}

    t = b["ply_t"]
    W = p["stool_width"]
    H = p["stool_height"]
    D = p["stool_depth"]

    inner_w = W - 2 * t
    inner_d = D - 2 * t

    pieces = []

    # Left side panel: outline on face x=0, panel extends in +X by t
    pieces.append({
        "name": "left side panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (0, 0, 0),
            (0, D, 0),
            (0, D, H),
            (0, 0, H),
        ],
        "covers": ["paint", "paint"],
    })

    # Right side panel: outline on face x=W, panel extends in -X by t
    pieces.append({
        "name": "right side panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (W, 0, 0),
            (W, D, 0),
            (W, D, H),
            (W, 0, H),
        ],
        "covers": ["paint", "paint"],
    })

    # Front panel: outline on face y=0, panel extends in +Y by t
    pieces.append({
        "name": "front panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t,     0, 0),
            (W - t, 0, 0),
            (W - t, 0, H),
            (t,     0, H),
        ],
        "covers": ["paint", "paint"],
    })

    # Back panel: outline on face y=D, panel extends in -Y by t
    pieces.append({
        "name": "back panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t,     D, 0),
            (W - t, D, 0),
            (W - t, D, H),
            (t,     D, H),
        ],
        "covers": ["paint", "paint"],
    })

    # Top tread: outline on face z=H, panel extends in -Z by t
    pieces.append({
        "name": "top tread",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t,     t,     H),
            (W - t, t,     H),
            (W - t, D - t, H),
            (t,     D - t, H),
        ],
        "covers": ["paint", "paint"],
    })

    return pieces