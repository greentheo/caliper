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

import numpy as np

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


def _build(script: str, values: Optional[dict] = None) -> Optional[dict]:
    """A build of ``script`` (with ``values`` written into its PARAMS): ``{"names", "declared", "mesh"}``, or None where it
    won't build."""
    from . import aero, sandbox

    run = sandbox.run_script(aero.set_params(script, values) if values else script, {})
    if not run.ok:
        return None
    declared = run.declared or {}
    try:
        mesh = run.geometry.require_mesh()
    except Exception:  # noqa: BLE001 — no mesh to compare: its shape isn't known, said by the caller
        mesh = None
    return {"names": [it.get("name") for it in declared.get("construction") or [] if isinstance(it, dict)],
            "declared": declared, "mesh": mesh}


#: How finely the two builds are compared (#332 review): about this many points across the part's box.
SAMPLES = 200_000
#: Material a build at 0 may add or take from another piece and still only have taken that piece away: tessellation's
#: noise, never a rounded corner or a thinner sheet (the reviewer's fillet_r squared the top's corners: +2,350 mm³).
CHANGE_MM3 = 50.0


def _regions(shapes: list, mesh, pts: np.ndarray, margin: float) -> np.ndarray:
    """For each point, the index of the declared sheet or stick it's inside (by a margin), or -1. A sheet's thickness goes
    to the side of its outline the solid is on."""
    from . import spatial
    from .consistency import _inside2d

    owner = np.full(len(pts), -1)
    for i, sh in enumerate(shapes):
        if sh["kind"] == "sheet":
            for poly in sh["polys"]:
                o = poly[0]
                n = np.cross(poly[1] - poly[0], poly[2] - poly[0])
                for k in range(2, len(poly) - 1):
                    if np.linalg.norm(n) > 1e-9:
                        break
                    n = np.cross(poly[k] - poly[0], poly[k + 1] - poly[0])
                n = n / (np.linalg.norm(n) or 1.0)
                u = (poly[1] - poly[0]) / (np.linalg.norm(poly[1] - poly[0]) or 1.0)
                v = np.cross(n, u)
                t = float(sh["thickness"])
                mid = poly.mean(axis=0)
                side = 1.0 if spatial.contains(mesh, np.array([mid + n * t / 2]))[0] else -1.0
                rel = pts - o
                d = rel @ (n * side)
                m = min(margin, t / 4)
                inside = (d > m) & (d < t - m) & _inside2d(np.stack([rel @ u, rel @ v], 1),
                                                            np.stack([(poly - o) @ u, (poly - o) @ v], 1))
                owner[inside & (owner < 0)] = i
        elif sh["kind"] == "stick":
            a, b, half = np.asarray(sh["a"], float), np.asarray(sh["b"], float), float(sh["half"])
            L = float(np.linalg.norm(b - a)) or 1.0
            ax = (b - a) / L
            along = (pts - a) @ ax
            off = np.linalg.norm((pts - a) - np.outer(along, ax), axis=1)
            m = min(margin, half / 2)
            inside = (along > m) & (along < L - m) & (off < half - m)
            owner[inside & (owner < 0)] = i
    return owner


def _also(before: dict, after: dict, piece: str) -> Optional[str]:
    """What else the build at 0 changes, in words, or None where it only took ``piece`` away (#332 review): material
    added anywhere (a corner squared), or taken from inside another declared piece (a sheet thinned)."""
    from . import consistency, spatial

    m0, m1 = before["mesh"], after["mesh"]
    if m0 is None or m1 is None:
        return "its shape couldn't be compared"
    lo, hi = np.minimum(m0.bounds[0], m1.bounds[0]), np.maximum(m0.bounds[1], m1.bounds[1])
    s = max(float(np.prod(hi - lo) / SAMPLES) ** (1 / 3), 0.25)
    axes = [np.arange(lo[k] + s / 2, hi[k], s) for k in range(3)]
    pts = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    was, now = spatial.contains(m0, pts), spatial.contains(m1, pts)
    cell = s ** 3
    try:
        shapes = [sh for sh in consistency.shapes(before["declared"]) if sh["name"] != piece]
    except ValueError:                           # a piece it can't weigh: no regions to name
        shapes = []
    owner = _regions(shapes, m0, pts, s / 2) if shapes else np.full(len(pts), -1)
    added, taken = now & ~was, was & ~now & (owner >= 0)
    for what, mask in (("changes", added), ("changes", taken)):
        if mask.sum() * cell > CHANGE_MM3:
            hit = owner[mask & (owner >= 0)]
            if len(hit):
                return f"{what} the {shapes[int(np.bincount(hit).argmax())]['name']}"
            return "adds to the part where nothing is declared"
    return None


#: What :func:`off_switch` found, by the script's text and the piece: a version builds its few tries once (Things to fix asks
#: on every open).
_FOUND: dict = {}


def _found(store: DesignStore, pid: str, piece: str) -> tuple:
    import hashlib

    script = store.read_script(pid)
    key = (hashlib.sha1(script.encode()).hexdigest(), piece)
    if key not in _FOUND:
        if len(_FOUND) > 256:
            _FOUND.clear()
        _FOUND[key] = _off_switch(store, pid, piece, script)
    return _FOUND[key]


def off_switch(store: DesignStore, pid: str, piece: str) -> Optional[dict]:
    """The number that turns ``piece`` off, built to be sure: ``{"param", "value": 0, "unit"}``, the first of
    :func:`named` whose build at 0 has every piece it has now but that one, each of them as it was (#332 review: a
    number that also squares a corner or thins a sheet isn't it). None where none does."""
    return _found(store, pid, piece)[0]


def off_why(store: DesignStore, pid: str, piece: str) -> Optional[str]:
    """Why a number that turns ``piece`` off isn't the off switch, in words: "fillet_r turns them off but also changes the
    top". None where there's a switch, or no number turned it off."""
    return _found(store, pid, piece)[1]


def _off_switch(store: DesignStore, pid: str, piece: str, script: str) -> tuple:
    now = _build(script)
    if not now or piece not in now["names"]:
        return None, None
    rest = sorted(n for n in now["names"] if n != piece)
    why = None
    for e in named(store, pid, piece)[:TRIES]:
        got = _build(script, {e["name"]: 0})
        if got is None or piece in got["names"]:
            continue
        them = "them" if _many(piece) else "it"
        if sorted(got["names"]) != rest:         # it took another piece away too
            gone = [n for n in rest if n not in got["names"]]
            why = why or (f"{e['name']} turns {them} off but also takes away the {' and the '.join(gone)}"
                          if gone else f"{e['name']} turns {them} off but also changes what the part declares")
            continue
        also = _also(now, got, piece)
        if also is not None:
            why = why or f"{e['name']} turns {them} off but also {also}"
            continue
        return {"param": e["name"], "value": 0, "unit": e.get("unit") or "mm"}, None
    return None, why


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
    why = off_why(store, pid, piece)              # a number that would, but changes another piece too: said (#332)
    lead = f"{why}, so it" if why else f"that changes {pid}'s code, so it"
    return {"piece": piece, "name": name, "how": "designer", "designer_call": True, **({"why": why} if why else {}),
            "said": f"Delete the {name}: {lead} asks the designer (one Claude call, about a minute). A new version of "
                    f"{pid}, rolled back as any other."}


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
