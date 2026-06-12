"""Regenerate the demo assembly parts (CALI-20): a base, a post, and a cap that stack & mate.

    python examples/make_assembly.py

Each STL is modelled at its *local* origin (centered); the assembly file (`examples/assembly.yaml`)
positions them with `position:` so the parts stack:

    cap   16x16x4   on top of the post   (z 32..36)
    post  10x10x30  standing on the base (z  2..32)
    base  40x40x4   on the ground        (z -2..2)

post bottom (z=2) meets base top (z=2); cap bottom (z=32) meets post top (z=32) — two `touch` mates,
and no pair interferes. See pm/DEMO.md.
"""

import trimesh


def box(extents, path):
    m = trimesh.creation.box(extents=extents)  # centered at the local origin
    m.export(path)
    print(f"wrote {path}  extents={extents}")


box((40, 40, 4), "examples/asm_base.stl")
box((10, 10, 30), "examples/asm_post.stl")
box((16, 16, 4), "examples/asm_cap.stl")
