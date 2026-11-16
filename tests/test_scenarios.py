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
    wall = {"name": "screwed to the wall", "lo": [0, 345, 200], "hi": [406.4, 356, 400]}
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "on": False}], got["supports"] + [wall])
    rec = L.study(store, "stool")
    assert rec["loads_edited"] and rec["loads_off"] == ["its rating (EN 14183, 150 kg)"]
    assert [c["name"] for c in rec["cases"]] == ["stepping on the front edge"]
    assert rec["version"] == store.design.part("stool").version
    assert "screwed to the wall" in [h["name"] for h in rec["held"]]                 # its supports, as edited
    from caliper import answers, design_api

    work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
    texts = [ln["text"] for ln in work["lines"]]                                   # "Will it work?"
    assert "Not checked: its rating (EN 14183, 150 kg) is turned off." in texts, texts     # on the card


# --- the page ----------------------------------------------------------------------------------------------------------
def _page(extra):
    from .test_carve_click import _page as page, _run

    return _run(page(["dirFromPick", "pickFromDir", "scenarioRow", "supportRow", "scenariosView", "keptXyz", "keptDir"],
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


def test_each_row_says_the_name_its_checks_use_and_a_standard_s_can_t_be_retyped(store):
    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "amount": 100}], got["supports"])
    rows = S.get(store, "stool")["scenarios"]
    assert rows[1]["said"] == "EN 14183, edited: 100 kg (the standard is 150 kg)" and rows[0]["said"] == rows[0]["name"]
    html = _page(f"""out = scenarioRow({json.dumps(rows[1])}, 1);""")
    assert 'data-f="name" value="EN 14183, edited: 100 kg (the standard is 150 kg)" readonly' in html, html
    src = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "src", "caliper", "web", "static",
                                         "design.js")).read()
    assert "name: was.standard ? was.name : f('name').value.trim()" in src                 # its own name, kept


def test_every_scenario_turned_off_is_refused(store):
    got = S.get(store, "stool")
    with pytest.raises(ValueError, match="turn at least one scenario on"):
        S.put(store, "stool", [{**sc, "on": False} for sc in got["scenarios"]], got["supports"])


def test_a_field_left_as_it_was_keeps_its_exact_value():
    """Saving rounded the corners to 0.1 mm (19.05 to 19.1), so a standard's case put back read as edited."""
    out = _page("""out = [xyz([19.05, 387.35, 152.39999999999998]),
      keptXyz([19.05, 387.35, 152.39999999999998], '19.05, 387.35, 152.4'),
      keptXyz([19.05, 387.35, 152.4], '19.05, 390, 152.4'),
      keptDir([0.287, 0, -0.958], 'angle', pickFromDir([0.287, 0, -0.958]).deg, pickFromDir([0.287, 0, -0.958]).heading),
      keptDir([0.287, 0, -0.958], 'down', 0, 0)];""".replace("_page", "_page"))
    assert out[0] == "19.05, 387.35, 152.4"
    assert out[1] == [19.05, 387.35, 152.39999999999998]                              # untouched: exactly as it was
    assert out[2] == [19.05, 390, 152.4]                                              # touched: what was typed
    assert out[3] == [0.287, 0, -0.958]                                               # the angle shown, left alone
    assert out[4] == [0, 0, -1]


# --- #312 review -------------------------------------------------------------------------------------------------------------
TALLER = RATED.replace('"h": 406.4', '"h": 450.0')


def _lowered(store):
    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "amount": 100}], got["supports"])
    return got


def test_a_version_carries_its_loads_and_a_restore_puts_them_back(store):
    import os

    v0 = store.design.part("stool").version
    _lowered(store)
    v1 = store.design.part("stool").version
    assert os.path.exists(os.path.join(store.version_dir("stool", v1), "scenarios.yaml"))
    assert not os.path.exists(os.path.join(store.version_dir("stool", v0), "scenarios.yaml"))   # the script's
    store.restore("stool", v0)
    assert not S.get(DesignStore.load(store.root), "stool")["overridden"]               # its loads undone too
    store.restore("stool", v1)
    assert S.get(DesignStore.load(store.root), "stool")["scenarios"][1]["amount"] == 100


def test_roll_it_back_says_its_loads_are_undone(store):
    from caliper import chat

    _lowered(store)
    got = chat.revert_part(store, "stool")
    assert "its loads are the script's again" in got.reply and "EN 14183, edited: 100 kg" in got.reply, got.reply
    assert not S.get(DesignStore.load(store.root), "stool")["overridden"]
    back = chat.revert_part(DesignStore.load(store.root), "stool", to=2)
    assert "its loads are as they were at v2" in back.reply, back.reply


def test_rows_never_moved_follow_the_script_s_box_by_name(store):
    from caliper import construction as C

    got = _lowered(store)                                                            # boxes untouched: amounts only
    store.write_part("stool", TALLER, intent="taller")
    loads = S.loads(store, "stool", C.declared(store, "stool"))
    assert loads[0]["lo"][2] == pytest.approx(448.0) and loads[1]["lo"][2] == pytest.approx(448.0)   # on the new top
    assert loads[1]["name"].startswith("EN 14183, edited: 100 kg")
    assert S.drift(store, "stool") == ""                                             # nothing to say: they followed


def test_a_moved_row_stays_where_it_was_put_and_the_reply_names_it(store):
    from caliper import chat

    got = S.get(store, "stool")
    moved = {**got["scenarios"][0], "lo": [150, 150, 404.4], "hi": [250, 250, 406.4]}
    S.put(store, "stool", [moved, got["scenarios"][1]], got["supports"])
    store.write_part("stool", TALLER, intent="taller")
    said = S.drift(store, "stool")
    assert "'stepping on the front edge' doesn't touch it any more" in said and "move it" in said, said
    assert "its rating" not in said                                                  # the unmoved one followed
    assert chat.drift_note(store, "stool") == said


def test_the_floor_beside_another_support_is_kept(store):
    from caliper import construction as C
    from caliper import load_study as L

    got = S.get(store, "stool")
    clamp = {"name": "a clamp at the back foot", "lo": [0, 345, 0], "hi": [40, 356, 40]}
    S.put(store, "stool", got["scenarios"], [S.FLOOR, clamp])
    held = L.parse_held(S.held(store, "stool", C.declared(store, "stool")), [[0, 0, 0], [406.4, 355.6, 406.4]], 1.0)
    assert [h["name"] for h in held] == ["a clamp at the back foot", "the floor"]       # never dropped


def test_the_scorecard_says_a_scenario_turned_off(store, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper import scorecard

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], "on": False}], got["supports"])
    L.study(store, "stool")
    card = scorecard.compute(DesignStore.load(store.root))
    m = card["metrics"]["strength.stool.safety"]
    assert "its rating (EN 14183, 150 kg) is turned off" in (m.get("note") or ""), m
    (check,) = [c for c in card["checks"] if c.get("metric") == "strength.safety"]      # the line the page shows (#312)
    assert "its rating (EN 14183, 150 kg) is turned off" in check["loads"] and check["loads"] in check["note"], check


def test_a_row_s_standard_is_never_taken_from_the_request(store):
    from caliper import construction as C

    got = S.get(store, "stool")
    forged = {**got["scenarios"][1], "amount": 100, "standard": {**got["scenarios"][1]["standard"], "amount": 100}}
    S.put(store, "stool", [got["scenarios"][0], forged], got["supports"])
    assert S.loads(store, "stool", C.declared(store, "stool"))[1]["name"] == "EN 14183, edited: 100 kg (the standard is 150 kg)"


def test_back_to_the_script_with_nothing_edited_writes_nothing(store):
    v = store.design.part("stool").version
    assert S.clear(store, "stool") == v and DesignStore.load(store.root).design.part("stool").version == v


def test_history_says_what_changed(store):
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, {**got["scenarios"][1], "on": False}], got["supports"])
    said = DesignStore.load(store.root).history("stool")[-1]["feedback"]
    assert "stepping on the front edge: 250 → 260 lb" in said and "its rating (EN 14183, 150 kg): off" in said, said


def test_a_mirror_s_loads_are_its_source_s(tmp_path):
    from caliper import mirror

    s = DesignStore.create("a pair", base=str(tmp_path / "designs"))
    s.write_part("stool", RATED, intent="a step stool")
    mirror.make(s, "stool_m", "stool")
    with pytest.raises(ValueError, match="stool_m mirrors stool: edit stool's loads"):
        S.put(s, "stool_m", S.get(s, "stool")["scenarios"], [S.FLOOR])


def test_the_routes_refuse_while_a_job_works_on_the_part(api, monkeypatch):
    from caliper import design_api
    from fastapi import HTTPException

    c, slug = api

    def busy(slug_, parts):
        raise HTTPException(409, "stool is being checked: wait for it, or stop that first.")

    monkeypatch.setattr(design_api, "_refuse_while_busy", busy)
    got = c.get(f"/api/designs/{slug}/parts/stool/scenarios").json()
    r = c.put(f"/api/designs/{slug}/parts/stool/scenarios", json={"scenarios": got["scenarios"], "supports": got["supports"]})
    assert r.status_code == 409 and "being checked" in r.json()["detail"]


def test_setting_a_number_that_leaves_a_moved_load_behind_says_so(store):
    from caliper import params

    got = S.get(store, "stool")
    moved = {**got["scenarios"][0], "lo": [150, 150, 404.4], "hi": [250, 250, 406.4]}
    S.put(store, "stool", [moved, got["scenarios"][1]], got["supports"])
    said = params.set_value(store, "stool", "h", 450, None)["said"]
    assert "'stepping on the front edge' doesn't touch it any more" in said, said


def test_the_card_says_a_moved_load_its_shape_left_behind_and_a_checked_part_isn_t_called_unchecked(store, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import answers, design_api
    from caliper import load_study as L

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "lo": [150, 150, 404.4], "hi": [250, 250, 406.4]}, got["scenarios"][1]],
          got["supports"])
    L.study(store, "stool")
    work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
    texts = [ln["text"] for ln in work["lines"]]
    assert "Not checked yet: check it when it looks right." not in texts, texts       # checked: never called unchecked
    store.write_part("stool", TALLER, intent="taller")
    work = next(c for c in answers.part(store, design_api.design_state(store), "stool") if c["key"] == "work")
    assert any("'stepping on the front edge' doesn't touch it any more" in ln["text"] for ln in work["lines"])


def test_a_turn_that_writes_the_part_ends_with_what_its_loads_did(store, monkeypatch):
    from caliper import chat

    got = _lowered(store)                                                            # v2, edited
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, got["scenarios"][1]], got["supports"])   # v3
    monkeypatch.setattr(chat, "drift_note", lambda s, pid: "THE LOADS NOTE" if pid == "stool" else "")
    got = chat.turn(store, "roll it back", scope="stool", use_llm=False)
    assert got.reply.rstrip().endswith("THE LOADS NOTE"), got.reply


# --- #312 re-check: every reader of a part's loads reads the loads its check reads; the override is edits on the script

MIDDLE = {"lo": [150, 150, 404.4], "hi": [250, 250, 406.4]}


def _edge_taken(store, how):
    got = S.get(store, "stool")
    front, rating = got["scenarios"]
    rows = {"removed": [rating], "off": [{**front, "on": False}, rating], "middle": [{**front, **MIDDLE}, rating]}[how]
    S.put(store, "stool", rows, got["supports"])

#: The same stool without its rails: its step is held on its two sides only, so its front edge is where it's weakest.
#: Its tipping case stays, at the front edge, as Theo's step-stool-3 has one: it's no foot there (#314).
OPEN = RATED.replace('"front rail": ((t, 0, h - t - r), (w - t, t, h - t)), '
                     '"back rail": ((t, d - t, h - t - r), (w - t, d, h - t)),\n            ', "") \
    .replace('            "front rail": [(t, 0, h - t - r), (w - t, 0, h - t - r), (w - t, 0, h - t), (t, 0, h - t)],\n'
             '            "back rail": [(t, d, h - t - r), (w - t, d, h - t - r), (w - t, d, h - t), (t, d, h - t)],\n', "")


@pytest.mark.parametrize("how", ["removed", "off", "middle"])
def test_an_edge_case_an_edit_takes_away_is_warned_of_as_the_script_s_would_be(tmp_path, how):
    """The reviewer's step-stool edits: the front edge removed, turned off, or moved to the middle. The warning read the
    script's loads, which still stood there, so the card said nothing and a ✓ counted as one."""
    from caliper import answers, consistency, design_api

    assert "front rail" not in OPEN and "back rail" not in OPEN and '"leaning off the edge", "tip": True' in OPEN
    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", OPEN, intent="a step stool")
    assert consistency.bare_edge(store, "stool") is None
    _edge_taken(store, how)
    fresh = DesignStore.load(store.root)
    edge = consistency.bare_edge(fresh, "stool")
    assert edge and "no load stands on its free edge" in edge, edge
    lines = [ln["text"] for c in answers.part(fresh, design_api.design_state(fresh), "stool") for ln in c["lines"]]
    assert any("no load stands on its free edge" in t for t in lines), lines
    S.clear(fresh, "stool")
    assert consistency.bare_edge(DesignStore.load(store.root), "stool") is None       # the script's again: no warning


def test_a_seat_s_unchecked_cases_read_the_edited_loads(tmp_path):
    from caliper import answers, design_api, tipping

    store = DesignStore.create("a stool to sit on", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a stool to sit on")
    assert "sitting on the front edge" not in tipping.unchecked(S.declared(store, "stool"), "a stool to sit on")
    _edge_taken(store, "removed")
    fresh = DesignStore.load(store.root)
    assert "sitting on the front edge" in tipping.unchecked(S.declared(fresh, "stool"), "a stool to sit on")
    work = next(c for c in answers.part(fresh, design_api.design_state(fresh), "stool") if c["key"] == "work")
    seat = [ln["text"] for ln in work["lines"] if ln["text"].startswith("Not checked yet for a seat")]
    assert seat and "sitting on the front edge" in seat[0], seat


def test_the_edited_declarations_keep_the_script_s_tipping_cases_and_take_its_supports(store):
    from caliper import construction as C

    assert S.declared(store, "stool") == C.declared(store, "stool")                  # nothing edited: the script's
    _edge_taken(store, "removed")
    d = S.declared(store, "stool")
    assert [ld["name"] for ld in d["loads"]] == ["its rating (EN 14183, 150 kg)", "leaning off the edge"]
    assert d["loads"][-1]["tip"] and len(d["loads"]) == 2


REFINED = RATED.replace('''{"name": "stepping on the front edge", "lb": 250,''', '''{"name": "standing on the front edge", "lb": 300,''') \
    .replace('''            {"name": "leaning off the edge",''', '''            {"name": "kneeling on the step", "lb": 200, "factor": 2.0,
             "lo": (150, 150, h - 2), "hi": (250, 250, h)},
            {"name": "leaning off the edge",''')


def test_the_reviewer_s_refine_checks_the_design_s_new_cases_and_keeps_the_edit_and_says_so(store):
    """The rating edited to 100 kg; then the design is refined: 300 lb standing on the renamed front edge, a new
    kneeling case. The override replaced the script's loads, so neither was checked and nothing was said."""
    from caliper import chat
    from caliper import construction as C

    _lowered(store)
    store.write_part("stool", REFINED, intent="refined")
    loads = {ld["name"]: ld for ld in S.loads(store, "stool", C.declared(store, "stool"))}
    assert set(loads) == {"standing on the front edge", "kneeling on the step",
                          "EN 14183, edited: 100 kg (the standard is 150 kg)"}, set(loads)
    assert np.linalg.norm(loads["standing on the front edge"]["force"]) == pytest.approx(300 * 4.4482216, rel=1e-3)
    said = S.drift(store, "stool")
    assert "the design added 'standing on the front edge': it's checked" in said, said
    assert "the design added 'kneeling on the step': it's checked" in said, said
    assert "yours kept: EN 14183, edited: 100 kg" in said, said
    assert chat.drift_note(store, "stool") == said
    got = S.get(store, "stool")
    assert [r["source"] for r in got["scenarios"]] == ["script", "edited", "script"]


def test_an_edit_the_design_changed_underneath_is_asked_about(store):
    from caliper import construction as C

    _lowered(store)
    store.write_part("stool", RATED.replace('"kg": 150', '"kg": 200'), intent="a heavier rating")
    said = S.drift(store, "stool")
    assert ("you'd edited 'its rating (EN 14183, 150 kg)' to 100 kg; the design now asks 200 kg: checked at the design's "
            "200 kg until you choose; yours is 100 kg: keep yours, or take the design's?") in said, said
    row = S.get(store, "stool")["scenarios"][1]
    assert row["conflict"] and row["design"]["amount"] == 200 and row["amount"] == 100
    amounts = sorted(round(float(np.linalg.norm(ld["force"]))) for ld in S.loads(store, "stool", C.declared(store, "stool")))
    assert round(200 * 9.80665) in amounts and round(100 * 9.80665) not in amounts   # the more demanding, till chosen
    got = S.get(store, "stool")                                                  # take the design's: the script's again
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], **{k: row["design"][k] for k in
                                                ("amount", "unit", "factor", "direction", "lo", "hi", "name")}}],
          got["supports"])
    assert not S.get(store, "stool")["scenarios"][1].get("conflict") and S.drift(store, "stool") == ""


def test_an_edit_whose_case_the_design_dropped_is_still_read_and_named(store):
    _lowered(store)
    gone = RATED.replace('''            {"name": "its rating (EN 14183, 150 kg)", "kg": 150, "factor": 1.0,
             "lo": (20, 20, h - 2), "hi": (w - 20, 335, h)},
''', "")
    store.write_part("stool", gone, intent="no rating")
    said = S.drift(store, "stool")
    assert ("you'd edited 'its rating (EN 14183, 150 kg)'; the design no longer has it: yours is still checked until you "
            "choose: keep yours, or remove it?") in said, said


def test_after_a_refine_get_shows_the_followed_box_and_an_untouched_save_leaves_it_unmoved(store):
    from caliper import construction as C

    _lowered(store)
    store.write_part("stool", TALLER, intent="taller")
    got = S.get(store, "stool")
    assert [r["lo"][2] for r in got["scenarios"]] == pytest.approx([448.0, 448.0])
    S.put(store, "stool", got["scenarios"], got["supports"])                     # saved as shown
    store.write_part("stool", RATED, intent="back down")
    loads = S.loads(store, "stool", C.declared(store, "stool"))
    assert [ld["lo"][2] for ld in loads] == pytest.approx([404.4, 404.4])         # still followed: never moved


def test_a_standard_moved_only_is_said_as_moved(store):
    got = S.get(store, "stool")
    S.put(store, "stool", [got["scenarios"][0], {**got["scenarios"][1], **MIDDLE}], got["supports"])
    assert S.get(store, "stool")["scenarios"][1]["said"].startswith("EN 14183, moved"), S.get(store, "stool")


def test_a_restore_says_in_its_history_what_it_did_to_the_loads(store):
    v0 = store.design.part("stool").version
    _lowered(store)
    v1 = store.design.part("stool").version
    store.restore("stool", v0)
    assert DesignStore.load(store.root).history("stool")[-1]["feedback"].startswith(
        "its loads are the script's again (undone: EN 14183, edited: 100 kg")
    store.restore("stool", v1)
    assert DesignStore.load(store.root).history("stool")[-1]["feedback"] == f"its loads are as they were at v{v1}"


def test_the_editor_asks_about_a_case_the_design_changed_and_takes_the_design_s():
    mine = {"name": "its rating (EN 14183, 150 kg)", "said": "EN 14183, edited: 100 kg (the standard is 200 kg)",
            "amount": 100, "unit": "kg", "direction": [0, 0, -1], "factor": 1, "lo": [20, 20, 404.4],
            "hi": [386, 335, 406.4], "on": True, "of": "its rating (EN 14183, 150 kg)", "source": "edited",
            "conflict": "you'd edited 'its rating (EN 14183, 150 kg)' to 100 kg; the design now asks 200 kg",
            "design": {"name": "its rating (EN 14183, 150 kg)", "amount": 200, "unit": "kg", "direction": [0, 0, -1],
                       "factor": 1, "lo": [20, 20, 404.4], "hi": [386, 335, 406.4], "on": True}}
    added = {**mine, "name": "kneeling on the step", "said": "kneeling on the step", "amount": 200, "unit": "lb",
             "source": "script", "new": True, "conflict": None, "design": None, "of": "kneeling on the step"}
    gone = {**mine, "conflict": "you'd edited 'the old edge'; the design no longer has it", "design": None}
    html = _page(f"""out = scenariosView({{id: 'stool'}}, {{overridden: true, scenarios: {json.dumps([mine, added, gone])},
      supports: []}});""")
    assert "the design now asks 200 kg." in html and 'data-scen-take="0"' in html and "Take the design's" in html
    assert "the design added this case since you edited them" in html and "its script's" in html
    assert "the design no longer has it." in html and 'data-scen-keep="2"' in html and 'data-scen-take="2"' not in html
    assert "Yours where you edited them" in html
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "S.scen[p.id].scenarios[i] = { ...sc.design, of: sc.of, source: 'script' }; repaint();" in src
    assert "S.scen[p.id].scenarios[+b.dataset.scenKeep].keep = true; repaint();" in src             # Keep mine, wired


# --- #312 third round: an open conflict checks the more demanding, and a Save settles only what was acted on ----------

RAISED = RATED.replace('"lb": 250,', '"lb": 300,')                  # the design now asks 300 lb on the front edge
LOWERED = RATED.replace('"lb": 250,', '"lb": 200,')                 # ... or 200 lb


def _front_at(store, lb, **more):
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": lb, **more}, got["scenarios"][1]], got["supports"])


def _front_forces(store):
    from caliper import construction as C

    return {ld["name"]: round(float(np.linalg.norm(ld["force"])) / 4.4482216, 1)
            for ld in S.loads(store, "stool", C.declared(store, "stool")) if "front edge" in ld["name"]}


def test_an_open_conflict_where_the_design_rose_checks_the_design_s_and_says_so(store):
    _front_at(store, 260)
    store.write_part("stool", RAISED, intent="it has to hold 300 lb standing on the front edge")
    assert _front_forces(store) == {"stepping on the front edge": 300.0}
    said = S.drift(store, "stool")
    assert ("you'd edited 'stepping on the front edge' to 260 lb; the design now asks 300 lb: checked at the design's "
            "300 lb until you choose; yours is 260 lb: keep yours, or take the design's?") in said, said
    assert not said.endswith("?.") and said.endswith("?"), said
    row = S.get(store, "stool")["scenarios"][0]
    assert row["amount"] == 260 and row["checked"] == "checked at the design's 300 lb until you choose; yours is 260 lb"
    assert S.asked(store, "stool") == [said[said.index("you'd edited"):-len(": keep yours, or take the design's?")]]


def test_an_open_conflict_where_the_design_fell_checks_yours(store):
    _front_at(store, 260)
    store.write_part("stool", LOWERED, intent="lighter")
    assert _front_forces(store) == {"stepping on the front edge": 260.0}
    assert "checked at yours, 260 lb, until you choose; the design's is 200 lb" in S.drift(store, "stool")


def test_an_open_conflict_on_a_row_turned_off_checks_the_design_s(store):
    _front_at(store, 250, on=False)
    store.write_part("stool", LOWERED, intent="lighter")                           # the design's 200 lb, against yours off
    assert _front_forces(store) == {"stepping on the front edge": 200.0}
    assert "checked at the design's 200 lb until you choose; yours is off" in S.drift(store, "stool")


def test_an_open_conflict_that_doesn_t_order_checks_both_under_their_own_names(store):
    _front_at(store, 260, lo=[150, 150, 404.4], hi=[250, 250, 406.4])            # moved, and the design raised it
    store.write_part("stool", RAISED, intent="heavier")
    assert _front_forces(store) == {"stepping on the front edge (yours)": 260.0,
                                    "stepping on the front edge (the design's)": 300.0}
    assert "both checked until you choose" in S.drift(store, "stool")


def test_a_save_settles_only_the_conflicts_acted_on_and_names_the_rest(store):
    from caliper import construction as C

    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, {**got["scenarios"][1], "amount": 100}], got["supports"])
    store.write_part("stool", RAISED.replace('"kg": 150', '"kg": 200'), intent="heavier all round")
    assert len(S.asked(store, "stool")) == 2
    rows = S.get(store, "stool")["scenarios"]
    S.put(store, "stool", [rows[0], {**rows[1], "factor": 1.5}], got["supports"])   # an unrelated change: both stay open
    assert len(S.asked(store, "stool")) == 2
    assert S.drift(store, "stool").count("keep yours, or take the design's?") == 2      # still asked, the design unchanged
    said = DesignStore.load(store.root).history("stool")[-1]["feedback"]
    assert "still open:" in said and "stepping on the front edge" in said and "its rating" in said, said
    rows = S.get(store, "stool")["scenarios"]
    S.put(store, "stool", [rows[0], {**rows[1], "keep": True}], got["supports"])     # Keep mine, on the rating only
    asked = S.asked(store, "stool")
    assert len(asked) == 1 and asked[0].startswith("you'd edited 'stepping on the front edge'"), asked
    kg = sorted(round(float(np.linalg.norm(ld["force"])) / 9.80665)
                for ld in S.loads(store, "stool", C.declared(store, "stool")) if "front edge" not in ld["name"])
    assert kg == [100]                                                               # yours, kept: no longer asked
    assert not S.get(store, "stool")["scenarios"][1].get("conflict")


def test_keep_mine_on_a_dropped_case_keeps_it_as_one_added(store):
    _lowered(store)
    gone = RATED.replace('''            {"name": "its rating (EN 14183, 150 kg)", "kg": 150, "factor": 1.0,
             "lo": (20, 20, h - 2), "hi": (w - 20, 335, h)},
''', "")
    store.write_part("stool", gone, intent="no rating")
    rows = S.get(store, "stool")["scenarios"]
    S.put(store, "stool", [rows[0], {**rows[1], "keep": True}], S.get(store, "stool")["supports"])
    assert S.asked(store, "stool") == [] and S.get(store, "stool")["scenarios"][1]["source"] == "added"


def test_taking_the_design_s_for_the_only_edit_leaves_no_override(store):
    _front_at(store, 260)
    store.write_part("stool", RAISED, intent="heavier")
    got = S.get(store, "stool")
    design = got["scenarios"][0]["design"]
    S.put(store, "stool", [{**design, "of": got["scenarios"][0]["of"]}, got["scenarios"][1]], got["supports"])
    again = S.get(store, "stool")
    assert not again["overridden"] and S.asked(store, "stool") == []


def test_the_scorecard_and_the_release_say_an_open_conflict(store, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import load_study as L
    from caliper import release, scorecard

    monkeypatch.setattr(L, "VOXELS_THROUGH", 2)
    _front_at(store, 260)
    store.write_part("stool", RAISED, intent="heavier")
    L.study(store, "stool")
    fresh = DesignStore.load(store.root)
    monkeypatch.setattr(L, "unresolved", lambda run, c: False)     # a run fine enough: only the question is open
    card = scorecard.compute(fresh)
    m = card["metrics"]["strength.stool.safety"]
    assert "an open question about its loads: you'd edited 'stepping on the front edge' to 260 lb" in (m.get("note") or ""), m
    assert m["trust"] == "question open", m
    (check,) = [c for c in card["checks"] if c.get("metric") == "strength.safety"]      # the line the page shows (#312)
    assert check["trust"] == "question open", check
    assert "an open question about its loads: you'd edited 'stepping on the front edge' to 260 lb" in check["loads"], check
    assert check["loads"] in check["note"] and card["metrics"]["strength.safety"]["trust"] == "question open"
    from caliper import verdicts

    real = verdicts.goal

    def braced(*a, **kw):                                            # a verdict resting on joints nothing checks (#265)
        got = real(*a, **kw)
        return {**got, "joints": True, "brace": {"joints_n": 2, "wood": True}, "why": "joints not checked"} \
            if got["kind"] in ("holds", "fails") else got

    with monkeypatch.context() as mp:                                # the question's label wins over the joints' one
        mp.setattr(verdicts, "goal", braced)
        (check,) = [c for c in scorecard.compute(fresh)["checks"] if c.get("metric") == "strength.safety"]
        assert check["trust"] == "question open" and check["joints"], check
    with monkeypatch.context() as mp:                                # the same run with no question open: a model's
        mp.setattr(S, "asked", lambda store, pid: [])
        again = scorecard.compute(fresh)
        assert again["metrics"]["strength.stool.safety"]["trust"] == "model"
        (check,) = [c for c in again["checks"] if c.get("metric") == "strength.safety"]
        assert check["trust"] != "question open" and not check.get("loads"), check
    asked = release._loads_asked(fresh, ["stool"])
    assert asked == {"stool": S.asked(fresh, "stool")}
    html = "".join(release.asked_html({"loads_asked": asked}))
    assert "stool: an open question about its loads" in html and "checked at the design&#x27;s 300 lb" in html, html
    book = release.book({"id": "r1", "created": 0, "design": "a stool", "versions": {"stool": 1}, "loads_asked": asked},
                        {"summary": {"pass": 0, "fail": 0, "unknown": 1}, "checks": [], "metrics": {}},
                        {"usd": 0, "groups": [], "basis": ""}, {}, [], [])
    assert "stool: an open question about its loads" in book                     # in the book itself
    import inspect

    assert '"loads_asked": _loads_asked(store, list(versions)),' in inspect.getsource(release)   # and in its record


def test_the_editor_offers_keep_mine_beside_take_the_design_s():
    mine = {"name": "stepping on the front edge", "said": "stepping on the front edge", "amount": 260, "unit": "lb",
            "direction": [0, 0, -1], "factor": 2, "lo": [0, 0, 0], "hi": [1, 1, 1], "on": True,
            "of": "stepping on the front edge", "source": "edited",
            "conflict": "you'd edited 'stepping on the front edge' to 260 lb; the design now asks 300 lb",
            "checked": "checked at the design's 300 lb until you choose; yours is 260 lb",
            "design": {"name": "stepping on the front edge", "amount": 300, "unit": "lb", "direction": [0, 0, -1],
                       "factor": 2, "lo": [0, 0, 0], "hi": [1, 1, 1], "on": True}}
    html = _page(f"""out = scenariosView({{id: 'stool'}}, {{overridden: true, scenarios: {json.dumps([mine, {**mine, "keep": True}])},
      supports: []}});""")
    assert 'data-scen-take="0"' in html and 'data-scen-keep="0"' in html and "Keep mine" in html
    assert "checked at the design&#39;s 300 lb until you choose" in html or "checked at the design's 300 lb until you choose" in html
    assert "or save to keep yours" not in html and "yours, kept when you save" in html and 'data-scen-keep="1"' not in html


# --- the guard, as an ast walk (#312 third round): reviewer-2's ten readers -------------------------------------------

def _readers(src: str, path: str) -> list:
    """Each read of a part's ``loads`` that isn't the edited loads its check reads, in ``src`` (a file at ``path``): a
    ``["loads"]`` or ``.get("loads")`` on anything but a check's ``ctx``, a part state's has-loads flag (``p``) or a run;
    an ``.id == "loads_edge"`` outside consistency.py; a ``tipping.unchecked(`` not fed ``scenarios.declared``. A line
    may say which it means and why (``# script's loads:``, ``# edited:``). Only ``prepare`` is exempt in load_study."""
    import ast
    import os

    edited, marks = {"ctx", "p", "run"}, ("# script's loads", "# edited:")

    def root(n):
        while isinstance(n, (ast.Subscript, ast.Attribute, ast.Call)):
            n = n.func if isinstance(n, ast.Call) else n.value
        return n.id if isinstance(n, ast.Name) else None

    tree, lines, base = ast.parse(src), src.splitlines(), os.path.basename(path)
    bound = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "declared"
             for t in n.targets if isinstance(t, ast.Name)}               # a name holding declarations: never the check's
    edited = edited - bound
    skip = {id(x) for n in ast.walk(tree) if base == "load_study.py" and isinstance(n, ast.FunctionDef)
            and n.name == "prepare" for x in ast.walk(n)}
    out = []
    for n in ast.walk(tree):
        why = None
        if id(n) in skip:
            continue
        if (isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)          # a read, not a store into it
                and isinstance(n.slice, ast.Constant) and n.slice.value == "loads"):
            why = root(n.value) not in edited and "reads loads"
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and n.args
              and isinstance(n.args[0], ast.Constant) and n.args[0].value == "loads"):
            why = root(n.func.value) not in edited and "reads loads"
        elif isinstance(n, ast.Compare) and base != "consistency.py":
            ops = [n.left, *n.comparators]
            why = (any(isinstance(x, ast.Constant) and x.value == "loads_edge" for o in ops for x in ast.walk(o))
                   and any(isinstance(o, ast.Attribute) and o.attr == "id" for o in ops)) and "the script's edge row"
        elif (isinstance(n, ast.Call) and base != "tipping.py"
              and ((isinstance(n.func, ast.Attribute) and n.func.attr == "unchecked" and root(n.func) == "tipping")
                   or (isinstance(n.func, ast.Name) and n.func.id == "unchecked"))):
            a = n.args[0] if n.args else None
            why = not (isinstance(a, ast.Call) and isinstance(a.func, ast.Attribute) and a.func.attr == "declared"
                       and isinstance(a.func.value, ast.Name) and a.func.value.id in ("SC", "scenarios")) \
                and "a seat's cases not fed scenarios.declared"
        if why and not any(m in lines[n.lineno - 1] for m in marks):
            out.append(f"{base}:{n.lineno}: {why}: {lines[n.lineno - 1].strip()}")
    return out


def test_nothing_reads_a_script_s_loads_but_the_check_and_the_marked_few():
    """A guard: a reader of ``loads`` off a part's declarations reads the script's, not what its check reads (#312
    re-check; an ast walk since its third round, as reviewer-2 found a line pattern let most new readers through)."""
    import glob
    import os

    src = os.path.join(os.path.dirname(__file__), "..", "src", "caliper")
    bad = [h for path in glob.glob(os.path.join(src, "**", "*.py"), recursive=True)
           if os.path.basename(path) != "scenarios.py" for h in _readers(open(path).read(), path)]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("path, src", [
    ("new.py", 'x = C.declared(store, pid)["loads"]'),
    ("new.py", 'dec = C.declared(store, pid)\nx = dec["loads"]'),
    ("new.py", "x = declared.get('loads')"),
    ("new.py", 'x = construction.declared(store, pid).get("loads")'),
    ("new.py", 'x = L.parse_loads(spec["loads"])'),
    ("new.py", 'x = tipping.unchecked(construction.declared(store, pid), "")'),
    ("new.py", 'x = [r for r in said if r.id=="loads_edge"]'),
    ("load_study.py", 'def listing(declared):\n    return declared["loads"]'),
    ("new.py", 'x = declared["loads"]'),                                         # the two the line pattern caught
    ("new.py", 'x = d.get("loads")'),
])
def test_the_guard_catches_each_way_reviewer_2_wrote_a_new_reader(path, src):
    assert _readers(src, path), src


@pytest.mark.parametrize("path, src", [
    ("new.py", 'x = ctx["loads"][0]'),                                           # a check's own: the edited loads
    ("new.py", 'c["loads"] = words'),                                            # a store into a dict, not a read
    ("new.py", 'x = p.get("loads") and p.get("built")'),                         # a part state's has-loads flag
    ("load_study.py", 'def prepare(store, pid):\n    return declared["loads"]'),  # where the script's are read in
    ("new.py", 'x = declared["loads"]   # script\'s loads: the drawing of its script'),
    ("new.py", "x = tipping.unchecked(SC.declared(store, pid), '')"),
])
def test_the_guard_lets_the_check_s_own_and_the_marked_through(path, src):
    assert not _readers(src, path), src



# --- #312 fourth round: _demand's unit and margin, an untouched Save, the guard's last realistic gaps ---------------

def test_a_conflict_in_another_unit_orders_by_the_force(store):
    _front_at(store, 150, unit="kg")                                                 # 330.7 lb
    store.write_part("stool", RAISED, intent="heavier")                              # the design: 300 lb
    assert _front_forces(store) == {"stepping on the front edge": 330.7}
    assert "checked at yours, 150 kg, until you choose; the design's is 300 lb" in S.drift(store, "stool")


def test_a_conflict_orders_by_the_margin_too(store):
    _front_at(store, 260)                                                            # 260 lb × 2: 520
    store.write_part("stool", RATED.replace('"lb": 250, "factor": 2.0,', '"lb": 300, "factor": 1.5,'), intent="less margin")
    assert _front_forces(store) == {"stepping on the front edge": 260.0}               # yours: 300 × 1.5 is 450
    assert "checked at yours, 260 lb, until you choose; the design's is 300 lb" in S.drift(store, "stool")


def test_a_save_with_nothing_changed_writes_nothing(store):
    v = store.design.part("stool").version
    got = S.get(store, "stool")
    assert S.put(store, "stool", got["scenarios"], got["supports"]) == v               # the script's, as they were
    _lowered(store)
    v = store.design.part("stool").version
    n = len(DesignStore.load(store.root).history("stool"))
    got = S.get(store, "stool")
    assert S.put(store, "stool", got["scenarios"], got["supports"]) == v               # the edits, as they were
    assert store.design.part("stool").version == v and len(DesignStore.load(store.root).history("stool")) == n


@pytest.mark.parametrize("path, src", [
    ("new.py", 'p = C.declared(store, pid)\nx = p.get("loads")'),
    ("new.py", 'ctx = C.declared(store, pid)\nx = ctx["loads"]'),
    ("new.py", 'run = construction.declared(store, pid)\nx = run["loads"]'),
    ("new.py", 'from .tipping import unchecked\nx = unchecked(C.declared(store, pid), "")'),
    ("new.py", 'x = [r for r in said if r.id in ("loads_edge",)]'),
])
def test_the_guard_catches_the_names_it_lets_through_when_they_hold_declarations(path, src):
    assert _readers(src, path), src


def test_the_page_says_the_strength_line_s_loads_and_its_trust():
    from .test_carve_click import _page, _run

    html = _run(_page(["scoreView", "scoreMark", "scoreNum", "safetyNum", "asOf"], consts=["esc", "TRUST", "goalLimit"],
                      extra="""out = scoreView({parts: [], scorecards: [{created: 0, summary: {pass: 1, fail: 0},
      objectives: [], checks: [{id: 'strength_loads', label: 'holds what its loads say', metric: 'strength.safety',
        status: 'pass', value: 3.1, unit: '×', limit: 2, op: '>=', trust: 'question open',
        loads: "an open question about its loads: you'd edited 'x' to 260 lb"}]}]});"""))
    assert "question open" in html and "an open question about its loads: you'd edited 'x' to 260 lb" in html, html
