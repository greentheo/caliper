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
- A piece run in from one edge of another is a notch, and the outline needs it cut there (#275 review: a stringer on the
  floor, through the sides' bottom edge); one run from edge to edge cuts it in two, so that one is the tenon.
"""

from __future__ import annotations

import ast
from typing import Optional

import numpy as np

NAME = "JOINTS"
#: The kinds a joint can be (#222's proposal, and the through tenon from step-stool-5).
KINDS = ("butt", "bevel", "mitre", "rabbet", "dado", "pocket screw", "dowel", "glue block", "printed connector",
         "through tenon", "notch")
#: What can hold one.
FIXES = ("glue", "screws", "dowels")
#: What an unlisted contact is taken as held by.
ASSUMED_FIX = ["glue", "screws"]


#: What :func:`readable` says of a ``JOINTS`` that isn't plain data: the round fails on it, never drops it (#275 review).
UNREAD = f"{NAME} isn't plain data: write it as a list of dicts"


def readable(script: str) -> tuple[bool, list]:
    """``(ok, joints)``: the ``JOINTS`` a script carries, from its text, never run (``JOINTS = [...]`` or annotated,
    ``JOINTS: list = [...]``). ``(True, [])`` where it has none; ``(False, [])`` where it has one that isn't plain data (a
    comprehension, a loop's appends): said, never dropped."""
    try:
        tree = ast.parse(script or "")
    except SyntaxError:
        return True, []
    value, built = None, False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == NAME for t in node.targets):
            value = node.value if value is None else value
        elif isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == NAME and node.value is not None:
            value = node.value if value is None else value
        elif isinstance(node, ast.AugAssign) and getattr(node.target, "id", None) == NAME:
            built = True                              # JOINTS += [...]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and getattr(node.func.value, "id", None) == NAME):
            built = True                              # JOINTS.append(...), .extend(...)
    if built:
        return False, []
    if value is None:
        return True, []
    try:
        got = ast.literal_eval(value)
    except (ValueError, SyntaxError, TypeError):
        return False, []
    return (True, [j for j in got if isinstance(j, dict)]) if isinstance(got, list) else (False, [])


def read(script: str) -> list:
    """The ``JOINTS`` a script carries, as plain data; [] where it has none or can't be read (:func:`readable` says which)."""
    return readable(script)[1]


def _said(name: str) -> str:
    return "the " + name


def _ends_at_edges(pts: np.ndarray, flat: np.ndarray, near: float) -> int:
    """How many of a crossing's two ends, along its length, come within ``near`` of the host's edge: 2, it runs edge to edge
    and would cut the host in two; 1, it runs in from one edge (a notch); 0, it's inside (a mortise)."""
    from .consistency import _edge_dist2d

    if len(pts) < 2:
        return 0
    c = pts - pts.mean(axis=0)
    along = c @ np.linalg.svd(c, full_matrices=False)[2][0]
    lo, hi = float(along.min()), float(along.max())
    band = max(near, 0.02 * (hi - lo))
    return sum(bool(float(_edge_dist2d(pts[end], flat).min()) <= near) for end in (along <= lo + band, along >= hi - band))


def _through(host: dict, piece: dict, tol: float) -> Optional[dict]:
    """Where sheet ``piece`` runs through or into sheet ``host``: its mid-plane sampled finely, kept inside the host's outline
    and within its thickness, reaching into the host (some of it more than the piece's thickness in from the host's edge: a
    stringer's end flush in a side runs into the side, not the side into the stringer; a dado running out at the side's
    edges is still in the side). ``{"through": runs the whole thickness, "notch": it runs in from one of the host's edges,
    "points": those (u, v) in the host's frame, "frame", "span": how deep into the host's thickness it reaches, from the face
    its outline gives}``, or None where it doesn't, or where it runs through from one edge
    to the opposite one: then the host is the tenon (a side through a proud stringer), not the mortise."""
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
    through = span[0] <= tol and span[1] >= t - tol
    ends = _ends_at_edges(q[inside], flat, 2.0 * tol) if through else 0
    if ends == 2:
        return None                                  # edge to edge: the host is the tenon, not the mortise (#275)
    return {"through": through, "notch": ends == 1, "points": q[inside], "frame": (o, u, v, n), "span": span}


def contacts(pieces: list[dict], tol: float, reach: Optional[float] = None) -> dict:
    """``{(a, b): {"how": "edge" | "through" | "into", "length_mm", "on": {key: [(u, v), ...]}}}``, keyed by the pieces' keys,
    sorted: every pair of wood pieces that touch. An edge on a face as ``fasteners.joints`` finds it; a sheet run through
    another (``through``) or set into it (``into``, a dado or rabbet) from the pieces' own planes. ``on``: where on each
    sheet the other one meets it, its own (u, v), probed just past each face within ``reach`` (the tolerance by default):
    one finder for the joint list, the shopping list and Lighten's rim, which passes its own reach (#275 review)."""
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
            how = "notch" if got["notch"] else "through" if got["through"] else "into"
            out[key] = {"how": how, "length_mm": 2.0 * across}
    for key, c in out.items():
        c["on"] = {}
    _footprints(wood, out, tol if reach is None else reach)
    return out


def _footprints(sheets: list[dict], found: dict, reach: float) -> None:
    """Where on each sheet each piece it touches meets it: its face sampled, probed just past each face, kept within ``reach``
    of the other piece. Into ``found[key]["on"][sheet key]`` as (u, v) points in that sheet's frame."""
    from .consistency import _frame, polygon_samples, slab_distance

    for a in sheets:
        if len(a["polys"]) != 1:
            continue
        o, u, v, n, _ = _frame(a["polys"][0])
        n = n * a["sides"][0]
        face = polygon_samples(a["polys"][0], n=64)
        uv = np.stack([(face - o) @ u, (face - o) @ v], axis=1)
        probes = [face - n * reach, face + n * (float(a["thickness"]) + reach)]
        for b in sheets:
            if b is a:
                continue
            key = tuple(sorted((a["key"], b["key"])))
            if key not in found:
                continue
            hit = np.zeros(len(face), dtype=bool)
            for pr in probes:
                hit |= np.min([slab_distance(pr, op, b["thickness"], sd) for op, sd in zip(b["polys"], b["sides"])], axis=0) <= reach
            if hit.any():
                found[key]["on"][a["key"]] = [tuple(map(float, p)) for p in uv[hit]]


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
            if covered.mean() < 0.9 and got["notch"]:      # at the host's edge: its outline, not a hole (#275 review)
                wrong.append(f"{_said(piece['name'])} passes through {_said(host['name'])} at its edge, but "
                             f"{_said(host['name'])}'s outline has no notch there: cut a notch in {_said(host['name'])}'s "
                             f"outline where {_said(piece['name'])} sits")
            elif covered.mean() < 0.9:
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
    ok, said_joints = readable(script)
    wrong = [] if ok else [UNREAD]
    for j in said_joints:
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


def wooden(script: str) -> bool:
    """Whether a part's script declares more than one wood piece, from its text (cheap, for a run read before its joints were
    counted, #275 review): two sheet or stick pieces of plywood or lumber, or one built in a loop."""
    import re

    kinds = len(re.findall(r"""["']kind["']\s*:\s*["'](?:sheet|stick)["']""", script or ""))
    wood = re.search(r"""["'](?:plywood|lumber)["']""", script or "")
    looped = re.search(r"def construction\(.*?(?:\bfor\b)", script or "", re.S)
    return bool(wood) and (kinds >= 2 or (kinds == 1 and bool(looped)))


def mark_uncounted(store, rec: Optional[dict]) -> Optional[dict]:
    """A strength or Lighten run read before its joints were counted, on a part of wood pieces: ``wood_joints: "uncounted"``,
    so its ✓ still says the joints aren't checked, with no count (#275 review: no bare ✓ on a multi-piece wood part)."""
    if rec and "wood_joints" not in rec and rec.get("part"):
        try:
            if store.design.part(rec["part"]) is not None and store.is_scripted(rec["part"]) and wooden(store.read_script(rec["part"])):
                rec["wood_joints"] = "uncounted"
        except Exception:  # noqa: BLE001 — as it was read
            pass
    return rec


def listed(store, pid: str) -> list[dict]:
    """A part's joints, as Built-from and the book list them: its ``JOINTS`` entries, then every other contact as an assumed
    butt (or through tenon), glue and screws. ``[{"pieces": [a, b], "kind", "fix", "assumed"}]``, pieces sorted."""
    from . import construction as C
    from . import fasteners
    from .consistency import _sides, shapes, tolerance

    script = store.read_script(pid)
    ok, said_joints = readable(script)
    try:
        mesh = store.part_geometry(pid).require_mesh()
        pieces = shapes(C.declared(store, pid))
    except Exception:  # noqa: BLE001 — no pieces to join: none listed
        return []
    _sides(mesh, [pc for pc in pieces if pc["kind"] == "sheet"])
    fasteners.keys(pieces)
    found = contacts(pieces, tolerance(mesh))
    out, said = [], set()
    for j in said_joints:
        two = sorted(p for p in j.get("pieces") or [] if isinstance(p, str))
        if len(two) == 2 and tuple(two) in found:
            out.append({"pieces": two, "kind": j.get("kind"), "fix": list(j.get("fix") or []), "assumed": False})
            said.add(tuple(two))
    for key, c in sorted(found.items()):
        if key not in said:
            glued = c["how"] in ("through", "notch")      # glued in its mortise, as the patterns and the book say (#283 review)
            out.append({"pieces": list(key), "kind": {"through": "through tenon", "into": "dado", "notch": "notch"}.get(c["how"], "butt"),
                        "fix": ["glue"] if glued else list(ASSUMED_FIX), "assumed": True, **({} if ok else {"unread": UNREAD})})
    return out
