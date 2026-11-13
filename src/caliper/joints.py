"""CALI-156 (#222) slice A — Caliper reads how a part's pieces join.

Pieces are unioned into one body, so the strength check takes every joint as solid wood (Theo, on step-stool-3: "the sides
are joined to the top in such a way though that the stool will never hold"). Slice A makes a joint a thing Caliper reads
and says, with no capacity numbers yet (slice B):

- **``JOINTS``**, a module-level list in the part's script, data like ``HOLES``, read from the script's text and never run
  (:func:`read`). Each entry names two pieces and a kind, and what holds it::

      JOINTS = [{"pieces": ["top", "side front"], "kind": "bevel", "fix": ["glue", "screws"]}]

- **Checked** (:func:`check`, in each authoring round): each entry's pieces exist and touch, its kind and fix are ones
  Caliper knows; and a piece that runs through another's outline (a through tenon: step-stool-5's stringer "through the
  left and right side") has the mortise cut into that outline, or the cut list would have him cut whole sides.
- **Every contact is a joint** (:func:`contacts`): where an edge meets a face (as ``fasteners.joints`` finds them), and where
  a piece runs through or is set into another, which edge probes never see (#272's review: the through-mortised stringer
  had no glue or screws on the shopping list). A contact with no entry is listed as an assumed butt (or through tenon),
  glue and screws (:func:`listed`).
"""

from __future__ import annotations

import ast
from typing import Optional

import numpy as np

NAME = "JOINTS"
#: The kinds a joint can be (#222's proposal, and the through tenon from step-stool-5).
KINDS = ("butt", "bevel", "mitre", "rabbet", "dado", "pocket screw", "dowel", "glue block", "printed connector",
         "through tenon")
#: What can hold one.
FIXES = ("glue", "screws", "dowels")
#: What an unlisted contact is taken as held by.
ASSUMED_FIX = ["glue", "screws"]


def read(script: str) -> list:
    """The ``JOINTS`` a script carries, from its text, never run: [] where it has none, or isn't plain data."""
    try:
        tree = ast.parse(script or "")
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) == NAME:
            try:
                got = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                return []
            return [j for j in got if isinstance(j, dict)] if isinstance(got, list) else []
    return []


def _said(name: str) -> str:
    return "the " + name


def _through(host: dict, piece: dict, tol: float) -> Optional[dict]:
    """Where sheet ``piece`` runs through or into sheet ``host``: its mid-plane sampled finely, kept inside the host's outline
    and within its thickness, reaching into the host (some of it more than the piece's thickness in from the host's edge: a
    stringer's end flush in a side runs into the side, not the side into the stringer; a dado running out at the side's
    edges is still in the side). ``{"through": runs the whole thickness, "points": those (u, v) in the host's frame, "frame"}``,
    or None where it doesn't."""
    from .consistency import _edge_dist2d, _frame, _inside2d, polygon_samples

    if len(host["polys"]) != 1 or len(piece["polys"]) != 1:
        return None
    o, u, v, n, flat = _frame(host["polys"][0])
    n = n * host["sides"][0]
    t = float(host["thickness"])
    pp = piece["polys"][0]
    _, _, _, pn, _ = _frame(pp)
    if abs(float(pn @ n)) > 0.95:                    # in the host's own plane, or parallel: no crossing
        return None
    mid = polygon_samples(pp, n=96) + pn * piece["sides"][0] * float(piece["thickness"]) / 2.0
    rel = mid - o
    q, w = np.stack([rel @ u, rel @ v], axis=1), rel @ n
    inside = _inside2d(q, flat) & (w > tol) & (w < t - tol)
    if not inside.any():
        return None
    if float(_edge_dist2d(q[inside], flat).max()) < float(piece["thickness"]):
        return None                                  # all of it at the host's own edge: an edge on a face, not a mortise
    near = _inside2d(q, flat) & (w > -tol) & (w < t + tol)
    span = (float(w[near].min()), float(w[near].max()))
    return {"through": span[0] <= tol and span[1] >= t - tol, "points": q[inside], "frame": (o, u, v, n)}


def contacts(pieces: list[dict], tol: float) -> dict:
    """``{(a, b): {"how": "edge" | "through" | "into", "length_mm"}}``, keyed by the pieces' keys, sorted: every pair of wood
    pieces that touch. An edge on a face as ``fasteners.joints`` finds it; a sheet run through another (``through``) or
    set into it (``into``, a dado or rabbet) from the pieces' own planes."""
    from . import fasteners

    out = {k: {"how": "edge", "length_mm": mm} for k, mm in fasteners.edge_joints(pieces, tol).items()}
    wood = [pc for pc in pieces if pc.get("material") in fasteners.WOOD and pc["kind"] == "sheet"]
    for host in wood:
        for piece in wood:
            if piece is host:
                continue
            got = _through(host, piece, tol)
            if got is None:
                continue
            key = tuple(sorted((host["key"], piece["key"])))
            across = float(np.ptp(got["points"], axis=0).max()) if len(got["points"]) > 1 else 0.0
            out[key] = {"how": "through" if got["through"] else "into", "length_mm": 2.0 * across}
    return out


def _host_mortises(pieces: list[dict], tol: float) -> list[str]:
    """Each through tenon whose host's outline has no hole where it goes, said."""
    from .consistency import _inside2d

    wrong = []
    wood = [pc for pc in pieces if pc["kind"] == "sheet"]
    for host in wood:
        for piece in wood:
            if piece is host:
                continue
            got = _through(host, piece, tol)
            if got is None or not got["through"]:
                continue
            o, u, v, _ = got["frame"]
            holes = [np.stack([(np.asarray(h, float) - o) @ u, (np.asarray(h, float) - o) @ v], axis=1)
                     for h in host.get("holes") or []]
            pts = got["points"]
            covered = np.zeros(len(pts), dtype=bool)
            for h in holes:
                covered |= _inside2d(pts, h)
            if covered.mean() < 0.9:
                wrong.append(f"{_said(piece['name'])} passes through {_said(host['name'])}, but {_said(host['name'])}'s "
                             f"outline has no hole where it goes: cut the mortise into {_said(host['name'])}'s outline")
    return wrong


def check(script: str, declared: Optional[dict], mesh) -> list:
    """The round's checks of a part's joints: ``joints`` (each entry's pieces exist and touch, its kind and fix known) and
    ``mortises`` (a piece through another's outline has its mortise there). [] where the part declares no pieces."""
    from .consistency import _sides, shapes, tolerance
    from .evaluate import AssertionResult

    if not declared or declared.get("error") or mesh is None:
        return []
    try:
        pieces = shapes(declared)
    except (ValueError, KeyError, TypeError):
        return []                                      # construction_reads says it
    sheets = [pc for pc in pieces if pc["kind"] == "sheet"]
    if len(pieces) < 2:
        return []
    _sides(mesh, sheets)
    tol = tolerance(mesh)
    from . import fasteners

    fasteners.keys(pieces)
    names = {pc.get("name") for pc in pieces}
    touching = {frozenset(k) for k in contacts(pieces, tol)}
    wrong = []
    for j in read(script):
        two = [p for p in j.get("pieces") or [] if isinstance(p, str)]
        missing = [p for p in two if p not in names]
        for p in missing:
            wrong.append(f"{NAME} names {_said(p)}, which isn't one of its pieces")
        if len(two) != 2:
            wrong.append(f"{NAME} has an entry that doesn't name two pieces: {j.get('pieces')!r}")
            continue
        if not missing and frozenset(two) not in touching:
            wrong.append(f"{NAME} joins {_said(two[0])} and {_said(two[1])}, which don't touch")
        kind, fix = j.get("kind"), [f for f in j.get("fix") or [] if f not in FIXES]
        if kind not in KINDS or fix:
            said = []
            if kind not in KINDS:
                said.append(f"the kind \"{kind}\", which isn't one of {', '.join(KINDS)}")
            if fix:
                said.append(f"the fix \"{', '.join(fix)}\", which isn't glue, screws or dowels")
            wrong.append(f"{NAME} gives {_said(two[0])} and {_said(two[1])} " + ", and ".join(said))
    out = [AssertionResult(id="joints", expr=f"its {NAME} name pieces that touch, with a kind and fix Caliper knows",
                           status="fail" if wrong else "pass", passed=not wrong, actual=len(wrong), detail="; ".join(wrong))]
    mort = _host_mortises(sheets, tol)
    out.append(AssertionResult(id="mortises", expr="a piece through another's outline has its mortise cut there",
                               status="fail" if mort else "pass", passed=not mort, actual=len(mort), detail="; ".join(mort)))
    return out


def listed(store, pid: str) -> list[dict]:
    """A part's joints, as Built-from and the book list them: its ``JOINTS`` entries, then every other contact as an assumed
    butt (or through tenon), glue and screws. ``[{"pieces": [a, b], "kind", "fix", "assumed"}]``, pieces sorted."""
    from . import construction as C
    from . import fasteners
    from .consistency import _sides, shapes, tolerance

    script = store.read_script(pid)
    try:
        mesh = store.part_geometry(pid).require_mesh()
        pieces = shapes(C.declared(store, pid))
    except Exception:  # noqa: BLE001 — no pieces to join: none listed
        return []
    _sides(mesh, [pc for pc in pieces if pc["kind"] == "sheet"])
    fasteners.keys(pieces)
    found = contacts(pieces, tolerance(mesh))
    out, said = [], set()
    for j in read(script):
        two = sorted(p for p in j.get("pieces") or [] if isinstance(p, str))
        if len(two) == 2 and tuple(two) in found:
            out.append({"pieces": two, "kind": j.get("kind"), "fix": list(j.get("fix") or []), "assumed": False})
            said.add(tuple(two))
    for key, c in sorted(found.items()):
        if key not in said:
            out.append({"pieces": list(key), "kind": "through tenon" if c["how"] == "through" else "butt",
                        "fix": list(ASSUMED_FIX), "assumed": True})
    return out
