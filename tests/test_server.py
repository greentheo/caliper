"""CALI-9 (M2) — webapp API. Health + static need no kernel; run/refine are OCCT-gated."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from caliper.server import create_app  # noqa: E402


def _client():
    return TestClient(create_app())


def test_health():
    r = _client().get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_static_index_served():
    r = _client().get("/")
    assert r.status_code == 200
    assert "Caliper" in r.text and "import" in r.text  # the import-map page


def test_refine_unknown_run_404():
    r = _client().post("/api/refine", json={"run_id": "run_9999", "instruction": "8mm holes"})
    assert r.status_code == 404


# --- end-to-end through the kernel ----------------------------------------
def test_run_then_refine_and_stl(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    c = _client()

    run = c.post("/api/run", json={
        "intent": "a 60 mm corner bracket for 2020 extrusion with four M5 holes",
        "no_llm": True, "max_iter": 2,
    })
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["build_ok"] and body["stl_url"]
    assert body["report"]["all_pass"] in (True, False)
    assert any(r["id"] == "bolt_pattern" for r in body["report"]["results"])

    # the STL is downloadable
    stl = c.get(body["stl_url"])
    assert stl.status_code == 200 and stl.headers["content-type"] == "model/stl"
    assert len(stl.content) > 1000

    # refine it
    ref = c.post("/api/refine", json={"run_id": body["run_id"], "instruction": "make the holes 8mm"})
    assert ref.status_code == 200, ref.text
    assert any("8" in str(c) for c in ref.json()["changes"])


def test_refine_unrecognized_returns_422(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    c = _client()
    run = c.post("/api/run", json={"intent": "a 60 mm bracket with four M5 holes",
                                   "no_llm": True, "max_iter": 1})
    rid = run.json()["run_id"]
    bad = c.post("/api/refine", json={"run_id": rid, "instruction": "make it prettier"})
    assert bad.status_code == 422
