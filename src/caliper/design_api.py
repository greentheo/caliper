"""CALI-32 — the HTTP surface of the design session (designs, chat turns, clarify, whittle).

Kept apart from ``server.py`` (the M2 control panel's endpoints) so the new page has one place to
look. Every write to a design goes through the per-design lock (``design:<slug>``), whether it's a
long chat turn on a worker or a one-line settings change in the request thread — DesignStore is
single-writer, and a quick write sneaking in under a turn's save would be silently lost.

Long work (a chat turn, drafting clarify questions, a whittle study) returns a ``job_id``; the page
follows it on ``GET /api/jobs/{id}/events`` (Server-Sent Events, CALI-31).
"""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel

from . import aero, chat, clarify, promote
from . import whittle_bridge as wb
from .design import DesignStore
from .jobs import RUNNER, stream


# --- request bodies (module level: FastAPI resolves stringized annotations against globals) -------
class NewDesign(BaseModel):
    prompt: str
    name: Optional[str] = None


class ChatMessage(BaseModel):
    message: str
    scope: Optional[str] = None


class ClarifyAnswers(BaseModel):
    answers: dict[str, str] = {}
    skip: bool = False


class DesignSettings(BaseModel):
    display_units: Optional[str] = None


class WhittleRequest(BaseModel):
    part: str
    kind: str = "flow"
    carve: str = "anywhere"           # "anywhere" (free air) | "tail" (it rides behind something)
    tail_fraction: float = 0.4
    keep_inset_mm: Optional[float] = None
    remove_up_to: float = 0.2
    speed_kmh: float = 105.0
    stations: int = 6
    resolution: int = 40
    flow: list[float] = [-1.0, 0.0, 0.0]
    mirror: Optional[str] = "y"
    flat: list[str] = ["-z"]
    cargo_kg: float = 0.0


class Adopt(BaseModel):
    station: int


class AeroRequest(BaseModel):
    part: str
    bounds: dict[str, list[float]]          # {name: [lo, hi]} — the PARAMS to search
    obstacles: list[str] = []               # parts it rides behind (shelter only)
    keep_inset_mm: Optional[float] = None
    remove_up_to: float = 0.15
    stations: int = 4
    effort: float = 0.5
    speed_kmh: float = 105.0
    resolution: int = 20


def _aero_available() -> bool:
    try:
        import whittle  # noqa: F401

        return hasattr(whittle, "ParametricStudy")
    except ImportError:
        return False


class PartSettings(BaseModel):
    role: Optional[str] = None        # "fixed" = a reference (e.g. the car) — drawn as context


def _lock(slug: str) -> str:
    return f"design:{slug}"


# --- serialising -----------------------------------------------------------------------------------
def _bbox(store: DesignStore, pid: str) -> Optional[dict]:
    try:
        lo, hi = store.part_geometry(pid).require_mesh().bounds
    except Exception:  # noqa: BLE001 — a part that won't build is reported by the measurement
        return None
    return {"min": [round(float(v), 2) for v in lo], "max": [round(float(v), 2) for v in hi],
            "size": [round(float(b - a), 2) for a, b in zip(lo, hi)]}


def design_state(store: DesignStore, history_limit: int = 30) -> dict:
    """Everything the page draws, in one payload."""
    from .assembly import derived_assertions

    d = store.design
    slug = d.slug
    roles = {p.id: p.role for p in store.assembly.parts}
    parts = []
    for p in d.parts:
        spec = store.read_spec(p.id) if store.is_scripted(p.id) or os.path.exists(
            store.spec_path(p.id)) else None
        params = aero.read_params(store.read_script(p.id)) if store.is_scripted(p.id) else None
        parts.append({
            "params": params,
            "suggest": {k: aero.suggest(k, v) for k, v in (params or {}).items()},
            "id": p.id, "intent": p.intent, "version": p.version, "origin": p.origin,
            "role": roles.get(p.id, "movable"), "scripted": store.is_scripted(p.id),
            "stl_url": f"/api/designs/{slug}/parts/{p.id}.stl?v={p.version}",
            "bbox": _bbox(store, p.id),
            "rules": [{"id": a.id, "expr": a.expr} for a in (spec.assertions if spec else [])],
            "history": store.history(p.id)[-history_limit:],
            "versions": store.versions(p.id),
        })
    report, part_errors = (None, {})
    if store.assembly.parts and derived_assertions(store.assembly):
        try:
            report, part_errors = store.evaluate(tolerant=True)
        except Exception as e:  # noqa: BLE001
            part_errors = {"<design>": f"{type(e).__name__}: {e}"}
    proposal = promote.pending(store)
    return {
        "slug": slug, "name": d.name, "prompt": d.prompt, "units": d.units,
        "display_units": d.display_units,
        "requirements": [r.model_dump() for r in d.requirements],
        "parts": parts,
        "mates": [{"id": m.id, "between": m.between, "kind": m.kind} for m in store.assembly.mates],
        "rules": [{"id": a.id, "expr": a.expr} for a in store.assembly.assertions],
        "report": report.to_dict() if report is not None else None,
        "part_errors": part_errors,
        "proposal": proposal.to_dict() if proposal else None,
        "clarify": [q.to_dict() for q in clarify.pending(store)],
        "log": store.log(),
        "whittle_runs": [_run_summary(r) for r in wb.list_runs(store)],
        "aero_runs": aero.list_runs(store),
        "aero_available": _aero_available(),
    }


def _run_summary(rec: dict) -> dict:
    out = {k: rec.get(k) for k in ("id", "part", "kind", "carve", "notes", "columns",
                                   "stations", "rows", "speed_kmh", "created")}
    out["setup"] = {k: rec.get("setup", {}).get(k)
                    for k in ("flow", "mirror", "flat", "removeUpTo", "keepBoxes", "surfaces")}
    return out


def turn_result(res) -> dict:
    return {
        "action": res.action, "reply": res.reply, "ok": res.ok, "part": res.part,
        "version": res.version, "broke": res.broke, "fixed": res.fixed,
        "part_errors": res.part_errors, "error": res.error,
        "report": res.report.to_dict() if res.report is not None else None,
        "part_report": res.part_report.to_dict() if res.part_report is not None else None,
        "proposal": res.proposal.to_dict() if res.proposal is not None else None,
    }


# --- the router ------------------------------------------------------------------------------------
def router():
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import Response, StreamingResponse

    r = APIRouter()

    def load(slug: str) -> DesignStore:
        try:
            return DesignStore.load(slug)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"no design {slug!r}")

    # -- jobs ----------------------------------------------------------------------------------------
    @r.get("/api/jobs/{job_id}")
    def job(job_id: str, after: int = 0):
        j = RUNNER.get(job_id)
        if j is None:
            raise HTTPException(status_code=404, detail="no such job (it may have expired)")
        return j.to_dict(after)

    @r.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str, after: int = 0):
        j = RUNNER.get(job_id)
        if j is None:
            raise HTTPException(status_code=404, detail="no such job (it may have expired)")
        return StreamingResponse(stream(j, after=after), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    # -- designs -------------------------------------------------------------------------------------
    @r.get("/api/designs")
    def designs():
        return {"designs": DesignStore.list_designs()}

    @r.post("/api/designs")
    def new_design(req: NewDesign):
        if not req.prompt.strip():
            raise HTTPException(status_code=422, detail="say what you're building")
        store = DesignStore.create(req.prompt.strip(), name=req.name)
        if clarify.speaks_inches(req.prompt):
            store.design.display_units = "in"
            store.save()
        slug = store.design.slug

        def ask(j):
            j.emit("clarify", "working out what to ask…")
            qs, source = clarify.draft_questions(req.prompt.strip())   # the slow part — unlocked
            with RUNNER.locked(_lock(slug)):
                clarify.open_round(DesignStore.load(slug), qs, source)
            return {"questions": [q.to_dict() for q in qs], "source": source}

        job = RUNNER.submit("clarify", ask, label="clarify", lock=f"clarify:{slug}")
        return {"slug": slug, "job_id": job.id}

    @r.get("/api/designs/{slug}")
    def get_design(slug: str):
        return design_state(load(slug))

    @r.patch("/api/designs/{slug}")
    def settings(slug: str, req: DesignSettings):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            if req.display_units is not None:
                if req.display_units not in ("mm", "in"):
                    raise HTTPException(status_code=422, detail="display_units is 'mm' or 'in'")
                store.design.display_units = req.display_units
            store.save()
            return design_state(store)

    @r.post("/api/designs/{slug}/clarify")
    def answer_clarify(slug: str, req: ClarifyAnswers):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            clarify.answer_round(store, req.answers, skip=req.skip)
            return design_state(store)

    @r.post("/api/designs/{slug}/chat")
    def chat_turn(slug: str, req: ChatMessage):
        load(slug)                                   # 404 now, not inside the job
        if not req.message.strip():
            raise HTTPException(status_code=422, detail="empty message")

        def work(j):
            store = DesignStore.load(slug)
            res = chat.turn(store, req.message.strip(), scope=req.scope or None,
                            on_event=lambda ev: j.emit(ev.kind, ev.text, **ev.data))
            return turn_result(res)

        job = RUNNER.submit("chat", work, label=req.message[:60], lock=_lock(slug))
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/parts/{pid}.stl")
    def part_stl(slug: str, pid: str):
        store = load(slug)
        if store.design.part(pid) is None:
            raise HTTPException(status_code=404, detail=f"no part {pid!r}")
        try:
            data = store.part_stl(pid)
        except Exception as e:  # noqa: BLE001 — name the real failure (CALI-27)
            raise HTTPException(status_code=500, detail=f"{pid} won't build: {e}")
        return Response(data, media_type="model/stl",
                        headers={"Content-Disposition": f'attachment; filename="{slug}_{pid}.stl"'})

    @r.patch("/api/designs/{slug}/parts/{pid}")
    def part_settings(slug: str, pid: str, req: PartSettings):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            part = next((p for p in store.assembly.parts if p.id == pid), None)
            if part is None:
                raise HTTPException(status_code=404, detail=f"no part {pid!r}")
            if req.role is not None:
                if req.role not in ("fixed", "movable"):
                    raise HTTPException(status_code=422, detail="role is 'fixed' or 'movable'")
                part.role = req.role
                store.append_history(pid, {"kind": "setting", "role": req.role})
            store.save()
            return design_state(store)

    @r.get("/api/designs/{slug}/parts/{pid}/script")
    def part_script(slug: str, pid: str):
        store = load(slug)
        if not os.path.exists(store.script_path(pid)):
            raise HTTPException(status_code=404, detail=f"{pid} has no script")
        spec = store.read_spec(pid)
        return {"script": store.read_script(pid), "scripted": store.is_scripted(pid),
                "spec_yaml": spec.to_yaml() if spec else None}

    # -- whittle -------------------------------------------------------------------------------------
    @r.get("/api/whittle/health")
    def whittle_health():
        return wb.health()

    @r.post("/api/designs/{slug}/whittle")
    def whittle_run(slug: str, req: WhittleRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")

        def work(j):
            s = DesignStore.load(slug)
            kw = req.model_dump()
            part = kw.pop("part")
            return wb.run(s, part, emit=lambda k, t="", **d: j.emit(k, t, **d), **kw)

        job = RUNNER.submit("whittle", work, label=f"whittle {req.kind} · {req.part}",
                            lock=f"whittle:{slug}")
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/whittle")
    def whittle_runs(slug: str, part: Optional[str] = None):
        return {"runs": [_run_summary(x) for x in wb.list_runs(load(slug), part)]}

    @r.get("/api/designs/{slug}/whittle/{wid}/stations/{index}.stl")
    def whittle_station(slug: str, wid: str, index: int):
        store = load(slug)
        try:
            path = wb.station_path(store, wid, index)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad run id")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such station")
        with open(path, "rb") as f:
            return Response(f.read(), media_type="model/stl")

    @r.post("/api/designs/{slug}/whittle/{wid}/adopt")
    def whittle_adopt(slug: str, wid: str, req: Adopt):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                got = wb.adopt(store, wid, req.station)
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            store.append_log({"kind": "whittle", "action": "adopted", "run": wid,
                              "station": req.station, "version": got["version"],
                              **({"grew_mm": got["grew_mm"]} if got["grew_mm"] else {})})
            return {**got, "design": design_state(store)}

    # -- parametric drag search (CALI-39): whittle searches PARAMS, numbers come back ---------------
    @r.post("/api/designs/{slug}/aero")
    def aero_run(slug: str, req: AeroRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")
        if not _aero_available():
            raise HTTPException(status_code=503, detail="whittle with ParametricStudy isn't installed "
                                "in Caliper's environment (pip install -e ~/githubrepo/whittle)")
        bounds = {k: (float(v[0]), float(v[1])) for k, v in req.bounds.items() if len(v) == 2}

        def work(j):
            s = DesignStore.load(slug)
            return aero.study(s, req.part, bounds, obstacles=req.obstacles,
                              keep_inset_mm=req.keep_inset_mm, remove_up_to=req.remove_up_to,
                              stations=req.stations, effort=req.effort, speed_kmh=req.speed_kmh,
                              resolution=req.resolution,
                              emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("aero", work, label=f"shape {req.part} for drag", lock=f"aero:{slug}")
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/aero/{rid}/stations/{index}.stl")
    def aero_station(slug: str, rid: str, index: int):
        store = load(slug)
        try:
            path = aero.station_path(store, rid, index)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad run id")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such station")
        with open(path, "rb") as f:
            return Response(f.read(), media_type="model/stl")

    @r.post("/api/designs/{slug}/aero/{rid}/adopt")
    def aero_adopt(slug: str, rid: str, req: Adopt):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                got = aero.adopt(store, rid, req.station)
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=409, detail=str(e))
            store.append_log({"kind": "aero", "action": "adopted", "run": rid,
                              "station": req.station, "version": got["version"],
                              "params": got["params"],
                              **({"grew_mm": got["grew_mm"]} if got["grew_mm"] else {})})
            return {**got, "design": design_state(store)}

    return r
