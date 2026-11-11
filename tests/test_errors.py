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


def test_errors_recorded_at_once_are_all_kept(tmp_path, monkeypatch):
    """CALI-92 (#70 item 12): record() had no lock, and every writer shared one ".tmp": two at once could lose one,
    or raise. A lock, and a temporary name of each writer's own."""
    import threading

    monkeypatch.setenv("CALIPER_ERRORS", str(tmp_path / "errors.jsonl"))
    real_open = open
    gate = threading.Barrier(8)

    def slow_open(path, *a, **k):                  # every writer reaches its write together
        if str(path).endswith(".tmp") or ".tmp" in os.path.basename(str(path)):
            try:
                gate.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", slow_open)
    said = []
    threads = [threading.Thread(target=lambda k=k: said.append(errors.record("a job", f"boom {k}")["id"])) for k in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    monkeypatch.setattr("builtins.open", real_open)
    kept = {e["id"] for e in errors.recent(50)}
    assert len(said) == 8 and set(said) <= kept, (said, kept)


def test_a_running_jobs_error_is_scrubbed_as_a_report_is(tmp_path, monkeypatch):
    """CALI-92 (#70 item 18): a job's live error, which the page shows, was str(e): a server's paths, once hosted."""
    from caliper.jobs import JobRunner

    monkeypatch.setenv("CALIPER_ERRORS", str(tmp_path / "errors.jsonl"))
    home = os.path.expanduser("~")

    def boom(job):
        raise ValueError(f"no such file: {home}/designs/garden-bench-for-mum/run.json")

    j = JobRunner().submit("carve", boom)
    _wait(j)
    assert j.status == "error" and home not in j.error and "garden-bench" not in j.error, j.error
    assert j.error.startswith("ValueError: no such file: ~/designs/<design>"), j.error


def test_a_failed_chat_turns_reply_is_the_plain_sentence_with_its_id(tmp_path, monkeypatch):
    """CALI-92 (#70 item 18): the log's reply was the raw "I couldn't do that: {type}: {e}"."""
    from fastapi.testclient import TestClient

    from caliper import chat, design_api
    from caliper.design import DesignStore
    from caliper.jobs import JobRunner
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_ERRORS", str(tmp_path / "errors.jsonl"))
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    runner = JobRunner()
    monkeypatch.setattr(design_api, "RUNNER", runner)
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))

    def broken(*a, **k):
        raise ValueError("/Users/someone/secret went wrong")

    monkeypatch.setattr(chat, "turn", broken)
    slug = os.path.basename(store.root)
    r = TestClient(create_app()).post(f"/api/designs/{slug}/chat", json={"message": "make it taller"})
    assert r.status_code == 200, r.text
    j = runner.get(r.json()["job_id"])
    _wait(j)
    reply = [x for x in DesignStore.load(slug).log() if x.get("kind") == "reply"][-1]["reply"]
    assert reply == errors.plain({"id": j.error_id}) and "secret" not in reply, reply
    assert len([e for e in errors.recent(50) if e["id"] == j.error_id]) == 1 and len(errors.recent(50)) == 1   # kept once


@pytest.mark.parametrize("secret", ["sk-ant-api03-AbCdEf0123456789_xyz-ABCDEFG", "sk-proj-abcdef0123456789abcdef",
                                    "ghp_abcdefghijklmnopqrstuvwxyz0123456789", "github_pat_11ABCDE0_abcdefghij1234567890",
                                    "gho_abcdefghijklmnopqrstuvwxyz0123456789", "xoxb-1234567890-abcdefghij",
                                    "AKIAIOSFODNN7EXAMPLE"])
def test_a_key_or_token_never_reaches_a_report_or_the_page(secret):
    """#215 review: errors.scrub covered home folders and design names only: a key in an exception's text went
    into job.error and the stored report."""
    said = errors.scrub(f"401 from the API with key {secret} (try again)")
    assert secret not in said and "<secret>" in said and said.endswith("(try again)"), said


def test_a_key_set_in_the_environment_is_scrubbed_whatever_it_looks_like(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "plainlookingvalue123")
    assert "plainlookingvalue123" not in errors.scrub("sent plainlookingvalue123 to the API")


def test_ordinary_words_are_left_alone():
    text = "ValueError: the task-ant skeleton and sk-8 board don't fit"
    assert errors.scrub(text) == text


KEY = "sk-ant-api03-AbCdEf0123456789_xyz"


def test_the_live_event_through_the_jobs_route_carries_no_path_and_no_key(tmp_path, monkeypatch):
    """#215 review: job.error was scrubbed, but the event beside it carried the raw last line of the trace."""
    from fastapi.testclient import TestClient

    from caliper import jobs, server

    monkeypatch.setenv("CALIPER_ERRORS", str(tmp_path / "errors.jsonl"))
    home = os.path.expanduser("~")

    def boom(job):
        raise ValueError(f"{home}/secret/path.py with {KEY}")

    j = jobs.RUNNER.submit("carve", boom, lock="design:scrub")
    _wait(j)
    got = TestClient(server.create_app()).get(f"/api/jobs/{j.id}").json()
    text = str(got)
    assert home not in text and KEY not in text and "secret/path.py" in text, text
    assert [e for e in got["events"] if e["kind"] == "error"][0]["trace"].startswith("ValueError: ~/secret/path.py")


def test_a_raw_exception_in_a_first_build_or_a_chat_reply_is_scrubbed(tmp_path, monkeypatch):
    from caliper import carve, chat, firstrun, goals
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path))
    home = os.path.expanduser("~")

    def boom(*a, **k):
        raise ValueError(f"{home}/x with {KEY}")

    heard = []
    monkeypatch.setattr(goals, "update", boom)
    monkeypatch.setattr(firstrun, "_author", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop here")), raising=False)
    try:
        firstrun.build(store, emit=lambda k, t="", **d: heard.append(t), strength=False, use_llm=False)
    except Exception:  # noqa: BLE001 — only what it said before stopping is under test
        pass
    told = [t for t in heard if t.startswith("couldn't write down")]
    assert told and KEY not in told[0] and home not in told[0], heard
    monkeypatch.setattr(carve, "study", boom)
    store.write_part("p", "def build(params):\n    return None\n", intent="x")
    got = chat.carve_part(store, "p")
    assert KEY not in got.reply and home not in got.reply and KEY not in got.error, got.reply
