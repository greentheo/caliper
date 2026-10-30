"""CALI-39 — shape a part for drag and get numbers back, not a mesh.

The PARAMS read/rewrite is pure and fast. The study runs the real thing — a warm build worker,
whittle's ParametricStudy, a tiny box — gated on cadquery and whittle, at minimal effort.
"""

import ast
import os

import pytest

from caliper import aero, chat
from caliper.design import DesignStore

SCRIPT = '''# a box with a tunable tail
PARAMS = {
    "width": 200.0,    # across
    "depth": 120,
    "height": 100.0,
    "x_front": 0.0,
    "tail_len": 0.0,   # 0 = square back
    "tail_drop": 0.0,
    "label": "box",    # not a number: left alone
}


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}
    W, D, H, x0 = p["width"], p["depth"], p["height"], p["x_front"]
    L = min(max(p["tail_len"], 0.0), 0.8 * D)

    def section(x, top):
        pts = [(x, -W / 2, 0), (x, W / 2, 0), (x, W / 2, top), (x, -W / 2, top)]
        return cq.Wire.makePolygon([cq.Vector(*q) for q in pts], close=True)

    body = cq.Workplane("XY").add(cq.Solid.makeLoft([section(x0, H), section(x0 - (D - L), H)], True))
    if L > 1.0:
        tail = cq.Solid.makeLoft([section(x0 - (D - L), H), section(x0 - D, H - p["tail_drop"])], True)
        body = body.union(cq.Workplane("XY").add(tail))
    return body
'''


# --- PARAMS: read and rewrite ------------------------------------------------------------
def test_read_params_takes_the_numbers_and_skips_everything_else():
    got = aero.read_params(SCRIPT)
    assert got == {"width": 200.0, "depth": 120.0, "height": 100.0, "x_front": 0.0,
                   "tail_len": 0.0, "tail_drop": 0.0}


def test_negative_numbers_are_numbers():
    assert aero.read_params('PARAMS = {"x": -457.2}\n') == {"x": -457.2}


def test_a_script_without_params_says_so():
    assert aero.read_params("def build(params):\n    pass\n") is None
    assert aero.read_params("this is not python(") is None


def test_rewrite_changes_only_the_named_numbers():
    out = aero.write_params(SCRIPT, {"tail_len": 312.456, "tail_drop": 40})
    assert aero.read_params(out)["tail_len"] == pytest.approx(312.456)
    assert aero.read_params(out)["tail_drop"] == 40.0
    # every other line — comments, layout, the build function — is byte-for-byte the same
    before, after = SCRIPT.splitlines(), out.splitlines()
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(before) == len(after) and len(changed) == 2
    assert "# 0 = square back" in out and '"label": "box"' in out
    ast.parse(out)                                         # still valid Python


def test_rewrite_is_byte_offset_safe_with_unicode_comments_before_it():
    script = '# “tunable” — a box\nPARAMS = {"r": 5.0}  # radius ≥ 0\n'
    assert aero.write_params(script, {"r": 12.5}) == '# “tunable” — a box\nPARAMS = {"r": 12.5}  # radius ≥ 0\n'


def test_rewrite_refuses_a_name_it_cannot_place():
    with pytest.raises(KeyError, match="nope"):
        aero.write_params(SCRIPT, {"nope": 1})
    with pytest.raises(KeyError, match="no module-level PARAMS"):
        aero.write_params("x = 1\n", {"a": 1})


def test_numbers_are_written_tidily():
    out = aero.write_params('PARAMS = {"a": 1.0, "b": 2.0, "c": 3.0}\n', {"a": 10.0, "b": 0.30000001, "c": -0.0})
    assert out == 'PARAMS = {"a": 10, "b": 0.3, "c": 0}\n'


# --- suggestions -------------------------------------------------------------------------
def test_shape_and_radius_parameters_are_suggested_for_the_search():
    assert aero.suggest("tail_len", 0)["search"] and aero.suggest("tail_len", 0)["bounds"] == [0, 600]
    assert aero.suggest("tail_edge_r", 0)["search"]
    assert aero.suggest("top_taper_deg", 0)["bounds"] == [0, 20]


def test_envelope_dimensions_are_not_searched_by_default():
    s = aero.suggest("width", 1879.6)
    assert not s["search"] and s["bounds"][0] < 1879.6 < s["bounds"][1]


# --- the study, for real (OCCT + whittle) ---------------------------------------------------
@pytest.fixture
def tunable(tmp_path):
    store = DesignStore.create("a tunable box", base=str(tmp_path / "designs"))
    store.write_part("box", SCRIPT, intent="a box with a tunable tail")
    return store


def _quick(store, **kw):
    return aero.study(store, "box", {"tail_len": (0, 90), "tail_drop": (0, 50)},
                      remove_up_to=0.1, stations=2, effort=0.05, resolution=10, **kw)


def test_a_study_returns_numbers_for_every_station(tunable):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    seen = []
    rec = _quick(tunable, emit=lambda k, t="", **d: seen.append(k))
    assert rec["kind"] == "parametric" and len(rec["stations"]) == 2
    first, last = rec["stations"]
    assert first["design"]["tail_len"] == 0                       # station 0 is the part as it is
    assert set(rec["searched"]) == {"tail_len", "tail_drop"}
    assert last["metrics"]["drag"] <= 1.0 + 1e-9                  # never worse than the start
    assert os.path.exists(aero.station_path(tunable, rec["id"], 1))
    assert "progress" in seen and seen[-1] == "done"
    assert rec["builds"] > 5


def test_bringing_numbers_back_makes_a_parametric_revision(tunable):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    rec = _quick(tunable)
    got = aero.adopt(tunable, rec["id"], 1)
    assert tunable.is_scripted("box")                             # still a script, not a mesh
    assert tunable.design.part("box").origin == "authored"
    now = aero.read_params(tunable.read_script("box"))
    for name, value in got["params"].items():
        assert now[name] == pytest.approx(value, abs=1e-3)
        assert round(value, 1) == value                       # build-to numbers, not float noise
    assert tunable.history("box")[-1]["aero_run"] == rec["id"]
    # and chat can keep revising it like any other part
    assert chat.offline_classify(tunable, "make it wider", scope="box").action == "refine"


def test_a_part_without_params_is_refused_with_a_way_forward(tmp_path):
    store = DesignStore.create("plain", base=str(tmp_path / "designs"))
    store.write_part("box", "def build(params):\n    import cadquery as cq\n    return cq.Workplane().box(1,1,1)\n")
    with pytest.raises(ValueError, match="make it tunable"):
        aero.study(store, "box", {"x": (0, 1)})


def test_a_range_that_excludes_the_current_value_is_refused(tunable):
    with pytest.raises(ValueError, match="outside the range"):
        aero.study(tunable, "box", {"width": (10, 20)})


def test_an_unknown_parameter_is_refused(tunable):
    with pytest.raises(ValueError, match="no 'nope'"):
        aero.study(tunable, "box", {"nope": (0, 1)})


def test_run_ids_cannot_escape_the_design(tunable):
    assert aero.load_run(tunable, "../../etc") is None
    with pytest.raises(ValueError):
        aero.station_path(tunable, "../x", 0)


def test_a_parameter_pinned_at_its_limit_is_named():
    """'The bounds ran out' is vague; which bound, is actionable. (Seen live: tail_len stuck at 500.)"""
    bounds = {"tail_len": (0, 500), "tail_drop": (0, 250), "tail_edge_r": (0, 120), "width": (1800, 1900)}
    start = {"tail_len": 0, "tail_drop": 0, "tail_edge_r": 0, "width": 1880}
    best = {"tail_len": 500, "tail_drop": 146, "tail_edge_r": 0, "width": 1800}
    notes = aero.limit_notes(bounds, start, best)
    assert notes[0].startswith("tail_len ended at its upper limit (500)")
    assert "volume you allow" in notes[0]
    assert not any("tail_drop" in n for n in notes)            # mid-range: not a limit
    assert not any("tail_edge_r" in n for n in notes)          # started at 0: a choice, not a limit
    assert any(n.startswith("width ended at its lower limit (1800)") for n in notes)


def test_params_written_inside_build_with_inch_arithmetic_are_still_found():
    """Seen live: the author put PARAMS inside build() and wrote `70.5 * 25.4` — both still searchable."""
    script = (
        "def build(params):\n"
        "    import cadquery as cq\n"
        "    PARAMS = {\n"
        '        "width_mm": 70.5 * 25.4,   # full car width\n'
        '        "p0z": 12  * 25.4,\n'
        '        "gap": -(18 * 25.4) / 2,\n'
        "    }\n"
        "    p = {**PARAMS, **(params or {})}\n"
        "    return cq.Workplane().box(p['width_mm'], 10, 10)\n"
    )
    got = aero.read_params(script)
    assert got["width_mm"] == pytest.approx(1790.7) and got["p0z"] == pytest.approx(304.8)
    assert got["gap"] == pytest.approx(-228.6)
    out = aero.write_params(script, {"width_mm": 1800})
    assert '"width_mm": 1800,   # full car width' in out          # the whole expression replaced
    assert aero.read_params(out)["p0z"] == pytest.approx(304.8)    # the rest untouched


def test_a_division_by_zero_is_not_a_number():
    assert aero.read_params('PARAMS = {"a": 1 / 0, "b": 2.0}\n') == {"b": 2.0}


def test_the_signature_ignores_numbers_but_not_code():
    a = aero.shape_signature(SCRIPT)
    assert a == aero.shape_signature(aero.write_params(SCRIPT, {"tail_len": 77, "width": 300}))
    assert a != aero.shape_signature(SCRIPT.replace("0.8 * D", "0.7 * D"))


def test_numbers_from_a_study_of_an_older_script_are_refused(tunable):
    """Seen while comparing shapes: a run from the box's previous parametrisation was still listed."""
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    rec = _quick(tunable)
    tunable.write_part("box", SCRIPT.replace("0.8 * D", "0.7 * D"), action="refine")   # code changed
    with pytest.raises(ValueError, match="earlier version"):
        aero.adopt(tunable, rec["id"], 1)


def test_numbers_from_the_same_script_can_be_swapped_freely(tunable):
    """Adopting writes only numbers, so trying station 1 then station 0 must both work."""
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    rec = _quick(tunable)
    aero.adopt(tunable, rec["id"], 1)
    aero.adopt(tunable, rec["id"], 0)
    assert aero.read_params(tunable.read_script("box"))["tail_len"] == 0


# --- CALI-42: a part's own ranges, and what it has to hold --------------------------------------
RANGED = SCRIPT + '''

# how far a study may take each number
RANGES = {
    "tail_len": (0.0, 90.0),
    "tail_drop": (0, 30 + 20),
    "label": "not a range",
}
'''


def test_a_part_can_give_its_own_search_ranges():
    r = aero.read_ranges(RANGED)
    assert r == {"tail_len": (0.0, 90.0), "tail_drop": (0.0, 50.0)}
    assert aero.suggest("tail_len", 0.0, r) == {"search": True, "bounds": [0.0, 90.0], "from": "part"}
    # a range that leaves out where the part is now is widened to take it in
    assert aero.suggest("tail_drop", 70.0, r)["bounds"] == [0.0, 70.0]
    assert aero.suggest("width", 200.0, r)["search"] is False                 # not in RANGES: a guess
    assert aero.suggest("tail_curve", 1.0, r)["search"] is False              # ...even if it sounds like shape
    assert aero.suggest("tail_curve", 1.0)["search"] is True
    assert aero.read_ranges(SCRIPT) == {}


def test_ranges_dont_change_the_shape_but_keeps_do():
    sig = aero.shape_signature(SCRIPT)
    assert aero.shape_signature(RANGED) == sig
    kept = SCRIPT + '\n\ndef keeps(params):\n    return [{"name": "cargo", "lo": (0, 0, 0), "hi": (1, 1, 1)}]\n'
    assert aero.shape_signature(kept) != sig


def _cube(n=100.0):
    v = [(x, y, z) for x in (0, n) for y in (0, n) for z in (0, n)]
    f = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
         (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return v, f


def test_a_surface_that_crosses_a_keep_is_measured_by_how_deep():
    v, f = _cube()
    inside, across, touching = aero.keep_check(v, f, [
        {"name": "inside", "lo": (10, 10, 10), "hi": (90, 90, 90)},
        {"name": "across", "lo": (50, 10, 10), "hi": (150, 90, 90)},       # the x=100 face runs through it
        {"name": "touching", "lo": (0, 0, 0), "hi": (100, 100, 50)},       # sits on the faces
    ])
    assert inside["clear"] and inside["depth_mm"] == 0
    assert not across["clear"] and across["depth_mm"] == pytest.approx(40, abs=2)
    assert touching["clear"]


KEPT = SCRIPT + '''

def keeps(params):
    """the top-back corner holds something tall"""
    return [{"name": "crate", "note": "a crate at the back", "lo": (-120, -50, 0), "hi": (-70, 50, 90)}]
'''


def test_a_study_keeps_what_the_part_has_to_hold(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    store = DesignStore.create("a box that holds a crate", base=str(tmp_path / "designs"))
    store.write_part("box", KEPT, intent="a box with a crate at the back")
    rec = _quick(store)
    assert [k["name"] for k in rec["keeps"]] == ["crate"]
    assert any(n.startswith("Kept clear: crate (a crate at the back)") for n in rec["notes"])
    # whatever the search found, a station that cuts in is owned up to
    last = rec["stations"][-1]["design"]
    if last["tail_drop"] > 12:
        assert any(n.startswith("Not quite clear") for n in rec["notes"])
