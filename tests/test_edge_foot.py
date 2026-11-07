"""CALI-94 (#73; rule 6) — a step is stood on at its front edge, so a load case puts a foot there.

A top resting on only two sides is weakest at its free edge, where a foot spreads over less of it (BS 8110 cl.
3.5.2.2's edge width; NEEDS ENGINEER CHECK). The designer put one foot in the middle, so a stool that fails at its
front edge read as holding, from a load case nobody stands in."""

import pytest

from caliper import answers, consistency, design_api, sandbox
from caliper.design import DesignStore

from .test_consistency import STOOL
from .test_load_study import BOX_STOOL, LOADS

pytest.importorskip("cadquery")

#: The test stool as the designer used to load it: the middle only (and the shove, side-on).
CENTRED = LOADS.replace('''    return [{"name": "stepping on the front edge", "lb": 200, "factor": 2.0,
             "lo": (-50, -d / 2, h - 2), "hi": (50, -d / 2 + 100, h)},
            {"name": "an adult stepping up"''', '''    return [{"name": "an adult stepping up"''')
WARN = ("the top is held on two sides, and no load stands on its free edge, where it's weakest: add a case, the same "
        "foot mid-span with its edge on the free edge (\"stepping on the front edge\")")


def _checks(src):
    run = sandbox.run_script(src, timeout=120)
    return {r.id: r for r in consistency.check(run.declared, run.geometry)}


def test_the_fixtures_are_what_they_say():
    assert CENTRED != LOADS and "stepping on the front edge" in LOADS and "front edge\"" not in CENTRED


def test_a_two_sided_top_with_only_a_centred_foot_gets_a_warning_and_still_passes():
    got = _checks(STOOL + CENTRED)
    edge = got["loads_edge"]
    assert edge.passed and edge.status == "pass" and edge.detail == WARN       # a warning: the round passes
    assert got["loads_land"].passed


def test_with_a_foot_at_the_edge_there_s_no_warning_and_it_lands():
    got = _checks(STOOL + LOADS)
    assert got["loads_edge"].passed and got["loads_edge"].detail == ""
    assert got["loads_land"].passed, got["loads_land"].detail                # the edge case is on the top


def test_a_top_held_all_round_keeps_its_one_centred_foot():
    assert "loads_edge" not in _checks(BOX_STOOL)


def test_the_part_card_says_what_s_missing(tmp_path):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", STOOL + CENTRED, intent="a step stool")
    lines = answers.answers(store, design_api.design_state(store), "stool")[0]["lines"]
    assert {"text": WARN[0].upper() + WARN[1:] + ".", "status": "warn", "study": "load"} in lines
    store.write_part("stool", STOOL + LOADS, intent="a step stool")
    lines = answers.answers(store, design_api.design_state(store), "stool")[0]["lines"]
    assert not [ln for ln in lines if "free edge" in ln["text"]]


def test_the_designer_is_told_to_put_a_foot_there():
    import os

    import caliper

    text = open(os.path.join(os.path.dirname(caliper.__file__), "part_scripts.md")).read()
    assert '"stepping on the front edge", the same foot mid-span with its edge on the free edge' in text
    assert "A top held all round keeps the one centred foot." in text


# --- #106 review: a ✓ from the middle only isn't one, on any card, the scorecard or the books -------------------
from .test_mixed import CENTRED as MIXED_CENTRED, MIXED  # noqa: E402

KID_GOALS = """written_by: caliper
checks:
- id: strength_kid
  label: holds a kid stepping up (60 lb), 2 times over
  metric: strength.safety
  op: '>='
  limit: 2.0
  source: assumed
"""


def _kid(tmp_path, monkeypatch, src, name):
    import os

    from caliper import load_study

    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a stool", base=str(tmp_path / name))
    store.write_part("stool", src.replace('"lb": 200', '"lb": 60').replace("an adult", "a kid"), intent="kid")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(KID_GOALS)
    return store, load_study.study(store, "stool")


def test_a_top_on_printed_sides_with_only_a_middle_foot_gets_the_warning():
    """The printed-rest path (the solid under the top holds it), which #106 had no test for."""
    edge = _checks(MIXED_CENTRED)["loads_edge"]
    assert edge.passed and edge.detail == WARN
    assert _checks(MIXED)["loads_edge"].detail == ""


def test_a_middle_only_tick_reads_warn_everywhere_and_isn_t_a_pass(tmp_path, monkeypatch):
    """The reviewer's case: MIXED at 60 lb, the middle foot only, read ✓ "Holds a kid stepping up, 2.2 times over"."""
    from caliper import consistency, release, scorecard, studies

    store, rec = _kid(tmp_path, monkeypatch, MIXED_CENTRED, "middle")
    assert rec["holds"]                                              # the middle foot alone holds
    assert consistency.bare_edge(store, "stool") == WARN
    part = [ln for ln in answers.answers(store, design_api.design_state(store), "stool")[1]["lines"]
            if ln.get("study") == "load"]
    assert part and all(ln["status"] == "warn" for ln in part), part
    assert part[0]["text"] == "Holds a kid stepping up in the middle: " + consistency.MIDDLE_ONLY + "."
    design = [ln for ln in answers.answers(store, design_api.design_state(store))[1]["lines"] if ln.get("study") == "load"]
    assert design and all(ln["status"] == "warn" and "checked in the middle only" in ln["text"].lower() for ln in design), design
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_kid"]
    assert check["status"] == "edge" and card["summary"]["edge"] == 1 and card["summary"]["pass"] < len(card["checks"])
    assert "1 checked in the middle only, not at the front edge" in release._status(card)
    assert studies._headline("scorecard", card)[1] is False
    # what the build book's Will it hold? row and the kid's book read: no "holds" from it either
    strength = release._strength(store, {"stool": store.design.part("stool").version})
    assert all(c["edge"] for c in strength["stool"]) and any(c["holds"] for c in strength["stool"])


def test_with_its_front_edge_foot_the_same_stool_is_a_fail_and_stays_one(tmp_path, monkeypatch):
    store, rec = _kid(tmp_path, monkeypatch, MIXED, "edge")
    edge, middle = rec["cases"]
    assert not edge["holds"] and edge["safety"] == pytest.approx(1.91, abs=0.05) and middle["holds"]
    from caliper import consistency

    assert consistency.bare_edge(store, "stool") is None
    part = [ln for ln in answers.answers(store, design_api.design_state(store), "stool")[1]["lines"]
            if ln.get("study") == "load"]
    assert part[0]["status"] == "bad" and part[0]["text"].startswith("Doesn't hold stepping on the front edge"), part


# --- #106 review, round 2: the panel, the callout, the history, the picture reply and the chat's facts ----------
def test_no_reader_says_holds_on_the_middle_only(tmp_path, monkeypatch):
    import json
    import os
    import re
    import shutil
    import subprocess

    from caliper import chat, pictures

    store, rec = _kid(tmp_path, monkeypatch, MIXED_CENTRED, "middle")
    # the page's state marks each case, and the history the study wrote says it
    (shown,) = design_api.design_state(store)["load_runs"]
    assert all(c.get("middle_only") for c in shown["cases"])
    h = store.history("stool")[-1]
    assert h["kind"] == "load" and h["holds"] and h["middle_only"] is True
    # the chat answers from facts that say so
    assert "CHECKED IN THE MIDDLE ONLY" in chat._facts(store, None)
    # the picture reply (kid-facing)
    text = pictures.reply({"subject": "T. rex", "size_in": [6.0, 4.0], "panel": "front", "safety": 2.2,
                           "min_safety": 2, "holds": True, "middle_only": True})
    assert "still holds" not in text and "times over" not in text and "a grown-up checks it" in text
    # the page: the badges, the run's word and the history line, run in node; the callout asks the same caveat()
    node = shutil.which("node") or os.path.expanduser("~/.nvm/versions/node/v22.17.1/bin/node")
    if not os.path.exists(node):
        pytest.skip("no node")
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    consts = "".join(re.search(rf"^const {n} = .*?;\n(?=\S)", src, re.M | re.S).group(0)
                     for n in ("coarseWord", "caveat", "caseBadge", "runCoarse", "runBadge", "runWord"))
    hist = re.search(r"^function historyItem\(.*?^}\n", src, re.S | re.M).group(0)
    script = "const esc = (s) => String(s);\n" + consts + hist + (
        f"const run = {json.dumps(shown)}, c = run.cases[0];\n"
        f"console.log(JSON.stringify([caseBadge(c), runBadge(run), runWord(run), historyItem({json.dumps(h)})]));")
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert got[:3] == ['<span class="badge warn">middle only</span>', '<span class="badge warn">middle only</span>',
                       "middle only"], got
    assert "strength check: checked in the middle only" in got[3] and "holds" not in got[3]
    callout = re.search(r"^async function showHeat\(.*?^}\n", src, re.S | re.M).group(0)
    assert "caveat(c)" in callout and "${c.breaks_lb && !caveat(c) ?" in callout


def test_the_make_card_and_the_scorecard_line_name_the_middle_only():
    """#106 merged with #111: the make card's reason, and the design card's scorecard line, say it."""
    assert answers._why_not({"card": {"summary": {"fail": 0, "untrusted": 0, "unresolved": 0, "edge": 1}}}) \
        == "a strength check skipped the front edge"


def test_the_design_card_s_scorecard_line_counts_it_apart(tmp_path):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    state = {"parts": [{"id": "stool", "version": 1, "role": "movable"}], "prompt": "a stool", "name": "s",
             "scorecards": [{"summary": {"pass": 1, "fail": 0, "unknown": 2, "untrusted": 0, "unresolved": 1, "edge": 1},
                             "checks": [], "versions": {}}], "goals": {"checks": []}, "load_runs": []}
    (line,) = [c for c in answers.design(store, state) if c["key"] == "work"][0]["lines"][:1]
    assert line["text"] == "1 check pass, 1 not resolved, 1 middle only." and line["status"] == "warn"
