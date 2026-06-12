"""Regenerate the demo fit reference (CALI-10): a block that collides with a 60mm bracket flange.

    python examples/make_obstacle.py

Positioned at x∈[42,62] so the default 60mm corner bracket's horizontal flange overlaps it; the
`caliper fit` loop then shrinks the bracket until it clears the block. See pm/DEMO.md.
"""

import trimesh

m = trimesh.creation.box(extents=(20, 24, 8))
m.apply_translation([52, 0, 2])
m.export("examples/obstacle.stl")
print("wrote examples/obstacle.stl  bounds:", m.bounds.tolist())
