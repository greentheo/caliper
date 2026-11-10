"""CALI-102 (#94, slice a) — the part tree: every part and its pieces, named, coloured, shown or hidden.

Theo, on the bar stool: "it looks like the part i made is called i_want ... it should have each part in a tree, and the
subcomponents for that part, can toggle them off and on ... relabel them". A part's pieces are what ``construction()``
and ``members()`` declare; each has a colour by its material (the tree's swatches are the legend), and a solid of its
own for the viewport, built the way the checks build it (``wood_solids``, ``printed_solid``).

**Names are labels, not ids.** A rename sets a label; the id that scripts, history, runs and files key on never changes,
so nothing saved breaks. A design with no labels shows its ids as it always has. Hiding a piece is the viewer's
business, kept in the page: it's still in every check.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore

#: a colour per material: the tree's swatches, and the viewport's pieces
COLOURS = {"plywood": "#C98A4B", "xps": "#E8D36A", "eps": "#EDE3B0", "steel": "#AAB6C3", "lumber": "#B5835A",
           "petg": "#4F8FE8", "pla": "#6FB98F", "abs": "#C77DD6", "tpu": "#E0806F"}
OTHER = "#9AA4AD"
#: the kinds of piece that are a solid of their own (a covering is on another piece's faces)
SOLID = ("sheet", "stick", "printed")
MOST = 60


#: words that follow a position, not a piece: "the front edge", "the top face"
GEOMETRY = r"(?!\s+(?:edges?|corners?|faces?|sides?|walls?)\b)"


def relabelled(store, pid: str, text: str) -> str:
    """``text`` with the part's pieces called what the person renamed them to (#185: "seat disk" stayed "seat top" on the cards and
    in the cut list, which keep the name the script gave them)."""
    import re

    for old, new in ((store.design.piece_labels or {}).get(pid) or {}).items():
        if new and new != old:
            # a name is whatever was typed, so it's never read as a pattern; and "the front edge" isn't the piece called front
            text = re.sub(r"(?<![\w])" + re.escape(old).replace("_", "[_ ]").replace(r"\ ", "[_ ]") + r"(?![\w])" + GEOMETRY,
                          lambda _, to=new: to, text)
    return text


def clean_label(text: str) -> str:
    """A name as it's kept: one line, trimmed. Raises with why for one too long."""
    label = " ".join((text or "").split())
    if len(label) > MOST:
        raise ValueError(f"a name is at most {MOST} characters")
    return label


def _items(store: DesignStore, pid: str) -> list[dict]:
    from . import construction as C

    try:
        return [it for it in (C._items(C.declared(store, pid)) or []) if isinstance(it, dict) and it.get("kind") in SOLID]
    except Exception:  # noqa: BLE001 — a part that won't declare shows as one body
        return []


def _keyed(items: list[dict]) -> list[tuple[str, dict]]:
    """Each piece with a key that's unique in its part: its name, or its name and a count where two share one."""
    seen: dict = {}
    out = []
    for it in items:
        name = it.get("name") or it["kind"]
        seen[name] = seen.get(name, 0) + 1
        out.append((name if seen[name] == 1 else f"{name} {seen[name]}", it))
    return out


def _material(it: dict) -> tuple[str, str]:
    """(what the row says, what the legend says) for one piece."""
    from . import construction as C
    from . import materials as M

    mat, kind = it.get("material") or "", it.get("kind")
    try:
        if kind == "printed":
            return mat.upper(), f"{mat.upper()}, printed"
        if kind == "sheet":
            name = M.sheet(mat)["name"]
            return name, f"{M.nominal(float(it['thickness']))} {name}"
        if "outer" in it:
            label = C.tube_label(it["outer"], it["wall"])
            return "steel tube", label
        return M.STICKS[mat or "lumber"]["name"], f"{it.get('size', '')} {M.STICKS[mat or 'lumber']['name']}".strip()
    except Exception:  # noqa: BLE001 — a material it can't name is said as written
        return mat, mat


def _colour(it: dict) -> str:
    return COLOURS.get(it.get("material") or ("lumber" if it.get("kind") == "stick" else ""), OTHER)


def pieces(store: DesignStore, pid: str) -> list[dict]:
    """A part's pieces, as the tree shows them: ``[{key, name, label, kind, material, legend, color}]``."""
    labels = (store.design.piece_labels or {}).get(pid) or {}
    out = []
    for key, it in _keyed(_items(store, pid)):
        short, legend = _material(it)
        out.append({"key": key, "name": labels.get(key) or key, "labelled": key in labels, "kind": it["kind"],
                    "material": short, "legend": legend, "color": _colour(it)})
    return out


def legend(parts: list[dict]) -> list[dict]:
    """The materials across these parts' pieces and how many of each: what the swatches mean."""
    seen: dict = {}
    for p in parts:
        for pc in p.get("pieces") or []:
            row = seen.setdefault((pc["legend"], pc["color"]), {"label": pc["legend"], "color": pc["color"], "count": 0})
            row["count"] += 1
    return list(seen.values())


def set_label(store: DesignStore, pid: str, label: str, piece: Optional[str] = None) -> str:
    """Rename a part, or one of its pieces (an empty name goes back to its id). The id never changes."""
    entry = store.design.part(pid)
    if entry is None:
        raise ValueError(f"there's no part {pid!r}")
    if next((p.role for p in store.assembly.parts if p.id == pid), None) == "fixed":
        raise ValueError(f"{pid} is a reference: it isn't yours to rename")
    label = clean_label(label)
    if piece is None:
        entry.label = label or None
    else:
        if piece not in dict(_keyed(_items(store, pid))):
            raise ValueError(f"{pid} has no piece {piece!r}")
        mine = {**((store.design.piece_labels or {}).get(pid) or {})}
        if label and label != piece:
            mine[piece] = label
        else:
            mine.pop(piece, None)
        store.design.piece_labels = {**(store.design.piece_labels or {}), pid: mine}
    store.save()
    return label


def mesh(store: DesignStore, pid: str, key: str):
    """One piece as a solid, where it sits in the design: the printed rest as the checks cut it (a carved part's is the
    carving), a sheet or stick as ``wood_solids`` builds it. Raises ``KeyError`` for a piece it hasn't got."""
    import numpy as np
    import trimesh

    from . import construction as C
    from . import measure

    it = dict(_keyed(_items(store, pid))).get(key)
    if it is None:
        raise KeyError(key)
    if it["kind"] == "printed":
        return C.printed_solid(store, pid, C.declared(store, pid))
    posed = store.part_geometry(pid).require_mesh()
    part = next(p for p in store.assembly.parts if p.id == pid)
    pose = measure.pose_matrix(part.position, part.rotation)
    local = posed
    if not np.allclose(pose, np.eye(4)):
        local = posed.copy()
        local.apply_transform(np.linalg.inv(pose))
    solid = trimesh.util.concatenate(C.wood_solids({"construction": [it]}, local))
    solid.apply_transform(pose)
    return solid
