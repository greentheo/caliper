"""CALI-25 — horizontal beam: a solid 20x40 bar, built in ASSEMBLY/WORLD coordinates.

100 (x) x 40 (y) x 20 (z), at the top of the post (x 10..110, y -20..20, z 80..100). Its left end
face (x=10) abuts the post's right face (x=10) — the corner. Threaded bracket holes along +Y near the
corner (axis Y, at x=30, z=85 & 95), matching the gusset bracket's clearance holes.
"""

R_TAP = 2.1   # M5 tap drill


def build(params):
    import cadquery as cq

    body = cq.Workplane("XY").box(100, 40, 20).translate((60, 0, 90))   # x[10,110] y[-20,20] z[80,100]
    for z in (85, 95):
        cutter = cq.Workplane("XY").cylinder(20, R_TAP).rotate((0, 0, 0), (1, 0, 0), 90).translate((30, 13, z))
        body = body.cut(cutter)
    return body
