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

    return _run(page(["loadView", "scenariosBox", "scenariosView", "scenarioRow", "supportRow", "pickFromDir"],
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
