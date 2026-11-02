"""CALI-59 (#8) — when something breaks, a report you can read and choose to send.

Nothing leaves the machine on its own. What broke (a job that failed, a request that crashed, an error
on the page) is kept on this machine in ``~/.caliper/errors.jsonl`` (or ``$CALIPER_ERRORS``), the newest
50 of them, with your home folder written as ``~``. A **report** is one of them, plus Caliper's version,
the OS and Python. It holds nothing of the design: no prompt, no part, no script. The page shows it in
full, and sending it opens a new GitHub issue in your browser with it filled in, so you send it yourself.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import traceback
import uuid
from typing import Optional
from urllib.parse import quote

KEEP = 50
#: Where a report goes when you choose to send it: a new issue, filled in, in your own browser.
ISSUES = "https://github.com/greentheo/caliper/issues/new"
#: GitHub refuses very long URLs; a report's traceback is cut to fit.
MOST_URL = 7000


def path() -> str:
    return os.environ.get("CALIPER_ERRORS") or os.path.join(os.path.expanduser("~"), ".caliper", "errors.jsonl")


def scrub(text: str) -> str:
    """Your home folder as ``~``, so a report doesn't carry your user name."""
    home = os.path.expanduser("~")
    return (text or "").replace(home, "~") if home and home != "/" else (text or "")


def record(where: str, error: str, trace: str = "") -> dict:
    """Keep one error. Never raises: a failure to record must not hide the failure itself."""
    e = {"id": uuid.uuid4().hex[:8], "at": time.time(), "where": scrub(where)[:200], "error": scrub(error)[:2000],
         "trace": scrub(trace)[-6000:]}
    try:
        p = path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        kept = recent(KEEP - 1)
        with open(p + ".tmp", "w") as f:
            for x in [*reversed(kept), e]:
                f.write(json.dumps(x) + "\n")
        os.replace(p + ".tmp", p)
    except OSError:
        pass
    return e


def record_exception(where: str, exc: BaseException) -> dict:
    return record(where, f"{type(exc).__name__}: {exc}",
                  "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


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
    head = (f"**What broke:** {e['error']}\n**Where:** {e['where']}\n**When:** {when}\n\n"
            f"Caliper {__version__} · {_os()} ({platform.machine()}) · Python {sys.version.split()[0]}\n\n"
            "**What I was doing:** (say here, if you like)\n\n")
    trace = e.get("trace") or ""
    body = head + (f"```\n{trace}\n```\n" if trace else "")
    title = f"Error: {e['error'][:80]}"
    url = f"{ISSUES}?title={quote(title)}&body={quote(body)}"
    while len(url) > MOST_URL and trace:
        trace = trace[len(trace) // 4:]                           # keep the end: the line that failed
        body = head + f"```\n…{trace}\n```\n"
        url = f"{ISSUES}?title={quote(title)}&body={quote(body)}"
    return {"id": e["id"], "title": title, "body": body, "url": url}
