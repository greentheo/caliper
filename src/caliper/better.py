"""CALI-100 (#92 item 1, the server side) — Make it better, where the person looks: on *Will it work?*.

Theo, on the bar stool: "Where is the card for reducing mass using stress loading and 3d printable shapes?" The carve
and the lightening lived one click down, under the part's numbers. The four-questions spec puts them on *Will it
work?* as suggestions with a cost, not tools. Each line here is one improvement this part can take:

- **It fails as drawn:** only what would make it hold (a thicker sheet, from the plate check's own numbers), never
  something lighter (a carve or lightening takes material away, #137 item 3).
- **A result first, the cheapest first:** a thinner sheet the plate check says still holds (a number to change), then
  a carve's or lightening's step that holds, to use. A result is quoted only from a settled verdict: the part's own
  check holds (not middle only, too coarse, on a filled-in shape or of an older version), and the step holds.
- **Then an invitation,** with what it takes: a carve (a printed part) or a lightening (sheet walls), offered only
  where :func:`load_study.blocked` allows it, the one test the Carve button and the card both read (#144).

The page draws these as card lines (``better: True``), each going to its panel; its design waits for Theo's mockup.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore

#: a carve takes at least this many of its default check's time (the page's CARVE_PER_CHECK_AT_LEAST, #102)
CARVE_PER_CHECK = 45


def _minutes(m: float) -> str:
    return (f"{max(1, round(m))} min" if m < 60 else
            f"{m / 60:.1f}".rstrip("0").rstrip(".") + " h")


def _line(text: str, action: str, **kw) -> dict:
    return {"text": text, "status": "info", "study": "load", "action": action, "better": True, **kw}


def _printed_name(store: DesignStore, pid: str) -> str:
    from . import construction as C

    try:
        items = C.declared(store, pid).get("construction") or []
    except Exception:  # noqa: BLE001 — said with the part's own name
        items = []
    return next((it.get("name") for it in items if isinstance(it, dict) and it.get("kind") == "printed"), None) \
        or pid.replace("_", " ")


def _settled_check(store: DesignStore, p: dict, run: Optional[dict]) -> bool:
    """The part's own strength check, at this version, holds as a settled verdict: the numbers may be quoted."""
    from . import consistency, verdicts

    if run is None or run.get("version") != p["version"]:
        return False
    v = verdicts.run(run, filled=p.get("untrusted"), edge=bool(consistency.bare_edge(store, p["id"])))
    return v["kind"] == "holds"


def _sheet_offers(run: dict, fails: bool) -> list[dict]:
    """From the plate check on this version's run: the thinnest sheet that still holds (or, failing, the thinnest that
    would), its number the plate check's own, never the FEA's."""
    out, seen = [], set()
    need = run.get("min_safety") or 2
    for c in run.get("cases") or []:
        pl = c.get("plate") or {}
        if not pl.get("done") or c.get("governs") != "plate" or pl.get("piece") in seen:
            continue
        seen.add(pl["piece"])
        now = pl.get("thickness_mm")
        rows = [b for b in pl.get("by_thickness") or [] if b.get("safety_across") is not None]
        label_now = next((b["label"] for b in rows if abs(b["thickness_mm"] - now) < 0.01), f"{now:g} mm")
        if fails:
            ok = sorted((b for b in rows if b["thickness_mm"] > now + 0.01 and b["safety_across"] >= need),
                        key=lambda b: b["thickness_mm"])
            if ok:
                b = ok[0]
                out.append(_line(f"Make the {pl['piece']} from {b['label']} instead of {label_now}: it holds then, "
                                 f"about {b['safety_across']:.1f} times over by the plate check.", "use_t",
                                 say=f"Make the {pl['piece']} from {b['label']} instead of {label_now}"))
        else:
            ok = sorted((b for b in rows if b["thickness_mm"] < now - 0.01 and b["safety_across"] >= need),
                        key=lambda b: b["thickness_mm"])
            if ok:
                b = ok[0]
                out.append(_line(f"Make the {pl['piece']} from {b['label']} instead of {label_now}: still about "
                                 f"{b['safety_across']:.1f} times over by the plate check.", "use_t",
                                 say=f"Make the {pl['piece']} from {b['label']} instead of {label_now}"))
    return out


def offers(store: DesignStore, state: dict, pid: str) -> list[dict]:
    """Make it better, for one part: card lines, cheapest real improvement first. [] where there's nothing to offer
    (a reference, nothing it must hold)."""
    from . import carve as K
    from . import load_study as L
    from . import verdicts

    p = next((x for x in state.get("parts") or [] if x["id"] == pid), None)
    if p is None or p.get("role") == "fixed" or not p.get("loads") or not p.get("built"):
        return []
    blocked = p.get("blocked") if "blocked" in p else L.blocked(store, pid)
    run = L.default_check(store, pid)
    if blocked and blocked.get("why") == "already_fails":       # what would make it hold, never lighter
        return _sheet_offers(run, fails=True) if run else []
    settled = _settled_check(store, p, run)
    results, invites = [], []
    if settled:
        results += _sheet_offers(run, fails=False)
    name = _printed_name(store, pid)
    if p.get("printed") and not p.get("carved") and not (blocked or {}).get("carve"):
        mine = [r for r in state.get("carve_runs") or [] if r["part"] == pid and r.get("version") == p["version"]]
        done = next((r for r in mine if r.get("status") == "done"), None)
        if done is not None:
            best = next((st for st in done.get("stations") or [] if st["index"] == done.get("best")), None)
            v = verdicts.carve_step(best, p.get("untrusted"), done) if best else None
            if settled and best and best.get("saved_g") and v and v["counts_as_pass"]:
                results.append(_line(
                    f"Carve the {name} where it isn't working: {best['removed']:.0%} {K.share(done)} carved away, "
                    f"{best['saved_g']:,} g less filament, still about {best['safety']:.1f} times over.", "carve_use",
                    run=done["id"], station=best["index"]))
        elif not any(r.get("status") in (None, "running") for r in mine):
            secs = (run or {}).get("seconds")
            invites.append(_line(f"Carve the {name} where it isn't working, to use less filament: it takes "
                                 + (f"at least about {_minutes(secs * CARVE_PER_CHECK / 60)} at this size"
                                    if secs else "a while (check it holds first, and the time comes from that)")
                                 + ".", "carve"))
    if p.get("sheets") and not (blocked or {}).get("lighten") and not p.get("framed"):
        mine = [r for r in state.get("lighten_runs") or [] if r["part"] == pid and r.get("version") == p["version"]]
        done = mine[0] if mine else None
        if done is not None:
            ok = [st for st in done.get("stations") or [] if st.get("saved_lb")
                  and verdicts.lighten_step(st, p.get("untrusted"), done)["counts_as_pass"]]
            best = max(ok, key=lambda st: st["saved_lb"], default=None)
            if settled and best:
                results.append(_line(
                    f"Lighten it with holes where the wood isn't working: {best['saved_lb']:g} lb lighter, still "
                    f"about {best['safety']:.1f} times over.", "lighten_use", run=done["id"], station=best["index"]))
        else:
            invites.append(_line("Lighten it with holes where the wood isn't working: it takes a few minutes.",
                                 "lighten"))
    return results + invites
