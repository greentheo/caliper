"""CALI-157 (#223) — the one door to Claude: which model does which job, how hard it thinks, and what happens when it won't or can't answer.

Every request goes through :func:`ask`, named by its job in :data:`JOBS`, so a job moves to another model with one line. Thinking counts inside
``max_tokens`` on these models, so the caps are set for that, and a reply cut off is a failure, never half an answer read as a whole one.
"""

from __future__ import annotations

import contextvars
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("caliper.llm")

DEFAULT_MODEL = "claude-opus-5-5"
QUICK_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class Job:
    model: str
    effort: str
    max_tokens: int
    stream: bool = False      # a long reply: a plain request would hit the HTTP timeout
    cache: bool = False       # a long system prompt resent every try


#: Who does what. A job moves with one line here, or for one run with ``CALIPER_MODEL_<JOB>`` (``CALIPER_MODEL_CLASSIFY``); ``CALIPER_MODEL`` moves them all.
JOBS = {
    "classify": Job(QUICK_MODEL, "low", 2000),
    "describe": Job(QUICK_MODEL, "low", 2000),
    "clarify": Job(QUICK_MODEL, "low", 4000),
    "explain": Job(DEFAULT_MODEL, "medium", 4000),
    "author": Job(DEFAULT_MODEL, "high", 64000, stream=True, cache=True),
    "plan": Job(DEFAULT_MODEL, "high", 32000, stream=True),
    "refine": Job(DEFAULT_MODEL, "high", 8000),
    "intake": Job(DEFAULT_MODEL, "medium", 8000),
    "goals": Job(DEFAULT_MODEL, "medium", 8000),
    "promote": Job(DEFAULT_MODEL, "medium", 8000),
    "draw": Job(DEFAULT_MODEL, "medium", 8000),
}
#: The server re-runs a declined request on another model by itself, on these models (server-side refusal fallbacks).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACKS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")
#: Models that reject ``output_config.effort``.
_NO_EFFORT = ("claude-sonnet-4-5", "claude-haiku-4-5", "claude-3")


class Stopped(RuntimeError):
    """Claude gave no usable answer, for a reason a person should be told."""


class Declined(Stopped):
    """Claude's safety checks stopped the request (``stop_reason`` "refusal")."""


class CutOff(Stopped):
    """The reply hit ``max_tokens`` before it finished."""


def said(e: Exception) -> str:
    """What to tell the person when Claude gave no usable answer: the one place these words are read from."""
    return str(e)


def tell(store, e: Exception, then: str = "") -> str:
    """:func:`said`, on the design's own record, for a path that carries on without Claude's answer."""
    words = f"{said(e)}.{' ' + then if then else ''}"
    store.append_log({"kind": "reply", "action": "claude", "ok": False, "reply": words})
    return words


_LOG_TO: contextvars.ContextVar = contextvars.ContextVar("caliper_llm_log", default=None)


def log_to(store) -> None:
    """Which design's log this request's Claude calls are noted in. A job inherits it from the request that started it."""
    _LOG_TO.set(store)


def model_for(job: str, model: Optional[str] = None) -> str:
    """The model for a job, as of now: a ``.env`` loaded after import still counts."""
    return model or os.environ.get(f"CALIPER_MODEL_{job.upper()}") or os.environ.get("CALIPER_MODEL") or JOBS[job].model


def _declined(msg) -> Declined:
    category = getattr(getattr(msg, "stop_details", None), "category", None)
    return Declined("Claude's safety checks stopped this request" + (f" ({category})" if category else "") + ": try saying it another way")


def _note(job: str, name: str, msg, seconds: float, retried_from: Optional[str]) -> None:
    usage = getattr(msg, "usage", None)
    entry = {"kind": "model", "job": job, "model": getattr(msg, "model", None) or name, "seconds": round(seconds, 1),
             "cache_read": getattr(usage, "cache_read_input_tokens", None), **({"after_refusal_on": retried_from} if retried_from else {})}
    log.info("%s", entry)
    store = _LOG_TO.get()
    if store is not None:
        try:
            store.append_log(entry)
        except OSError:              # a note about a call never stops the call's answer
            pass


def _once(client, name: str, job: str, kw: dict):
    spec = JOBS[job]
    kw = {**kw, "model": name}
    if not name.startswith(_NO_EFFORT):
        kw["output_config"] = {"effort": spec.effort}
    api, beta = client.messages, getattr(client, "beta", None)
    if name in _FALLBACKS and beta is not None:
        api = beta.messages
        kw.update({"betas": [FALLBACK_BETA], "fallbacks": "default"})
    if spec.stream and hasattr(api, "stream"):
        with api.stream(**kw) as running:
            return running.get_final_message()
    return api.create(**kw)


def ask(client, job: str, *, messages: list, system: Optional[str] = None, tools: Optional[list] = None, model: Optional[str] = None,
        cut_off_ok: bool = False):
    """One request, by its job in :data:`JOBS`. A refusal on a model with no server-side fallback (Haiku) is asked of Opus once. ``cut_off_ok``:
    the caller reads a reply cut off itself. Raises :class:`Declined`, or :class:`CutOff`."""
    spec, name = JOBS[job], model_for(job, model)
    kw: dict = {"max_tokens": spec.max_tokens, "messages": messages}
    if system is not None:
        kw["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] if spec.cache else system
    if tools:
        kw["tools"] = tools
    started = time.time()
    msg, retried_from = _once(client, name, job, kw), None
    if getattr(msg, "stop_reason", None) == "refusal" and name not in _FALLBACKS and name != DEFAULT_MODEL:
        retried_from, name = name, DEFAULT_MODEL
        msg = _once(client, name, job, kw)
    _note(job, name, msg, time.time() - started, retried_from)
    stop = getattr(msg, "stop_reason", None)
    if stop == "refusal":
        raise _declined(msg)
    if stop == "max_tokens" and not cut_off_ok:
        raise CutOff(f"Claude's reply was cut off at {spec.max_tokens} tokens, before it finished")
    return msg
