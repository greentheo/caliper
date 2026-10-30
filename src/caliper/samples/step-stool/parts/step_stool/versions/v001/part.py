import cadquery as cq

PARAMS = {
    "stool_width": 406.4,        # 16 in
    "top_height": 228.6,         # 9 in - top step surface height
    "step_depth": 254.0,         # 10 in - front-to-back depth of each tread
    "bottom_step_height": 114.3, # 4.5 in - height of bottom step surface
    "ply_t": 19.05,              # 3/4 in plywood thickness
}

BUILD = {
    "ply_t": 19.05,  # 3/4 in plywood
}


def build(params):
    p = {**PARAMS, **(params or {})}

    t = p["ply_t"]
    W = p["stool_width"]
    H = p["top_height"]
    D = p["step_depth"]
    H2 = p["bottom_step_height"]
    total_depth = D * 2

    # Strategy: build as ONE solid L-shaped extrusion (the outer shell),
    # then this won't have watertight issues from panel unions.
    # 
    # The stool profile (side view, in Y-Z plane) is an L-shape / staircase:
    # Bottom step occupies: y=0..D, z=0..H2+t  (the bottom tread top surface at z=H2+t... 
    # wait, let me think about what geometry we want.
    #
    # Actually let's define the outer envelope as a staircase solid and subtract nothing.
    # The stool from the side looks like:
    #   - A full rectangle from y=0..total_depth, z=0..H (the two side panels)
    #   - Between the side panels: filled regions forming the staircase structure
    #
    # Better approach: model as a union of boxes that FULLY share faces (co-planar and touching).
    # The problem before was internal voids. Let's fill everything solid in key zones.
    #
    # The stool structure:
    # Side panels: x=0..t and x=W-t..W, full y=0..total_depth, full z=0..H
    # These are the "bookends". Between them (x=t..W-t):
    #   - Bottom tread: y=0..D, z=H2..H2+t
    #   - Top tread: y=D..total_depth, z=H-t..H
    #   - Middle riser: y=D..D+t, z=0..H2+t  (from floor to bottom tread top)
    #   - Back brace: y=total_depth-t..total_depth, z=0..H-t
    #
    # The watertight issue: the inner panels don't close the volume.
    # Solution: model each side panel as a full solid, then union with inner panels
    # that are extended to meet the side panels exactly.
    # 
    # Actually the real fix: make the side panels contain ALL the structure by
    # making them the full enclosure, and fill between them properly.
    #
    # Let me try: build the full stool as the side panels (which are solid rectangles)
    # PLUS inner structure. The inner pieces span exactly from x=t to x=W-t.
    # The union should be watertight if all pieces touch without gaps.

    inner_w = W - 2 * t

    # Side panels (left and right) - solid boxes, full height and depth
    left_side = (cq.Workplane("XY")
                 .box(t, total_depth, H)
                 .translate((t / 2, total_depth / 2, H / 2)))

    right_side = (cq.Workplane("XY")
                  .box(t, total_depth, H)
                  .translate((W - t / 2, total_depth / 2, H / 2)))

    # Bottom tread: sits at z=H2..H2+t, y=0..D
    # Extend it to touch both side panels exactly: x=t..W-t
    bottom_tread = (cq.Workplane("XY")
                    .box(inner_w, D, t)
                    .translate((t + inner_w / 2, D / 2, H2 + t / 2)))

    # Top tread: sits at z=H-t..H, y=D..total_depth
    top_tread = (cq.Workplane("XY")
                 .box(inner_w, D, t)
                 .translate((t + inner_w / 2, D + D / 2, H - t / 2)))

    # Middle riser: vertical panel at y=D..D+t, z=0..H2+t (floor to bottom tread top surface)
    # This closes the front of the upper step area
    riser_h = H2 + t
    middle_riser = (cq.Workplane("XY")
                    .box(inner_w, t, riser_h)
                    .translate((t + inner_w / 2, D + t / 2, riser_h / 2)))

    # Back brace: at y=total_depth-t..total_depth, z=0..H-t
    # Vertical panel at the back
    back_h = H - t
    back_brace = (cq.Workplane("XY")
                  .box(inner_w, t, back_h)
                  .translate((t + inner_w / 2, total_depth - t / 2, back_h / 2)))

    # Now: we need to close ALL open faces. The inner panels create a structure but
    # the "air gaps" between them (the open step spaces) are not enclosed.
    # 
    # The stool is NOT a closed box — it's an open framework. Union of open-framework
    # panels = NOT watertight because the structure has open faces (you can see inside).
    #
    # Fix: The solid must be watertight. The stool shape (as a solid) should be
    # modeled as the MATERIAL itself, which is a set of connected solid panels.
    # For a union to be watertight, the panels must form a closed surface.
    #
    # The current set of panels leaves open faces. We need to add panels to close them,
    # OR model the stool as a single extrusion.
    #
    # BEST APPROACH: Model from the profile.
    # The stool's outer silhouette from the side (Y-Z plane) is a staircase polygon.
    # Extrude it by W to get the full solid, then subtract two rectangular voids
    # (the hollow spaces under the bottom tread and under the top tread).
    # This gives a watertight solid that looks like a step stool.

    # Staircase outer profile (in Y-Z, i.e., depth vs height):
    # Going around the outside clockwise from origin:
    # (0,0) -> (total_depth, 0) -> (total_depth, H) -> (D, H) -> (D, H2+t) -> (0, H2+t) -> back? 
    # No wait - the stool has:
    #   Bottom step surface at z=H2 (top of bottom tread at z=H2+t)... 
    #   Hmm, let me re-think the geometry.
    #
    # Let me define a clean staircase profile and extrude it.
    # The stool as a solid block shaped like stairs, then subtract inner voids.
    #
    # Outer profile (Y-Z plane, going counterclockwise):
    # The stool spans y=0..total_depth (front to back), z=0..H (floor to top)
    # The staircase step-down: from z=H at y=D..total_depth, steps down at y=D to z=H2+t
    # 
    # Full outer profile:
    # (0, 0), (total_depth, 0), (total_depth, H), (D, H), (D, H2+t), (0, H2+t)
    # This is the 2D profile extruded by W in X.
    #
    # Then subtract inner voids to make it hollow (leaving t-thick walls):
    # Void 1 (under bottom tread, inside front portion):
    #   y=0..D-t (leave riser at back), z=0..H2 (below bottom tread)
    #   But we also need side walls (x=t..W-t)
    # Void 2 (inside upper step area):
    #   y=D+t..total_depth-t, z=0..H-t
    #   Again x=t..W-t

    # Build outer staircase profile
    pts = [
        (0, 0),
        (total_depth, 0),
        (total_depth, H),
        (D, H),
        (D, H2 + t),
        (0, H2 + t),
    ]

    outer = (cq.Workplane("XZ")
             .polyline([(y, z) for (y, z) in pts])
             .close()
             .extrude(W))
    # This extrudes in Y direction by W. But we want X direction.
    # Let me use a different workplane.

    # Use YZ plane, extrude in X
    outer = (cq.Workplane("YZ")
             .polyline(pts)
             .close()
             .extrude(W))

    # Now subtract inner voids (x from t to W-t, between side panels)
    # Void 1: the hollow space in the lower-front step area
    # y=0..D-t (leave riser thickness), z=0..H2 (below bottom tread)
    # x=t..W-t (between side panels)
    void1_depth = D - t   # from y=0 to y=D-t
    void1_h = H2          # from z=0 to z=H2
    if void1_depth > 0 and void1_h > 0:
        void1 = (cq.Workplane("YZ")
                 .rect(void1_depth, void1_h, centered=False)
                 .extrude(inner_w))
        # This makes a box from y=0..void1_depth, z=0..void1_h, x=0..inner_w
        # We need to position it at x=t
        void1 = void1.translate((t, 0, 0))
        outer = outer.cut(void1)

    # Void 2: the hollow space in the upper-back step area
    # y=D+t..total_depth-t (after riser, before back brace), z=0..H-t (below top tread)
    # x=t..W-t
    void2_y_start = D + t
    void2_y_end = total_depth - t
    void2_depth = void2_y_end - void2_y_start
    void2_h = H - t
    if void2_depth > 0 and void2_h > 0:
        void2 = (cq.Workplane("YZ")
                 .rect(void2_depth, void2_h, centered=False)
                 .extrude(inner_w))
        void2 = void2.translate((t, void2_y_start, 0))
        outer = outer.cut(void2)

    return outer


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}

    t = b["ply_t"]
    W = p["stool_width"]
    H = p["top_height"]
    D = p["step_depth"]
    H2 = p["bottom_step_height"]
    total_depth = D * 2

    pieces = []

    # Left side panel: x=0..t, y=0..total_depth, z=0..H (staircase shape)
    # Approximated as a staircase outline for the construction declaration
    pieces.append({
        "name": "left side panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (0, 0, 0),
            (0, total_depth, 0),
            (0, total_depth, H),
            (0, D, H),
            (0, D, H2 + t),
            (0, 0, H2 + t),
        ],
        "covers": ["paint", "paint"],
    })

    # Right side panel: x=W..W-t (outline on face x=W)
    pieces.append({
        "name": "right side panel",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (W, 0, 0),
            (W, total_depth, 0),
            (W, total_depth, H),
            (W, D, H),
            (W, D, H2 + t),
            (W, 0, H2 + t),
        ],
        "covers": ["paint", "paint"],
    })

    # Bottom tread: z=H2..H2+t, y=0..D, x=t..W-t
    pieces.append({
        "name": "bottom tread",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t, 0, H2 + t),
            (W - t, 0, H2 + t),
            (W - t, D, H2 + t),
            (t, D, H2 + t),
        ],
        "covers": ["paint", "paint"],
    })

    # Top tread: z=H-t..H, y=D..total_depth, x=t..W-t
    pieces.append({
        "name": "top tread",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t, D, H),
            (W - t, D, H),
            (W - t, total_depth, H),
            (t, total_depth, H),
        ],
        "covers": ["paint", "paint"],
    })

    # Middle riser: y=D..D+t, z=0..H2+t, x=t..W-t
    pieces.append({
        "name": "middle riser",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t, D, 0),
            (W - t, D, 0),
            (W - t, D, H2 + t),
            (t, D, H2 + t),
        ],
        "covers": ["paint", "paint"],
    })

    # Back brace: y=total_depth-t..total_depth, z=0..H-t, x=t..W-t
    pieces.append({
        "name": "back brace",
        "kind": "sheet",
        "material": "plywood",
        "thickness": t,
        "outline": [
            (t, total_depth - t, 0),
            (W - t, total_depth - t, 0),
            (W - t, total_depth - t, H - t),
            (t, total_depth - t, H - t),
        ],
        "covers": ["paint", "paint"],
    })

    return pieces