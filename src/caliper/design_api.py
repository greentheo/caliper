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

from . import (aero, answers, chat, clarify, construction, cutplan, frame_study, goals, lighten,
               load_study, making, patterns, promote, release, scorecard, shop, studies)
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


class FrameRequest(BaseModel):
    part: str
    load_lb: float = 100.0              # the box + what's in it, spread along the rails
    factor: float = 2.5                 # driving: bumps
    min_safety: float = 3.5
    on_groups: list[str] = ["rails"]
    from_design: bool = False           # carry the other parts as built (+ payload_lb on the floor) instead
    payload_lb: float = 100.0
    params: dict = {}                   # a what-if layout (one of the frame's LAYOUTS)
    walls: bool = True                  # a carried part's shell() walls carry load too
    build: dict[str, dict] = {}         # what-if construction of the carried parts


class LoadRequest(BaseModel):
    part: str
    min_safety: float = load_study.MIN_SAFETY     # at each load times its factor


class Shop(BaseModel):
    hand: list[str] = []
    machines: list[dict] = []


class GoalDecision(BaseModel):
    keep: bool


class GussetRequest(BaseModel):
    part: str
    thickness: float = 3.175            # 1/8 in
    plates: int = 2                     # cheek plates, one each side
    min_safety: float = 3.5
    payload_lb: float = 100.0
    walls: bool = True


class GussetPick(BaseModel):
    picks: dict[str, int] = {}          # joint -> station; the lightest that holds if left out


class PartSettings(BaseModel):
    role: Optional[str] = None        # "fixed" = a reference (e.g. the car) — drawn as context


class BuildChoices(BaseModel):
    build: dict = {}                  # BUILD entries to try (or, on /use, to write into the script)


class BalanceRequest(BaseModel):
    build: dict[str, dict] = {}       # {part: BUILD overrides} — what-ifs, not saved
    payload_lb: float = 0.0           # gear or people, on the floor


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
        script = store.read_script(p.id) if store.is_scripted(p.id) else ""
        params = aero.read_params(script) if script else None
        ranges = aero.read_ranges(script) if script else {}
        parts.append({
            "params": params,
            # a part that declares its tubes is a frame: it gets sized, not shaped for drag
            "framed": "def members(" in script and "def supports(" in script,
            "layouts": frame_study.read_layouts(script) if "LAYOUTS" in script else {},
            "gussets": list(frame_study.read_gussets(script)) if "GUSSETS" in script else [],
            # a part that says what it's built from (or a frame) can be weighed (CALI-41)
            "built": construction.declares(script),
            # what it has to hold (keeps()) — a drag study keeps it clear (CALI-42)
            "keeps": "def keeps(" in script,
            "shell": "def shell(" in script,      # its walls can carry load in a frame study (CALI-44)
            "loads": "def loads(" in script,      # what it must hold: a strength study (CALI-54)
            "suggest": {k: aero.suggest(k, v, ranges) for k, v in (params or {}).items()},
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
    runs = {"load": load_study.list_runs(store), "lighten": lighten.list_runs(store),
            "frame": frame_study.list_runs(store), "patterns": patterns.list_runs(store),
            "gussets": frame_study.list_gussets(store), "aero": aero.list_runs(store),
            "whittle": wb.list_runs(store), "cutplan": cutplan.list_runs(store),
            "scorecard": scorecard.list_cards(store, 20), "release": release.list_releases(store)}
    air = studies.in_air(d, parts, has_runs=bool(runs["aero"] or runs["whittle"]))
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
        "whittle_runs": [_run_summary(r) for r in runs["whittle"]],
        "aero_runs": runs["aero"],
        "frame_runs": runs["frame"],
        "load_runs": runs["load"],
        "lighten_runs": runs["lighten"],
        "pattern_runs": runs["patterns"],
        "cutplans": runs["cutplan"],
        "gusset_runs": runs["gussets"],
        "scorecards": runs["scorecard"][:2],
        "releases": runs["release"],
        # does it move through air? drag studies only when it does (CALI-67)
        "in_air": air,
        "studies": studies.index(store, runs, parts, air),
        "has_goals": os.path.exists(scorecard.goals_path(store)),
        "goals": _goals_summary(store),
        "cutplan_unavailable": cutplan.available(),
        "aero_available": _aero_available(),
    }


def _goals_summary(store: DesignStore) -> dict:
    data = goals.read(store)
    checks = [c for c in data.get("checks") or [] if isinstance(c, dict) and c.get("metric") and "limit" in c]
    return {"ours": goals.ours(data), "checks": checks, "objectives": data.get("objectives") or []}


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

        def checks(j):                  # what it's held to, from the answers (CALI-55), off the request
            with RUNNER.locked(_lock(slug)):
                s = DesignStore.load(slug)
                return goals.update(s, "(the answers to the clarifying questions)")

        RUNNER.submit("goals", checks, label=f"checks · {slug}", lock=f"goals:{slug}")
        return design_state(load(slug))

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

    # -- strength (CALI-54): the part's own loads() through whittle's FEA and a plate check -----------
    @r.post("/api/designs/{slug}/load-study")
    def load_run(slug: str, req: LoadRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")

        if not _aero_available():
            raise HTTPException(status_code=503, detail="whittle isn't installed in Caliper's environment")

        def work(j):
            s = DesignStore.load(slug)
            return load_study.study(s, req.part, min_safety=req.min_safety,
                                    emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("load", work, label=f"strength · {req.part}", lock=f"load:{slug}")
        return {"job_id": job.id}

    # -- the four questions (spec step 1): each answered in a line anyone can read --------------------------
    @r.get("/api/designs/{slug}/answers")
    def design_answers(slug: str, part: Optional[str] = None):
        store = load(slug)
        if part and store.design.part(part) is None:
            raise HTTPException(status_code=404, detail=f"no part {part!r}")
        if not goals.read(store) and (store.design.requirements or store.design.prompt) and store.design.parts \
                and not RUNNER.busy(f"goals:{slug}"):
            # what it's held to, from what was said, for a design from before the conversation wrote it (step 2)
            def checks(j):
                with RUNNER.locked(_lock(slug)):
                    s = DesignStore.load(slug)
                    return None if goals.read(s) else goals.update(s, "(the design's goal and requirements)")

            RUNNER.submit("goals", checks, label=f"checks · {slug}", lock=f"goals:{slug}")
        return {"part": part, "cards": answers.answers(store, design_state(store), part)}

    # -- your shop (CALI-48): what you have, and how each part gets made with it --------------------------
    @r.get("/api/shop")
    def get_shop():
        return {"shop": shop.read(), "hand": shop.HAND, "machines": list(shop.MACHINES)}

    @r.put("/api/shop")
    def put_shop(req: Shop):
        return {"shop": shop.write(req.model_dump()), "hand": shop.HAND, "machines": list(shop.MACHINES)}

    @r.get("/api/designs/{slug}/parts/{pid}/making")
    def part_making(slug: str, pid: str):
        store = load(slug)
        if store.design.part(pid) is None:
            raise HTTPException(status_code=404, detail=f"no part {pid!r}")
        try:
            return making.plan(store, pid)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # -- patterns for hand tools (CALI-48): measure and mark, print and tape, project and trace ------------
    @r.post("/api/designs/{slug}/parts/{pid}/patterns")
    def make_patterns(slug: str, pid: str):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            if store.design.part(pid) is None:
                raise HTTPException(status_code=404, detail=f"no part {pid!r}")
            try:
                rec = patterns.make(store, pid)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            return {"run": rec, "design": design_state(store)}

    @r.get("/api/designs/{slug}/patterns/{rid}/{name}")
    def pattern_file(slug: str, rid: str, name: str):
        store = load(slug)
        try:
            path = patterns.file_path(store, rid, name)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad path")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such file")
        kind = {".pdf": "application/pdf", ".svg": "image/svg+xml", ".png": "image/png",
                ".html": "text/html"}.get(os.path.splitext(name)[1], "application/octet-stream")
        with open(path, "rb") as f:
            return Response(f.read(), media_type=kind)

    # -- what it's held to (CALI-55): keep or drop a check the conversation proposed -------------------
    @r.post("/api/designs/{slug}/goals/{check_id}")
    def goal_decide(slug: str, check_id: str, req: GoalDecision):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                goals.decide(store, check_id, req.keep)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=409, detail=str(e))
            return design_state(store)

    # -- lighten (CALI-71): through-cuts where the wood isn't working, every station checked in 3D --------
    @r.post("/api/designs/{slug}/lighten")
    def lighten_run(slug: str, req: LoadRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")
        if not _aero_available():
            raise HTTPException(status_code=503, detail="whittle isn't installed in Caliper's environment")

        def work(j):
            s = DesignStore.load(slug)
            return lighten.study(s, req.part, min_safety=req.min_safety,
                                 emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("lighten", work, label=f"lighten · {req.part}", lock=f"load:{slug}")
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/lighten/{rid}/stations/{index}.stl")
    def lighten_station(slug: str, rid: str, index: int):
        store = load(slug)
        try:
            path = lighten.station_path(store, rid, index)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad run id")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such station")
        with open(path, "rb") as f:
            return Response(f.read(), media_type="model/stl")

    @r.post("/api/designs/{slug}/lighten/{rid}/adopt")
    def lighten_adopt(slug: str, rid: str, req: Adopt):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                got = lighten.adopt(store, rid, req.station)
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            store.append_log({"kind": "lighten", "action": "adopted", "run": rid, "station": req.station,
                              "version": got["version"]})
            return {**got, "design": design_state(store)}

    @r.get("/api/designs/{slug}/load-study/{rid}/cases/{index}.json")
    def load_heat(slug: str, rid: str, index: int):
        store = load(slug)
        try:
            path = load_study.heat_path(store, rid, index)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad run id")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such case")
        with open(path, "rb") as f:
            return Response(f.read(), media_type="application/json")

    # -- frame sizing (CALI-40): whittle's FrameStudy on the tubes a part declares --------------------
    @r.post("/api/designs/{slug}/frame-study")
    def frame_run(slug: str, req: FrameRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")
        if not _aero_available():
            raise HTTPException(status_code=503, detail="whittle isn't installed in Caliper's environment")

        def work(j):
            s = DesignStore.load(slug)
            return frame_study.study(s, req.part, load_lb=req.load_lb, factor=req.factor,
                                     min_safety=req.min_safety, on_groups=tuple(req.on_groups),
                                     from_design=req.from_design, payload_lb=req.payload_lb,
                                     params=req.params or None, walls=req.walls,
                                     build=req.build or None,
                                     emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("frame", work, label=f"size {req.part}", lock=f"frame:{slug}")
        return {"job_id": job.id}

    # -- how it's built, in 3D (CALI-52) -----------------------------------------------------------
    @r.get("/api/designs/{slug}/parts/{pid}/pieces")
    def part_pieces(slug: str, pid: str):
        store = load(slug)
        if store.design.part(pid) is None:
            raise HTTPException(status_code=404, detail=f"no part {pid!r}")
        try:
            return construction.pieces3d(store, pid)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    # -- cut plan (CALI-45): panels unfolded and nested by unfold-to-sheets, sticks cut-listed ----------
    @r.post("/api/designs/{slug}/parts/{pid}/cutplan")
    def cutplan_run(slug: str, pid: str):
        store = load(slug)
        if store.design.part(pid) is None:
            raise HTTPException(status_code=404, detail=f"no part {pid!r}")
        why = cutplan.available()
        if why:
            raise HTTPException(status_code=503, detail=why)

        def work(j):
            return cutplan.run(DesignStore.load(slug), pid, emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("cutplan", work, label=f"cut plan for {pid}", lock=_lock(slug))
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/cutplans/{rid}/files/{path:path}")
    def cutplan_file(slug: str, rid: str, path: str):
        store = load(slug)
        if cutplan.load_run(store, rid) is None:
            raise HTTPException(status_code=404, detail="no such cut plan")
        try:
            full = cutplan.file_path(store, rid, path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="no such file")
        types = {".svg": "image/svg+xml", ".dxf": "application/dxf", ".pdf": "application/pdf",
                 ".txt": "text/plain; charset=utf-8", ".obj": "text/plain", ".json": "application/json"}
        with open(full, "rb") as f:
            data = f.read()
        media = types.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        headers = {} if media.startswith(("image/", "text/", "application/pdf")) else {
            "Content-Disposition": f'attachment; filename="{rid}-{path.replace("/", "-")}"'}
        return Response(data, media_type=media, headers=headers)

    # -- the build package (CALI-51): a released, versioned bundle for the shop ---------------------
    @r.post("/api/designs/{slug}/release")
    def release_run(slug: str):
        load(slug)
        why = cutplan.available()
        if why:
            raise HTTPException(status_code=503, detail=why)

        def work(j):
            return release.make(DesignStore.load(slug), emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("release", work, label="build package", lock=_lock(slug))
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/releases/{rid}/files/{path:path}")
    def release_file(slug: str, rid: str, path: str):
        store = load(slug)
        if release.load_release(store, rid) is None:
            raise HTTPException(status_code=404, detail="no such release")
        try:
            full = release.file_path(store, rid, path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="no such file")
        types = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                 ".dxf": "application/dxf", ".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
                 ".csv": "text/csv; charset=utf-8", ".json": "application/json", ".py": "text/plain; charset=utf-8",
                 ".yaml": "text/plain; charset=utf-8", ".zip": "application/zip"}
        with open(full, "rb") as f:
            data = f.read()
        media = types.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        inline = media.startswith(("image/", "text/", "application/pdf", "application/json"))
        headers = {} if inline else {"Content-Disposition": f'attachment; filename="{os.path.basename(full)}"'}
        return Response(data, media_type=media, headers=headers)

    # -- the scorecard (CALI-47): every requirement measured, every objective tracked -----------------
    @r.post("/api/designs/{slug}/scorecard")
    def scorecard_run(slug: str):
        load(slug)

        def work(j):
            return scorecard.compute(DesignStore.load(slug), emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("scorecard", work, label="score the design", lock=f"score:{slug}")
        return {"job_id": job.id}

    # -- gusset plates (CALI-46): whittle's plate mode at the joints a frame names ---------------------
    @r.post("/api/designs/{slug}/gussets")
    def gussets_run(slug: str, req: GussetRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")

        def work(j):
            return frame_study.gussets(DesignStore.load(slug), req.part, thickness=req.thickness,
                                       plates=req.plates, min_safety=req.min_safety, payload_lb=req.payload_lb,
                                       walls=req.walls, emit=lambda k, t="", **d: j.emit(k, t, **d))

        job = RUNNER.submit("gussets", work, label=f"gussets for {req.part}", lock=f"frame:{slug}")
        return {"job_id": job.id}

    @r.get("/api/designs/{slug}/gussets/{rid}/{joint}/{name}")
    def gussets_file(slug: str, rid: str, joint: str, name: str):
        store = load(slug)
        if frame_study.load_gussets(store, rid) is None or "/" in joint or ".." in joint:
            raise HTTPException(status_code=404, detail="no such study")
        path = os.path.join(frame_study.gussets_dir(store), rid, joint, os.path.basename(name))
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="no such file")
        with open(path, "rb") as f:
            data = f.read()
        return Response(data, media_type="image/svg+xml" if name.endswith(".svg") else "application/dxf")

    @r.post("/api/designs/{slug}/gussets/{rid}/adopt")
    def gussets_adopt(slug: str, rid: str, req: GussetPick):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                got = frame_study.adopt_gussets(store, rid, req.picks or None)
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=409, detail=str(e))
            store.append_log({"kind": "gussets", "action": "adopted", "run": rid})
            return {**got, "design": design_state(DesignStore.load(slug))}

    @r.get("/api/designs/{slug}/frame-study/{rid}/stations/{index}.stl")
    def frame_station(slug: str, rid: str, index: int):
        store = load(slug)
        try:
            path = frame_study.station_path(store, rid, index)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad run id")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="no such design")
        with open(path, "rb") as f:
            return Response(f.read(), media_type="model/stl")

    @r.post("/api/designs/{slug}/frame-study/{rid}/adopt")
    def frame_adopt(slug: str, rid: str, req: Adopt):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            try:
                got = frame_study.adopt(store, rid, req.station)
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=409, detail=str(e))
            store.append_log({"kind": "frame", "action": "adopted", "run": rid,
                              "station": req.station, "version": got["version"],
                              "design": got["design"]})
            return {**got, "design": design_state(store)}

    # -- what it's built from (CALI-41): weight, centre of gravity, bill of materials ---------------
    def _built(store: DesignStore, pid: str, build: Optional[dict] = None) -> dict:
        if store.design.part(pid) is None:
            raise HTTPException(status_code=404, detail=f"no part {pid!r}")
        try:
            return construction.report(store, pid, build)
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=409, detail=str(e))

    @r.get("/api/designs/{slug}/parts/{pid}/construction")
    def part_construction(slug: str, pid: str):
        return _built(load(slug), pid)

    @r.post("/api/designs/{slug}/parts/{pid}/construction")
    def part_construction_whatif(slug: str, pid: str, req: BuildChoices):
        return _built(load(slug), pid, req.build)

    @r.post("/api/designs/{slug}/parts/{pid}/construction/use")
    def part_construction_use(slug: str, pid: str, req: BuildChoices):
        with RUNNER.locked(_lock(slug)):
            store = load(slug)
            if store.design.part(pid) is None:
                raise HTTPException(status_code=404, detail=f"no part {pid!r}")
            try:
                got = construction.adopt(store, pid, req.build)
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=409, detail=str(e))
            if got["changed"]:
                store.append_log({"kind": "build", "action": "adopted", "part": pid,
                                  "version": got["version"], "build": got["changed"]})
            return {**got, "report": construction.report(store, pid), "design": design_state(store)}

    @r.post("/api/designs/{slug}/balance")
    def design_balance(slug: str, req: BalanceRequest):
        try:
            return construction.balance(load(slug), req.build, req.payload_lb)
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=409, detail=str(e))

    # -- parametric drag search (CALI-39): whittle searches PARAMS, numbers come back ---------------
    @r.post("/api/designs/{slug}/aero")
    def aero_run(slug: str, req: AeroRequest):
        store = load(slug)
        if store.design.part(req.part) is None:
            raise HTTPException(status_code=404, detail=f"no part {req.part!r}")
        if not _aero_available():
            raise HTTPException(status_code=503, detail="whittle with ParametricStudy isn't installed "
                                "in Caliper's environment (run `make tools`)")
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
