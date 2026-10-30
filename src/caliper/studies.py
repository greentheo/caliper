"""CALI-70 — every study a design has, in one list, and what each part could have next.

The studies live with their parts' panels (a drag search under the part it shaped, a strength check
under the part it loaded), which is the right place to read one and the wrong place to find one. This
is the index: every run of every kind, newest first, each with the part and the version it was run on
(and whether the part has changed since), the one line it came to, and where to open it. And a menu:
for each part, every study Caliper has, whether it can run on that part, and if not, what it's missing.

Runs that don't record the version they saw get it from the part's history: the last revision before
the run.

Not every study fits every design (CALI-67): drag matters to something that moves through air, and a
bathroom stool shouldn't be offered a drag study at 65 mph. :func:`in_air` decides that once, from what
the design says, and the panels and this menu both follow it.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Optional

#: What says a design moves through air, or air moves past it: a vehicle, a road speed, wind.
AIR_WORDS = re.compile(r"\b(cars?|trucks?|vans?|vehicles?|trailers?|hitch\w*|tow(?:s|ed|ing)?|roof ?racks?|"
                       r"cargo box|drag|aero\w*|airflow|fairings?|wind(?:s|y)?|wind turbine|mph|km/?h|"
                       r"highway|bikes?|bicycles?|boats?|drones?|kites?)\b", re.I)


def in_air(design, parts: list[dict], has_runs: bool = False) -> dict:
    """``{"yes": bool, "why": str}``: does anything say this design moves through air?

    Its prompt, its requirements and its parts' descriptions are read for a vehicle, a road speed or wind;
    a reference part (the car) means something rides behind it; and a design that already has drag studies
    keeps them."""
    text = " ".join([design.prompt or ""] + [f"{r.question} {r.answer}" for r in design.requirements]
                    + [p.get("intent") or "" for p in parts])
    m = AIR_WORDS.search(text)
    if m:
        return {"yes": True, "why": f"it says “{m.group(0)}”"}
    ref = next((p["id"] for p in parts if p.get("role") == "fixed"), None)
    if ref:
        return {"yes": True, "why": f"it rides behind {ref}"}
    if has_runs:
        return {"yes": True, "why": "it has drag studies already"}
    return {"yes": False, "why": "nothing in the design says it moves through air (a vehicle, a road speed, "
                                 "wind); say so and the drag studies appear"}

#: Every kind of study, in the order the menu offers them: the question it answers, and its label.
KINDS = {
    "load": ("Strength", "Will it hold what it must carry?"),
    "frame": ("Frame sizing", "The lightest tubes that still hold, and what the hitch carries"),
    "gussets": ("Gusset plates", "Plates for the frame's hardest-worked joints, cut for a plasma table"),
    "aero": ("Drag shape search", "The numbers in its script that cut drag, within their ranges"),
    "whittle": ("whittle carving", "Carve the outside for drag (or lighten it under load) as a mesh"),
    "cutplan": ("Cut plan", "Every sheet laid out flat for the saw, router or plasma table"),
    "scorecard": ("Scorecard", "Every check and objective of the design as it stands"),
    "release": ("Build package", "The build book, cut files and shopping list for this exact version"),
}


def _epoch(ts) -> Optional[float]:
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return dt.datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        return None


def version_at(history: list[dict], when: Optional[float]) -> Optional[int]:
    """The part's version at ``when``: its last revision before then."""
    if when is None:
        return None
    seen = None
    for h in history:
        t = _epoch(h.get("ts"))
        if h.get("kind") == "revision" and h.get("version") is not None and t is not None and t <= when + 1:
            seen = int(h["version"])
    return seen if seen is not None else 1


def _lb(v) -> str:
    return f"{v:,.1f} lb" if v is not None else "?"


def _headline(kind: str, r: dict) -> tuple[str, Optional[bool]]:
    """What a run came to, in one line, and whether that's good news (None: neither)."""
    if kind == "load":
        cases = r.get("cases") or []
        worst = min(cases, key=lambda c: c.get("safety") if c.get("safety") is not None else 1e9, default=None)
        if worst is None:
            return "no loads", None
        what = (f"{worst['name']}: {round(worst['safety'], 1):g}x" if worst.get("safety") is not None
                else worst["name"])
        return (("holds" if r.get("holds") else "doesn't hold") + f" — weakest {what}"
                + (f" (needs {r.get('min_safety', 2):g}x)" if not r.get("holds") else ""), bool(r.get("holds")))
    if kind == "frame":
        ok = [s for s in r.get("stations", []) if s.get("safety", 0) >= r.get("min_safety", 0)]
        if not ok:
            best = max(r.get("stations", []), key=lambda s: s.get("safety", 0), default={})
            return f"no tubes reach {r.get('min_safety')}x (best {best.get('safety', '?')}x)", False
        light = min(ok, key=lambda s: s.get("mass_lb", 1e9))
        return (f"{r.get('layout') or 'as drawn'} · lightest that holds: {_lb(light.get('mass_lb'))} of steel "
                f"at {light.get('safety')}x"), True
    if kind == "gussets":
        joints = r.get("joints") or {}
        return f"{len(joints)} joint(s): {', '.join(joints)}", None
    if kind == "aero":
        best = max(r.get("stations", []), key=lambda s: (s.get("derived") or {}).get("saved_n", 0), default={})
        d = best.get("derived") or {}
        searched = ", ".join(r.get("searched") or [])
        if not d:
            return f"searched {searched}", None
        return (f"best saves {d.get('saved_lbf', 0):g} lbf ({d.get('saved_kwh_per_100mi', 0):g} kWh/100 mi) "
                f"· searched {searched}"), None
    if kind == "whittle":
        st = r.get("stations") or []
        most = max((s.get("removed_part") or s.get("removed") or 0 for s in st), default=0)
        best = max(st, key=lambda s: (s.get("derived") or {}).get("saved_n", 0), default={})
        saved = (best.get("derived") or {}).get("saved_kwh_per_100mi")
        return (f"{r.get('kind')} · {len(st)} stations, up to {most:.0%} removed"
                + (f" · best saves {saved:g} kWh/100 mi" if saved else "")), None
    if kind == "cutplan":
        sheets = r.get("sheets") or []
        n = sum(s.get("sheets", 0) for s in sheets)
        use = [s.get("utilisation") for s in sheets if s.get("utilisation") is not None]
        tubes = len(r.get("tubes") or [])
        bits = ([f"{n} sheet(s)" + (f", {sum(use) / len(use):.0%} used" if use else "")] if n else [])
        bits += [f"{tubes} tube cut list(s)"] if tubes else []
        return " · ".join(bits) or "; ".join((r.get("notes") or ["nothing to cut"])[:1]), None
    if kind == "scorecard":
        s = r.get("summary") or {}
        return f"{s.get('pass', 0)} pass · {s.get('fail', 0)} fail", not s.get("fail")
    if kind == "release":
        return (f"release {r.get('id')} · {'ready to cut' if r.get('ready') else 'not ready: a check fails'}"
                f" · ~${round(r.get('shopping_usd') or 0)} to buy"), bool(r.get("ready"))
    return "", None


def index(store, runs: dict[str, list[dict]], parts: list[dict], air: Optional[dict] = None) -> dict:
    """``{"runs": [...], "menu": {part: [...]}}`` from the runs ``design_state`` already loaded (by kind)
    and its part summaries; ``air`` is :func:`in_air`'s answer (drag studies need it)."""
    current = {p["id"]: p["version"] for p in parts}
    history = {p["id"]: store.history(p["id"]) for p in parts}
    rows = []
    for kind, recs in runs.items():
        for r in recs:
            created = _epoch(r.get("created"))
            part = r.get("part")
            row = {"kind": kind, "label": KINDS[kind][0], "id": r.get("id"), "part": part,
                   "created": created}
            if r.get("versions"):                     # a scorecard or release: every part's version
                row["versions"] = r["versions"]
                row["stale"] = any(current.get(k) not in (None, v) for k, v in r["versions"].items())
            elif part in current:
                v = r.get("version") or version_at(history[part], created)
                row.update({"version": v, "current": current[part], "stale": v != current[part]})
            row["headline"], row["ok"] = _headline(kind, r)
            rows.append(row)
    rows.sort(key=lambda x: x["created"] or 0, reverse=True)
    whole = [{"kind": k, "label": KINDS[k][0], "what": KINDS[k][1], "ready": bool(parts), "why": "no parts yet"}
             for k in ("scorecard", "release")]
    return {"runs": rows, "menu": {p["id"]: menu(p, air) for p in parts}, "design": whole}


def menu(p: dict, air: Optional[dict] = None) -> list[dict]:
    """Every study, for one part: can it run here, and if not, why not (what to say or do to get it)."""
    mesh = not p.get("scripted")
    roll = "it's a mesh right now: say “roll it back” to get its script back"
    if p.get("role") == "fixed":
        return [{"kind": k, "label": label, "what": what, "ready": False,
                 "why": "it's a reference (context, like the car), not something you build"}
                for k, (label, what) in KINDS.items() if k not in ("scorecard", "release")]

    airborne, grounded = (air is None or air["yes"]), (air or {}).get("why", "")

    def item(kind, ready, why=""):
        label, what = KINDS[kind]
        return {"kind": kind, "label": label, "what": what, "ready": bool(ready), "why": "" if ready else why}

    out = [
        item("load", p.get("loads") and p.get("built"),
             roll if mesh else
             "a frame's strength is its frame sizing" if p.get("framed") else
             "say what it must carry (“it has to hold me, 200 lb, standing on top”) and the designer adds "
             "its loads()" if not p.get("loads") else "it doesn't say what it's built from (construction())"),
        item("frame", p.get("framed"), roll if mesh else "it isn't a welded tube frame (members() and supports())"),
        item("gussets", p.get("framed") and p.get("gussets"),
             "its frame names no joints for plates (GUSSETS)" if p.get("framed") else "it isn't a tube frame"),
        item("aero", airborne and not mesh and p.get("params") and not p.get("framed"),
             "a frame is sized, not shaped" if p.get("framed") else grounded if not airborne
             else roll if mesh else "its script keeps no dimensions in PARAMS"),
        item("whittle", airborne and not p.get("framed"),
             "a frame is sized, not shaped" if p.get("framed") else grounded),
        item("cutplan", p.get("built"), roll if mesh else "it doesn't say what it's built from (construction())"),
    ]
    return out
