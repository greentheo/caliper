"""CALI-185 (#296) slice A: a part's scenarios (its strength loads) and supports as data in design.yaml, read in place of
its script's ``loads()`` and ``HELD``.

Theo, 2026-11-14: "I can click on 'show the stress' on every one of the 3 scenarios (and I probably should be able to edit
the scenarios or add new ones)"; "every part needs to be able to have the static 'doesn't move' fix point, and the loading
stress specified … it should be correctable, either with user input as text in the right hand menu …"; and on a
standard's case: "lowered, default to the standard, allow it to be edited".
"""

import json

import numpy as np
import pytest

from caliper import scenarios as S
from caliper.design import DesignStore

from .test_joint_check import STEP_ON_SIDES

pytest.importorskip("cadquery")

#: The step stool, with a standard's case beside its own.
RATED = STEP_ON_SIDES.replace('''    return [{"name": "stepping on the front edge", "lb": 250, "factor": 2.0,
             "lo": (w / 2 - 50, 0, h - 2), "hi": (w / 2 + 50, 100, h)}]''',
                              '''    return [{"name": "stepping on the front edge", "lb": 250, "factor": 2.0,
             "lo": (w / 2 - 50, 0, h - 2), "hi": (w / 2 + 50, 100, h)},
            {"name": "its rating (EN 14183, 150 kg)", "kg": 150, "factor": 1.0,
             "lo": (20, 20, h - 2), "hi": (w - 20, 335, h)},
            {"name": "leaning off the edge", "tip": True, "force": (20, 0, -600), "factor": 1.0,
             "lo": (w / 2 - 10, 0, h - 2), "hi": (w / 2 + 10, 20, h)}]''')


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", RATED, intent="a step stool")
    return s


def test_with_no_override_the_script_s_loads_and_supports_are_read_as_they_are(store):
    from caliper import construction as C
    from caliper import load_study as L

    got = S.get(store, "stool")
    assert not got["overridden"]
    assert [sc["name"] for sc in got["scenarios"]] == ["stepping on the front edge", "its rating (EN 14183, 150 kg)"]
    declared = C.declared(store, "stool")
    strength = [ld for ld in declared["loads"] if not ld.get("tip")]
    assert S.loads(store, "stool", declared) == strength                       # the very same items: byte for byte
    assert S.held(store, "stool", declared) == declared.get("held")
    assert L.parse_loads(S.loads(store, "stool", declared)) == L.parse_loads(strength)


def test_an_override_round_trips_through_design_yaml(store):
    got = S.get(store, "stool")
    rows = got["scenarios"]
    rows[0] = {**rows[0], "amount": 300, "direction": [0.6, 0.0, -0.8]}
    rows.append({"name": "a 50 lb box on the step", "amount": 50, "unit": "lb", "factor": 1.0, "on": True,
                 "direction": [0, 0, -1], "lo": [150, 150, 404.4], "hi": [250, 250, 406.4]})
    S.put(store, "stool", rows, got["supports"])
    again = S.get(DesignStore.load(store.root), "stool")
    assert again["overridden"]
    assert [sc["name"] for sc in again["scenarios"]] == ["stepping on the front edge", "its rating (EN 14183, 150 kg)",
                                                        "a 50 lb box on the step"]
    assert again["scenarios"][0]["amount"] == 300 and again["scenarios"][0]["direction"] == pytest.approx([0.6, 0.0, -0.8])
    raw = open(store.root + "/design.yaml").read()
    assert "scenarios:" in raw and "a 50 lb box on the step" in raw


def test_a_sideways_scenario_changes_the_force_and_the_joints_modes(store):
    from caliper import construction as C
    from caliper import joint_check as JC
    from caliper import load_study as L

    from .test_joint_check import _pieces

    got = S.get(store, "stool")
    down = L.parse_loads(S.loads(store, "stool", C.declared(store, "stool")))[0]
    rows = got["scenarios"]
    rows[0] = {**rows[0], "direction": [0.0, -1.0, 0.0]}                          # pushed toward the front, not down
    S.put(store, "stool", rows, got["supports"])
    side = L.parse_loads(S.loads(store, "stool", C.declared(store, "stool")))[0]
    assert side["force"] == pytest.approx([0.0, -float(np.linalg.norm(down["force"])), 0.0])
    pieces, tol, held = _pieces(store)
    su = JC.setup(store, "stool")
    before = {tuple(r["pieces"]): r["mode"] for r in JC.check(su, down, held, 2.0)["rows"]}
    after = {tuple(r["pieces"]): r["mode"] for r in JC.check(su, side, held, 2.0)["rows"]}
    assert before[("left side", "step")] == "bearing" and after[("left side", "step")] == "shear"


def test_an_edit_makes_the_part_s_checks_out_of_date(store):
    v = store.design.part("stool").version
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 200}], got["supports"])
    fresh = DesignStore.load(store.root)
    assert fresh.design.part("stool").version == v + 1                          # every run of it reads "older version"
    last = fresh.history("stool")[-1]
    assert last["kind"] == "revision" and last["action"] == "loads"
    assert fresh.read_script("stool") == RATED                                   # the script is the same
    S.clear(fresh, "stool")                                                      # and back to the script's: another
    assert DesignStore.load(store.root).design.part("stool").version == v + 2
    assert not S.get(DesignStore.load(store.root), "stool")["overridden"]


def test_an_edited_standard_case_never_says_it_meets_the_standard_and_back_to_it_does(store):
    from caliper import construction as C

    got = S.get(store, "stool")
    rating = got["scenarios"][1]
    assert rating["standard"]["name"] == "its rating (EN 14183, 150 kg)" and rating["amount"] == 150 and rating["unit"] == "kg"
    S.put(store, "stool", [got["scenarios"][0], {**rating, "amount": 100}], got["supports"])
    names = [ld["name"] for ld in S.loads(store, "stool", C.declared(store, "stool"))]
    assert names[1] == "EN 14183, edited: 100 kg (the standard is 150 kg)"
    assert not any("its rating" in n or "meets EN 14183" in n for n in names)
    edited = S.get(store, "stool")["scenarios"][1]
    S.put(store, "stool", [got["scenarios"][0], S.standard(edited)], got["supports"])   # back to the standard
    assert [ld["name"] for ld in S.loads(store, "stool", C.declared(store, "stool"))][1] == "its rating (EN 14183, 150 kg)"


def test_a_case_turned_off_isn_t_checked_and_says_so(store):
    from caliper import construction as C

    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "on": False}], got["supports"])
    assert [ld["name"] for ld in S.loads(store, "stool", C.declared(store, "stool"))] == ["stepping on the front edge"]
    assert S.off(store, "stool") == ["its rating (EN 14183, 150 kg)"]


@pytest.mark.parametrize("row,said", [
    ({"amount": 0}, "more than nothing"),
    ({"factor": 0}, "more than nothing"),
    ({"name": " "}, "a name"),
    ({"direction": [0, 0, 0]}, "which way"),
    ({"lo": [5000, 5000, 5000], "hi": [5100, 5100, 5100]}, "doesn't touch the part"),
    ({"unit": "stone"}, "lb, kg or N"),
])
def test_a_row_it_can_t_act_on_is_refused_in_words_and_nothing_is_written(store, row, said):
    got = S.get(store, "stool")
    v = store.design.part("stool").version
    with pytest.raises(ValueError, match=said):
        S.put(store, "stool", [{**got["scenarios"][0], **row}], got["supports"])
    assert DesignStore.load(store.root).design.part("stool").version == v and not S.get(store, "stool")["overridden"]


def test_supports_override_what_holds_it(store):
    from caliper import construction as C
    from caliper import load_study as L

    got = S.get(store, "stool")
    assert got["supports"] == [S.FLOOR]                                         # the floor at the underside, as now
    wall = {"name": "screwed to the wall", "lo": [0, 345, 200], "hi": [406.4, 356, 400]}
    S.put(store, "stool", got["scenarios"], [wall])
    held = S.held(store, "stool", C.declared(store, "stool"))
    assert held == [wall] and L.parse_held(held, [[0, 0, 0], [406.4, 355.6, 406.4]], 1.0)[0]["name"] == "screwed to the wall"
    with pytest.raises(ValueError, match="doesn't touch the part"):
        S.put(store, "stool", got["scenarios"], [{"name": "a hook in the air", "lo": [0, 0, 900], "hi": [1, 1, 901]}])


# --- the API -----------------------------------------------------------------------------------------------------------
@pytest.fixture
def api(store, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(store.root.rsplit("/", 1)[0]))
    return TestClient(create_app()), store.design.slug


def test_the_routes_read_write_and_clear_a_part_s_scenarios(api, store):
    c, slug = api
    got = c.get(f"/api/designs/{slug}/parts/stool/scenarios").json()
    assert not got["overridden"] and len(got["scenarios"]) == 2
    rows = got["scenarios"]
    rows[0]["amount"] = 275
    put = c.put(f"/api/designs/{slug}/parts/stool/scenarios", json={"scenarios": rows, "supports": got["supports"]})
    assert put.status_code == 200, put.text
    assert put.json()["design"]["parts"][0]["version"] == 2
    bad = c.put(f"/api/designs/{slug}/parts/stool/scenarios",
                json={"scenarios": [{**rows[0], "amount": 0}], "supports": got["supports"]})
    assert bad.status_code == 422 and "more than nothing" in bad.json()["detail"]
    back = c.delete(f"/api/designs/{slug}/parts/stool/scenarios")
    assert back.status_code == 200 and not c.get(f"/api/designs/{slug}/parts/stool/scenarios").json()["overridden"]


def test_a_case_turned_off_is_said_on_the_card_a_standard_s_in_amber():
    from caliper import answers

    lines = answers.off_lines({"loads_off": ["its rating (EN 14183, 150 kg)", "a box on the step"]})
    assert [(ln["text"], ln["status"]) for ln in lines] == [
        ("Not checked: its rating (EN 14183, 150 kg) is turned off.", "warn"),
        ("Not checked: a box on the step is turned off.", "info")]


def test_a_check_s_record_says_its_loads_were_edited_and_which_are_off(store, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import load_study as L

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "on": False}], got["supports"])
    rec = L.study(store, "stool")
    assert rec["loads_edited"] and rec["loads_off"] == ["its rating (EN 14183, 150 kg)"]
    assert [c["name"] for c in rec["cases"]] == ["stepping on the front edge"]
    assert rec["version"] == store.design.part("stool").version


# --- the page ----------------------------------------------------------------------------------------------------------
def _page(extra):
    from .test_carve_click import _page as page, _run

    return _run(page(["dirFromPick", "pickFromDir", "scenarioRow", "supportRow", "scenariosView"],
                     consts=["esc", "SCEN_DIRS", "SCEN_SAID", "xyz"], extra=extra))


def test_a_direction_round_trips_through_the_picker():
    out = _page("""out = [dirFromPick('down'), dirFromPick('front'), dirFromPick('angle', 30, 90),
      pickFromDir([0, 0, -1]), pickFromDir([0, 1, 0]), pickFromDir(dirFromPick('angle', 20, 45))];""")
    assert out[0] == [0, 0, -1] and out[1] == [0, -1, 0]
    assert out[2] == pytest.approx([0.5, 0.0, -0.866025], abs=1e-5)                     # 30° from down, toward the right
    assert out[3] == {"kind": "down"} and out[4] == {"kind": "back"}
    assert out[5] == {"kind": "angle", "deg": 20, "heading": 45}


def test_the_editor_shows_each_row_and_a_standard_s_way_back():
    rating = {"name": "EN 14183, edited: 100 kg (the standard is 150 kg)", "amount": 100, "unit": "kg",
              "direction": [0, 0, -1], "factor": 1, "lo": [20, 20, 404.4], "hi": [386, 335, 406.4], "on": True,
              "standard": {"name": "its rating (EN 14183, 150 kg)", "amount": 150, "unit": "kg"}}
    html = _page(f"""out = scenariosView({{id: 'stool'}}, {{overridden: true, scenarios: [{json.dumps(rating)}],
      supports: [{{name: 'the floor', floor: true}}, {{name: 'the wall', lo: [0, 345, 200], hi: [406, 356, 400]}}]}});""")
    assert "the standard is 150 kg" in html and 'data-scen-std="0"' in html and "Back to the standard" in html
    assert "the floor at its underside" in html and 'value="the wall"' in html
    assert "Back to its script" in html and "Saving makes a new version of stool" in html
    plain = _page("""out = scenariosView({id: 'stool'}, {overridden: false, scenarios: [], supports: []});""")
    assert "Back to its script" not in plain and "As its script says them" in plain


def test_the_editor_is_wired_to_the_routes():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "api('PUT', `/api/designs/${S.slug}/parts/${p.id}/scenarios`, readScenarios(got))" in src
    assert "api('DELETE', `/api/designs/${S.slug}/parts/${p.id}/scenarios`)" in src
    assert "api('GET', `/api/designs/${S.slug}/parts/${p.id}/scenarios`)" in src
    assert "${scenariosBox(p)}" in src and "wireScenarios(p);" in src
