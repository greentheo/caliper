"""CALI-132 (#163) — one strength study at a time in this process, and a waiting one says so.

Found reviewing #159: a Lighten running beside a carve read its FEA wrong and stopped at step 0 (0.17x to 0.7x, against
3.11x alone), with nothing on the record to say so. The cause wasn't found; jobs share a thread pool and each takes only
its own lock. Three different low values looks like a race, and a race can read high as easily as low, so these studies
take turns. A strength number that can't be trusted is worse than one that's late (rule 6).
"""

from __future__ import annotations

import contextlib
import functools
import threading
import time
from typing import Callable, Optional

#: re-entrant: a study that starts another (a carve's first check) is still one study
_TURN = threading.RLock()
#: what a study waiting its turn says; names no other design or part, whoever's it is
WAITING = "Waiting for another strength study on this server to finish."
#: how often a waiting study says how it's going (#174: nobody waits for hours without being told)
TELL_EVERY_S = 30.0
_mu = threading.Lock()
_since = 0.0                      # when the study that has the turn got it
_queued = 0                       # how many are waiting for it


def _how_long(others: int) -> str:
    gone = max(0.0, time.monotonic() - _since) / 60.0
    return (f"{WAITING} It's been running {f'{gone:.0f} min' if gone >= 1 else 'under a minute'}"
            + (f", and {others} other{'s are' if others != 1 else ' is'} waiting too." if others else "."))


def take_turn(emit: Optional[Callable] = None, stop: Optional[Callable[[], None]] = None) -> bool:
    """Wait for this thread's turn, saying so once if it has to wait. ``stop`` may raise, to cancel while waiting.
    True if it waited."""
    global _since, _queued
    mine = _TURN._is_owned()          # a study inside a study isn't a new one
    if _TURN.acquire(blocking=False):
        if not mine:
            _since = time.monotonic()
        return False
    if emit:
        emit("waiting", WAITING)
    told = time.monotonic()
    with _mu:
        _queued += 1
    try:
        while not _TURN.acquire(timeout=0.25):
            if stop:
                stop()
            if emit and time.monotonic() - told >= TELL_EVERY_S:
                told = time.monotonic()
                with _mu:
                    others = _queued - 1
                emit("waiting", _how_long(others))
    finally:
        with _mu:
            _queued -= 1
    _since = time.monotonic()
    return True


@contextlib.contextmanager
def my_turn(store, emit: Optional[Callable] = None, stop: Optional[Callable[[], None]] = None):
    """This thread's turn, held for a block, for a caller that has to look at what's there once it has waited (#184: a build package
    queued behind a strength check ran the same check again). Re-entrant, so a study inside it doesn't wait. One that waited
    reads the design again, as :func:`one_at_a_time` does."""
    waited = take_turn(emit, stop)
    try:
        if waited:
            store.__dict__.update(type(store).load(store.root).__dict__)
        yield
    finally:
        _TURN.release()


def one_at_a_time(study: Callable) -> Callable:
    """A study (``emit=``, ``stop=`` by keyword, where it has them) that takes its turn. One that waited works from the
    design as it is now, not as it was when it was asked for (#169 review: a part revised during the wait, and v1's record
    carried v2's number): its store is read again, in place, so whoever holds it sees the same."""

    @functools.wraps(study)
    def run(*args, **kw):
        waited = take_turn(kw.get("emit"), kw.get("stop"))
        try:
            if waited and args and hasattr(args[0], "root"):
                args[0].__dict__.update(type(args[0]).load(args[0].root).__dict__)
            return study(*args, **kw)
        finally:
            _TURN.release()

    return run
