"""CALI-92 (#70), the leftovers' second part: the reviewer's weight notes from #237, #235's three, #209's notes, the
filled() follow-up, the router's edge cases, and items 10 and 20. Stubbed models only."""

import os
import re

import pytest

from caliper import making

from .test_leftovers_70 import SLICED, _goal, mixed  # noqa: F401  (the fixture)

FAILED = {"hours": None, "filament_g": None, "usd": None, "trust": None, "from": "no estimate (it crashed)", "slicer_failed": True}


# --- #237's weight notes ---------------------------------------------------------------------------------------------------
def test_only_the_solid_s_share_is_a_bound():
    solid = {"bom": {"printed": [{"filament_from": making.FROM_SOLID}]}}
    rough = {"bom": {"printed": [{"filament_from": making.FROM_ROUGH}]}}
    sliced = {"bom": {"printed": [{"filament_from": making.FROM_SLICER}]}}
    assert making.filament_bound([solid]) and not making.filament_bound([rough]) and not making.filament_bound([sliced])
    assert not making.filament_bound([solid, rough])
    assert making.settled_by_bound("<=", True) and making.settled_by_bound(">=", False)
    assert not making.settled_by_bound("<=", False) and not making.settled_by_bound(">=", True)


@pytest.mark.parametrize("limit,guessed", [(5, False), (3, True)])
def test_a_weight_under_goal_on_the_solid_s_upper_bound(mixed, monkeypatch, limit, guessed):
    """Note 2: the solid's share is an upper bound: under the limit it passes; over it, it may still be under: a guess."""
    from caliper import answers, design_api, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    _goal(mixed, "weight.total_lb", limit)
    state = design_api.design_state(mixed)
    now = answers.measured(mixed, state)
    assert now["weight.total_lb"] == pytest.approx(3.5, abs=0.05) and now.get("filament.upper")
    (line,) = [ln for ln in answers.held_to(state, now) if "light enough" in ln["text"].lower()]
    assert ("a guess" in line["text"]) is guessed
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert (check["status"] == "pass") is not guessed


def test_a_weight_limit_under_the_wood_alone_is_a_sure_fail(mixed, monkeypatch):
    """The upper bound is the printed share's only: the wood weighs what it weighs. A limit under the wood alone is a ✗, not
    an estimate (#70, the book's 0.2 lb goal on the mixed stool read "estimate")."""
    from caliper import answers, design_api, making, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    state = design_api.design_state(mixed)
    now = answers.measured(mixed, state)
    wood = now["weight.total_lb"] - now["filament.upper_lb"]
    assert 0.3 < wood < now["weight.total_lb"] - 0.3, now                # some of each
    _goal(mixed, "weight.total_lb", round(wood - 0.2, 2))
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert line["status"] == "bad" and "a guess" not in line["text"], line
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert check["status"] == "fail", check
    assert making.settled_by_bound("<=", False, False) and not making.settled_by_bound("<=", False, True)
    assert making.settled_by_bound(">=", True, True) and not making.settled_by_bound(">=", True, False)


def test_a_part_s_weight_says_where_its_filament_came_from(mixed, monkeypatch):
    """Note 3: weight.table read trust model, source construction, while its value was the rough figure."""
    from caliper import printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: {**SLICED, "trust": "rough", "from": "rough"})
    m = scorecard.compute(mixed)["metrics"]["weight.table"]
    assert m["trust"] == "rough" and m["source"] == "a guess (the filament is a rough guess)"


def test_the_panel_says_its_table_is_the_solid_s(mixed):
    """Note 1: the table, the pieces and the balance are the solid's: said, where the part's weight above isn't."""
    from .test_small_words import _js

    got = _js(["solidSaid"], "return [solidSaid({mass_lb: 2.6, filament_more_kg: -0.396}), solidSaid({mass_lb: 3.5})];",
              "const lbs = (x) => `${(+x).toFixed(1)} lb`;")
    assert got[0].startswith("<div") and "the model's solid" in got[0] and "(3.5 lb)" in got[0] and "2.6 lb" in got[0]
    assert got[1] == ""


def test_a_slicer_that_failed_leaves_the_print_total_unknown_not_a_crash(mixed, monkeypatch):
    """Found on the way: a failed slice's hours are None, and the scorecard's sum raised TypeError."""
    from caliper import printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    m = scorecard.compute(mixed)["metrics"]
    assert m["print.hours"]["value"] is None and "the slicer couldn't" in m["print.hours"]["note"]


# --- #235's three notes --------------------------------------------------------------------------------------------------------
def test_a_very_slender_wall_reads_under_a_tenth_not_0_times_over():
    """#235 note 3: 0.02 against 2 was cut to "0", so the card said "only 0 times over"."""
    from caliper import answers

    assert answers.safety_num(0.02, 2.0) == answers.safety_num(0.099, 2.0) == answers.safety_num(0.01) == "under 0.1"
    assert answers.safety_num(0.1, 2.0) == "0.1" and answers.safety_num(0.19, 2.0) == "0.1"
    assert answers._times(0.02, need=2.0) == "under 0.1 times over"
    assert answers._times(0.02, about=True, need=2.0) == "under 0.1 times over"       # never "about under"


def test_the_fail_line_says_under_a_tenth_without_only():
    from caliper import answers

    run = {"min_safety": 2.0, "material": {"key": "plywood"}, "cases": []}
    case = {"name": "An adult standing", "lb": 200, "factor": 1.0, "safety": 0.01, "holds": False, "governs": "buckling",
            "buckling": [{"piece": "wall", "done": True, "safety": 0.01, "down": True, "edges_held": 0}],
            "fea": {"supported": True, "safety": 40.0}}
    run["cases"] = [case]
    text = answers._case_line("p", run, case, None, False, False)["text"]
    assert "Doesn't hold an adult standing: under 0.1 times over, and it needs 2." in text, text


def _flat(points, t=6.35):
    import numpy as np

    return {"name": "wall", "kind": "sheet", "thickness": t, "sides": [1], "polys": [np.asarray(points, float)]}


@pytest.mark.parametrize("deg", [8, 20])
def test_a_load_a_little_off_its_edges_isn_t_checked_as_square(deg):
    """#235 note 2: a slant that leaves one pair of edges reading as along it, but the other not square to it."""
    import math

    from caliper import buckling, load_study

    a = math.radians(deg)
    f = (1000 * math.sin(a), 0.0, -1000 * math.cos(a))
    (row,) = buckling.check([_flat([(0, 0, 0), (300, 0, 0), (300, 0, 600), (0, 0, 600)])], {"force": f, "factor": 2.0},
                            {"E": 8000.0, "across": 0.5}, 2.0)
    assert not row["done"] and row["why"] == "the load runs at a slant to its edges", row
    assert load_study.buckling_notes([_flat([(0, 0, 0), (300, 0, 0), (300, 0, 600), (0, 0, 600)])],
                                     [{"force": f, "factor": 2.0}], {"E": 8000.0, "across": 0.5}) != [load_study.BUCKLING_CHECKED]


def test_a_shove_in_a_sheet_s_plane_says_it_s_taken_as_a_squeeze():
    """#235 note 1: a sideways push on a top, in its own plane, isn't a load running down a wall; it's taken as one, the safe
    side. The verdict stays (Rule 6); the words say what it was taken as."""
    from caliper import answers, buckling

    top = _flat([(0, 0, 400), (300, 0, 400), (300, 300, 400), (0, 300, 400)])
    wall = _flat([(0, 0, 0), (300, 0, 0), (300, 0, 600), (0, 0, 600)])
    ply = {"E": 8000.0, "across": 0.5}
    (shoved,) = buckling.check([top], {"force": (0.0, 300.0, 0.0), "factor": 1.0}, ply, 2.0)
    (pressed,) = buckling.check([wall], {"force": (0.0, 0.0, -1000.0), "factor": 1.0}, ply, 2.0)
    assert shoved["done"] and shoved["down"] is False and pressed["down"] is True
    run = {"min_safety": 2.0}
    c = {"governs": "buckling", "buckling": [{**shoved, "piece": "top", "safety": 0.5}], "fea": {"safety": 9.0}}
    said = answers.fail_hedge(run, c, {"kind": "fails"}, False)
    assert said.startswith(" The top folds first, taken as squeezed end to end by a push that doesn't run down it"), said
    assert "the safe side" in said and "running down it (" not in said
    c["buckling"][0] = {**pressed, "safety": 0.5}
    assert answers.fail_hedge(run, c, {"kind": "fails"}, False).startswith(" The wall folds first: it's too slender for the load running down it")
    # the page's "(by …)" says it too
    from .test_carve_click import _page, _run

    out = _run(_page(["foldedBy"], extra="""
const esc = (s) => String(s);
out = [foldedBy({ buckling: [{ piece: 'top', done: true, safety: 20.9, down: false, edges_held: 0 }] }),
       foldedBy({ buckling: [{ piece: 'wall', done: true, safety: 2.6, down: true, edges_held: 0 }] })];
"""))
    assert "a push that doesn't run down it, taken as a squeeze, the safe side for the sheet" in out[0], out
    assert out[1].endswith("free along its sides, its top free to sway, its whole load on it"), out


# --- #209's notes ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("items, said", [
    ([{"kind": "sheet", "material": "plywood"}, {"kind": "lump", "name": "hinge"}], None),          # part_scripts.md's own
    ([{"kind": "sheet", "material": "plywood"}, {"kind": "stick", "size": "2x4"}], None),           # lumber, as piece() reads it
    ([{"kind": "printed"}, {"kind": "lump", "name": "hinge"}], "Printers, infill and the bond"),
    ([{"kind": "sheet", "material": "plywood"}, {"kind": "sheet", "material": "foam"}], "the other materials"),
])
def test_the_promise_skips_a_lump_and_reads_a_bare_stick_as_lumber(items, said, monkeypatch):
    """#209 note 1: a hinge lump read as another material, and a stick with no material as "other"."""
    from caliper import answers

    monkeypatch.setattr(answers.C, "declared", lambda store, pid: {"construction": items})
    got = answers.promise(None, ["p"])
    assert (got == answers.PROMISE) if said is None else (said in got), got


def test_a_ring_seat_s_basis_says_on_a_ring_beneath_it(monkeypatch, tmp_path):
    """#209 note 3: a round seat on a ring was called "held all round"; the ring check rests it on a ring beneath it."""
    from caliper import trials
    from caliper.design import DesignStore

    from .test_trials import _plate_run

    def ring(store, pid):
        run = _plate_run("plate")
        run["cases"][0]["plate"].update({"support": "ring", "ring_mm": 300.0})
        return run

    store = DesignStore.create("a bar stool", base=str(tmp_path))
    store.write_part("seat", "def build(params):\n    return None\n", intent="x")
    monkeypatch.setattr(trials, "_run", ring)
    basis = trials.predict(store, "seat")["basis"]
    assert "the plate check's (on a ring beneath it, edges free to turn" in basis and "held all round" not in basis, basis
    monkeypatch.setattr(trials, "_run", lambda s, pid: _plate_run("plate"))
    assert "the plate check's (held all round, edges free to turn" in trials.predict(store, "seat")["basis"]


def test_the_build_book_s_promise_keeps_the_card_s_rough_note(monkeypatch):
    """#209 note 4: the card adds "Printed parts are a rough model…" to a printed verdict's promise; the book dropped it."""
    from caliper import load_study, release

    import caliper.answers as A

    monkeypatch.setattr(A, "promise", lambda store, parts: "A prediction.")
    rough = {"seat": [{"name": "a", "rough": True}], "legs": [{"name": "b", "rough": False}]}
    assert release._promise(None, ["seat", "legs"], rough) == "A prediction. " + load_study.ROUGH
    assert release._promise(None, ["legs"], {"legs": rough["legs"]}) == "A prediction."
    assert release._promise(None, ["seat"], {}) == "A prediction."


def test_every_reader_says_both_causes_of_a_solid_with_more_in_it():
    """#209 note 2: "a filled-in shape" was still the only cause in the scorecard, Studies, the run's note, the book's
    cell and the page's Lighten and carve lines; with a piece missing from construction() the solid is the part as built."""
    import pathlib

    from caliper import load_study, release, studies

    more = "a solid with more in it than its pieces"
    assert load_study.NO_RESULT["untrusted"] == f"not trusted: it ran on {more}"
    assert release._safety_cell({"verdict": {"kind": "untrusted"}})[0] == f"not trusted: checked on {more}"
    assert studies._headline("lighten", {"filled": True, "stations": [{"index": 0, "holds": True, "saved_lb": 0.0,
                                                                        "safety": 3.0}]})[0].startswith(f"not trusted, on {more}:")
    assert load_study.FILLED_NOTE.startswith(f"This ran on {more}: its shape filled in, or a piece missing from its construction")
    src = pathlib.Path(load_study.__file__).parent
    for f in ("load_study.py", "scorecard.py", "studies.py", "release.py", "chat.py", "answers.py", "web/static/design.js"):
        said = re.findall(r"""["'`][^"'`\n]*filled-in shape""", (src / f).read_text())    # in words a person reads
        assert not said, (f, said)


# --- the filled() follow-up ------------------------------------------------------------------------------------------------
def _filled_run(v):
    return {"id": "r1", "part": "stool", "version": v, "kind": "load", "filled": True, "cut": True, "min_safety": 2.0,
            "spacing_mm": 3.0, "resolved": True, "safety": 3.0, "holds": True,
            "cases": [{"name": "Dad", "lb": 200, "factor": 2.0, "safety": 3.0, "holds": True, "governs": "fea",
                       "fea": {"supported": True, "safety": 3.0}}]}


def _box(tmp_path):
    import os

    from caliper.design import DesignStore

    from .test_filled_verdict import GOALS
    from .test_load_study import BOX_STOOL

    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(GOALS)
    return store


def test_the_card_s_goal_takes_the_current_run_s_own_filled(tmp_path, monkeypatch):
    """The run on this version says it ran on a filled solid; filled(), asked now, can't tell. The card's goal said "holds"."""
    from caliper import answers, consistency

    store = _box(tmp_path)
    v = store.design.part("stool").version
    monkeypatch.setattr(consistency, "filled", lambda s, pid: None)
    now = answers.measured(store, {"parts": [{"id": "stool", "version": v}], "load_runs": [_filled_run(v)]})
    assert now.get("strength.filled", "").startswith("Not trusted yet: the strength check ran on a solid with more in it"), now
    older = answers.measured(store, {"parts": [{"id": "stool", "version": v}], "load_runs": [_filled_run(v - 1)]})
    assert "strength.filled" not in older                          # an older version's run isn't this one's


def test_the_scorecard_takes_the_current_run_s_own_filled(tmp_path, monkeypatch):
    from caliper import consistency, cutplan, scorecard
    from caliper import load_study as L

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store = _box(tmp_path)
    v = store.design.part("stool").version
    monkeypatch.setattr(consistency, "filled", lambda s, pid: None)
    monkeypatch.setattr(L, "list_runs", lambda s, pid=None: [_filled_run(v)])
    monkeypatch.setattr(L, "study", lambda *a, **k: pytest.fail("a stored run of this version is used"))
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_adult"]
    assert check["status"] == "untrusted", check


# --- reviewer-2's router edge cases (#209, #212) ------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def designs(tmp_path_factory):
    from caliper import samples
    from caliper.design import DesignStore

    d = tmp_path_factory.mktemp("router")
    return DesignStore.create("nothing yet", base=str(d / "empty")), samples.open_sample("step-stool", base=str(d / "stool"))


@pytest.mark.parametrize("message", [
    "use plain words: why is it wider and heavier",                       # "heavier" lands after "and"
    "put it in plain English: why is it taller than before and heavier",
    "use plain words - is it heavier than before",                        # a dash
    "use plain words, it's heavier than I thought",                       # a statement
])
def test_a_plain_words_question_changes_nothing(designs, message):
    from caliper import chat

    for store in designs:
        got = chat.offline_classify(store, message, None)
        assert got.action == "answer", (store.design.name, message, got)


@pytest.mark.parametrize("message", ["use plain words, and make it wider", "use plain words - and make it 2 in taller"])
def test_a_plain_words_request_with_a_change_is_still_the_change(designs, message):
    from caliper import chat

    _, stool = designs
    assert chat.offline_classify(stool, message, None).action == "refine", message


@pytest.mark.parametrize("message, action", [("I need them painted", "refine"), ("I need it by Friday", "answer"),
                                             ("I need it", "answer"), ("I need them sanded smooth", "refine")])
def test_i_need_them_painted_is_a_change_and_i_need_it_by_friday_isn_t(designs, message, action):
    from caliper import chat

    _, stool = designs
    pid = stool.design.parts[0].id
    assert chat.offline_classify(stool, message, pid).action == action, message


@pytest.mark.parametrize("message", [
    "I don't get it - make it 2 inches taller", "I don't get it: make it 2 inches taller",
    "I don't get it, can you make it 2 in taller", "I don't get it, could you make it 2 in taller",
    "I don't get it so make it taller", "I don't get it — make it taller",
])
def test_a_change_after_a_dash_a_colon_so_or_can_you_is_the_change(designs, message):
    from caliper import chat

    _, stool = designs
    pid = stool.design.parts[0].id
    assert (chat.offline_classify(stool, message, pid).action, chat.offline_classify(stool, message, None).action) == \
        ("refine", "refine"), message


@pytest.mark.parametrize("message", ["I don't get it, make it 2 inches taller", "explain why, and make the legs thicker"])
def test_on_an_empty_design_an_explain_plus_change_has_nothing_to_change(designs, message):
    """It authored parts named `i_don` and `explain_why`."""
    from caliper import chat

    empty, _ = designs
    got = chat.offline_classify(empty, message, None)
    assert got.action == "answer", got
    assert chat.offline_classify(empty, "add a step stool", None).action == "author"      # a new thing still is one


def test_a_renamed_part_s_fix_words_reach_it_with_nothing_selected(tmp_path):
    """reviewer-2 on #209: renamed "Bathroom stool", its card said "add the missing piece to the Bathroom stool", which with
    nothing selected authored `missing_piece`: named_part didn't know labels."""
    from caliper import chat, samples

    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    store.design.part("step_stool").label = "Bathroom stool"           # as the tree's rename sets it
    store.save()
    for phrase in ("add the missing piece to the Bathroom stool", "fix the shape of the bathroom stool to match its pieces"):
        got = chat.offline_classify(store, phrase, None)
        assert (got.action, got.part) == ("refine", "step_stool"), (phrase, got)
    assert chat.named_part("make the bathroom stool taller", ["step_stool"], {"step_stool": "Bathroom stool"}) == "step_stool"
    assert chat.named_part("make the bathroom taller", ["step_stool"], {}) is None


def test_the_part_card_s_fix_words_name_the_part(tmp_path):
    """reviewer-2 on #209: with `pid` dropped at part()'s fix_for, the card said "… to the part" and no test failed."""
    from caliper import answers, design_api
    from caliper.design import DesignStore

    from .test_filled_verdict import FILLED

    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", FILLED, intent="a box step stool")
    lines = answers.part(store, design_api.design_state(store), "stool")
    said = " ".join(ln["text"] for card in lines for ln in card["lines"])
    assert '"add the missing piece to the stool"' in said and "to the part" not in said, said


# --- item 10: releasing a carved part ---------------------------------------------------------------------------------------
def test_a_carved_part_releases_its_carved_print_and_a_source_that_rebuilds(tmp_path, monkeypatch):
    """#70 item 10 (#57): the build book, patterns and print files were never made from a carved part. The print files are the
    carved shape, and the source/ script names a mesh that's in the package, so it builds again."""
    import glob
    import os

    import trimesh

    cq = pytest.importorskip("cadquery")
    from caliper import cutplan, release, shop
    from caliper.assembly import _carved
    from caliper.design import DesignStore

    from .test_mixed import MIXED

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    shop.write({"hand": ["jigsaw", "drill", "circular saw"],
                "machines": [{"id": "printer", "kind": "printer", "volume_mm": [256, 256, 256], "materials": ["pla", "petg"]}]})
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED, intent="a plywood top on printed sides")
    ns: dict = {}
    exec(MIXED, ns)
    window = lambda x0: cq.Workplane().box(22, 100, 120, centered=False).translate((x0, 60, 40))    # noqa: E731
    carved = ns["build"](None).cut(window(-1)).cut(window(279))          # a window out of each printed side
    folder = os.path.join(store.part_dir("stool"), "carved")
    os.makedirs(folder)
    cq.exporters.export(carved, os.path.join(folder, "carved-x-01.stl"), tolerance=0.05)
    store.write_part("stool", MIXED.rstrip("\n") + '\n\n\n# The printed rest as carved by the strength study (CALI-82): '
                     'Caliper builds the part as this mesh.\nCARVED = "carved-x-01.stl"\n', action="carve")
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    stls = glob.glob(os.path.join(root, "printer", "stool", "*.stl"))
    assert stls, os.listdir(root)
    rest = 2 * 20 * 220 * (220 - 12.7) - 2 * 20 * 100 * 120                # the two sides, less their windows
    assert sum(abs(trimesh.load(f, force="mesh").volume) for f in stls) == pytest.approx(rest, rel=0.02)
    (src,) = glob.glob(os.path.join(root, "source", "stool-v*.py"))
    assert os.path.exists(os.path.join(root, "source", "carved", "carved-x-01.stl"))
    assert _carved(src, open(src).read()) is not None                     # it builds from the package alone
    assert "printer/stool/" in open(os.path.join(root, "index.html")).read()


# --- item 20: a 1024 px window --------------------------------------------------------------------------------------------
def test_fit_stands_back_for_a_view_narrower_than_it_is_tall():
    """#70 item 20: fit cropped the stool in a narrow view. Across, the half-angle's tangent is the height's times the aspect."""
    from .test_carve_click import _page, _run

    out = _run(_page(["narrowBy"], extra="out = [narrowBy(1.6), narrowBy(1), narrowBy(0.5), narrowBy(375 / 700)];"))
    assert out[:3] == [1, 1, 2] and out[3] == pytest.approx(700 / 375)


def test_below_1280_px_the_cards_go_under_the_view():
    """#70 item 20: at 1024 px the view was squeezed to about 220 px between the chat and the cards (checked in a browser at
    1024, 800 and 1440 px: the view is 704 px wide at 1024, and the three columns are kept at 1440)."""
    import pathlib

    import caliper

    css = (pathlib.Path(caliper.__file__).parent / "web" / "static" / "design.css").read_text()
    rule = css[css.index("@media (min-width: 701px) and (max-width: 1279px)"):]
    rule = rule[:rule.index("\n}\n")]
    assert ".inspector { grid-column: 2; grid-row: 2;" in rule and ".chat { grid-column: 1; grid-row: 1 / span 2; }" in rule


def test_a_resize_frames_it_again_until_the_camera_is_moved():
    """reviewer-2 on #250: a live resize past square (1024 to 701 px, or a phone turned) left the stool framed for the old aspect, cut
    off at the edge, until fit was pressed. A resize re-frames while the camera is where fit put it; once it's moved, it's left alone."""
    from .test_carve_click import _page, _run

    out = _run(_page(["narrowBy", "frame", "resize", "unfit"], extra="""
let fitted = false, framed = 0;
const viewer = { clientWidth: 400, clientHeight: 800 };
const renderer = { setPixelRatio() {}, setSize() {} };
const camera = { aspect: 1, position: { set() { framed += 1; } }, updateProjectionMatrix() {} };
const controls = { target: { copy() {} }, update() {} };
const v3 = () => ({ length: () => 100 });
const THREE = { Vector3: function () {} };
const contentBox = () => ({ isEmpty: () => false, getCenter: () => ({ x: 0, y: 0, z: 0 }), getSize: () => v3() });
const fitGrid = () => {}; const devicePixelRatio = 1;
frame(); const first = framed;
resize(); const again = framed;
unfit(); resize();
out = { first, again, after: framed, aspect: camera.aspect };
"""))
    assert out == {"first": 1, "again": 2, "after": 2, "aspect": 0.5}
    js = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "controls.addEventListener('start', unfit);" in js


# --- #250 review -----------------------------------------------------------------------------------------------------------
def test_a_cost_goal_on_the_solid_s_share_stays_an_estimate(mixed, monkeypatch):
    """The review: "✓ The goal: $71, within its $71 cap" on the solid's share. It bounds the plastic that stays in the part, not
    what's bought or laid down (supports, brim, purge): a cost goal on it is an estimate until the slicer's figure is in."""
    from caliper import answers, design_api, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    state = design_api.design_state(mixed)
    usd = answers.measured(mixed, state)["cost.usd"]
    _goal(mixed, "cost.usd", round(usd + 0.5, 2))                         # just within its cap
    state = design_api.design_state(mixed)
    now = answers.measured(mixed, state)
    assert now.get("filament.upper")
    (line,) = [ln for ln in answers.held_to(state, now) if "light enough" in ln["text"].lower()]
    assert line["status"] != "ok" and "a guess" in line["text"], line
    assert "the filament is the model's solid share" in line["text"], line
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert check["status"] == "estimate", check
    _goal(mixed, "cost.usd", round(usd - 5, 2))                           # over its cap: an estimate too, either way (#250 review)
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert line["status"] == "warn" and "a guess" in line["text"], line
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert check["status"] == "estimate", check


def test_a_cost_cap_under_the_parts_that_aren_t_printed_is_a_sure_fail(mixed, monkeypatch):
    """The foreman (#250): a sure ✗ only where the wood and bought parts alone are over the cap, and it says so."""
    from caliper import answers, design_api, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(FAILED))
    state = design_api.design_state(mixed)
    now = answers.measured(mixed, state)
    rest = now["cost.usd"] - now["filament.upper_usd"]
    assert 1 < rest < now["cost.usd"] - 1, now                              # some of each
    _goal(mixed, "cost.usd", round(rest - 1, 2))
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert line["status"] == "bad" and "a guess" not in line["text"], line
    assert line["text"].endswith("The parts that aren't printed cost more than that alone, before any filament."), line
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert check["status"] == "fail", check


@pytest.mark.parametrize("message", ["I need them painted", "I need it wider", "I need them sanded smooth"])
def test_on_an_empty_design_an_i_need_statement_has_nothing_to_change(designs, message):
    """The review: "I need them painted" with nothing built authored a part named `i_need`."""
    from caliper import chat

    empty, _ = designs
    assert chat.offline_classify(empty, message, None).action == "answer", message
    assert chat.offline_classify(empty, "I need a bench", None).action == "author"         # a new thing still is one


def test_the_shove_says_what_s_checked_and_what_isn_t():
    """The review and the foreman: the squeeze is the safe side for the sheet; racking isn't checked, the FEA takes the joints as
    solid. Separately, on the card and on the page."""
    from caliper import answers

    from .test_carve_click import _page, _run

    c = {"governs": "buckling", "buckling": [{"piece": "top", "done": True, "safety": 0.5, "down": False}], "fea": {"safety": 9.0}}
    said = answers.fail_hedge({"min_safety": 2.0}, c, {"kind": "fails"}, False)
    assert ("The top folds first, taken as squeezed end to end by a push that doesn't run down it: the safe side for the sheet. "
            "Racking (the frame leaning over at its joints) isn't checked: the FEA takes the joints as solid.") in said, said
    assert "more likely racks" not in said
    out = _run(_page(["foldedBy"], extra="""
const esc = (s) => String(s);
out = foldedBy({ buckling: [{ piece: 'top', done: true, safety: 20.9, down: false, edges_held: 0 }] });
"""))
    assert "taken as a squeeze, the safe side for the sheet" in out and "racking (the frame leaning over at its joints) isn't checked" in out, out
