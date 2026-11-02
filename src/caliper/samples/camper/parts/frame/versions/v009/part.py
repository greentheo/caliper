PARAMS = {
    "shank_w": 50.8,           # 2 in square tube in the receiver
    "shank_t": 6.35,           # 1/4 in wall
    "riser_w": 50.8,           # 2 in
    "riser_t": 3.175,          # 1/8 in
    "upper_w": 50.8,           # 2 in
    "upper_t": 3.175,          # 1/8 in
    "rail_w": 50.8,            # 2 in
    "rail_t": 3.175,           # 1/8 in
    "cross_w": 50.8,           # 2 in
    "cross_t": 3.175,          # 1/8 in
    "shank_x_front": 228.6,    # 9 in: 6 in inside the receiver (the mouth is at 3 in)
    "riser_x": -177.8,         # -7 in: the riser, just behind the bumper
    "ladder_x_front": -457.2,  # -18 in: front of the ladder (the box's front face)
    "ladder_x_back": -1447.8,  # -57 in: back of the ladder
    "shank_z_ctr": 228.6,      # 9 in: receiver centreline
    "ladder_z_top": 457.2,     # 18 in: top of the ladder = the box floor
    "rail_y": 762.0,           # 30 in: rails each side of the centreline
}

# Members meet where the frame analysis needs them to: every end below sits on another member's
# centreline. The cross members sit ON the upper shank, so short stubs join the two centrelines.


def _layout(p):
    top, cw, uw = p["ladder_z_top"], p["cross_w"], p["upper_w"]
    z_ladder = top - cw / 2.0                  # rails and cross members share this centreline
    z_upper = top - cw - uw / 2.0              # the upper shank sits just under the cross members
    xf = p["ladder_x_front"] - cw / 2.0        # cross member centrelines (outer faces flush with the ends)
    xb = p["ladder_x_back"] + cw / 2.0
    return z_ladder, z_upper, xf, xb


def members(params):
    p = {**PARAMS, **(params or {})}
    z_ladder, z_upper, xf, xb = _layout(p)
    y, zs, xr = p["rail_y"], p["shank_z_ctr"], p["riser_x"]

    def m(name, group, a, b, w, t):
        return {"name": name, "group": group, "a": a, "b": b, "outer": w, "wall": t}

    sec = {g: (p[f"{k}_w"], p[f"{k}_t"]) for g, k in
           (("shank", "shank"), ("riser", "riser"), ("upper_shank", "upper"), ("rails", "rail"), ("cross", "cross"))}
    out = [
        m("lower_shank", "shank", (p["shank_x_front"], 0.0, zs), (xr, 0.0, zs), *sec["shank"]),
        m("riser", "riser", (xr, 0.0, zs), (xr, 0.0, z_upper), *sec["riser"]),
        m("upper_shank_a", "upper_shank", (xr, 0.0, z_upper), (xf, 0.0, z_upper), *sec["upper_shank"]),
        m("upper_shank_b", "upper_shank", (xf, 0.0, z_upper), (xb, 0.0, z_upper), *sec["upper_shank"]),
        m("stub_front", "cross", (xf, 0.0, z_upper), (xf, 0.0, z_ladder), *sec["cross"]),
        m("stub_back", "cross", (xb, 0.0, z_upper), (xb, 0.0, z_ladder), *sec["cross"]),
    ]
    for side, s in (("neg", -1.0), ("pos", 1.0)):
        out.append(m(f"rail_{side}", "rails", (xf, s * y, z_ladder), (xb, s * y, z_ladder), *sec["rails"]))
        out.append(m(f"cross_front_{side}", "cross", (xf, 0.0, z_ladder), (xf, s * y, z_ladder), *sec["cross"]))
        out.append(m(f"cross_back_{side}", "cross", (xb, 0.0, z_ladder), (xb, s * y, z_ladder), *sec["cross"]))
    return out


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}
    z_ladder, z_upper, xf, xb = _layout(p)
    y, zs, xr = p["rail_y"], p["shank_z_ctr"], p["riser_x"]
    eps = 1.0

    def tube(axis, lo, hi, centre, w, t):
        """A hollow square tube along `axis` from lo to hi, open at both ends, hollowed on its own."""
        size, inner = [w, w, w], [w - 2 * t] * 3
        size[axis], inner[axis] = hi - lo, hi - lo + 2 * eps
        c = list(centre)
        c[axis] = (lo + hi) / 2.0
        outer = cq.Workplane("XY").box(*size).translate(tuple(c))
        return outer.cut(cq.Workplane("XY").box(*inner).translate(tuple(c)))

    sw, st = p["shank_w"], p["shank_t"]
    rw, rt = p["riser_w"], p["riser_t"]
    uw, ut = p["upper_w"], p["upper_t"]
    lw, lt = p["rail_w"], p["rail_t"]
    cw, ct = p["cross_w"], p["cross_t"]

    # Each tube runs INTO whatever it meets (by that member's wall + 1 mm, or across it), so the solids
    # overlap and fuse — tubes that only touch along a thin wall ring stay separate bodies.
    parts = [
        tube(0, xr - rw / 2.0, p["shank_x_front"], (0, 0.0, zs), sw, st),                    # lower shank
        tube(2, zs - sw / 2.0, z_upper + uw / 2.0, (xr, 0.0, 0), rw, rt),                    # riser
        tube(0, p["ladder_x_back"], xr + rw / 2.0, (0, 0.0, z_upper + eps), uw, ut),         # upper shank
        tube(1, -(y + lw / 2.0), y + lw / 2.0, (xf, 0, z_ladder), cw, ct),                   # front cross
        tube(1, -(y + lw / 2.0), y + lw / 2.0, (xb, 0, z_ladder), cw, ct),                   # back cross
    ]
    for s in (-1.0, 1.0):                                                                    # rails
        parts.append(tube(0, xb + cw / 2.0 - ct - eps, xf - cw / 2.0 + ct + eps, (0, s * y, z_ladder), lw, lt))

    frame = parts[0]
    for piece in parts[1:]:
        frame = frame.union(piece)
    return frame
