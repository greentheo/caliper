"""CALI-105 (#98) — what Caliper just asked, so the next short answer means that.

On Theo's bar stool Caliper ended a reply with its own instruction ("Tell me to have a go"); he typed "have a go", and
the LLM router sent it to author a new part. A question Caliper asks parks what it's waiting for here, as a proposal
already does (``promote.pending``), and the next turn reads a go-ahead or a no against it first, with no LLM:

- ``fix_rule``: an accepted rule that doesn't hold yet ("have a go" refines that part to meet it);
- ``remove``: "Remove conical_skirt? Its files go to the design's trash." (yes removes it);
- ``repeat``: a request that matches what the last revision just did (yes does it again on top).

Anything else lets the question lapse: the turn goes on as ever.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from .design import DesignStore

#: a go-ahead: Caliper's own "Tell me to have a go", and the short ways to say yes
_GO = re.compile(r"\b(have a go|have a try|go ahead|go for it|try it|fix it|do it|do that|yes|yep|yeah|sure|ok|okay|"
                 r"please do|make it so|again)\b", re.I)
_NO = re.compile(r"\b(no|nope|don'?t|do not|skip|leave it|not now|nah|forget it|cancel|keep it)\b", re.I)


def path(store: DesignStore) -> str:
    return os.path.join(store.root, "awaiting.json")


def park(store: DesignStore, kind: str, **data) -> dict:
    """What Caliper's question waits for; one at a time, the newest."""
    got = {"kind": kind, **data, "at": time.time()}
    with open(path(store), "w") as f:
        json.dump(got, f, indent=2)
    return got


def pending(store: DesignStore) -> Optional[dict]:
    try:
        with open(path(store)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clear(store: DesignStore) -> None:
    if os.path.exists(path(store)):
        os.remove(path(store))


def reads(message: str) -> Optional[bool]:
    """A short go-ahead (True), a no (False), or not an answer to the question (None): a longer message is its own
    request, never taken as yes."""
    text = (message or "").strip().lower()
    if not text or len(text.split()) > 6:
        return None
    go, no = _GO.search(text), _NO.search(text)
    if no and not go:
        return False
    if go and not no:
        return True
    return None
