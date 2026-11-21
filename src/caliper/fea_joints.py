"""#316 slice 2 (CALI-194): each joint's force and moment, read from a case's FEA, beside the hand rule.

whittle's FEA keeps a solve's nodal displacements. With the solver's own element stiffness (``E h`` times the unit hex's,
times a voxel's own multiple where the part is of two materials), each voxel's nodal forces are ``K u``. Summed over the
nodes one piece's voxels share with another's, they are the force and moment that piece puts across the joint, by
statics.

**What it can and can't say:**
- **The FEA holds the pieces as one.** Its union bonds every joint, so the moment it reads is a fully fixed joint's. A
  screwed joint is semi-rigid and takes less, so the bonded moment errs safe for the joint itself (the foreman, #316).
- **A statics pin, per piece.** The joints into a piece, plus the load the solver put on it, plus the reactions where
  it's held, must sum to zero. Each node is read once: a piece's own, or a joint's. A solve that didn't converge, a voxel
  no piece has (an overlap, below), or a load landing on a joint leaves a residual. Over :data:`STATICS_TOL` of the
  case's load, no joint of that case is read from the FEA. **It can't see a voxel given to the wrong real piece:** each
  piece's joints still carry exactly what reaches it, so that one balances, and only moves force from one of the
  piece's joints to another (caliper-reviewer, #344). The labelling's own tests and the finer-grid check cover that.
- **A joint it can't see** reads not checked, never a number:
  - a piece fewer than ``VOXELS_THROUGH`` voxels through;
  - fewer than :data:`MIN_NODES` shared nodes;
  - a load or a support on the joint's own nodes.
- **Labelling:** each solid voxel is the piece it's inside (its centre within half a voxel of the piece's declared solid,
  the nearest if two are that close). A voxel inside two pieces at once (an overlap, a glue block drawn into its
  neighbour) belongs to neither: it's its own body, so what passes through it is no joint's. The statics pin then shows
  it as a residual.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

#: The statics pin's bar: a piece's residual, as a share of the case's load (see the PR for the measured residuals).
STATICS_TOL = 0.01
#: The fewest nodes two pieces share for the FEA to read the joint between them.
MIN_NODES = 4
#: A voxel's centre within this many voxels of a piece's declared solid is inside it.
INSIDE = 0.5
#: A voxel in no piece, and one in two at once.
NONE, OVERLAP = -1, -2

#: Why the FEA's side of a joint isn't read.
CANT_SEE = "the FEA can't see this joint at {h:.1f} mm voxels"
LOADED_AT = "a load or a support lands on the joint itself, so the FEA's force there isn't the joint's"
UNBALANCED = "the FEA's forces don't balance on the {piece} ({pct:.1f}% of the load), so no joint of this case is read from it"


#: A joint the hand rule couldn't follow, which the FEA read (#344): checked, by the FEA, and said so (#383)
CHECKED_BY_FEA = "checked by the FEA"

def _stick(points: np.ndarray, pc: dict) -> tuple[np.ndarray, np.ndarray]:
    """A stick's distance from each point (outside its inscribed radius, and past its flat ends), and whether each is
    surely inside it: within that radius and between its ends. Its section's turn about its axis isn't declared, so its
    corners (out to ``reach``, its half-diagonal) are claimed only where no other piece is nearer (:func:`labels`)."""
    a, b = np.asarray(pc["a"], float), np.asarray(pc["b"], float)
    L = float(np.linalg.norm(b - a)) or 1.0
    ax = (b - a) / L
    t = (points - a) @ ax
    radial = np.linalg.norm(points - a - t[:, None] * ax, axis=1)
    past = np.maximum(np.maximum(-t, t - L), 0.0)
    out = np.maximum(radial - float(pc["half"]), 0.0)
    return np.hypot(out, past), (out == 0.0) & (past == 0.0)


def distances(points: np.ndarray, pieces: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """``(len(pieces), len(points))`` twice: each point's distance from each piece's declared solid, mm (0 inside a
    sheet, or a stick's inscribed prism), and whether it's surely inside that piece."""
    from .consistency import slab_distance

    d = np.full((len(pieces), len(points)), np.inf)
    deep = np.zeros((len(pieces), len(points)), bool)
    for i, pc in enumerate(pieces):
        if pc["kind"] == "sheet" and pc.get("polys"):
            d[i] = np.min([slab_distance(points, p, pc["thickness"], s) for p, s in zip(pc["polys"], pc["sides"])],
                          axis=0)
            deep[i] = d[i] <= 1e-9
        elif pc["kind"] == "stick" and pc.get("a") is not None:
            d[i], deep[i] = _stick(points, pc)
    return d, deep


def labels(centres: np.ndarray, pieces: list[dict], h: float) -> np.ndarray:
    """Each voxel's piece, as an index into ``pieces``: of those whose solid its centre is in, within half a voxel
    (:data:`INSIDE`) or, for a stick, within its corners, the nearest. :data:`NONE` where it's in none, :data:`OVERLAP` where it's
    surely inside two at once (an overlap, a glue block drawn into its neighbour)."""
    if not pieces:
        return np.full(len(centres), NONE)
    d, deep = distances(centres, pieces)
    reach = np.array([(float(pc.get("reach", pc["half"])) - float(pc["half"])) if pc["kind"] == "stick" else 0.0
                      for pc in pieces])[:, None]
    inside = d <= reach + INSIDE * h
    near = np.argmin(np.where(inside, d, np.inf), axis=0)     # the nearest of those that can have it
    out = np.where(inside.any(axis=0), near, NONE)
    out[deep.sum(axis=0) > 1] = OVERLAP
    return out


def _how(j: dict, setup_: dict) -> str:
    """What holds a joint in shear, in words: its fixings, as the hand check says them."""
    from .joint_check import capacity

    return capacity(j, setup_["screw_mm"])["why"]["shear"]


def readable(j: dict) -> bool:
    """A joint the FEA's side is read for: one the hand check models as an edge on a face (``EDGE_KINDS``), placed.
    A dado, a through tenon, a notch or a leg short of the top is said as the hand check says it, never a number."""
    from .joint_check import EDGE_KINDS

    return ("unplaced" not in j and j.get("short") is None and not j.get("notch") and "edge" in j
            and j.get("kind") in EDGE_KINDS)


def _through(pc: dict) -> float:
    return float(pc["thickness"]) if pc["kind"] == "sheet" else 2.0 * float(pc["half"])


def read(solver, result, grid, pieces: list[dict], joints: list[dict], through: int, case: int = 0) -> dict:
    """Each placed joint's force and moment from one case's solve: ``{"joints": {pair: row}, "residual": share,
    "worst": piece key, "unbalanced": why or None, "each": {piece: share}}``. A row is ``{"force", "moment", "nodes"}``
    (what the joint's edge piece puts into its face piece, N and N mm about the joint's ``mid``), or ``{"unread": why}``.

    **Exact, by nodes.** A piece's voxels' nodal forces (``K u``), summed at a node, are what holds that piece there:
    the other pieces whose voxels touch the node, and any load or support on it. A node only two pieces share is wholly
    their joint's. Where three or more meet (a leg's top, under the top, between two aprons), the pairwise forces are
    the nearest even ones, weighted by how many voxel faces each pair has there, that are equal and opposite and give
    each piece exactly its own nodal force. So what one piece puts on another is what the other takes, each piece's
    joints carry exactly what reaches it, and the statics pin is left with the solve's own residual and whatever passed
    through a voxel no piece has (:data:`NONE`, :data:`OVERLAP`)."""
    h = float(grid.spacing)
    shape = tuple(grid.shape)
    kept = np.asarray(result.solid, bool)
    flat = np.flatnonzero(kept.ravel())
    n_el = len(flat)
    nodes = solver._nodes[flat]                                 # (elements, 8) node ids, corners in whittle's order
    u = np.asarray(result.displacement, float).reshape(-1, 3)
    n_nodes = len(u)
    fe = u[nodes].reshape(n_el, 24) @ solver._ke
    if solver.stiffness is not None:
        fe = fe * np.asarray(solver.stiffness).ravel()[flat][:, None]
    fe = fe.reshape(n_el, 8, 3)
    origin = np.asarray(grid.origin, float)
    ijk = np.stack(np.unravel_index(flat, shape), axis=1)
    lab = labels(origin + h * ijk, pieces, h)
    bodies = sorted(set(int(x) for x in lab))

    def by_node(ids, f):
        return np.stack([np.bincount(ids, weights=f[:, k], minlength=n_nodes) for k in range(3)], axis=1)

    force = {b: by_node(nodes[lab == b].ravel(), fe[lab == b].reshape(-1, 3)) for b in bodies}
    touch = {b: np.bincount(nodes[lab == b].ravel(), minlength=n_nodes) for b in bodies}
    count = sum((touch[b] > 0).astype(int) for b in bodies)
    voxels = sum(touch.values())
    applied = np.asarray(solver.forces[case], float).reshape(-1, 3)
    fixed = np.asarray(solver._fixed, bool).reshape(-1, 3)
    outer = np.where(fixed, sum(force.values()), applied)      # what acts on a node from outside: its load, or reaction
    on_node = (np.abs(applied).sum(axis=1) > 0) | fixed.any(axis=1)

    # each pair of bodies' voxel faces at each node: how a node's force is split where three or more meet
    from whittle.physics.fea import _CORNERS

    where = np.full(shape, -1, dtype=np.int64)
    where[tuple(ijk.T)] = np.arange(n_el)
    contact: dict = {}
    for axis in range(3):
        lo, hi = [slice(None)] * 3, [slice(None)] * 3
        lo[axis], hi[axis] = slice(0, -1), slice(1, None)
        ea, eb = where[tuple(lo)].ravel(), where[tuple(hi)].ravel()
        m = (ea >= 0) & (eb >= 0)
        ea, eb = ea[m], eb[m]
        m = lab[ea] != lab[eb]
        ea, eb = ea[m], eb[m]
        corners = nodes[ea][:, _CORNERS[:, axis] == 1]          # the shared face: a's high side on this axis
        for x, y in set(zip(lab[ea].tolist(), lab[eb].tolist())):
            pick = (lab[ea] == x) & (lab[eb] == y)
            c = np.bincount(corners[pick].ravel(), minlength=n_nodes)
            contact[(x, y)] = contact.get((x, y), 0) + c
            contact[(y, x)] = contact.get((y, x), 0) + c

    # what each piece puts on each other at the nodes they share, equal and opposite: where two meet, all of it; where
    # three or more do, the pairwise forces nearest even (a Laplacian, weighted by their faces there) that give each
    # piece exactly its own nodal force
    at = np.flatnonzero(count > 1)
    nb = len(bodies)
    T = np.stack([touch[b][at] > 0 for b in bodies], axis=1)                   # (shared nodes, bodies)
    g = np.stack([force[b][at] - outer[at] * (touch[b][at] / np.maximum(voxels[at], 1))[:, None] for b in bodies],
                 axis=1)                                                       # each body's force there, less its load
    pairs: dict = {}                                                           # (x, y): ([node], [force on y from x])

    def put(x, y, ids, f):
        got = pairs.setdefault((x, y), ([], []))
        got[0].append(ids)
        got[1].append(f)

    two = T.sum(axis=1) == 2
    for x in range(nb):
        for y in range(x + 1, nb):
            m = two & T[:, x] & T[:, y]
            if m.any():
                put(bodies[x], bodies[y], at[m], g[m, y])
                put(bodies[y], bodies[x], at[m], g[m, x])
    for k in np.flatnonzero(~two):
        here = np.flatnonzero(T[k])
        w = np.full((len(here), len(here)), 1e-3)                              # every pair joined, faces weigh most
        for p_, x in enumerate(here):
            for q_, y in enumerate(here):
                c = contact.get((bodies[x], bodies[y]))
                if p_ != q_ and c is not None:
                    w[p_, q_] += float(c[at[k]])
        np.fill_diagonal(w, 0.0)
        lap = np.diag(w.sum(axis=1)) - w
        phi = np.linalg.pinv(lap) @ g[k, here]                                 # (k, 3)
        for p_, x in enumerate(here):
            for q_, y in enumerate(here):
                if p_ != q_:
                    put(bodies[x], bodies[y], np.array([at[k]]), (w[p_, q_] * (phi[q_] - phi[p_]))[None])
    pairs = {xy: (np.concatenate(ids), np.concatenate(fs)) for xy, (ids, fs) in pairs.items()}

    pos = origin - h / 2 + h * np.stack(np.unravel_index(np.arange(n_nodes), tuple(s + 1 for s in shape)), axis=1)
    key = {i: pc["key"] for i, pc in enumerate(pieces)}
    idx = {pc["key"]: i for i, pc in enumerate(pieces)}
    load = float(np.linalg.norm(applied.sum(axis=0))) or 1.0
    residual, worst, each = 0.0, None, {}
    for a in bodies:
        if a < 0:
            continue
        held = sum((f.sum(axis=0) for (x, y), (_, f) in pairs.items() if y == a and x >= 0), np.zeros(3))
        r = held + (outer * (touch[a] / np.maximum(voxels, 1))[:, None]).sum(axis=0)
        each[key[a]] = float(np.linalg.norm(r)) / load
        if each[key[a]] > residual:
            residual, worst = each[key[a]], key[a]

    rows = {}
    for j in joints:
        if not readable(j):
            continue
        a, b = idx.get(j["edge"]), idx.get(j["face"])
        if a is None or b is None:
            continue
        pair_key = tuple(j["pieces"])
        ids, onto = pairs.get((a, b), (np.zeros(0, int), np.zeros((0, 3))))   # on the face piece, from the edge
        n = len(np.unique(ids))
        thin = min(_through(pieces[a]), _through(pieces[b])) / h
        if not sees(thin, through, n):
            rows[pair_key] = {"unread": CANT_SEE.format(h=h), "nodes": n}
            continue
        if bool(on_node[ids].any()):
            rows[pair_key] = {"unread": LOADED_AT, "nodes": n}
            continue
        arm = pos[ids] - np.asarray(j["mid"], float)
        rows[pair_key] = {"force": onto.sum(axis=0), "moment": np.cross(arm, onto).sum(axis=0), "nodes": n}
    unbalanced = unbalanced_by(residual, worst)
    return {"joints": rows, "residual": residual, "worst": worst, "unbalanced": unbalanced, "each": each}


def sees(thin: float, through: int, nodes: int) -> bool:
    """Whether the FEA can read a joint: both pieces ``through`` voxels or more through (``thin``, the thinner's), and
    :data:`MIN_NODES` shared nodes or more."""
    return thin >= through and nodes >= MIN_NODES


def unbalanced_by(residual: float, worst: Optional[str]) -> Optional[str]:
    """Why no joint of a case is read from the FEA: a piece's residual past :data:`STATICS_TOL` of its load; None at or
    under it."""
    return UNBALANCED.format(piece=worst, pct=100 * residual) if residual > STATICS_TOL else None


# ---------------------------------------------------------------------------------------------------------------------
# Beside the hand rule (#316 option C: each joint's demand is the larger, and a big disagreement is said)
# ---------------------------------------------------------------------------------------------------------------------
#: The FEA's demand on a joint this much more than the hand rule's is said.
DISAGREE = 0.25
#: What a row reading the FEA says about it, always.
BONDED = "the FEA holds the pieces as one, so its moment is a fully fixed joint's"
#: A joint with no pull capacity (a push-only post, glue on an edge with no screws): the bonded moment's pull is one it
#: can't give, so the load goes round it. That pull alone is waived, said so (the foreman, #316's (a)).
NO_PULL = "the FEA bonds the {edge} to the {face}, a pull its fixing can't give; the load goes round it, as the hand check has it"
#: An apron's end on a leg, its load from a top that bears on it by contact: the FEA's shear there stands (the
#: foreman, #316 (α)), said so.
HANDS = "the {top} bears on the {apron}, and it hands {lb:.0f} lb to the {leg} through {how}"
#: The same, where the apron hangs from the top: the bonded model's, waived (the foreman's (α)), naming what's there.
HUNG = "the FEA hangs the {apron} from the {top} by {by}, so what it hands the {leg} goes round it"
#: The same where what holds the apron to the top is credited a pull: the hang is carried by its fixings, so the shear the
#: apron hands the leg stands (the foreman, #344).
HUNG_HELD = "the {apron} hangs from the {top} by {by}, which hold a pull, and it hands {lb:.0f} lb to the {leg} through {how}"
#: A net pull without the moment, on a joint that can't take one: it lifts or opens, read as that.
LIFTS = "the FEA lifts the {edge} off the {face}"


def _arm(points, centre: np.ndarray, axis: np.ndarray, fallback: float) -> float:
    """The lever arm a moment about ``axis`` (through ``centre``) is taken over: where two or more fixings are
    declared, the farthest one's share, Σx² / x_max (so its force is M x_max / Σx²); else ``fallback``."""
    if points is not None and len(points) >= 2:
        rel = np.asarray(points, float) - centre
        x = rel - np.outer(rel @ axis, axis)                    # each fixing's distance from the axis
        r = np.linalg.norm(x, axis=1)
        if float(r.max()) > 1e-9:
            return float((r ** 2).sum() / r.max())
    return fallback


def demand(j: dict, force: np.ndarray, moment: np.ndarray, pull_cap: Optional[float] = None,
           keep: float = 0.0) -> tuple[dict, bool]:
    """The FEA's force and moment on joint ``j`` as ``{"bearing", "withdrawal", "shear"}``, N, and whether a moment's
    pull was waived. The moment, a fully fixed joint's: about the joint's line, a couple over half the edge's thickness;
    about the line across it, over half its length (or its fixings, :func:`_arm`); turning in its plane, shear over half
    its length (or its fixings). Where the joint can take no pull (``pull_cap`` 0, or a post), the bonded model's
    pull is waived, said so (the foreman, #316 (iii)):
    - **a post:** only the moment's. A net pull without it is a real lift, so it still asks a pull: ✗;
    - **an edge joint:** the moment's and its direct net pull, past ``keep``: the pull statics alone puts on it (a raked
      leg's thrust on its tie, :func:`caliper.joint_check.rake_rows`), which is never waived."""
    from .joint_check import _face, split

    parts = split(j, force, j["edge"])
    n = _face(j)
    along = np.asarray(j.get("along") if j.get("along") is not None else np.cross(n, [1.0, 0.0, 0.0]), float)
    along = along - n * float(along @ n)
    along = along / (np.linalg.norm(along) or 1.0)
    across = np.cross(n, along)
    m = np.asarray(moment, float)
    centre = np.asarray(j["mid"], float)
    half_t, half_l = float(j.get("edge_t", 1.0)) / 2.0, float(j.get("length_mm", 1.0)) / 2.0
    pts = j.get("points") or None
    pull = (abs(float(m @ along)) / max(half_t, 1e-6)
            + abs(float(m @ across)) / max(_arm(pts, centre, across, half_l), 1e-6))
    turn = abs(float(m @ n)) / max(_arm(pts, centre, n, half_l), 1e-6)
    none = bool(j.get("post")) if pull_cap is None else pull_cap <= 0.0
    if not none:
        return {"bearing": parts["bearing"], "withdrawal": parts["withdrawal"] + pull, "shear": parts["shear"] + turn}, False
    if j.get("post"):
        return {"bearing": parts["bearing"], "withdrawal": parts["withdrawal"], "shear": parts["shear"] + turn}, pull > 1e-6
    total = parts["withdrawal"] + pull
    return ({"bearing": parts["bearing"], "withdrawal": min(total, max(float(keep), 0.0)), "shear": parts["shear"] + turn},
            total > max(float(keep), 0.0) + 1e-6)


def row(j: dict, reading: dict, screw_mm: float, min_safety: float, keep: float = 0.0) -> dict:
    """The FEA's side of one joint: ``{"safety", "mode", "demand_lb", "nodes", "said"}``, or ``{"unread": why}``."""
    from . import verdicts as V
    from .joint_check import LBF, capacity

    if "unread" in reading:
        return {"unread": reading["unread"]}
    cap = capacity(j, screw_mm)
    parts, waived = demand(j, reading["force"], reading["moment"], cap["withdrawal"], keep)
    by = {m: (cap[m] / parts[m] if cap[m] > 0 else 0.0) for m in ("bearing", "withdrawal", "shear") if parts[m] > 1e-6}
    mode = min(by, key=by.get) if by else None
    safety = V.cut(by[mode]) if mode else None
    said = [BONDED]
    if waived:
        said.append(NO_PULL.format(edge=j["edge"], face=j["face"]))
    if j.get("post") and cap["withdrawal"] <= 0.0 and parts["withdrawal"] > 1e-6:
        said.append(LIFTS.format(edge=j["edge"], face=j["face"]))
    return {"safety": safety, "mode": mode, "nodes": reading["nodes"], "waived": waived,
            "demand_lb": {m: round(v / LBF, 1) for m, v in parts.items() if v > 1e-6},
            "said": "; ".join(said)}


def _feeds(j: dict, setup_: dict, reading: dict) -> Optional[tuple]:
    """For an apron's end on a leg: how its load reaches the apron from the piece above it, by the FEA. ``(top, push,
    joint)``:
    the joint of the apron's edge on a sheet's face that isn't a leg, and whether the apron pushes up into it (the top
    bearing down on it, by contact) rather than hangs from it. None where there's no such joint, or the FEA didn't read
    it."""
    from .joint_check import split

    apron = j["edge"]
    for k in setup_["joints"]:
        if k is j or not readable(k) or k.get("edge") != apron or k.get("apron") or k.get("post"):
            continue
        got = reading["joints"].get(tuple(k["pieces"]))
        if got is None or "force" not in got:
            continue
        parts = split(k, got["force"], apron)
        return k["face"], parts["bearing"] >= parts["withdrawal"], k
    return None


def held_by(k: dict) -> str:
    """What holds joint ``k`` in a pull, in words, as the hand check credits it (caliper-reviewer, #344: never "a glue
    line" where it's screwed)."""
    from .joint_check import _count

    n = int(k.get("screws") or 0) if "screws" in (k.get("fix") or []) else 0
    glue = "glue" in (k.get("fix") or [])
    if n:
        return f"{_count(n)} #8 screw{'' if n == 1 else 's'}" + (" and glue" if glue else "")
    return "a glue line that gets no credit in a pull" if glue else "nothing that holds a pull"


def _both(j: dict, got: dict, hand_n: Optional[list], keep: float, screw_mm: float, min_safety: float):
    """A joint's row safety held by ``n`` screws, as the fresh check will read it (#344): the lower of the FEA's side
    (its demand read again, since a pull's waiver turns on what holds it) and the hand rule's, from ``hand_n`` (each
    demand it answers to, N by mode, unrounded), where it has a number."""
    from . import joint_check as JC

    by_hand = JC._by_hand(j, hand_n, screw_mm) if hand_n else None

    def at(n: int):
        f = row(JC.screwed(j, n), got, screw_mm, min_safety, keep=keep).get("safety")
        h = by_hand(n) if by_hand else None
        return min((x for x in (f, h) if x is not None), default=None)
    return at


def beside(check: dict, reading: dict, setup_: dict, min_safety: float) -> dict:
    """The hand check's result with the FEA's side of each joint beside it (#316 option C). Each row's safety is the
    lower of the two; where the hand rule has none, the FEA's is the row's; where the FEA can't read the joint, it's
    said and the hand rule's stands, or the joint stays not checked, never ✓. A disagreement of :data:`DISAGREE` or more
    is said. Returns a new result."""
    from . import joint_check as JC
    from . import verdicts as V

    out = {**check, "rows": [dict(r) for r in check.get("rows") or []],
           "unchecked": list(check.get("unchecked") or []), "fea": {"residual": round(reading["residual"], 5)}}
    if reading.get("unbalanced"):
        out["fea"]["unread"] = reading["unbalanced"]
        return out
    by_pair = {tuple(r["pieces"]): r for r in out["rows"] if "pieces" in r and not r.get("column")}
    for j in setup_["joints"]:
        got = reading["joints"].get(tuple(j["pieces"])) if readable(j) else None
        if got is None:
            continue
        hand = by_pair.get(tuple(j["pieces"]))
        fea = row(j, got, setup_["screw_mm"], min_safety, keep=(hand or {}).get("rake_n", 0.0))
        between = f"the {j['edge']} and the {j['face']}"
        if hand is None:                                     # the hand rule couldn't follow it: the FEA's is the row
            if "unread" in fea:
                out["unchecked"].append(f"the joint between {between} ({fea['unread']})")
                continue
            # a pull waived with no hand number beside it: the load's route is the joint, so never ✓ through the
            # waiver (the foreman); what's left failing still fails
            if fea["waived"] and (fea["safety"] is None or fea["safety"] >= min_safety):   # producer
                out["unchecked"].append(f"the joint between {between} ({NO_PULL.format(edge=j['edge'], face=j['face'])})")
                continue
            hand = {"pieces": j["pieces"], "between": between, "edge": j["edge"], "face": j["face"], "mode": None,
                    "safety": None, "need": min_safety, "holds": True, "said": CHECKED_BY_FEA,
                    "assumed": j.get("assumed"), "_new": True,
                    **({"crowded": j["crowded"], "said": f"{CHECKED_BY_FEA}; {j['crowded']}"} if j.get("crowded") else {})}
            out["rows"].append(hand)
        hand["fea"] = fea
        if "unread" in fea:
            continue
        fed = _feeds(j, setup_, reading) if j.get("apron") else None
        if fed is not None and fea["mode"] == "shear":     # an apron's end on a leg: which way its load came (#316 (α))
            top, push, k = fed
            if push:
                fea["said"] += "; " + HANDS.format(top=top, apron=j["edge"], leg=j["face"],
                                                   lb=fea["demand_lb"].get("shear", 0.0), how=_how(j, setup_))
            elif JC.capacity(k, setup_["screw_mm"])["withdrawal"] > 0.0:   # its fixings carry the hang: it stands
                fea["said"] += "; " + HUNG_HELD.format(top=top, apron=j["edge"], leg=j["face"], by=held_by(k),
                                                       lb=fea["demand_lb"].get("shear", 0.0), how=_how(j, setup_))
            else:                                         # nothing credited holds the hang: the bonded model's, waived
                hung = HUNG.format(apron=j["edge"], top=top, leg=j["face"], by=held_by(k))
                if hand.pop("_new", False):               # no hand number beside it: not checked, never ✓
                    out["rows"].remove(hand)
                    out["unchecked"].append(f"the joint between {between} ({hung})")
                    continue
                hand["fea"] = {**fea, "safety": None, "waived": True, "said": f"{fea['said']}; {hung}"}
                continue
        hs, fs = hand.get("safety"), fea["safety"]
        if fs is not None and (hs is None or fs < hs):
            hand.update({"safety": fs, "mode": fea["mode"], "by": "fea", "need": min_safety,
                         "verdict": V.meets(fs, min_safety), "holds": fs >= min_safety})  # producer
            if hand.get("_new"):                 # the hand rule had none: the FEA checked it, said once (#383)
                hand["said"] = f"{CHECKED_BY_FEA}: {fea['said']}" + (f"; {hand['crowded']}" if hand.get("crowded") else "")
            else:
                hand["said"] = f"{hand.get('said') or ''}; by the FEA: {fea['said']}".lstrip("; ")
        now = hand.get("safety")                 # the row's, the lower of the two: both read again at each count
        if fs is not None and now is not None and now < min_safety:   # producer: what takes it past (#316, #344)
            hand.pop("more_screws", None)
            hand.pop("fix", None)
            # a hand number with no demand to read it again by: no count, rather than one only the FEA's side passes
            more = JC.fix_it(j, min_safety, _both(j, got, hand.get("demands_n") if hs is not None else None,
                                                  hand.get("rake_n", 0.0), setup_["screw_mm"], min_safety)) \
                if hs is None or hand.get("demands_n") else None
            if more:                              # the count both sides pass at: the fresh check reads the lower
                hand.update({"more_screws": more, "fix": more["said"]})
        hd = sum((hand.get("demand_lb") or {}).values())
        fd = sum(fea["demand_lb"].values())
        if hd > 0 and fd >= (1.0 + DISAGREE) * hd:
            hand["disagree"] = f"the FEA puts {100 * (fd / hd - 1):.0f}% more on it than the hand rule"
    # where the hand rule couldn't follow the load, its "not checked" goes only once the FEA has read every joint the
    # part has: one it didn't (a notch, a through tenon, one it can't see) keeps the case not checked, never ✓
    numbered = {tuple(r["pieces"]) for r in out["rows"] if (r.get("fea") or {}).get("safety") is not None}
    if not check.get("chain") and setup_["joints"] and all(readable(j) and tuple(j["pieces"]) in numbered
                                                            for j in setup_["joints"]):
        out["chain"] = True
        out["by_hand"] = list(check.get("unchecked") or [])
        out["unchecked"] = [u for u in out["unchecked"] if u not in out["by_hand"]]
    for r in out["rows"]:
        r.pop("_new", None)
    rated = [r for r in out["rows"] if r.get("safety") is not None]
    out["governing"] = min(rated, key=lambda r: r["safety"]) if rated else None
    return out
