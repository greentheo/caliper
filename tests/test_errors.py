"""CALI-59 (#8) — when something breaks: kept on this machine, reported only if the person sends it."""

import os

import pytest

from caliper import errors


def test_errors_are_kept_newest_first_without_your_home_folder():
    home = os.path.expanduser("~")
    errors.record("chat: make it wider", "ValueError: boom", f'File "{home}/caliper/x.py", line 3')
    e = errors.recent(1)[0]
    assert e["error"] == "ValueError: boom" and home not in e["trace"] and "~/caliper/x.py" in e["trace"]
    for i in range(errors.KEEP + 5):
        errors.record("w", f"E{i}")
    kept = errors.recent(errors.KEEP + 10)
    assert len(kept) == errors.KEEP and kept[0]["error"] == f"E{errors.KEEP + 4}"


def test_a_report_says_what_broke_and_nothing_of_the_design():
    e = errors.record("firstrun: first build", "RuntimeError: the sandbox died", "Traceback…\n" + "x" * 20000)
    rep = errors.report(e["id"])
    assert rep["title"].startswith("Error: RuntimeError") and "the sandbox died" in rep["body"]
    assert "Caliper" in rep["body"] and "Python" in rep["body"]
    assert rep["url"].startswith(errors.ISSUES + "?title=") and len(rep["url"]) <= errors.MOST_URL
    assert errors.report("nope") is None


def test_a_failed_job_and_a_crashed_request_are_both_kept():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.jobs import JobRunner
    from caliper.server import create_app

    r = JobRunner()
    j = r.submit("chat", lambda job: 1 / 0, label="divide")
    for _ in range(200):
        if j.over:
            break
        import time
        time.sleep(0.01)
    assert j.status == "error" and j.error_id and j.to_dict()["error_id"] == j.error_id
    assert errors.recent(1)[0]["where"] == "chat: divide"

    app = create_app()

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    app.router.routes.insert(0, app.router.routes.pop())        # ahead of the static files at /

    c = TestClient(app, raise_server_exceptions=False)
    got = c.get("/api/boom")
    assert got.status_code == 500 and got.json()["error_id"]
    rep = c.get(f"/api/errors/report?id={got.json()['error_id']}").json()
    assert "kaboom" in rep["body"] and "GET /api/boom" in rep["body"]
    seen = c.post("/api/errors", json={"where": "design.js:12", "error": "TypeError: x is undefined"}).json()
    assert c.get(f"/api/errors/report?id={seen['id']}").json()["title"] == "Error: TypeError: x is undefined"
