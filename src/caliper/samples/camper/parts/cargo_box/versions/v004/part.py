PARAMS = {
    "width":      1879.6,   # 74 in
    "depth":       990.6,   # 39 in
    "height":     1041.4,   # 41 in
    "x_front":    -457.2,   # -18 in  (front face x)
    "z_bottom":    457.2,   # 18 in   (floor z)
    "wall_h":      304.8,   # 12 in   (straight side-wall height above floor)
    "tail_len":      0.0,   # how much of back tapers (mm); 0 = plain box
    "tail_drop":     0.0,   # top falls this much at very back (mm)
    "tail_pinch":    0.0,   # each side draws in this much at very back (mm)
    "tail_edge_r":   0.0,   # rounding of back top/side edges (mm); 0 = sharp
    "tail_curve":    1.0,   # 1 = straight panels; 2 = teardrop curve
}


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    w       = p["width"]
    d       = p["depth"]
    h       = p["height"]
    xf      = p["x_front"]
    zb      = p["z_bottom"]
    wall_h  = p["wall_h"]
    tl      = p["tail_len"]
    td      = p["tail_drop"]
    tp      = p["tail_pinch"]
    er      = p["tail_edge_r"]
    tc      = p["tail_curve"]

    IN = 25.4  # mm per inch

    x_back = xf - d        # rearmost x
    half_w = w / 2.0
    z_top  = zb + h

    # ------------------------------------------------------------------
    # Helper: one closed wire at world-x = x, tail parameter t in [0,1]
    # ------------------------------------------------------------------
    def make_wire(x, t):
        pinch  = tp * (t ** tc)
        roof_h = h - td * (t ** tc)
        roof_h = max(roof_h, wall_h + 1.0)

        pts = [
            cq.Vector(x, -half_w,           zb),
            cq.Vector(x,  half_w,           zb),
            cq.Vector(x,  half_w,           zb + wall_h),
            cq.Vector(x,  half_w - pinch,   zb + roof_h),
            cq.Vector(x, -(half_w - pinch), zb + roof_h),
            cq.Vector(x, -half_w,           zb + wall_h),
        ]
        edges = []
        n = len(pts)
        for i in range(n):
            edges.append(cq.Edge.makeLine(pts[i], pts[(i + 1) % n]))
        return cq.Wire.assembleEdges(edges)

    # ------------------------------------------------------------------
    # Plain box (no tail)
    # ------------------------------------------------------------------
    if tl < 1.0 * IN:
        cx = xf - d / 2.0
        cy = 0.0
        cz = zb + h / 2.0
        box = (
            cq.Workplane("XY")
            .box(d, w, h)
            .translate((cx, cy, cz))
        )
        return box

    # ------------------------------------------------------------------
    # Teardrop-tail build
    # ------------------------------------------------------------------
    # x where the taper starts (measured from the back face forward)
    x_taper_start = x_back + tl
    x_taper_start = min(x_taper_start, xf)  # can't go past front face

    front_len = xf - x_taper_start  # length of the plain-box front section

    # --- Front extrusion: full rectangular section --------------------
    front_solid = None
    if front_len > 1e-6:
        pts_yz = [
            (-half_w, zb),
            ( half_w, zb),
            ( half_w, zb + wall_h),
            ( half_w, zb + h),
            (-half_w, zb + h),
            (-half_w, zb + wall_h),
        ]
        wp = cq.Workplane("YZ", origin=(x_taper_start, 0, 0))
        wp = wp.polyline([(y, z) for y, z in pts_yz]).close()
        front_solid = wp.extrude(front_len)

    # --- Tail loft: x_taper_start → x_back ---------------------------
    n_tail = 8
    sections = []
    # First section at taper start, t = 0
    sections.append((x_taper_start, 0.0))
    # 8 evenly spaced through the tail
    for i in range(1, n_tail + 1):
        t_val = i / n_tail
        x_pos = x_taper_start - t_val * tl
        x_pos = max(x_back, x_pos)
        sections.append((x_pos, t_val))
    # Ensure exact back face
    if abs(sections[-1][0] - x_back) > 1e-4:
        sections.append((x_back, 1.0))

    # Remove x-duplicates
    seen_x = []
    unique_sections = []
    for sx, st in sections:
        key = round(sx, 3)
        if key not in seen_x:
            seen_x.append(key)
            unique_sections.append((sx, st))

    tail_wires = [make_wire(sx, st) for sx, st in unique_sections]

    # Smooth loft through tail sections
    try:
        tail_solid = cq.Solid.makeLoft(tail_wires, ruled=False)
    except Exception:
        tail_solid = cq.Solid.makeLoft(tail_wires, ruled=True)

    tail_wp = cq.Workplane("XY").add(tail_solid)

    # --- Union front extrusion + tail loft ----------------------------
    if front_solid is not None:
        result = front_solid.union(tail_wp)
    else:
        result = tail_wp

    # --- Optional edge rounding on back face --------------------------
    if er > 0.0:
        max_r = min(er, h / 2.0 - 0.1, half_w - 0.1)
        if max_r > 0.01:
            try:
                result = result.faces("<X").edges().fillet(max_r)
            except Exception:
                pass  # skip fillet if topology fails

    return result