PARAMS = {
    "shank_sq": 50.8,        # 2 in square tube side
    "shank_x_start": 228.6,  # 9 in (receiver mouth, x from bumper face going +x into car)
    "shank_x_end": -1447.8,  # -57 in (box front edge side, negative = behind bumper)
    "shank_z_bot": 203.2,    # 8 in (bottom of shank)
    "shank_z_top": 254.0,    # 10 in (top of shank)
    "ladder_z_bot": 254.0,   # 10 in (bottom of ladder)
    "ladder_z_top": 304.8,   # 12 in (top of ladder)
    "rail_y_pos": 762.0,     # +30 in rail centre y
    "rail_y_neg": -762.0,    # -30 in rail centre y
    "rail_width": 50.8,      # 2 in rail cross-section (square tube)
    "cross_width": 50.8,     # 2 in cross member cross-section
    "num_cross": 4,          # number of cross members (including front and back)
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

    # --- Shank: centred on y=0, z from shank_z_bot to shank_z_top ---
    shank_len = abs(sx_start - sx_end)  # length along x
    # Centre of shank in x: midpoint between sx_start and sx_end
    shank_cx = (sx_start + sx_end) / 2.0
    shank_cz = (sz_bot + sz_top) / 2.0

    shank = (
        cq.Workplane("XY")
        .box(shank_len, sq, sq)
        .translate((shank_cx, 0.0, shank_cz))
    )

    # --- Ladder frame on top: z from lz_bot to lz_top ---
    ladder_z_centre = (lz_bot + lz_top) / 2.0
    ladder_height = lz_top - lz_bot  # should equal rw (2 in)

    # Rails run the full x extent of the ladder (same x as shank)
    rail_len = shank_len

    # Positive-y rail
    rail_pos = (
        cq.Workplane("XY")
        .box(rail_len, rw, ladder_height)
        .translate((shank_cx, ry_pos, ladder_z_centre))
    )

    # Negative-y rail
    rail_neg = (
        cq.Workplane("XY")
        .box(rail_len, rw, ladder_height)
        .translate((shank_cx, ry_neg, ladder_z_centre))
    )

    # Cross members: span from ry_neg to ry_pos (inclusive of rail width)
    cross_span = abs(ry_pos - ry_neg) + rw  # outer edge to outer edge
    cross_cy = 0.0  # centred on y=0

    # Distribute cross members along x: front (sx_start) and back (sx_end) plus interior
    result = shank.union(rail_pos).union(rail_neg)

    if num_cross >= 2:
        # positions along x for cross members
        x_positions = []
        for i in range(num_cross):
            # front cross at sx_start, back cross at sx_end
            frac = i / (num_cross - 1)
            x_pos = sx_start + frac * (sx_end - sx_start)
            x_positions.append(x_pos)
    else:
        x_positions = [shank_cx]

    for x_pos in x_positions:
        cross = (
            cq.Workplane("XY")
            .box(cw, cross_span, ladder_height)
            .translate((x_pos, cross_cy, ladder_z_centre))
        )
        result = result.union(cross)

    return result