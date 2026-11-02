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

# How it's built — these change the weight and the bill of materials, not the shape (Caliper reads
# them with construction() below; a drag study of PARAMS still applies whatever they are).
BUILD = {
    "floor":       "plywood",  # the floor: one full-size panel, the walls stand on it
    "floor_t":       9.525,    # 3/8 in
    "floor_under": "paint",    # sealer under the floor ("none" to skip)
    "walls":       "xps",      # walls and roof
    "walls_t":      25.4,      # 1 in
    "skin_out":    "pmf",      # outside of the walls and roof: canvas + glue + paint
    "skin_in":     "none",     # inside of the walls and roof
    "posts":       "2x2",      # a post in each corner, inside the foam ("none" to leave out)
    "allowance":     1.4,      # kg (~3 lb): glue, screws, hinges and trim
}


def construction(params, build=None):
    """The pieces of the box: plywood floor, foam walls and roof standing on it, corner posts inside.

    Front and back panels run the full width; the sides fit between them; the roof sits on top of all
    four. Faces are in world mm; Caliper weighs them and makes the bill of materials.
    """
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    w, d, h, xf, zb, wall_h = (p[k] for k in ("width", "depth", "height", "x_front", "z_bottom", "wall_h"))
    tl, td, tp, tc = p["tail_len"], p["tail_drop"], p["tail_pinch"], p["tail_curve"]
    hw, xb = w / 2.0, xf - d
    ft, wt = b["floor_t"], b["walls_t"]
    z0, ztop = zb + ft, zb + h                 # walls stand on the floor
    skin = [s for s in (b["skin_out"], b["skin_in"]) if s != "none"]

    def foam(name, outline=None, facets=None):
        out = {"name": name, "kind": "sheet", "material": b["walls"], "thickness": wt, "covers": skin}
        out.update({"outline": outline} if outline else {"facets": facets})
        return out

    def section(t):                            # the shape's corners above the walls, as in build()
        pinch = tp * t ** tc
        roof = max(h - td * t ** tc, wall_h + 1.0)
        return hw - pinch, zb + roof

    tailed = tl >= 25.4
    xs = min(xb + tl, xf) if tailed else xb    # where the taper starts
    st = []
    if tailed:
        for i in range(9):
            x = max(xb, xs - i / 8 * tl)
            if not st or abs(st[-1][0] - x) > 1e-3:
                st.append((x, i / 8))
        if abs(st[-1][0] - xb) > 1e-3:
            st.append((xb, 1.0))
    yb, zr = section(st[-1][1]) if tailed else (hw, ztop)

    items = [{"name": "floor", "group": "floor", "kind": "sheet", "material": b["floor"], "thickness": ft,
              "outline": [(xf, -hw, zb), (xb, -hw, zb), (xb, hw, zb), (xf, hw, zb)],
              "covers": [b["floor_under"]]}]
    items.append(foam("front", [(xf, -hw, z0), (xf, hw, z0), (xf, hw, ztop - wt), (xf, -hw, ztop - wt)]))
    items.append(foam("back", [(xb, -hw, z0), (xb, hw, z0), (xb, hw, zb + wall_h), (xb, yb, zr - wt),
                               (xb, -yb, zr - wt), (xb, -hw, zb + wall_h)]))
    for side, s in (("left", 1.0), ("right", -1.0)):
        y = s * hw
        if not tailed:
            items.append(foam(f"side_{side}", [(xf - wt, y, z0), (xb + wt, y, z0),
                                               (xb + wt, y, ztop - wt), (xf - wt, y, ztop - wt)]))
            continue
        items.append(foam(f"side_{side}", [(xf - wt, y, z0), (xb + wt, y, z0),
                                           (xb + wt, y, zb + wall_h), (xf - wt, y, zb + wall_h)]))
        if xf - xs > 1.0:
            items.append(foam(f"side_{side}_upper", [(xf - wt, y, zb + wall_h), (xs, y, zb + wall_h),
                                                     (xs, y, ztop - wt), (xf - wt, y, ztop - wt)]))
        quads = []
        for (x0, t0), (x1, t1) in zip(st, st[1:]):
            (y0, r0), (y1, r1) = section(t0), section(t1)
            quads.append([(x0, y, zb + wall_h), (x1, y, zb + wall_h), (x1, s * y1, r1 - wt), (x0, s * y0, r0 - wt)])
        items.append(foam(f"tail_{side}", facets=quads))
    if not tailed:
        items.append(foam("roof", [(xf, -hw, ztop), (xb, -hw, ztop), (xb, hw, ztop), (xf, hw, ztop)]))
    else:
        if xf - xs > 1.0:
            items.append(foam("roof", [(xf, -hw, ztop), (xs, -hw, ztop), (xs, hw, ztop), (xf, hw, ztop)]))
        quads = []
        for (x0, t0), (x1, t1) in zip(st, st[1:]):
            (y0, r0), (y1, r1) = section(t0), section(t1)
            quads.append([(x0, -y0, r0), (x0, y0, r0), (x1, y1, r1), (x1, -y1, r1)])
        items.append(foam("roof_tail", facets=quads))

    if b["posts"] != "none":
        c = wt + 0.75 * 25.4                   # post centre: in from the outside by the foam + half a 2x2
        back_top = zr - wt if tp < c else zb + wall_h
        for name, x, top in (("front", xf - c, ztop - wt), ("back", xb + c, back_top)):
            for side, s in (("left", 1.0), ("right", -1.0)):
                items.append({"name": f"post_{name}_{side}", "kind": "stick", "material": "lumber",
                              "size": b["posts"], "a": (x, s * (hw - c), z0), "b": (x, s * (hw - c), top)})
    if b["allowance"]:
        items.append({"name": "glue, screws & hardware", "kind": "lump", "mass": b["allowance"],
                      "at": (xf - d / 2.0, 0.0, zb + h / 2.0)})
    return items
