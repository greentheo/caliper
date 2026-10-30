PARAMS = {
    "shank_w": 50.8,        # 2 in outer
    "shank_t": 6.35,        # 1/4 in wall
    "riser_w": 50.8,        # 2 in outer
    "riser_t": 3.175,       # 1/8 in wall
    "upper_w": 50.8,        # 2 in outer
    "upper_t": 3.175,       # 1/8 in wall
    "rail_w":  50.8,        # 2 in outer
    "rail_t":  3.175,       # 1/8 in wall
    "cross_w": 50.8,        # 2 in outer
    "cross_t": 3.175,       # 1/8 in wall
    "shank_x_front":  228.6,   #  9 in
    "riser_x":       -177.8,   # -7 in
    "ladder_x_front": -457.2,  # -18 in
    "ladder_x_back": -1447.8,  # -57 in
    "shank_z_ctr":    228.6,   #  9 in
    "ladder_z_top":   457.2,   # 18 in
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
        {"name": "lower_shank", "group": "shank",
         "a": (sx_front, 0.0, shank_z), "b": (rx, 0.0, shank_z),
         "outer": sw, "wall": st},
        {"name": "riser", "group": "riser",
         "a": (rx, 0.0, riser_z_bot), "b": (rx, 0.0, riser_z_top),
         "outer": rw, "wall": rt},
        {"name": "upper_shank", "group": "upper_shank",
         "a": (rx, 0.0, upper_z_ctr), "b": (lx_b, 0.0, upper_z_ctr),
         "outer": uw, "wall": ut},
        {"name": "rail_pos", "group": "rails",
         "a": (lx_f, rail_y, rail_z_ctr), "b": (lx_b, rail_y, rail_z_ctr),
         "outer": rlw, "wall": rlt},
        {"name": "rail_neg", "group": "rails",
         "a": (lx_f, -rail_y, rail_z_ctr), "b": (lx_b, -rail_y, rail_z_ctr),
         "outer": rlw, "wall": rlt},
        {"name": "cross_front", "group": "cross",
         "a": (lx_f - cw/2.0, -(rail_y + rlw/2.0), rail_z_ctr),
         "b": (lx_f - cw/2.0,  (rail_y + rlw/2.0), rail_z_ctr),
         "outer": cw, "wall": ct},
        {"name": "cross_back", "group": "cross",
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

    sw  = p["shank_w"]
    rw  = p["riser_w"]
    uw  = p["upper_w"]
    rlw = p["rail_w"]
    cw  = p["cross_w"]

    # Derived Z positions
    ls_z_bot    = shank_z - sw / 2.0
    ls_z_top    = shank_z + sw / 2.0

    upper_z_top = ltop - rlw        # underside of rails / top of upper shank
    upper_z_bot = upper_z_top - uw  # bottom of upper shank

    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top

    rail_z_bot  = ltop - rlw
    rail_z_top  = ltop

    cross_y_min = -(rail_y + rlw / 2.0)
    cross_y_max =  (rail_y + rlw / 2.0)

    def solid_bar(x0, x1, y0, y1, z0, z1):
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        cz = (z0 + z1) / 2.0
        lx = abs(x1 - x0)
        ly = abs(y1 - y0)
        lz = abs(z1 - z0)
        return (cq.Workplane("XY")
                .box(lx, ly, lz)
                .translate((cx, cy, cz)))

    # Lower shank (along X, from receiver to riser)
    lower_shank = solid_bar(
        rx, sx_front,
        -sw/2.0, sw/2.0,
        ls_z_bot, ls_z_top,
    )

    # Riser (along Z, joining lower shank to upper shank)
    riser = solid_bar(
        rx - rw/2.0, rx + rw/2.0,
        -rw/2.0,      rw/2.0,
        riser_z_bot,  riser_z_top,
    )

    # Upper shank (along X, from riser to back cross member)
    upper_shank = solid_bar(
        lx_b, rx,
        -uw/2.0, uw/2.0,
        upper_z_bot, upper_z_top,
    )

    # Rail +y
    rail_pos = solid_bar(
        lx_b, lx_f,
        rail_y - rlw/2.0,  rail_y + rlw/2.0,
        rail_z_bot, rail_z_top,
    )

    # Rail -y
    rail_neg = solid_bar(
        lx_b, lx_f,
        -rail_y - rlw/2.0, -rail_y + rlw/2.0,
        rail_z_bot, rail_z_top,
    )

    # Front cross member (outer face at x = lx_f)
    cross_front = solid_bar(
        lx_f - cw, lx_f,
        cross_y_min, cross_y_max,
        rail_z_bot, rail_z_top,
    )

    # Back cross member (outer face at x = lx_b)
    cross_back = solid_bar(
        lx_b, lx_b + cw,
        cross_y_min, cross_y_max,
        rail_z_bot, rail_z_top,
    )

    # Union all into one solid
    result = lower_shank
    for part in [riser, upper_shank, rail_pos, rail_neg, cross_front, cross_back]:
        result = result.union(part)

    return result