"""CALI-110 (#110; rule 6) — the scorecard and the build book never call an unresolved strength ✓ a pass.

#100 made both cards read "Not resolved yet…" when a ✓ rests on an FEA too coarse to see the wall; the scorecard
still scored it pass, so the Studies row was green and the build book said "Ready to cut — 2 of 2 checks pass"."""

import html
import os

import pytest

from caliper import load_study, release, scorecard, studies
from caliper.design import DesignStore

from .test_consistency import STOOL
from .test_load_study import LOADS
from .test_resolved import GOALS, TUBE

pytest.importorskip("cadquery")

#: The test stool under a light load: every case holds. At one voxel through its 3/4 in panels, the shove (side-on,
#: so the FEA governs it) is a ✓ the voxels can't see the wall for; at four, it's resolved.
LIGHT = STOOL + LOADS.replace('"lb": 200', '"lb": 40').replace('"force": (0, 300, 0)', '"force": (0, 100, 0)')
STOOL_GOALS = GOALS.replace("strength_foot", "strength_step").replace("holds a foot (40 lb)", "holds a step (40 lb)")


def _store(tmp_path, monkeypatch, src, pid, through, goals):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    store = DesignStore.create("a part", base=str(tmp_path / f"designs{through}"))
    store.write_part(pid, src, intent="a part")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(goals)
    return store, load_study.study(store, pid)


def test_the_fixture_is_what_it_says(tmp_path, monkeypatch):
    store, rec = _store(tmp_path, monkeypatch, LIGHT, "stool", 1, STOOL_GOALS)
    assert rec["holds"] and any(load_study.unresolved(rec, c) and c["holds"] for c in rec["cases"])


def test_an_unresolved_check_is_never_a_pass_or_ready(tmp_path, monkeypatch):
    """The reviewer's tube at 4 mm voxels: strength_foot read pass, and the summary 2 pass, 0 unknown."""
    store, rec = _store(tmp_path, monkeypatch, TUBE, "tube", 1, GOALS)
    assert not rec["resolved"] and rec["holds"]
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_foot"]
    assert check["status"] == "unresolved" and check["note"].startswith("Not resolved yet")
    assert card["summary"]["pass"] == 0 and card["summary"]["unresolved"] == 1 and card["summary"]["unknown"] == 1
    text, ok = studies._headline("scorecard", card)
    assert ok is False and "1 not resolved" in text                  # the Studies row isn't green
    status = release._status(card)                                   # (the printed tube's shop check fails too)
    assert status.startswith('<span class="status notready">Not ready —') and "1 not resolved" in status, status
    alone = {"summary": {"pass": 1, "fail": 0, "unknown": 1, "untrusted": 0, "unresolved": 1}}   # nothing else wrong
    assert studies._headline("release", {"id": "001", "ready": False, "card": alone})[0].startswith(
        "release 001 · not ready: a strength check isn't resolved")


def test_the_same_tube_seen_finely_passes_and_is_ready(tmp_path, monkeypatch):
    store, rec = _store(tmp_path, monkeypatch, TUBE, "tube", 4, GOALS)
    assert rec["resolved"]
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_foot"]
    assert check["status"] == "pass" and card["summary"].get("unresolved") == 0
    assert "not resolved" not in release._status(card) and "not resolved" not in studies._headline("scorecard", card)[0]


def test_a_fail_on_coarse_voxels_stays_a_fail(tmp_path, monkeypatch):
    store, rec = _store(tmp_path, monkeypatch, TUBE.replace('"lb": 40', '"lb": 2000'), "tube", 1, GOALS)
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_foot"]
    assert check["status"] == "fail" and card["summary"].get("unresolved") == 0


def test_the_books_promise_nothing_on_it(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, rec = _store(tmp_path, monkeypatch, LIGHT, "stool", 1, STOOL_GOALS)
    strength = release._strength(store, {"stool": store.design.part("stool").version})
    assert any(c["unresolved"] and c["holds"] for c in strength["stool"])
    made = release.make(store, pdf=False)
    assert not made["ready"]
    root = os.path.join(release.releases_dir(store), made["id"])
    page = open(os.path.join(root, "index.html")).read()
    assert "Not ready — 1 not resolved" in page and "Ready to cut" not in page
    row = page.split("Will it hold?")[1].split("</table>")[0]
    assert "not resolved: too coarse to see its walls" in row, row
    book = html.unescape(open(os.path.join(root, "kids.html")).read())
    assert "It should hold" not in book and "Don't stand on it yet" in book


def test_seen_finely_the_book_is_ready_and_the_kid_s_book_says_it_holds(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, rec = _store(tmp_path, monkeypatch, LIGHT, "stool", 4, STOOL_GOALS)
    assert not any(load_study.unresolved(rec, c) for c in rec["cases"])
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    book = html.unescape(open(os.path.join(root, "kids.html")).read())
    assert made["ready"] and "It should hold" in book and "Don't stand on it yet" not in book


def test_the_test_it_panel_and_the_chat_say_the_number_isn_t_resolved(tmp_path, monkeypatch):
    """The audit's other two readers: the trial's prediction and the facts the chat answers from."""
    from caliper import chat, trials

    store, rec = _store(tmp_path, monkeypatch, TUBE, "tube", 1, GOALS)
    assert trials.predict(store, "tube")["basis"].startswith("from an FEA too coarse to see its walls")
    assert "NOT RESOLVED: the voxels were too coarse to see its walls" in chat._facts(store, None)
    fine, _ = _store(tmp_path, monkeypatch, TUBE, "tube", 4, GOALS)
    assert not trials.predict(fine, "tube")["basis"].startswith("from an FEA too coarse")



def test_the_design_card_s_scorecard_line_names_it(tmp_path):
    """Merged with #103's card line: an unresolved check reads "not resolved", apart from "not checked yet"."""
    from caliper import answers

    store = DesignStore.create("a tube", base=str(tmp_path / "designs"))
    state = {"parts": [{"id": "tube", "version": 1, "role": "movable"}], "prompt": "a tube", "name": "t",
             "scorecards": [{"summary": {"pass": 1, "fail": 0, "unknown": 2, "untrusted": 0, "unresolved": 1},
                             "checks": [], "versions": {}}], "goals": {"checks": []}, "load_runs": []}
    (line,) = [c for c in answers.design(store, state) if c["key"] == "work"][0]["lines"][:1]
    assert line == {**line, "text": "1 check pass, 1 not resolved, 1 not checked yet.", "status": "warn"}


# --- the four places the reviewer found still saying "holds" (#111 review) ---------------------------------------
JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _fn(src, name):
    import re

    m = re.search(rf"^(async )?function {name}\(.*?^}}\n", src, re.S | re.M)
    assert m, name
    return m.group(0)


def test_the_picture_reply_never_says_it_still_holds_on_an_unresolved_check():
    from caliper import pictures

    got = {"subject": "T. rex", "size_in": [6.0, 4.0], "panel": "front", "safety": 3.5, "min_safety": 2,
           "holds": True, "unresolved": True, "too_thin": False}
    text = pictures.reply(got)
    assert "still holds" not in text and "times over" not in text
    assert text.endswith("so a grown-up checks it again finer before anyone stands on it.")
    assert pictures.reply({**got, "too_thin": True}).endswith(
        "a grown-up checks it again by hand or with a printed test piece before anyone stands on it.")
    assert "It still holds, 3.5 times over" in pictures.reply({**got, "unresolved": False})


def test_the_make_card_names_why_a_book_isn_t_ready():
    from caliper import answers

    def why(**s):
        return answers._why_not({"card": {"summary": {"fail": 0, "untrusted": 0, "unresolved": 0, **s}}})
    assert why(unresolved=1) == "a strength check isn't resolved"
    assert why(untrusted=1) == "a check isn't trusted yet" and why(fail=1) == "a check fails"


def test_the_history_line_says_not_resolved(tmp_path, monkeypatch):
    import json
    import shutil
    import subprocess

    store, rec = _store(tmp_path, monkeypatch, TUBE, "tube", 1, GOALS)
    h = store.history("tube")[-1]
    assert h["kind"] == "load" and h["holds"] and h["unresolved"] is True
    fine, _ = _store(tmp_path, monkeypatch, TUBE, "tube", 4, GOALS)
    assert "unresolved" not in fine.history("tube")[-1]
    node = shutil.which("node") or os.path.expanduser("~/.nvm/versions/node/v22.17.1/bin/node")
    if not os.path.exists(node):
        pytest.skip("no node")
    script = "const esc = (s) => String(s);\n" + _fn(open(JS).read(), "historyItem") + (
        f"console.log(JSON.stringify([historyItem({json.dumps(h)}), historyItem({json.dumps(fine.history('tube')[-1])})]));")
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert "strength check: not resolved" in got[0] and "holds" not in got[0]
    assert "strength check: holds" in got[1]


def test_the_stress_callout_has_no_holds_or_breaking_load_for_it():
    src = _fn(open(JS).read(), "showHeat")
    assert "caveat(c)" in src and "${c.breaks_lb && !caveat(c) ?" in src     # one helper for every such ✓ (#106)
    page = open(JS).read()
    assert "c.unresolved ? coarseWord(c)" in page.split("const caveat = ", 1)[1].split("\n", 1)[0]
