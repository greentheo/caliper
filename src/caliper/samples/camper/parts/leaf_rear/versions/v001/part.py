def build(params):
    import cadquery as cq

    # All dimensions converted from inches to mm (1 in = 25.4 mm)
    PARAMS = {
        "width_mm": 70.5 * 25.4,   # 1790.7 mm, full car width
        # Profile corners (x, z) in inches, converted to mm:
        # (0,12),(0,26),(3,30),(28,60),(60,60),(60,12)
        # x = depth from rear bumper face, z = height from ground
        "p0x": 0   * 25.4,
        "p0z": 12  * 25.4,
        "p1x": 0   * 25.4,
        "p1z": 26  * 25.4,
        "p2x": 3   * 25.4,
        "p2z": 30  * 25.4,
        "p3x": 28  * 25.4,
        "p3z": 60  * 25.4,
        "p4x": 60  * 25.4,
        "p4z": 60  * 25.4,
        "p5x": 60  * 25.4,
        "p5z": 12  * 25.4,
    }

    p = {**PARAMS, **(params or {})}

    width = p["width_mm"]

    # Build the 2-D profile polygon in the X-Z plane
    # Corners in order: (0,12)->(0,26)->(3,30)->(28,60)->(60,60)->(60,12)->close
    pts = [
        (p["p0x"], p["p0z"]),
        (p["p1x"], p["p1z"]),
        (p["p2x"], p["p2z"]),
        (p["p3x"], p["p3z"]),
        (p["p4x"], p["p4z"]),
        (p["p5x"], p["p5z"]),
    ]

    # Create a closed wire from the polygon points in the XZ plane
    # We'll work in the XZ plane: cadquery's workplane on YZ won't map cleanly,
    # so we build as a 2D polygon in the XY plane of a workplane, then rotate.

    # Use cadquery Workplane on XZ: build polygon in XZ, extrude along Y (width)
    # CadQuery doesn't have a native XZ workplane name, so we use "XZ" or build manually.
    # Strategy: create the profile on the XZ plane (cadquery supports "XZ")
    # Extrude in Y direction by full width, centered on y=0

    half_w = width / 2.0

    # Build profile as a closed polygon wire on the XZ workplane
    # In cadquery, on workplane "XZ", the "x" axis is X and "y" axis is Z
    # So our (x_profile, z_profile) maps to (x_wp, y_wp)

    profile_pts_2d = [(x, z) for (x, z) in pts]

    solid = (
        cq.Workplane("XZ")
        .polyline(profile_pts_2d)
        .close()
        .workplane()
        .extrude(half_w, both=True)
    )

    return solid