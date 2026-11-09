"""CALI-105 (#98) — what Caliper just asked, so the next short answer means that.

On Theo's bar stool Caliper ended a reply with its own instruction ("Tell me to have a go"); he typed "have a go", and
the LLM router sent it to author a new part. A question Caliper asks parks what it's waiting for here, as a proposal
already does (``promote.pending``), and the next turn reads a go-ahead or a no against it first, with no LLM:

- ``fix_rule``: an accepted rule that doesn't hold yet ("have a go" refines that part to meet it);
- ``remove``: "Remove conical_skirt? Its files go to the design's trash." (yes removes it);
- ``repeat``: a request that matches what the last revision just did (yes does it again on top).

Only a message that is just the go-ahead or the no answers it. Anything else lets the question lapse: the turn goes on
as ever, as its own request.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from .design import DesignStore

#: the whole message is the answer, or it isn't one (#153 review: "yes, but make it taller" removed the part, and "ok
#: thanks" read as yes); punctuation aside, and a "please" either side of a go-ahead
_GO = re.compile(r"(?:please )?(?:have a go|have a try|go ahead|go for it|try it|fix it|do it|do it again|do that|yes|yep|"
                 r"yeah|sure|ok|okay|please do|make it so|again)(?: please)?")
_NO = re.compile(r"(?:no|nope|nah)(?: thanks| thank you| leave it| keep it| don'?t| skip it| forget it)?|don'?t|do not|"
                 r"skip|skip it|leave it|not now|forget it|cancel|keep it")


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
    """A bare go-ahead (True), a bare no (False), or not an answer (None): the whole message has to be the answer, or
    it's its own request. Nothing is removed or built on a qualified yes."""
    text = " ".join(re.sub(r"[^\w' ]+", " ", (message or "").lower()).split())
    if _GO.fullmatch(text):
        return True
    if _NO.fullmatch(text):
        return False
    return None
