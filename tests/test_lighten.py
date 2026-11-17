"""CALI-71 (#32) — lighten a sheet part where the wood isn't working, in cuts a sheet can take."""

import numpy as np
import pytest

from caliper import consistency, holes, lighten, load_study, sandbox
from caliper import construction as C
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

#: A 2 x 2 in hole through the box stool's left wall (x = 0..t), on its outline face at x = 0.
HOLE = '''

HOLES = [{"piece": "left", "normal": [1, 0, 0], "depth": 19.05,
          "polygons": [[[0, 100, 80], [0, 150.8, 80], [0, 150.8, 130.8], [0, 100, 130.8]]]}]
'''


def test_holes_are_cut_after_build_and_counted_in_their_piece():
    solid = sandbox.run_script(BOX_STOOL, timeout=120)
    holed = sandbox.run_script(BOX_STOOL + HOLE, timeout=120)
    assert holed.ok and holed.geometry.mesh.is_watertight
    gone = solid.geometry.mesh.volume - holed.geometry.mesh.volume
    assert gone == pytest.approx(50.8 * 50.8 * 19.05, rel=0.01)
    left = next(p for p in holed.declared["construction"] if p["name"] == "left")
    assert len(left["holes"]) == 1
    # the take-off: the left wall weighs its outline less the hole
    rows = {r["name"]: r for r in C.takeoff(holed.declared["construction"])}
    full = {r["name"]: r for r in C.takeoff(solid.declared["construction"])}
    assert rows["left"]["area_mm2"] == pytest.approx(full["left"]["area_mm2"] - 50.8 ** 2, rel=1e-6)
    assert rows["left"]["holes"] == 1
    # and what it says it's built from still matches what was built
    got = {r.id: r for r in consistency.check(holed.declared, holed.geometry)}
    assert got["construction_inside"].passed and got["construction_covers"].passed
    assert got["construction_volume"].actual == pytest.approx(1.0, abs=0.02)


def test_merge_leaves_other_pieces_alone():
    pieces = [{"name": "left", "kind": "sheet"}, {"name": "top", "kind": "sheet"}]
    out = holes.merge(pieces, [{"piece": "left", "polygons": [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]]}])
    assert out[0]["holes"] and "holes" not in out[1] and "holes" not in pieces[0]
    assert holes.area([[0, 0, 0], [2, 0, 0], [2, 3, 0], [0, 3, 0]]) == pytest.approx(6.0)


@pytest.fixture
def stool(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: quick, and the rules still bite
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    return store


def test_it_goes_down_until_the_safety_runs_out(stool):
    """The walls first, then hole-saw holes in the top one at a time, then thinner sheet as an estimate:
    every step lighter than the last, until one doesn't hold."""
    rec = lighten.study(stool, "stool", steps=(0.5, 1.0))
    from caliper import construction

    assert rec["part_lb"] == construction.report(stool, "stool")["mass_lb"] and rec["part_lb"] > 1   # for its least worth a button (#207)
    walls = sorted(p["name"] for p in rec["panels"] if not p["stood_on"])
    assert walls == ["back", "front", "left", "right"] and [p["name"] for p in rec["panels"] if p["stood_on"]] == ["top"]
    first, *rest = rec["stations"]
    assert first["removed"] == 0 and first["holes"] == 0 and first["phase"] == "walls"
    real = [s for s in rec["stations"] if not s.get("estimate")]
    assert [s["saved_lb"] for s in real] == sorted(s["saved_lb"] for s in real)
    phases = [s["phase"] for s in rec["stations"]]
    assert phases.index("walls") < phases.index("top")                     # the walls before the top
    assert all(s["phase"] == "walls" or s["removed"] >= max(x["removed"] for x in real if x["phase"] == "walls") - 1e-9
               for s in real)
    # the top, while solid, is judged by the plate check; with holes, by the FEA calibrated against it
    assert first["cases"][0]["governs"] == "plate"
    holed = [s for s in real if s["phase"] == "top"]
    assert holed and holed[0]["cases"][0]["governs"] == "fea-calibrated" and holed[0]["top_holes"] == 1
    assert holed[0]["safety"] <= first["safety"] + 1e-9
    # it stops at the first that doesn't hold, or when there's nothing left to try
    assert all(s["holds"] for s in real[:-1])
    # thinner sheet: estimates, never adopted as they stand
    est = [s for s in rec["stations"] if s.get("estimate")]
    assert est and all(s["phase"] == "thinner" and s["thickness_mm"] < 19.05 for s in est)
    with pytest.raises(ValueError, match="estimate"):
        lighten.adopt(stool, rec["id"], est[0]["index"])
    # every hole keeps its rim: no corner nearer the panel's edge than the rim
    walls = {p["name"]: p for p in C.declared(stool, "stool")["construction"]}
    for st in rec["stations"]:
        for name, polys in st["panels"].items():
            outline = np.asarray(walls[name]["outline"], float)
            lo, hi = outline.min(axis=0), outline.max(axis=0)
            for poly in polys:
                pts = np.asarray(poly)
                flat = [i for i in range(3) if hi[i] - lo[i] > 1]
                gap = np.minimum(pts[:, flat] - lo[flat], hi[flat] - pts[:, flat]).min()
                assert gap >= lighten.RIM_MM - 1.0
    # holes in the top are round, from a hole saw
    for s_ in holed:
        for poly in s_["panels"]["top"]:
            pts = np.asarray(poly)
            r = np.linalg.norm(pts - pts.mean(axis=0), axis=1)
            assert r.mean() * 2 == pytest.approx(lighten.HOLE_SAW_MM, rel=0.02)


def test_using_a_station_cuts_its_holes_into_the_part(stool):
    rec = lighten.study(stool, "stool", steps=(1.0,))
    st = max((s for s in rec["stations"] if s["holds"] and not s.get("estimate")), key=lambda s: s["saved_lb"])
    assert st["holds"] and st["holes"]
    before = C.report(stool, "stool")["mass_lb"]
    got = lighten.adopt(stool, rec["id"], st["index"])
    assert got["version"] == 2 and "HOLES = [" in stool.read_script("stool")
    assert C.report(stool, "stool")["mass_lb"] < before
    run = sandbox.run_script(stool.read_script("stool"), timeout=120)
    assert run.ok and run.geometry.mesh.is_watertight
    assert all(r.passed for r in consistency.check(run.declared, run.geometry))
    # and lightening it again starts from the holes it has
    again = lighten.study(stool, "stool", steps=(1.0,))
    assert again["stations"][0]["safety"] == pytest.approx(st["safety"], rel=0.15)


def test_the_check_of_a_cut_step_reads_as_the_step_did(stool):
    """#323 (Theo's step-stool-5 v8): Lighten's step 14 read 1.47 standing; the check of the shape it cut read 1.10. The
    rebuilt holes voxelize a few columns wider than the circles Lighten cut, and the check's ring round them was the
    circles': the stair-stepped voxels at the real edge counted in the panel's peak. Each case of the check of the cut
    shape reads within the band the card says, CUT_DRIFT (7%) either way: v8 rebuilt reads 1.67, 1.47 and 7.72 where its
    step read 1.59, 1.47 and 8.28."""
    rec = lighten.study(stool, "stool", steps=(1.0,), min_safety=1.3)
    assert any("the check of the cut part can read up to about 7% either way from its step" in n and
               '"holds, close: cut it and the check decides"' in n for n in rec["notes"])          # the card's note
    top = [s for s in rec["stations"] if s["phase"] == "top" and s["holds"] and not s.get("estimate")]
    st = max(top, key=lambda s: s["top_holes"])
    lighten.adopt(stool, rec["id"], st["index"])
    run = load_study.study(stool, "stool", min_safety=1.3)
    step = {c["name"]: c["safety"] for c in st["cases"]}
    got = {c["name"]: c["safety"] for c in run["cases"]}
    assert set(got) == set(step)
    from caliper import verdicts

    off = {n: (step[n], got[n]) for n in step if abs(got[n] / step[n] - 1) > verdicts.CUT_DRIFT}
    assert not off, f"step {st['index']} ({st['top_holes']} holes): the check reads off its step by more than the band {off}"


def test_the_check_s_ring_is_round_the_holes_its_solve_has(stool, monkeypatch):
    """#323: the ring left out of a holed panel's peak is round the holes as the solve has them (the panel's voxels
    filled in but not in the solid), not only round the circles' cells: Theo's v8 voxelized 200 voxels just outside its
    circles (19.2 to 20.3 mm from their centres, the circles 19.05) and kept 80 inside, and the voxels at that real edge
    counted in the peak, 8.40 MPa where Lighten's step read 5.61."""
    from scipy import ndimage

    rec = lighten.study(stool, "stool", steps=(1.0,), min_safety=1.3)
    st = max((s for s in rec["stations"] if s["phase"] == "top" and s["holds"]), key=lambda s: s["top_holes"])
    lighten.adopt(stool, rec["id"], st["index"])
    calls, real = [], lighten._panel_peak

    def spy(p, vm, solid, near, ring=None):
        calls.append((p, solid, ring))
        return real(p, vm, solid, near, ring)

    monkeypatch.setattr(lighten, "_panel_peak", spy)
    covered, shifted = lighten._covered, []                      # the circles' cells a column off the solve's holes,

    def off(p, polys, s):                                          # as v8's
        shifted.append(np.roll(covered(p, polys, s), 1, axis=0))
        return shifted[-1]

    monkeypatch.setattr(lighten, "_covered", off)
    load_study.study(stool, "stool", min_safety=1.3)
    pairs = [(a, b) for a, b in zip(calls, calls[1:]) if a[2] is None and b[2] is not None and a[0] is b[0]]
    assert pairs                                                   # judge_holed's: the filled solve's, then the holed
    for (p, filled, _), (_, solid, ring) in pairs:
        vx = p["voxels"]
        gone = np.zeros(filled.shape, bool)
        m = filled[vx[:, 0], vx[:, 1], vx[:, 2]] & ~solid[vx[:, 0], vx[:, 1], vx[:, 2]]
        gone[vx[m, 0], vx[m, 1], vx[m, 2]] = True
        edge = ndimage.binary_dilation(gone, iterations=1) & solid
        assert m.any() and not (edge & ~ring).any(), int((edge & ~ring).sum())
        inside = solid[vx[:, 0], vx[:, 1], vx[:, 2]]
        ringed = ring[vx[:, 0], vx[:, 1], vx[:, 2]] & inside
        assert ringed.sum() < 0.5 * inside.sum()                   # the rest of the panel is still the FEA's to read
        # and it's one voxel wide (caliper-reviewer on #326: a 3-voxel ring passed): every ringed voxel is next to a hole,
        # as the solve has it or as the circles' cells do
        holes = gone.copy()
        cells = shifted[-1][p["cells"][:, 0], p["cells"][:, 1]]
        holes[vx[cells, 0], vx[cells, 1], vx[cells, 2]] = True
        far = ndimage.distance_transform_edt(~holes)
        assert far[ring].max() <= 1.0, float(far[ring].max())



@pytest.mark.parametrize("safety, holes, estimate, kind", [
    (1.35, 10, False, "close"),           # within 7% of 1.3: the check of the cut part decides
    (1.39, 3, False, "close"),
    (1.40, 3, False, "holds"),            # 1.3 x 1.07 = 1.391
    (1.35, 0, False, "holds"),            # nothing cut: the part as it is, no drift to allow
    (1.35, 10, True, "estimate")])        # a thinner sheet stays an estimate
def test_a_step_within_the_band_of_its_minimum_holds_close_and_the_check_decides(safety, holes, estimate, kind):
    """#323, the foreman: what Theo hit. A step within CUT_DRIFT of its minimum reads "holds, close: cut it and the check
    decides", not a plain holds, and the run's note says the band."""
    from caliper import verdicts

    st = {"index": 14, "holds": True, "safety": safety, "holes": holes, "top_holes": holes, "saved_lb": 1.0,
          "cases": [], **({"estimate": True} if estimate else {})}
    v = verdicts.lighten_step(st, None, {"min_safety": 1.3, "kind": "lighten"})
    assert v["kind"] == kind
    if kind == "close":
        assert v["word"] == "holds, close: cut it and the check decides" and v["counts_as_pass"] and v["status"] == "warn"
    assert verdicts.CUT_DRIFT == 0.07



def test_a_close_step_resting_on_a_joint_keeps_cut_it_and_the_check_decides():
    """caliper-reviewer on #326: on the brace path the cut's words went, and only the joints' were said."""
    from caliper import verdicts

    st = {"index": 14, "holds": True, "safety": 1.35, "holes": 10, "top_holes": 10, "saved_lb": 1.0, "cases": []}
    v = verdicts.lighten_step(st, None, {"min_safety": 1.3, "kind": "lighten", "wood_joints": "uncounted"})
    assert v["kind"] == "close" and v["joints"] and v["counts_as_pass"]
    assert v["word"] == "holds, close: cut it and the check decides, and joints not checked"
    assert v["short"] == "holds 1.4x, close: cut it and the check decides, and joints not checked"
    far = verdicts.lighten_step({**st, "safety": 1.5}, None, {"min_safety": 1.3, "kind": "lighten", "wood_joints": "uncounted"})
    assert "cut it" not in far["word"]                              # outside the band: the joints' words alone
