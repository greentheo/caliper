"""CALI-132 (#163) — one strength study at a time in this process, and a waiting one says so.

Found reviewing #159: a Lighten running beside a carve read its FEA wrong and stopped at step 0 (0.17x to 0.7x, against
3.11x alone), with nothing on the record to say so. The cause wasn't found; jobs share a thread pool and each takes only
its own lock. Three different low values looks like a race, and a race can read high as easily as low, so these studies
take turns. A strength number that can't be trusted is worse than one that's late (rule 6).
"""

from __future__ import annotations

import functools
import threading
from typing import Callable, Optional

#: re-entrant: a study that starts another (a carve's first check) is still one study
_TURN = threading.RLock()
#: what a study waiting its turn says; names no other design or part, whoever's it is
WAITING = "Waiting for another strength study on this server to finish."


def take_turn(emit: Optional[Callable] = None, stop: Optional[Callable[[], None]] = None) -> None:
    """Wait for this thread's turn, saying so once if it has to wait. ``stop`` may raise, to cancel while waiting."""
    if _TURN.acquire(blocking=False):
        return
    if emit:
        emit("waiting", WAITING)
    while not _TURN.acquire(timeout=0.25):
        if stop:
            stop()


def one_at_a_time(study: Callable) -> Callable:
    """A study (``emit=``, ``stop=`` by keyword, where it has them) that takes its turn."""

    @functools.wraps(study)
    def run(*args, **kw):
        take_turn(kw.get("emit"), kw.get("stop"))
        try:
            return study(*args, **kw)
        finally:
            _TURN.release()

    return run
