"""CALI-25 — foot: a base plate under the post, screwed up into the post's bottom.

40 (x) x 60 (y) x 8 (z), under the post (z -8..0), wider than the bar for stability. Two *clearance*
through-holes (axis Z) at x=0, y=+/-12 — coaxial with the post's bottom tap holes, so the screws pass
up through the foot and thread into the post.
"""

R_CLR = 2.75   # M5 clearance


def build(params):
    import cadquery as cq

    body = cq.Workplane("XY").box(40, 60, 8).translate((0, 0, -4))   # x[-20,20] y[-30,30] z[-8,0]
    for y in (12, -12):
        cutter = cq.Workplane("XY").cylinder(20, R_CLR).translate((0, y, -4))
        body = body.cut(cutter)
    return body
