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


def test_gen_authors_and_persists(tmp_path, monkeypatch):
    # CALI-16/17 via the webapp: /api/gen → author/iterate → persist (incl. part.py) → render shape.
    # improve() is monkeypatched to a known geometry+script so the test is deterministic + offline.
    pytest.importorskip("cadquery")
    import trimesh

    import caliper.authoring as authoring
    from caliper.evaluate import AssertionResult, Report
    from caliper.measure import Geometry

    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    script = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(40, 30, 4)\n"

    def fake_improve(spec, **kw):
        geom = Geometry.from_mesh(trimesh.creation.box(extents=(40, 30, 4)))
        report = Report([AssertionResult("solid", "is_watertight", "pass", True, actual=True)])
        return authoring.ImproveResult(ok=True, geometry=geom, script=script, report=report, rounds=2,
                                       history=[("build_error", "x"), ("passed", "")])

    monkeypatch.setattr(authoring, "improve", fake_improve)
    c = _client()
    r = c.post("/api/gen", json={"intent": "a 40x30x4 plate", "max_rounds": 4})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["build_ok"] and body["status"] == "passed" and body["rounds"] == 2
    assert body["script"] == script and body["report"]["all_pass"]
    assert c.get(body["stl_url"]).status_code == 200
    # reloading the run returns the authored script too
    got = c.get(f"/api/runs/{body['run_id']}").json()
    assert got["script"] == script


def test_fit_unknown_run_404():
    r = _client().post("/api/fit", json={"run_id": "run_9999", "reference_b64": ""})
    assert r.status_code == 404


def test_fit_routes_authored_through_author_loop(tmp_path, monkeypatch):
    # CALI-22: fitting an LLM-authored part routes through the author loop (refit_authored, seeded with
    # the existing part.py) and persists a revised part — no longer a 422. refit is faked for determinism.
    pytest.importorskip("cadquery")
    import base64

    import trimesh

    import caliper.authoring as authoring
    from caliper.evaluate import AssertionResult, Report
    from caliper.measure import Geometry

    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    script = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(30, 20, 4)\n"
    d = tmp_path / "runs" / "run_0000"
    d.mkdir(parents=True)
    (d / "spec.yaml").write_text("part: gizmo\n")
    (d / "part.py").write_text(script)

    captured = {}

    def fake_refit(spec, seed, **kw):
        captured["seed"] = seed
        geom = Geometry.from_mesh(trimesh.creation.box(extents=(30, 20, 4)))
        report = Report([AssertionResult("o_no_interference", "interference(o) <= 0", "pass", True,
                                         actual=0.0)])
        return authoring.ImproveResult(ok=True, geometry=geom, script=script, report=report, rounds=1,
                                       history=[("passed", "")])

    monkeypatch.setattr(authoring, "refit_authored", fake_refit)

    b64 = base64.b64encode(b"solid s\nendsolid s\n").decode()
    r = _client().post("/api/fit", json={"run_id": "run_0000", "reference_b64": b64,
                                         "reference_id": "o", "fit": "slip"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["build_ok"] and body["script"] == script
    assert captured["seed"] == script  # the author loop was seeded with the existing part.py


def test_refine_routes_authored_through_author_loop(tmp_path, monkeypatch):
    # CALI-22: refining an LLM-authored part revises its script via the author loop, not the bracket
    # refiner. refine_authored is faked; we assert it ran and the instruction reached it.
    pytest.importorskip("cadquery")
    import trimesh

    import caliper.authoring as authoring
    from caliper.evaluate import AssertionResult, Report
    from caliper.measure import Geometry

    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    script = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(30, 20, 4)\n"
    d = tmp_path / "runs" / "run_0000"
    d.mkdir(parents=True)
    (d / "spec.yaml").write_text("part: gizmo\n")
    (d / "part.py").write_text(script)

    captured = {}

    def fake_refine(spec, seed, instruction, **kw):
        captured["instruction"] = instruction
        geom = Geometry.from_mesh(trimesh.creation.box(extents=(30, 20, 4)))
        report = Report([AssertionResult("solid", "is_watertight", "pass", True, actual=True)])
        return authoring.ImproveResult(ok=True, geometry=geom, script=script, report=report, rounds=1,
                                       history=[("passed", "")])

    monkeypatch.setattr(authoring, "refine_authored", fake_refine)
    r = _client().post("/api/refine", json={"run_id": "run_0000", "instruction": "make it 2mm taller"})
    assert r.status_code == 200, r.text
    assert captured["instruction"] == "make it 2mm taller"
    assert r.json()["script"] == script


def test_fit_end_to_end(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    import base64

    import trimesh

    monkeypatch.setenv("CALIPER_RUNS", str(tmp_path / "runs"))
    c = _client()
    run = c.post("/api/run", json={
        "intent": "a 60 mm corner bracket for 2020 extrusion with four M5 holes",
        "no_llm": True, "max_iter": 1,
    })
    rid = run.json()["run_id"]

    # a reference box centered on its own origin; pose it against the bracket flange end.
    m = trimesh.creation.box(extents=(20, 24, 8))
    b64 = base64.b64encode(m.export(file_type="stl")).decode()

    fit = c.post("/api/fit", json={
        "run_id": rid, "reference_b64": b64, "reference_id": "obstacle",
        "position": [52, 0, 2], "rotation": [0, 0, 0], "min_clearance": 2, "max_iter": 6,
    })
    assert fit.status_code == 200, fit.text
    body = fit.json()
    assert body["build_ok"] and body["status"] == "passed"
    # the reference comes back with a pose + a serve url, and is fetchable for rendering
    assert body["references"] and body["references"][0]["id"] == "obstacle"
    ref_url = body["references"][0]["stl_url"]
    assert c.get(ref_url).status_code == 200
    # the clearance assertion is satisfied and the bracket shrank to fit
    assert any(r["id"] == "obstacle_clearance" and r["status"] == "pass"
               for r in body["report"]["results"])
    assert "bolt_circle: 60" not in body["spec_yaml"]  # resized off the original 60mm

    # reloading the fit run returns the reference pose too
    got = c.get(f"/api/runs/{body['run_id']}").json()
    assert got["references"] and got["references"][0]["position"] == [52, 0, 2]


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
