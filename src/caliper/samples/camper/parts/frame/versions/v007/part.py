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
    upper_z_top = ltop - rlw
    upper_z_bot = upper_z_top - uw
    upper_z_ctr = (upper_z_bot + upper_z_top) / 2.0
    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top
    rail_z_bot  = ltop - rlw
    rail_z_top  = ltop
    rail_z_ctr  = (rail_z_bot + rail_z_top) / 2.0

    EPS = 1.0  # mm: inner void extends past tube ends so ends are open

    def hollow_tube_x(x0, x1, y_ctr, z_ctr, outer, wall):
        """Hollow square tube along X axis, open ends."""
        lx = abs(x1 - x0)
        cx = (x0 + x1) / 2.0
        inner = outer - 2.0 * wall
        outer_box = cq.Workplane("XY").box(lx, outer, outer).translate((cx, y_ctr, z_ctr))
        inner_box = cq.Workplane("XY").box(lx + 2.0 * EPS, inner, inner).translate((cx, y_ctr, z_ctr))
        return outer_box.cut(inner_box)

    def hollow_tube_y(y0, y1, x_ctr, z_ctr, outer, wall):
        """Hollow square tube along Y axis, open ends."""
        ly = abs(y1 - y0)
        cy = (y0 + y1) / 2.0
        inner = outer - 2.0 * wall
        outer_box = cq.Workplane("XY").box(outer, ly, outer).translate((x_ctr, cy, z_ctr))
        inner_box = cq.Workplane("XY").box(inner, ly + 2.0 * EPS, inner).translate((x_ctr, cy, z_ctr))
        return outer_box.cut(inner_box)

    def hollow_tube_z(z0, z1, x_ctr, y_ctr, outer, wall):
        """Hollow square tube along Z axis, open ends."""
        lz = abs(z1 - z0)
        cz = (z0 + z1) / 2.0
        inner = outer - 2.0 * wall
        outer_box = cq.Workplane("XY").box(outer, outer, lz).translate((x_ctr, y_ctr, cz))
        inner_box = cq.Workplane("XY").box(inner, inner, lz + 2.0 * EPS).translate((x_ctr, y_ctr, cz))
        return outer_box.cut(inner_box)

    # Build each finished hollow tube individually
    # Lower shank: x from sx_front back to rx (centre of riser)
    lower_shank = hollow_tube_x(rx, sx_front, 0.0, shank_z, sw, st)

    # Riser: z from bottom of lower shank to top of upper shank
    riser = hollow_tube_z(riser_z_bot, riser_z_top, rx, 0.0, rw, rt)

    # Upper shank: x from rx to lx_b, z centred at upper_z_ctr
    upper_shank = hollow_tube_x(lx_b, rx, 0.0, upper_z_ctr, uw, ut)

    # Rails: x from lx_b to lx_f, y = ±rail_y
    rail_pos = hollow_tube_x(lx_b, lx_f,  rail_y, rail_z_ctr, rlw, rlt)
    rail_neg = hollow_tube_x(lx_b, lx_f, -rail_y, rail_z_ctr, rlw, rlt)

    # Cross members: y spans from -rail_y-rlw/2 to +rail_y+rlw/2
    cross_y0 = -(rail_y + rlw / 2.0)
    cross_y1 =  (rail_y + rlw / 2.0)
    # Front cross: outer face at x=lx_f, centre at lx_f - cw/2
    cf_xc = lx_f - cw / 2.0
    cross_front = hollow_tube_y(cross_y0, cross_y1, cf_xc, rail_z_ctr, cw, ct)
    # Back cross: outer face at x=lx_b, centre at lx_b + cw/2
    cb_xc = lx_b + cw / 2.0
    cross_back  = hollow_tube_y(cross_y0, cross_y1, cb_xc, rail_z_ctr, cw, ct)

    # Union all finished hollow tubes together
    result = (lower_shank
              .union(riser)
              .union(upper_shank)
              .union(rail_pos)
              .union(rail_neg)
              .union(cross_front)
              .union(cross_back))

    return result