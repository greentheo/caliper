"""CALI-100 (#92, the server side) — Make it better on *Will it work?*, and Carve on the Studies page.

Theo, on the bar stool: "Where is the card for reducing mass using stress loading and 3d printable shapes?" Each part's
*Will it work?* now ends with what would make it better: only what ``load_study.blocked`` allows (#144), the cheapest
real improvement first, a number quoted only from a settled verdict. Runs are written as the studies write them; no
FEA, no Claude."""

import json
import os

import pytest

from caliper import answers, better, carve, design_api, lighten, load_study, studies
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL
from .test_resolved import TUBE

pytest.importorskip("cadquery")

NEED = 2


def _store(tmp_path, src, pid):
    store = DesignStore.create(f"a {pid}", base=str(tmp_path / "designs"))
    store.write_part(pid, src, intent=f"a {pid}")
    return store


def _save(folder, rec):
    os.makedirs(os.path.join(folder, rec["id"]), exist_ok=True)
    with open(os.path.join(folder, rec["id"], "run.json"), "w") as f:
        json.dump(rec, f)


def _check(store, pid, safety, *, plate=None, thinnest=10.0, spacing=2.0, rid="20261107-000000-check", **extra):
    """A strength run on this version: the FEA governs (resolved: 5 voxels across its walls), or the plate check."""
    case = {"name": "a foot", "lb": 40, "factor": 2.0, "safety": safety, "holds": safety >= NEED,
            "governs": "plate" if plate else "fea", "plate": plate,
            "fea": {"supported": True, "safety": safety if not plate else 50.0, "deflection_mm": 0.1}}
    _save(load_study.runs_dir(store), {"id": rid, "part": pid, "version": store.design.part(pid).version,
                                        "created": 1.0, "seconds": 60.0, "min_safety": NEED, "safety": safety,
                                        "holds": safety >= NEED, "spacing_mm": spacing, "thinnest_mm": thinnest,
                                        "across": thinnest / spacing, "cases": [case], **extra})


def _carved(store, pid, *, whole=3.0, safety=2.6, saved=644, seen=True, material=None):
    _save(carve.runs_dir(store), {
        "id": "20261107-000100-carve", "part": pid, "kind": "carve", "version": store.design.part(pid).version, **({"material": material} if material else {}),
        "created": 2.0, "status": "done", "min_safety": NEED, "spacing_mm": 2.0, "thinnest_mm": 10.0, "across": 5.0,
        "share": "printed", "best": 1,
        "stations": [{"index": 0, "removed": 0.0, "safety": 3.0, "holds": True, "whole": 3.0, "whole_holds": True,
                      "saved_g": 0},
                     {"index": 1, "removed": 0.61, "safety": safety, "holds": safety >= NEED, "whole": whole,
                      "whole_holds": whole >= NEED, "saved_g": saved, "seen": seen}]})


def _offers(store, pid):
    return better.offers(store, design_api.design_state(store), pid)


def _plate(t=19.05, rows=((12.7, "1/2 in", 1.4), (15.875, "5/8 in", 2.3), (19.05, "3/4 in", 3.1),
                         (25.4, "1 in", 5.2))):
    return {"done": True, "as": "plate", "piece": "top", "thickness_mm": t, "safety": 6.0, "safety_across": 3.1,
            "by_thickness": [{"thickness_mm": tt, "label": lab, "safety": s * 2, "safety_across": s}
                             for tt, lab, s in rows]}


# --- the carve, on a printed part --------------------------------------------------------------------------------------

def test_a_printed_part_that_holds_is_invited_to_carve_with_what_it_takes(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    (first,) = _offers(store, "tube")                              # no check yet: only that (#157 review)
    assert first["text"] == "Check it holds first: what would make it better comes from that." and first["action"] == "load"
    assert first["button"] == "Check it holds" and first["part"] == "tube"
    _check(store, "tube", 3.0)
    (line,) = _offers(store, "tube")
    assert line["text"] == ("Carve the tube where it isn't working, to use less filament: it takes at least about "
                            "45 min at this size.")                              # 60 s × 45
    assert line["action"] == "carve" and line["better"] and line["status"] == "info"
    assert "study" not in line                                         # not a strength verdict, to any reader of those


def test_after_a_carve_it_gives_the_result_to_use(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _carved(store, "tube")
    (line,) = _offers(store, "tube")
    assert line["text"] == ("Carve the tube where it isn't working: 61% of the printed part carved away, 644 g less "
                            "filament, still about 2.6 times over by the carve's own check. No step whose walls the re-check can see clears what it must hold by half again (a rule of thumb), so this one may not hold once it's re-checked. That takes it from about 3 to 2.6 times over. Using it re-checks it, "
                            "and that's the number to go by.")
    assert line["action"] == "carve_use" and line["station"] == 1


@pytest.mark.parametrize("kw,word", [({"saved": 10, "material": "PETG (printed)"}, "22¢"), ({"seen": False}, "couldn't settle")])
def test_with_nothing_worth_clicking_the_card_says_why_and_has_no_button(tmp_path, kw, word):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _carved(store, "tube", **kw)
    (line,) = _offers(store, "tube")
    assert word in line["text"] and line["button"] == "" and line["action"] == "" and "step to use" not in line["text"]


def test_a_carve_whose_whole_part_doesn_t_hold_quotes_nothing(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _carved(store, "tube", whole=1.4)                                   # the printed part holds; the whole doesn't
    assert _offers(store, "tube") == []


def test_an_unsettled_check_quotes_no_number(tmp_path):
    """Too coarse to see its walls (1 voxel across): blocked doesn't stop the carve, but no result is quoted."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0, thinnest=2.0, spacing=2.0)
    _carved(store, "tube")
    assert not [ln for ln in _offers(store, "tube") if "times over" in ln["text"]]


def test_a_part_that_fails_is_offered_what_would_make_it_hold_never_lighter(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 1.2)
    _carved(store, "tube")
    assert _offers(store, "tube") == []                                 # no thicker sheet for a printed tube
    stool = _store(tmp_path / "s", BOX_STOOL, "stool")
    _check(stool, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    (line,) = _offers(stool, "stool")
    assert line["text"] == ("Make the top from 5/8 in instead of 1/2 in: that panel holds then, about 2.3 times over "
                            "by the plate check.")
    assert line["action"] == "use_t" and line["say"] == "Make the top from 5/8 in instead of 1/2 in"


def test_a_thicker_sheet_is_offered_only_where_it_would_make_it_hold(tmp_path, monkeypatch):
    """Not for a load the FEA governs (a thicker sheet may not fix it), nor on a check that left the front edge out."""
    from caliper import consistency

    stool = _store(tmp_path / "a", BOX_STOOL, "stool")
    _check(stool, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4})
    assert len(_offers(stool, "stool")) == 1
    monkeypatch.setattr(consistency, "bare_edge", lambda store, pid: "no foot at its front edge")
    assert _offers(stool, "stool") == []
    monkeypatch.undo()
    fea = _store(tmp_path / "b", BOX_STOOL, "stool")
    _check(fea, "stool", 1.4, plate=None)                                # fails, and the FEA governs
    assert _offers(fea, "stool") == []


def test_every_load_on_a_panel_has_to_hold_at_the_offered_sheet(tmp_path):
    """The thinnest sheet that holds the worst load on the panel, not just the first load listed."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1, plate=_plate())
    run = load_study.default_check(store, "stool")
    heavy = json.loads(json.dumps(run["cases"][0]))
    heavy["name"] = "a heavier foot"
    for b in heavy["plate"]["by_thickness"]:
        b["safety_across"] = round(b["safety_across"] * 0.8, 2)         # 5/8 in: 1.84, under the 2 it needs
    run["cases"].append(heavy)
    _save(load_study.runs_dir(store), run)
    assert [ln for ln in _offers(store, "stool") if ln["action"] == "use_t"] == []      # 3/4 in is the thinnest


def test_ten_or_more_reads_more_than_10_never_a_bigger_number(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 14.0)
    _carved(store, "tube", whole=14.0, safety=12.3)
    (line,) = _offers(store, "tube")
    assert "still more than 10 times over by the carve's own check." in line["text"]


# --- the cheapest first: a thinner sheet, then a lightening ------------------------------------------------------------

def test_the_cheapest_real_improvement_comes_first(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1, plate=_plate())
    got = _offers(store, "stool")
    assert [ln["action"] for ln in got] == ["use_t", "lighten"]
    assert got[0]["text"] == "Make the top from 5/8 in instead of 3/4 in: still about 2.3 times over by the plate check."
    assert got[1]["text"] == "Lighten it with holes where the wood isn't working: it takes a few minutes."
    _save(lighten.runs_dir(store), {"id": "20261107-000200-lighten", "part": "stool",
                                    "version": store.design.part("stool").version, "created": 3.0,
                                    "spacing_mm": 2.0, "thinnest_mm": 19.05, "across": 9.5,
                                    "stations": [{"index": 0, "saved_lb": 0, "safety": 3.1, "holds": True},
                                                 {"index": 1, "saved_lb": 1.8, "safety": 2.4, "holds": True},
                                                 {"index": 2, "saved_lb": 2.5, "safety": 1.6, "holds": False}]})
    got = _offers(store, "stool")
    assert [ln["action"] for ln in got] == ["use_t", "lighten_use"]
    assert got[1]["text"] == ("Lighten it with holes where the wood isn't working: 1.8 lb lighter, still about 2.4 "
                              "times over by the lightening's own check. No step whose walls the re-check can see clears what it must hold by half again (a rule of thumb), so this one may not hold once it's re-checked. That takes it from about 3.1 to 2.4 times over. Using it re-checks it, and that's the number to go by.")


def test_the_card_and_a_one_part_design_s_card_carry_them(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    state = design_api.design_state(store)
    work = next(c for c in answers.part(store, state, "tube") if c["key"] == "work")
    assert work["lines"][-1]["better"] and work["lines"][-1]["action"] == "carve"
    design = next(c for c in answers.design(store, state) if c["key"] == "work")
    assert [ln["text"] for ln in design["lines"] if ln.get("better")] == [work["lines"][-1]["text"]]


# --- the Studies page: Carve listed, and each says why not -------------------------------------------------------------

def test_studies_lists_carve_for_a_printed_part_and_lighten_for_a_sheet_one(tmp_path):
    tube = _store(tmp_path / "t", TUBE, "tube")
    _check(tube, "tube", 3.0)
    menu = {m["kind"]: m for m in studies.menu(design_api.design_state(tube)["parts"][0])}
    assert menu["carve"]["ready"] and not menu["lighten"]["ready"]
    assert menu["lighten"]["why"] == "it has no sheet pieces: printed parts get carved instead"
    stool = _store(tmp_path / "s", BOX_STOOL, "stool")
    _check(stool, "stool", 3.1, plate=_plate())
    menu = {m["kind"]: m for m in studies.menu(design_api.design_state(stool)["parts"][0])}
    assert menu["lighten"]["ready"] and not menu["carve"]["ready"]
    assert menu["carve"]["why"] == "it has no printed piece: sheet walls are lightened with holes"
    # what the Carve button refuses, Studies does too (#144)
    fails = _store(tmp_path / "f", TUBE, "tube")
    _check(fails, "tube", 1.2)
    menu = {m["kind"]: m for m in studies.menu(design_api.design_state(fails)["parts"][0])}
    assert not menu["carve"]["ready"] and menu["carve"]["why"].startswith("it already fails")


# --- the page's shape, per the mockup Theo approved -------------------------------------------------------------------

THIN = ("its thinnest walls, 0.25 mm in the cone skirt, are too thin for the strength check to see: at this size it sees "
        "walls from 9.2 mm on, so check it by hand or with a test piece instead.")


@pytest.mark.parametrize("extra", [{"thin_said": THIN}, {"thin_said": "older words", "sees_mm": 9.2}])
def test_a_thin_named_piece_gets_how_thick_rounded_up_and_says_a_finer_check_follows(tmp_path, extra):
    """#159 review: a real 9.2 mm wall came back still too thin (the true figure was 9.207), and the next click was no
    verdict either: it never says the check will settle it."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0, thinnest=0.25, spacing=2.3, too_thin=True, thinnest_where={"piece": "cone skirt"}, **extra)
    wall, carve_it = _offers(store, "tube")
    assert wall["lead"] == "Make the cone skirt 9.3 mm thick so a finer check can see it"
    assert wall["cost"].startswith("It takes more filament, and then a finer check: ")
    assert "trust" not in wall["cost"]
    assert wall["button"] == "Try it" and wall["action"] == "use_t" and not wall.get("disabled")
    assert wall["say"] == "Make the cone skirt at least 9.3 mm thick so the strength check can see it"
    assert carve_it["disabled"] and carve_it["action"] == "carve" and carve_it["lead"] == "Carve the tube where it isn't working"
    assert carve_it["cost"] == "At least about 45 min at this size. It waits for a check it can trust."


#: as a real check records it: a sliver at a point, not a piece (#159 review: the fixture's {"piece": …} hid this)
REAL_WHERE = {"at": [12.3, -4.5, 409.0]}


def test_a_thin_spot_that_isn_t_a_piece_says_where_and_promises_nothing(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0, thinnest=0.25, spacing=2.3, too_thin=True, thinnest_where=REAL_WHERE, sees_mm=9.2)
    spot, carve_it = _offers(store, "tube")
    assert spot["lead"] == "The thinnest spot is 0.25 mm, around z 409 mm: thicken it or change the openings"
    assert spot["cost"] == ("It takes more filament. If the numbers don't move it, it's how the openings are cut: that's a change to "
                            "ask for in the chat. A finer check can see walls from 9.3 mm: at least about 8 min.")
    assert "around z 409 mm" in spot["say"] and "9.3 mm" in spot["say"] and spot["action"] == "use_t"
    assert "thicken it, or if it's beside an opening, change how the opening is cut" in spot["say"]    # a plain wall has no openings
    assert carve_it["disabled"]


def test_theo_s_stool_a_fail_too_coarse_to_judge_reaches_the_screen(tmp_path):
    """0.53x on a run too coarse to see its walls: before this, already_fails returned nothing at all."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 0.53, thinnest=0.25, spacing=4.6, too_thin=True, thinnest_where=REAL_WHERE, sees_mm=9.2)
    spot, carve_it = _offers(store, "tube")
    assert spot["lead"].startswith("The thinnest spot is 0.25 mm") and carve_it["disabled"]
    assert carve_it["cost"].endswith("make it hold first, then carve.") and "It waits" not in carve_it["cost"]        # the button's own words (#185)


def test_a_fail_on_a_settled_run_stays_as_it_was(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 0.53)
    assert _offers(store, "tube") == []


def test_every_offer_has_its_lead_cost_button_and_part(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _carved(store, "tube")
    (line,) = _offers(store, "tube")
    assert line["lead"] == "Carve the tube where it isn't working" and line["button"] == "Use it" and line["part"] == "tube"
    assert line["cost"] == ("61% of the printed part carved away, 644 g less filament, still about 2.6 times over by the "
                            "carve's own check. No step whose walls the re-check can see clears what it must hold by half again (a rule of thumb), so this one may not hold once it's re-checked. That takes it from about 3 to 2.6 times over. Using it re-checks it, and that's the number to go by.")
    assert line["text"] == f"{line['lead']}: {line['cost']}"                 # the same, as one sentence


def _page_of(extra):
    from .test_carve_click import _page, _run

    return _run(_page(["qlines", "betterLines", "useBetter"], consts=["esc"], extra=extra))


CARD = ("const trackedFor = () => null;\n"
        "const GOTO = {load: 'loadBox'};\n"
        "const c = {key: 'work', lines: [{text: 'Holds a foot.', status: 'ok', study: 'load'},\n"
        "  {better: true, status: 'info', lead: 'Make the top thinner', cost: 'Still about 2.3 times over.', button: 'Try it',\n"
        "   action: 'use_t', say: 'Make it thinner', part: 'p'},\n"
        "  {better: true, status: 'info', lead: 'Carve the cone', cost: 'It waits for a check it can trust.', button: 'Carve it',\n"
        "   action: 'carve', part: 'p', disabled: true}]};\n")


def test_the_card_draws_a_make_it_better_section_with_buttons():
    html = _page_of(CARD + "out = qlines(c);")
    assert html.count('class="qbetter-h">Make it better<') == 1 and html.count('class="qoffer"') == 2
    assert 'Make the top thinner.<span class="qoffer-c">Still about 2.3 times over.</span>' in html
    assert 'data-better="1" data-better-action="use_t" data-better-part="p" data-card="work">Try it</button>' in html
    assert 'data-better="2" data-better-action="carve" data-better-part="p" data-card="work" disabled>Carve it</button>' in html
    assert html.count('class="qline') == 1                                  # the offers aren't drawn as verdict lines too
    assert _page_of("const GOTO = {}; out = qlines({key: 'w', lines: [{text: 'a', status: 'ok'}]});").count("qbetter") == 0


@pytest.mark.parametrize("line,called", [
    ("{action: 'use_t', say: 'Make it thinner', part: 'p'}", ["send:Make it thinner:p"]),
    ("{action: 'carve', part: 'p'}", ["scope:p", "goto:loadBox", "carve:p"]),
    ("{action: 'lighten', part: 'p'}", ["scope:p", "goto:loadBox", "lighten:p"]),
    ("{action: 'carve_use', part: 'p', run: 'r1', station: 3}", ["scope:p", "goto:loadBox", "adopt:p:r1:3:carve"]),
    ("{action: 'lighten_use', part: 'p', run: 'r2', station: 1}", ["scope:p", "goto:loadBox", "adopt:p:r2:1:lighten"]),
    ("{action: 'load', part: 'p'}", ["scope:p", "goto:loadBox", "load:p"]),
    ("{action: 'carve', part: 'p', disabled: true}", []),
])
def test_each_button_goes_through_what_its_panel_already_does(line, called):
    got = _page_of(
        "const calls = []; const S = {claude: true, scope: null, design: {parts: [{id: 'p'}]}};\n"
        "async function refresh() {} function studyDone() { return false; } function tellOffer() {}\n"
        "function send(t, s) { calls.push(`send:${t}:${s}`); } function setScope(p) { S.scope = p; calls.push(`scope:${p}`); }\n"
        "function goTo(b) { calls.push(`goto:${b}`); } function runCarve(p) { calls.push(`carve:${p.id}`); }\n"
        "function runLighten(p) { calls.push(`lighten:${p.id}`); }\n"
        "function runLoad(p) { calls.push(`load:${p.id}`); }\n"
        "function adoptStation(p, r, i, k) { calls.push(`adopt:${p}:${r}:${i}:${k}`); }\n"
        f"await useBetter({line}); out = calls;")
    assert got == called


# --- #157 review -------------------------------------------------------------------------------------------------------

def test_before_a_check_the_only_line_is_check_it_first(tmp_path):
    """On Theo's stool (no check of v7) the card said "Lighten it with holes…", a dead end."""
    store = _store(tmp_path, BOX_STOOL, "stool")
    assert [ln["action"] for ln in _offers(store, "stool")] == ["load"]


def test_a_printed_part_is_never_offered_lighten(tmp_path):
    """Plywood on printed sides: the page has no Lighten panel for a printed part, and Studies says so."""
    from .test_mixed import MIXED

    store = _store(tmp_path, MIXED, "stool")
    _check(store, "stool", 3.0)
    assert not [ln for ln in _offers(store, "stool") if "lighten" in ln["action"]]
    menu = {m["kind"]: m for m in studies.menu(design_api.design_state(store)["parts"][0])}
    assert not menu["lighten"]["ready"] and menu["lighten"]["why"] == "printed parts get carved instead, not lightened with holes"


def _with_cases(store, pid, cases, safety):
    _check(store, pid, safety)
    run = load_study.default_check(store, pid)
    run["cases"] = cases
    _save(load_study.runs_dir(store), run)


def _case(name, safety, need=NEED, governs="plate", plate=None):
    return {"name": name, "lb": 40, "factor": 2.0, "safety": safety, "holds": safety is not None and safety >= need,
            "governs": governs, "plate": plate, "fea": {"supported": True, "safety": 50.0, "deflection_mm": 0.1}}


def _on(piece, t=12.7, rows=((12.7, "12 mm", 1.2), (18.0, "18 mm", 2.4))):
    return {**_plate(t=t, rows=rows), "piece": piece, "safety_across": rows[0][2]}


def test_only_the_panel_that_fails_is_offered_more_material(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _with_cases(store, "stool", [_case("on the top", 1.2, plate=_on("top")),
                                 _case("on the shelf", 2.5, plate=_on("shelf", rows=((12.7, "12 mm", 2.5), (18.0, "18 mm", 5.0))))], 1.2)
    (line,) = _offers(store, "stool")
    assert line["text"].startswith("Make the top from 18 mm instead of 12 mm: that panel holds then")


def test_nothing_is_offered_if_a_load_fails_that_the_plate_check_doesn_t_govern(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _with_cases(store, "stool", [_case("on the top", 1.2, plate=_on("top")), _case("the frame", 1.1, governs="fea")], 1.1)
    assert _offers(store, "stool") == []


def test_a_panel_with_a_load_the_fea_governs_is_left_out(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    both = _plate()
    _with_cases(store, "stool", [_case("a foot", 3.1, plate=both), _case("a shove", 3.5, governs="fea", plate=both)], 3.1)
    assert not [ln for ln in _offers(store, "stool") if ln["action"] == "use_t"]


def test_an_unknown_case_on_a_failing_panel_quotes_nothing(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _with_cases(store, "stool", [_case("on the top", 1.2, plate=_on("top")),
                                 _case("not reached", None, plate=_on("top"))], 1.2)
    assert _offers(store, "stool") == []


@pytest.mark.parametrize("minutes,words", [(1, "1 min"), (60, "60 min"), (80, "an hour"), (99, "an hour"), (120, "2.0 hours")])
def test_the_card_and_the_carve_button_say_the_same_time(tmp_path, minutes, words):
    from .test_carve_click import _page, _run

    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    run = load_study.default_check(store, "tube")
    run["seconds"] = minutes * 60 / better.CARVE_PER_CHECK
    _save(load_study.runs_dir(store), run)
    (line,) = _offers(store, "tube")
    p = design_api.design_state(store)["parts"][0]
    assert p["carve_takes"] == f"at least about {words} at this size" and p["carve_takes"] in line["text"]
    out = _run(_page(["carveTime", "carveBlocked"], ["minutesText"], (
        "const carveRuns = () => [];\n" f"out = carveTime({json.dumps({'id': 'tube', 'carve_takes': p['carve_takes']})});")))
    assert out == p["carve_takes"]


def test_the_time_goes_by_the_default_check_not_a_finer_one(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0, spacing=2.3, rid="20261107-000100-finer")
    run = load_study.default_check(store, "tube")
    _save(load_study.runs_dir(store), {**run, "seconds": 2350.0, "created": 9.0})
    _check(store, "tube", 3.0, spacing=4.6, rid="20261107-000000-default")
    default = next(r for r in load_study.list_runs(store, "tube") if r["id"].endswith("default"))
    _save(load_study.runs_dir(store), {**default, "seconds": 20.0})
    assert better.carve_takes(load_study.default_check(store, "tube")) == "at least about 15 min at this size"


# --- #159 review: the card follows the runs, one click one run, no SDK error -------------------------------------------
def _page(names: tuple, head: str, body: str) -> dict:
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(_JS).read()
    script = head + "\n".join(_fn(src, n) for n in names) + f"\n(async () => {{ const out = await (async () => {{ {body} }})();\nconsole.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


_JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def test_a_finished_carve_or_lighten_asks_the_cards_again():
    head = """const S = { slug: 'x', scope: 'p', shopKey: 0, design: { parts: [], carve_runs: [{ id: 'a', status: 'running' }], lighten_runs: [] } };\n"""
    got = _page(("answersKey",), head, """const a = answersKey();
        S.design.carve_runs = [{ id: 'a', status: 'done' }];
        const b = answersKey();
        S.design.lighten_runs = [{ id: 'l', status: 'done' }];
        return { a, b, c: answersKey() };""")
    assert len({got["a"], got["b"], got["c"]}) == 3


_RUNS = """const S = { slug: 'x', running: {}, loadRun: {}, design: {} };
const esc = (s) => String(s);
let posts = 0, release;
const gate = new Promise((r) => { release = r; });
const el = () => ({ disabled: false, innerHTML: '', value: '2', querySelector: () => null });
const $ = () => el();
const api = async () => { posts += 1; return { job_id: 'j' }; };
const follow = async () => { await gate; };
const trackJob = () => ({ done: gate });
const plainly = (m) => m;
const clearStation = () => {}, refresh = async () => {}, loadRuns = () => [], lightenRuns = () => [], showHeat = () => {}, holdsHere = () => false, showStation = () => {};
"""


@pytest.mark.parametrize("name,inner", [("runLoad", "startLoad"), ("runLighten", "startLighten")])
def test_a_second_click_starts_nothing(name, inner):
    got = _page((name, inner), _RUNS, f"""const p = {{ id: 'p' }};
        const first = {name}(p), second = {name}(p);
        await second;
        const during = posts;
        release();
        await first;
        await {name}(p);
        return {{ during, after: posts }};""")
    assert got == {"during": 1, "after": 2}                                 # and once it's over, another may start


_BETTER = """const S = { claude: CLAUDE, design: { parts: [{ id: 'p' }] } };
const errs = [], sent = [];
const tellOffer = (m) => errs.push(m), send = (t, s) => sent.push([t, s]);
const refresh = async () => {}, studyDone = () => false;
const setScope = () => {}, goTo = () => {}, runLoad = () => {}, runCarve = () => {}, runLighten = () => {}, adoptStation = () => {};
"""


@pytest.mark.parametrize("claude,errs,sent", [(False, 1, 0), (True, 0, 1)])
def test_try_it_with_no_key_says_so_and_sends_nothing(claude, errs, sent):
    got = _page(("useBetter",), _BETTER.replace("CLAUDE", "true" if claude else "false"),
                """await useBetter({ part: 'p', action: 'use_t', say: 'thicken it' }); return { errs, sent };""")
    assert len(got["errs"]) == errs and len(got["sent"]) == sent
    assert not errs or "isn't set up here" in got["errs"][0]


# --- #159, the second round -----------------------------------------------------------------------------------------
def test_a_carved_part_s_sliver_points_back_at_the_carve(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0, thinnest=0.02, spacing=2.3, too_thin=True, thinnest_where=REAL_WHERE, sees_mm=9.2)
    state = design_api.design_state(store)
    state["parts"][0]["carved"] = True
    got = better.offers(store, state, "tube")
    assert len(got) == 1 and got[0]["button"] == "Roll it back" and got[0]["say"] == "roll it back"
    assert "from the carve" in got[0]["lead"] and "thicken" not in got[0]["text"]


@pytest.mark.parametrize("seen,said", [(9.2, 9.3), (9.207, 9.3), (4.0, 4.1)])
def test_one_number_for_the_wall_and_it_s_rounded_up(seen, said):
    assert load_study.sees_from(seen) == said


def test_the_panel_says_the_card_s_number(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    words = load_study.thin_words(store, "tube", 0.25, {"at": [0, 0, 400]}, 2.302, True)
    assert "walls must be at least 9.3 mm at this size" in words and "9.2" not in words


_STALE = """const S = { claude: true, scope: 'p', design: { parts: [{ id: 'p', version: 3 }], carve_runs: [] } };
const calls = [];
const send = () => {}, setScope = () => {}, goTo = () => {}, runLoad = () => {}, adoptStation = () => {}, tellOffer = () => {};
const runCarve = (p) => calls.push('carve'), runLighten = (p) => calls.push('lighten');
let done = false;
const refresh = async () => { if (done) S.design.carve_runs = [{ part: 'p', version: 3, status: 'done' }]; };
"""


def test_a_stale_tab_can_t_start_a_second_carve():
    got = _page(("useBetter", "studyDone"), _STALE, """await useBetter({ part: 'p', action: 'carve' });
        const first = calls.length; done = true;
        await useBetter({ part: 'p', action: 'carve' });
        return { first, after: calls.length };""")
    assert got == {"first": 1, "after": 1}


_STATION = """const S = { slug: 'x', running: {}, design: { parts: [] } };
let posts = 0, release; const gate = new Promise((r) => { release = r; });
const $ = () => null, STUDY_PATH = {}, clearStation = () => {}, showErr = () => {};
const api = async () => { posts += 1; await gate; };
const refresh = async () => {}, runLoad = () => {};
"""


def test_a_double_click_on_use_it_takes_the_step_once():
    got = _page(("adoptStation", "takeStation"), _STATION, """const a = adoptStation('p', 'r', 1, 'other'), b = adoptStation('p', 'r', 1, 'other');
        await b; const during = posts; release(); await a;
        return { during };""")
    assert got == {"during": 1}


def test_carve_it_is_off_while_its_carve_runs():
    head = """const S = { slug: 'd', carveJob: { 'd/p': { text: 'x' } } };
const carveKey = (pid) => `${S.slug}/${pid}`;
const esc = (s) => String(s);
"""
    got = _page(("betterLines",), head, """const line = { better: true, lead: 'Carve', cost: 'c', button: 'Carve it', action: 'carve', part: 'p' };
        return { h: betterLines({ key: 'work', lines: [line] }, [line]) };""")
    assert " disabled>Carve it" in got["h"]


# --- #159, the server is the gate ---------------------------------------------------------------------------------------
def _lightened(store, pid, rid="20261107-000200-light"):
    """As a real Lighten writes it: once, when it's finished, with no ``status``."""
    _save(lighten.runs_dir(store), {"id": rid, "part": pid, "kind": "lighten", "created": 2.0,
                                    "version": store.design.part(pid).version, "seconds": 60.0, "min_safety": NEED,
                                    "material": "plywood", "spacing_mm": 2.0, "panels": [], "rules": {}, "stations": [],
                                    "notes": []})


@pytest.fixture
def post(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import design_api as D
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.setattr(D, "_aero_available", lambda: True)
    monkeypatch.setattr(carve, "study", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(lighten, "study", lambda *a, **k: {"ok": True})
    c = TestClient(create_app())

    def go(store, kind, **body):
        return c.post(f"/api/designs/{os.path.basename(store.root)}/{kind}", json={"part": "tube", "min_safety": 2, **body})

    return go


FINISHED = {"carve": _carved, "lighten": _lightened}


@pytest.mark.parametrize("kind", ["carve", "lighten"])
def test_a_stale_button_can_t_start_a_second_run_of_a_finished_version(tmp_path, post, kind):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    FINISHED[kind](store, "tube")
    got = post(store, kind)
    assert got.status_code == 409 and got.json()["detail"] == f"This version already has a finished {kind}: its result is on the card."


@pytest.mark.parametrize("kind", ["carve", "lighten"])
def test_a_run_asked_for_again_goes_ahead(tmp_path, post, kind):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    FINISHED[kind](store, "tube")
    assert post(store, kind, again=True).status_code == 200


@pytest.mark.parametrize("kind", ["carve", "lighten"])
def test_a_finished_run_of_an_older_version_doesn_t_stop_this_one(tmp_path, post, kind):
    store = _store(tmp_path, TUBE, "tube")
    FINISHED[kind](store, "tube")
    store.write_part("tube", TUBE, intent="again")
    _check(store, "tube", 3.0)
    assert post(store, kind).status_code == 200


@pytest.mark.parametrize("kind", ["carve", "lighten"])
def test_what_blocked_says_stops_it_even_asked_again(tmp_path, post, kind):
    """The same test the buttons read: a stale button on a part that now fails is refused, with why."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 0.5)
    for extra in ({}, {"again": True}):
        got = post(store, kind, **extra)
        assert got.status_code == 409 and "already fails" in got.json()["detail"], got.json()


def test_a_carve_on_an_unchecked_version_is_refused_with_why(tmp_path, post):
    """A stale Carve on a new version that hasn't been checked."""
    store = _store(tmp_path, TUBE, "tube")
    got = post(store, "carve")
    assert got.status_code == 409 and "Check it holds first" in got.json()["detail"]


@pytest.mark.parametrize("kind", ["carve", "lighten"])
def test_a_first_run_goes_ahead(tmp_path, post, kind):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    assert post(store, kind).status_code == 200


def test_a_carved_part_that_fails_points_back_at_the_carve_too(tmp_path):
    """#159 review: only the holds path was pinned."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 0.5, thinnest=0.02, spacing=2.3, too_thin=True, thinnest_where=REAL_WHERE, sees_mm=9.2)
    state = design_api.design_state(store)
    state["parts"][0]["carved"] = True
    state["parts"][0]["blocked"] = load_study.blocked(store, "tube")
    got = better.offers(store, state, "tube")
    assert [ln["button"] for ln in got] == ["Roll it back"] and not any("thicken" in ln["text"] for ln in got)
    assert got[0]["cost"].startswith("Roll it back, or use an earlier step of the carve")
    assert got[0]["local"]


@pytest.mark.parametrize("local,sent", [(True, 1), (False, 0)])
def test_rolling_back_needs_no_claude(local, sent):
    got = _page(("useBetter",), _BETTER.replace("CLAUDE", "false"), f"""await useBetter({{ part: 'p', action: 'use_t', say: 'roll it back', local: {str(local).lower()} }});
        return {{ sent }};""")
    assert len(got["sent"]) == sent


def test_only_the_again_buttons_say_again():
    src = open(_JS).read()
    assert "runCarve(p, e.target.dataset.again === '1')" in src and "runLighten(p, e.target.dataset.again === '1')" in src
    assert "if (ln.action === 'carve') return runCarve(p);" in src and "if (ln.action === 'lighten') return runLighten(p);" in src


def test_a_lighten_on_a_new_unchecked_version_is_no_repeat(tmp_path, post):
    store = _store(tmp_path, TUBE, "tube")
    _lightened(store, "tube")
    store.write_part("tube", TUBE, intent="again")
    assert post(store, "lighten").status_code == 200


@pytest.mark.parametrize("run,done", [("{ part: 'p', version: 3 }", True), ("{ part: 'p', version: 3, status: 'done' }", True),
                                      ("{ part: 'p', version: 3, status: 'running' }", False),
                                      ("{ part: 'p', version: 2 }", False)])
def test_the_page_reads_finished_as_the_server_does(run, done):
    head = f"const S = {{ design: {{ parts: [{{ id: 'p', version: 3 }}], lighten_runs: [{run}] }} }};\n"
    assert _page(("studyDone",), head, "return { d: studyDone('lighten', 'p') };") == {"d": done}


@pytest.mark.parametrize("status", ["cancelled", "failed", "running"])
def test_a_carve_that_didn_t_finish_doesn_t_block_a_new_one(tmp_path, post, status):
    """#159 review: a mutant dropping the status test counted a cancelled run as finished."""
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _save(carve.runs_dir(store), {"id": "20261107-000100-carve", "part": "tube", "kind": "carve", "created": 2.0, "status": status,
                                  "version": store.design.part("tube").version, "stations": []})
    assert post(store, "carve").status_code == 200


def test_the_page_doesn_t_count_a_cancelled_run_as_finished():
    head = "const S = { design: { parts: [{ id: 'p', version: 3 }], carve_runs: [{ part: 'p', version: 3, status: 'cancelled' }] } };\n"
    assert _page(("studyDone",), head, "return { d: studyDone('carve', 'p') };") == {"d": False}
