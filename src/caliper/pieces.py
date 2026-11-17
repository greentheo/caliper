"""CALI-196 (#324): a piece of a part, deleted from its menu.

A piece is one of the things a part's ``construction()`` declares (the tree's rows under a part, keyed by its declared name).
Taking one away changes the part's code, so it's a new version either way, rolled back as any other:

- **A number turns it off** where one of its PARAMS, set to 0, builds the part without that piece and with every other one
  (step_stool's ``fillet_r`` = 0 skips its inside-corner fillet strips): a number change, at once, no Claude.
- **Otherwise the designer's**: a revise of the part, one Claude call, said with its cost before it's asked.

Which number: one whose name shares a word with the piece's ("fillet_r", "inside corner fillet strips"), tried by building
it at 0, a few at most. A name that only looks right never deletes anything unbuilt.
"""

from __future__ import annotations

import re
from typing import Optional

from .design import DesignStore

#: How many numbers a Delete… tries by building, each a build of the part (a few seconds).
TRIES = 3


def _words(s: str) -> set:
    return {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in re.findall(r"[a-z]+", str(s).lower()) if len(w) >= 3}


def named(store: DesignStore, pid: str, piece: str) -> list[dict]:
    """The part's numbers that could turn ``piece`` off, by name alone: a word in common, a value above 0 and a range
    that lets it be 0. Not built: :func:`off_switch` builds them."""
    from . import params

    want = _words(piece)
    out = []
    for e in params.listing(store, pid):
        rng = e.get("range")
        if not e.get("read") or not isinstance(e.get("value"), (int, float)) or e["value"] <= 0:
            continue
        if rng and rng[0] is not None and float(rng[0]) > 0:
            continue
        if _words(e["name"].replace("_", " ")) & want:
            out.append(e)
    return out


def _declared(script: str, values: Optional[dict] = None) -> Optional[list[str]]:
    """The piece names a build of ``script`` declares (with ``values`` written into its PARAMS), or None where it won't
    build."""
    from . import aero, sandbox

    run = sandbox.run_script(aero.set_params(script, values) if values else script, {})
    if not run.ok:
        return None
    return [it.get("name") for it in (run.declared or {}).get("construction") or [] if isinstance(it, dict)]


#: What :func:`off_switch` found, by the script's text and the piece: a version builds its few tries once (Things to fix asks
#: on every open).
_FOUND: dict = {}


def off_switch(store: DesignStore, pid: str, piece: str) -> Optional[dict]:
    """The number that turns ``piece`` off, built to be sure: ``{"param", "value": 0, "unit"}``, the first of
    :func:`named` whose build at 0 has every piece it has now but that one. None where none does."""
    import hashlib

    script = store.read_script(pid)
    key = (hashlib.sha1(script.encode()).hexdigest(), piece)
    if key not in _FOUND:
        if len(_FOUND) > 256:
            _FOUND.clear()
        _FOUND[key] = _off_switch(store, pid, piece, script)
    return _FOUND[key]


def _off_switch(store: DesignStore, pid: str, piece: str, script: str) -> Optional[dict]:
    now = _declared(script)
    if not now or piece not in now:
        return None
    rest = [n for n in now if n != piece]
    for e in named(store, pid, piece)[:TRIES]:
        got = _declared(script, {e["name"]: 0})
        if got is not None and piece not in got and sorted(got) == sorted(rest):
            return {"param": e["name"], "value": 0, "unit": e.get("unit") or "mm"}
    return None


def plan(store: DesignStore, pid: str, piece: str) -> dict:
    """What Delete… on a piece will do, said before it's done: ``{"piece", "name", "how": number | designer, "param"?,
    "said", "designer_call"}``."""
    from .tree import pieces

    row = next((p for p in pieces(store, pid) if p["key"] == piece), None)
    if row is None:
        raise KeyError(f"{pid} has no piece {piece!r}")
    name = row["name"]
    sw = off_switch(store, pid, piece)
    if sw is not None:
        return {"piece": piece, "name": name, "how": "number", **sw, "designer_call": False,
                "said": f"Delete the {name}: {sw['param']} to 0 turns {'them' if _many(name) else 'it'} off. A number "
                        f"change, at once (no Claude): a new version of {pid}, rolled back as any other."}
    return {"piece": piece, "name": name, "how": "designer", "designer_call": True,
            "said": f"Delete the {name}: that changes {pid}'s code, so it asks the designer (one Claude call, about a "
                    f"minute). A new version of {pid}, rolled back as any other."}


def _many(name: str) -> bool:
    return name.rstrip().endswith("s")


def delete(store: DesignStore, pid: str, piece: str) -> dict:
    """Delete… by its number (the designer's way goes through the chat, as any revise): ``{"version", "said"}``, the
    reply naming what went. Raises ValueError where no number turns it off."""
    from . import params

    p = plan(store, pid, piece)
    if p["how"] != "number":
        raise ValueError(f"no number turns the {p['name']} off: it's the designer's to take out")
    got = params.set_values(store, pid, [{"name": p["param"], "value": 0, "unit": p["unit"]}])
    return {"version": got["version"], "how": "number",
            "said": f"Deleted the {p['name']} from {pid}: {p['param']} to 0 (v{got['version']}). Roll it back to put "
                    f"{'them' if _many(p['name']) else 'it'} back."}
