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
                                       ("the seat tops", "the seat tops"), ("a seat topper", "a seat topper")])
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


def test_a_pick_stays_after_a_chat_error_and_goes_once_it_s_used():
    src = _fn(open(JS).read(), "send")
    assert src.index("if (shown) clearPick();") < src.index("catch (e)")
    assert "if (S.pick) { clearPick(); renderScope(); }" not in open(JS).read()


def test_folding_a_panel_repaints_where_its_job_is_said():
    assert "addEventListener('toggle', paintJobs, true)" in open(JS).read()


def test_the_lighten_line_doesn_t_read_as_if_it_was_carved():
    src = open(studies.__file__).read()
    assert "printed parts get carved instead, not lightened with holes" in src and "its printed part is carved" not in src


def test_the_test_plan_stops_where_it_should_break(tmp_path):
    src = open(trials.__file__).read()
    assert "math.ceil(breaks)" in src


def test_a_rule_is_named_in_words():
    from caliper import part_rules

    said = part_rules._said({"id": "shell_wall_thickness", "expr": "min_wall >= 2.85", "actual": 0.25, "status": "fail"}, None, True)
    assert said.startswith("shell wall thickness: its thinnest walls") and "shell_wall" not in said
    assert answers and design_api and params


def test_after_a_rebuild_the_part_is_called_by_its_name():
    assert "getattr(store.design.part(pid), 'label', None) or pid.replace('_', ' ')" in open(params.__file__).read()

