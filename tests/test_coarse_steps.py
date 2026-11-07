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

from .test_resolved import SPOOL as SPOOL_PLAIN


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

    assert re.match(r"its thinnest walls, 0\.(59|6) mm around z 2\d mm, are thinner than your rule", said), said
    assert said.endswith(" mm, are thinner than your rule shell_wall_thickness (at least 2.85 mm): thicken them to "
                         "that. For a strength carve, walls must be at least " + f"{4 * ctx['finest']:.1f}" + " mm at "
                         "this size, so check it by hand or with a test piece instead."), said
    assert "nozzle" not in said                                    # 0.6 mm prints on a 0.4 mm nozzle
    # where no run a study may make can see them, resolution carries the words
    seen = load_study.resolution({**ctx, "spacing": 4.6, "finest": 1.0})
    assert seen["too_thin"] and seen["said"] == said and seen["where"] == ctx["thinnest_where"]
    # the bar stool's webs, in its own units: one number, where, the nozzle, its rule
    assert load_study.thin_words(_spool(tmp_path / "in"), "spool", 0.25, {"at": [0, 165, 410]}, 2.3, True) == (
        "its thinnest walls, 0.25 mm around z 16.1 in, are too thin for a 0.4 mm nozzle to print and for your rule "
        "shell_wall_thickness (at least 2.85 mm): thicken them to that. For a strength carve, walls must be at least "
        "9.2 mm at this size, so check it by hand or with a test piece instead.")
    # with no rule and nothing to print, only the strength check's limit, in mm (#136 review: not "3/8 in")
    plain = DesignStore.create("a wood thing", base=str(tmp_path / "plain"))
    plain.write_part("spool", SPOOL_PLAIN, intent="a spool")
    assert load_study.thin_words(plain, "spool", 3.0, {"piece": "seat top"}, 2.3, False) == (
        "its thinnest walls, 3 mm in the seat top, are too thin for the strength check to see: at this size it sees walls from "
        "9.2 mm on, so check it by hand or with a test piece instead.")


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
    # walls in mm everywhere, whatever the design's units (#139 review)
    out = _run(_page(["wallLen"], consts=["gcd"], extra="const IN = 25.4; function inches() { return true; }\n"
                                                         "out = [wallLen(0.25), wallLen(0.6), wallLen(4)];"))
    assert out == ["0.25 mm", "0.6 mm", "4 mm"]                   # as answers._wall says them: mm (#139 review)
    assert [answers._wall(mm, True) for mm in (0.25, 0.6, 4)] == ["0.25 mm", "0.6 mm", "4 mm"]


def test_the_page_says_the_check_s_words_on_a_blocked_carve():
    from .test_carve_click import _page, _run

    said = "its 0.25 mm walls around z 16.1 in are too thin for the strength check to see. Thicken them first."
    check = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "too_thin": True, "thin_said": said, "cases": []}
    out = _run(_page(["carveBlocked", "defaultCheck"], extra=(
        f"function loadRuns() {{ return [{__import__('json').dumps(check)}]; }}\n"
        "out = [carveBlocked({id: 'stool', version: 7}), carveBlocked({id: 'stool', version: 6})];")))
    assert out == ["Can't carve it by strength: " + said, ""]


# --- #136 review round 2: the page keeps a blocked carve off, and a coarse lightening isn't a ✗ -------------------

def test_a_coarse_fail_stays_a_fail():
    coarse = {"resolved": False, "too_thin": True}
    step = {"index": 1, "holds": False, "safety": 0.4, "whole": 0.4, "whole_holds": False, "saved_g": 100}
    assert verdicts.carve_step(step, run=coarse)["kind"] == "fails"
    # the whole part holding there: only the printed part's own fail keeps it a fail (the review's mutant hid behind
    # whole_holds: False)
    assert verdicts.carve_step({**step, "whole": 2.5, "whole_holds": True}, run=coarse)["kind"] == "fails"
    assert verdicts.lighten_step({"index": 1, "holds": False, "safety": 0.4, "saved_lb": 1}, run=coarse)["kind"] == "fails"


def test_the_page_keeps_a_blocked_carve_off_after_a_job_ends():
    """paintCarve set ``disabled`` from the job alone, so after a cancel "Carve it again" was clickable on a part its
    check blocks."""
    from .test_carve_click import _page, _run

    out = _run(_page(["paintCarve"], extra=(
        "const els = {carveGo: {disabled: false}}; function $(id) { return els[id]; }\n"
        "const S = {scope: 'a', carveJob: {}, design: {parts: [{id: 'a'}]}};\n"
        "let blocked = 'too thin'; function carveBlocked() { return blocked; }\n"
        "paintCarve('a'); const off = els.carveGo.disabled; blocked = ''; paintCarve('a');\n"
        "out = [off, els.carveGo.disabled];")))
    assert out == [True, False]


def test_a_refusal_reads_without_the_exception_s_name():
    from .test_carve_click import _page, _run

    out = _run(_page([], consts=["plainly"], extra=(
        "out = [plainly(\"ValueError: Can't carve it by strength: its walls…\"), plainly('the part is busy')];")))
    assert out == ["Can't carve it by strength: its walls…", "the part is busy"]


def test_a_refused_carve_on_the_page_reads_without_the_exception_s_name():
    """The page's own refusal (runCarve's catch) goes through plainly(), not e.message as it came."""
    from .test_carve_click import _page, _run

    out = _run(_page(["runCarve"], consts=["esc", "plainly"], extra=(
        "const els = {carveProgress: {innerHTML: ''}}; function $(id) { return els[id]; }\n"
        "const S = {slug: 'd', carveJob: {}}; function paintCarve() {} function loadRuns() { return []; }\n"
        "async function refresh() {} async function followCarve() {}\n"
        "async function api() { throw new Error(\"ValueError: Can't carve it by strength: its walls…\"); }\n"
        "await runCarve({id: 'a'}); out = els.carveProgress.innerHTML;")))
    assert "⚠ Can&#39;t carve it" in out or "⚠ Can't carve it by strength: its walls…" in out
    assert "ValueError" not in out


def test_lighten_on_a_coarse_run_says_not_resolved_not_nothing_holds():
    """The page said "Nothing lighter still holds" (a false ✗) where Studies said "not resolved"."""
    import json as _json
    import os

    from .test_carve_click import _page, _run

    def view(kind):
        run = {"id": "r", "part": "a", "notes": [], "stations": [
            {"index": 0, "saved_lb": 0, "safety": 3.0, "verdict": {"kind": kind, "counts_as_pass": False}},
            {"index": 1, "saved_lb": 1.0, "safety": 2.5, "verdict": {"kind": kind, "counts_as_pass": False}}]}
        return _run(_page(["lightenView", "lightenBlocked"], consts=["esc", "holdsHere"], extra=(
            f"const S = {{design: {{lighten_runs: [{_json.dumps(run)}]}}, station: null}};\n"
            "function lightenRuns() { return S.design.lighten_runs; } function defaultCheck() { return null; }\n"
            "function sx(v) { return v + 'x'; } function pct(v) { return v; } function lbs(v) { return v + ' lb'; }\n"
            "function notTrusted() { return ''; } function verdictTone() { return 'warn'; }\n"
            "out = lightenView({id: 'a'});")))

    assert "Not resolved yet: the check was too coarse to see its walls" in view("unresolved")
    assert "Not checked: its walls are too thin for the voxels" in view("unchecked")
    assert "Nothing lighter still holds" not in view("unresolved")
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "id=\"lightGo\" ${lightenBlocked(p) ? 'disabled' : ''}" in src                 # #137: one reason, both
