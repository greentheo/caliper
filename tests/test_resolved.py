"""CALI-97 (#80; rule 6) — a ✓ can't rest on an FEA too coarse to see the wall it's checking.

Found on Theo's bar stool: "✓ Holds a 250 lb person sitting … 2.58x", governed by the FEA, at 4.6 mm voxels across
a 3.9 mm printed wall (about one voxel through it). Reworked from #100's review: 4 voxels across (RESOLVE_MIN), a
finer run only within a voxel budget, else "not checked"; the thinnest wall, never a percentile; a ✗ stays a ✗."""

import math
import os
import time

import pytest

from caliper import answers, design_api, load_study, studies
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: A printed PETG tube, 4 mm wall, stood on: the load on its rim, held by the floor.
TUBE = '''import cadquery as cq

PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0}
BUILD = {"material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().circle(p["r"]).circle(p["r"] - p["wall"]).extrude(p["h"])


def construction(params, build=None):
    b = {**BUILD, **(build or {})}
    return [{"name": "tube", "kind": "printed", "material": b["material"], "infill": b["infill"]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "a foot", "lb": 40, "factor": 2.0, "lo": (-32, -32, p["h"] - 2), "hi": (32, 32, p["h"])}]
'''
#: The reviewer's spool (#100): two printed discs hung on a 10 mm tube neck with 0.6 mm walls, the load through the
#: neck. The neck is a sliver of the surface, so a 10th-percentile wall read 20 mm, the voxels went to 5 mm, and the card
#: said "✓ Holds a foot, about 2.4 times over" (9.7x at 10 lb); a hand check gives about 1.4x. main read ✗ 0.8x.
SPOOL = TUBE.replace('''PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0}''', '''PARAMS = {"r": 30.0, "disc": 20.0, "nr": 10.0, "wall": 0.6, "neck": 10.0}''').replace(
    '''    return cq.Workplane().circle(p["r"]).circle(p["r"] - p["wall"]).extrude(p["h"])''',
    '''    lo = cq.Workplane().circle(p["r"]).extrude(p["disc"])
    neck = (cq.Workplane().circle(p["nr"]).circle(p["nr"] - p["wall"]).extrude(p["neck"] + 2)
            .translate((0, 0, p["disc"] - 1)))
    hi = cq.Workplane().circle(p["r"]).extrude(p["disc"]).translate((0, 0, p["disc"] + p["neck"]))
    return lo.union(neck).union(hi)''').replace(
    '''"lo": (-32, -32, p["h"] - 2), "hi": (32, 32, p["h"])''',
    '''"lo": (-28, -28, 2 * p["disc"] + p["neck"] - 2), "hi": (28, 28, 2 * p["disc"] + p["neck"])''')
#: No loads(): a strength check of it stops at once ("it has no loads()").
NO_LOADS = TUBE.split("\n\ndef loads")[0] + "\n"
#: Fifty times the load: it fails, on the same coarse voxels.
HEAVY = TUBE.replace('"lb": 40', '"lb": 2000')
GOALS = """written_by: caliper
checks:
- id: strength_foot
  label: holds a foot (40 lb), 2 times over
  metric: strength.safety
  op: '>='
  limit: 2.0
  source: assumed
"""
COARSE = "Not resolved yet: the check was too coarse to see its thinnest walls, 4 mm around z "   # which (#139)
COARSE_END = " mm. Check it again finer."
NOT_CHECKED = load_study.NOT_CHECKED


def _store(tmp_path, src=TUBE, name="designs"):
    store = DesignStore.create("a tube", base=str(tmp_path / name))
    store.write_part("tube", src, intent="a printed tube")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(GOALS)
    return store


def _studied(tmp_path, monkeypatch, through, src=TUBE):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    store = _store(tmp_path, src, f"designs{through}")
    return store, load_study.study(store, "tube")


def _work(store, pid=None):
    lines = answers.answers(store, design_api.design_state(store), pid)[1]["lines"]
    return [ln for ln in lines if ln.get("study") == "load"]


def test_it_takes_four_across():
    """The foreman's call on #100, from its own table (the printed box: ✓ 2.7x at 2 across, ✗ 1.9x at 4)."""
    assert load_study.RESOLVE_MIN == 4.0


def test_a_verdict_on_an_fea_that_cant_see_the_wall_reads_warn(tmp_path, monkeypatch):
    store, rec = _studied(tmp_path, monkeypatch, 1)               # 4 mm voxels across a 4 mm wall: one voxel
    (case,) = rec["cases"]
    assert case["governs"] == "fea" and case["holds"] and rec["thinnest_mm"] == pytest.approx(4.0, abs=0.3)
    assert not rec["resolved"]
    part = _work(store, "tube")
    assert part and all(ln["status"] == "warn" and ln["text"].startswith(COARSE) and ln["text"].endswith(COARSE_END) for ln in part), part
    design = _work(store)
    assert design and all(ln["status"] == "warn" and COARSE in ln["text"] for ln in design), design
    # the page's numbers: no green "holds" under the warn (#100 item 7)
    (shown,) = design_api.design_state(store)["load_runs"]
    assert shown["cases"][0]["unresolved"] == "unresolved"
    assert studies._headline("load", shown) == ("not resolved yet: too coarse to see its walls (the FEA read "
                                                f"{round(case['safety'], 1):g}x)", None)
    # the finer run it offers: 4 voxels across, and about how long
    assert rec["finer"]["spacing_mm"] <= rec["thinnest_mm"] / 4 and rec["finer"]["minutes"] >= 1
    finer = load_study.study(store, "tube", spacing=rec["finer"]["spacing_mm"])
    assert finer["resolved"] and finer["spacing_mm"] == pytest.approx(rec["finer"]["spacing_mm"], abs=0.01)
    assert not [ln for ln in _work(store, "tube") if ln["text"].startswith(COARSE)]
    assert not [ln for ln in _work(store) if COARSE in ln["text"]]        # the design card reads the latest too


def test_the_same_tube_seen_finely_reads_as_its_safety_says_with_about(tmp_path, monkeypatch):
    store, rec = _studied(tmp_path, monkeypatch, 4)               # 1 mm voxels: four across the wall
    assert rec["resolved"] and "finer" not in rec
    (part,) = _work(store, "tube")
    assert part["text"].startswith(("Holds a foot, about ", "Doesn't hold a foot: only about ")), part["text"]
    (design,) = _work(store)
    assert ": about " in design["text"] and design["text"].endswith("x."), design["text"]


def test_two_across_isnt_enough_any_more(tmp_path, monkeypatch):
    """At RESOLVE_MIN 2 this run was a ✓; it's 2 mm voxels across a 4 mm wall."""
    store, rec = _studied(tmp_path, monkeypatch, 2)
    assert rec["thinnest_mm"] / rec["spacing_mm"] == pytest.approx(2, abs=0.1) and not rec["resolved"]
    assert [ln["status"] for ln in _work(store, "tube")] == ["warn"]


def test_a_fail_on_coarse_voxels_stays_a_fail(tmp_path, monkeypatch):
    """#100 item 4 (rule 6): an unresolved FEA can't turn a ✗ into a warn. It says the fail may be the model's."""
    store, rec = _studied(tmp_path, monkeypatch, 1, HEAVY)
    (case,) = rec["cases"]
    assert case["governs"] == "fea" and not case["holds"] and not rec["resolved"]
    (part,) = _work(store, "tube")
    assert part["status"] == "bad" and part["text"].startswith("Doesn't hold a foot: only about ")
    assert part["text"].endswith("where its wall is 4 mm, too thin for the voxels to see: the fail may be the model's. "
                                 "Check it again finer."), part["text"]
    (design,) = _work(store)
    assert design["status"] == "bad" and design["text"].startswith("✗ Holds a foot (40 lb), 2 times over (assumed)")
    # the same words as the part card, the same wall (#139's pass)
    assert "where its wall is 4 mm, too thin for the voxels to see: the fail may be the model's" in design["text"]
    (shown,) = design_api.design_state(store)["load_runs"]
    text, ok = studies._headline("load", shown)
    assert ok is False and text.startswith("doesn't hold") and "the fail may be the model's" in text


def test_where_no_run_a_study_may_make_can_see_the_walls_it_says_not_checked(tmp_path, monkeypatch):
    """#100 items 1 and 2: on the bar stool the finer run it offered was 0.15 mm (7×10^10 voxels, "about 5108 min").
    A finer run is capped by the voxel budget; where that can't reach four across, it isn't offered."""
    monkeypatch.setattr(load_study, "MAX_VOXELS", 2_000)          # the tube, as big for its walls as the bar stool
    store, rec = _studied(tmp_path, monkeypatch, 4)
    assert not rec["resolved"] and "finer" not in rec and rec["too_thin"]
    assert any(NOT_CHECKED in n for n in rec["notes"])
    (part,) = _work(store, "tube")
    assert part["status"] == "warn" and part["text"] == NOT_CHECKED
    (design,) = _work(store)
    assert design["status"] == "warn" and NOT_CHECKED in design["text"]
    (shown,) = design_api.design_state(store)["load_runs"]
    assert shown["cases"][0]["unresolved"] == "unchecked"
    assert studies._headline("load", shown)[1] is None


def test_an_asked_for_voxel_size_cant_go_past_the_budget(tmp_path, monkeypatch):
    """#100 item 2: an explicit spacing skipped the budget, so one click could ask for 10^10 voxels."""
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "MAX_VOXELS", 2_000)
    store = _store(tmp_path)
    rec = load_study.study(store, "tube", spacing=0.1)
    least = load_study.finest(math.pi * (30 ** 2 - 26 ** 2) * 80, 80, load_study.FINER_BUDGET)
    assert rec["spacing_mm"] == pytest.approx(least, rel=0.05) and rec["voxels"] < 8 * 2_000 * 1.5
    assert any(n.startswith("Asked for 0.1 mm voxels, finer than a study of a part this size may take")
               for n in rec["notes"])


def test_a_spool_hung_on_a_thin_neck_never_reads_holds(tmp_path, monkeypatch):
    """The reviewer's blocker on #100: the wall that gates a verdict is the thinnest, so the 0.6 mm neck the load goes
    through is seen (or the verdict says it isn't), never a ✓ from voxels that can't see it."""
    assert SPOOL != TUBE and "nr" in SPOOL
    store, rec = _studied(tmp_path, monkeypatch, 4, SPOOL)
    lines = _work(store, "tube") + _work(store)
    assert lines and all(ln["status"] != "ok" for ln in lines), lines
    assert not [ln for ln in lines if ln["text"].startswith(("Holds", "✓"))], lines
    assert rec["thinnest_mm"] == pytest.approx(0.6, abs=0.05) and rec["too_thin"]


@pytest.mark.parametrize("mm,inches,said", [
    (0.3, True, "0.3 mm"),          # the bar stool's lip: never "0 in"
    (2.84, True, "1/8 in"), (3.9, True, "5/32 in"), (4.0, True, "5/32 in"), (12.7, True, "1/2 in"),
    (25.4, True, "1 in"), (4.0, False, "4 mm"), (3.9, False, "3.9 mm"), (0.3, False, "0.3 mm"), (19.05, False, "19 mm"),
])
def test_a_thin_wall_is_said_in_a_unit_that_doesnt_round_it_away(mm, inches, said):
    """#100 item 5: a 0.3 mm wall read "0 in". A small length the chat says beside its mm keeps that rule
    (``_small_len``); a wall itself is said in mm, whatever the design's units (#139 review)."""
    assert answers._small_len(mm, inches) == said
    assert answers._wall(mm, inches) == answers._wall(mm, False) and answers._wall(mm).endswith(" mm")


def test_the_finer_run_s_time_is_from_its_own_time_per_voxel():
    """#100 item 10: twice as fine is 8 times the voxels, each slower as the grid grows (time per voxel went as about
    the cube root of the voxel count, measured on the tube and the box stool): 16 times the FEA's time."""
    assert load_study.finer_minutes(10_000, 2.0, 1.0, 60, 0) == 16
    assert load_study.finer_minutes(10_000, 2.0, 1.0, 60, 120) == 18     # and the setup, as it was
    assert load_study.finer_minutes(10_000, 2.0, 2.0, 1, 0) == 1         # never "about 0 min"


@pytest.mark.parametrize("mm", [0.09, 0.0, -1.0, 50.01, 1e9])
def test_the_api_refuses_a_voxel_size_outside_0_1_to_50_mm(tmp_path, monkeypatch, mm):
    """#100 item 9: the bound held, but no test pinned it (a mutant widening it to 0 survived)."""
    pytest.importorskip("whittle")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = _store(tmp_path, NO_LOADS)              # so a size let through fails here, not hours into a run
    c = TestClient(create_app())
    got = c.post(f"/api/designs/{store.design.slug}/load-study", json={"part": "tube", "spacing_mm": mm})
    if got.status_code == 200:
        _finish(c, got.json()["job_id"])
    assert got.status_code == 422, got.text


def _finish(c, job_id):
    end = time.time() + 60
    while c.get(f"/api/jobs/{job_id}").json()["status"] not in ("done", "error"):
        assert time.time() < end
        time.sleep(0.05)


@pytest.mark.parametrize("mm", [0.1, 50.0])
def test_and_takes_one_at_its_ends(tmp_path, monkeypatch, mm):
    pytest.importorskip("whittle")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = _store(tmp_path, NO_LOADS)
    c = TestClient(create_app())
    got = c.post(f"/api/designs/{store.design.slug}/load-study", json={"part": "tube", "spacing_mm": mm})
    assert got.status_code == 200, got.text
    _finish(c, got.json()["job_id"])


def test_four_across_counted_with_a_hair_of_rounding_is_four():
    """A default run is sized at exactly RESOLVE_MIN across, which floats to 3.9999; without the 0.1% allowance it
    read "not resolved" on a run that is (#100, a surviving mutant)."""
    run, case = {"thinnest_mm": 4.0, "spacing_mm": 1.0, "across": 3.9999}, {"governs": "fea"}
    assert not load_study.unresolved(run, case)
    assert load_study.unresolved({**run, "across": 3.99}, case)            # but 3.99 is short of four
    assert not load_study.unresolved({**run, "across": 3.0}, {"governs": "plate"})   # and only the FEA's verdict


#: A tube big enough that the default voxel budget can't put four voxels across its 4 mm wall (1.25 mm voxels), and
#: the finer run's budget, 8x, can (0.625 mm): nothing patched but the part's size.
BIG = TUBE.replace('PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0}', 'PARAMS = {"r": 60.0, "h": 200.0, "wall": 4.0}') \
    .replace('"lo": (-32, -32, p["h"] - 2), "hi": (32, 32, p["h"])', '"lo": (-62, -62, p["h"] - 2), "hi": (62, 62, p["h"])')


def test_where_the_default_budget_binds_the_finer_run_is_offered_within_eight_times_it(tmp_path):
    """#100, a surviving mutant: FINER_BUDGET = 1 (the finer run in the default's own budget) went unnoticed, because
    the tests reached a coarse run by patching VOXELS_THROUGH. Here the budget itself binds."""
    pytest.importorskip("whittle")
    assert BIG != TUBE
    store = _store(tmp_path, BIG)
    rec = load_study.study(store, "tube")
    assert rec["spacing_mm"] == pytest.approx(1.25, abs=0.02) and not rec["resolved"]
    assert rec["finer"]["spacing_mm"] == pytest.approx(rec["thinnest_mm"] / 4, abs=0.011)
    assert rec["finer"]["spacing_mm"] >= load_study.finest(rec["voxels"] * 1.25 ** 3, 200, load_study.FINER_BUDGET) - 0.05
    assert "too_thin" not in rec


def test_a_run_that_didnt_connect_gives_no_time_for_the_finer_one(tmp_path, monkeypatch):
    """#100 review: on the bar stool copy, finer_minutes said "about 1 min" for a run that took 39: its default run's
    voxels didn't connect the load to a support, so its FEA stopped at once. Such a run's time says nothing."""
    from types import SimpleNamespace

    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 1)

    def unjoined(ctx, i, min_safety, solid=None):
        load = ctx["loads"][i]
        return ({"name": load["name"], "lb": load["lb"], "factor": load["factor"], "holds": False, "safety": 0.0,
                 "governs": "fea", "fea": {"supported": False}, "plate": None},
                SimpleNamespace(supported=False))

    monkeypatch.setattr(load_study, "check_load", unjoined)
    rec = load_study.study(_store(tmp_path), "tube")
    assert rec["finer"]["spacing_mm"] and rec["finer"]["minutes"] is None
    assert any(n.endswith("how long it takes can't be told from this run, whose voxels didn't connect the load to "
                          "a support.") for n in rec["notes"]), rec["notes"]


def test_an_asked_for_spacing_below_the_finest_is_clamped_before_anything_is_voxelized(tmp_path, monkeypatch):
    """#100 review: the clamp's mutant only failed by running away (SIGKILL). Here whittle's LoadStudy is a stub that
    records the spacing it's given and stops, so removing the clamp fails on an assert."""
    pytest.importorskip("whittle")
    import whittle

    got = {}

    class Stop(Exception):
        pass

    class Recorded:
        def __init__(self, mesh, material=None, spacing=None):
            got["spacing"] = spacing
            raise Stop()

    monkeypatch.setattr(whittle, "LoadStudy", Recorded)
    store = _store(tmp_path)
    with pytest.raises(Stop):
        load_study.prepare(store, "tube", spacing=0.1)
    mesh = store.part_geometry("tube").require_mesh()
    least = load_study.finest(float(abs(mesh.volume)), float(max(mesh.extents)), load_study.FINER_BUDGET)
    assert got["spacing"] == pytest.approx(least) and least > 0.1
