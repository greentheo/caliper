"""CALI-136 (#174), before hosting, from #215's review: about 78 raw ``str(e)``/``{e}`` sites reached the page (route details,
results, replies), and ``errors.scrub`` missed a Bearer header, ``https://user:pass@…`` and ``password=…`` unless the value was
also in an environment variable. Everything an exception says, on its way to a person, goes through one place."""

import os
import re

import pytest

from caliper import errors, evaluate
from caliper.spec import Assertion

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "caliper")


@pytest.mark.parametrize("raw, gone", [
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.abc_DEF-123", "eyJhbGciOiJIUzI1NiJ9"),
    ("authorization: bearer abc123def456", "abc123def456"),
    ("failed to reach https://theo:hunter2@example.com/api", "hunter2"),
    ("postgres://admin:s3cr3t@db.internal:5432/caliper", "s3cr3t"),
    ("login with password=hunter2&user=theo", "hunter2"),
    ("config: api_key: abcd1234wxyz", "abcd1234wxyz"),
    ("token=short1 refused", "short1"),
])
def test_scrub_takes_secrets_by_their_shape_not_only_by_the_environment(raw, gone, monkeypatch):
    for name in list(os.environ):
        if re.search(r"KEY|TOKEN|SECRET|PASSWORD", name, re.I):
            monkeypatch.delenv(name, raising=False)        # none of these values is in an environment variable
    said = errors.scrub(raw)
    assert gone not in said and "<secret>" in said, said


def test_scrub_leaves_plain_words_alone():
    assert errors.scrub("the password field is required; use a bearer of good news") == \
        "the password field is required; use a bearer of good news"
    assert errors.scrub("see https://example.com/docs") == "see https://example.com/docs"


def test_a_route_s_detail_is_scrubbed_on_its_way_out():
    """The ~45 route details go through one handler, not each site."""
    pytest.importorskip("fastapi")
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    app = create_app()

    def boom():
        raise HTTPException(status_code=422, detail="could not read /Users/someone/designs/secret-project/x.py "
                                                   "(Authorization: Bearer abcdef0123456789)")

    app.add_api_route("/api/__test_boom", boom, methods=["GET"])
    app.router.routes.insert(0, app.router.routes.pop())                  # ahead of the page's catch-all
    got = TestClient(app).get("/api/__test_boom")
    assert got.status_code == 422
    detail = got.json()["detail"]
    assert "someone" not in detail and "secret-project" not in detail and "abcdef0123456789" not in detail, detail
    assert detail.startswith("could not read ~/designs/<design>"), detail


def test_an_assertion_that_raises_says_it_scrubbed():
    def measure(*a):
        raise ValueError("can't open /Users/someone/thing.step with token=abc123secret")

    got = evaluate.evaluate_assertion(Assertion(id="r", expr="probe() > 0"), {"probe": measure})
    assert got.status == "error" and "someone" not in got.detail and "abc123secret" not in got.detail, got.detail


#: where an exception's own text may stand raw: it's re-raised (the next reader scrubs it), printed to this server's own log, the
#: command line on your own machine, the sandbox's own process (its parent scrubs what comes back), or errors itself
_ALLOWED_FILES = {"cli.py", "errors.py", "_sandbox_runner.py", "_build_worker.py"}
_RAW = re.compile(r"str\((?:e|exc|err)\)|\{(?:e|exc|err)\}")


def test_no_raw_exception_text_on_its_way_to_a_person():
    found = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".py") or name in _ALLOWED_FILES:
            continue
        lines = open(os.path.join(SRC, name)).read().splitlines()
        for i, line in enumerate(lines):
            if not _RAW.search(line) or "scrub" in line:
                continue
            here = line + (lines[i + 1] if i + 1 < len(lines) else "")
            if re.search(r"\braise\b", line) or "sys.stderr" in here:
                continue
            found.append(f"{name}:{i + 1}: {line.strip()[:100]}")
    assert not found, "\n".join(found)
