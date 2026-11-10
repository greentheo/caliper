"""CALI-90 (#66 item 2): jobs had no time limit (a carve ran 874 s at VOXELS_THROUGH=2 in the reviewer's run, and
nothing would ever stop one). A long study now stops at the first step past its limit, keeps the steps it finished,
says why, and isn't logged as a crash; the carve panel says the limit beside how long it's been running."""

import json
import os
import re
import subprocess
import time

from caliper import errors, jobs

from .test_carve_click import _node

JS = os.path.join(os.path.dirname(jobs.__file__), "web", "static", "design.js")


def test_a_study_past_its_limit_stops_at_its_next_step(monkeypatch):
    monkeypatch.setitem(jobs.LIMIT_S, "carve", 0.3)
    recorded = []
    monkeypatch.setattr(errors, "record_exception", lambda *a, **k: recorded.append(a) or {"id": "x"})
    steps = []

    def carve(j):
        for k in range(100):
            time.sleep(0.05)
            j.check()                          # a step boundary
            steps.append(k)
        return "done"

    r = jobs.JobRunner()
    job = r.submit("carve", carve, lock="design:a")
    end = time.time() + 10
    while not job.over and time.time() < end:
        time.sleep(0.02)
    assert job.status == "error" and 3 <= len(steps) < 100, (job.status, len(steps))
    assert "ran past its limit" in job.error and "kept the steps it finished" in job.error, job.error
    assert not recorded and not job.error_id                       # a limit, not a crash: nothing to report
    started = next(e for e in job.since(0) if e["kind"] == "started")
    assert started["limit_s"] == 0.3


def test_every_study_has_a_limit_and_a_chat_doesnt():
    assert all(jobs.LIMIT_S.get(k) for k in jobs.STUDIES)
    assert jobs.LIMIT_S.get("chat") is None


def test_the_carve_panel_says_its_limit_beside_how_long_it_has_run():
    src = open(JS).read()
    ran = re.search(r"^const ran = .*$", src, re.M).group(0)
    minutes = re.search(r"^const minutesText = [\s\S]*?;\n", src, re.M).group(0)
    script = minutes + ran + """
const now = Date.now();
console.log(JSON.stringify([ran({ t0: now - 14 * 60000, limit: 3 * 3600 }), ran({ t0: now - 14 * 60000 })]));
"""
    got = json.loads(subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30,
                                    check=True).stdout)
    assert got[0] == " · running for 14 min (it stops at a step after 3 hours)", got[0]
    assert got[1] == " · running for 14 min"


def test_the_limit_is_six_hours():
    # the sample stool's own carve was quoted at "at least about 3.4 hours": 3 would cut what it's for (#211 review)
    assert jobs.STUDY_LIMIT_S == 6 * 3600 and jobs.LIMIT_S["carve"] == 6 * 3600


def test_a_carve_estimate_past_the_limit_says_so_before_the_click():
    from caliper import better

    within = better.carve_takes({"seconds": 60})                 # 45 min
    assert within == "at least about 45 min at this size"
    past = better.carve_takes({"seconds": 600})                  # 7.5 hours
    assert past.startswith("at least about 7.5 hours at this size")
    assert "past the 6-hour limit" in past and "keeps the steps it finished" in past, past
    assert "past the" not in better.carve_takes({"seconds": 470})   # 5.9 hours: within it


def test_the_clock_starts_when_the_study_takes_its_turn(monkeypatch):
    """#211 review: the limit ran from when the job started, so waiting behind another study counted: with the turn
    held past the limit, a check that never ran ended "it ran past its limit … it kept the steps it finished"."""
    import threading

    from caliper import one_study

    monkeypatch.setitem(jobs.LIMIT_S, "load", 0.5)
    held, go = threading.Event(), threading.Event()

    def holder():
        one_study.take_turn()
        held.set()
        go.wait(5)
        one_study._TURN.release()

    t = threading.Thread(target=holder)
    t.start()
    held.wait(5)
    steps = []

    def study(j):
        one_study.take_turn(stop=j.check)                        # waits 1 s here, past the 0.5 s limit
        try:
            for k in range(3):
                time.sleep(0.05)
                j.check()
                steps.append(k)
        finally:
            one_study._TURN.release()
        return "done"

    r = jobs.JobRunner()
    job = r.submit("load", study, lock="design:b")
    time.sleep(1.0)
    go.set()
    t.join(5)
    end = time.time() + 10
    while not job.over and time.time() < end:
        time.sleep(0.02)
    assert job.status == "done" and steps == [0, 1, 2], (job.status, job.error, steps)

    # and once it has its turn, the limit holds
    def long(j):
        for k in range(100):
            time.sleep(0.05)
            j.check()

    late = r.submit("load", long, lock="design:c")
    end = time.time() + 10
    while not late.over and time.time() < end:
        time.sleep(0.02)
    assert late.status == "error" and "ran past its limit" in late.error


def test_a_carve_that_ran_past_its_limit_says_so_not_cancelled():
    from caliper import studies

    rec = {"kind": "carve", "status": "timed_out", "steps": 7, "best": None, "limit_s": 6 * 3600,
           "stations": [{"index": 0, "safety": 3.0, "holds": True, "whole": 3.0, "whole_holds": True, "saved_g": 0}]}
    text, _ = studies._headline("carve", rec)
    assert text.startswith("stopped at its 6-hour limit after 1 of 7 steps") and "cancelled" not in text, text
