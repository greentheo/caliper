"""CALI-184 (#295): Lighten runs a plywood part with printed trim as plywood, never as its trim's PLA.

Found on Theo's step-stool-5 v4 (2026-11-14): a plywood stool with a sliver of printed PLA (its inside corner fillet strips).
`load_study` made the headline material PLA, and Lighten read it: its hole weights at PLA's 1.24 g/cm³ (11.4 lb lighter at
step 16 where plywood says about 5.1), the top holes' allowable and plate check PLA's, and `run.material` "PLA (printed)",
so the thinner-sheet estimate's Use sent "Make it from 5/8 in pla (printed)" and the designer rebuilt the stool as one
printed part. Synthetic parts in that shape, not Theo's.
"""

import json
import re
import subprocess

import pytest

pytest.importorskip("cadquery")

from caliper import load_study as L  # noqa: E402
from caliper import materials as M  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

from .test_lighten_or_carve import WITH_STRIPS  # noqa: E402
from .test_load_study import BOX_STOOL  # noqa: E402

#: The same stool, its ply thickness a number in PARAMS that its build reads (as Theo's ply_t is).
WITH_STRIPS_P = WITH_STRIPS.replace('PARAMS = {"w": 406.4, "d": 254.0, "h": 228.6}',
                                    'PARAMS = {"w": 406.4, "d": 254.0, "h": 228.6, "ply_t": 19.05}').replace(
    'for lo, hi in _boxes(p, BUILD["t"]).values():', 'for lo, hi in _boxes(p, p["ply_t"]).values():').replace(
    't, w, d, h = BUILD["t"], p["w"], p["d"], p["h"]', 't, w, d, h = p["ply_t"], p["w"], p["d"], p["h"]')
PLY, PLA = {"name": M.sheet("plywood")["name"], "density": 0.56}, {"name": "PLA (printed)"}   # as load_study says them


def _store(tmp, script):
    s = DesignStore.create("a part", base=str(tmp / "designs"))
    s.write_part("p", script, intent="a part")
    return s


def test_the_fixture_reads_its_thickness_from_params():
    assert WITH_STRIPS_P.count('p["ply_t"]') == 2 and "BUILD[\"t\"]" not in WITH_STRIPS_P


# --- 1: Lighten's material is the sheet's -------------------------------------------------------------------------------
def test_lighten_s_material_is_the_sheet_s_and_a_printed_part_s_its_print(tmp_path):
    from caliper import lighten

    trim = L.prepare(_store(tmp_path / "a", WITH_STRIPS), "p")
    assert trim["mat"]["name"] == PLA["name"]                        # the FEA's base material: the print, voxel by voxel
    assert lighten.sheet_of(trim)["name"] == PLY["name"] and lighten.sheet_of(trim)["density"] == pytest.approx(PLY["density"])
    pla = {"name": "PLA (printed)", "density": 1.24}                 # an all-printed part: prepare's plate_mat is its mat
    assert lighten.sheet_of({"mat": pla, "plate_mat": pla}) is pla and lighten.sheet_of({"mat": pla}) is pla


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """A real Lighten (one step size) of the plywood stool with a printed strip, its ply thickness in PARAMS."""
    pytest.importorskip("whittle")
    from caliper import lighten

    s = _store(tmp_path_factory.mktemp("trim"), WITH_STRIPS_P)
    L.study(s, "p")
    return s, lighten.study(s, "p", steps=(1.0,)), L.prepare(s, "p")


def test_a_lighten_of_plywood_with_trim_is_plywood(run):
    _, rec, _ = run
    assert rec["material"] == PLY["name"], rec["material"]
    assert {k: rec["sheet"][k] for k in ("name", "param", "now")} == {"name": PLY["name"], "param": "ply_t", "now": "3/4 in"}
    assert set(rec["sheet"]["pieces"].values()) == {"ply_t"}, rec["sheet"]                # each sheet's number: the one


def test_its_weights_are_at_plywood_s_density(run):
    """An estimate's weight comes from the sheets' volume at the density it used: worked back, it's plywood's."""
    _, rec, ctx = run
    est = [x for x in rec["stations"] if x.get("estimate")]
    assert est, [x.get("phase") for x in rec["stations"]]
    base = next(x for x in rec["stations"] if x["index"] == est[0]["from_step"])
    t0 = max(pc["thickness"] for pc in ctx["pieces"] if pc["kind"] == "sheet")
    ratio = est[0]["thickness_mm"] / t0
    wood_lb = base["saved_lb"] + (est[0]["saved_lb"] - base["saved_lb"]) / (1 - ratio)
    volume = sum(pc["volume"] for pc in ctx["pieces"] if pc["kind"] == "sheet")         # mm³
    density = wood_lb * 453.59237 / volume * 1e3                                       # g/cm³
    assert density == pytest.approx(PLY["density"], rel=0.03), density


# --- 2: the headline names both; the plate's table is the sheet's -------------------------------------------------------
def test_the_check_s_headline_names_both_and_its_plate_material_is_the_sheet(run):
    s, _, _ = run
    rec = L.study(s, "p")
    assert rec["headline"] == "softwood plywood, with PLA trim", rec["headline"]
    assert rec["plate_material"]["name"] == PLY["name"] and rec["material"]["name"] == PLA["name"]
    assert {k: rec["sheet"][k] for k in ("name", "param", "now")} == {"name": PLY["name"], "param": "ply_t", "now": "3/4 in"}


def test_a_sheet_or_printed_part_s_headline_is_its_material(tmp_path):
    from caliper import load_study

    assert load_study.headline(PLY, None) == PLY["name"] and load_study.headline(None, PLA) == PLA["name"]
    assert load_study.headline(PLY, PLA, mostly="printed") == "PLA (printed), with softwood plywood pieces"


def test_the_thickness_param_is_the_one_the_sheets_read(tmp_path):
    from caliper import lighten

    assert lighten.sheet_param(_store(tmp_path / "a", WITH_STRIPS_P), "p", 19.05) == "ply_t"
    assert lighten.sheet_param(_store(tmp_path / "b", BOX_STOOL), "p", 19.05) is None       # its t is in BUILD


# --- 3: an estimate's Use is a thickness, not a sentence ----------------------------------------------------------------
JS = "src/caliper/web/static/design.js"


def _node_run(script):
    from .test_carve_click import _node

    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_use_sets_the_thickness_param_or_names_the_sheet_never_its_print():
    import os

    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    out = _node_run(_fn(src, "sheetUse") + """
const esc = (s) => String(s);
const param = { sheet: { name: 'softwood plywood', param: 'ply_t', now: '3/4 in' }, material: 'PLA (printed)' };
const words = { sheet: { name: 'softwood plywood', param: null, now: '3/4 in' }, material: 'PLA (printed)' };
const old = { material: 'PLA (printed)' };
console.log(JSON.stringify({ param: sheetUse(param, '5/8 in', 15.875), words: sheetUse(words, '5/8 in', 15.875),
                             old: sheetUse(old, '5/8 in', 15.875) }));
""")
    assert out["param"] == '<button class="ghost" data-use-param="ply_t" data-use-mm="15.875">Use</button>'
    assert 'data-use-t="Make the 3/4 in softwood plywood 5/8 in"' in out["words"]
    for b in out.values():
        assert not re.search(r"pla\b|printed", b, re.I), b
    assert "sheetUse(run, x.label, x.thickness_mm, undefined, undefined," in _fn(src, "lightenView")   # its words (#297)
    assert "sheetUse(run, b.label, b.thickness_mm, nowLabel, pl.piece," in src            # its piece, then the words (#306 review)
    assert "data-use-t=\"Make it from" not in src


def test_a_param_use_sets_the_number_without_the_designer():
    import os

    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    out = _node_run(_fn(src, "useParam") + """
const S = { slug: 'stool', design: null };
const posted = [], calls = [];
const api = async (m, u, b) => { posted.push([m, u, b]); return { design: { parts: [] }, version: 5 }; };
const render = () => calls.push('render');
const syncParts = async () => calls.push('sync');
const send = () => calls.push('send');
const showErr = (m) => calls.push(['err', m]);
const plainly = (m) => m;
useParam({ id: 'p' }, 'ply_t', 15.875).then(() => console.log(JSON.stringify({ posted, calls })));
""")
    assert out["posted"] == [["POST", "/api/designs/stool/parts/p/params", {"name": "ply_t", "value": 15.875, "unit": "mm"}]]
    assert "send" not in out["calls"] and "sync" in out["calls"]


# --- 4: a revise that changes how a part is made, unasked, says so and gets no ✓ -----------------------------------------
PANEL = '''import cadquery as cq

PARAMS = {"w": 300.0}


def build(params):
    return cq.Workplane().box(300.0, 200.0, 19.05, centered=False)


def construction(params, build=None):
    return [{"name": "panel", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0, 0, 19.05), (300.0, 0, 19.05), (300.0, 200.0, 19.05), (0, 200.0, 19.05)]}]
'''
PRINTED = PANEL.replace('''    return [{"name": "panel", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0, 0, 19.05), (300.0, 0, 19.05), (300.0, 200.0, 19.05), (0, 200.0, 19.05)]}]''',
                        '''    return [{"name": "panel", "kind": "printed", "material": "pla", "infill": 0.4}]''').replace(
    'PARAMS = {"w": 300.0}', 'PARAMS = {"w": 300.0, "t": 15.875}')


@pytest.mark.parametrize("asked,warned", [
    ("make the panel 5/8 in thick", True), ("print it in PLA instead", False), ("make it printed", False),
    # #303 review: a material word alone isn't asking for what it became
    ("make the panel from 5/8 in plywood", True), ("keep it wooden, just thinner", True),
    ("make it lighter, use less material", True), ("make the panel thinner, it's fine as plywood", True)])
def test_a_revise_that_changes_how_it_s_made_unasked_reads_warned(asked, warned, tmp_path):
    from caliper import chat

    s = DesignStore.create("a panel", base=str(tmp_path / "designs"))
    s.write_part("panel", PANEL, intent="a panel")
    got = chat.refine_part(s, "panel", asked, author=lambda *a: PRINTED, use_llm=False, max_rounds=1,
                           promote_feedback=False)
    first = got.reply.splitlines()[0]
    if warned:
        assert first.startswith("⚠ revised **panel** → v2") and not got.ok, first
        assert ("it also changed how it's made: the panel was a softwood plywood sheet and is now a PLA (printed) print. "
                "Say \"roll it back\" to undo it.") in got.reply, got.reply
    else:
        assert not first.startswith("⚠") and "changed how it's made" not in got.reply, got.reply


def test_lighten_never_reads_the_check_s_base_material():
    """Its holed top's allowable and the plate at other thicknesses too: every material a Lighten reads is sheet_of(ctx)."""
    import inspect

    from caliper import lighten

    src = inspect.getsource(lighten)
    assert 'ctx["mat"]' not in src and src.count("sheet_of(ctx)") >= 3


#: A sheet whose thickness comes from ply_t; rail_t is read too and is 19.05, but moves no sheet. With MAX, the thickness is
#: max(ply_t, rail_t): either moves it, so neither can be told for certain.
NUMBERS = """PARAMS = {"ply_t": 19.05, "rail_t": 19.05, "spare": 19.05, "w": 300.0}


def build(params):
    import cadquery as cq

    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["w"], 200.0, p["ply_t"] + p["rail_t"], centered=False)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t = THICK
    return [{"name": "panel", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (p["w"], 0, 0), (p["w"], 200.0, 0), (0, 200.0, 0)]}]
"""


@pytest.mark.parametrize("thick,want", [('p["ply_t"]', "ply_t"), ('max(p["ply_t"], p["rail_t"])', None)])
def test_the_thickness_param_is_the_number_the_sheet_follows_and_only_one(thick, want, tmp_path):
    """#303 review: a number that equals the thickness isn't enough; moved, the sheet must follow it, and only it."""
    from caliper import lighten

    s = DesignStore.create("numbers", base=str(tmp_path / "designs"))
    s.write_part("p", NUMBERS.replace("THICK", thick), intent="numbers")
    assert lighten.sheet_param(s, "p", 19.05) == want          # "spare" isn't read; rail_t moves no sheet


def test_a_param_use_button_is_wired_to_set_the_number():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    assert "b.onclick = () => useParam(p, b.dataset.useParam, Number(b.dataset.useMm));" in src


# --- #303 review -----------------------------------------------------------------------------------------------------------
SHELVED = PANEL.replace('''             "outline": [(0, 0, 19.05), (300.0, 0, 19.05), (300.0, 200.0, 19.05), (0, 200.0, 19.05)]}]''',
                        '''             "outline": [(0, 0, 19.05), (300.0, 0, 19.05), (300.0, 200.0, 19.05), (0, 200.0, 19.05)]},
            {"name": "shelf", "kind": "sheet", "material": "plywood", "thickness": 19.05,
             "outline": [(0, 0, 9.0), (300.0, 0, 9.0), (300.0, 200.0, 9.0), (0, 200.0, 9.0)]}]''')


@pytest.mark.parametrize("was,now,asked", [(PANEL, SHELVED, "add a shelf between the sides"),
                                           (SHELVED, PANEL, "take the shelf out")])
def test_a_piece_added_or_taken_away_in_its_own_material_isn_t_made_otherwise(was, now, asked, tmp_path):
    from caliper import chat

    assert SHELVED.count('"name": "shelf"') == 1
    s = DesignStore.create("a panel", base=str(tmp_path / "designs"))
    s.write_part("panel", was, intent="a panel")
    got = chat.refine_part(s, "panel", asked, author=lambda *a: now, use_llm=False, max_rounds=1, promote_feedback=False)
    assert "changed how it's made" not in got.reply and not got.reply.startswith("⚠"), got.reply


def test_the_words_stay_on_a_failed_round():
    from caliper import chat

    head = "✗ revised **panel** → v2 (1 round(s))\nAsked for: x"
    said = chat._say_made(head, "the panel was a softwood plywood sheet and is now a PLA (printed) print")
    assert said.splitlines()[0] == ("✗ revised **panel** → v2 (1 round(s)): it also changed how it's made: the panel was a "
                                    "softwood plywood sheet and is now a PLA (printed) print. Say \"roll it back\" to undo it.")
    assert chat._say_made("✓ revised **p** → v2", "x").startswith("⚠ revised **p** → v2: it also changed")


#: A top 1/2 in and sides 3/4 in, each from its own number; and a lip that happens to be 12.7 too, which isn't a thickness.
TWO = '''import cadquery as cq

PARAMS = {"top_t": 12.7, "side_t": 19.05, "lip": 12.7, "w": 300.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["w"], 200.0, p["top_t"] + p["lip"], centered=False)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, top, side = p["w"], p["top_t"], p["side_t"]
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": top,
             "outline": [(0, 0, 400), (w, 0, 400), (w, 200, 400), (0, 200, 400)]},
            {"name": "left", "kind": "sheet", "material": "plywood", "thickness": side,
             "outline": [(0, 0, 0), (0, 200, 0), (0, 200, 400), (0, 0, 400)]},
            {"name": "right", "kind": "sheet", "material": "plywood", "thickness": side,
             "outline": [(w, 0, 0), (w, 200, 0), (w, 200, 400), (w, 0, 400)]}]
'''


def test_each_sheet_s_thickness_number_is_its_own_and_a_lighten_has_none_where_they_differ(tmp_path):
    s = DesignStore.create("two", base=str(tmp_path / "designs"))
    s.write_part("p", TWO, intent="two thicknesses")
    ctx = {"pieces": [{"name": n, "kind": "sheet", "thickness": t} for n, t in (("top", 12.7), ("left", 19.05), ("right", 19.05))],
           "plate_mat": {"name": PLY["name"]}, "mat": {"name": PLY["name"]}}
    said = L.sheet_said(s, "p", ctx)
    assert said["pieces"] == {"top": "top_t", "left": "side_t", "right": "side_t"}, said     # never "lip"
    assert said["param"] is None                        # a Lighten scales every sheet: one number only where all are one


def test_a_plate_row_s_use_sets_its_own_piece_s_number_or_says_it():
    import os

    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    out = _node_run(_fn(src, "sheetUse") + """
const esc = (s) => String(s);
const run = { sheet: { name: 'softwood plywood', param: null, now: '3/4 in', pieces: { top: 'top_t', left: 'side_t' } } };
console.log(JSON.stringify({ top: sheetUse(run, '3/8 in', 9.525, '1/2 in', 'top'),
                             shelf: sheetUse(run, '3/8 in', 9.525, '1/2 in', 'shelf'),
                             lighten: sheetUse(run, '5/8 in', 15.875) }));
""")
    assert 'data-use-param="top_t"' in out["top"] and "side_t" not in out["top"]
    assert 'data-use-t="Make the shelf 3/8 in softwood plywood, not 1/2 in"' in out["shelf"]
    assert "data-use-param" not in out["lighten"] and 'data-use-t="Make the 3/4 in softwood plywood 5/8 in"' in out["lighten"]
    assert "sheetUse(run, b.label, b.thickness_mm, nowLabel, pl.piece," in src            # its piece, then the words (#306 review)


#: Theo's Lighten of step-stool-5 v4 before the fix (20261113-172306): its material the trim's print, its weights at PLA's.
PRE_FIX = {"id": "20261113-172306-9204", "part": "p", "kind": "lighten", "version": 1, "material": "PLA (printed)",
           "min_safety": 1.3, "spacing_mm": 4.76, "notes": [], "created": 1794618883.27,
           "panels": [{"name": "left", "thickness_mm": 19.05, "stood_on": False},
                      {"name": "top", "thickness_mm": 19.05, "stood_on": True}],
           "stations": [{"index": 0, "phase": "walls", "saved_lb": 0.0, "holes": 0, "top_holes": 0, "safety": 2.1,
                         "holds": True, "cases": [], "panels": {}},
                        {"index": 1, "phase": "top", "saved_lb": 11.39, "holes": 17, "top_holes": 12, "safety": 1.4,
                         "holds": True, "cases": [], "panels": {}}]}
NOT_TRUSTED = "Not trusted: it ran as PLA (printed), not as its softwood plywood. Lighten it again."


def _with_run(tmp_path, script, run):
    import os

    from caliper import lighten

    s = _store(tmp_path, script)
    d = os.path.join(lighten.runs_dir(s), run["id"])
    os.makedirs(d)
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump(run, f)
    return s


def test_a_lighten_run_as_the_print_on_a_sheet_part_isn_t_trusted_or_adoptable(tmp_path):
    from caliper import design_api, lighten

    s = _with_run(tmp_path, WITH_STRIPS, PRE_FIX)
    (run,) = lighten.list_runs(s)
    assert run["not_trusted"] == NOT_TRUSTED
    with pytest.raises(ValueError, match="Not trusted: it ran as PLA"):
        lighten.adopt(s, PRE_FIX["id"], 1)
    st = design_api.design_state(s)
    (shown,) = st["lighten_runs"]
    assert all(x["verdict"]["kind"] == "untrusted" and not x["verdict"]["counts_as_pass"] for x in shown["stations"])
    assert NOT_TRUSTED in json.dumps([x["verdict"] for x in shown["stations"]])


def test_a_plywood_run_or_a_printed_part_s_run_is_trusted(tmp_path):
    from caliper import lighten

    ply = dict(PRE_FIX, material=PLY["name"], id="20261114-170224-d0b2")
    assert lighten.list_runs(_with_run(tmp_path / "a", WITH_STRIPS, ply))[0].get("not_trusted") is None
    carve = dict(PRE_FIX, kind="carve", id="20261114-170224-c4rv")
    assert lighten.wrong_material(_store(tmp_path / "b", WITH_STRIPS), "p", carve) is None        # a carve's own material


def test_the_panel_leads_with_why_a_run_isn_t_trusted():
    import os

    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    assert "run.not_trusted ? esc(run.not_trusted)" in _fn(src, "lightenView")


def test_sheets_that_went_while_prints_came_under_a_new_name_are_made_otherwise(tmp_path):
    from caliper import chat

    renamed = PRINTED.replace('"name": "panel"', '"name": "body"')
    s = DesignStore.create("a panel", base=str(tmp_path / "designs"))
    s.write_part("panel", PANEL, intent="a panel")
    got = chat.refine_part(s, "panel", "make it lighter", author=lambda *a: renamed, use_llm=False, max_rounds=1,
                           promote_feedback=False)
    assert "it also changed how it's made: 1 softwood plywood sheet became 1 PLA (printed) print." in got.reply, got.reply


def test_a_row_takes_its_own_piece_s_number_before_the_part_s():
    import os

    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    out = _node_run(_fn(src, "sheetUse") + """
const esc = (s) => String(s);
const run = { sheet: { name: 'softwood plywood', param: 'side_t', now: '3/4 in', pieces: { top: 'top_t' } } };
console.log(JSON.stringify({ top: sheetUse(run, '3/8 in', 9.525, '1/2 in', 'top') }));
""")
    assert 'data-use-param="top_t"' in out["top"]



def test_a_run_as_the_print_stays_untrusted_after_the_part_is_made_all_printed(tmp_path):
    """#303 re-check: judged by the run, never by what the part is now: made all printed after the run, the run's steps
    are still a print's weights for sheets that were there."""
    from caliper import lighten

    from .test_lighten_or_carve import ALL_PRINTED

    s = _with_run(tmp_path, ALL_PRINTED, PRE_FIX)
    (run,) = lighten.list_runs(s)
    assert run["not_trusted"] == "Not trusted: it ran as PLA (printed), not as its sheets. Lighten it again."
    with pytest.raises(ValueError, match="Not trusted"):
        lighten.adopt(s, PRE_FIX["id"], 1)
    own = dict(PRE_FIX, sheet={"name": "softwood plywood"}, id="20261113-172306-0wn5")
    assert lighten.wrong_material(s, "p", own) == NOT_TRUSTED                       # the run's own sheet, where it says
