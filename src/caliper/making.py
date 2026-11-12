"""CALI-48 (#4) — how a part gets made in your shop: every piece routed, printed parts fitted and costed.

For each piece a part is built from, :func:`caliper.shop.route` says what in your shop makes it (the
router if it fits, the jigsaw otherwise, the printer for a printed part) or what's missing. A printed part
is fitted to your printer: split with pin holes if it must be, with the time, filament and cost of each
piece. (Foam folds stay within what foam takes because the cut plan makes any sharper fold a cut.) This is
what "How do I make it?" reads, what the scorecard checks, and how the build package is filed.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from . import construction as C
from . import shop as S
from .design import DesignStore

IN = 25.4


def rows(store: DesignStore, part_id: str) -> list[dict]:
    """The part's take-off rows, a printed piece measured from the part's own solid."""
    d = C.declared(store, part_id)
    items = C.with_printed(store, part_id, C._items(d) or [], d)
    return C.takeoff(items) if items else []


def rough_said(rough: int, pieces: int, said: str) -> str:
    """How much of a printed group's numbers are a guess, and why, in one wording for the card, the panel and the build
    book (#160, #166): "" where every piece was sliced. ``said`` is the rough piece's ``from``, with its reason in brackets."""
    if not rough:
        return ""
    why = said[said.rfind("(") + 1:].rstrip(")") if "(" in said else said or "no reason given"
    if rough < pieces:
        return f"{rough} of {pieces} pieces {'is' if rough == 1 else 'are'} a rough guess: {why}"
    return f"a rough guess: {why}" if why == "no slicer installed" else f"a rough guess; the slicer couldn't work it out: {why}"


def _too_big_said(pieces: int, over: list, volume, inches: bool) -> str:
    """What doesn't fit, in the person's units: the piece that's furthest over, against the printer and its clearance. Only
    a part that doesn't fit gets here, and ``split`` always cuts one of those: so there are always pieces to count."""
    from . import printing
    from .answers import _len

    worst = max(over, key=lambda m: float(max(m.extents)))
    size = " x ".join(_len(float(v), inches) for v in sorted(worst.extents, reverse=True))
    bed = " x ".join(_len(float(v), inches) for v in volume)
    many = f"all {pieces} are too big" if len(over) == pieces else f"{len(over)} of the {pieces} {'is' if len(over) == 1 else 'are'} too big"
    return (f"cut into {pieces} pieces, {many}: the biggest is {size}, and your printer takes {bed}, less "
            f"{_len(printing.BED_MARGIN_MM, inches)} clearance: section it differently, in the chat, or use a bigger printer")


#: Where a printed group's filament figure came from, said beside it wherever it's given (#70 item 23).
FROM_SLICER, FROM_ROUGH, FROM_SOLID = "the slicer's estimate", "a rough guess", "by the model's solid"


def filament(report: Optional[dict], mk: Optional[dict]) -> Optional[dict]:
    """One filament figure for a printed group, wherever it's said (CALI-92, #70 item 23: the buy card said 1122 g and the
    shop panel 726 g for one print). It's the making plan's where the plan has one (the slicer's, or its rough guess
    where the slicer couldn't), else the model's solid share, and the part's weight goes with it. Each group says which
    in ``filament_from``. ``report`` is construction.report's and isn't changed: a new one is returned."""
    printed = ((report or {}).get("bom") or {}).get("printed")
    if not printed:
        return report
    made = {pr["name"]: pr for pr in (mk or {}).get("printed") or [] if pr.get("filament_g") is not None}
    groups, more_g = [], 0.0
    for g in printed:
        pr = made.get(g["name"])
        if pr is None:
            waiting = any(x.get("pending") for x in (mk or {}).get("printed") or [] if x["name"] == g["name"])
            groups.append({**g, "filament_from": FROM_SOLID, **({"filament_pending": True} if waiting else {})})
            continue
        more_g += pr["filament_g"] - g["filament_g"]
        groups.append({**g, "filament_g": pr["filament_g"],
                       "filament_from": FROM_SLICER if pr.get("trust") == "model" else FROM_ROUGH})
    out = {**report, "bom": {**report["bom"], "printed": groups}, "filament_more_kg": more_g / 1000}
    if report.get("mass_kg") is not None and more_g:          # kilograms and pounds on the one figure (#237 review)
        out["mass_kg"] = round(report["mass_kg"] + more_g / 1000, 2)
        out["mass_lb"] = round(out["mass_kg"] * C.M.LB_KG, 1)
    elif report.get("mass_lb") is not None and more_g:      # a report given its pounds alone
        out["mass_lb"] = round(report["mass_lb"] + more_g / 1000 * C.M.LB_KG, 1)
    return out


def filament_said(reports) -> tuple[str, str]:
    """``(guess, pending)`` over these reports' printed groups (#237 review): "a guess (…)" where a figure isn't the
    slicer's, so a weight or cost goal on it is an estimate, never a ✓; "still slicing" where the slicer's at it, so a
    goal waits rather than reading the solid's figure red. ``("", "")`` where every figure is the slicer's."""
    groups = [g for r in reports if r for g in ((r.get("bom") or {}).get("printed") or [])]
    pending = "still slicing" if any(g.get("filament_pending") for g in groups) else ""
    off = [g.get("filament_from", FROM_SOLID) for g in groups if g.get("filament_from") != FROM_SLICER]
    return (f"a guess (the filament is {off[0]})" if off else ""), pending


def filament_bound(reports) -> bool:
    """Whether every printed figure that isn't the slicer's is the solid's share, an upper bound on what it weighs (#237
    review): a "weighs under" goal that passes on it passes, and a "weighs at least" one that fails on it fails. A rough
    guess can run either way, so it's never a bound."""
    groups = [g for r in reports if r for g in ((r.get("bom") or {}).get("printed") or [])]
    off = [g.get("filament_from", FROM_SOLID) for g in groups if g.get("filament_from") != FROM_SLICER]
    return bool(off) and all(f == FROM_SOLID for f in off)


def settled_by_bound(op: str, met: Optional[bool]) -> bool:
    """Whether an upper bound settles a goal: under it and met, or at least it and not met."""
    return met is not None and ((op in ("<=", "<") and met) or (op in (">=", ">") and not met))


def no_print_total(mk: dict) -> str:
    """Why a print total can't be given for this part: a printed piece it can't make isn't in ``printed``, so a sum over that
    would read as the whole (#179 review, rule 6). "" where there's no such piece."""
    gone = next((m for m in mk["missing"] if m["kind"] == "printed"), None)
    if gone is None:
        return ""
    why = f"the {gone['name']} doesn't fit your printer" if gone.get("too_big") else f"your shop can't print the {gone['name']}"
    return f"can't be worked out: {why}"


def plan(store: DesignStore, part_id: str, shop: Optional[dict] = None, *, out_dir: Optional[str] = None,
         wait: bool = True) -> dict:
    """How this part is made in the shop. ``out_dir`` keeps a printed part's pieces as STLs there. ``wait=False``
    (the cards, #97): a printed part not sliced yet says its print time is being worked out (``pending``), no number."""
    from . import printing

    shop = shop or S.read()
    pieces = []
    for r in rows(store, part_id):
        if r["kind"] not in ("sheet", "stick", "printed"):
            continue
        how = S.route(r, shop)
        size = r.get("size_mm") or ([r["length_mm"]] if r.get("length_mm") else None)
        pieces.append({"name": r["name"], "kind": r["kind"], "label": r["label"], "material": r.get("material"),
                       "size_in": [round(v / IN, 2) for v in size] if size else None,
                       "holes": r.get("holes", 0), **how})
    printed = []
    printer = S.machine(shop, "printer")
    for pc in (p for p in pieces if p["kind"] == "printed" and p["ok"]):
        mesh = C.printed_solid(store, part_id)            # the sides, for a plywood top on printed sides
        volume = printer.get("volume_mm") or (256, 256, 256)
        parts = printing.split(mesh, volume)
        over = printing.too_big(parts, volume)
        if over:                                          # never ok on a piece that doesn't fit (#179, rule 6)
            pc["ok"], pc["too_big"], pc["why"] = False, True, _too_big_said(len(parts), over, volume, store.design.display_units == "in")
            continue
        keep = out_dir or tempfile.mkdtemp(prefix="caliper-print-")
        os.makedirs(keep, exist_ok=True)
        each = []
        for i, m in enumerate(parts):
            name = f"{part_id}-{i + 1}-of-{len(parts)}.stl" if len(parts) > 1 else f"{part_id}.stl"
            path = os.path.join(keep, name)
            m.export(path)
            each.append({"file": name, **printing.estimate(path, pc["material"], volume, wait=wait)})
        if any(e.get("hours") is None and e.get("slicer_failed") for e in each):   # a crashed slice: said, no total
            printed.append({"name": pc["name"], "material": pc["material"], "pieces": len(parts),
                            "pinned": printing.pinned(parts), "files": each, "slicer_failed": True, "hours": None,
                            "filament_g": None, "usd": None, "trust": None,
                            "from": next(e["from"] for e in each if e.get("hours") is None)})
            continue
        if any(e.get("pending") for e in each):     # one piece still slicing: no total, never a part of one
            printed.append({"name": pc["name"], "material": pc["material"], "pieces": len(parts),
                            "pinned": printing.pinned(parts), "files": each, "pending": True, "hours": None,
                            "filament_g": None, "usd": None, "trust": None, "from": printing.WORKING["from"]})
            continue
        rough = [e for e in each if e.get("trust") == "rough"]   # the group is as rough as its roughest piece (#160)
        printed.append({"name": pc["name"], "material": pc["material"], "pieces": len(parts),
                        "pinned": printing.pinned(parts), "files": each,
                        "hours": round(sum(e["hours"] for e in each), 1),
                        "filament_g": round(sum(e["filament_g"] for e in each)),
                        "usd": round(sum(e["usd"] for e in each), 2), "trust": (rough or each)[0]["trust"],
                        "from": (rough or each)[0]["from"], "rough": len(rough),
                        "rough_said": rough_said(len(rough), len(parts), rough[0]["from"] if rough else ""),
                        "slicer_failed": any(e.get("slicer_failed") for e in each)})
    by_how: dict = {}
    for p in pieces:
        if p["ok"]:
            by_how.setdefault(p["how"], []).append(p["name"])
    missing = [p for p in pieces if not p["ok"]]
    return {"part": part_id, "shop_default": bool(shop.get("default")), "pieces": pieces, "by_how": by_how,
            "printed": printed, "missing": missing, "ok": not missing,
            "pending": any(pr.get("pending") for pr in printed)}
