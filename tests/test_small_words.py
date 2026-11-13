"""CALI-145 (#185) — small words and marks from the bar stool walk, and three asks from the re-check of #186."""
import json
import os
import subprocess

import pytest

from caliper import answers, design_api, params, studies, tree, trials

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
pytest.importorskip("cadquery")


def _js(names, body, head=""):
    src = open(JS).read()
    script = "const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');\n" + head + "\n".join(_fn(src, n) for n in names) + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


class _D:
    def __init__(self, labels):
        self.piece_labels = labels


class _S:
    def __init__(self, labels):
        self.design = _D(labels)


@pytest.mark.parametrize("text,want", [("Cut the seat top first.", "Cut the seat disk first."), ("seat_top: declared", "seat disk: declared"),
                                       ("the seat tops", "the seat tops"), ("a seat topper", "a seat topper"), ("unseat top", "unseat top"),
                                       ("seat top, then the seat top", "seat disk, then the seat disk")])
def test_a_renamed_piece_is_called_what_it_was_renamed_to(text, want):
    assert tree.relabelled(_S({"p": {"seat_top": "seat disk"}}), "p", text) == want


def test_a_part_with_no_labels_is_left_alone():
    assert tree.relabelled(_S({}), "p", "the seat top") == "the seat top"


def test_the_cut_list_uses_the_new_name():
    assert "tree.relabelled(store, pid, f.read())" in open(os.path.join(os.path.dirname(JS), "..", "..", "release.py")).read()


@pytest.mark.parametrize("text,want", [("_a plain line_", "<i>a plain line</i>"),
                                       ("_it can't see min_wall, bbox or volume._", "<i>it can&#x27;t see min_wall, bbox or volume.</i>".replace("&#x27;", "'")),
                                       ("min_wall stays", "min_wall stays"), ("a_b_c stays", "a_b_c stays")])
def test_italics_with_an_underscore_inside(text, want):
    assert _js(("md",), f"return {{ h: md({json.dumps(text)}) }};")["h"] == want


def test_a_change_of_units_asks_for_the_cards_again():
    assert "d.display_units]);" in _fn(open(JS).read(), "answersKey")


def test_a_person_s_own_cancel_isn_t_an_error():
    got = _js(("jobEnded",), "return { h: jobEnded({ status: 'cancelled', message: 'cancelled' }) };", "const plainly = (s) => s;\n")["h"]
    assert "Cancelled." in got and "⚠" not in got and "--bad" not in got


def test_a_server_that_s_away_is_said_in_words():
    got = _js(("jobEnded",), "return { h: jobEnded({ message: 'Failed to fetch' }) };", "const plainly = (s) => s;\n")["h"]
    assert "isn't answering" in got and "Failed to fetch" not in got


def test_any_other_ending_is_still_an_error():
    got = _js(("jobEnded",), "return { h: jobEnded({ message: 'the part would not build' }) };", "const plainly = (s) => s;\n")["h"]
    assert "⚠ the part would not build" in got and "--bad" in got


def test_a_box_parameter_d_is_depth():
    src = open(JS).read()
    i = src.index("const PARAM_WORD")
    head = src[i:src.index("\n", i)] + "\n"
    assert _js(("paramName",), "return { n: paramName({ name: 'd', note: '' }) };", head)["n"] == "Depth"


def test_the_stress_banner_says_when_it_s_from_an_older_version():
    assert "from v${run.version}: the part has changed since" in _fn(open(JS).read(), "showHeat")


def test_the_balance_marker_shrinks_on_a_small_part():
    assert "Math.max(across / 160, Math.min(8, across / 25))" in _fn(open(JS).read(), "showMarks")


def test_folding_a_panel_repaints_where_its_job_is_said():
    assert "addEventListener('toggle', paintJobs, true)" in open(JS).read()


def test_the_lighten_line_doesn_t_read_as_if_it_was_carved():
    src = open(studies.__file__).read()
    # since #272 the words are the Lighten-or-Carve rule's, read by blocked(), the card and this list alike
    from caliper import load_study

    assert "its printed part is carved" not in src
    assert "It's mostly printed: it's carved, not lightened" in open(load_study.__file__).read()


def _plan(tmp_path, monkeypatch, lb, breaks):
    from caliper import load_study
    from caliper.design import DesignStore

    from .test_goals import BOX

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a stool")
    d = os.path.join(load_study.runs_dir(s), "20261110-000000-x")
    os.makedirs(d)
    fea = {"supported": True, "deflection_mm": 1.5, "wall_mm": 19.0, "at": [0, 0, 10], "in": "the top", "peak_mpa": 5.0}
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "x", "part": "stool", "version": s.design.part("stool").version, "created": 1.0, "safety": 1.0, "min_safety": 2.0,
                   "spacing_mm": 2.0, "thinnest_mm": 19.05, "across": 9.5, "finer": True,
                   "cases": [{"name": "a person", "lb": lb, "factor": 1.5, "safety": 1.0, "holds": False, "governs": "fea", "breaks_lb": breaks, "fea": fea}]}, f)
    return [st["lb"] for st in trials.predict(s, "stool")["steps"]]


def test_the_test_plan_stops_at_the_break_even_when_the_check_s_own_load_is_past_it(tmp_path, monkeypatch):
    """The real stool: 250 lb checked, predicted to break at about 220 lb. Its plan read 50 to 220, then 250."""
    assert _plan(tmp_path, monkeypatch, 250, 220) == [50, 100, 150, 200, 220]


def test_the_test_plan_reaches_the_break_when_the_load_is_under_it(tmp_path, monkeypatch):
    assert _plan(tmp_path, monkeypatch, 75, 180) == [50, 75, 100, 150, 180]


def test_a_rule_is_named_in_words():
    from caliper import part_rules

    said = part_rules._said({"id": "shell_wall_thickness", "expr": "min_wall >= 2.85", "actual": 0.25, "status": "fail"}, None, True)
    assert said.startswith("shell wall thickness: its thinnest walls") and "shell_wall" not in said
    assert answers and design_api and params


def test_after_a_rebuild_the_part_is_called_by_its_name_or_this_part():
    assert "check {'the ' + label if label else 'this part'} again" in open(params.__file__).read()


@pytest.mark.parametrize("name", ["C:\\dock", "lid\\1", "a\\g<0>b"])
def test_a_backslash_in_a_name_is_just_a_character(name):
    assert tree.relabelled(_S({"p": {"top": name}}), "p", "cut the top first") == f"cut the {name} first"


def test_a_piece_name_doesn_t_change_ordinary_words():
    labels = _S({"p": {"front": "door"}})
    assert tree.relabelled(labels, "p", "sitting on the front edge") == "sitting on the front edge"
    assert tree.relabelled(labels, "p", "the front: cut it first") == "the door: cut it first"


def test_the_cards_call_a_piece_what_it_was_renamed_to(tmp_path, monkeypatch):
    from caliper import shop
    from caliper.design import DesignStore

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    monkeypatch.setenv("CALIPER_SLICER", "")
    shop.write({"hand": ["drill"], "machines": []})             # no printer: the make card names the piece
    s = DesignStore.create("a thing", base=str(tmp_path / "designs"))
    s.write_part("t", """import cadquery as cq

def build(params):
    return cq.Workplane('XY').box(20, 20, 20)

def construction(params, build=None):
    return [{"name": "cone skirt", "kind": "printed", "material": "petg"}]
""", intent="a thing")
    s.design.piece_labels = {"t": {"cone skirt": "the shell"}}
    s.save()
    cards = answers.part(s, design_api.design_state(s), "t")
    how = next(c for c in cards if c["key"] == "make")
    words = " ".join(ln["text"] for ln in how["lines"])
    assert "the shell" in words and "cone skirt" not in words


def test_the_banner_says_older_only_when_it_is():
    assert "${run.version !== partOf(pid).version ? `· <b style=\"color:var(--amber)\">from v${run.version}" in _fn(open(JS).read(), "showHeat")


_SEND = """
const els = {}; const $ = (id) => (els[id] = els[id] || {});
let S = { slug: 'a', busy: false, opening: null, pick: { said: 'edge', id: 'e1' } };
const PICK = { turn: 0, overlay: null }; const scene = { remove() {} };
const createDesign = () => {}; const liveTurn = () => ({ step() {}, fail() {} });
const api = async () => ({ job_id: 'j' }); const refresh = async () => { seen.push(S.pick && S.pick.id); };
const seen = []; let end, die; const follow = () => new Promise((r, x) => { end = r; die = x; });
const tick = () => new Promise((r) => setImmediate(r));
"""


def _send(body):
    src = open(JS).read()
    script = _SEND + _fn(src, "clearPick") + _fn(src, "send") + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_pick_stays_while_it_s_answered_and_goes_once_it_s_used():
    assert _send("""const go = send('x', 's', null, 'shown'); await tick(); const during = S.pick.id; end(); await go;
                    return { during, after: S.pick };""") == {"during": "e1", "after": None}


def test_a_pick_made_during_the_reply_is_kept():
    assert _send("""const go = send('x', 's', null, 'shown'); await tick(); S.pick = { said: 'other', id: 'e2' }; end(); await go;
                    return { after: S.pick.id };""") == {"after": "e2"}


def test_after_a_chat_error_the_pick_stays():
    assert _send("""const go = send('x', 's', null, 'shown'); await tick(); die(new Error('no')); await go;
                    return { after: S.pick.id };""") == {"after": "e1"}

