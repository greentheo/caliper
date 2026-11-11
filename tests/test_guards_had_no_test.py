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
