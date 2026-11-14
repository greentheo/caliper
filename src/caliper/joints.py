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

from .fasteners import WOOD

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


def contacts(pieces: list[dict], tol: float, reach: Optional[float] = None, at: Optional[dict] = None,
             materials: Optional[tuple] = WOOD) -> dict:
    """``{(a, b): {"how": "edge" | "through" | "into" | "notch" | "face", "length_mm", "on": {key: [(u, v), ...]}}}``, keyed by
    the pieces' keys, sorted: every pair of wood pieces that touch. An edge on a face as ``fasteners.joints`` finds it; a sheet
    run through another (``through``) or set into it (``into``, a dado or rabbet) from the pieces' own planes; and a piece lying
    on a sheet's face (``face``: a cleat, a doubled panel), which edge probes never see (#280: Lighten's rim kept wood under
    them, and the rim reads this finder now). ``on``: where on each sheet the other one meets it, its own (u, v), probed just
    past each face within ``reach`` (the tolerance by default), at ``at[sheet key]``'s (u, v) points where given (Lighten's
    cells), else a grid over its face: one finder for the joint list, the shopping list and Lighten's rim, which passes its
    own reach (#275 review). A pair is a joint by ``tol`` alone, whatever the reach. ``materials``: the pieces it looks
    between, wood for the joint list and the shopping list (glue and screws); None, every piece, for Lighten's rim, which
    keeps whatever meets a panel, a steel tube or a foam side (#281 review)."""
    from . import fasteners

    def ours(pc):
        return materials is None or pc.get("material") in materials

    out = {k: {"how": "edge", "length_mm": mm} for k, mm in fasteners.edge_joints(pieces, tol).items()}
    wood = [pc for pc in pieces if ours(pc) and pc["kind"] == "sheet"]
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
    sticks = [pc for pc in pieces if ours(pc) and pc["kind"] != "sheet" and pc.get("a") is not None]
    _footprints(wood, wood + sticks, out, tol, tol if reach is None else reach, at or {})
    return out


def _footprints(sheets: list[dict], others: list[dict], found: dict, tol: float, reach: float, at: dict) -> None:
    """Where on each sheet each piece it touches meets it: its face sampled (or ``at`` its key's (u, v) points), probed just
    past each face, kept within ``reach`` of the other piece, a sheet or a stick. Into ``found[key]["on"][sheet key]`` as (u, v)
    points in that sheet's frame. A pair no other probe found, within ``tol`` of a face, is a ``face`` contact."""
    from .consistency import _frame, polygon_samples, segment_distance, slab_distance

    for a in sheets:
        if len(a["polys"]) != 1:
            continue
        o, u, v, n, _ = _frame(a["polys"][0])
        n = n * a["sides"][0]
        if a["key"] in at:
            uv = np.asarray(at[a["key"]], float).reshape(-1, 2)
            face = o + uv[:, :1] * u + uv[:, 1:] * v
        else:
            face = polygon_samples(a["polys"][0], n=64)
            uv = np.stack([(face - o) @ u, (face - o) @ v], axis=1)
        probes = [face - n * tol, face + n * (float(a["thickness"]) + tol)]      # just past each face, as Lighten's rim did
        for b in others:
            if b is a:
                continue
            key = tuple(sorted((a["key"], b["key"])))
            d = np.full(len(face), np.inf)
            for pr in probes:
                if b["kind"] == "sheet":
                    d = np.minimum(d, np.min([slab_distance(pr, op, b["thickness"], sd)
                                              for op, sd in zip(b["polys"], b["sides"])], axis=0))
                else:
                    d = np.minimum(d, segment_distance(pr, b["a"], b["b"]) - b.get("half", 0.0))
            hit = d <= reach
            if key not in found:
                if not (d <= tol).any():
                    continue
                touch = uv[d <= tol]
                found[key] = {"how": "face", "on": {},
                              "length_mm": float(np.ptp(touch, axis=0).max()) if len(touch) > 1 else 0.0}
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
    from . import shop as shop_

    have = shop_.read()
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
        elif shop_.joint_needs(kind, have) is not None:      # the shop decides what's possible (CALI-178, #222 §3)
            wrong.append(f"{NAME} makes {_said(two[0])} and {_said(two[1])} a {kind}, which needs "
                         f"{shop_.joint_needs(kind, have)}, and your shop hasn't got one: choose a joint it can make, or say "
                         f"what it needs")
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


# ---------------------------------------------------------------------------------------------------------------------------
# A pick names a joint (CALI-178, #222 slice D)
# ---------------------------------------------------------------------------------------------------------------------------
#: The kinds a joint check can measure in the pieces: a rabbet's or a dado's step (#285 review); a bevel's angle, and a
#: through tenon's mortise or a notch, from the make side's marks (#283, CALI-180). Any other is said as the entry only,
#: never "Checked".
MEASURED = ("rabbet", "dado", "bevel", "through tenon", "notch")
#: The cut a joint kind makes in its host, as :func:`marks.cuts` says it, and how that cut is told from the other.
_CUT = {"through tenon": "mortise", "notch": "notch"}
_CUT_IS = {"mortise": "closed all round", "notch": "open at its edge"}
#: What a joint check says when it can't tell: landed and missed each need positive evidence, as for an edge (#177).
NOT_MEASURED = "I couldn't tell whether that joint changed the way you asked."
UNDO = ' Say "roll it back" to undo it.'
#: The kinds a request can ask for, and the words it might use: the longer phrases first.
_ASK = (("pocket screw", r"pocket[- ]?(?:screw|hole)s?"), ("glue block", r"glue[- ]?blocks?"),
        ("printed connector", r"printed connectors?"), ("through tenon", r"(?:through[- ])?tenons?|mortise(?:s|d)?(?:[- ]and[- ]tenons?)?"),
        ("mitre", r"mit(?:re|er)(?:ed|s)?"), ("rabbet", r"rabbet(?:ed|s)?|rebate(?:d|s)?"), ("dado", r"dado(?:e?s)?"),
        ("dowel", r"dowel(?:s|led|ed)?"), ("bevel", r"bevel(?:led|ed|s)?"), ("notch", r"notch(?:ed|es)?"),
        ("butt", r"butt(?:[- ]joint)?s?"))


def _pieces_of(store, pid: str):
    """A part's pieces with their sides and keys, and its tolerance; ``([], 0)`` where it has none to read."""
    from . import construction as C
    from . import fasteners
    from .consistency import _sides, shapes, tolerance

    try:
        mesh = store.part_geometry(pid).require_mesh()
        pieces = shapes(C.declared(store, pid))
    except Exception:  # noqa: BLE001 — no pieces: no joints to name
        return [], 0.0
    _sides(mesh, [pc for pc in pieces if pc["kind"] == "sheet"])
    fasteners.keys(pieces)
    return pieces, tolerance(mesh)


def _distance(pc: dict, P: np.ndarray) -> float:
    from .consistency import segment_distance, slab_distance

    if pc["kind"] == "sheet":
        return float(min(slab_distance(P, poly, pc["thickness"], side).min() for poly, side in zip(pc["polys"], pc["sides"])))
    if pc.get("a") is not None:
        return float((segment_distance(P, pc["a"], pc["b"]) - pc.get("half", 0.0)).min())
    return float("inf")


def namer(store, pid: str):
    """``name(point)``: the joint a point in the script's frame lies on, ``{"pieces", "said", "kind"}``, or None. A point is
    on a joint where it's on both pieces' surfaces (within twice the tolerance) and they touch; a corner where three meet is
    no one joint, so None."""
    pieces, tol = _pieces_of(store, pid)
    if not pieces:
        return lambda point: None
    found = contacts(pieces, tol)
    by = {pc["key"]: pc for pc in pieces}
    try:
        kinds = {tuple(j["pieces"]): j["kind"] for j in listed(store, pid)}
    except Exception:  # noqa: BLE001 — named without its kind
        kinds = {}

    def name(point) -> Optional[dict]:
        P = np.asarray(point, float).reshape(1, 3)
        near = sorted((max(_distance(by[a], P), _distance(by[b], P)), (a, b)) for a, b in found)
        near = [x for x in near if x[0] <= 2.0 * tol]
        if not near or (len(near) > 1 and near[1][0] <= near[0][0] + 0.5):
            return None
        key = near[0][1]
        return {"pieces": list(key), "said": f"the joint between the {key[0]} and the {key[1]}", "kind": kinds.get(key, "butt")}
    return name


def asked_kind(text: str) -> Optional[str]:
    """The kind of joint a request asks for ("make that a rabbet"), or None."""
    import re

    for kind, rx in _ASK:
        if re.search(rf"\b(?:{rx})\b", text or "", re.I):
            return kind
    return None


def focus(joint: dict, kind: str, at) -> str:
    """What the designer is told when a request is about a picked joint (#222 §3): which entry, what kind, where."""
    a, b = joint["pieces"]
    at = tuple(round(float(v), 2) for v in at)
    return (f"The picked edge is {joint['said']}. Make that joint a {kind}: set its JOINTS entry, pieces [\"{a}\", \"{b}\"], "
            f"to \"kind\": \"{kind}\" with \"at\": {at}, keeping its \"fix\" (add the entry if it has none). Build it that way "
            f"in build() and construction() too: for a rabbet or a dado, cut the step into the piece whose face the other's "
            f"edge meets, and run the other piece into it by the step's depth.")


def sunk(a: dict, b: dict) -> float:
    """How far one sheet's edge runs into the other's thickness at their joint (mm): a rabbet's or a dado's step, as the
    pieces are declared; 0 for an edge that stops at the face."""
    from .consistency import _frame, _inside2d

    best = 0.0
    for edge, host in ((a, b), (b, a)):
        if host["kind"] != "sheet" or edge["kind"] != "sheet" or len(host["polys"]) != 1:
            continue
        o, u, v, n, flat = _frame(host["polys"][0])
        N, t = n * host["sides"][0], float(host["thickness"])
        for poly, side in zip(edge["polys"], edge["sides"]):
            Ne = _frame(poly)[3] * side
            mid = poly + Ne * float(edge["thickness"]) / 2.0             # its corners at mid-thickness
            rel = mid - o
            q, w = np.stack([rel @ u, rel @ v], axis=1), rel @ N
            keep = _inside2d(q, flat) & (w > 0.0) & (w < t)
            if keep.any():
                best = max(best, float(np.minimum(w[keep], t - w[keep]).max()))
    return best


def landed(before_script: str, after_script: str, store, pid: str, joint: dict, kind: str, inches: bool) -> dict:
    """Did "make that a rabbet" land on the picked joint? ``{"said", "landed": True, False or None}``, as
    :func:`features.landed` says it (#177): landed, its entry now has that kind, the pieces still touch, and the pieces show
    it (a rabbet's or dado's step, a bevel's angle on an edge that meets the other piece, a through tenon's mortise or a
    notch); missed, they don't, or its entry is unchanged, gone or another kind; couldn't tell, a kind not measured here."""
    key = tuple(joint["pieces"])

    def entry(script):
        return next((j.get("kind") for j in read(script)
                     if tuple(sorted(p for p in j.get("pieces") or [] if isinstance(p, str))) == key), None)

    was, now = entry(before_script), entry(after_script)
    said = joint["said"]
    if now == kind:
        if kind not in MEASURED:                     # "Checked" only for what's measured (#285 review, rule 6)
            return {"said": f"Its JOINTS entry now says {kind}: the shape isn't checked here.", "landed": None}
        pieces, tol = _pieces_of(store, pid)
        if not pieces:
            return {"said": NOT_MEASURED, "landed": None}
        if key not in contacts(pieces, tol):
            return {"said": f"Its JOINTS entry says {kind}, but the {key[0]} and the {key[1]} don't touch now." + UNDO,
                    "landed": False}
        by = {pc["key"]: pc for pc in pieces}
        if any(by[k]["kind"] != "sheet" or len(by[k].get("polys") or []) != 1 for k in key):
            # a stick's ends and cuts aren't read here: couldn't tell, never an error (#289 review)
            return {"said": f"Its JOINTS entry now says {kind}: a stick's cut isn't checked here.", "landed": None}
        if kind not in ("rabbet", "dado"):
            return _marked(store, pid, key, by, kind, said, inches, tol)
        depth = sunk(by[key[0]], by[key[1]])
        if depth <= tol:                             # the step asked for isn't in the pieces: a miss (#285 review)
            return {"said": f"Its JOINTS entry says {kind}, but the pieces show no step: neither runs into the other."
                            + UNDO, "landed": False}
        from .release import inches as _in

        deep = _in(depth) if inches else f"{depth:.0f} mm"
        return {"said": f"Checked: {said} is now a {kind}, {deep} deep.", "landed": True}
    if now == was:
        before = was or f"{joint.get('kind') or 'butt'} (assumed)"
        return {"said": f"{said[0].upper()}{said[1:]} is still a {before}: its JOINTS entry didn't change." + UNDO,
                "landed": False}
    if now is None:
        return {"said": f"Its JOINTS entry is gone, not a {kind}." + UNDO, "landed": False}
    return {"said": f"Its JOINTS entry now says {now}, not {kind}." + UNDO, "landed": False}   # another kind: a miss


def _marked(store, pid: str, key: tuple, by: dict, kind: str, said: str, inches: bool, tol: float) -> dict:
    """A bevel, checked against the make side's marks (CALI-180): the same bevels the patterns, the cut list and the book
    are drawn from. A through tenon or notch, from the declared pieces: landed only where the host's outline has it, as
    the router cuts it; the solid alone is partial, and says what's missing (#289 review)."""
    from . import marks as K
    from .release import inches as _in

    a, b = key
    if kind == "bevel":
        m = K.of(store, pid)                              # an edge of one cut at an angle to sit on the other
        cut = [(float(x["angle"]), k) for k, o in ((a, b), (b, a)) for x in (m["bevels"].get(k) or []) if x.get("meets") == o]
        if not cut:
            return {"said": f"Its JOINTS entry says bevel, but neither edge is cut at an angle where the {a} and the {b} "
                            f"meet." + UNDO, "landed": False}
        angle, k = max(cut)
        return {"said": f"Checked: {said} is now a bevel, {angle:.0f}° on the {k}'s edge.", "landed": True}
    want = _CUT[kind]
    found = [(cut[0], host, other, cut) for host, other in ((a, b), (b, a)) for cut in [_cut_in(by[host], by[other], tol)]
             if cut is not None]
    hit = next((f for f in found if f[0] == want), None)
    corner = next((f for f in found if f[0] == "corner"), None)
    if hit is None and corner is not None:
        _, host, other, _ = corner
        return {"said": f"Its JOINTS entry says {kind}, but the {other} rests in a corner of the {host}'s outline: it "
                        f"isn't cut round on both sides, so there's no {want}." + UNDO, "landed": False}
    if hit is None:
        if found:
            got, host, other, _ = found[0]
            return {"said": f"Its JOINTS entry says {kind}, but the {host} has a {got} for the {other}, {_CUT_IS[got]}, "
                            f"not a {want}." + UNDO, "landed": False}
        return {"said": f"Its JOINTS entry says {kind}, but neither piece runs through the other: there's no {want}."
                        + UNDO, "landed": False}
    _, host, other, (_, got, cut) = hit
    if not cut:                                      # the solid has it; the outline the router cuts doesn't (#289 review)
        from .features import PARTIAL

        where, what = (f"through the {host}", "hole") if want == "mortise" else (f"in the {host}'s edge", "notch")
        return {"said": f"The solid has the {other} {where}, but the {host}'s outline has no {what} there yet: cut the "
                        f"{want} into the {host}'s outline." + UNDO, "landed": PARTIAL}
    C = np.asarray(K._footprint(by[host], by[other], got), float)
    lo, hi = sorted((float(np.linalg.norm(C[1] - C[0])), float(np.linalg.norm(C[3] - C[0]))))
    size = f"{_in(lo)} x {_in(hi)}" if inches else f"{lo:.0f} x {hi:.0f} mm"
    return {"said": f"Checked: {said} is now a {kind}: a {size} {want} in the {host}.", "landed": True}


def _hull(host: dict) -> Optional[dict]:
    """The host with its outline's convex hull for an outline: where a notch cut into the outline was (#289 review). None
    where the outline is already convex."""
    from .consistency import _frame

    o, u, v, _, flat = _frame(host["polys"][0])
    pts = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in flat})
    if len(pts) < 3:
        return None

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    hull = half(pts)[:-1] + half(pts[::-1])[:-1]          # counter-clockwise, as an outline is in its own frame
    if len(hull) == len(pts):
        return None
    return {**host, "polys": [np.array([o + x * u + y * v for x, y in hull])]}


def _cut_in(host: dict, piece: dict, tol: float) -> Optional[tuple]:
    """``(kind, crossing, in the outline)``: a mortise or notch ``piece`` makes in ``host``, from the declared pieces, and
    whether the host's outline has it, as #275's rule reads it: a mortise as a hole, a notch cut into the outline
    itself. None where the piece doesn't run right through the host (#289 review)."""
    from .consistency import _inside2d

    got = _through(host, piece, tol)
    if got is not None and got["through"]:
        o, u, v, _ = got["frame"]
        covered = np.zeros(len(got["points"]), dtype=bool)
        for h in host.get("holes") or []:
            h = np.asarray(h, float)
            covered |= _inside2d(got["points"], np.stack([(h - o) @ u, (h - o) @ v], axis=1))
        return ("notch" if got["notch"] else "mortise"), got, bool(covered.mean() >= 0.9)
    if got is None and len(host["polys"]) == 1:      # outside the outline: cut into it, if it's inside its hull
        hull = _hull(host)
        got = _through(hull, piece, tol) if hull is not None else None
        if got is not None and got["through"]:
            if not _flanked(host, piece, got):       # an open corner it rests in: no pocket (#289 review)
                return "corner", got, False
            return ("notch" if got["notch"] else "mortise"), got, True
    return None


def _flanked(host: dict, piece: dict, got: dict) -> bool:
    """Whether the host's outline flanks a crossing on both sides, just past the piece's own thickness: a pocket cut round
    it (a notch), not a concave corner it rests in, as a tread on a stair-cut side does (#289 review)."""
    from .consistency import _frame, _inside2d

    o, u, v, _ = got["frame"]
    poly = np.asarray(host["polys"][0], float)
    flat = np.stack([(poly - o) @ u, (poly - o) @ v], axis=1)
    pts = got["points"]
    if len(pts) < 2:
        return False
    c = pts - pts.mean(axis=0)
    ax = np.linalg.svd(c, full_matrices=False)[2][0]
    e2 = np.array([-ax[1], ax[0]])                   # across the piece, in the host's face
    across = abs(float((e2[0] * u + e2[1] * v) @ _frame(piece["polys"][0])[3])) or 1e-3
    t = float(piece["thickness"])
    reach = t / across / 2.0 + max(2.0, 0.25 * t)
    both = _inside2d(pts + e2 * reach, flat) & _inside2d(pts - e2 * reach, flat)
    return bool(both.mean() >= 0.5)


def beside(store, pid: str, point, corner: Optional[str] = None) -> Optional[str]:
    """What to say when a joint is asked of an edge that isn't one: an edge on one piece, beside the flush seam where it meets
    another (the seam is no edge in the joined solid, so it can't be picked). None where no joint is near it (#285 review)."""
    pieces, tol = _pieces_of(store, pid)
    if not pieces:
        return None
    P = np.asarray(point, float).reshape(1, 3)
    on = [pc for pc in pieces if _distance(pc, P) <= 2.0 * tol]
    if len(on) != 1:
        return None
    me = on[0]
    near = []
    for a, b in contacts(pieces, tol):
        if me["key"] not in (a, b):
            continue
        other = next(pc for pc in pieces if pc["key"] == (b if a == me["key"] else a))
        reach = 1.5 * max(float(me.get("thickness") or 0.0), float(other.get("thickness") or 0.0)) + 2.0 * tol
        d = _distance(other, P)
        if d <= reach:
            near.append((d, (a, b)))
    if not near:
        return None
    a, b = min(near)[1]
    what = f"the {me['key']}'s {corner} corner" if corner else f"an edge of the {me['key']}"
    return (f"That edge is {what}, not where two pieces meet. The joint between the {a} and the {b} is where they meet "
            f"inside: pick that inside corner, or name the pieces (\"the joint between the {a} and the {b}\").")
