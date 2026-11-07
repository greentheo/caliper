"""CALI-106 (#101; rule 6) — a carve or lightening step on voxels too coarse to see the wall is no "holds".

#100 stopped a strength ✓ resting on an FEA too coarse to see the wall it checks, for the load study. Carve and
lighten run the same FEA at the same default voxels, and their steps still read "holds 2.2x" on a printed wall one
voxel across. Now they record whether their voxels see the walls (``load_study.resolution``), a step that holds on a
run that doesn't reads "not resolved" (a fail stays a fail) everywhere it's shown, and where no run a study may make
can see them the carve isn't run: "Its walls are too thin for the voxel check at this size…"."""

import pytest

from caliper import carve, chat, design_api, load_study, studies, verdicts
from caliper.design import DesignStore

from .test_resolved import TUBE

pytest.importorskip("cadquery")


#: The tube with 12 mm walls: four voxels across them at 3 mm voxels, so a resolving carve stays quick.
THICK = TUBE.replace('"wall": 4.0', '"wall": 12.0')


def _carve(tmp_path, monkeypatch, through, name, src=TUBE):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    store = DesignStore.create("a printed tube", base=str(tmp_path / name))
    store.write_part("tube", src, intent="a printed tube")
    return store, carve.study(store, "tube", stations=2, remove_up_to=0.4)


def test_a_carve_on_coarse_voxels_reads_not_resolved_at_every_step_that_holds(tmp_path, monkeypatch):
    store, rec = _carve(tmp_path, monkeypatch, 1, "coarse")
    assert rec["resolved"] is False and rec["finer"] and rec["across"] < load_study.RESOLVE_MIN
    held = [x for x in rec["stations"] if x["holds"]]
    assert held, rec["stations"]
    for x in rec["stations"]:
        v = verdicts.carve_step(x, None, rec)
        assert v["kind"] == ("unresolved" if x["holds"] else "fails") and not v["counts_as_pass"], (x, v)
    # the page's verdict, the Studies row and the chat's reply say it
    shown = design_api.design_state(store)["carve_runs"][0]
    assert all(st["verdict"]["kind"] == "unresolved" for st in shown["stations"] if st["holds"])
    text, ok = studies._headline("carve", rec)
    assert ok is not True and "too coarse to see its walls" in text, text
    monkeypatch.setattr(carve, "study", lambda *a, **k: rec)
    got = chat.carve_part(store, "tube")
    if rec["best"] is not None and next(x for x in rec["stations"] if x["index"] == rec["best"])["saved_g"]:
        assert not got.ok and "too coarse to see its walls" in got.reply and "The lightest that holds" not in got.reply


def test_at_resolving_voxels_the_same_carve_reads_as_its_safety_says(tmp_path, monkeypatch):
    store, rec = _carve(tmp_path, monkeypatch, 4, "fine", THICK)
    assert rec["resolved"] is True
    for x in rec["stations"]:
        assert verdicts.carve_step(x, None, rec)["kind"] == ("holds" if x["holds"] else "fails")


def test_resolution_says_whether_a_finer_run_could_see_the_walls():
    """The bar stool v7 copy's own numbers: a 0.25 mm wall at 4.6 mm voxels, and no run fine enough: too thin."""
    stool = load_study.resolution({"thinnest": 0.25, "spacing": 4.6, "finest": 1.0})
    assert stool == {"thinnest_mm": 0.25, "across": 0.054, "resolved": False, "too_thin": True}
    assert load_study.resolution({"thinnest": 4.0, "spacing": 2.0, "finest": 0.5})["finer"] is True
    assert load_study.resolution({"thinnest": 4.0, "spacing": 1.0, "finest": 0.5})["resolved"] is True


def test_where_no_run_can_see_the_walls_it_isn_t_carved(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 1)
    monkeypatch.setattr(load_study, "resolution", lambda ctx: {"resolved": False, "too_thin": True})
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    with pytest.raises(ValueError, match="Its walls are too thin for the voxel check at this size, so it can't be "
                                         "carved by strength"):
        carve.study(store, "tube", stations=3)
    assert carve.list_runs(store) == []                                       # nothing ran


def test_a_lightening_step_on_coarse_voxels_isn_t_the_lightest_that_holds():
    coarse = {"resolved": False, "finer": True}
    real = {"index": 2, "holds": True, "safety": 2.8, "saved_lb": 1.0}
    assert verdicts.lighten_step(real, run=coarse)["kind"] == "unresolved"
    assert verdicts.lighten_step(real, run={**coarse, "too_thin": True})["kind"] == "unchecked"
    assert verdicts.lighten_step({**real, "holds": False}, run=coarse)["kind"] == "fails"     # a fail stays one
    text, ok = studies._headline("lighten", {"stations": [real], **coarse})
    assert text.startswith("not resolved") and ok is None


def test_the_page_disables_carve_and_lighten_with_the_reason():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "id=\"carveGo\" ${S.carveJob[p.id] || carveBlocked(p) ? 'disabled' : ''}" in src
    assert "can\\'t be carved by strength" in src and "can\\'t be lightened by strength" in src


# --- #136 review: where the thin walls are, what to change, and the part's own rule ------------------------------

def _spool(tmp_path, units="in"):
    from caliper.spec import Assertion, Spec

    from .test_resolved import SPOOL

    store = DesignStore.create("a printed spool", base=str(tmp_path / "designs"))
    store.design.display_units = units
    store.save()
    rule = Assertion(id="shell_wall_thickness", expr="min_wall >= 3.0 - 0.15")       # the bar stool's locked rule
    store.write_part("spool", SPOOL, intent="a printed spool",
                     spec=Spec(part="spool", intent="a printed spool", assertions=[rule]))
    return store


def test_the_thinnest_wall_is_found_where_it_is():
    """The reviewer's spool: a 0.6 mm neck between z 19 and 31 mm. Its thinnest wall is found there, not just how
    thin it is."""
    from caliper import measure, sandbox

    from .test_resolved import SPOOL

    g = sandbox.run_script(SPOOL, timeout=120).geometry
    mm, at = measure.thinnest_wall(g)
    assert mm == pytest.approx(0.6, abs=0.05) and 19 <= at[2] <= 31
    assert measure.min_wall_thickness(g) == mm


def test_the_too_thin_line_says_where_what_to_change_and_the_rule(tmp_path):
    store = _spool(tmp_path, units="mm")
    ctx = load_study.prepare(store, "spool")
    assert 19 <= ctx["thinnest_where"]["at"][2] <= 31
    said = ctx["thin_said"]
    import re

    assert re.match(r"its 0\.(59|6) mm walls around z 2\d mm are too thin for the strength check to see", said), said
    assert said.endswith("Your rule shell_wall_thickness says at least 2.85 mm: thicken them to that first.")
    assert "nozzle" not in said                                    # 0.6 mm prints on a 0.4 mm nozzle
    # where no run a study may make can see them, resolution carries the words
    seen = load_study.resolution({**ctx, "spacing": 4.6, "finest": 1.0})
    assert seen["too_thin"] and seen["said"] == said and seen["where"] == ctx["thinnest_where"]
    # the bar stool's webs, in its own units: one number, where, the nozzle, its rule
    assert load_study.thin_words(_spool(tmp_path / "in"), "spool", 0.25, {"at": [0, 165, 410]}, 2.3, True) == (
        "its 0.25 mm walls around z 16.1 in are too thin for the strength check to see (at this size it sees walls "
        "from 3/8 in on) and for a 0.4 mm nozzle to print. Your rule shell_wall_thickness says at least 2.85 mm: "
        "thicken them to that first.")


def test_a_refused_carve_says_where_and_what_to_change(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 1)
    said = "its 0.25 mm walls around z 16.1 in are too thin for the strength check to see. Thicken them first."
    monkeypatch.setattr(load_study, "resolution", lambda ctx: {"resolved": False, "too_thin": True, "said": said})
    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    with pytest.raises(ValueError) as e:
        carve.study(store, "tube", stations=3)
    assert str(e.value) == "Can't carve it by strength: " + said
    assert carve.list_runs(store) == []


def test_one_wall_number_on_the_card_and_the_page():
    """#137 item 2: the card said 0.2 mm and the page 0.3 mm for the same 0.25 mm wall."""
    from caliper import answers

    from .test_carve_click import _page, _run

    assert answers._wall(0.25, True) == answers._wall(0.25, False) == "0.25 mm"
    assert answers._wall(0.6, False) == "0.6 mm" and answers._wall(4.0, False) == "4 mm"
    out = _run(_page(["wallLen"], consts=["gcd"], extra="const IN = 25.4; function inches() { return true; }\n"
                                                         "out = [wallLen(0.25), wallLen(0.6), wallLen(4)];"))
    assert out == ["0.25 mm", "1/32″", "5/32″"]                   # as answers._wall says them in inches
    assert [answers._wall(mm, True) for mm in (0.25, 0.6, 4)] == ["0.25 mm", "1/32 in", "5/32 in"]


def test_the_page_says_the_check_s_words_on_a_blocked_carve():
    from .test_carve_click import _page, _run

    said = "its 0.25 mm walls around z 16.1 in are too thin for the strength check to see. Thicken them first."
    check = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "too_thin": True, "thin_said": said, "cases": []}
    out = _run(_page(["carveBlocked", "defaultCheck"], extra=(
        f"function loadRuns() {{ return [{__import__('json').dumps(check)}]; }}\n"
        "out = [carveBlocked({id: 'stool', version: 7}), carveBlocked({id: 'stool', version: 6})];")))
    assert out == ["Can't carve it by strength: " + said, ""]
