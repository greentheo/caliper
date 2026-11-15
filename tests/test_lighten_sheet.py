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
    assert rec["sheet"] == {"name": PLY["name"], "param": "ply_t", "now": "3/4 in"}, rec["sheet"]


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
    assert rec["sheet"] == {"name": PLY["name"], "param": "ply_t", "now": "3/4 in"}


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
    assert "sheetUse(run, x.label, x.thickness_mm)" in _fn(src, "lightenView")
    assert "sheetUse(run, b.label, b.thickness_mm, nowLabel)" in src
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


@pytest.mark.parametrize("asked,warned", [("make the panel 5/8 in thick", True), ("print it in PLA instead", False)])
def test_a_revise_that_changes_how_it_s_made_unasked_reads_warned(asked, warned, tmp_path):
    from caliper import chat

    s = DesignStore.create("a panel", base=str(tmp_path / "designs"))
    s.write_part("panel", PANEL, intent="a panel")
    got = chat.refine_part(s, "panel", asked, author=lambda *a: PRINTED, use_llm=False, max_rounds=1,
                           promote_feedback=False)
    first = got.reply.splitlines()[0]
    if warned:
        assert first.startswith("⚠ revised **panel** → v2") and not got.ok, first
        assert ("it also changed how it's made: 1 softwood plywood sheet became 1 PLA (printed) printed piece. Say "
                "\"roll it back\" to undo it.") in got.reply, got.reply
    else:
        assert not first.startswith("⚠") and "changed how it's made" not in got.reply, got.reply


def test_lighten_never_reads_the_check_s_base_material():
    """Its holed top's allowable and the plate at other thicknesses too: every material a Lighten reads is sheet_of(ctx)."""
    import inspect

    from caliper import lighten

    src = inspect.getsource(lighten)
    assert 'ctx["mat"]' not in src and src.count("sheet_of(ctx)") >= 3


#: Numbers that equal the sheet's thickness: the one the build reads is it, never two, never one it doesn't read.
NUMBERS = '''PARAMS = {"ply_t": 19.05, "rail_t": 19.05, "spare": 19.05, "w": 300.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return (p["ply_t"], p["w"]WITH_RAIL)
'''


@pytest.mark.parametrize("rail,want", [("", "ply_t"), (', p["rail_t"]', None)])
def test_the_thickness_param_is_one_the_script_reads_and_only_one(rail, want, tmp_path):
    from caliper import lighten

    s = DesignStore.create("numbers", base=str(tmp_path / "designs"))
    s.write_part("p", NUMBERS.replace("WITH_RAIL", rail), intent="numbers")
    assert lighten.sheet_param(s, "p", 19.05) == want          # "spare" isn't read; with rail_t read too, it can't tell


def test_a_param_use_button_is_wired_to_set_the_number():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", JS)).read()
    assert "b.onclick = () => useParam(p, b.dataset.useParam, Number(b.dataset.useMm));" in src
