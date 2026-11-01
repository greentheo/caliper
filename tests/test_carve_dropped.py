"""CALI-87 (#63, finding 2) — a carve fits the shape it was cut from: every revision that changes the part drops
it and says so, and a picture or lightening (which would cut into the carved shape) is refused until it's off."""

import json
import os

import pytest

from caliper import aero, carve, construction, frame_study, lighten, pictures
from caliper.design import DesignStore

from .test_mixed import MIXED

pytest.importorskip("cadquery")


@pytest.fixture
def carved(tmp_path):
    """A plywood top on printed sides, carved (here: its own shape saved as the carve, as carve.adopt writes it)."""
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED, intent="a plywood top on printed sides")
    folder = os.path.join(store.part_dir("stool"), "carved")
    os.makedirs(folder)
    store.part_geometry("stool").require_mesh().export(os.path.join(folder, "carved-x-01.stl"))
    store.write_part("stool", MIXED.rstrip("\n") + '\n\n\n# The printed rest as carved by the strength study (CALI-82): '
                     'Caliper builds the part as this mesh.\nCARVED = "carved-x-01.stl"\n', action="carve")
    assert carve.NAME in store.read_script("stool")
    return store


def _record(folder: str, rec: dict) -> str:
    rid = "20261101-000000-abcd"
    os.makedirs(os.path.join(folder, rid))
    with open(os.path.join(folder, rid, "run.json"), "w") as f:
        json.dump(rec, f)
    return rid


def _dropped(store, got):
    assert carve.NAME not in store.read_script("stool")
    wrote = next(h for h in reversed(store.history("stool")) if h.get("feedback"))   # the revision, not a note after it
    assert "carve came off" in got["note"] and "carve came off" in wrote["feedback"]


def test_a_build_what_if_adopted_drops_the_carve(carved):
    _dropped(carved, construction.adopt(carved, "stool", {"top": 19.05}))


def test_a_frame_design_adopted_drops_the_carve(carved):
    pytest.importorskip("whittle")
    rid = _record(frame_study.runs_dir(carved), {"part": "stool", "stations": [{"index": 0, "design": {}, "mass_lb": 9.0, "safety": 3.0}],
                                                 "params": {"w": 320.0}})
    _dropped(carved, frame_study.adopt(carved, rid, 0))


def test_gusset_plates_adopted_drop_the_carve(carved):
    rid = _record(frame_study.gussets_dir(carved), {"part": "stool", "joints": {}, "thickness": 6.35, "plates": 2})
    _dropped(carved, frame_study.adopt_gussets(carved, rid))


def test_a_drag_station_adopted_drops_the_carve(carved):
    rid = _record(aero.runs_dir(carved), {"part": "stool", "searched": ["w"], "start": dict.fromkeys(
        ["w", "d", "h", "side"], 0), "stations": [{"index": 0, "design": {"w": 320.0}}]})
    _dropped(carved, aero.adopt(carved, rid, 0))


def test_a_picture_on_a_carved_part_is_refused(carved):
    with pytest.raises(ValueError, match="it's carved, so putting a T-rex on it would cut into the shape"):
        pictures.put(carved, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", strength=False)
    assert carve.NAME in carved.read_script("stool")
    from caliper import chat

    res = chat.picture_part(carved, "stool", "T-rex", "", strength=False)      # as the person reads it
    assert not res.ok and res.reply == (
        "I couldn't put a T-rex on it: it's carved, so putting a T-rex on it would cut into the shape the carve was "
        "made for. Take the carve off first (any change through the chat does), put the T-rex on, then carve it again.")


def test_lightening_a_carved_part_is_refused(carved):
    rid = _record(lighten.runs_dir(carved), {"part": "stool", "version": 2, "panels": [], "stations": [
        {"index": 0, "panels": {}, "removed": 0.0, "holes": 0, "saved_lb": 0.0, "safety": 3.0}]})
    with pytest.raises(ValueError, match="it's carved, so lightening it would cut into the shape"):
        lighten.adopt(carved, rid, 0)
    assert carve.NAME in carved.read_script("stool")
