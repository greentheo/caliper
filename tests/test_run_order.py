"""CALI-97 (#100, item 8) — "the latest run" is the one made last. Run ids are a second and four random hex digits,
and every listing sorted them as strings, so two runs started in the same second came back in either order (the
reviewer's flake: test_resolved's finer run read as the older, coarser one about half the time)."""

import json
import os

import pytest

from caliper import aero, carve, cutplan, frame_study, lighten, load_study, patterns, samples
from caliper import whittle_bridge as wb
from caliper.design import DesignStore

#: Two runs in one second, the older with the suffix that sorts last as a string.
OLDER, NEWER = "20261105-220403-4126", "20261105-220403-143f"

LISTINGS = [
    (load_study.list_runs, "loads", "run.json"),
    (carve.list_runs, "carves", "run.json"),
    (lighten.list_runs, "lighten", "run.json"),
    (aero.list_runs, "aero", "run.json"),
    (frame_study.list_runs, "frames", "run.json"),
    (frame_study.list_gussets, "gussets", "run.json"),
    (wb.list_runs, "whittle", "run.json"),
    (patterns.list_runs, "patterns", "run.json"),
    (cutplan.list_runs, "cutplans", "cutplan.json"),
]


def _two_in_one_second(store, folder, name):
    for rid, created in ((OLDER, 1762380243.50), (NEWER, 1762380244.42)):
        os.makedirs(os.path.join(store.root, folder, rid), exist_ok=True)
        with open(os.path.join(store.root, folder, rid, name), "w") as f:
            json.dump({"id": rid, "part": "p", "kind": folder, "created": created, "version": 1}, f)


def test_the_fixture_is_the_case_that_broke():
    assert sorted([OLDER, NEWER], reverse=True)[0] == OLDER          # what sorting the ids did


@pytest.mark.parametrize("listing,folder,name", LISTINGS, ids=[f for _, f, _ in LISTINGS])
def test_the_newest_run_comes_first_even_in_the_same_second(tmp_path, listing, folder, name):
    store = DesignStore.create("runs", base=str(tmp_path / "designs"))
    _two_in_one_second(store, folder, name)
    assert [r["id"] for r in listing(store)] == [NEWER, OLDER]


def test_a_saved_sample_keeps_the_run_made_last(tmp_path):
    store = DesignStore.create("runs", base=str(tmp_path / "designs"))
    _two_in_one_second(store, "loads", "run.json")
    out = samples.save(store.design.slug, "two-runs", base=str(tmp_path / "designs"), out=str(tmp_path / "samples"))
    assert os.listdir(os.path.join(out, "loads")) == [NEWER]
