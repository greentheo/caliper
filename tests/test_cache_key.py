"""CALI-120 (#128) — the server keys the page's scripts and styles by their contents; no PR bumps a ?v= again."""

import re

import pytest

from caliper import server


@pytest.fixture
def static(tmp_path, monkeypatch):
    (tmp_path / "design.js").write_text("console.log(1);\n")
    (tmp_path / "design.css").write_text("body {}\n")
    (tmp_path / "index.html").write_text('<link href="/design.css?v=dev"><script src="/design.js?v=dev"></script>'
                                         '<script type="importmap">{"three": "/vendor/three/three.module.js"}</script>')
    monkeypatch.setattr(server, "STATIC_DIR", str(tmp_path))
    return tmp_path


def _keys(resp):
    return dict(re.findall(r"/(design\.(?:js|css))\?v=(\w+)", resp.body.decode()))


def test_the_key_is_the_file_s_and_changes_only_when_it_does(static):
    first = _keys(server.keyed_page("index.html"))
    assert first == {"design.js": server.cache_key("design.js"), "design.css": server.cache_key("design.css")}
    assert "dev" not in first.values() and len(first["design.js"]) == 10
    assert _keys(server.keyed_page("index.html")) == first                    # unchanged: the same key
    (static / "design.js").write_text("console.log(2);\n")
    second = _keys(server.keyed_page("index.html"))
    assert second["design.js"] != first["design.js"] and second["design.css"] == first["design.css"]
    assert "/vendor/three/three.module.js\"" in server.keyed_page("index.html").body.decode()   # untouched


def test_the_served_page_is_keyed_and_never_cached():
    from fastapi.testclient import TestClient

    app = TestClient(server.create_app())
    for path in ("/", "/index.html"):
        got = app.get(path)
        assert got.status_code == 200 and got.headers["cache-control"] == "no-store"
        assert f"/design.js?v={server.cache_key('design.js')}" in got.text and "?v=dev" not in got.text
    assert f"/app.js?v={server.cache_key('app.js')}" in app.get("/classic").text
    assert app.get(f"/design.js?v={server.cache_key('design.js')}").status_code == 200


def test_the_pages_keep_the_placeholder():
    """index.html never changes for a ?v= again: it says dev, and the server sets the key."""
    import os

    for page in ("index.html", "classic.html"):
        html = open(os.path.join(server.STATIC_DIR, page)).read()
        assert re.findall(r"\?v=(\w+)", html) and set(re.findall(r"\?v=(\w+)", html)) == {"dev"}, page
