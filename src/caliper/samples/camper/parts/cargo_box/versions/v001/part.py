PARAMS = {
    "width":      1879.6,   # 74 in
    "depth":       990.6,   # 39 in
    "height":     1041.4,   # 41 in
    "x_front":    -457.2,   # -18 in  (front face x)
    "z_bottom":    304.8,   # 12 in   (floor z)
    "tail_len":      0.0,   # how much of back tapers (mm)
    "tail_drop":     0.0,   # top falls this much at very back (mm)
    "tail_pinch":    0.0,   # each side draws in this much at very back (mm)
    "tail_edge_r":   0.0,   # rounding of back top/side edges (mm); 0 = sharp
}


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    w  = p["width"]
    d  = p["depth"]
    h  = p["height"]
    xf = p["x_front"]
    zb = p["z_bottom"]

    tl = p["tail_len"]
    td = p["tail_drop"]
    tp = p["tail_pinch"]
    er = p["tail_edge_r"]

    # x runs negative going rearward; back face is at xf - d
    x_back  = xf - d
    x_taper = x_back + tl   # taper starts here (measured from back)

    half_w = w / 2.0
    z_top  = zb + h

    # ------------------------------------------------------------------ #
    # Plain box (default: tail_len=0 or no taper)                        #
    # ------------------------------------------------------------------ #
    if tl <= 0.0 or (td == 0.0 and tp == 0.0):
        # Centre of box in world coords
        cx = xf - d / 2.0
        cy = 0.0
        cz = zb + h / 2.0

        box = (
            cq.Workplane("XY")
            .box(d, w, h)
            .translate((cx, cy, cz))
        )

        if er > 0.0:
            max_r = min(er, h / 2.0 - 0.1, w / 2.0 - 0.1, d / 2.0 - 0.1)
            if max_r > 0.01:
                try:
                    # Select edges on or near the rear face (x = x_back)
                    box = (
                        box
                        .faces("<X")
                        .edges()
                        .fillet(max_r)
                    )
                except Exception:
                    pass

        return box

    # ------------------------------------------------------------------ #
    # Tapered / boat-tail box                                            #
    # Build six faces explicitly, sew into a Shell, then make a Solid.  #
    # ------------------------------------------------------------------ #

    # Cross-section helpers
    # sec = [BL, BR, TR, TL] when viewed from front (+X)
    def sec(x, hy, z_b, z_t):
        return [
            cq.Vector(x, -hy, z_b),   # 0 BL
            cq.Vector(x,  hy, z_b),   # 1 BR
            cq.Vector(x,  hy, z_t),   # 2 TR
            cq.Vector(x, -hy, z_t),   # 3 TL
        ]

    sf = sec(xf,       half_w,        zb, z_top)         # front
    sm = sec(x_taper,  half_w,        zb, z_top)         # mid (taper start)
    sb = sec(x_back,   half_w - tp,   zb, z_top - td)    # back

    def planar_face(pts4):
        """Make a planar Face from 4 coplanar points (closed polygon)."""
        wire = cq.Wire.makePolygon(list(pts4) + [pts4[0]])
        return cq.Face.makeFromWires(wire)

    def ruled_face(p0, p1, p2, p3):
        """
        Ruled quad face:  p0-p1 is the first edge, p3-p2 is the second edge.
        Returns a Face.
        """
        e0 = cq.Edge.makeLine(p0, p1)
        e1 = cq.Edge.makeLine(p3, p2)
        return cq.Face.makeRuledSurface(e0, e1)

    faces = []

    # Front cap  (normal +X, CCW when viewed from +X: BL->TL->TR->BR)
    faces.append(planar_face([sf[0], sf[3], sf[2], sf[1]]))

    # Rear cap   (normal -X, CCW when viewed from -X: BL->BR->TR->TL)
    faces.append(planar_face([sb[0], sb[1], sb[2], sb[3]]))

    # Bottom face – keep flat (z = zb throughout)
    # Straight section: front BL -> mid BL, front BR -> mid BR
    faces.append(planar_face([sf[0], sf[1], sm[1], sm[0]]))
    # Taper section: mid bottom -> back bottom (ruled in case tp != 0)
    faces.append(ruled_face(sm[0], sm[1], sb[1], sb[0]))

    # Top face
    # Straight section (front to mid) – flat
    faces.append(planar_face([sf[3], sm[3], sm[2], sf[2]]))
    # Taper section – ruled (drops by td)
    faces.append(ruled_face(sm[3], sm[2], sb[2], sb[3]))

    # Left side (y = -half_w at front/mid, narrows to -(half_w-tp) at back)
    # Straight section
    faces.append(planar_face([sf[0], sm[0], sm[3], sf[3]]))
    # Taper section – ruled
    faces.append(ruled_face(sm[0], sm[3], sb[3], sb[0]))

    # Right side (y = +half_w at front/mid, narrows to +(half_w-tp) at back)
    # Straight section
    faces.append(planar_face([sf[1], sf[2], sm[2], sm[1]]))
    # Taper section – ruled
    faces.append(ruled_face(sm[1], sm[2], sb[2], sb[1]))

    # Sew faces into a shell, then solidify
    shell = cq.Shell.makeShell(faces)
    solid = cq.Solid.makeSolid(shell)

    result = cq.Workplane("XY").add(solid)

    if er > 0.0:
        max_r = min(er, h / 2.0 - 0.1, w / 2.0 - 0.1, tl / 2.0 - 0.1)
        if max_r > 0.01:
            try:
                result = result.faces("<X").edges().fillet(max_r)
            except Exception:
                pass

    return result