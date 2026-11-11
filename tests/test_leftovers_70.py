"""CALI-92 (#70) — the leftovers: the items main still had after the triage of 2026-11-10."""
import re

import pytest

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
