"""CALI-215 (#362): a one-part design opens on its part, so its action bar (Check it holds, #325) is there at first look.

Theo's live test on step-stool-5: the page opened on the design view, which has the part's Parameters but no action bar,
and he couldn't find "Check it holds". The bar's buttons are wired to the part view's own panels, so the design opens
scoped to its one part (never to a lone reference); the design view stays one click away."""
import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _sole(design):
    src = open(JS).read()
    got = subprocess.run([_node(), "-e", _fn(src, "soleFor") + f"\nconsole.log(JSON.stringify({{ r: soleFor({json.dumps(design)}) }}));"],
                         capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)["r"]


@pytest.mark.parametrize("parts,want", [
    ([{"id": "step_stool", "role": "movable"}], "step_stool"),
    ([{"id": "a", "role": "movable"}, {"id": "b", "role": "movable"}], None),
    ([{"id": "car", "role": "fixed"}], None),
    ([], None)])
def test_only_a_one_part_design_opens_on_its_part(parts, want):
    assert _sole({"parts": parts}) == want


_OPEN = """
const calls = []; let S = { slug: null, scope: null, station: null, fixes: {}, fixOpen: null, design: null };
const location = {}; const api = async () => (DESIGN);
const dropBuildFollow = () => {}, clearPick = () => {}, pickHint = () => {}, showLoading = () => {}, doneLoading = () => {}, sayMissed = () => {};
const loadFailed = () => {}; const render = () => calls.push(['render', S.scope]); const syncParts = async () => {};
"""


def _open(design):
    src = open(JS).read()
    script = (_OPEN.replace("DESIGN", json.dumps(design)) + _fn(src, "soleFor") + _fn(src, "openDesign")
              + "\n(async () => { await openDesign('step-stool-5'); console.log(JSON.stringify({ scope: S.scope, calls })); })();")
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_step_stool_5_opens_on_its_part_and_draws_it_so():
    got = _open({"slug": "step-stool-5", "parts": [{"id": "step_stool", "role": "movable"}]})
    assert got == {"scope": "step_stool", "calls": [["render", "step_stool"]]}       # the first draw is the part view


def test_a_two_part_design_still_opens_on_the_design():
    got = _open({"slug": "camper", "parts": [{"id": "frame", "role": "movable"}, {"id": "box", "role": "movable"}]})
    assert got["scope"] is None


def test_the_part_view_is_where_the_bar_is():
    """What the scope buys: partView draws partActions (the bar), designView doesn't."""
    src = open(JS).read()
    assert "${partActions(p)}" in _fn(src, "partView") and "partActions" not in _fn(src, "designView")
