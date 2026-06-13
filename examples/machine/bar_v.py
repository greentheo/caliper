"""CALI-25 — vertical post: a solid 20x40 bar, built in ASSEMBLY/WORLD coordinates.

20 (x) x 40 (y) x 100 (z), base on the ground (z 0..100). Threaded (tap-diameter) bolt holes:
  - 2 along +Y near the top  → take the corner bracket  (axis Y, at x=0, z=80 & 95)
  - 2 along +Z in the bottom → take the foot            (axis Z, at x=0, y=+/-12)
The matching parts drill *clearance* holes at the same world axes, so a screw passes straight through.
"""

R_TAP = 2.1   # M5 tap drill (threads cut into the solid bar)


def build(params):
    import cadquery as cq

    body = cq.Workplane("XY").box(20, 40, 100).translate((0, 0, 50))   # x[-10,10] y[-20,20] z[0,100]
    # bracket holes — axis Y, open on the +Y face (y=20), blind into the bar
    for z in (80, 95):
        cutter = cq.Workplane("XY").cylinder(20, R_TAP).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 13, z))
        body = body.cut(cutter)
    # foot holes — axis Z, open on the bottom face (z=0), blind up into the bar
    for y in (12, -12):
        cutter = cq.Workplane("XY").cylinder(20, R_TAP).translate((0, y, 7))
        body = body.cut(cutter)
    return body
