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
            "declared": declared, "mesh": mesh, "solid": run.geometry.solid}


#: Material (mm³) a build at 0 may add, or take from another declared piece, and still have only taken that piece away
#: (#332 review). Measured on the exact solids (OCC booleans, 30–40 ms a compare), so the bar is the kernel's own
#: noise: a true off switch reads 0.000000 mm³, beside a round tube too (#332 re-check: mesh booleans read the tube
#: re-tessellated as 4–9 mm³ "added"). The smallest real change it must see, a 3 mm rounding of a 3/4 in sheet's
#: corners, is 147 mm³.
CHANGE_MM3 = 1.0

#: Couldn't be compared: never read as "no change" (#332 re-check), so the number isn't offered and it's the designer's.
UNCOMPARED = "its shape couldn't be compared"


def _vol(m) -> float:
    return 0.0 if m is None or len(getattr(m, "faces", [])) == 0 else float(abs(m.volume))


def _prisms(shapes: list, mesh, margin: float = 0.5) -> list:
    """Each declared sheet and stick as a solid, inset by ``margin`` (never more than a quarter of its thickness) so a
    neighbour's face against it isn't in it: ``[(name, trimesh)]``. A sheet's thickness goes to the side of its outline the
    solid is on."""
    import shapely.geometry as G
    import trimesh

    from . import spatial

    out = []
    for sh in shapes:
        if sh["kind"] == "sheet":
            t = float(sh["thickness"])
            m = min(margin, t / 4)
            for poly in sh["polys"]:
                o = poly[0]
                n = np.cross(poly[1] - poly[0], poly[2] - poly[0])
                for k in range(2, len(poly) - 1):
                    if np.linalg.norm(n) > 1e-9:
                        break
                    n = np.cross(poly[k] - poly[0], poly[k + 1] - poly[0])
                if np.linalg.norm(n) <= 1e-9:
                    continue
                n = n / np.linalg.norm(n)
                side = 1.0 if spatial.contains(mesh, np.array([poly.mean(axis=0) + n * t / 2]))[0] else -1.0
                u = (poly[1] - poly[0]) / (np.linalg.norm(poly[1] - poly[0]) or 1.0)
                w = side * n                             # into the solid; (u, v, w) right-handed
                v = np.cross(w, u)
                flat = G.Polygon(np.stack([(poly - o) @ u, (poly - o) @ v], 1)).buffer(0).buffer(-m)
                if flat.is_empty or t - 2 * m <= 0:
                    continue
                for part in getattr(flat, "geoms", [flat]):
                    pr = trimesh.creation.extrude_polygon(part, t - 2 * m)
                    frame = np.eye(4)
                    frame[:3, 0], frame[:3, 1], frame[:3, 2], frame[:3, 3] = u, v, w, o + w * m
                    out.append((sh["name"], pr.apply_transform(frame)))
        elif sh["kind"] == "stick":
            a, b, half = np.asarray(sh["a"], float), np.asarray(sh["b"], float), float(sh["half"])
            L = float(np.linalg.norm(b - a))
            m = min(margin, half / 2)
            if L <= 2 * m:
                continue
            ax = (b - a) / L
            out.append((sh["name"], trimesh.creation.cylinder(radius=half - m, segment=[a + ax * m, b - ax * m])))
    return out


def _exact(build: dict):
    """A build's solid, as one OCC shape (a Workplane's solids together), or None."""
    wp = build.get("solid")
    if wp is None:
        return None
    return wp.findSolid() if hasattr(wp, "findSolid") else wp


def _meshed(shape):
    """A small exact solid (what one build has that the other hasn't) as a mesh, for its overlap with the pieces' solids:
    its own skin's error, never the whole part's."""
    import trimesh

    vs, fs = shape.tessellate(0.05, 0.1)
    return trimesh.Trimesh([(v.x, v.y, v.z) for v in vs], fs)


def _also(before: dict, after: dict, piece: str) -> Optional[str]:
    """What else the build at 0 changes, in words, or None where it only took ``piece`` away (#332 review): material
    added anywhere (a corner squared), or taken from inside another declared piece (a sheet thinned). Exact: the two
    builds' solids cut each other (OCC), and what was taken is set against each other piece's solid. Anything that
    fails on the way is :data:`UNCOMPARED`, never None."""
    import trimesh

    from . import consistency
    from .occt import OCCT

    try:
        with OCCT:
            s0, s1 = _exact(before), _exact(after)
            if s0 is None or s1 is None:
                return UNCOMPARED
            # by each of the other's solids: a build of two touching solids (a tube on a plate) comes as a compound, and
            # cut by the compound whole, all of the plate read as taken
            added, taken = s1.cut(*s0.Solids()), s0.cut(*s1.Solids())
            change = [(added if added.Volume() > CHANGE_MM3 else None, False),
                      (taken if taken.Volume() > CHANGE_MM3 else None, True)]
            change = [(_meshed(sh) if sh is not None else None, gone) for sh, gone in change]
        if all(m is None for m, _ in change):
            return None
        shapes = [sh for sh in consistency.shapes(before["declared"]) if sh["name"] != piece]
        prisms = _prisms(shapes, before["mesh"]) if before.get("mesh") is not None else None
        if prisms is None:
            return UNCOMPARED
        for solid, gone in change:
            if solid is None:
                continue
            into: dict = {}
            for name, pr in prisms:
                into[name] = into.get(name, 0.0) + _vol(trimesh.boolean.intersection([solid, pr], engine="manifold"))
            name, most = max(into.items(), key=lambda kv: kv[1], default=(None, 0.0))
            if most > CHANGE_MM3:
                return f"changes the {name}"
            if not gone:                          # what was taken outside every other piece is the piece itself
                return "adds to the part where nothing is declared"
    except Exception:  # noqa: BLE001 — a boolean, a mesh or a piece it can't read: not compared, so never the switch
        return UNCOMPARED
    return None


#: What :func:`off_switch` found, by the script's text and the piece: a version builds its few tries once (Things to fix asks
#: on every open).
_FOUND: dict = {}


def _key(store: DesignStore, pid: str, piece: str) -> tuple:
    import hashlib

    return hashlib.sha1(store.read_script(pid).encode()).hexdigest(), piece


def _found(store: DesignStore, pid: str, piece: str) -> tuple:
    key = _key(store, pid, piece)
    if key not in _FOUND:
        if len(_FOUND) > 256:
            _FOUND.clear()
        _FOUND[key] = _off_switch(store, pid, piece, store.read_script(pid))
    return _FOUND[key]


def known(store: DesignStore, pid: str, piece: str) -> Optional[tuple]:
    """What :func:`off_switch` found for this version, ``(switch, why)``, or None where it hasn't been built yet: never a
    build (#332 review: the menu and Things to fix don't wait on one)."""
    return _FOUND.get(_key(store, pid, piece))


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
    "checked"?, "said", "designer_call"}``. Never a build (#332 review): what the Delete click found, where it has been
    clicked for this version; else the number its name points to, said as built first to be sure (``checked`` False)."""
    from .tree import pieces

    row = next((p for p in pieces(store, pid) if p["key"] == piece), None)
    if row is None:
        raise KeyError(f"{pid} has no piece {piece!r}")
    name = row["name"]
    them = "them" if _many(name) else "it"
    found = known(store, pid, piece)
    if found is None:
        tries = [e["name"] for e in named(store, pid, piece)[:TRIES]]
        if tries:                                 # by name only: which, if any, is the switch is the click's to build
            each = "It's" if len(tries) == 1 else "Each is"
            return {"piece": piece, "name": name, "how": "number", "params": tries, "checked": False,
                    "designer_call": False,
                    "said": f"Delete the {name}: {' or '.join(tries)} at 0 may turn {them} off. {each} built first to be "
                            f"sure (a few seconds, no Claude); where none only does that, it's the designer's instead. A "
                            f"new version of {pid}, rolled back as any other."}
        found = (None, None)
    sw, why = found
    if sw is not None:
        return {"piece": piece, "name": name, "how": "number", **sw, "checked": True, "designer_call": False,
                "said": f"Delete the {name}: {sw['param']} to 0 turns {them} off. A number change, at once (no Claude): "
                        f"a new version of {pid}, rolled back as any other."}
    return _designer(piece, name, pid, why)


def _designer(piece: str, name: str, pid: str, why: Optional[str]) -> dict:
    lead = f"{why}, so it" if why else f"that changes {pid}'s code, so it"      # a number that would, but does more: said
    return {"piece": piece, "name": name, "how": "designer", "designer_call": True, **({"why": why} if why else {}),
            "said": f"Delete the {name}: {lead} asks the designer (one Claude call, about a minute). A new version of "
                    f"{pid}, rolled back as any other."}


def _many(name: str) -> bool:
    return name.rstrip().endswith("s")


def delete(store: DesignStore, pid: str, piece: str) -> dict:
    """The Delete click: its number built at 0 to be sure, then set (``{"version", "how": "number", "said"}``, the reply
    naming what went); or, where no number only turns it off, the designer's plan with why, nothing set (the page asks
    again before the designer's revise)."""
    from . import params

    p = plan(store, pid, piece)
    if p["how"] == "number" and not p["checked"]:
        off_switch(store, pid, piece)             # the builds: here, on the click
        p = plan(store, pid, piece)
    if p["how"] != "number":
        return p
    got = params.set_values(store, pid, [{"name": p["param"], "value": 0, "unit": p["unit"]}])
    return {"version": got["version"], "how": "number",
            "said": f"Deleted the {p['name']} from {pid}: {p['param']} to 0 (v{got['version']}). Roll it back to put "
                    f"{'them' if _many(p['name']) else 'it'} back."}
