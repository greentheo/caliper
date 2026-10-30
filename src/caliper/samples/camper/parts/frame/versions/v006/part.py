PARAMS = {
    "shank_w":        50.8,    # 2 in
    "shank_t":        6.35,    # 1/4 in
    "riser_w":        50.8,    # 2 in
    "riser_t":        3.175,   # 1/8 in
    "upper_w":        50.8,    # 2 in
    "upper_t":        3.175,   # 1/8 in
    "rail_w":         50.8,    # 2 in
    "rail_t":         3.175,   # 1/8 in
    "cross_w":        50.8,    # 2 in
    "cross_t":        3.175,   # 1/8 in
    "shank_x_front":  228.6,   # 9 in
    "riser_x":       -177.8,   # -7 in
    "ladder_x_front": -457.2,  # -18 in
    "ladder_x_back": -1447.8,  # -57 in
    "shank_z_ctr":    228.6,   # 9 in (lower shank centreline)
    "ladder_z_top":   457.2,   # 18 in (top of ladder = box floor)
    "rail_y":         762.0,   # 30 in
}


def members(params):
    p = {**PARAMS, **(params or {})}

    sx_front = p["shank_x_front"]
    rx       = p["riser_x"]
    lx_f     = p["ladder_x_front"]
    lx_b     = p["ladder_x_back"]
    shank_z  = p["shank_z_ctr"]
    ltop     = p["ladder_z_top"]
    rail_y   = p["rail_y"]

    sw  = p["shank_w"];  st  = p["shank_t"]
    rw  = p["riser_w"];  rt  = p["riser_t"]
    uw  = p["upper_w"];  ut  = p["upper_t"]
    rlw = p["rail_w"];   rlt = p["rail_t"]
    cw  = p["cross_w"];  ct  = p["cross_t"]

    upper_z_top = ltop - rlw
    upper_z_ctr = upper_z_top - uw / 2.0
    ls_z_bot    = shank_z - sw / 2.0
    rail_z_ctr  = ltop - rlw / 2.0
    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top

    return [
        {"name": "lower_shank",  "group": "shank",
         "a": (sx_front, 0.0, shank_z),     "b": (rx, 0.0, shank_z),
         "outer": sw, "wall": st},
        {"name": "riser",        "group": "riser",
         "a": (rx, 0.0, riser_z_bot),       "b": (rx, 0.0, riser_z_top),
         "outer": rw, "wall": rt},
        {"name": "upper_shank",  "group": "upper_shank",
         "a": (rx, 0.0, upper_z_ctr),       "b": (lx_b, 0.0, upper_z_ctr),
         "outer": uw, "wall": ut},
        {"name": "rail_pos",     "group": "rails",
         "a": (lx_f, rail_y, rail_z_ctr),   "b": (lx_b, rail_y, rail_z_ctr),
         "outer": rlw, "wall": rlt},
        {"name": "rail_neg",     "group": "rails",
         "a": (lx_f, -rail_y, rail_z_ctr),  "b": (lx_b, -rail_y, rail_z_ctr),
         "outer": rlw, "wall": rlt},
        {"name": "cross_front",  "group": "cross",
         "a": (lx_f - cw/2.0, -(rail_y + rlw/2.0), rail_z_ctr),
         "b": (lx_f - cw/2.0,  (rail_y + rlw/2.0), rail_z_ctr),
         "outer": cw, "wall": ct},
        {"name": "cross_back",   "group": "cross",
         "a": (lx_b + cw/2.0, -(rail_y + rlw/2.0), rail_z_ctr),
         "b": (lx_b + cw/2.0,  (rail_y + rlw/2.0), rail_z_ctr),
         "outer": cw, "wall": ct},
    ]


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    sx_front = p["shank_x_front"]
    rx       = p["riser_x"]
    lx_f     = p["ladder_x_front"]
    lx_b     = p["ladder_x_back"]
    shank_z  = p["shank_z_ctr"]
    ltop     = p["ladder_z_top"]
    rail_y   = p["rail_y"]

    sw  = p["shank_w"];  st  = p["shank_t"]
    rw  = p["riser_w"];  rt  = p["riser_t"]
    uw  = p["upper_w"];  ut  = p["upper_t"]
    rlw = p["rail_w"];   rlt = p["rail_t"]
    cw  = p["cross_w"];  ct  = p["cross_t"]

    # Derived positions
    ls_z_bot    = shank_z - sw / 2.0
    ls_z_top    = shank_z + sw / 2.0

    upper_z_top = ltop - rlw          # top of upper shank = bottom of rails
    upper_z_bot = upper_z_top - uw
    upper_z_ctr = (upper_z_bot + upper_z_top) / 2.0

    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top

    rail_z_bot  = ltop - rlw
    rail_z_top  = ltop

    def hollow_tube_x(x0, x1, y_ctr, z_ctr, outer, wall):
        """Hollow square tube along X axis, open ends."""
        lx = abs(x1 - x0)
        cx = (x0 + x1) / 2.0
        ext = wall + 1.0
        outer_s = cq.Workplane("XY").box(lx, outer, outer).translate((cx, y_ctr, z_ctr))
        inner_s = cq.Workplane("XY").box(lx + ext * 2, outer - 2*wall, outer - 2*wall).translate((cx, y_ctr, z_ctr))
        return outer_s.cut(inner_s)

    def hollow_tube_y(y0, y1, x_ctr, z_ctr, outer, wall):
        """Hollow square tube along Y axis, open ends."""
        ly = abs(y1 - y0)
        cy = (y0 + y1) / 2.0
        ext = wall + 1.0
        outer_s = cq.Workplane("XY").box(outer, ly, outer).translate((x_ctr, cy, z_ctr))
        inner_s = cq.Workplane("XY").box(outer - 2*wall, ly + ext * 2, outer - 2*wall).translate((x_ctr, cy, z_ctr))
        return outer_s.cut(inner_s)

    def hollow_tube_z(z0, z1, x_ctr, y_ctr, outer, wall):
        """Hollow square tube along Z axis, open ends."""
        lz = abs(z1 - z0)
        cz = (z0 + z1) / 2.0
        ext = wall + 1.0
        outer_s = cq.Workplane("XY").box(outer, outer, lz).translate((x_ctr, y_ctr, cz))
        inner_s = cq.Workplane("XY").box(outer - 2*wall, outer - 2*wall, lz + ext * 2).translate((x_ctr, y_ctr, cz))
        return outer_s.cut(inner_s)

    # ---- Lower shank: X from sx_front back to riser centre ----
    # Extend into riser by rw/2 so they physically overlap
    ls = hollow_tube_x(
        rx - rw/2.0, sx_front,
        0.0, shank_z,
        sw, st
    )

    # ---- Riser: Z from ls_z_bot up to upper_z_top ----
    # Extend slightly into lower shank below and into upper shank above
    rs = hollow_tube_z(
        riser_z_bot - sw/2.0, riser_z_top + uw/2.0,
        rx, 0.0,
        rw, rt
    )

    # ---- Upper shank: X from riser centre to lx_b ----
    # Extend into riser and into back cross member
    us = hollow_tube_x(
        lx_b - cw/2.0, rx + rw/2.0,
        0.0, upper_z_ctr,
        uw, ut
    )

    # ---- Rails: X from lx_b to lx_f ----
    # Extend into cross members at both ends so they overlap
    rail_z_ctr = (rail_z_bot + rail_z_top) / 2.0

    r_pos = hollow_tube_x(
        lx_b - cw/2.0, lx_f + cw/2.0,
        rail_y, rail_z_ctr,
        rlw, rlt
    )
    r_neg = hollow_tube_x(
        lx_b - cw/2.0, lx_f + cw/2.0,
        -rail_y, rail_z_ctr,
        rlw, rlt
    )

    # ---- Cross members: Y from -(rail_y+rlw/2) to +(rail_y+rlw/2) ----
    # Front cross: outer face at x=lx_f, so spans lx_f-cw to lx_f
    # Back cross:  outer face at x=lx_b, so spans lx_b to lx_b+cw
    cross_y_half = rail_y + rlw / 2.0

    cf = hollow_tube_y(
        -cross_y_half, cross_y_half,
        lx_f - cw/2.0, rail_z_ctr,
        cw, ct
    )
    cb = hollow_tube_y(
        -cross_y_half, cross_y_half,
        lx_b + cw/2.0, rail_z_ctr,
        cw, ct
    )

    # ---- Union all members ----
    # Because tubes overlap at every joint they fuse into one body
    result = ls.union(rs).union(us).union(r_pos).union(r_neg).union(cf).union(cb)

    return result