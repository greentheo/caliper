PARAMS = {
    "shank_sq": 50.8,
    "shank_x_start": 228.6,
    "shank_x_end": -1447.8,
    "shank_z_bot": 203.2,
    "shank_z_top": 254.0,
    "ladder_z_bot": 254.0,
    "ladder_z_top": 304.8,
    "rail_y_pos": 762.0,
    "rail_y_neg": -762.0,
    "rail_width": 50.8,
    "cross_width": 50.8,
    "num_cross": 4,
    "ladder_x_start": -457.2,
    "ladder_x_end": -1447.8,
}

def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    sq = p["shank_sq"]
    sx_start = p["shank_x_start"]
    sx_end = p["shank_x_end"]
    sz_bot = p["shank_z_bot"]
    sz_top = p["shank_z_top"]

    lz_bot = p["ladder_z_bot"]
    lz_top = p["ladder_z_top"]

    ry_pos = p["rail_y_pos"]
    ry_neg = p["rail_y_neg"]
    rw = p["rail_width"]
    cw = p["cross_width"]
    num_cross = int(p["num_cross"])

    lx_start = p["ladder_x_start"]  # -18 in: front outer face
    lx_end = p["ladder_x_end"]      # -57 in: back outer face

    # Shank
    shank_len = abs(sx_start - sx_end)
    shank_cx = (sx_start + sx_end) / 2.0
    shank_cz = (sz_bot + sz_top) / 2.0

    shank = (
        cq.Workplane("XY")
        .box(shank_len, sq, sq)
        .translate((shank_cx, 0.0, shank_cz))
    )

    # Ladder dimensions
    ladder_z_centre = (lz_bot + lz_top) / 2.0
    ladder_height = lz_top - lz_bot

    # Rails: outer faces flush with lx_start and lx_end
    # Rail length = lx_start - lx_end (front face to back face)
    rail_len = lx_start - lx_end
    rail_cx = (lx_start + lx_end) / 2.0

    rail_pos = (
        cq.Workplane("XY")
        .box(rail_len, rw, ladder_height)
        .translate((rail_cx, ry_pos, ladder_z_centre))
    )

    rail_neg = (
        cq.Workplane("XY")
        .box(rail_len, rw, ladder_height)
        .translate((rail_cx, ry_neg, ladder_z_centre))
    )

    # Cross members span full width between outer rail edges
    cross_span = abs(ry_pos - ry_neg) + rw
    cross_cy = 0.0

    result = shank.union(rail_pos).union(rail_neg)

    # Cross member positions:
    # Front outer face flush with lx_start => center at lx_start - cw/2
    # Back outer face flush with lx_end => center at lx_end + cw/2
    if num_cross >= 2:
        front_cx = lx_start - cw / 2.0
        back_cx = lx_end + cw / 2.0
        x_positions = []
        for i in range(num_cross):
            frac = i / (num_cross - 1)
            x_pos = front_cx + frac * (back_cx - front_cx)
            x_positions.append(x_pos)
    else:
        x_positions = [(lx_start + lx_end) / 2.0]

    for x_pos in x_positions:
        cross = (
            cq.Workplane("XY")
            .box(cw, cross_span, ladder_height)
            .translate((x_pos, cross_cy, ladder_z_centre))
        )
        result = result.union(cross)

    return result