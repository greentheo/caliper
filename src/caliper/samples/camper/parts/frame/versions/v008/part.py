PARAMS = {
    "shank_w": 50.8, "shank_t": 6.35,
    "riser_w": 50.8, "riser_t": 3.175,
    "upper_w": 50.8, "upper_t": 3.175,
    "rail_w":  50.8, "rail_t":  3.175,
    "cross_w": 50.8, "cross_t": 3.175,
    "shank_x_front":  228.6,   # 9 in
    "riser_x":       -177.8,   # -7 in
    "ladder_x_front": -457.2,  # -18 in
    "ladder_x_back": -1447.8,  # -57 in
    "shank_z_ctr":    228.6,   # 9 in (centreline of lower shank)
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
    sw  = p["shank_w"]
    rw  = p["riser_w"]
    uw  = p["upper_w"]
    rlw = p["rail_w"]
    cw  = p["cross_w"]

    ls_z_bot    = shank_z - sw / 2.0
    upper_z_top = ltop - rlw
    upper_z_bot = upper_z_top - uw
    upper_z_ctr = (upper_z_bot + upper_z_top) / 2.0
    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top
    rail_z_ctr  = ltop - rlw / 2.0

    return [
        {"name": "lower_shank", "group": "shank",
         "a": (sx_front, 0.0, shank_z), "b": (rx, 0.0, shank_z),
         "outer": sw, "wall": p["shank_t"]},
        {"name": "riser", "group": "riser",
         "a": (rx, 0.0, riser_z_bot), "b": (rx, 0.0, riser_z_top),
         "outer": rw, "wall": p["riser_t"]},
        {"name": "upper_shank", "group": "upper_shank",
         "a": (rx, 0.0, upper_z_ctr), "b": (lx_b, 0.0, upper_z_ctr),
         "outer": uw, "wall": p["upper_t"]},
        {"name": "rail_pos", "group": "rails",
         "a": (lx_f,  rail_y, rail_z_ctr), "b": (lx_b,  rail_y, rail_z_ctr),
         "outer": rlw, "wall": p["rail_t"]},
        {"name": "rail_neg", "group": "rails",
         "a": (lx_f, -rail_y, rail_z_ctr), "b": (lx_b, -rail_y, rail_z_ctr),
         "outer": rlw, "wall": p["rail_t"]},
        {"name": "cross_front", "group": "cross",
         "a": (lx_f - cw/2.0, -(rail_y + rlw/2.0), rail_z_ctr),
         "b": (lx_f - cw/2.0,  (rail_y + rlw/2.0), rail_z_ctr),
         "outer": cw, "wall": p["cross_t"]},
        {"name": "cross_back", "group": "cross",
         "a": (lx_b + cw/2.0, -(rail_y + rlw/2.0), rail_z_ctr),
         "b": (lx_b + cw/2.0,  (rail_y + rlw/2.0), rail_z_ctr),
         "outer": cw, "wall": p["cross_t"]},
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

    ls_z_bot    = shank_z - sw / 2.0
    ls_z_top    = shank_z + sw / 2.0
    upper_z_top = ltop - rlw
    upper_z_bot = upper_z_top - uw
    upper_z_ctr = (upper_z_bot + upper_z_top) / 2.0
    riser_z_bot = ls_z_bot
    riser_z_top = upper_z_top
    rail_z_bot  = ltop - rlw
    rail_z_top  = ltop
    rail_z_ctr  = (rail_z_bot + rail_z_top) / 2.0

    cf_xc = lx_f - cw / 2.0
    cb_xc = lx_b + cw / 2.0
    cross_y0 = -(rail_y + rlw / 2.0)
    cross_y1 =  (rail_y + rlw / 2.0)

    # Build solid outer boxes for each member, then union, then cut inner voids.
    # The voids are cut per-member but sized so they don't break connectivity.

    def box_x(x0, x1, y_ctr, z_ctr, w, h=None):
        if h is None:
            h = w
        xa, xb = min(x0, x1), max(x0, x1)
        length = xb - xa
        return (cq.Workplane("YZ")
                .rect(w, h)
                .extrude(length)
                .translate((xa, y_ctr - w/2.0, z_ctr - h/2.0)))

    def box_y(y0, y1, x_ctr, z_ctr, w):
        ya, yb = min(y0, y1), max(y0, y1)
        length = yb - ya
        return (cq.Workplane("XZ")
                .rect(w, w)
                .extrude(length)
                .translate((x_ctr - w/2.0, ya, z_ctr - w/2.0)))

    def box_z(z0, z1, x_ctr, y_ctr, w):
        za, zb = min(z0, z1), max(z0, z1)
        length = zb - za
        return (cq.Workplane("XY")
                .rect(w, w)
                .extrude(length)
                .translate((x_ctr - w/2.0, y_ctr - w/2.0, za)))

    # --- Outer solid boxes ---
    s_lower  = box_x(rx, sx_front, 0.0, shank_z, sw)
    s_riser  = box_z(riser_z_bot, riser_z_top, rx, 0.0, rw)
    s_upper  = box_x(lx_b, rx, 0.0, upper_z_ctr, uw)
    s_rpos   = box_x(lx_b, lx_f, +rail_y, rail_z_ctr, rlw)
    s_rneg   = box_x(lx_b, lx_f, -rail_y, rail_z_ctr, rlw)
    s_cfront = box_y(cross_y0, cross_y1, cf_xc, rail_z_ctr, cw)
    s_cback  = box_y(cross_y0, cross_y1, cb_xc, rail_z_ctr, cw)

    # Union all outer solids
    frame = (s_lower
             .union(s_riser)
             .union(s_upper)
             .union(s_rpos)
             .union(s_rneg)
             .union(s_cfront)
             .union(s_cback))

    # --- Inner voids ---
    # Each void is cut along the axis of the member it belongs to.
    # The void length equals the member length only (not overshooting into neighbours),
    # so the wall material at joints is preserved and connectivity is maintained.
    # The void is slightly shorter than the outer box to keep end caps,
    # BUT since the spec calls for open-ended tubes we extend slightly past the ends.
    # However, at joints where members meet, we must NOT cut through the joint material.
    # Strategy: extend void 1 mm past each free end, but stop at joints where
    # another member's outer wall provides the material bridge.

    # Inner dimensions
    si  = sw  - 2 * st   # lower shank inner
    ri  = rw  - 2 * rt   # riser inner
    ui  = uw  - 2 * ut   # upper shank inner
    rli = rlw - 2 * rlt  # rail inner
    ci  = cw  - 2 * ct   # cross inner

    OVR = 2.0  # overshoot past free ends to open the tube

    # Lower shank void: runs x from rx to sx_front, free ends at both
    # At rx end it meets the riser outer wall; void stops at rx (no overshoot into riser)
    # At sx_front it's a free end (open to receiver)
    void_ls = box_x(rx, sx_front + OVR, 0.0, shank_z, si)
    frame = frame.cut(void_ls)

    # Riser void: runs z from riser_z_bot to riser_z_top
    # Both ends buried in lower/upper shank — stop at exact ends (no overshoot)
    # Actually open the free face: riser_z_bot is inside lower shank, riser_z_top is inside upper shank
    # The riser's hollow should run through its own length only
    void_rs = box_z(riser_z_bot, riser_z_top, rx, 0.0, ri)
    frame = frame.cut(void_rs)

    # Upper shank void: runs x from lx_b to rx
    # At rx end it meets riser; at lx_b end it meets cross_back outer wall
    # Stop at both ends (no overshoot) to preserve joint material
    void_us = box_x(lx_b, rx, 0.0, upper_z_ctr, ui)
    frame = frame.cut(void_us)

    # Rail voids: run x from lx_b to lx_f
    # Both ends buried in cross members — stop at exact ends
    void_rpos = box_x(lx_b, lx_f, +rail_y, rail_z_ctr, rli)
    void_rneg = box_x(lx_b, lx_f, -rail_y, rail_z_ctr, rli)
    frame = frame.cut(void_rpos)
    frame = frame.cut(void_rneg)

    # Cross member voids: run y from cross_y0 to cross_y1
    # Both ends are free (outside the rails) — open them
    void_cf = box_y(cross_y0 - OVR, cross_y1 + OVR, cf_xc, rail_z_ctr, ci)
    void_cb = box_y(cross_y0 - OVR, cross_y1 + OVR, cb_xc, rail_z_ctr, ci)
    frame = frame.cut(void_cf)
    frame = frame.cut(void_cb)

    return frame