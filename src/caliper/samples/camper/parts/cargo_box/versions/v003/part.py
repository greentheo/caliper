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
    import math

    p = {**PARAMS, **(params or {})}

    w        = p["width"]
    d        = p["depth"]
    h        = p["height"]
    xf       = p["x_front"]
    zb       = p["z_bottom"]
    wall_h   = p["wall_h"]
    tl       = p["tail_len"]
    td       = p["tail_drop"]
    tp       = p["tail_pinch"]
    er       = p["tail_edge_r"]
    tc       = p["tail_curve"]

    IN = 25.4  # mm per inch

    # x runs negative going rearward
    x_back  = xf - d          # rearmost face
    half_w  = w / 2.0
    z_top   = zb + h

    # ------------------------------------------------------------------ #
    # Plain box when tail_len < 1 in                                     #
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Teardrop-tail loft                                                  #
    # ------------------------------------------------------------------ #
    # x where the taper starts (measured from the back face forward)
    x_taper_start = x_back + tl   # tl measured from back toward front

    def make_section(x, t):
        """
        Build one closed wire (six-sided) in the YZ plane at position x.
        t = 0 ahead of tail; t in [0,1] over tail.
        Points (all in world coords, wire in the plane x=const):
          P0 = ( x, -half_w,              zb )          floor left
          P1 = ( x, +half_w,              zb )          floor right
          P2 = ( x, +half_w,              zb+wall_h )   wall top right
          P3 = ( x, +(half_w - pinch(t)), zb+roof_h(t)) roof right
          P4 = ( x, -(half_w - pinch(t)), zb+roof_h(t)) roof left
          P5 = ( x, -half_w,              zb+wall_h )   wall top left
        """
        pinch   = tp * (t ** tc)
        roof_h  = h - td * (t ** tc)
        # never below wall_h + 1 mm
        roof_h  = max(roof_h, wall_h + 1.0)

        pts = [
            cq.Vector(x, -half_w,           zb),
            cq.Vector(x,  half_w,           zb),
            cq.Vector(x,  half_w,           zb + wall_h),
            cq.Vector(x,  half_w - pinch,   zb + roof_h),
            cq.Vector(x, -(half_w - pinch), zb + roof_h),
            cq.Vector(x, -half_w,           zb + wall_h),
        ]
        # close the wire
        edges = []
        n = len(pts)
        for i in range(n):
            edges.append(cq.Edge.makeLine(pts[i], pts[(i + 1) % n]))
        wire = cq.Wire.assembleEdges(edges)
        return wire

    # Build list of section x-positions and t-values
    # Section 0: front face, t=0
    # Section 1: taper start, t=0
    # Sections 2..9: 8 evenly spaced through the tail, t=1/8 .. 1
    n_tail = 8
    sections = []

    # Front face
    sections.append((xf, 0.0))
    # Taper start (only add if it's strictly between front and back)
    if x_taper_start < xf and x_taper_start > x_back + 1e-6:
        sections.append((x_taper_start, 0.0))
    elif x_taper_start >= xf:
        # tail_len >= depth: entire box tapers; skip the mid section
        pass

    # 8 sections through the tail
    for i in range(1, n_tail + 1):
        t_val = i / n_tail
        x_pos = x_taper_start - t_val * tl   # goes from x_taper_start toward x_back
        # clamp to [x_back, x_taper_start]
        x_pos = max(x_back, min(x_taper_start, x_pos))
        sections.append((x_pos, t_val))

    # Ensure back face is exactly at x_back with t=1
    # (the last section should already be at x_back; just make sure)
    if abs(sections[-1][0] - x_back) > 1e-4:
        sections.append((x_back, 1.0))

    # Remove duplicate x positions
    seen = []
    unique_sections = []
    for sx, st in sections:
        key = round(sx, 3)
        if key not in seen:
            seen.append(key)
            unique_sections.append((sx, st))
    sections = unique_sections

    # Build wires
    wires = [make_section(sx, st) for sx, st in sections]

    # Loft through wires
    # CadQuery loft expects profiles added via workplane; use the shell API directly
    # Build loft using cq.Solid.makeLoft
    try:
        loft_solid = cq.Solid.makeLoft(wires, ruled=False)
    except Exception:
        # fallback: ruled loft
        loft_solid = cq.Solid.makeLoft(wires, ruled=True)

    result = cq.Workplane("XY").add(loft_solid)

    # Optional edge rounding on back face
    if er > 0.0:
        max_r = min(er, h / 2.0 - 0.1, half_w - 0.1)
        if max_r > 0.01:
            try:
                result = result.faces("<X").edges().fillet(max_r)
            except Exception:
                pass

    return result