"""CALI-59 (#8) — when something breaks, a report you can read and choose to send.

Nothing leaves the machine on its own. What broke (a job that failed, a request that crashed, an error
on the page) is kept on this machine in ``~/.caliper/errors.jsonl`` (or ``$CALIPER_ERRORS``), the newest
50 of them, with your home folder written as ``~``. A **report** is one of them, plus Caliper's version,
the OS and Python. A job is named by its kind, a design's folder or address by ``designs/<design>``, anyone's home
folder by ``~``, and a YAML error by its line and column, not the lines it quotes. The error's own words can still
quote what was typed or name a part, so the page shows the report in full, and sending it opens a new GitHub issue in your browser with it filled in, so you
send it yourself.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import threading
import time
import traceback
import uuid
from typing import Optional
from urllib.parse import quote


class Refused(KeyError):
    """A choice the person's script can't take ("the script has no BUILD dict"): the server says it as a refusal (a 409,
    a plain line on the page), where a KeyError from a bug shows as the crash it is, with Report it (#237 review)."""

    def __str__(self) -> str:                   # its words, not KeyError's quoted repr
        return str(self.args[0]) if self.args else ""


KEEP = 50
#: One writer at a time: two errors at once could lose one, or raise (CALI-92, #70 item 12).
_MU = threading.Lock()
#: Where a report goes when you choose to send it: a new issue, filled in, in your own browser.
ISSUES = "https://github.com/greentheo/caliper/issues/new"
#: GitHub refuses very long URLs; a report's traceback is cut to fit.
MOST_URL = 7000


def path() -> str:
    return os.environ.get("CALIPER_ERRORS") or os.path.join(os.path.expanduser("~"), ".caliper", "errors.jsonl")


#: What a job was, said by its kind: a job's label is the person's own words (a chat turn's is their message).
JOBS = {"chat": "a chat turn", "clarify": "a question about the design", "firstrun": "a first build",
        "load": "a strength check", "lighten": "lightening a part", "carve": "carving a part",
        "picture": "a picture on a part", "goals": "writing what it's held to", "scorecard": "a scorecard",
        "cutplan": "a cut plan", "release": "a build package", "frame": "sizing a frame",
        "gussets": "gusset plates", "aero": "a drag search", "whittle": "a whittle study"}
#: A design's folder or address names it, and a design's name is the person's words (its slug comes from them).
_DESIGN = re.compile(r"designs/[^/\s'\"]+")
_HOMES = re.compile(r"/(?:Users|home)/[^/\s'\"]+")
#: API keys and tokens by their shape: a key must never reach a report or the page (#215 review).
_SECRETS = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                      r"|xox[abprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16})")
#: ... and by where they're set, whatever they look like.
_SECRET_ENV = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)


def job_where(kind: str) -> str:
    return JOBS.get(kind, f"a {kind} job")


def scrub(text: str) -> str:
    """Your home folder as ``~`` and any design's name as ``<design>``, so a report carries neither your user
    name nor anything you called a design."""
    text = _SECRETS.sub("<secret>", text or "")
    for name, value in os.environ.items():
        if _SECRET_ENV.search(name) and len(value) >= 12:
            text = text.replace(value, "<secret>")
    custom = os.environ.get("CALIPER_DESIGNS")
    if custom:
        text = re.sub(re.escape(custom.rstrip("/")) + r"/[^/\s'\"]+", "designs/<design>", text)
    home = os.path.expanduser("~")
    if home and home != "/":
        text = text.replace(home, "~")
    text = _HOMES.sub("~", text)                             # anyone's home folder, not just this one (CALI-86)
    return _DESIGN.sub("designs/<design>", text)


def scrubbed(e) -> str:
    """An exception (or its text) as a person or a report may read it (#215 review)."""
    return scrub(str(e))


def record(where: str, error: str, trace: str = "") -> dict:
    """Keep one error. Never raises: a failure to record must not hide the failure itself."""
    e = {"id": uuid.uuid4().hex[:8], "at": time.time(), "where": scrub(where)[:200], "error": scrub(error)[:2000],
         "trace": scrub(trace)[-6000:]}
    try:
        p = path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = f"{p}.{uuid.uuid4().hex[:8]}.tmp"          # its own: never another writer's half-written file
        with _MU:
            kept = recent(KEEP - 1)
            with open(tmp, "w") as f:
                for x in [*reversed(kept), e]:
                    f.write(json.dumps(x) + "\n")
            os.replace(tmp, p)
    except OSError:
        pass
    return e


def _said(exc: BaseException) -> str:
    """What the exception says, minus anything it quotes from a file the person wrote: a YAML error keeps its
    problem, line and column but not the excerpt it shows, which is their own words (CALI-86)."""
    try:
        import yaml
    except ImportError:                                   # pragma: no cover — yaml is a dependency
        yaml = None
    if yaml is not None and isinstance(exc, yaml.MarkedYAMLError):
        mark = exc.problem_mark or exc.context_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        return f"{type(exc).__name__}: {exc.problem or exc.context or 'the file would not parse'}{where}"
    return f"{type(exc).__name__}: {exc}"


def record_exception(where: str, exc: BaseException) -> dict:
    said = _said(exc)
    frames = "".join(traceback.format_tb(exc.__traceback__))
    return record(where, said, "Traceback (most recent call last):\n" + frames + said)


def plain(e: dict) -> str:
    """What a page is told when a request crashes: a sentence and the error's id, never the error's own words."""
    return f"Something went wrong on Caliper's side (error {e['id']}). You can see what broke and report it."


def recent(n: int = 10) -> list[dict]:
    """The newest first."""
    try:
        with open(path()) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return []
    return list(reversed(rows))[:n]


def _os() -> str:
    mac = platform.mac_ver()[0]
    return f"macOS {mac}" if mac else f"{platform.system()} {platform.release()}"


def report(error_id: Optional[str] = None) -> Optional[dict]:
    """One error as a report: ``{"id", "title", "body", "url"}``, the newest if no id is given."""
    from . import __version__

    rows = recent(KEEP)
    e = next((x for x in rows if x["id"] == error_id), None) if error_id else (rows[0] if rows else None)
    if e is None:
        return None
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["at"]))

    def build(error: str, trace: str) -> tuple[str, str, str]:
        head = (f"**What broke:** {error}\n**Where:** {e['where']}\n**When:** {when}\n\n"
                f"Caliper {__version__} · {_os()} ({platform.machine()}) · Python {sys.version.split()[0]}\n\n"
                "**What I was doing:** (say here, if you like)\n\n")
        body = head + (f"```\n{trace}\n```\n" if trace else "")
        title = f"Error: {error[:80]}"
        return title, body, f"{ISSUES}?title={quote(title)}&body={quote(body)}"

    # too long for a link: cut the trace from its start (the end is the line that failed), then the error from its
    # end. Each pass cuts at least a character, so it always stops.
    error, trace = e["error"], e.get("trace") or ""
    title, body, url = build(error, trace)
    while len(url) > MOST_URL and (trace or len(error) > 1):
        if trace:
            trace = trace[max(1, len(trace) // 4):]
            title, body, url = build(error, "…" + trace if trace else "")
        else:
            error = error[:len(error) - max(1, len(error) // 4)]
            title, body, url = build(error + "…", "")
    return {"id": e["id"], "title": title, "body": body, "url": url}
