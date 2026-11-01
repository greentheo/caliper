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
    assert errors.recent(1)[0]["where"] == "a chat turn"                  # by its kind, never its label

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


def _wait(job):
    import time

    for _ in range(300):
        if job.over:
            return
        time.sleep(0.01)


def test_a_report_always_fits_and_returns(monkeypatch):
    """CALI-86 (#62, finding 3b): an error too long for a link on its own looped forever."""
    import threading

    e = errors.record("w", "é" * 2000, "abc")
    got = {}
    t = threading.Thread(target=lambda: got.update(rep=errors.report(e["id"])), daemon=True)
    t.start()
    t.join(10)
    assert not t.is_alive(), "report() never returned"
    assert len(got["rep"]["url"]) <= errors.MOST_URL and "é" in got["rep"]["body"]


def test_a_failed_chat_turn_is_kept_by_kind_never_by_what_was_said():
    """CALI-86 (#62, finding 3a): a chat job's label is the person's message."""
    from caliper.jobs import JobRunner

    said = "make the step stool taller for Ezra so he reaches the bathroom sink"
    j = JobRunner().submit("chat", lambda job: 1 / 0, label=said[:60])
    _wait(j)
    rep = errors.report(j.error_id)
    assert rep is not None and errors.recent(1)[0]["where"] == "a chat turn"
    words = {w for w in said.lower().split() if len(w) > 3}
    assert not [w for w in words if w in rep["body"].lower() or w in rep["title"].lower()], rep["body"]


def test_a_design_s_name_is_scrubbed_from_paths_and_urls(tmp_path, monkeypatch):
    """CALI-86 (#62, finding 3a): a traceback through designs/<slug>/, or a request to /api/designs/<slug>, names
    the design, and its name is the person's own words."""
    trace = ('File "/srv/caliper/designs/a-step-stool-so-my-6/parts/stool/part.py", line 4\n'
             'File "designs/step-stool/parts/x.py", line 9')
    e = errors.record("POST /api/designs/step-stool/chat", "ValueError: boom", trace)
    assert "step-stool" not in e["trace"] + e["where"] and "a-step-stool-so-my-6" not in e["trace"]
    assert "designs/<design>/parts/stool/part.py" in e["trace"] and e["where"] == "POST /api/designs/<design>/chat"
    custom = tmp_path / "my things"
    monkeypatch.setenv("CALIPER_DESIGNS", str(custom))
    e = errors.record("w", "OSError", f'File "{custom}/garden-bench-for-mum/parts/p.py"')
    assert "garden-bench" not in e["trace"] and "designs/<design>/parts/p.py" in e["trace"]


def test_anyones_home_folder_is_scrubbed():
    """CALI-86 (#69 rework, item 2a): only $HOME was scrubbed; someone else's path came through whole."""
    e = errors.record("w", "OSError: '/Users/sarah/x.py'", 'File "/home/bob/y.py", line 2\nFile "/Users/sarah/z/w.py"')
    assert "sarah" not in e["error"] + e["trace"] and "bob" not in e["trace"]
    assert "~/x.py" in e["error"] and "~/y.py" in e["trace"]


def _client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    return TestClient(create_app(), raise_server_exceptions=False)


def test_a_crash_says_a_plain_sentence_and_the_error_id(tmp_path, monkeypatch):
    """CALI-86 (#69 rework, item 2b): a 500's detail was the raw exception, paths and all."""
    pytest.importorskip("fastapi")
    from caliper.design import DesignStore

    c = _client(tmp_path, monkeypatch)
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", "def build(p):\n    return None\n", intent="a stool")
    from caliper import trials

    def broken(*a, **k):
        raise OSError(13, "Permission denied", "/Users/sarah/y.py")

    monkeypatch.setattr(trials, "compared", broken)
    got = c.get(f"/api/designs/{store.design.slug}/parts/stool/trial")
    assert got.status_code == 500
    body = got.json()
    assert body["error_id"] and body["error_id"] in body["detail"]
    assert "/" not in body["detail"] and "sarah" not in body["detail"] and "Permission" not in body["detail"]


def test_a_yaml_error_keeps_its_line_and_column_but_not_what_it_quotes(tmp_path, monkeypatch):
    """CALI-86 (#69 rework, item 2c): a design.yaml that won't parse put the person's own sentence into the report:
    the reviewer's "a surprise stool for Emma: she turns 6 on friday"."""
    pytest.importorskip("fastapi")
    from caliper.design import DesignStore

    c = _client(tmp_path, monkeypatch)
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    path = os.path.join(store.root, "design.yaml")
    text = open(path).read()
    with open(path, "w") as f:
        f.write(text + "\nprompt: a surprise stool for Emma: she turns 6 on friday\n")
    got = c.get(f"/api/designs/{store.design.slug}")
    assert got.status_code == 500
    rep = c.get(f"/api/errors/report?id={got.json()['error_id']}").json()
    said = (rep["body"] + rep["title"] + rep["url"]).lower()
    for word in ("emma", "surprise", "friday", "turns"):
        assert word not in said, word
    assert "line" in rep["body"] and "column" in rep["body"]


def test_a_failed_job_s_yaml_error_drops_its_excerpt_too():
    import yaml

    from caliper.jobs import JobRunner

    said = {"text": "prompt: a surprise stool for Emma: she turns 6 on friday\n"}

    def bad(job):
        yaml.safe_load(said["text"])                 # the words come from a file, as they would, not from this line

    j = JobRunner().submit("chat", bad, label="x")
    _wait(j)
    e = next(x for x in errors.recent(5) if x["id"] == j.error_id)
    assert "Emma" not in e["error"] + e["trace"] and "line 1, column" in e["error"]
