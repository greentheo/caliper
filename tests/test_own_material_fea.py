"""CALI-209 (#348): the FEA judges each piece in its own material, in a part of more than one.

It judged a part of two sheet materials in one, its most by volume: every voxel at that strength and solved at that
stiffness. Per-voxel material (CALI-82) was only for wood with printed pieces. So, both ways:
- an XPS floor in a mostly plywood box, resting on the ground (no plate check: the FEA is the number), read ✓ 105x under
  600 lb at plywood's 30 MPa, where its own 0.4 MPa gives 1.38x: a false ✓;
- a plywood floor in a box of XPS walls read 0.47x by the FEA, at foam's strength, where the plate check read 9.18x.

Synthetic, #328's box. Each piece's voxels now carry its own strength and stiffness. A voxel two pieces of different
materials share is the weaker's; a voxel no piece claims is the weakest material's, where nothing's printed."""

from types import SimpleNamespace

import numpy as np
import pytest

from caliper import load_study as L
from caliper.design import DesignStore

from .test_plate_held import BOX, RAILS

pytest.importorskip("cadquery")

PLY, XPS = (L.material([{"material": k, "volume": 1.0}]) for k in ("plywood", "xps"))

#: plywood walls 3/4 in x 600 mm (most of it by volume), a 2 in XPS floor resting on the ground, 600 lb x 2 on it
XPS_FLOOR = (BOX.replace("T, W, D, H, X = 9.525, 600.0, 400.0, 300.0, 50.8",
                         "T, W, D, H, X = 50.8, 600.0, 400.0, 600.0, 19.05")
             .replace('"name": "floor", "kind": "sheet", "material": "plywood"',
                      '"name": "floor", "kind": "sheet", "material": "xps"')
             .replace('"material": "xps", "thickness": X', '"material": "plywood", "thickness": X')
             .replace('"lb": 400', '"lb": 600'))
#: XPS walls 2 in (most of it), a 3/4 in plywood floor spanning two rails, 50 lb x 2 on it
PLY_FLOOR = RAILS.replace("T, W, D, H, X = 9.525,", "T, W, D, H, X = 19.05,").replace('"lb": 400', '"lb": 50')


def _study(tmp_path, src):
    store = DesignStore.create("a box", base=str(tmp_path / "designs"))
    store.write_part("box", src, intent="a box of foam and plywood")
    return L.study(store, "box")


def test_an_xps_floor_in_a_mostly_plywood_box_is_judged_as_xps(tmp_path):
    pytest.importorskip("whittle")
    rec = _study(tmp_path, XPS_FLOOR)
    (c,) = rec["cases"]
    assert not c["holds"] and c["governs"] == "fea" and c["fea"]["in"] == "floor"
    assert c["safety"] <= 1.4                                     # was ✓ 105x, at plywood's strength
    assert any(n.startswith("Each piece in its own material: ") for n in rec["notes"])
    assert not any(n.startswith("Analysed as all ") for n in rec["notes"])


def test_a_plywood_floor_in_a_box_of_xps_walls_is_judged_as_plywood(tmp_path):
    pytest.importorskip("whittle")
    rec = _study(tmp_path, PLY_FLOOR)
    (c,) = rec["cases"]
    pl = c["plate"]
    assert pl["done"] and pl["piece"] == "floor"
    assert c["fea"]["safety"] > 0.47 * 5                          # was 0.47x, at foam's strength
    assert c["holds"]


def _box_ctx(pieces, rest_mat=None):
    """A 6 x 1 x 1 row of voxels, 1 mm, for the map alone."""
    solid = np.ones((6, 1, 1), dtype=bool)
    ls = SimpleNamespace(solid=solid, grid=SimpleNamespace(origin=(0.0, 0.0, 0.0), shape=solid.shape), stiffness=None)
    ctx = {"ls": ls, "mat": rest_mat or PLY, "spacing": 1.0}
    return ctx, ls


def _stick(name, x0, x1, key):
    return {"name": name, "kind": "stick", "material": key, "a": (x0, 0.0, 0.0), "b": (x1, 0.0, 0.0), "half": 0.2}


@pytest.mark.parametrize("foam_first", [False, True])          # the weaker wins a shared voxel, in either order
def test_a_shared_voxel_is_the_weaker_s_and_an_unclaimed_one_the_weakest(foam_first):
    """Voxels 0-2 plywood, 2-3 XPS (voxel 2 in both), 4 and 5 in neither."""
    wood = [_stick("ply", 0.0, 2.0, "plywood"), _stick("foam", 2.0, 3.0, "xps")]
    if foam_first:
        wood.reverse()
    ctx, ls = _box_ctx(wood)
    L._two_materials(ctx, wood, PLY, None)
    got = ctx["strength_map"][:, 0, 0]
    assert got.tolist() == [PLY["strength"], PLY["strength"], XPS["strength"], XPS["strength"], XPS["strength"],
                            XPS["strength"]]
    assert np.allclose(ls.stiffness[:, 0, 0] * PLY["E"], [PLY["E"]] * 2 + [XPS["E"]] * 4)
    assert "note" not in ctx["mat"] and ctx["note"].startswith("Each piece in its own material: the ")
