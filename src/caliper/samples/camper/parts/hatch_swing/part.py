PARAMS = {
    "x_min": -355.6,   # -14 in (behind bumper, hatch swing zone)
    "x_max": 0.0,      # 0 in (rear bumper face)
    "y_min": -609.6,   # -24 in
    "y_max": 609.6,    # +24 in
    "z_min": 660.4,    # 26 in
    "z_max": 1524.0,   # 60 in
}

def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}

    x_min = p["x_min"]
    x_max = p["x_max"]
    y_min = p["y_min"]
    y_max = p["y_max"]
    z_min = p["z_min"]
    z_max = p["z_max"]

    dx = x_max - x_min
    dy = y_max - y_min
    dz = z_max - z_min

    cx = (x_min + x_max) / 2.0
    cy = (y_min + y_max) / 2.0
    cz = (z_min + z_max) / 2.0

    solid = (
        cq.Workplane("XY")
        .box(dx, dy, dz)
        .translate((cx, cy, cz))
    )

    return solid