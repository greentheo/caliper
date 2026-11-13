"""CALI-93 (#72) — guards the reviews' mutation runs found no test failing without (rule 3: a check you never saw fail isn't evidence)."""

import json
import os
import subprocess
import sys
import textwrap

import pytest

from caliper import consistency, load_study, samples, trials

pytest.importorskip("cadquery")

ROOT = os.path.join(os.path.dirname(__file__), "..")


# --- #51: the test record ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def sample(tmp_path):
    return samples.open_sample("step-stool", base=str(tmp_path / "designs"))


def test_a_negative_sag_isnt_a_measurement(sample):
    with pytest.raises(ValueError, match="how far did it sag"):
        trials.record(sample, "step_stool", 100, sag_mm=-1.0)
    assert trials.rows(sample, "step_stool") == []


def test_a_negative_sag_in_the_file_isnt_read_as_a_step():
    assert trials._row(json.dumps({"load_lb": 100, "sag_mm": -1, "version": 1})) is None


def test_the_middle_band_of_sags_is_read_with_a_rule():
    assert trials.measure_with(1.0) == "a straightedge across the top and a steel rule or feeler gauges at the middle"
    assert trials.measure_with(2.99).startswith("a straightedge") and trials.measure_with(3.0).startswith("a tape")


def test_a_case_that_never_reached_a_support_isnt_the_one_predicted(sample):
    run_dir = os.path.join(load_study.runs_dir(sample), load_study.list_runs(sample, "step_stool")[0]["id"])
    path = os.path.join(run_dir, "run.json")
    with open(path) as f:
        run = json.load(f)
    run["cases"].append({"name": "a load that reached nothing", "lb": 200, "factor": 2.0, "safety": 0.0, "holds": False, "governs": "fea",
                         "fea": {"supported": False}})
    with open(path, "w") as f:
        json.dump(run, f)
    assert trials.predict(sample, "step_stool")["case"] != "a load that reached nothing"


# --- #74: a load's box buried in the solid ---------------------------------------------------------------------------------------
def test_a_box_buried_in_a_block_near_no_surface_is_on_it():
    import trimesh

    block = trimesh.creation.box(extents=(100, 100, 100))
    assert load_study.touches(block, ((-5, -5, -5), (5, 5, 5)), 2.0) == (True, 0.0)


# --- #56: the edges of the volume band ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("share, passes", [(0.66, False), (0.68, True)])
def test_the_edges_of_the_volume_band(monkeypatch, share, passes):
    import trimesh

    block = trimesh.creation.box(extents=(100, 100, 100))
    monkeypatch.setattr(consistency, "_in_no_piece", lambda *a, **k: 0.0)
    monkeypatch.setattr(consistency, "_loose_regions", lambda *a, **k: [])      # the band's edge, not where it's loose (#224)
    got = consistency._volume(block, [{"name": "a", "volume": share * 1e6}], strength=True)
    assert got.passed is passes


#: A box's six walls, every one a declared panel, around a block filled in: its pieces are 6t/L of it.
def _filled_cube(side: float, t: float = 19.05) -> str:
    return f'''import cadquery as cq

L, T = {side}, {t}


def build(params):
    return cq.Workplane().box(L, L, L, centered=False)


def construction(params, build=None):
    def sheet(name, o):
        return {{"name": name, "kind": "sheet", "material": "plywood", "thickness": T, "outline": o}}
    return [sheet("top", [(0, 0, L), (L, 0, L), (L, L, L), (0, L, L)]),
            sheet("bottom", [(0, 0, 0), (L, 0, 0), (L, L, 0), (0, L, 0)]),
            sheet("left", [(0, 0, 0), (0, L, 0), (0, L, L), (0, 0, L)]),
            sheet("right", [(L, 0, 0), (L, L, 0), (L, L, L), (L, 0, L)]),
            sheet("front", [(0, 0, 0), (L, 0, 0), (L, 0, L), (0, 0, L)]),
            sheet("back", [(0, L, 0), (L, L, 0), (L, L, L), (0, L, L)])]


def loads(params, build=None):
    return [{{"name": "a foot", "lb": 100, "factor": 2.0, "lo": (L / 2 - 20, L / 2 - 20, L - 2), "hi": (L / 2 + 20, L / 2 + 20, L)}}]
'''


@pytest.mark.parametrize("side, leg", [(176.0, "the solid is its pieces"), (166.0, "of the solid is in no piece")])
def test_the_volume_band_on_a_real_filled_box(tmp_path, side, leg):
    """#230 review (reviewer-2, item 1): the band on a real shape. A filled box with its six walls declared fails on either side of
    0.67, which is why the stubbed test above pins only the comparison: just under, on its pieces' volume; just over, on the share
    of it in no piece."""
    from caliper.design import DesignStore

    s = DesignStore.create("a filled box", base=str(tmp_path / "designs"))
    s.write_part("box", _filled_cube(side), intent="a box")
    got = next(r for r in consistency.checked(s, "box") if r.id == "construction_volume")
    assert not got.passed and leg in got.expr, (got.expr, got.actual)


def test_solid_4_mm_past_a_panel_is_in_no_piece():
    """#75's finding 11 (#72): the share in no piece is judged at the surface's own tolerance (2 mm here). Three times it passed
    every test, since the 4 in cube's grid has no point between 2 and 6 mm past a panel. Here, with 1/4 in panels on a 155.25 mm
    block, the grid's first row is 4 mm past each one: all of it is in no piece (measured: 100%; at 6 mm, 63%)."""
    from caliper import sandbox

    built = sandbox.run_script(_filled_cube(155.25, 6.35), timeout=120)
    got = {r.id: r for r in consistency.check(built.declared, built.geometry)}["construction_volume"]
    assert consistency.tolerance(built.geometry.mesh) == 2.0
    assert not got.passed and "100% of it is in no piece" in got.detail, got.detail


# --- #63's session report: chat.carve_part on a real carve's record ---------------------------------------------------------------
def test_the_carve_reply_on_a_real_two_step_carve(tmp_path, monkeypatch):
    """#72: ``chat.carve_part``'s reply was tested only on stubbed records (and in test_coarse_steps only when the best step saved
    something). Here the plywood top on printed sides is checked for real at two steps, as drawn and with its left side's top
    cut away (measured: the printed part 2.19x then 0.42x; the whole part 0.57x then 0.42x). Needing 0.5x, no step past the
    first holds, and the headline and the reply both say nothing could come off: never a step to use."""
    pytest.importorskip("whittle")
    import numpy as np
    import trimesh
    from types import SimpleNamespace
    from whittle import LoadStudy

    from caliper import carve, chat, studies
    from caliper.design import DesignStore

    from .test_mixed import MIXED

    def top_of_the_left_side(ls):
        at = [np.asarray(ls.grid.origin)[a] + ls.grid.spacing * np.arange(ls.solid.shape[a]) for a in (0, 2)]
        out = ls.solid.copy()
        out[np.broadcast_to((at[0] < 30.0)[:, None, None] & (at[1] > 160.0)[None, None, :], out.shape)] = False
        return out

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    monkeypatch.setattr(LoadStudy, "sweep", lambda self, **kw: SimpleNamespace(stations=[
        SimpleNamespace(design=d, build=lambda: None) for d in (self.solid.copy(), top_of_the_left_side(self))]))
    monkeypatch.setattr(carve, "_station_mesh", lambda mesh: trimesh.creation.box())
    monkeypatch.setattr(carve, "_judge", lambda *a, **k: None)
    s = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    s.write_part("stool", MIXED, intent="a plywood top on printed sides")
    rec = carve.study(s, "stool", stations=2, min_safety=0.5)
    drawn, cut = rec["stations"]
    assert drawn["whole"] > cut["whole"] and drawn["whole_holds"] and not cut["holds"] and cut["saved_g"]   # the fixture
    assert studies._headline("carve", rec) == ("nothing could come off and still hold", False)
    monkeypatch.setattr(carve, "study", lambda *a, **k: rec)
    got = chat.carve_part(s, "stool")
    assert not got.ok and got.reply == "Nothing could come off it and still hold.", got.reply


# --- #56: the page's note while a lightening step is previewed -------------------------------------------------------------------
def test_patterns_made_while_previewing_a_step_say_it_isnt_cut_in():
    """#56 (#72): the note had no test. It shows on the part whose lightening step is on screen, and only there: not
    on another part, not with nothing previewed, not for a station that isn't a lightening run's (a drag study's, say)."""
    from .test_carve_click import _page, _run

    out = _run(_page(["previewNote"], consts=["esc"], extra="""
const S = {station: {part: 'stool', run: 'l1', index: 3}, design: {lighten_runs: [{id: 'l1'}]}};
out = [previewNote({id: 'stool', name: 'Step stool'}), previewNote({id: 'lid'})];
S.station = {part: 'stool', run: 'd1', index: 2}; out.push(previewNote({id: 'stool'}));
S.station = null; out.push(previewNote({id: 'stool'}));"""))
    assert "These are of the Step stool as it is, without the step you're previewing." in out[0]
    assert "<b>Cut these holes</b>" in out[0] and out[1:] == ["", "", ""]


# --- #74/#75: an all-wood build lists kids.html; #52: its shop book glues and screws --------------------------------------------------
def test_an_all_wood_build_lists_its_kids_book(tmp_path):
    """#72: the index lists kids.html only when one was made. The other side, a wooden build listing it, had no test. And #52: the
    shop book tells a wooden build to glue and screw where pieces meet, never the camper's foam-safe adhesive; forcing that off
    passed every test."""
    from caliper import cutplan, release
    from caliper.design import DesignStore

    from .test_load_study import BOX_STOOL

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    s = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL, intent="a box step stool")
    made = release.make(s, pdf=False)
    root = os.path.join(release.releases_dir(s), made["id"])
    assert made["kids"] == "kids.html" and os.path.exists(os.path.join(root, "kids.html"))
    book = open(os.path.join(root, "index.html")).read()
    assert "<code>kids.html</code>" in book
    # glued and screwed at the holes the patterns mark (CALI-177: the step says the marks, not a screw every 6 in)
    assert "screw holes marked + on the patterns" in book and "glue each joint" in book, book
    assert "floor's edge" not in book and "foam-safe" not in book


# --- the hash seed: a page's wording mustn't change with it (#75's rework) -------------------------------------------------------
ORDER = textwrap.dedent("""
    import tempfile
    from caliper.design import DesignStore
    from caliper import kidbook, construction as C, consistency, fasteners
    from tests.test_load_study import BOX_STOOL
    s = DesignStore.create("a box stool", base=tempfile.mkdtemp())
    s.write_part("stool", BOX_STOOL, intent="a box stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = consistency.shapes(C.declared(s, "stool"))
    consistency._sides(mesh, pcs)
    wood = [pc for pc in pcs if pc.get("material") in kidbook.WOOD]
    joints = fasteners.joints(wood, consistency.tolerance(mesh))
    fasteners.keys(wood)
    seq = kidbook.order(wood, joints)
    print([(pc["name"], against) for pc, against in seq], kidbook._words(seq))
""")


def test_the_order_of_a_kids_book_doesnt_depend_on_the_hash_seed():
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([os.path.join(ROOT, "src"), ROOT, os.environ.get("PYTHONPATH", "")])}
    said = [subprocess.run([sys.executable, "-c", ORDER], env={**env, "PYTHONHASHSEED": seed}, cwd=ROOT, capture_output=True, text=True, timeout=120)
            for seed in ("0", "1", "2", "3", "4", "5")]        # the old set read differently on 5 seeds of 6
    assert all(r.returncode == 0 for r in said), said[0].stderr
    assert len({r.stdout for r in said}) == 1 and said[0].stdout.strip()
