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


def _check(store, pid, safety, *, plate=None, thinnest=10.0, spacing=2.0, rid="20261107-000000-check"):
    """A strength run on this version: the FEA governs (resolved: 5 voxels across its walls), or the plate check."""
    case = {"name": "a foot", "lb": 40, "factor": 2.0, "safety": safety, "holds": safety >= NEED,
            "governs": "plate" if plate else "fea", "plate": plate,
            "fea": {"supported": True, "safety": safety if not plate else 50.0, "deflection_mm": 0.1}}
    _save(load_study.runs_dir(store), {"id": rid, "part": pid, "version": store.design.part(pid).version,
                                        "created": 1.0, "seconds": 60.0, "min_safety": NEED, "safety": safety,
                                        "holds": safety >= NEED, "spacing_mm": spacing, "thinnest_mm": thinnest,
                                        "across": thinnest / spacing, "cases": [case]})


def _carved(store, pid, *, whole=3.0, safety=2.6, saved=644):
    _save(carve.runs_dir(store), {
        "id": "20261107-000100-carve", "part": pid, "kind": "carve", "version": store.design.part(pid).version,
        "created": 2.0, "status": "done", "min_safety": NEED, "spacing_mm": 2.0, "thinnest_mm": 10.0, "across": 5.0,
        "share": "printed", "best": 1,
        "stations": [{"index": 0, "removed": 0.0, "safety": 3.0, "holds": True, "whole": 3.0, "whole_holds": True,
                      "saved_g": 0},
                     {"index": 1, "removed": 0.61, "safety": safety, "holds": safety >= NEED, "whole": whole,
                      "whole_holds": whole >= NEED, "saved_g": saved}]})


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
    assert _offers(store, "tube") == []                            # no check yet: blocked, "check it holds first"
    _check(store, "tube", 3.0)
    (line,) = _offers(store, "tube")
    assert line["text"] == ("Carve the tube where it isn't working, to use less filament: it takes at least about "
                            "45 min at this size.")                              # 60 s × 45
    assert line["action"] == "carve" and line["better"] and line["status"] == "info" and line["study"] == "load"


def test_after_a_carve_it_gives_the_result_to_use(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    _check(store, "tube", 3.0)
    _carved(store, "tube")
    (line,) = _offers(store, "tube")
    assert line["text"] == ("Carve the tube where it isn't working: 61% of the printed part carved away, 644 g less "
                            "filament, still about 2.6 times over.")
    assert line["action"] == "carve_use" and line["station"] == 1


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
    assert line["text"].endswith("still more than 10 times over.")


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
                              "times over.")


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
    assert menu["lighten"]["why"] == "it has no sheet pieces: a printed part is carved"
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
