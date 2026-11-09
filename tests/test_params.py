"""CALI-108 (#108, the backend) — a part's exact numbers, set by hand, with no Claude call.

Theo: "the advantage to manual cad is the ability to specify things precisely". Listing a part's PARAMS in plain
words, and setting one: converted to mm, refused outside its range, only its line rewritten (its comment kept), built,
written as a new version that says so, the design measured again, and a value the build ignores or clamps said."""

import json
import os
import subprocess

import pytest

from caliper import aero, params
from caliper.design import DesignStore

pytest.importorskip("cadquery")

BOX = '''import cadquery as cq

PARAMS = {
    "w": 400.0,         # width of the box
    # how tall it stands
    "h": 200.0,
    "fillet_r": 6.0,    # fillet radius at the top edges mm
    "spare": 3.0,       # a number the build never reads
    "mesh_rows": 4,     # rows of holes
}
RANGES = {"h": (100.0, 300.0), "w": (100.0, 800.0)}


def build(params):
    p = {**PARAMS, **(params or {})}
    r = min(p["fillet_r"], 2.0)          # clamped: anything over 2 mm is 2 mm
    return cq.Workplane().box(p["w"], 100.0, p["h"]).edges("|Z").fillet(r)
'''


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import caliper.chat as chat

    def no_claude(*a, **k):
        raise AssertionError("a number set by hand never asks Claude")

    monkeypatch.setattr(chat, "author_part", no_claude)
    monkeypatch.setattr(chat, "refine_part", no_claude)
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX, intent="a box")
    return s


def test_the_numbers_are_listed_in_plain_words_with_their_ranges(store):
    got = {e["name"]: e for e in params.listing(store, "box")}
    assert list(got) == ["w", "h", "fillet_r", "spare", "mesh_rows"]
    assert got["w"] == {"name": "w", "note": "width of the box", "value": 400.0, "unit": "mm", "range": [100.0, 800.0],
                        "read": True}
    assert got["h"]["note"] == "how tall it stands"                               # the comment line just above it
    assert got["fillet_r"]["range"] is None and got["spare"]["read"] is False
    # what each is, by what the script says (#147 review): a length by its comment or name, a count, nothing known
    assert [got[k]["unit"] for k in ("w", "h", "fillet_r", "spare", "mesh_rows")] == ["mm", "mm", "mm", "", "count"]


def test_only_that_params_line_is_rewritten_its_comment_kept():
    new = aero.write_params(BOX, {"fillet_r": 1.5}, keep_float=True)
    before, after = BOX.splitlines(), new.splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and changed == [
        ('    "fillet_r": 6.0,    # fillet radius at the top edges mm', '    "fillet_r": 1.5,    # fillet radius at the top edges mm')]
    assert '"h": 250.0,' in aero.write_params(BOX, {"h": 250}, keep_float=True)    # a float stays a float
    assert '"h": 250,' in aero.write_params(BOX, {"h": 250})                       # as the drag study writes it


def test_setting_a_number_writes_a_new_version_rebuilt_and_measured_with_no_claude_call(store):
    v = store.design.part("box").version
    got = params.set_value(store, "box", "h", 250, "mm")
    assert got["version"] == v + 1 and got["said"] == "set h to 250 mm by hand" and got["warning"] is None
    assert '"h": 250.0,' in store.read_script("box")
    assert store.part_geometry("box").require_mesh().extents[2] == pytest.approx(250.0, abs=0.01)
    h = store.history("box")[-1]
    assert h["action"] == "params" and h["feedback"] == "set h to 250 mm by hand" and h["params"] == {"h": [200.0, 250.0]}
    assert got["report"] is not None                                               # the design measured again


def test_inches_in_millimetres_stored(store):
    got = params.set_value(store, "box", "h", 10, "in")
    assert got["value"] == pytest.approx(254.0) and got["said"] == "set h to 10 in by hand"
    assert '"h": 254.0,' in store.read_script("box")


def test_a_value_outside_its_range_is_refused_with_the_range_and_nothing_written(store):
    v = store.design.part("box").version
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 400 mm is outside it$"):
        params.set_value(store, "box", "h", 400, "mm")
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 1 ft is outside it$"):
        params.set_value(store, "box", "h", 1, "ft")                               # 304.8 mm
    with pytest.raises(ValueError, match="has no number called 'depth'"):
        params.set_value(store, "box", "depth", 10)
    with pytest.raises(ValueError, match="is a length: give it in mm or in"):
        params.set_value(store, "box", "h", 10, "furlongs")
    assert store.design.part("box").version == v and '"h": 200.0,' in store.read_script("box")


def test_a_value_the_build_ignores_or_clamps_is_said(store):
    clamped = params.set_value(store, "box", "fillet_r", 8, "mm")
    assert clamped["moved"] is False
    assert clamped["warning"] == "the part's shape didn't change: its build clamps or ignores fillet_r at 8 mm"
    unread = params.set_value(store, "box", "spare", 9)
    assert unread["warning"] == "spare isn't used by the part's build, so setting it changed nothing"


def test_the_api_lists_and_sets_a_number(store, monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    c, slug = TestClient(create_app()), store.design.slug
    listed = c.get(f"/api/designs/{slug}/parts/box/params").json()
    assert [e["name"] for e in listed["params"]] == ["w", "h", "fillet_r", "spare", "mesh_rows"]
    got = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 500, "unit": "mm"})
    assert got.status_code == 200 and got.json()["said"] == "set w to 500 mm by hand"
    assert next(p for p in got.json()["design"]["parts"] if p["id"] == "box")["version"] == 2
    bad = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 900, "unit": "mm"})
    assert bad.status_code == 422 and "w must be between 100 and 800 mm" in bad.json()["detail"]



# --- #147 review ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,unit,why", [
    ("mesh_rows", "in", "mesh rows is a count: give a number, no unit"),
    ("mesh_rows", "mm", "mesh rows is a count: give a number, no unit"),
    ("h", "furlongs", "h is a length: give it in mm or in, not 'furlongs'"),
])
def test_only_a_length_converts_and_a_unit_on_a_count_is_refused(store, name, unit, why):
    """#147 review: "mesh_rows 8 in" was 203.2 on an inch design. A count takes a number, no unit."""
    with pytest.raises(ValueError, match=f"^{why}$"):
        params.set_value(store, "box", name, 8, unit)
    assert '"mesh_rows": 4,' in store.read_script("box")
    got = params.set_value(store, "box", "mesh_rows", 8)
    assert '"mesh_rows": 8,' in store.read_script("box") and got["said"] == "set mesh_rows to 8 by hand"


def test_a_number_with_no_known_unit_is_taken_as_it_is_and_said(store):
    got = params.set_value(store, "box", "spare", 9)
    assert got["value"] == 9.0 and "spare has no unit in its script, so 9 is taken as it is, not converted" in got["notes"]


def test_a_unit_on_a_number_of_no_known_kind_is_refused_never_dropped(store):
    """#147 review, blocking: "set p1z to 26 in" (Theo's leaf_rear: no comment) wrote 26, as mm, with a note."""
    leaf = BOX.replace('    "mesh_rows": 4,     # rows of holes\n', '    "mesh_rows": 4,     # rows of holes\n    "p1z": 660.4,\n')
    store.write_part("leaf", leaf, intent="a leaf")
    v = store.design.part("leaf").version
    for unit in ("in", "mm"):
        with pytest.raises(ValueError, match="^I don't know if p1z is a length: give it in mm, without a unit$"):
            params.set_value(store, "leaf", "p1z", 26, unit)
    assert store.design.part("leaf").version == v and '"p1z": 660.4,' in store.read_script("leaf")


#: Theo's own PARAMS lines (read-only from his designs; the names and comments the review quotes), with what each is.
THEOS = [
    ("rib_v", "vertical rib between rows mm", "mm"),                      # i-want: a unit in the comment wins
    ("rib_h", "circumferential rib between cols mm", "mm"),
    ("mesh_rows", "number of vertical rows of mesh openings", "count"),
    ("wall_t", "printed shell thickness mm (increased from 4mm)", "mm"),
    ("foot_fillet_r", "", "mm"),
    ("shoulder", "side from wall top to roof edge: 1 = straight, 2 = round", "choice"),   # the cargo box
    ("tail_curve", "1 = straight panels; 2 = teardrop curve", "choice"),
    ("edges", "0: no edges; 1: front and back edges; 2: all four sides", "choice"),
    ("spine_back", "1: the spine runs to the back of the floor; 0: it stops under the X's middle", "choice"),
    ("edge_w", '1 in: edges under the walls (see "edges")', "mm"),
    ("p1z", "", ""),                                                        # leaf_rear: not known, a unit refused
    ("p1x", "", ""),
    ("recess_margin", "border left around recess", ""),                     # step-stool
    ("ribs", "how many ribs around the cone", "count"),                     # not Theo's: a count by its comment alone
]


@pytest.mark.parametrize("name,note,unit", THEOS)
def test_what_each_of_theo_s_numbers_is(name, note, unit):
    assert params.unit_of(name, note) == unit


def test_a_choice_takes_no_unit(store):
    shaped = BOX.replace('    "mesh_rows": 4,     # rows of holes\n',
                         '    "mesh_rows": 4,     # rows of holes\n    "shoulder": 1.4,   # side from wall top to roof '
                         'edge: 1 = straight, 2 = round\n')
    store.write_part("box", shaped, intent="a box")
    assert {e["name"]: e["unit"] for e in params.listing(store, "box")}["shoulder"] == "choice"
    with pytest.raises(ValueError, match="^shoulder is a choice: give a number, no unit$"):
        params.set_value(store, "box", "shoulder", 2, "in")


def test_no_range_is_said_and_a_ranged_number_says_nothing_of_it(store):
    got = params.set_value(store, "box", "fillet_r", 1.5)
    assert "no range is set for fillet_r in the script, so it isn't checked" in got["notes"]
    assert not [n for n in params.set_value(store, "box", "h", 250)["notes"] if "no range" in n]


def test_a_partial_clamp_is_measured_and_said(store):
    """#107's fillet: asked more than the build makes. The shape moves (1.5 → 2), so only a probe of the built fillet
    says it: asked 3 mm, built 2 mm."""
    params.set_value(store, "box", "fillet_r", 1.5)
    exact = params.set_value(store, "box", "fillet_r", 1.8)
    assert exact["moved"] and not [n for n in exact["notes"] if n.startswith("asked")]
    got = params.set_value(store, "box", "fillet_r", 3)
    assert got["moved"] and "asked 3 mm, built 2 mm (the closest fillet)" in got["notes"]


def test_a_part_with_a_strength_check_says_check_it_again(store):
    import json
    import os

    from caliper import load_study

    run = {"id": "20261107-000000-box", "part": "box", "version": store.design.part("box").version, "created": 1.0,
           "min_safety": 2, "safety": 3.0, "holds": True, "cases": []}
    folder = os.path.join(load_study.runs_dir(store), run["id"])
    os.makedirs(folder)
    with open(os.path.join(folder, "run.json"), "w") as f:
        json.dump(run, f)
    assert "strength: check the box again" in params.set_value(store, "box", "h", 250)["notes"]


# --- the panel's Rebuild: everything changed, one version (#108, the mockup) ------------------------------------------
def test_several_numbers_are_one_version_with_each_said(store):
    got = params.set_values(store, "box", [{"name": "h", "value": 150}, {"name": "w", "value": 300}])
    assert got["version"] == 2 and store.design.part("box").version == 2
    assert got["said"] == "set h to 150 mm and w to 300 mm by hand"
    entry = store.history("box")[-1]
    assert entry["feedback"] == got["said"] and set(entry["params"]) == {"h", "w"}
    now = {e["name"]: e["value"] for e in params.listing(store, "box")}
    assert now["h"] == 150 and now["w"] == 300


def test_one_bad_number_in_a_batch_writes_none_of_them(store):
    was = store.read_script("box")
    with pytest.raises(ValueError, match="between 100 and 300"):
        params.set_values(store, "box", [{"name": "w", "value": 300}, {"name": "h", "value": 9000}])
    assert store.read_script("box") == was and store.design.part("box").version == 1


def test_a_batch_is_built_as_one_change(store, monkeypatch):
    """Numbers that only work together: built one at a time, the first could be refused or leave a half-way version."""
    from caliper import sandbox

    calls, real = [], sandbox.run_script
    monkeypatch.setattr(sandbox, "run_script", lambda script, p, **k: calls.append(script) or real(script, p, **k))
    params.set_values(store, "box", [{"name": "h", "value": 150}, {"name": "w", "value": 300}])
    new = [c for c in calls if '"h": 150' in c]                     # the old script may be built to compare with
    assert len(new) == 1 and '"w": 300' in new[0]


def test_nothing_to_set_and_a_number_twice_are_refused(store):
    with pytest.raises(ValueError):
        params.set_values(store, "box", [])
    with pytest.raises(ValueError, match="twice"):
        params.set_values(store, "box", [{"name": "h", "value": 150}, {"name": "h", "value": 160}])


def test_in_a_batch_a_number_the_build_ignores_is_named(store):
    got = params.set_values(store, "box", [{"name": "h", "value": 150}, {"name": "spare", "value": 9}])
    assert "spare" in got["warning"] and "h " not in got["warning"]


def test_the_api_takes_a_batch_in_the_person_s_units(store, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.post(f"/api/designs/{slug}/parts/box/params",
                 json={"values": [{"name": "h", "value": 6, "unit": "in"}, {"name": "w", "value": 300, "unit": "mm"}]})
    assert got.status_code == 200 and got.json()["version"] == 2
    now = {e["name"]: e["value"] for e in c.get(f"/api/designs/{slug}/parts/box/params").json()["params"]}
    assert now["h"] == pytest.approx(152.4) and now["w"] == 300
    assert c.post(f"/api/designs/{slug}/parts/box/params", json={"values": []}).status_code == 422


# --- the page ---------------------------------------------------------------------------------------------------------
JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
_LIST = """[
  { name: 'wall_t', note: 'cone wall thickness mm', value: 12.7, unit: 'mm', range: [6.35, 25.4], read: true },
  { name: 'mesh_rows', note: 'rows of holes', value: 4, unit: 'count', range: [1, 8], read: true },
  { name: 'spare', note: '', value: 3, unit: 'mm', range: null, read: false },
  { name: 'tilt', note: 'lean angle', value: 5, unit: 'deg', range: null, read: true } ]"""
_CONST = "const PARAM_WORD = { dia: 'diameter', bot: 'bottom', t: 'thickness', r: 'radius', h: 'height', w: 'width', d: 'diameter' };"
_FNS = ("inchText", "paramName", "readNumber", "paramRange", "paramProblem", "paramRows", "paramsHtml", "paramView")


def _page(body: str, units: str = "in") -> dict:
    from .test_carve_click import _fn, _node

    src = open(JS).read()
    head = """
const IN = 25.4;
const gcd = (a, b) => (b ? gcd(b, a % b) : a);
const S = { slug: 'x', design: { display_units: 'UNITS' }, params: null, paramsDone: null };
const inches = () => S.design.display_units === 'in';
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const paramKey = (p) => `${S.slug}/${p.id}/${p.version}/${S.design.display_units}`;
const isLength = (e) => e.unit === 'mm';
const paramText = (e, v) => (isLength(e) && inches() ? inchText(v) : `${+Number(v).toFixed(3)}`);
const paramUnit = (e) => (isLength(e) ? (inches() ? 'in' : 'mm') : e.unit === 'deg' ? 'deg' : '');
let loaded = 0;
const loadParams = () => { loaded += 1; };
globalThis.setTimeout = (f) => f();
const LIST = LIST_HERE;
const P = { id: 'box', version: 5, scripted: true, role: 'part' };
const state = (drafts) => ({ key: 'x/box/5/UNITS', list: LIST, drafts: drafts || {}, saving: false, err: null });
const byName = (n) => LIST.find((e) => e.name === n);
""".replace("UNITS", units).replace("LIST_HERE", _LIST)
    script = head + _CONST + "\n".join(_fn(src, n) for n in _FNS) + f"\nconst out = (() => {{ {body} }})();\nconsole.log(JSON.stringify(out));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@pytest.mark.parametrize("mm,said", [(12.7, "1/2"), (31.75, "1 1/4"), (25.4, "1"), (6, "0.236"), (736.6, "29")])
def test_lengths_show_in_the_person_s_inches(mm, said):
    assert _page(f"return {{ s: inchText({mm}) }};")["s"] == said


@pytest.mark.parametrize("typed,value,unit", [("0.5", 0.5, "in"), ("1/2", 0.5, "in"), ("1 1/4", 1.25, "in"), ('2"', 2, "in"),
                                              ("12.7 mm", 12.7, "mm"), (".25", 0.25, "in")])
def test_what_s_typed_is_read_with_its_unit(typed, value, unit):
    got = _page(f"return readNumber({json.dumps(typed)}, byName('wall_t'));")
    assert got == {"value": value, "unit": unit}


@pytest.mark.parametrize("typed", ["", "abc", "1/0", "1/2/3", "--2"])
def test_what_isn_t_a_number_isn_t_read(typed):
    assert _page(f"return {{ r: readNumber({json.dumps(typed)}, byName('wall_t')) }};")["r"] is None


def test_a_count_takes_no_unit_and_a_unit_on_it_is_not_a_number():
    got = _page("return { a: readNumber('5', byName('mesh_rows')), b: readNumber('5 mm', byName('mesh_rows')) };")
    assert got["a"] == {"value": 5} and got["b"] is None


def test_the_panel_lists_each_number_in_plain_words_in_the_person_s_units():
    h = _page("return { h: paramsHtml(P, state(), null) };")["h"]
    assert "Cone wall thickness<" in h and 'value="1/2"' in h and "1/4 to 1 in" in h
    assert "Rows of holes" in h and 'value="4"' in h and "1 to 8" in h
    assert "set by hand, no Claude call" in h and "doesn't use this" in h
    assert "Rebuild" not in h                                    # nothing changed


def test_the_panel_in_mm():
    h = _page("return { h: paramsHtml(P, state(), null) };", units="mm")["h"]
    assert 'value="12.7"' in h and "6.35 to 25.4 mm" in h


def test_a_change_says_what_it_was_and_offers_the_next_version():
    h = _page("return { h: paramsHtml(P, state({ wall_t: '3/4' }), null) };")["h"]
    assert 'value="3/4"' in h and "was 1/2 in" in h and "Rebuilds as v6" in h and "data-param-rebuild" in h
    assert "prow changed" in h and "disabled>Rebuild" not in h


def test_retyping_the_number_shown_is_not_a_change():
    got = _page("return { n: paramRows(state({ wall_t: ' 1/2 ' })).filter((r) => r.changed).length };")
    assert got == {"n": 0}


@pytest.mark.parametrize("typed,why", [("2", "Must be 1/4 to 1 in."), ("nope", "That isn&#39;t a number.")])
def test_a_bad_number_is_refused_with_the_range_and_rebuild_is_off(typed, why):
    h = _page(f"return {{ h: paramsHtml(P, state({{ wall_t: {json.dumps(typed)} }}), null) }};")["h"]
    assert why.replace("&#39;", "'") in h and "prow changed bad" in h and "disabled>Rebuild" in h


def test_a_range_is_checked_in_the_scripts_mm_whatever_unit_was_typed():
    got = _page("return { a: paramProblem(byName('wall_t'), { value: 20, unit: 'mm' }), "
                "b: paramProblem(byName('wall_t'), { value: 30, unit: 'mm' }) };")
    assert got["a"] == "" and got["b"].startswith("Must be")


def test_half_a_row_is_refused():
    assert _page("return { w: paramProblem(byName('mesh_rows'), { value: 4.5 }) };")["w"] == "A whole number."


def test_after_a_rebuild_it_says_what_was_written_and_what_was_ignored():
    h = _page("""return { h: paramsHtml(P, state(), { part: 'box', version: 5, said: 'set wall_t to 3/4 in by hand',
                 warning: "spare isn't used", notes: ['strength: check the box again'] }) };""")["h"]
    assert "v5 written: set wall_t to 3/4 in by hand." in h and "spare isn't used." in h
    assert "strength: check the box again." in h


def test_a_written_line_from_another_part_stays_away():
    h = _page("""return { h: paramsHtml(P, state(), { part: 'other', version: 5, said: 'x', notes: [] }) };""")["h"]
    assert "written" not in h


@pytest.mark.parametrize("p", ["{ ...P, role: 'fixed' }", "{ ...P, scripted: false }"])
def test_a_reference_or_a_mesh_has_no_panel(p):
    assert _page(f"return {{ h: paramView({p}), n: loaded }};") == {"h": "", "n": 0}


def test_the_numbers_are_fetched_once_for_a_version():
    got = _page("""const a = paramView(P), n = loaded;
                   S.params = { ...state(), key: 'x/box/5/in' };
                   const b = paramView(P);
                   return { a, n, again: loaded, drew: b.includes('Parameters') };""")
    assert got == {"a": "", "n": 1, "again": 1, "drew": True}


@pytest.mark.parametrize("name,note,said", [
    ("seat_dia", "12 in", "Seat diameter"),                                 # Theo's stool: a quantity isn't a name
    ("seat_t", "3/4 in plywood", "Seat thickness"),
    ("stool_h", "29", "Stool height"),
    ("cone_top_dia", "~10.5", "Cone top diameter"),
    ("cone_bot_dia", "18 in base", "Cone bottom diameter"),
    ("foot_fillet_r", "1 in fillet radius at cone-to-foot inner junction", "Fillet radius at cone-to-foot inner junction"),
    ("foot_t", "Extra radial width of foot ring (~2.5 in + 1", "Extra radial width of foot ring"),
    ("rib_v", "vertical rib between rows mm", "Vertical rib between rows"),
    ("wall_t", "", "Wall thickness"),
])
def test_a_number_s_name_is_words_not_a_quantity(name, note, said):
    got = _page(f"return {{ s: paramName({{ name: {json.dumps(name)}, note: {json.dumps(note)} }}) }};")
    assert got["s"] == said


@pytest.mark.parametrize("value,said", [(0.375, "3/8 in"), (0.5, "1/2 in"), (1.25, "1 1/4 in"), (6, "6 in"), (0.2362, "0.2362 in"),
                                        (0, "0 in")])
def test_an_exact_edit_is_said_exactly(value, said):
    assert params._said(value, "in") == said
