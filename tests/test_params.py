"""CALI-108 (#108, the backend) — a part's exact numbers, set by hand, with no Claude call.

Theo: "the advantage to manual cad is the ability to specify things precisely". Listing a part's PARAMS in plain
words, and setting one: converted to mm, refused outside its range, only its line rewritten (its comment kept), built,
written as a new version that says so, the design measured again, and a value the build ignores or clamps said."""

import pytest

from caliper import aero, params
from caliper.design import DesignStore

pytest.importorskip("cadquery")

BOX = '''import cadquery as cq

PARAMS = {
    "w": 400.0,         # width of the box
    # how tall it stands
    "h": 200.0,
    "fillet_r": 6.0,    # fillet radius at the top edges mm
    "spare": 3.0,       # a number the build never reads
    "mesh_rows": 4,     # rows of holes
}
RANGES = {"h": (100.0, 300.0), "w": (100.0, 800.0)}


def build(params):
    p = {**PARAMS, **(params or {})}
    r = min(p["fillet_r"], 2.0)          # clamped: anything over 2 mm is 2 mm
    return cq.Workplane().box(p["w"], 100.0, p["h"]).edges("|Z").fillet(r)
'''


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import caliper.chat as chat

    def no_claude(*a, **k):
        raise AssertionError("a number set by hand never asks Claude")

    monkeypatch.setattr(chat, "author_part", no_claude)
    monkeypatch.setattr(chat, "refine_part", no_claude)
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX, intent="a box")
    return s


def test_the_numbers_are_listed_in_plain_words_with_their_ranges(store):
    got = {e["name"]: e for e in params.listing(store, "box")}
    assert list(got) == ["w", "h", "fillet_r", "spare", "mesh_rows"]
    assert got["w"] == {"name": "w", "note": "width of the box", "value": 400.0, "unit": "mm", "range": [100.0, 800.0],
                        "read": True}
    assert got["h"]["note"] == "how tall it stands"                               # the comment line just above it
    assert got["fillet_r"]["range"] is None and got["spare"]["read"] is False
    # what each is, by what the script says (#147 review): a length by its comment or name, a count, nothing known
    assert [got[k]["unit"] for k in ("w", "h", "fillet_r", "spare", "mesh_rows")] == ["mm", "mm", "mm", "", "count"]


def test_only_that_params_line_is_rewritten_its_comment_kept():
    new = aero.write_params(BOX, {"fillet_r": 1.5}, keep_float=True)
    before, after = BOX.splitlines(), new.splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and changed == [
        ('    "fillet_r": 6.0,    # fillet radius at the top edges mm', '    "fillet_r": 1.5,    # fillet radius at the top edges mm')]
    assert '"h": 250.0,' in aero.write_params(BOX, {"h": 250}, keep_float=True)    # a float stays a float
    assert '"h": 250,' in aero.write_params(BOX, {"h": 250})                       # as the drag study writes it


def test_setting_a_number_writes_a_new_version_rebuilt_and_measured_with_no_claude_call(store):
    v = store.design.part("box").version
    got = params.set_value(store, "box", "h", 250, "mm")
    assert got["version"] == v + 1 and got["said"] == "set h to 250 mm by hand" and got["warning"] is None
    assert '"h": 250.0,' in store.read_script("box")
    assert store.part_geometry("box").require_mesh().extents[2] == pytest.approx(250.0, abs=0.01)
    h = store.history("box")[-1]
    assert h["action"] == "params" and h["feedback"] == "set h to 250 mm by hand" and h["params"] == {"h": [200.0, 250.0]}
    assert got["report"] is not None                                               # the design measured again


def test_inches_in_millimetres_stored(store):
    got = params.set_value(store, "box", "h", 10, "in")
    assert got["value"] == pytest.approx(254.0) and got["said"] == "set h to 10 in by hand"
    assert '"h": 254.0,' in store.read_script("box")


def test_a_value_outside_its_range_is_refused_with_the_range_and_nothing_written(store):
    v = store.design.part("box").version
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 400 mm is outside it$"):
        params.set_value(store, "box", "h", 400, "mm")
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 1 ft is outside it$"):
        params.set_value(store, "box", "h", 1, "ft")                               # 304.8 mm
    with pytest.raises(ValueError, match="has no number called 'depth'"):
        params.set_value(store, "box", "depth", 10)
    with pytest.raises(ValueError, match="is a length: give it in mm or in"):
        params.set_value(store, "box", "h", 10, "furlongs")
    assert store.design.part("box").version == v and '"h": 200.0,' in store.read_script("box")


def test_a_value_the_build_ignores_or_clamps_is_said(store):
    clamped = params.set_value(store, "box", "fillet_r", 8, "mm")
    assert clamped["moved"] is False
    assert clamped["warning"] == "the part's shape didn't change: its build clamps or ignores fillet_r at 8 mm"
    unread = params.set_value(store, "box", "spare", 9)
    assert unread["warning"] == "spare isn't used by the part's build, so setting it changed nothing"


def test_the_api_lists_and_sets_a_number(store, monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    c, slug = TestClient(create_app()), store.design.slug
    listed = c.get(f"/api/designs/{slug}/parts/box/params").json()
    assert [e["name"] for e in listed["params"]] == ["w", "h", "fillet_r", "spare", "mesh_rows"]
    got = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 500, "unit": "mm"})
    assert got.status_code == 200 and got.json()["said"] == "set w to 500 mm by hand"
    assert next(p for p in got.json()["design"]["parts"] if p["id"] == "box")["version"] == 2
    bad = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 900, "unit": "mm"})
    assert bad.status_code == 422 and "w must be between 100 and 800 mm" in bad.json()["detail"]



# --- #147 review ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,unit,why", [
    ("mesh_rows", "in", "mesh rows is a count: give a number, no unit"),
    ("mesh_rows", "mm", "mesh rows is a count: give a number, no unit"),
    ("h", "furlongs", "h is a length: give it in mm or in, not 'furlongs'"),
])
def test_only_a_length_converts_and_a_unit_on_a_count_is_refused(store, name, unit, why):
    """#147 review: "mesh_rows 8 in" was 203.2 on an inch design. A count takes a number, no unit."""
    with pytest.raises(ValueError, match=f"^{why}$"):
        params.set_value(store, "box", name, 8, unit)
    assert '"mesh_rows": 4,' in store.read_script("box")
    got = params.set_value(store, "box", "mesh_rows", 8)
    assert '"mesh_rows": 8,' in store.read_script("box") and got["said"] == "set mesh_rows to 8 by hand"


def test_a_number_with_no_known_unit_is_taken_as_it_is_and_said(store):
    got = params.set_value(store, "box", "spare", 9)
    assert got["value"] == 9.0 and "spare has no unit in its script, so 9 is taken as it is, not converted" in got["notes"]


def test_a_unit_on_a_number_of_no_known_kind_is_refused_never_dropped(store):
    """#147 review, blocking: "set p1z to 26 in" (Theo's leaf_rear: no comment) wrote 26, as mm, with a note."""
    leaf = BOX.replace('    "mesh_rows": 4,     # rows of holes\n', '    "mesh_rows": 4,     # rows of holes\n    "p1z": 660.4,\n')
    store.write_part("leaf", leaf, intent="a leaf")
    v = store.design.part("leaf").version
    for unit in ("in", "mm"):
        with pytest.raises(ValueError, match="^I don't know if p1z is a length: give it in mm, without a unit$"):
            params.set_value(store, "leaf", "p1z", 26, unit)
    assert store.design.part("leaf").version == v and '"p1z": 660.4,' in store.read_script("leaf")


#: Theo's own PARAMS lines (read-only from his designs; the names and comments the review quotes), with what each is.
THEOS = [
    ("rib_v", "vertical rib between rows mm", "mm"),                      # i-want: a unit in the comment wins
    ("rib_h", "circumferential rib between cols mm", "mm"),
    ("mesh_rows", "number of vertical rows of mesh openings", "count"),
    ("wall_t", "printed shell thickness mm (increased from 4mm)", "mm"),
    ("foot_fillet_r", "", "mm"),
    ("shoulder", "side from wall top to roof edge: 1 = straight, 2 = round", "choice"),   # the cargo box
    ("tail_curve", "1 = straight panels; 2 = teardrop curve", "choice"),
    ("edges", "0: no edges; 1: front and back edges; 2: all four sides", "choice"),
    ("spine_back", "1: the spine runs to the back of the floor; 0: it stops under the X's middle", "choice"),
    ("edge_w", '1 in: edges under the walls (see "edges")', "mm"),
    ("p1z", "", ""),                                                        # leaf_rear: not known, a unit refused
    ("p1x", "", ""),
    ("recess_margin", "border left around recess", ""),                     # step-stool
    ("ribs", "how many ribs around the cone", "count"),                     # not Theo's: a count by its comment alone
]


@pytest.mark.parametrize("name,note,unit", THEOS)
def test_what_each_of_theo_s_numbers_is(name, note, unit):
    assert params.unit_of(name, note) == unit


def test_a_choice_takes_no_unit(store):
    shaped = BOX.replace('    "mesh_rows": 4,     # rows of holes\n',
                         '    "mesh_rows": 4,     # rows of holes\n    "shoulder": 1.4,   # side from wall top to roof '
                         'edge: 1 = straight, 2 = round\n')
    store.write_part("box", shaped, intent="a box")
    assert {e["name"]: e["unit"] for e in params.listing(store, "box")}["shoulder"] == "choice"
    with pytest.raises(ValueError, match="^shoulder is a choice: give a number, no unit$"):
        params.set_value(store, "box", "shoulder", 2, "in")


def test_no_range_is_said_and_a_ranged_number_says_nothing_of_it(store):
    got = params.set_value(store, "box", "fillet_r", 1.5)
    assert "no range is set for fillet_r in the script, so it isn't checked" in got["notes"]
    assert not [n for n in params.set_value(store, "box", "h", 250)["notes"] if "no range" in n]


def test_a_partial_clamp_is_measured_and_said(store):
    """#107's fillet: asked more than the build makes. The shape moves (1.5 → 2), so only a probe of the built fillet
    says it: asked 3 mm, built 2 mm."""
    params.set_value(store, "box", "fillet_r", 1.5)
    exact = params.set_value(store, "box", "fillet_r", 1.8)
    assert exact["moved"] and not [n for n in exact["notes"] if n.startswith("asked")]
    got = params.set_value(store, "box", "fillet_r", 3)
    assert got["moved"] and "asked 3 mm, built 2 mm (the closest fillet)" in got["notes"]


def test_a_part_with_a_strength_check_says_check_it_again(store):
    import json
    import os

    from caliper import load_study

    run = {"id": "20261107-000000-box", "part": "box", "version": store.design.part("box").version, "created": 1.0,
           "min_safety": 2, "safety": 3.0, "holds": True, "cases": []}
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    assert "strength: check the box again" in params.set_value(store, "box", "h", 250)["notes"]
