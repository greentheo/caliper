"""CALI-219 (#367): the nightly tail, held to the list the issue agreed, and the per-PR set never losing a guard.

A PR's CI runs `-m "not nightly"`; the scheduled run (09:17 UTC, or by hand) runs everything. The tail is the tests that are
long and that no verdict or safety rule rests on, agreed on #367 with the studies lane (night shift), "when in doubt it
stays". A test can't drift in: a new `nightly` mark changes this list, in review."""
import ast
import os

import yaml

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

#: The tail, as agreed on #367 (night shift vetoed test_lighten_solves_each_step_s_cases_once: it guards #357's one solve;
#: #412's review kept two more, the only per-PR guards of a rule)
NIGHTLY = {
    ("test_server", "test_fit_end_to_end"),
    ("test_cli", "test_fit_end_to_end"),
    ("test_spatial", "test_two_threads_on_one_mesh_dont_take_the_app_down"),
    ("test_pictures", "test_a_drawing_from_the_pad_is_cut_out"),
    ("test_cases_together", "test_the_progress_line_says_together_only_where_they_are"),
    ("test_guards_had_no_test", "test_the_order_of_a_kids_book_doesnt_depend_on_the_hash_seed"),
    ("test_release", "test_releases_are_numbered_and_reuse_whats_current"),
}
#: Guards of a verdict or a safety number: per-PR, always (night shift's list on #367)
KEEP_FILES = {"test_lighten_own_material", "test_own_material_fea", "test_mixed", "test_check_own_frame", "test_lighten_vs_now"}
KEEP_TESTS = {
    # the only per-PR guards of a rule (#412 review): Lighten's web round a picture (MIN_WEB_MM), and the step a cancelled
    # carve offers (the lightest that holds)
    ("test_pictures", "test_lightening_leaves_a_picture_alone"),
    ("test_carve_click", "test_a_cancelled_carve_keeps_the_steps_it_finished"),
} | {("test_cases_together", n) for n in (
    "test_a_holed_panel_s_filled_solve_reads_its_own_case_as_main_does", "test_each_lighten_step_s_cases_are_solved_on_its_cut_not_the_part",
    "test_the_joints_of_every_case_read_as_each_alone", "test_every_case_together_is_bit_for_bit_each_alone",
    "test_lighten_solves_each_step_s_cases_once")}


def _marked():
    out = set()
    for f in sorted(os.listdir(HERE)):
        if not (f.startswith("test_") and f.endswith(".py")):
            continue
        tree = ast.parse(open(os.path.join(HERE, f)).read())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(ast.unparse(d) in ("pytest.mark.nightly", "mark.nightly") for d in node.decorator_list):
                    out.add((f[:-3], node.name))
            if isinstance(node, ast.Assign) and any(ast.unparse(t) == "pytestmark" for t in node.targets) \
                    and "nightly" in ast.unparse(node.value):
                out.add((f[:-3], "*"))                                  # a whole file: never, unless it's agreed here
    return out


def test_the_nightly_tail_is_the_agreed_list():
    assert _marked() == NIGHTLY


def test_no_guard_of_a_verdict_or_a_safety_number_leaves_the_per_pr_run():
    marked = _marked()
    assert not {m for m in marked if m[0] in KEEP_FILES} and not (marked & KEEP_TESTS)


def test_the_marker_is_declared():
    import tomllib

    markers = tomllib.load(open(os.path.join(ROOT, "pyproject.toml"), "rb"))["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("nightly:") for m in markers)


def test_ci_runs_the_tail_only_on_the_schedule_or_by_hand():
    path = os.path.join(ROOT, ".github", "workflows", "tests.yml")
    w = yaml.safe_load(open(path))
    on = w.get("on", w.get(True))
    assert on["schedule"] and "workflow_dispatch" in on and "pull_request" in on
    assert "github.event_name" in w["concurrency"]["group"]                  # a push never cancels the night's run
    steps = {s.get("name", ""): s.get("run", "") for s in w["jobs"]["pytest"]["steps"]}
    pick = next(v for k, v in steps.items() if k.startswith("Which tests"))
    assert 'echo "TAIL= and not nightly"' in pick and "schedule" in pick and "workflow_dispatch" in pick
    assert '-m "not serial$TAIL"' in steps["Test, across the runner's cores (CALI-114)"]
    assert '-m "serial$TAIL"' in steps["Test what can't share, on its own"]
