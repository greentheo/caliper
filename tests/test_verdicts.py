"""CALI-112 (#114; rule 6) — one verdict, asked by every reader.

Not trusted (#96), not resolved (#100/#110), waiting (#103) and middle only (#106) were each added one PR at a time,
and each time a reader that worked the verdict out for itself (``holds``, ``safety >= min_safety``) still said
"holds" or showed green. Every reader now asks ``verdicts``; these tests make a reader that doesn't fail."""

import glob
import json
import os
import re
import shutil
import subprocess

import pytest

from caliper import answers, kidbook, pictures, release, studies, verdicts

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "caliper")
#: What re-derives a verdict: the study's own flag, a safety or a goal's number against what it needs (either way
#: round), a release's ready, a study's best, a rule's holds_now (#132 review: widened so each of its findings fails).
RAW = re.compile(r'\["holds"\]|get\("holds"|\.holds\b|\["whole_holds"\]|get\("whole_holds"|'
                 r'[<>]=?\s*[A-Za-z_.\[\]"\']*min_safety\b|min_safety\b[\]"\')]*\s*[<>]=?\s*[A-Za-z_(]|'
                 r'>=\s*[A-Za-z_.]*\[?"?limit"?\]?|<=\s*[A-Za-z_.]*\[?"?limit"?\]?|[<>]=\s*lim\b|'
                 r'\["ready"\]|get\("ready"\)|\["best"\]|get\("best"\)|holds_now(?!\))')   # holds_now): what verdicts.rule() is handed


def test_no_module_works_a_verdict_out_for_itself():
    """Outside verdicts.py a line that reads ``holds`` or compares a safety with what it needs is a producer (the
    study that sets the flag) or a search (picking the lightest that holds), and says so; any other is a reader."""
    bad = []
    for path in glob.glob(os.path.join(SRC, "*.py")):
        if path.endswith("verdicts.py"):
            continue
        for n, line in enumerate(open(path), 1):
            if RAW.search(line) and "# producer" not in line and "# search" not in line:
                bad.append(f"{os.path.basename(path)}:{n}: {line.strip()}")
    assert not bad, "\n".join(bad)


#: What the page would work out for itself (#132 review: every step, thickness and the classic panel's badge too).
PAGE_RAW = re.compile(r"\.holds\b|whole_holds|safety_across\s*[<>]=|[<>]=\s*run\.min_safety|\.all_pass\s*\?")


def test_the_page_never_works_a_verdict_out_either():
    """design.js and app.js read the server's verdict on every run, case, step, thickness and history line."""
    bad = []
    for name in ("design.js", "app.js"):
        for n, line in enumerate(open(os.path.join(SRC, "web", "static", name)), 1):
            if PAGE_RAW.search(line):
                bad.append(f"{name}:{n}: {line.strip()[:120]}")
    assert not bad, "\n".join(bad)


# --- every kind through every reader -------------------------------------------------------------------------------
RUN = {"id": "r1", "part": "stool", "version": 1, "min_safety": 2.0, "safety": 3.1, "spacing_mm": 2.0,
       "thinnest_mm": 19.05, "across": 9.5, "finer": True}


def _case(**k):
    return {"name": "An adult stepping up", "lb": 200, "factor": 2.0, "safety": 3.1, "governs": "fea",
            "holds": True, "breaks_lb": 1240, **k}


#: Each kind, as a run and case that are it, and the filled-in reason if it's one.
KIND = {
    "holds": (RUN, _case(), None),
    "fails": (RUN, _case(safety=1.2, holds=False), None),
    "untrusted": (RUN, _case(), "the strength check ran on a filled-in shape"),
    "unresolved": ({**RUN, "across": 1.0}, _case(), None),
    "unchecked": ({**RUN, "across": 1.0, "finer": False}, _case(), None),
    "edge": (RUN, _case(middle_only=True), None),
    "waiting": (RUN, _case(safety=None, holds=None), None),
}
HOLDS = re.compile(r"\b[Hh]olds\b|should hold|still holds|✓")


def _verdict(kind):
    run, c, filled = KIND[kind]
    return verdicts.case(run, c, filled=filled)


@pytest.mark.parametrize("kind", list(KIND))
def test_each_kind_is_what_it_says(kind):
    v = _verdict(kind)
    assert v["kind"] == kind
    assert v["counts_as_pass"] is (kind == "holds")
    assert (v["status"] == "ok") is (kind == "holds")


def test_precedence_a_fail_stays_a_fail_then_untrusted_then_unresolved_then_edge():
    coarse = {**RUN, "across": 1.0}
    assert verdicts.case(coarse, _case(safety=1.2, holds=False), filled="block")["kind"] == "fails"
    assert verdicts.case(coarse, _case(middle_only=True), filled="block")["kind"] == "untrusted"
    assert verdicts.case(coarse, _case(middle_only=True))["kind"] == "unresolved"
    assert verdicts.case(RUN, _case(middle_only=True), stale=True)["kind"] == "edge"
    assert verdicts.case(RUN, _case(), stale=True)["kind"] == "stale"
    run = {**RUN, "cases": [_case(), _case(middle_only=True), _case(safety=1.2, holds=False)]}
    assert verdicts.run(run)["kind"] == "fails"
    assert verdicts.run({**RUN, "cases": [_case(), _case(middle_only=True)]})["kind"] == "edge"


@pytest.mark.parametrize("kind", [k for k in KIND if k != "holds"])
def test_no_reader_says_holds_or_shows_green_for_it(kind, tmp_path):
    run, c, filled = KIND[kind]
    v = verdicts.case(run, c, filled=filled)
    said = []
    # the part card's line
    if c.get("safety") is not None:
        ln = answers._case_line("stool", run, c, filled, False, True)
        assert ln["status"] != "ok", ln
        said.append(ln["text"])
    # the build book's Will it hold? row, and the kid's book
    cell, breaks = release._safety_cell({**c, "verdict": v})
    said.append(cell)
    page = kidbook._strength_page({"stool": [{**c, "verdict": v}]})
    assert page["title"] == "Don't stand on it yet", page
    said.append(page["say"])
    # Studies' row
    if c.get("safety") is not None:
        text, ok = studies._headline("load", {**run, "cases": [c], "holds": c["holds"],
                                             **({"filled": True} if filled else {})})
        assert ok is not True, text
        said.append(text)
    # the picture reply
    got = {"subject": "T. rex", "size_in": [6.0, 4.0], "panel": "front", "safety": c.get("safety") or 1.0,
           "min_safety": 2, "verdict": v}
    said.append(pictures.reply(got))
    for text in said:
        assert not HOLDS.search(text.replace("doesn't hold", "")), (kind, text)


def test_a_check_that_holds_reads_as_holding_everywhere():
    run, c, _ = KIND["holds"]
    v = verdicts.case(run, c)
    assert answers._case_line("stool", run, c, None, False, True)["text"].startswith("Holds an adult stepping up")
    assert release._safety_cell({**c, "verdict": v})[0] == "3.1x"
    assert kidbook._strength_page({"stool": [{**c, "verdict": v}]})["title"] == "Test it"
    assert studies._headline("load", {**run, "cases": [c], "holds": True}) == ("holds — weakest An adult stepping up: 3.1x", True)
    assert "It still holds, 3.1 times over" in pictures.reply({"subject": "T. rex", "size_in": [6.0, 4.0],
                                                                "panel": "front", "safety": 3.1, "min_safety": 2,
                                                                "verdict": v})


@pytest.mark.parametrize("status", ["fail", "untrusted", "unresolved", "edge", "unknown", "proposed"])
def test_a_scorecard_check_is_a_tick_only_when_it_passes(status):
    assert "✓" not in release._mark(status)
    assert not verdicts.check(status)["counts_as_pass"]
    assert "✓" in release._mark("pass")


@pytest.mark.parametrize("summary,ready,why", [
    ({"pass": 2, "fail": 0, "unknown": 0}, True, ""),
    ({"pass": 2, "fail": 1, "unknown": 0}, False, "a check fails"),
    ({"pass": 2, "fail": 0, "unknown": 1, "untrusted": 1}, False, "a check isn't trusted yet"),
    ({"pass": 2, "fail": 0, "unknown": 1, "unresolved": 1}, False, "a strength check isn't resolved"),
    ({"pass": 2, "fail": 0, "unknown": 1, "edge": 1}, False, "a strength check skipped the front edge"),
    ({"pass": 2, "fail": 0, "unknown": 1}, False, "a check isn't settled"),
    ({"pass": 0, "fail": 0, "unknown": 0}, False, "a check isn't settled"),        # nothing checked isn't ready
])
def test_one_summary_verdict_for_the_book_studies_and_the_make_card(summary, ready, why):
    card = {"summary": summary, "checks": []}
    assert verdicts.summary(summary)["counts_as_pass"] is ready
    assert ("Ready to cut" in release._status(card)) is ready
    assert studies._headline("scorecard", card)[1] is ready
    if not ready:
        assert answers._why_not({"card": card}) == why


@pytest.mark.parametrize("met,kw,kind", [
    (False, {"untrusted": "block"}, "fails"),                   # a ✗ on a filled-in block is certain: a ✗
    (True, {"untrusted": "block", "unresolved": "coarse"}, "untrusted"),
    (True, {"unresolved": "coarse"}, "unresolved"),
    (True, {"edge": True}, "edge"),
    (True, {}, "holds"),
    (None, {}, "waiting"),
])
def test_a_goal_on_a_metric(met, kw, kind):
    assert verdicts.goal(met, **kw)["kind"] == kind


def test_the_page_s_badges_word_and_history_are_the_verdict_s():
    node = shutil.which("node") or os.path.expanduser("~/.nvm/versions/node/v22.17.1/bin/node")
    if not os.path.exists(node):
        pytest.skip("no node")
    src = open(os.path.join(SRC, "web", "static", "design.js")).read()
    consts = "".join(re.search(rf"^const {n} = .*?;\n(?=\S)", src, re.M | re.S).group(0)
                     for n in ("verdictTone", "verdictBadge", "settled", "caseBadge", "runBadge", "runWord"))
    hist = re.search(r"^function historyItem\(.*?^}\n", src, re.S | re.M).group(0)
    every = {k: _verdict(k) for k in KIND}
    script = ("const esc = (s) => String(s);\n" + consts + hist
              + f"const every = {json.dumps(every)};\n"
              + "console.log(JSON.stringify(Object.fromEntries(Object.entries(every).map(([k, v]) => [k, "
                "[caseBadge({verdict: v}), runBadge({verdict: v}), runWord({verdict: v}), "
                "historyItem({kind: 'load', action: 'studied', safety: 3.1, verdict: v})]]))));")
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30,
                                    check=True).stdout)
    for kind, (badge, rbadge, word, hist_line) in got.items():
        if kind == "holds":
            assert badge == '<span class="badge ok">holds</span>' and "holds" in hist_line
            continue
        assert "badge ok" not in badge + rbadge, (kind, badge)
        assert not HOLDS.search(word.replace("doesn't hold", "")) and not HOLDS.search(
            hist_line.replace("doesn't hold", "")), (kind, word, hist_line)
