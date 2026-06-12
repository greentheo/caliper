"""CALI-9 (M2) — the webapp wrapper.

A thin FastAPI layer over the library (the loop is the product; this is a wrapper, design spec §8).
Endpoints drive the same intake → loop → build → measure → report → STL pipeline as the CLI and
serve a no-build three.js front end (``web/static``) with a 3D viewer, spec/report panels, the
refinement box, and 3Dconnexion SpaceMouse support via WebHID.

Run with ``caliper serve`` (or ``make serve``).
"""

from __future__ import annotations

import os

from typing import Optional

from pydantic import BaseModel

from . import generate
from .intake import draft_spec
from .loop import make_eval_fn, persist_run, run_loop
from .refine import apply_refinement
from .spec import Spec


# Request models live at module level so FastAPI can resolve them as the request body
# (stringized annotations from `from __future__ import annotations` resolve against module globals).
class RunRequest(BaseModel):
    intent: str
    no_llm: bool = True
    machine: str = "generic"
    max_iter: int = 4


class RefineRequest(BaseModel):
    run_id: str
    instruction: str
    no_llm: bool = True
    max_iter: int = 4


class GenRequest(BaseModel):
    intent: str
    no_llm: bool = False          # gen authors with the LLM; no_llm only affects the intake step
    machine: str = "generic"
    max_rounds: int = 4           # author/revise rounds (heal build errors + failing checks)


class FitRequest(BaseModel):
    run_id: str                       # the part to fit
    reference_b64: str                # the reference STL (base64; may be a data: URL)
    reference_id: str = "reference"
    position: list[float] = [0.0, 0.0, 0.0]   # mm, in the part's frame
    rotation: list[float] = [0.0, 0.0, 0.0]   # degrees, three.js XYZ euler
    min_clearance: Optional[float] = None     # require min_clearance(ref) >= this
    no_overlap: bool = True                   # require interference(ref) <= 0
    fit: Optional[str] = None                 # fit class (press/snug/slip/free/running) → clearance band
    nominal: Optional[float] = None           # mating size for the fit band (optional)
    free: Optional[str] = None                # parameter to resize (default: auto size param)
    max_iter: int = 6

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")


def _runs_dir() -> str:
    # resolved per-call so tests can point CALIPER_RUNS at a temp dir
    return os.environ.get("CALIPER_RUNS", "runs")


def _is_authored(run_id: str) -> bool:
    """True if a run is an LLM-authored part (has part.py) — fit/refine can't rebuild it as a bracket."""
    return os.path.isfile(os.path.join(_runs_dir(), run_id, "part.py"))


def _next_run() -> tuple[str, str]:
    base = _runs_dir()
    os.makedirs(base, exist_ok=True)
    n = len([d for d in os.listdir(base) if d.startswith("run_")])
    run_id = f"run_{n:04d}"
    return run_id, os.path.join(base, run_id)


def _finish(spec: Spec, status: str, iterations: int, report, geometry, extra: dict,
            error: str = "", script=None) -> dict:
    """Persist a finished run (spec + report + STL, plus references/script) and shape the response.

    Shared by the bracket loop (:func:`_execute`) and the LLM author (``/api/gen``). ``geometry`` is
    None on a build failure. ``script`` (the authored ``part.py``) is stored + returned when present.
    ``extra["references"]`` (fit path) is a list of ``{id, file, position, rotation}`` copied into the
    run dir + recorded so the viewer can re-render references at their pose.
    """
    import json
    import shutil
    from datetime import datetime

    run_id, out_dir = _next_run()
    persist_run(out_dir, spec, report, geometry)
    if script is not None:
        with open(os.path.join(out_dir, "part.py"), "w") as f:
            f.write(script if script.endswith("\n") else script + "\n")

    refs_meta = []
    for rinfo in extra.pop("references", []):
        dst = os.path.join(out_dir, f"ref_{rinfo['id']}.stl")
        try:
            shutil.copyfile(rinfo["file"], dst)
        except Exception:
            continue
        refs_meta.append({
            "id": rinfo["id"], "position": rinfo.get("position", [0, 0, 0]),
            "rotation": rinfo.get("rotation", [0, 0, 0]),
            "stl_url": f"/api/runs/{run_id}/ref/{rinfo['id']}.stl",
        })

    build_ok = geometry is not None
    meta = {
        "run_id": run_id, "part": spec.part, "status": status,
        "source": extra.get("source", ""), "label": extra.get("label", "") or spec.intent,
        "changes": extra.get("changes", []), "created": datetime.now().isoformat(timespec="seconds"),
        "build_ok": build_ok, "references": refs_meta, "has_script": script is not None,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    resp = {
        "run_id": run_id, "status": status, "iterations": iterations,
        "spec_yaml": spec.to_yaml(), "report": report.to_dict(),
        "stl_url": f"/api/runs/{run_id}/part.stl" if build_ok else None,
        "build_ok": build_ok, "error": error, "references": refs_meta, **extra,
    }
    if script is not None:
        resp["script"] = script
    return resp


def _execute(spec: Spec, max_iter: int, extra: dict) -> dict:
    """Run the bracket optimizer loop on a spec, then persist + shape the response."""
    result = run_loop(spec, make_eval_fn(), max_iter=max_iter)  # references load lazily (with pose)
    build = generate.build(result.spec)
    return _finish(result.spec, result.status, result.iterations, result.report,
                   build.geometry if build.build_ok else None, extra,
                   error="" if build.build_ok else build.error)


def create_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Caliper", description="Spec-driven, measurement-grounded 3D parts.")

    @app.middleware("http")
    async def _no_cache(request, call_next):
        # local dev tool: never let the browser serve a stale JS/CSS module
        resp = await call_next(request)
        p = request.url.path
        if p == "/" or p.endswith((".js", ".css", ".html")):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "caliper"}

    @app.post("/api/run")
    def run(req: RunRequest):
        intake = draft_spec(req.intent, machine=req.machine, use_llm=not req.no_llm)
        return _execute(intake.spec, req.max_iter,
                        {"source": intake.source, "questions": intake.questions, "changes": [],
                         "label": req.intent})

    @app.post("/api/refine")
    def refine(req: RefineRequest):
        spec_path = os.path.join(_runs_dir(), req.run_id, "spec.yaml")
        if not os.path.isfile(spec_path):
            raise HTTPException(status_code=404, detail=f"unknown run {req.run_id}")
        if _is_authored(req.run_id):
            raise HTTPException(status_code=422, detail="This is an LLM-authored part — refine rebuilds "
                                "via the bracket generator. Re-run with the author (✦ author any part) "
                                "and an adjusted intent instead.")
        res = apply_refinement(Spec.load(spec_path), req.instruction, use_llm=not req.no_llm)
        if not res.changed:
            raise HTTPException(status_code=422, detail="no recognized refinement for that instruction")
        return _execute(res.spec, req.max_iter,
                        {"source": res.source, "changes": res.changes, "questions": [],
                         "label": req.instruction})

    @app.post("/api/gen")
    def gen(req: GenRequest):
        from .authoring import improve

        intake = draft_spec(req.intent, machine=req.machine, use_llm=not req.no_llm)
        try:
            res = improve(intake.spec, max_rounds=req.max_rounds)
        except Exception as e:  # noqa: BLE001 — almost always a missing/invalid ANTHROPIC_API_KEY
            raise HTTPException(status_code=503, detail=f"authoring needs the Claude API: {e}")
        if res.geometry is None:
            raise HTTPException(status_code=422,
                                detail=f"author couldn't build a part in {res.rounds} round(s)")
        heals = sum(1 for k, _ in res.history if k == "build_error")
        revs = sum(1 for k, _ in res.history if k == "measurement_fail")
        return _finish(
            intake.spec, "passed" if res.ok else "capped", res.rounds, res.report, res.geometry,
            {"source": "gen", "label": req.intent, "changes": [], "questions": intake.questions,
             "rounds": res.rounds, "heals": heals, "revisions": revs},
            script=res.script,
        )

    @app.post("/api/fit")
    def fit(req: FitRequest):
        import base64

        from .fit import attach_reference, ensure_tunable, pick_free_param

        spec_path = os.path.join(_runs_dir(), req.run_id, "spec.yaml")
        if not os.path.isfile(spec_path):
            raise HTTPException(status_code=404, detail=f"unknown run {req.run_id}")
        if _is_authored(req.run_id):
            raise HTTPException(status_code=422, detail="This is an LLM-authored part — fit rebuilds "
                                "via the bracket generator and can't fit authored parts yet. Fit a "
                                "bracket-family part for now.")
        spec = Spec.load(spec_path)

        try:
            raw = base64.b64decode(req.reference_b64.split(",")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="reference_b64 is not valid base64")
        if not raw:
            raise HTTPException(status_code=400, detail="reference STL is empty")
        safe = "".join(c for c in req.reference_id if c.isalnum() or c in "-_") or "reference"
        refs_dir = os.path.join(_runs_dir(), "_refs")
        os.makedirs(refs_dir, exist_ok=True)
        ref_path = os.path.abspath(os.path.join(refs_dir, f"{req.run_id}_{safe}.stl"))
        with open(ref_path, "wb") as f:
            f.write(raw)

        no_overlap = req.no_overlap or (req.min_clearance is None and req.fit is None)
        attach_reference(spec, safe, ref_path, position=req.position, rotation=req.rotation,
                         min_clearance=req.min_clearance, no_overlap=no_overlap,
                         fit=req.fit, nominal=req.nominal)
        ensure_tunable(spec, req.free or pick_free_param(spec))
        return _execute(spec, req.max_iter, {
            "source": f"fit {req.run_id}", "changes": [], "questions": [], "label": f"fit → {safe}",
            "references": [{"id": safe, "file": ref_path,
                            "position": req.position, "rotation": req.rotation}],
        })

    @app.get("/api/runs/{run_id}/ref/{ref_id}.stl")
    def ref_stl(run_id: str, ref_id: str):
        safe = "".join(c for c in ref_id if c.isalnum() or c in "-_")
        path = os.path.join(_runs_dir(), run_id, f"ref_{safe}.stl")
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="no such reference")
        return FileResponse(path, media_type="model/stl")

    @app.get("/api/runs")
    def list_runs(limit: int = 40):
        import json

        base = _runs_dir()
        if not os.path.isdir(base):
            return {"runs": []}
        ids = sorted((d for d in os.listdir(base) if d.startswith("run_")), reverse=True)[:limit]
        runs = []
        for rid in ids:
            d = os.path.join(base, rid)
            info = {"run_id": rid, "part": rid, "status": "", "label": "", "created": None,
                    "stl_url": f"/api/runs/{rid}/part.stl" if os.path.isfile(os.path.join(d, "part.stl")) else None}
            mp = os.path.join(d, "meta.json")
            if os.path.isfile(mp):
                try:
                    info.update(json.load(open(mp)))
                    info["stl_url"] = f"/api/runs/{rid}/part.stl" if os.path.isfile(os.path.join(d, "part.stl")) else None
                except Exception:
                    pass
            runs.append(info)
        return {"runs": runs}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        import json

        d = os.path.join(_runs_dir(), run_id)
        spec_path = os.path.join(d, "spec.yaml")
        if not os.path.isfile(spec_path):
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
        spec = Spec.load(spec_path)
        report_path = os.path.join(d, "report.json")
        if os.path.isfile(report_path):
            report = json.load(open(report_path))
        else:  # legacy run without a stored report → re-evaluate (needs the kernel)
            from .evaluate import DEFAULT_MACHINE, Report, evaluate

            built = generate.build(spec)
            report = evaluate(spec, built.geometry, DEFAULT_MACHINE).to_dict() if built.build_ok \
                else Report().to_dict()
        meta = {}
        mp = os.path.join(d, "meta.json")
        if os.path.isfile(mp):
            try:
                meta = json.load(open(mp))
            except Exception:
                pass
        script = None
        script_path = os.path.join(d, "part.py")
        if os.path.isfile(script_path):
            try:
                script = open(script_path).read()
            except Exception:
                script = None
        return {
            "run_id": run_id, "spec_yaml": spec.to_yaml(), "report": report,
            "stl_url": f"/api/runs/{run_id}/part.stl" if os.path.isfile(os.path.join(d, "part.stl")) else None,
            "build_ok": os.path.isfile(os.path.join(d, "part.stl")),
            "status": meta.get("status", ""), "source": meta.get("source", ""),
            "changes": meta.get("changes", []), "questions": [],
            "references": meta.get("references", []), "script": script,
        }

    @app.get("/api/runs/{run_id}/part.stl")
    def stl(run_id: str):
        path = os.path.join(_runs_dir(), run_id, "part.stl")
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="no STL for that run")
        return FileResponse(path, media_type="model/stl", filename=f"caliper_{run_id}.stl")

    # the front end (registered last so /api/* wins)
    if os.path.isdir(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
