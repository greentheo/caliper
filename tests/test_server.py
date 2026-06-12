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


def test_list_runs_empty_when_no_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    r = _client().get("/api/runs")
    assert r.status_code == 200 and r.json()["runs"] == []


def test_get_unknown_run_404(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    assert _client().get("/api/runs/run_9999").status_code == 404


def test_recent_list_and_load(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    c = _client()
    c.post("/api/run", json={"intent": "a 60 mm corner bracket with four M5 holes",
                             "no_llm": True, "max_iter": 1})
    # list shows the run with metadata
    runs = c.get("/api/runs").json()["runs"]
    assert len(runs) == 1
    item = runs[0]
    assert item["run_id"] == "run_0000"
    assert item["part"] == "corner_bracket"
    assert item["stl_url"] and "four M5 holes" in item["label"]

    # load it back without rebuilding: spec + structured report + stl
    got = c.get("/api/runs/run_0000").json()
    assert "corner_bracket" in got["spec_yaml"]
    assert any(r["id"] == "bolt_pattern" for r in got["report"]["results"])
    assert got["stl_url"] == "/api/runs/run_0000/part.stl"


def test_refine_unrecognized_returns_422(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    c = _client()
    run = c.post("/api/run", json={"intent": "a 60 mm bracket with four M5 holes",
                                   "no_llm": True, "max_iter": 1})
    rid = run.json()["run_id"]
    bad = c.post("/api/refine", json={"run_id": rid, "instruction": "make it prettier"})
    assert bad.status_code == 422
