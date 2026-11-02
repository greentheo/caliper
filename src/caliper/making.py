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


def plan(store: DesignStore, part_id: str, shop: Optional[dict] = None, *, out_dir: Optional[str] = None) -> dict:
    """How this part is made in the shop. ``out_dir`` keeps a printed part's pieces as STLs there."""
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
        keep = out_dir or tempfile.mkdtemp(prefix="caliper-print-")
        os.makedirs(keep, exist_ok=True)
        each = []
        for i, m in enumerate(parts):
            name = f"{part_id}-{i + 1}-of-{len(parts)}.stl" if len(parts) > 1 else f"{part_id}.stl"
            path = os.path.join(keep, name)
            m.export(path)
            each.append({"file": name, **printing.estimate(path, pc["material"], volume)})
        printed.append({"name": pc["name"], "material": pc["material"], "pieces": len(parts),
                        "pinned": len(parts) > 1, "files": each,
                        "hours": round(sum(e["hours"] for e in each), 1),
                        "filament_g": round(sum(e["filament_g"] for e in each)),
                        "usd": round(sum(e["usd"] for e in each), 2), "trust": each[0]["trust"],
                        "from": each[0]["from"]})
    by_how: dict = {}
    for p in pieces:
        if p["ok"]:
            by_how.setdefault(p["how"], []).append(p["name"])
    missing = [p for p in pieces if not p["ok"]]
    return {"part": part_id, "shop_default": bool(shop.get("default")), "pieces": pieces, "by_how": by_how,
            "printed": printed, "missing": missing, "ok": not missing}
