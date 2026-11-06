"""CALI-31 — background jobs whose progress streams to the page.

Authoring a part is several LLM round trips over tens of seconds; a whittle sweep is a minute or
two. The webapp's handlers were synchronous POSTs, so the page sat dead for the whole run and a chat
read as broken. A :class:`Job` runs the work on a worker thread and records **events** as it goes —
the same events :func:`caliper.chat.turn` already emits through ``on_event`` — and the page follows
them over Server-Sent Events (``GET /api/jobs/{id}/events``).

Two jobs that write the same design must not interleave (``DesignStore`` is single-writer), but a
whittle sweep that is only *waiting on whittle* shouldn't block a chat about a different part. So
every job names a ``lock`` key: jobs sharing a key run one at a time, jobs with different keys run
side by side.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

#: How long a finished job's events stay readable. A page that reconnects late still gets the result.
KEEP_FINISHED_S = 60 * 60


class Cancelled(Exception):
    """Raised at a step boundary of a job asked to stop (CALI-101): it ends "cancelled", not "error"."""


class Busy(Exception):
    """An exclusive job's lock is taken: ``job`` is the one queued or running under it (CALI-101)."""

    def __init__(self, job: "Job"):
        super().__init__(f"{job.kind} {job.id} is {job.status}")
        self.job = job


class Job:
    """One unit of background work and everything it has said so far."""

    def __init__(self, kind: str, label: str = "", lock: str = ""):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.label = label
        self.lock = lock or self.id
        self.status = "queued"            # queued | running | done | error | cancelled
        self.events: list[dict] = []
        self.result: Any = None
        self.error = ""
        self.error_id = ""                # what it's kept as, for a report (CALI-59)
        self.created = time.time()
        self.finished: Optional[float] = None
        self._mu = threading.Lock()
        self._stop = threading.Event()    # asked to stop (CALI-101)

    def emit(self, kind: str, text: str = "", **data) -> dict:
        """Record one step of progress. Safe to call from the worker thread."""
        with self._mu:
            ev = {"seq": len(self.events), "kind": kind, "text": text, "t": time.time(), **data}
            self.events.append(ev)
        return ev

    def since(self, after: int) -> list[dict]:
        with self._mu:
            return list(self.events[after:])

    @property
    def over(self) -> bool:
        return self.status in ("done", "error", "cancelled")

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def check(self) -> None:
        """A step boundary: raise :class:`Cancelled` if the job's been asked to stop. The work calls it between
        steps, so a cancel takes effect there, with every finished step kept."""
        if self._stop.is_set():
            raise Cancelled()

    def to_dict(self, after: int = 0) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label, "status": self.status,
                "events": self.since(after), "result": self.result, "error": self.error,
                "error_id": self.error_id, "stopping": self.stopping}


class JobRunner:
    """A small worker pool with per-key serialization."""

    #: Called between an exclusive submit's check and its queueing, for a test that the two are one step (CALI-101).
    _between: Optional[Callable[[], None]] = None

    def __init__(self, workers: int = 4):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="caliper-job")
        self._jobs: dict[str, Job] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._mu = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Job], Any], *, label: str = "",
               lock: str = "", exclusive: bool = False) -> Job:
        """Queue ``fn(job)``; its return value becomes ``job.result``. Returns immediately.

        ``exclusive``: refuse (raise :class:`Busy`) while a job with this lock is queued or running, checked and
        queued in one step, so two requests 11 ms apart can't both get through (CALI-101)."""
        job = Job(kind, label=label, lock=lock)
        with self._mu:
            self._prune()
            if exclusive:
                ahead = next((j for j in self._jobs.values() if j.lock == job.lock and not j.over), None)
                if ahead is not None:
                    raise Busy(ahead)
                if self._between is not None:   # a test's hook between the check and the queueing (#102 review)
                    self._between()
            self._jobs[job.id] = job
            key_lock = self._locks.setdefault(job.lock, threading.Lock())
        self._pool.submit(self._run, job, fn, key_lock)
        return job

    def cancel(self, job_id: str) -> Optional[Job]:
        """Ask a job to stop (CALI-101): a queued one never starts; a running one stops at its next step boundary
        (:meth:`Job.check`). One that's over is left as it is. None if there's no such job."""
        with self._mu:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            asked = not job._stop.is_set()
            job._stop.set()
            if job.status == "running" and asked:          # said, so a page that reloads hears it (#102 review)
                job.emit("stopping", "stopping at the next step…")
            if job.status == "queued":
                job.status = "cancelled"
                job.finished = time.time()
                job.emit("cancelled", "cancelled before it started")
        return job

    def running(self, lock: str) -> Optional[Job]:
        """The job queued or running under this lock, if any."""
        with self._mu:
            return next((j for j in self._jobs.values() if j.lock == lock and not j.over), None)

    def busy(self, lock: str) -> bool:
        """Is a job with this lock queued or running? (So a background job isn't queued twice.)"""
        with self._mu:
            return any(j.lock == lock and j.status in ("queued", "running") for j in self._jobs.values())

    def get(self, job_id: str) -> Optional[Job]:
        with self._mu:
            return self._jobs.get(job_id)

    def locked(self, key: str) -> threading.Lock:
        """The lock jobs with this key share — hold it for a quick *synchronous* write too.

        Without this, a request that flips a setting while a chat job is mid-turn would be silently
        overwritten when the job saves the design it loaded before the change (a lost update).
        """
        with self._mu:
            return self._locks.setdefault(key, threading.Lock())

    def _run(self, job: Job, fn: Callable[[Job], Any], key_lock: threading.Lock) -> None:
        with key_lock:
            with self._mu:
                if job.status == "cancelled":                 # cancelled while it waited (CALI-101)
                    return
                job.status = "running"
            job.emit("started", job.label)
            try:
                job.result = fn(job)
                job.status = "done"
                job.emit("finished", "done")
            except Cancelled:
                job.status = "cancelled"
                job.emit("cancelled", "cancelled: it stopped at a step, and kept the steps it finished")
            except Exception as e:  # noqa: BLE001 — every failure must reach the page, named
                # the traceback's LAST line is the actual exception (the CALI-27 discipline)
                tail = [ln for ln in traceback.format_exc().strip().splitlines() if ln.strip()]
                job.error = f"{type(e).__name__}: {e}"
                from . import errors

                # kept by its kind, never its label (a chat turn's label is the message, CALI-86), and before
                # the job reads as failed, so whoever sees it fail has the error to report
                job.error_id = errors.record_exception(errors.job_where(job.kind), e)["id"]
                job.status = "error"
                job.emit("error", job.error, trace=tail[-1] if tail else "")
            finally:
                job.finished = time.time()

    def _prune(self) -> None:
        cutoff = time.time() - KEEP_FINISHED_S
        for jid in [j.id for j in self._jobs.values() if j.finished and j.finished < cutoff]:
            self._jobs.pop(jid, None)


RUNNER = JobRunner()


def stream(job: Job, after: int = 0, poll: float = 0.2, heartbeat: float = 15.0):
    """Server-Sent Events for a job: every event, then one ``end`` frame when it's over.

    A plain generator so it works under Starlette's ``StreamingResponse`` (sync generators run on
    the threadpool). Sends a comment heartbeat while a long step is quiet, so proxies and the browser
    don't decide the connection died during a two-minute whittle sweep.
    """
    import json

    seq, quiet = after, time.time()
    while True:
        fresh = job.since(seq)
        for ev in fresh:
            seq = ev["seq"] + 1
            yield f"id: {ev['seq']}\ndata: {json.dumps(ev, default=str)}\n\n"
        if fresh:
            quiet = time.time()
        if job.over and not job.since(seq):
            final = {"kind": "end", "status": job.status, "result": job.result, "error": job.error,
                     "error_id": job.error_id}
            yield f"data: {json.dumps(final, default=str)}\n\n"
            return
        if time.time() - quiet > heartbeat:
            quiet = time.time()
            yield ": keep-alive\n\n"
        time.sleep(poll)
