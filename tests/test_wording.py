"""CALI-99 (#89) — the wording pass: the bar stool walkthrough's smaller findings, the reviews' wording nits, and
#137's P2 list. No verdict changes here, except where a ✓ stood over nothing measured (P2 item 10)."""

import os
import re

import pytest

from caliper import answers, chat, design_api
from caliper.design import DesignStore, short_name

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _src():
    return open(JS).read()


# --- item 1: the design isn't named "I want" ----------------------------------------------------------------------

@pytest.mark.parametrize("said,name", [
    ("I want to make a bar stool to hold up to a 250lb person, sitting.", "Bar stool"),    # Theo's
    ("I want a bar stool", "Bar stool"), ("I need a shelf for my books", "Shelf"),
    ("Make me a step stool", "Step stool"), ("Can you design a planter box?", "Planter box"),
    ("I'd like a bike rack", "Bike rack"), ("I want to build a camper box for my Leaf", "Camper box"),
    ("A step stool so my 6-year-old can reach the sink.", "Step stool"),
])
def test_a_design_is_named_for_what_it_is_not_the_request(said, name):
    assert short_name(said) == name


# --- item 3: a one-part design's top line is its part's description -------------------------------------------------

def test_the_design_card_s_top_line_is_the_part_s_description(tmp_path):
    pytest.importorskip("cadquery")
    from .test_load_study import BOX_STOOL

    store = DesignStore.create("I want to make a step stool to reach the sink.", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="A one-platform step stool from 3/4 in plywood. Glued and screwed.")
    what = next(c for c in answers.answers(store, design_api.design_state(store)) if c["key"] == "what")
    assert what["lines"][0]["text"] == "A one-platform step stool from 3/4 in plywood."


# --- item 6: a print-time objective offers the carve ------------------------------------------------------------------

def _checked(runs, version=7, units="mm"):
    """A design whose only part, the stool at ``version``, has these strength runs (newest first), saved as runs are:
    what ``load_study.blocked`` reads, without a build."""
    import json
    import tempfile
    from types import SimpleNamespace

    from caliper import load_study

    store = SimpleNamespace(root=tempfile.mkdtemp(), design=SimpleNamespace(
        part=lambda pid: SimpleNamespace(version=version), display_units=units))
    for i, r in enumerate(runs):
        rid = f"2026110{7 - i}-000000-stool"
        os.makedirs(os.path.join(load_study.runs_dir(store), rid))
        with open(os.path.join(load_study.runs_dir(store), rid, "run.json"), "w") as f:
            json.dump({"id": rid, "part": "stool", "created": 100.0 - i, **r}, f)
    return store


def test_a_print_time_objective_offers_the_carve_on_a_printed_part(monkeypatch):
    from caliper import construction as C
    from caliper import load_study

    monkeypatch.setattr(C, "declared", lambda store, pid: {"construction": [{"name": "cone", "kind": "printed"}]})
    monkeypatch.setattr(load_study, "blocked", lambda store, pid: None)
    p = {"id": "i_want", "loads": True, "carved": False}
    mk = {"printed": [{"material": "petg", "pieces": 3, "hours": 165}]}
    aim = {"goals": {"objectives": [{"metric": "print.hours", "direction": "min"}]}}
    line = answers._carve_offer(None, aim, p, mk)
    assert line["text"] == "Carve the cone where it isn't working, to print less of it: try Carve it."
    assert line["action"] == "carve" and "carve: 'loadBox'" in _src()
    assert answers._carve_offer(None, {"goals": {"objectives": [{"metric": "cost.usd"}]}}, p, mk) is None
    assert answers._carve_offer(None, aim, {**p, "carved": True}, mk) is None
    assert answers._carve_offer(None, aim, {**p, "loads": False}, mk) is None


# --- the reviews' wording nits ----------------------------------------------------------------------------------------

def test_the_run_picker_says_each_run_s_own_verdict():
    """#96's final review: older runs read "not trusted" in the picker where on their versions they don't hold."""
    assert "· ${runWord(r)}</option>`).join('')}</select>`" in _src()
    assert "p.untrusted ? 'not trusted' : runWord(r)" not in _src()


def test_a_fail_on_a_filled_in_shape_is_likely_weaker_and_a_shape_unchecked_says_so():
    """#100's merge checks: "likely weaker", not "weaker still"; and a shape that couldn't be checked isn't "a filled-in
    shape", which isn't known. The ✗-on-filled-in line itself, pinned."""
    run = {"min_safety": 2, "spacing_mm": 1.0, "thinnest_mm": 19.0,
           "cases": [{"name": "an adult stepping up", "safety": 1.2, "holds": False, "governs": "plate"}]}
    (c,) = run["cases"]
    filled = answers._case_line("stool", run, c, "its pieces fill its shape", False, True)
    assert filled["status"] == "bad" and filled["text"].startswith("Doesn't hold an adult stepping up: only 1.2 times")
    assert filled["text"].endswith(" It ran on a solid with more in it than its pieces: filled in, the part as built "
                                   "is likely weaker; or a piece is missing from its construction.")
    unknown = answers._case_line("stool", run, c, "couldn't check its shape (no mesh)", False, True)
    assert unknown["text"].endswith(" Its shape couldn't be checked against its pieces, so this number may not be "
                                    "the part's.")
    assert answers.filled_fail(answers.untrusted("stool", "couldn't check its shape")).startswith(" Its shape couldn't")
    assert "weaker still" not in open(answers.__file__).read()


def test_the_scorecard_s_trust_text_says_which_it_is():
    src = open(os.path.join(os.path.dirname(answers.__file__), "scorecard.py")).read()
    assert "not trusted: its shape couldn't be checked" in src and 'str(untrue).startswith("couldn\'t")' in src


def test_the_heat_callout_rounds_the_material_s_strength():
    """From #3a's session: "breaks near 13.616958762213404"."""
    assert "breaks near ${fixed(run.material.strength, 1)} MPa" in _src()
    assert "breaks near ${run.material.strength})" not in _src()


def test_a_plan_without_a_key_never_says_press_build_it(tmp_path):
    """#104's merge check: the no-key page shows the key's note where Build it would be."""
    base = {"name": "Wind turbine", "prompt": "A wind turbine", "parts": [], "requirements": [],
            "plan": {"headline": "A wind turbine in 4 parts"}}
    for claude, want in ((False, "Building it needs Claude, which isn't set up here."),
                         (True, "Say what to change, or press Build it.")):
        what = next(c for c in answers.design(None, {**base, "claude": claude}) if c["key"] == "what")
        (line,) = [ln["text"] for ln in what["lines"] if ln["text"].startswith("That's the plan")]
        assert line.endswith(want) and ("press Build it" in line) == claude


# --- #137's P2 list -----------------------------------------------------------------------------------------------------

def test_the_least_safety_box_is_never_blank():
    assert 'value="${(runs[0] && runs[0].min_safety) || 2}"' in _src()


def test_a_check_that_just_ran_resets_the_test_beside_it():
    fn = re.search(r"^async function startLoad\(.*?^}\n", _src(), re.S | re.M).group(0)
    assert "S.trial = null;" in fn and fn.index("S.trial = null;") < fn.index("await refresh();")


def test_the_shop_check_is_no_tick_over_nothing_worked_out(tmp_path, monkeypatch):
    """P2 item 10: "✓ your shop can make every piece — 0 measured" where no part's plan could be made."""
    pytest.importorskip("cadquery")
    from caliper import making, scorecard

    from .test_load_study import BOX_STOOL

    monkeypatch.setenv("CALIPER_SLICER", "")
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL.split("\ndef loads(")[0], intent="a box")

    def broken(store, pid):
        raise ValueError("its pieces couldn't be read")

    monkeypatch.setattr(making, "plan", broken)
    (shop,) = [c for c in scorecard.compute(store)["checks"] if c["id"] == "make:shop"]
    assert shop["status"] == "unknown" and shop["value"] is None
    assert "couldn't work out how to make stool: its pieces couldn't be read" in shop["note"]


def test_the_shop_check_waits_when_one_part_s_plan_couldn_t_be_made(tmp_path, monkeypatch):
    """#144 review: two parts, one whose making plan raises and one that works, read ✓ with ``settled = planned``
    (the ``and not unplanned`` dropped). It waits, naming the part and why."""
    pytest.importorskip("cadquery")
    from caliper import making, scorecard

    from .test_load_study import BOX_STOOL

    monkeypatch.setenv("CALIPER_SLICER", "")
    store = DesignStore.create("two stools", base=str(tmp_path / "designs"))
    for pid in ("stool", "step"):
        store.write_part(pid, BOX_STOOL.split("\ndef loads(")[0], intent="a box")
    real = making.plan

    def one_broken(store, pid):
        if pid == "step":
            raise ValueError("its pieces couldn't be read")
        return real(store, pid)

    monkeypatch.setattr(making, "plan", one_broken)
    (shop,) = [c for c in scorecard.compute(store)["checks"] if c["id"] == "make:shop"]
    assert shop["status"] == "unknown" and shop["value"] is None and shop["trust"] is None
    assert "couldn't work out how to make step: its pieces couldn't be read" in shop["note"]
    assert "stool:" not in shop["note"]                                   # the one that worked isn't named


def test_a_stray_face_is_said_where_in_the_design_s_units():
    """P2 item 11: "at z 14.0–15.6 mm" on an inch design."""
    meta = {"strays": "left out 1 stray face from the CAD's meshing (at z 14.0–15.6 mm)", "strays_n": 1,
            "strays_z": [14.0, 15.6]}
    assert answers._strays(meta, True) == "left out 1 stray face from the CAD's meshing (at z 0.6 in)"
    assert answers._strays(meta, False) == "left out 1 stray face from the CAD's meshing (at z 14 mm–16 mm)"
    assert answers._strays({"strays": "as measure said it"}, True) == "as measure said it"


def test_an_old_reply_s_traceback_is_shown_to_its_last_line_without_server_paths():
    """P2 item 12: the 11/6 reply kept a raw traceback naming /Users/…/_sandbox_runner.py."""
    reply = ("I couldn't build 'stool' after 2 attempt(s). Last error:\n"
             "  Traceback (most recent call last):\n"
             "    File \"/Users/someone/caliper/src/caliper/_sandbox_runner.py\", line 40, in <module>\n"
             "      exec(code)\n"
             "  ValueError: Standard_Failure at /Users/someone/x/part.py\n"
             "Nothing was added to the design.")
    assert chat.shown(reply) == ("I couldn't build 'stool' after 2 attempt(s). Last error:\n"
                                 "  ValueError: Standard_Failure at part.py\n"
                                 "Nothing was added to the design.")
    assert chat.shown("All good.") == "All good."
    src = open(design_api.__file__).read()
    assert '"reply": chat.shown(e["reply"])' in src



# --- #144 review: the offer asks what the Carve button asks ----------------------------------------------------------

FAILS = {"version": 7, "seconds": 60, "spacing_mm": 4.6, "safety": 0.53, "min_safety": 2, "thinnest_mm": 19.0,
         "cases": [{"name": "sitting", "safety": 0.53, "holds": False, "governs": "plate"}]}
HOLDS = {**FAILS, "safety": 3.0, "cases": [{"name": "sitting", "safety": 3.0, "holds": True, "governs": "plate"}]}
THIN = {**HOLDS, "too_thin": True, "thin_said": "its 0.25 mm walls are too thin for the strength check to see."}


@pytest.mark.parametrize("runs,why", [
    ([FAILS], "already_fails"),
    ([THIN], "too_thin"),
    ([{**HOLDS, "cases": [{"name": "sitting", "safety": 3.0, "holds": True, "fea": {"supported": False}}]}],
     "unsupported"),
    # a finer run asked for, the latest, holding: the carve runs at the default voxels, whose check fails
    ([{**HOLDS, "spacing_mm": 2.3}, FAILS], "already_fails"),
    ([HOLDS], None),
    ([{**FAILS, "version": 6}], "unchecked"),           # an older version's check isn't this one's (Theo's v7)
    ([], "unchecked"),
])
def test_no_carve_is_offered_where_the_carve_button_refuses_it(monkeypatch, runs, why):
    """#144 review: on the bar stool, How do I make it? offered "Carve the cone skirt…" while the Carve button refused
    it ("its check says it fails…"). Both read load_study.blocked now; the page shows its words."""
    import json

    from caliper import construction as C
    from caliper import load_study

    from .test_carve_click import _page, _run

    monkeypatch.setattr(C, "declared", lambda store, pid: {"construction": [{"name": "cone", "kind": "printed"}]})
    store = _checked(runs)
    got = load_study.blocked(store, "stool")
    assert (got or {}).get("why") == why
    p = {"id": "stool", "loads": True, "carved": False}
    mk = {"printed": [{"material": "petg", "pieces": 3, "hours": 165}]}
    aim = {"goals": {"objectives": [{"metric": "print.hours", "direction": "min"}]}}
    offer = answers._carve_offer(store, aim, p, mk)
    button = _run(_page(["carveBlocked"], extra=f"out = carveBlocked({{id: 'stool', blocked: {json.dumps(got)}}});"))
    assert button == ((got or {}).get("carve") or "")                 # the button's reason: the same words, or none
    if why == "unchecked":                                             # both say check it first (#144, Theo's v7)
        assert offer["text"] == ("Check it holds first, then carve the cone where it isn't working, to print less of "
                                 "it.") and offer["action"] == "load"
        assert button == "Check it holds first: a carve starts from its strength check"
    else:
        assert (offer is None) == (why is not None)
        assert bool(button) == (offer is None)                         # never both offered and refused
        if offer:
            assert offer["action"] == "carve"
    if why == "already_fails":
        assert button == "it already fails (0.5 times over): make it hold first, then carve"


def test_the_design_state_carries_each_part_s_blocked(tmp_path):
    """What the page's carveBlocked reads: the server's own, on every part."""
    pytest.importorskip("cadquery")
    from .test_preflight_bar_stool import TUBE, _failed_check

    store = DesignStore.create("a printed tube", base=str(tmp_path / "designs"))
    store.write_part("tube", TUBE, intent="a printed tube")
    assert design_api.design_state(store)["parts"][0]["blocked"]["why"] == "unchecked"     # no check yet
    _failed_check(store, "tube")
    got = design_api.design_state(store)["parts"][0]["blocked"]
    assert got["why"] == "already_fails" and got["carve"].startswith("its check says it fails (0.5 times over")
