"""CALI-90 (#66 item 1): a double-clicked Build it. The page's button now disables on click, and first_build's
check (is one running?) and its submit are one step, so two presses at the same instant start one build."""

import os
import threading
import time

from caliper import design_api, firstrun, jobs
from caliper.design import DesignStore


def test_two_build_presses_at_once_start_one_build(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path))
    store = DesignStore.create("a step stool", base=str(tmp_path))
    slug = os.path.basename(store.root)
    runner = jobs.JobRunner()
    monkeypatch.setattr(design_api, "RUNNER", runner)
    go = threading.Event()
    monkeypatch.setattr(firstrun, "build", lambda store, **k: go.wait(5) and {})
    real_get = runner.get

    def slow_get(job_id):                      # the gap between "is one running?" and the submit, made wide
        got = real_get(job_id)
        time.sleep(0.3)
        return got

    monkeypatch.setattr(runner, "get", slow_get)
    ids = []
    presses = [threading.Thread(target=lambda: ids.append(design_api.first_build(slug).id)) for _ in range(2)]
    for t in presses:
        t.start()
    for t in presses:
        t.join(5)
    go.set()
    assert len(ids) == 2 and ids[0] == ids[1], ids                  # one build, followed by both presses
    assert len([j for j in runner._jobs.values() if j.kind == "firstrun"]) == 1


def test_the_build_button_disables_on_click():
    js = open(os.path.join(os.path.dirname(design_api.__file__), "web", "static", "design.js")).read()
    i = js.index("$('buildFirst').onclick")
    assert "disabled = true" in js[i:i + 400], js[i:i + 400]
