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


class InsertRequest(BaseModel):
    assembly_id: str                  # which assembly (a YAML stem under the assemblies dir)
    between: list[str]                # the two existing part ids to mate to
    fit: str = "slip"                 # fit class against each interface
    intent: str = "a connecting part"
    new_id: str = "insert"
    max_rounds: int = 6


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


# --- assemblies (CALI-20b / CALI-21b) -------------------------------------
def _assemblies_dirs() -> list[str]:
    """Directories scanned for assembly YAML files. ``CALIPER_ASSEMBLIES`` (os.pathsep) overrides."""
    raw = os.environ.get("CALIPER_ASSEMBLIES", "examples")
    return [d for d in raw.split(os.pathsep) if d]


def _list_assemblies() -> list[dict]:
    """Every YAML in the assemblies dir(s) that parses as an :class:`Assembly` — id is the file stem."""
    import glob

    from .assembly import Assembly

    out, seen = [], set()
    for d in _assemblies_dirs():
        for path in sorted(glob.glob(os.path.join(d, "*.yaml")) + glob.glob(os.path.join(d, "*.yml"))):
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem in seen:
                continue
            try:
                asm = Assembly.load(path)
            except Exception:
                continue  # not an assembly (e.g. a single-part spec) — skip
            seen.add(stem)
            out.append({"id": stem, "name": asm.name, "intent": asm.intent,
                        "parts": len(asm.parts), "mates": len(asm.mates)})
    return out


def _find_assembly(aid: str) -> tuple[str, str]:
    """Resolve an assembly id (file stem) to ``(path, base_dir)``. Raises KeyError if not found."""
    for d in _assemblies_dirs():
        for ext in (".yaml", ".yml"):
            path = os.path.join(d, aid + ext)
            if os.path.isfile(path):
                return path, (d or ".")
    raise KeyError(aid)


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


def _read_run_script(run_id: str) -> str:
    with open(os.path.join(_runs_dir(), run_id, "part.py")) as f:
        return f.read()


def _finish_authored(spec: Spec, res, extra: dict) -> dict:
    """Persist + shape an authored ``improve()`` result. Shared by /api/gen, /api/fit, /api/refine."""
    from fastapi import HTTPException

    if res.geometry is None:
        raise HTTPException(status_code=422,
                            detail=f"author couldn't build a part in {res.rounds} round(s): {res.error}")
    heals = sum(1 for k, _ in res.history if k == "build_error")
    revs = sum(1 for k, _ in res.history if k == "measurement_fail")
    extra = {**extra, "rounds": res.rounds, "heals": heals, "revisions": revs}
    return _finish(spec, "passed" if res.ok else "capped", res.rounds, res.report, res.geometry,
                   extra, script=res.script)


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
        if _is_authored(req.run_id):  # CALI-22: the LLM revises the real part.py
            from .authoring import refine_authored

            spec = Spec.load(spec_path)
            try:
                res = refine_authored(spec, _read_run_script(req.run_id), req.instruction,
                                      max_rounds=req.max_iter,
                                      ref_base=os.path.join(_runs_dir(), req.run_id))
            except Exception as e:  # noqa: BLE001 — missing/invalid ANTHROPIC_API_KEY
                raise HTTPException(status_code=503, detail=f"authoring needs the Claude API: {e}")
            return _finish_authored(spec, res, {
                "source": f"refine {req.run_id}", "label": req.instruction,
                "changes": [req.instruction], "questions": [],
            })
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
        return _finish_authored(intake.spec, res, {
            "source": "gen", "label": req.intent, "changes": [], "questions": intake.questions,
        })

    @app.post("/api/fit")
    def fit(req: FitRequest):
        import base64

        from .fit import attach_reference, ensure_tunable, pick_free_param

        spec_path = os.path.join(_runs_dir(), req.run_id, "spec.yaml")
        if not os.path.isfile(spec_path):
            raise HTTPException(status_code=404, detail=f"unknown run {req.run_id}")
        spec = Spec.load(spec_path)
        authored = _is_authored(req.run_id)

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
        extra = {
            "source": f"fit {req.run_id}", "changes": [], "questions": [], "label": f"fit → {safe}",
            "references": [{"id": safe, "file": ref_path,
                            "position": req.position, "rotation": req.rotation}],
        }
        if authored:  # CALI-22: the LLM revises the real part.py to clear the reference
            from .authoring import refit_authored

            try:
                res = refit_authored(spec, _read_run_script(req.run_id), max_rounds=req.max_iter,
                                     ref_base=os.path.join(_runs_dir(), req.run_id))
            except Exception as e:  # noqa: BLE001 — missing/invalid ANTHROPIC_API_KEY
                raise HTTPException(status_code=503, detail=f"authoring needs the Claude API: {e}")
            return _finish_authored(spec, res, extra)

        ensure_tunable(spec, req.free or pick_free_param(spec))
        return _execute(spec, req.max_iter, extra)

    # --- assemblies (CALI-20b viewer) + insert (CALI-21b) --------------------
    @app.get("/api/assemblies")
    def assemblies():
        return {"assemblies": _list_assemblies()}

    @app.get("/api/assembly/{aid}")
    def get_assembly(aid: str):
        from . import measure
        from .assembly import Assembly, evaluate_assembly, load_parts_tolerant

        try:
            path, base = _find_assembly(aid)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown assembly {aid}")
        asm = Assembly.load(path)
        parts = [{"id": p.id, "role": p.role, "position": p.position, "rotation": p.rotation,
                  "source": p.source, "stl_url": f"/api/assembly/{aid}/part/{p.id}.stl"}
                 for p in asm.parts]
        mates = [{"id": m.id, "between": m.between, "kind": m.kind, "fit": m.fit} for m in asm.mates]
        # CALI-27: one broken part must not sink the assembly — measure what loads, NAME what didn't.
        geoms, part_errors = load_parts_tolerant(asm, base_dir=base)
        try:
            report = evaluate_assembly(asm, base_dir=base, parts=geoms).to_dict()
            collisions = [[a, b] for a, b, v in measure.pairwise_interference(geoms) if v > 1e-6]
        except Exception as e:  # noqa: BLE001 — evaluation itself failing still shouldn't 500
            report, collisions = {"all_pass": False, "results": [], "error": str(e)}, []
        return {"id": aid, "name": asm.name, "intent": asm.intent, "parts": parts,
                "mates": mates, "report": report, "collisions": collisions,
                "part_errors": part_errors}

    @app.get("/api/assembly/{aid}/part/{pid}.stl")
    def assembly_part_stl(aid: str, pid: str):
        import tempfile

        from .assembly import Assembly, _build_py_local, _resolve_source

        try:
            path, base = _find_assembly(aid)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown assembly {aid}")
        asm = Assembly.load(path)
        part = next((p for p in asm.parts if p.id == pid), None)
        if part is None:
            raise HTTPException(status_code=404, detail=f"no part {pid} in {aid}")
        src = _resolve_source(part.source, base)
        if src.endswith(".py"):  # CALI-23/25: build the part and serve its LOCAL mesh (front end poses it)
            try:
                geom = _build_py_local(src)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(status_code=422, detail=f"could not build part {pid}: {e}")
            out = os.path.join(tempfile.mkdtemp(prefix="caliper_part_"), f"{pid}.stl")
            geom.require_mesh().export(out)
            return FileResponse(out, media_type="model/stl")
        if not os.path.isfile(src):
            raise HTTPException(status_code=404, detail=f"missing STL for {pid}: {part.source}")
        return FileResponse(src, media_type="model/stl")

    @app.post("/api/insert")
    def insert(req: InsertRequest):
        import json
        from datetime import datetime

        from .assembly import Assembly, evaluate_assembly, load_parts
        from .insert import add_part_to_assembly, insert_part

        try:
            path, base = _find_assembly(req.assembly_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown assembly {req.assembly_id}")
        if len(req.between) != 2:
            raise HTTPException(status_code=400, detail="`between` needs exactly two part ids")
        asm = Assembly.load(path)
        try:
            res = insert_part(asm, req.between, fit=req.fit, new_intent=req.intent,
                              new_id=req.new_id, max_rounds=req.max_rounds, base_dir=base)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # noqa: BLE001 — almost always a missing/invalid ANTHROPIC_API_KEY
            raise HTTPException(status_code=503, detail=f"authoring needs the Claude API: {e}")
        if res.geometry is None:
            raise HTTPException(status_code=422,
                                detail=f"author couldn't build an insert part in {res.rounds} round(s)")

        run_id, out_dir = _next_run()
        persist_run(out_dir, res.spec, res.report, res.geometry)
        with open(os.path.join(out_dir, "part.py"), "w") as f:
            f.write(res.script if res.script.endswith("\n") else res.script + "\n")
        with open(os.path.join(out_dir, "meta.json"), "w") as f:
            json.dump({"run_id": run_id, "part": req.new_id, "status": "passed" if res.ok else "capped",
                       "source": f"insert into {req.assembly_id}", "label": req.intent,
                       "created": datetime.now().isoformat(timespec="seconds"),
                       "build_ok": True, "references": [], "has_script": True}, f)

        new_asm = add_part_to_assembly(asm, req.new_id, os.path.abspath(out_dir), req.between, fit=req.fit)
        saved = os.path.join(base, f"{req.assembly_id}.inserted.yaml")
        try:
            with open(saved, "w") as f:
                f.write(new_asm.to_yaml())
            saved_id = f"{req.assembly_id}.inserted"
        except Exception:
            saved_id = None
        from . import measure
        new_geoms = load_parts(new_asm, base_dir=base)
        report2 = evaluate_assembly(new_asm, base_dir=base, parts=new_geoms).to_dict()
        collisions = [[a, b] for a, b, v in measure.pairwise_interference(new_geoms) if v > 1e-6]
        return {
            "ok": res.ok, "run_id": run_id, "new_id": req.new_id, "rounds": res.rounds,
            "new_part": {"id": req.new_id, "stl_url": f"/api/runs/{run_id}/part.stl",
                         "position": [0, 0, 0], "rotation": [0, 0, 0]},
            "report": report2, "script": res.script, "assembly_yaml": new_asm.to_yaml(),
            "saved_as": saved_id, "collisions": collisions,
            "bridge": ({"axis": res.bridge.axis_name, "gap": round(res.bridge.gap, 2)}
                       if res.bridge else None),
        }

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

    # M4 — the design session: designs, chat turns, clarify, jobs/SSE, whittle (CALI-31/32/33/38)
    from .design_api import router as design_router

    app.include_router(design_router())

    # the M2 control panel moved to /classic when the design session became the home page (CALI-32)
    @app.get("/classic")
    def classic():
        return FileResponse(os.path.join(STATIC_DIR, "classic.html"),
                            headers={"Cache-Control": "no-store"})

    # the front end (registered last so /api/* wins)
    if os.path.isdir(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
