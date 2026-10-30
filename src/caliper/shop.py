"""CALI-48 (#4) — the shop: what you have to make things with, and which of it makes each piece.

A design input beside the requirements, saved per person and used by every design (``specs/
caliper-make-loop-spec.md`` §2). Most shops are hand tools, so that's the default: a jigsaw, a drill, a
circular saw. Machines are added as they're there:

    hand: [jigsaw, drill, circular saw, hot wire, welder]
    machines:
      - {id: router, kind: router, bed_in: [48, 96], materials: [plywood, xps]}
      - {id: plasma, kind: plasma, bed_in: [48, 48], plate_max_in: 0.375, materials: [steel]}
      - {id: printer, kind: printer, volume_mm: [256, 256, 256], materials: [pla, petg]}

:func:`route` says, for each piece a part is built from, what in this shop makes it, or that nothing does
and what would. A machine is preferred where it's there and the piece fits it; hand tools otherwise.
"""

from __future__ import annotations

import os
from typing import Optional

IN = 25.4

#: Hand tools Caliper knows, and what each one cuts (or does).
HAND = {
    "jigsaw": "sheet goods up to 1 1/2 in thick, curves and holes (start a hole from a drilled one)",
    "circular saw": "straight cuts in sheets and boards",
    "hand saw": "straight cuts in boards and thin sheet, slowly",
    "drill": "holes, screws, and the starter hole a jigsaw needs",
    "hot wire": "foam board, curves and all",
    "knife": "foam board, straight cuts and score lines",
    "chop saw": "steel tube and lumber to length, square or mitred",
    "hacksaw": "steel tube to length, slowly",
    "welder": "steel tube and plate joined",
    "angle grinder": "steel plate, roughly",
}
DEFAULT = {"hand": ["jigsaw", "drill", "circular saw"], "machines": []}
MACHINES = ("router", "plasma", "printer")
#: The thickest a jigsaw goes through wood comfortably.
JIGSAW_MAX_MM = 1.5 * IN


def path() -> str:
    return os.environ.get("CALIPER_SHOP") or os.path.join(os.path.expanduser("~"), ".caliper", "shop.yaml")


def read() -> dict:
    """Your shop, or a hand-tool shop if you haven't said."""
    import yaml

    p = path()
    if not os.path.exists(p):
        return {**DEFAULT, "default": True}
    with open(p) as f:
        data = yaml.safe_load(f) or {}
    return {"hand": list(data.get("hand") or []), "machines": list(data.get("machines") or [])}


def write(data: dict) -> dict:
    import yaml

    hand = [h for h in data.get("hand") or [] if h in HAND]
    machines = [m for m in data.get("machines") or [] if isinstance(m, dict) and m.get("kind") in MACHINES]
    for m in machines:
        m.setdefault("id", m["kind"])
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), "w") as f:
        f.write("# Your shop (CALI-48): what Caliper plans the making with. Edit here or under Shop in the app.\n")
        yaml.safe_dump({"hand": hand, "machines": machines}, f, sort_keys=False)
    return read()


def machine(shop: dict, kind: str) -> Optional[dict]:
    return next((m for m in shop.get("machines") or [] if m.get("kind") == kind), None)


def _fits(size_mm, bed_in) -> bool:
    if not bed_in:
        return True
    a, b = sorted(size_mm, reverse=True)[:2]
    x, y = sorted((float(v) * IN for v in bed_in), reverse=True)
    return a <= x and b <= y


def route(piece: dict, shop: dict) -> dict:
    """What in this shop makes one piece (a take-off row): ``{"how", "machine", "ok", "why"}``."""
    kind, mat = piece.get("kind"), piece.get("material")
    hand = set(shop.get("hand") or [])

    def got(how, why="", machine=None):
        return {"how": how, "machine": machine, "ok": True, "why": why}

    def missing(why):
        return {"how": None, "machine": None, "ok": False, "why": why}

    if kind == "sheet":
        size, t = piece.get("size_mm") or [0, 0], float(piece.get("thickness") or 0)
        router, plasma = machine(shop, "router"), machine(shop, "plasma")
        if mat == "steel":
            if plasma and t <= float(plasma.get("plate_max_in", 0.375)) * IN + 0.01 and _fits(size, plasma.get("bed_in")):
                return got("plasma", machine=plasma["id"])
            if plasma and t > float(plasma.get("plate_max_in", 0.375)) * IN + 0.01:
                return missing(f"thicker than your plasma table cuts ({plasma.get('plate_max_in', 0.375)} in): "
                               f"a fab shop can cut it")
            if "angle grinder" in hand:
                return got("angle grinder", "roughly: file it to the line")
            return missing("steel plate: a plasma table, or a fab shop that has one")
        if router and mat in (router.get("materials") or [mat]) and _fits(size, router.get("bed_in")):
            return got("router", machine=router["id"])
        if mat in ("xps", "eps"):
            for tool in ("hot wire", "knife", "jigsaw"):
                if tool in hand:
                    return got(tool, "score lines with a knife" if piece.get("scored") else "")
            return missing("foam board: a hot wire or a knife")
        holes = bool(piece.get("holes"))
        if "jigsaw" in hand and t <= JIGSAW_MAX_MM:
            return got("jigsaw", "drill a 3/8 in hole inside each hole's line to start" if holes else "")
        if "circular saw" in hand and not holes and piece.get("flat", True):
            return got("circular saw", "straight cuts only")
        if router and not _fits(size, router.get("bed_in")):
            return missing("bigger than your router's bed, and no jigsaw for it")
        return missing("a jigsaw (or a router) for this one" if t <= JIGSAW_MAX_MM
                       else "too thick for a jigsaw: a router or a band saw")
    if kind == "stick":
        if mat == "steel":
            saw = next((s for s in ("chop saw", "hacksaw", "angle grinder") if s in hand), None)
            if not saw:
                return missing("steel tube: a chop saw or a hacksaw, and a welder to join it")
            return got(saw, "" if "welder" in hand else "and a welder to join it (not in your shop)")
        saw = next((s for s in ("chop saw", "circular saw", "hand saw", "jigsaw") if s in hand), None)
        return got(saw) if saw else missing("a saw for the lumber")
    if kind == "printed":
        printer = machine(shop, "printer")
        if not printer:
            return missing("a 3D printer (or a print service)")
        if mat and printer.get("materials") and mat not in printer["materials"]:
            return missing(f"your printer isn't set up for {mat.upper()}")
        return got("printer", machine=printer["id"])
    return got("by hand")
