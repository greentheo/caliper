"""CALI-25 — corner gusset bracket: a 6mm plate on the +Y faces of both bars, screwing them together.

y 20..26 (sits flush on the bars' +Y face at y=20), covering the corner (x -10..40, z 75..100).
Four *clearance* through-holes (axis Y) coaxial with the bars' tap holes:
  - x=0, z=80 & 95   → into the post (bar_v)
  - x=30, z=85 & 95  → into the beam (bar_h)
"""

R_CLR = 2.75   # M5 clearance (the bolt passes through the bracket, threads into the bar)


def build(params):
    import cadquery as cq

    body = cq.Workplane("XY").box(50, 6, 25).translate((15, 23, 87.5))   # x[-10,40] y[20,26] z[75,100]
    for (x, z) in [(0, 80), (0, 95), (30, 85), (30, 95)]:
        cutter = cq.Workplane("XY").cylinder(20, R_CLR).rotate((0, 0, 0), (1, 0, 0), 90).translate((x, 23, z))
        body = body.cut(cutter)
    return body
