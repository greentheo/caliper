"""CALI-87 (#63, finding 3) — a carve is of one version of a part, and is only adopted onto that version."""

import json
import os

import pytest

from caliper import carve
from caliper.design import DesignStore

from .test_mixed import MIXED

pytest.importorskip("cadquery")


def _carved_at_v1(tmp_path):
    """A part, a carve run of its first version (one step: the part as built), then a second version."""
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED, intent="a plywood top on printed sides")
    rid = "20261101-000000-abcd"
    run = os.path.join(carve.runs_dir(store), rid)
    os.makedirs(run)
    store.part_geometry("stool").require_mesh().export(os.path.join(run, "station_00.stl"))
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({"id": rid, "part": "stool", "kind": "carve", "version": 1, "min_safety": 2.0, "best": 0, "spacing_mm": 6.35,
                   "stations": [{"index": 0, "removed": 0.0, "safety": 3.0, "holds": True, "whole": 2.5,
                                 "whole_holds": True, "printed_g": 900, "saved_g": 0, "stl": "station_00.stl"}]}, f)
    store.write_part("stool", MIXED.replace('"lb": 200', '"lb": 150'), intent="a lighter load")
    return store, rid


def test_a_carve_of_an_older_version_isnt_adopted(tmp_path):
    store, rid = _carved_at_v1(tmp_path)
    with pytest.raises(ValueError, match="version 1.*version 2"):
        carve.adopt(store, rid, 0)
    assert store.design.part("stool").version == 2 and "CARVED" not in store.read_script("stool")


def test_nor_through_the_api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store, rid = _carved_at_v1(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    got = TestClient(create_app()).post(f"/api/designs/{store.design.slug}/carve/{rid}/adopt", json={"station": 0})
    assert got.status_code == 409 and "version" in got.json()["detail"]
