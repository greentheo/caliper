"""CALI-198 (#327): a part whose script has no loads() is given one in the Scenarios editor, and then says it has one.

Found on reviewer-2's aero walk, on a copy of the camper sample (the hitch cargo box): "Will it hold?" offered only "Say
what it must hold" (a designer call) and no editor. A case added through the editor's route was checked, yet the card
under the ✗ still said "It doesn't say what it must carry yet", with no Check it again and no Lighten.

Theo (quoted in scenarios.py): "every part needs to be able to have … the loading stress specified … correctable, either
with user input as text in the right hand menu"."""

import os

import pytest

from caliper import scenarios as S
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: a lidless box of 1/2 in ply that says what it's built from and nothing of what it must hold
BIN = '''import cadquery as cq

W, D, H, T = 400.0, 300.0, 200.0, 12.7


def build(params):
    out = cq.Workplane().box(W, D, T, centered=False)
    out = out.union(cq.Workplane().box(T, D, H, centered=False))
    return out.union(cq.Workplane().box(T, D, H, centered=False).translate((W - T, 0, 0)))


def construction(params, build=None):
    return [{"name": "floor", "kind": "sheet", "material": "plywood", "thickness": T,
             "outline": [(0, 0, T), (W, 0, T), (W, D, T), (0, D, T)]},
            {"name": "left", "kind": "sheet", "material": "plywood", "thickness": T,
             "outline": [(0, 0, 0), (0, D, 0), (0, D, H), (0, 0, H)]},
            {"name": "right", "kind": "sheet", "material": "plywood", "thickness": T,
             "outline": [(W, 0, 0), (W, D, 0), (W, D, H), (W, 0, H)]}]
'''

#: what the person adds in the editor: two people lying on it, 400 lb
LYING = {"name": "two people lying on it", "amount": 400, "unit": "lb", "direction": [0, 0, -1], "factor": 2.0,
         "lo": [100, 100, 10.7], "hi": [300, 200, 12.7], "on": True}

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a bin", base=str(tmp_path / "designs"))
    s.write_part("bin", BIN, intent="a plywood bin")
    return s


def _part(store, pid="bin"):
    from caliper import design_api

    return next(p for p in design_api.design_state(DesignStore.load(store.root))["parts"] if p["id"] == pid)


def test_a_case_added_in_the_editor_is_what_it_must_hold(store):
    assert not S.says_loads(store, "bin") and not _part(store)["loads"]
    got = S.get(store, "bin")
    assert got["scenarios"] == [] and not got["overridden"]
    S.put(store, "bin", [LYING], got["supports"])
    assert S.says_loads(DesignStore.load(store.root), "bin")
    assert _part(store)["loads"]
    assert [ln["name"] for ln in S.loads(DesignStore.load(store.root), "bin", {})] == ["two people lying on it"]


#: the bin built as a solid block round its pieces: a check of it would analyse the block (CALI-96)
FILLED = BIN.replace('''    out = cq.Workplane().box(W, D, T, centered=False)
    out = out.union(cq.Workplane().box(T, D, H, centered=False))
    return out.union(cq.Workplane().box(T, D, H, centered=False).translate((W - T, 0, 0)))''', '''    return cq.Workplane().box(W, D, H, centered=False)''')


def test_a_solid_filled_round_its_pieces_is_said_once_it_has_a_case(tmp_path):
    """What its strength checks read (``untrusted``) goes with the added case, as with a script's loads()."""
    assert FILLED.count("box(W, D, H") == 1
    s = DesignStore.create("a block", base=str(tmp_path / "designs"))
    s.write_part("bin", FILLED, intent="a plywood bin")
    assert _part(s)["untrusted"] is None
    S.put(s, "bin", [LYING], S.get(s, "bin")["supports"])
    assert _part(s)["untrusted"]


def test_a_script_s_own_loads_still_say_it(tmp_path):
    from .test_scenarios import RATED

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", RATED, intent="a step stool")
    assert S.says_loads(s, "stool") and _part(s, "stool")["loads"]


def test_its_studies_open_once_it_has_a_case(store):
    from caliper import design_api

    def menu():
        state = design_api.design_state(DesignStore.load(store.root))
        return {m["kind"]: m for m in state["studies"]["menu"]["bin"]}

    assert not menu()["load"]["ready"] and "say what it must carry" in menu()["load"]["why"]
    S.put(store, "bin", [LYING], S.get(store, "bin")["supports"])
    assert menu()["load"]["ready"], menu()["load"]


def test_the_build_plan_counts_it_as_unchecked_once_it_has_a_case(store):
    from caliper import build_plan

    assert not build_plan._unheld(store, {"bin": {}})
    S.put(store, "bin", [LYING], S.get(store, "bin")["supports"])
    assert build_plan._unheld(DesignStore.load(store.root), {"bin": {}})


def test_the_check_runs_on_the_added_case_and_the_card_reads_it(store, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import load_study as L

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    S.put(store, "bin", [LYING], S.get(store, "bin")["supports"])
    rec = L.study(DesignStore.load(store.root), "bin")
    assert [c["name"] for c in rec["cases"]] == ["two people lying on it"] and rec["loads_edited"]


# --- the page ----------------------------------------------------------------------------------------------------------
def _page(extra):
    from .test_carve_click import _page as page, _run

    return _run(page(["loadView", "scenariosBox", "scenariosView", "scenarioRow", "supportRow", "pickFromDir", "newLoadBox"],
                     consts=["esc", "SCEN_DIRS", "SCEN_SAID", "xyz"], extra=extra))


def test_a_part_with_no_loads_shows_the_editor_beside_say_what_it_must_hold():
    html = _page("""const S = { design: { aero_available: true }, scenOpen: 'bin',
                                  scen: { bin: { overridden: false, scenarios: [], supports: [{ name: 'the floor', floor: true }] } } };
                    out = loadView({ id: 'bin', loads: false });""")
    assert "Say what it must hold" in html and 'id="lAsk"' in html                  # the designer's way, as before
    assert 'id="scenBox"' in html and 'id="scenAdd"' in html and 'id="scenSave"' in html   # and the person's own
    assert "It doesn't say what it must hold yet: add a scenario below, or tell me" in html
    assert 'id="lGo"' not in html                                                    # nothing to check until there's one


def test_an_empty_editor_says_there_s_none_yet_not_as_its_script_says_them():
    html = _page("""out = scenariosView({ id: 'bin' }, { overridden: false, scenarios: [], supports: [] });""")
    assert "Its script doesn't say what it must hold: add a scenario." in html and "As its script says them" not in html


def test_a_row_added_on_the_page_is_never_as_its_script_says_them():
    """Found on the walk (8016, the camper's cargo box): Add a scenario on the empty editor turned its words to "As its
    script says them", where none is the script's."""
    html = _page("""out = scenariosView({ id: 'bin' }, { overridden: false, supports: [],
                        scenarios: [{ name: 'a new load', amount: 50, unit: 'lb', direction: [0, 0, -1], factor: 1, on: true,
                                      lo: [0, 0, 0], hi: [10, 10, 10] }] });""")
    assert "Its script doesn't say what it must hold" in html and "As its script says them" not in html
    script = _page("""out = scenariosView({ id: 'bin' }, { overridden: false, supports: [],
                        scenarios: [{ name: 'a crate', amount: 50, unit: 'lb', direction: [0, 0, -1], factor: 1, on: true,
                                      lo: [0, 0, 0], hi: [10, 10, 10], of: 'a crate', source: 'script' }] });""")
    assert "As its script says them" in script                       # a script's own rows read as before


def test_the_no_loads_view_is_wired_as_the_full_one():
    src = open(JS).read()
    head = src[src.index("function loadView(p)"):src.index("const runs = loadRuns(p.id);", src.index("function loadView(p)"))]
    assert "${scenariosBox(p)}" in head                                              # wireLoad wires it, either way
    assert "wireScenarios(p);" in src[src.index("function wireLoad(p)"):src.index("function wireLoad(p)") + 400]


def test_the_card_asks_for_a_check_once_it_has_a_case_not_for_what_it_must_hold(store):
    from caliper import answers, design_api

    def work():
        s = DesignStore.load(store.root)
        card = next(c for c in answers.part(s, design_api.design_state(s), "bin") if c["key"] == "work")
        return [ln["text"] for ln in card["lines"]]

    assert any("say what it has to hold" in t for t in work())
    S.put(store, "bin", [LYING], S.get(store, "bin")["supports"])
    assert "Not checked yet: check it when it looks right." in work() and not any("has to hold" in t for t in work())


#: the bin with a loads() of its own, as it was before the designer took it out
LOADED = BIN + '''

def loads(params, build=None):
    return [{"name": "a crate in it", "lb": 100, "factor": 2.0, "lo": (150, 100, 10.7), "hi": (250, 200, 12.7)}]
'''


def test_an_edit_whose_case_the_design_dropped_is_still_what_it_must_hold(tmp_path):
    """The check still reads an edit whose case the script no longer has (#312: said, and asked), so the part still says
    what it must hold when a revise takes its loads() out."""
    s = DesignStore.create("a bin", base=str(tmp_path / "designs"))
    s.write_part("bin", LOADED, intent="a plywood bin")
    got = S.get(s, "bin")
    S.put(s, "bin", [{**got["scenarios"][0], "amount": 150}], got["supports"])
    s = DesignStore.load(s.root)
    s.write_part("bin", BIN, intent="a plywood bin")                      # the designer's revise, without loads()
    s = DesignStore.load(s.root)
    assert [ld["name"] for ld in S.loads(s, "bin", {})] == ["a crate in it"]   # what its check reads
    assert S.says_loads(s, "bin") and _part(s)["loads"]


# --- the scorecard and the release (#337 review) -----------------------------------------------------------------------
def _card(store, monkeypatch, through=2):
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper import scorecard

    monkeypatch.setattr(L, "VOXELS_THROUGH", through)
    return scorecard.compute(DesignStore.load(store.root))


def _strength(card):
    return [c for c in card["checks"] if str(c.get("metric", "")).startswith("strength") and c.get("status") != "proposed"]


def test_the_scorecard_holds_a_part_to_a_case_added_in_the_editor(store, monkeypatch):
    """reviewer-2 at 4f3a372: the cargo box with a 400 lb case added read ✗ on its card, but the scorecard had no strength
    check for it, so a release could read ready over a ✗ (CALI-113: a part that says what it must hold is held to it)."""
    assert not _strength(_card(store, monkeypatch))                    # it says nothing: nothing to hold it to
    S.put(store, "bin", [{**LYING, "amount": 40000}], S.get(store, "bin")["supports"])
    card = _card(store, monkeypatch)
    (check,) = _strength(card)
    assert check["status"] == "fail", check
    assert "strength.bin.safety" in card["metrics"]


#: a block that says it's only its floor: no joints to check, so a light case passes and only "not trusted" holds it back
SLAB = """import cadquery as cq


def build(params):
    return cq.Workplane().box(400.0, 300.0, 200.0, centered=False)


def construction(params, build=None):
    return [{"name": "floor", "kind": "sheet", "material": "plywood", "thickness": 12.7,
             "outline": [(0, 0, 12.7), (400, 0, 12.7), (400, 300, 12.7), (0, 300, 12.7)]}]
"""


def test_a_solid_filled_round_its_pieces_isn_t_trusted_once_it_has_a_case(tmp_path, monkeypatch):
    """The scorecard's "not trusted" reads the same parts as its strength check: one with a case added counts. A pass on
    the block is no pass (a ✗ stays a ✗, so the case is reviewer-2's 1 lb one)."""
    s = DesignStore.create("a block", base=str(tmp_path / "designs"))
    s.write_part("bin", SLAB, intent="a plywood bin")
    S.put(s, "bin", [{**LYING, "amount": 1}], S.get(s, "bin")["supports"])
    from caliper import consistency, load_study as L

    monkeypatch.setattr(L, "FILLED_NOTE", None)                        # only the part's own reading, not the run's
    card = _card(s, monkeypatch)
    assert consistency.filled(DesignStore.load(s.root), "bin")
    assert [c["status"] for c in _strength(card)] == ["untrusted"], [(c.get("metric"), c["status"]) for c in _strength(card)]


def test_a_picture_cut_from_a_part_with_a_case_is_checked_again():
    """reviewer-2: "Put a picture on it" read only the script's loads(), so the added case went unchecked after the cut."""
    import inspect

    from caliper import pictures

    src = inspect.getsource(pictures)
    assert "has_loads = says_loads(store, part_id, script)" in src and '"def loads(" in script' not in src


#: the floor alone, as built as declared: no joints, not filled, so a light case passes and is the scorecard's to qualify
FLOOR = SLAB.replace("box(400.0, 300.0, 200.0, centered=False)", "box(400.0, 300.0, 12.7, centered=False)")


def test_the_scorecard_asks_whether_a_part_with_a_case_was_checked_in_the_middle_only(tmp_path, monkeypatch):
    """CALI-94's middle-only edge is asked of the same parts as the strength check: one with a case added counts. Whether a
    top is two-sided is consistency.bare_edge's (test_edge_foot); here it's whether the scorecard asks it."""
    from caliper import consistency

    s = DesignStore.create("a floor", base=str(tmp_path / "designs"))
    s.write_part("bin", FLOOR, intent="a plywood floor")
    S.put(s, "bin", [{**LYING, "amount": 1}], S.get(s, "bin")["supports"])
    assert [c["status"] for c in _strength(_card(s, monkeypatch, 4))] == ["pass"]       # fine enough to see its 12.7 mm
    asked = []
    monkeypatch.setattr(consistency, "bare_edge", lambda store, pid: asked.append(pid) or consistency.MIDDLE_ONLY)
    assert [c["status"] for c in _strength(_card(s, monkeypatch, 4))] == ["edge"] and asked == ["bin"]


def test_the_first_case_added_starts_on_the_part_s_top_face_so_it_saves(store):
    """reviewer-2 at 4f3a372: Add a scenario began a 10 mm box at the origin, and Save refused it: "'a new load' doesn't
    touch the part: it pushes on thin air, 453.6 mm from its nearest surface". The bin is open-topped: the middle of its
    box's top is air, its wall tops aren't."""
    import json

    from .test_carve_click import _page as page, _run

    bbox = _part(store)["bbox"]
    box = _run(page(["newLoadBox"], extra=f"out = newLoadBox({{ bbox: {json.dumps(bbox)} }});"))
    assert box["hi"][2] == pytest.approx(bbox["max"][2]) and box["lo"][2] == pytest.approx(bbox["max"][2] - 2)
    assert box["lo"][:2] == pytest.approx(bbox["min"][:2], abs=0.05) and box["hi"][:2] == pytest.approx(bbox["max"][:2], abs=0.05)
    row = {"name": "a new load", "amount": 50, "unit": "lb", "direction": [0, 0, -1], "factor": 1, "on": True, **box}
    S.put(store, "bin", [row], S.get(store, "bin")["supports"])                  # saves: it touches the part
    assert [ln["name"] for ln in S.loads(DesignStore.load(store.root), "bin", {})] == ["a new load"]
    assert _run(page(["newLoadBox"], extra="out = newLoadBox({});")) == {"lo": [0, 0, 0], "hi": [10, 10, 10]}


def test_saved_cases_on_a_part_whose_script_says_none_never_read_as_the_rest_its_script_s():
    """reviewer-2: once saved, "Yours where you edited them; the rest as its script says them", where there's no rest."""
    row = """{ name: 'two people', amount: 400, unit: 'lb', direction: [0, 0, -1], factor: 2, on: true,
              lo: [0, 0, 0], hi: [10, 10, 10] }"""
    saved = _page(f"out = scenariosView({{ id: 'bin' }}, {{ overridden: true, supports: [], scenarios: [{row}] }});")
    assert "Its script doesn't say what it must hold: these are yours, and what it's checked against." in saved
    assert "the rest as its script says them" not in saved
    edited = _page(f"""out = scenariosView({{ id: 'bin' }}, {{ overridden: true, supports: [],
                        scenarios: [{{ ...{row}, source: 'script' }}] }});""")
    assert "Yours where you edited them; the rest as its script says them" in edited      # a script's own, edited


def test_add_a_scenario_starts_from_the_part_s_top_where_there_s_no_row_to_copy():
    from .test_carve_click import _fn

    wire = _fn(open(JS).read(), "wireScenarios")
    assert "const box = last.lo ? { lo: last.lo, hi: last.hi } : newLoadBox(p);" in wire and "[10, 10, 10]" not in wire
