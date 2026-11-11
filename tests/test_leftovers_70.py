"""CALI-92 (#70) — the leftovers: the items main still had after the triage of 2026-11-10."""
import json
import os
import re
import subprocess

import pytest

from .test_carve_click import _fn, _node
from .test_small_words import _js

#: partView's neighbours, stubbed: only its heading and its Advanced line are under test.
STUBS = """const S = { design: { rules: [], in_air: { yes: false } } };
const len = (x) => String(x);
const ruleItem = () => '', historyItem = () => '', loadView = () => '', trialView = () => '', frameView = () => '',
  aeroView = () => '', whittleView = () => '', aeroRuns = () => [], runsFor = () => [], buildView = () => '',
  makingView = () => '', patternView = () => '', cutplanView = () => '', paramView = () => '';
function cardsView(c) { return c.what; }
"""


def _part(**kw):
    return {"id": "step_stool", "name": "Step stool", "version": 3, "scripted": True, "origin": None, "rules": [],
            "history": [], "bbox": None, "role": "design", **kw}


@pytest.mark.parametrize("kw,word", [({}, "parametric"), ({"scripted": False}, "imported"),
                                     ({"origin": "whittled"}, "whittled mesh")])
def test_the_part_view_heading_is_the_part_s_own_name(kw, word):
    """Item 21: no internal id or `parametric` badge in the top line; both are one click down, under Advanced."""
    html = _js(["partView"], f"return partView({_part(**kw)!r});".replace("None", "null").replace("True", "true")
               .replace("False", "false"), STUBS)
    heading = re.search(r"<h2>(.*?)</h2>", html, re.S).group(1)
    assert heading.strip() == "Step stool"
    advanced = re.search(r"<summary>(.*?)</summary>", html, re.S).group(1)
    assert "step_stool" in advanced and word in advanced


def _bar(kind, run_v, part_v, index=2):
    head = f"""const S = {{ design: {{ parts: [{{ id: 'stool', version: {part_v} }}] }} }};
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {{}};
const holdsHere = () => true;
"""
    return _js(["stationAction"], f"return stationAction('stool', {{ kind: '{kind}', version: {run_v} }}, {index}, {{}});", head)


@pytest.mark.parametrize("kind,again", [("lighten", "lighten it again"), ("carve", "carve it again")])
def test_a_stale_run_s_preview_doesn_t_offer_the_cut(kind, again):
    """Item 24: a Lighten of v3 previewed on v4 offered "Cut these holes", which the server then refused."""
    html = _bar(kind, 3, 4)
    assert "adoptBtn" not in html and again in html and "v3" in html and "v4" in html
    assert "adoptBtn" in _bar(kind, 4, 4)                      # the current version's step is still offered


def test_a_study_the_server_doesn_t_version_still_offers_its_step():
    assert "adoptBtn" in _bar("parametric", 3, 4) and "adoptBtn" in _bar("frame", 3, 4)


API = """globalThis.window = {};
globalThis.fetch = async (url) => ({ ok: false, status: +url, json: async () => ({ detail: 'said ' + url }) });
"""


def test_a_409_is_marked_a_refusal_and_a_500_isn_t():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    script = API + _fn(src, "api") + """
(async () => {
  const out = {};
  for (const code of [409, 500]) { try { await api('POST', String(code)); } catch (e) { out[code] = !!e.refused; } }
  out.marked = Object.keys(window.__refused || {});
  console.log(JSON.stringify(out));
})();"""
    got = json.loads(subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30).stdout)
    assert got == {"409": True, "500": False, "marked": ["said 409"]}


def _errbar(msg, refused):
    html = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "index.html")).read()
    show = re.search(r"function showErr\(msg\) \{.*?\n    \}\n", html, re.S).group(0)
    script = """class El { constructor() { this.children = []; this.dataset = {}; this.classList = { on: new Set(),
  toggle: (c, v) => (v ? this.classList.on.add(c) : this.classList.on.delete(c)) }; }
  append(c) { this.children.push(c); } }
const bar = new El();
globalThis.window = globalThis; window.__err = []; globalThis.__err = window.__err;
globalThis.document = { getElementById: () => bar, createElement: () => new El() };
""" + f"window.__refused = {json.dumps({msg: True} if refused else {})};\n" + show + f"""
showErr({json.dumps(msg)});
console.log(JSON.stringify({{ text: bar.textContent, plain: bar.classList.on.has('plain'),
  report: bar.children.some((c) => c.textContent === 'Report it…') }}));"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_refusal_shows_as_a_plain_line_with_no_report_link():
    """Item 24: the 409 went to the red bar with **Report it…**, as if it were a crash."""
    said = "this lightening is of version 3 and the part is at version 4: lighten it again"
    assert _errbar(said, True) == {"text": said + " ", "plain": True, "report": False}
    assert _errbar("boom", False) == {"text": "⚠ boom ", "plain": False, "report": True}


# --- item 23: one filament number -----------------------------------------------------------------------------------------
from caliper import making  # noqa: E402


def _rep(g=1122.0, lb=4.0):
    return {"mass_lb": lb, "bom": {"sheets": [], "printed": [{"name": "sides", "material": "petg", "label": "PETG",
                                                              "filament_g": g}]}}


@pytest.mark.parametrize("trust,said", [("model", "the slicer's estimate"), ("rough", "a rough guess")])
def test_the_filament_is_the_making_plan_s_and_the_weight_goes_with_it(trust, said):
    """Item 23: the buy card said 1122 g (the model's solid) and the shop panel 726 g (the slicer's), for one print."""
    got = making.filament(_rep(), {"printed": [{"name": "sides", "filament_g": 726, "trust": trust}]})
    g = got["bom"]["printed"][0]
    assert (g["filament_g"], g["filament_from"]) == (726, said)
    assert got["mass_lb"] == round(4.0 - 396 / 1000 * 2.20462, 1)


@pytest.mark.parametrize("mk", [None, {"printed": []}, {"printed": [{"name": "sides", "filament_g": None, "pending": True}]}])
def test_with_no_number_from_the_plan_it_s_the_solid_s_share_and_says_so(mk):
    got = making.filament(_rep(), mk)
    assert got["bom"]["printed"][0]["filament_g"] == 1122.0 and got["mass_lb"] == 4.0
    assert got["bom"]["printed"][0]["filament_from"] == "by the model's solid"


SLICED = {"hours": 3.0, "filament_g": 300.0, "usd": 7.5, "trust": "model", "from": "PrusaSlicer"}


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    """The plywood top on printed sides, with a slicer that says 300 g a piece."""
    from caliper import printing, shop
    from caliper.design import DesignStore

    from .test_mixed import MIXED

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    shop.write({"hand": ["drill", "jigsaw"], "machines": [{"id": "printer", "kind": "printer", "volume_mm": [400, 400, 400],
                                                           "materials": ["pla", "petg"]}]})
    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(SLICED))
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    store = DesignStore.create("a side table", base=str(tmp_path / "designs"), slug="table")
    store.write_part("table", MIXED, intent="a plywood top on printed sides")
    return store


def test_the_buy_card_the_shop_panel_and_the_weight_say_one_number(mixed):
    from caliper import answers, design_api
    from caliper import construction as C

    mk = making.plan(mixed, "table", wait=False)
    grams = sum(pr["filament_g"] for pr in mk["printed"])
    model = C.report(mixed, "table")
    assert grams != round(model["bom"]["printed"][0]["filament_g"])          # the two the walk saw differ
    cards = {c["key"]: c for c in answers.part(mixed, design_api.design_state(mixed), "table")}
    buy = cards["buy"]["lines"]
    assert f"{grams:.0f} g of PETG filament (the slicer's estimate)" in buy[0]["text"]
    lb = making.filament(model, mk)["mass_lb"]
    assert lb != model["mass_lb"] and any(f"It weighs {lb:g} lb" in ln["text"] for ln in buy)
    assert answers.measured(mixed, design_api.design_state(mixed))["weight.total_lb"] == lb


def test_the_cost_goes_by_the_same_grams(mixed):
    from caliper import answers
    from caliper import construction as C

    model = C.report(mixed, "table")
    one = making.filament(model, making.plan(mixed, "table", wait=False))
    assert answers._cost(mixed, "table", one) < answers._cost(mixed, "table", model)    # 300 g, under the model's


def test_the_scorecard_weighs_and_prices_by_the_same_grams(mixed):
    from caliper import scorecard

    one = making.filament(__import__("caliper.construction", fromlist=["report"]).report(mixed, "table"),
                          making.plan(mixed, "table"))
    card = scorecard.compute(mixed)
    assert card["metrics"]["weight.table"]["value"] == one["mass_lb"]
    grams = one["bom"]["printed"][0]["filament_g"]
    assert any(ln["item"].startswith(f"{grams:.0f} g of ") and ln["from"] == "the slicer's estimate"
               for ln in scorecard.cost_and_waste(mixed, {"table": {**one, "pieces_raw": []}}, {})["lines"])


def test_the_built_from_panel_says_the_same_grams(mixed):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    got = TestClient(create_app()).get("/api/designs/table/parts/table/construction").json()
    g = got["bom"]["printed"][0]
    grams = sum(pr["filament_g"] for pr in making.plan(mixed, "table", wait=False)["printed"])
    assert (g["filament_g"], g["filament_from"]) == (grams, "the slicer's estimate")


# --- #237 rework ----------------------------------------------------------------------------------------------------------
def test_the_design_s_weight_goes_by_the_filament_its_tongue_and_cog_by_the_solid(mixed):
    """Rework 1: one weight. The scorecard's total is the parts' weights by their one filament figure, with the payload;
    the tongue, the moment and the CG stay on the solid (the study of where it sits isn't by filament)."""
    from caliper import construction as C
    from caliper import scorecard

    one = making.filament(C.report(mixed, "table"), making.plan(mixed, "table"))
    b = C.balance(mixed, payload_lb=0)
    card = scorecard.compute(mixed)
    total = card["metrics"]["weight.total_lb"]["value"]
    assert total == round(b["mass_lb"] + one["filament_more_kg"] * C.M.LB_KG, 1) != b["mass_lb"]
    assert card["metrics"]["hitch.tongue_lb"]["value"] == b["mass_lb"]


def _goal(store, metric, limit):
    from caliper import goals

    goals.write(store, {"checks": [{"id": "g", "label": "light enough", "metric": metric, "op": "<=", "limit": limit,
                                    "source": "answered"}]})


@pytest.mark.parametrize("metric,limit", [("weight.total_lb", 100), ("cost.usd", 1000)])
def test_a_weight_or_cost_goal_on_a_rough_figure_is_an_estimate(mixed, monkeypatch, metric, limit):
    """Rework 2: the rough figure has no supports in it, so an overhanging part reads light: never a ✓ on it."""
    from caliper import answers, design_api, printing, scorecard

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: {**SLICED, "trust": "rough", "from": "walls + infill at rough speeds (no slicer installed)"})
    _goal(mixed, metric, limit)
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert line["status"] == "warn" and "a guess" in line["text"] and "✓" not in line["text"]
    (check,) = [c for c in scorecard.compute(mixed)["checks"] if c.get("id") == "g"]
    assert check["status"] != "pass" and check["trust"] == "rough"
    _goal(mixed, metric, limit)                                       # the slicer's own figure is no guess
    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(SLICED))
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert "a guess" not in line["text"]


def test_a_weight_goal_while_it_s_still_slicing_says_so(mixed, monkeypatch):
    """Rework 5: no false red from the solid's figure while the slicer's still at it."""
    from caliper import answers, design_api, printing

    monkeypatch.setattr(printing, "estimate", lambda *a, **k: dict(printing.WORKING))
    _goal(mixed, "weight.total_lb", 0.1)                              # the solid's weight would fail this
    state = design_api.design_state(mixed)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(mixed, state)) if "light enough" in ln["text"].lower()]
    assert line["status"] == "info" and line.get("working") and "still slicing" in line["text"]


@pytest.mark.parametrize("body", [None, {"build": {}}])
def test_the_panel_has_the_one_figure_tried_or_not_with_its_mass(mixed, body):
    """Rework 3: ``{build: {}}`` is the part as it is, so it gets the figure too; and its kilograms agree with its pounds."""
    from fastapi.testclient import TestClient

    from caliper import construction as C
    from caliper.server import create_app

    c = TestClient(create_app())
    url = "/api/designs/table/parts/table/construction"
    got = (c.get(url) if body is None else c.post(url, json=body)).json()
    assert got["bom"]["printed"][0]["filament_from"] == "the slicer's estimate"
    assert got["mass_lb"] == round(got["mass_kg"] * C.M.LB_KG, 1)
    assert got["mass_kg"] != C.report(mixed, "table")["mass_kg"]


def test_a_bug_s_key_error_is_a_crash_and_a_refusal_is_a_409(mixed, monkeypatch):
    """Rework 6: a 409 shows as a plain line with no Report it (item 24), so a KeyError from a bug mustn't become one."""
    from fastapi.testclient import TestClient

    from caliper import construction as C
    from caliper import errors
    from caliper.server import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    url = "/api/designs/table/parts/table/construction"
    monkeypatch.setattr(C, "report", lambda *a, **k: {}["mass_lb"])
    assert c.get(url).status_code == 500
    monkeypatch.setattr(C, "report", lambda *a, **k: (_ for _ in ()).throw(errors.Refused("the script has no BUILD dict")))
    got = c.get(url)
    assert got.status_code == 409 and "no BUILD dict" in got.json()["detail"]
    assert issubclass(errors.Refused, KeyError)                       # a caller that catches KeyError still does


def test_construction_s_own_refusals_are_marked():
    from caliper import construction as C
    from caliper import errors

    with pytest.raises(errors.Refused):
        C.write_build("x = 1\n", {"a": 1})
    with pytest.raises(errors.Refused):
        C.write_build("BUILD = {'b': 1}\n", {"a": 1})


@pytest.mark.parametrize("mk,said", [({"printed": [{"name": "sides", "filament_g": 726, "trust": "model"}]}, ("", "")),
                                     ({"printed": [{"name": "sides", "filament_g": 726, "trust": "rough"}]},
                                      ("a guess (the filament is a rough guess)", "")),
                                     (None, ("a guess (the filament is by the model's solid)", "")),       # a failed slice, say
                                     ({"printed": [{"name": "sides", "filament_g": None, "pending": True}]},
                                      ("a guess (the filament is by the model's solid)", "still slicing"))])
def test_only_the_slicer_s_own_figure_is_no_guess(mk, said):
    assert making.filament_said([making.filament(_rep(), mk), None]) == said
