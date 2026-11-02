PARAMS = {
    "shank_sq": 50.8,
    # Lower shank: x = 9 in to x = -8 in, z = 8 to 10 in
    "lower_shank_x_start": 228.6,    # 9 in
    "lower_shank_x_end": -203.2,     # -8 in
    "lower_shank_z_bot": 203.2,      # 8 in
    "lower_shank_z_top": 254.0,      # 10 in
    # Riser post: x = -8 to -6 in, z = 8 to 16 in
    "riser_x_start": -203.2,         # -8 in
    "riser_x_end": -152.4,           # -6 in
    "riser_z_bot": 203.2,            # 8 in
    "riser_z_top": 406.4,            # 16 in
    # Upper shank: x = -8 in to x = -57 in, z = 14 to 16 in
    "upper_shank_x_start": -203.2,   # -8 in
    "upper_shank_x_end": -1447.8,    # -57 in
    "upper_shank_z_bot": 355.6,      # 14 in
    "upper_shank_z_top": 406.4,      # 16 in
    # Ladder: z = 16 to 18 in, x = -18 to -57 in
    "ladder_z_bot": 406.4,           # 16 in
    "ladder_z_top": 457.2,           # 18 in
    "rail_y_pos": 762.0,             # 30 in
    "rail_y_neg": -762.0,            # -30 in
    "rail_width": 50.8,              # 2 in
    "cross_width": 50.8,             # 2 in
    "num_cross": 4,
    "ladder_x_start": -457.2,        # -18 in
    "ladder_x_end": -1447.8,         # -57 in
}

def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    sq = p["shank_sq"]

    # Lower shank
    ls_x_start = p["lower_shank_x_start"]
    ls_x_end = p["lower_shank_x_end"]
    ls_z_bot = p["lower_shank_z_bot"]
    ls_z_top = p["lower_shank_z_top"]
    ls_len = ls_x_start - ls_x_end
    ls_cx = (ls_x_start + ls_x_end) / 2.0
    ls_cz = (ls_z_bot + ls_z_top) / 2.0
    lower_shank = (
        cq.Workplane("XY")
        .box(ls_len, sq, ls_z_top - ls_z_bot)
        .translate((ls_cx, 0.0, ls_cz))
    )

    # Riser post
    rs_x_start = p["riser_x_start"]
    rs_x_end = p["riser_x_end"]
    rs_z_bot = p["riser_z_bot"]
    rs_z_top = p["riser_z_top"]
    rs_len = rs_x_end - rs_x_start
    rs_cx = (rs_x_start + rs_x_end) / 2.0
    rs_cz = (rs_z_bot + rs_z_top) / 2.0
    riser = (
        cq.Workplane("XY")
        .box(rs_len, sq, rs_z_top - rs_z_bot)
        .translate((rs_cx, 0.0, rs_cz))
    )

    # Upper shank
    us_x_start = p["upper_shank_x_start"]
    us_x_end = p["upper_shank_x_end"]
    us_z_bot = p["upper_shank_z_bot"]
    us_z_top = p["upper_shank_z_top"]
    us_len = us_x_start - us_x_end
    us_cx = (us_x_start + us_x_end) / 2.0
    us_cz = (us_z_bot + us_z_top) / 2.0
    upper_shank = (
        cq.Workplane("XY")
        .box(us_len, sq, us_z_top - us_z_bot)
        .translate((us_cx, 0.0, us_cz))
    )

    # Ladder
    lz_bot = p["ladder_z_bot"]
    lz_top = p["ladder_z_top"]
    ry_pos = p["rail_y_pos"]
    ry_neg = p["rail_y_neg"]
    rw = p["rail_width"]
    cw = p["cross_width"]
    num_cross = int(p["num_cross"])
    lx_start = p["ladder_x_start"]   # -18 in: front outer face
    lx_end = p["ladder_x_end"]       # -57 in: back outer face

    ladder_z_centre = (lz_bot + lz_top) / 2.0
    ladder_height = lz_top - lz_bot

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

    # Cross member X positions: front outer face at lx_start, back outer face at lx_end
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

    # Build result by unioning all pieces
    result = lower_shank.union(riser).union(upper_shank).union(rail_pos).union(rail_neg)

    for x_pos in x_positions:
        cross = (
            cq.Workplane("XY")
            .box(cw, cross_span, ladder_height)
            .translate((x_pos, cross_cy, ladder_z_centre))
        )
        result = result.union(cross)

    return result