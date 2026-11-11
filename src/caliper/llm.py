"""CALI-157 (#223) — the one door to Claude: which model, how hard it thinks, and what happens when it won't or can't answer.

Every request goes through :func:`ask`. Thinking is always on with Opus 5.5 and counts inside ``max_tokens``, so the caps are set for that
and a reply cut off is a failure, never a half-read answer. ``CALIPER_MODEL`` overrides the model, read when it's asked for, so a ``.env``
loaded after import still counts.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("caliper.llm")

DEFAULT_MODEL = "claude-opus-5-5"
#: The server re-runs a declined request on another model by itself, on these models (server-side refusal fallbacks).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACKS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")
#: Models that reject ``output_config.effort``.
_NO_EFFORT = ("claude-sonnet-4-5", "claude-haiku-4-5", "claude-3")


class Declined(RuntimeError):
    """Claude's safety checks stopped the request (``stop_reason`` "refusal"): said in words, never read as an empty answer."""


class CutOff(RuntimeError):
    """The reply hit ``max_tokens`` before it finished: half an answer isn't one."""


def model_name(model: Optional[str] = None) -> str:
    return model or os.environ.get("CALIPER_MODEL") or DEFAULT_MODEL


def _declined(msg) -> Declined:
    details = getattr(msg, "stop_details", None)
    category = getattr(details, "category", None)
    return Declined("Claude's safety checks stopped this request" + (f" ({category})" if category else "") + ": try saying it another way")


def ask(client, *, max_tokens: int, effort: str, messages: list, system: Optional[str] = None, tools: Optional[list] = None,
        model: Optional[str] = None, cache: bool = False, stream: bool = False, cut_off_ok: bool = False):
    """One request. ``effort``: "high" for writing and revising a design, "low" for routing and short descriptions. ``cache``: mark ``system`` for
    the prompt cache (a long one resent every try). ``stream``: for a long reply, where a plain request would hit the HTTP timeout. ``cut_off_ok``:
    the caller reads a reply cut off itself. Raises :class:`Declined`, or :class:`CutOff`."""
    name = model_name(model)
    kw: dict = {"model": name, "max_tokens": max_tokens, "messages": messages}
    if system is not None:
        kw["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] if cache else system
    if tools:
        kw["tools"] = tools
    if not name.startswith(_NO_EFFORT):
        kw["output_config"] = {"effort": effort}
    api, beta = client.messages, getattr(client, "beta", None)
    if name in _FALLBACKS and beta is not None:
        api = beta.messages
        kw.update({"betas": [FALLBACK_BETA], "fallbacks": "default"})
    if stream and hasattr(api, "stream"):
        with api.stream(**kw) as running:
            msg = running.get_final_message()
    else:
        msg = api.create(**kw)
    usage = getattr(msg, "usage", None)
    if usage is not None:
        log.info("%s: %s in, %s out, %s from the cache", name, getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"),
                 getattr(usage, "cache_read_input_tokens", "?"))
    stop = getattr(msg, "stop_reason", None)
    if stop == "refusal":
        raise _declined(msg)
    if stop == "max_tokens" and not cut_off_ok:
        raise CutOff(f"the reply was cut off at {max_tokens} tokens")
    return msg
