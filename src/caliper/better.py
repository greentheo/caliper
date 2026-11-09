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

Each is ``{text, lead, cost, button, action, part, better: True}``: the page draws the lead, the cost beneath it and a
button (the mockup Theo approved); ``text`` is the same as one sentence. Where :func:`load_study.blocked` stops a carve
for anything but a part that already fails, the line stays, ``disabled``, its cost saying why it waits; and walls too
thin for the check get what would let the check see them.
"""

from __future__ import annotations

from typing import Optional

from .design import DesignStore

#: a carve takes at least this many of its default check's time (#102)
CARVE_PER_CHECK = 45


def _minutes(m: float) -> str:
    """A time as the page says one (its ``minutesText``)."""
    return "1 min" if m < 1.5 else f"{round(m)} min" if m < 75 else "an hour" if m < 100 else f"{m / 60:.1f} hours"


def carve_takes(run: Optional[dict]) -> Optional[str]:
    """What a carve takes at least, from its default check: the one wording, for the card and the Carve button (#157)."""
    secs = (run or {}).get("seconds")
    return f"at least about {_minutes(secs * CARVE_PER_CHECK / 60)} at this size" if secs else None


def _line(lead: str, cost: str, button: str, action: str, **kw) -> dict:
    """One offer: what to do, what it costs, and the button for it. Not a strength verdict: no study."""
    return {"text": f"{lead}: {cost[:1].lower()}{cost[1:]}", "lead": lead, "cost": cost, "button": button,
            "status": "info", "action": action, "better": True, **kw}


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
    """From the plate check on this version's run: for each panel the plate check governs, the thinnest sheet that still
    holds every load on it (or, failing, the thinnest that would), its number the plate check's own, never the FEA's.
    A panel with a load the FEA governs, or one not settled, is left out: its number at another thickness isn't known.
    Failing, only a panel that fails is offered (never more material on one that holds), and nothing at all if a load
    fails that the plate check doesn't govern: a thicker sheet may not fix that."""
    from . import verdicts
    from .answers import _times

    every = run.get("cases") or []
    judged = {id(c): verdicts.case(run, c)["kind"] for c in every}
    cases = [c for c in every if c.get("safety") is not None]
    need = run.get("min_safety") or 2
    if fails and any(judged[id(c)] == "fails" and c.get("governs") != "plate" for c in cases):
        return []
    panels: dict = {}
    for c in every:
        pl = c.get("plate") or {}
        if pl.get("done") and pl.get("piece"):
            panels.setdefault(pl["piece"], []).append(c)
    out = []
    for piece, on in panels.items():
        if any(c.get("governs") != "plate" or judged[id(c)] not in ("holds", "fails") for c in on):
            continue                                    # the FEA's, or not settled: its number elsewhere isn't known
        if fails and not any(judged[id(c)] == "fails" for c in on):
            continue                                    # it already holds: more material for nothing
        now = on[0]["plate"].get("thickness_mm")
        tables = [{round(b["thickness_mm"], 2): b for b in c["plate"].get("by_thickness") or []
                   if b.get("safety_across") is not None} for c in on]
        common = sorted(set.intersection(*(set(t) for t in tables))) if tables else []
        worst = {t: min(tb[t]["safety_across"] for tb in tables) for t in common}
        label = {t: tables[0][t]["label"] for t in common}
        label_now = next((label[t] for t in common if abs(t - now) < 0.01), f"{now:g} mm")
        ok = [t for t in common if verdicts.meets(worst[t], need)["counts_as_pass"]
              and (t > now + 0.01 if fails else t < now - 0.01)]
        if not ok:
            continue
        t = min(ok)
        said = f"Make the {piece} from {label[t]} instead of {label_now}"
        out.append(_line(said, f"{'That panel holds then' if fails else 'Still'}{',' if fails else ''} "
                               f"{_times(worst[t], about=True)} by the plate check.", "Try it", "use_t", say=said))
    return out


def _seen_from(run: dict) -> Optional[float]:
    """The wall the check can see at this size, in mm: on the run, or (a run from before it was kept) in its words."""
    import re

    if run.get("sees_mm"):
        return run["sees_mm"]
    m = re.search(r"(?:walls must be at least|sees walls from) ([\d.]+) mm", run.get("thin_said") or "")
    return float(m.group(1)) if m else None


def offers(store: DesignStore, state: dict, pid: str) -> list[dict]:
    """Make it better, for one part: card lines, cheapest real improvement first. [] where there's nothing to offer
    (a reference, nothing it must hold)."""
    from . import carve as K
    from . import consistency
    from . import load_study as L
    from . import verdicts
    from .answers import _times

    p = next((x for x in state.get("parts") or [] if x["id"] == pid), None)
    if p is None or p.get("role") == "fixed" or not p.get("loads") or not p.get("built"):
        return []
    blocked = p.get("blocked") if "blocked" in p else L.blocked(store, pid)
    run = L.default_check(store, pid)
    if blocked and blocked.get("why") == "already_fails":       # what would make it hold, never lighter
        # on a filled-in shape, or with the front edge not checked, "it holds then" isn't known
        known = run and not p.get("untrusted") and not consistency.bare_edge(store, pid)
        return [{**ln, "part": pid} for ln in _sheet_offers(run, fails=True)] if known else []
    if blocked and blocked.get("why") == "unchecked":           # everything else comes from the check
        return [_line("Check it holds first", "What would make it better comes from that.", "Check it holds", "load",
                      part=pid)]
    settled = _settled_check(store, p, run)
    results, invites = [], []
    if settled:
        results += _sheet_offers(run, fails=False)
    name = _printed_name(store, pid)
    takes = carve_takes(run) or ""
    if (blocked or {}).get("why") == "too_thin" and p.get("printed") and _seen_from(run):
        from .answers import _wall

        wall, where = _seen_from(run), ((run.get("thinnest_where") or {}).get("piece") or name)   # mm, as walls are said
        results.append(_line(f"Make the {where} walls {_wall(wall)} so the check can see them",
                             "It takes more filament. Then the check runs at a size it can trust.", "Try it", "use_t",
                             say=f"Make the walls of the {where} at least {wall:g} mm thick so the strength check can "
                                 f"see them"))
    if p.get("printed") and not p.get("carved") and (blocked or {}).get("carve"):
        waits = ("It waits for a check it can trust." if blocked["why"] == "too_thin"
                 else f"{blocked['carve'][:1].upper()}{blocked['carve'][1:]}.")
        invites.append(_line(f"Carve the {name} where it isn't working", (f"{takes[:1].upper()}{takes[1:]}. " if takes else "")
                             + waits, "Carve it", "carve", disabled=True))
    if p.get("printed") and not p.get("carved") and not (blocked or {}).get("carve"):
        mine = [r for r in state.get("carve_runs") or [] if r["part"] == pid and r.get("version") == p["version"]]
        done = next((r for r in mine if r.get("status") == "done"), None)
        if done is not None:
            best = next((st for st in done.get("stations") or [] if st["index"] == done.get("best")), None)  # search
            v = verdicts.carve_step(best, p.get("untrusted"), done) if best else None
            if settled and best and best.get("saved_g") and v and v["counts_as_pass"]:
                results.append(_line(
                    f"Carve the {name} where it isn't working",
                    f"{best['removed']:.0%} {K.share(done)} carved away, {best['saved_g']:,} g less filament, still "
                    f"{_times(best['safety'], about=True)}.", "Use it", "carve_use", run=done["id"],
                    station=best["index"]))
        elif not any(r.get("status") in (None, "running") for r in mine):
            invites.append(_line(f"Carve the {name} where it isn't working, to use less filament",
                                 f"It takes {takes or 'a while'}.", "Carve it", "carve"))
    # a printed part is carved: it has no Lighten panel, and the study refuses walls the carve can't see either
    if p.get("sheets") and not p.get("printed") and not (blocked or {}).get("lighten") and not p.get("framed"):
        mine = [r for r in state.get("lighten_runs") or [] if r["part"] == pid and r.get("version") == p["version"]]
        done = mine[0] if mine else None
        if done is not None:
            ok = [st for st in done.get("stations") or [] if st.get("saved_lb")
                  and verdicts.lighten_step(st, p.get("untrusted"), done)["counts_as_pass"]]
            best = max(ok, key=lambda st: st["saved_lb"], default=None)
            if settled and best:
                results.append(_line(
                    "Lighten it with holes where the wood isn't working",
                    f"{best['saved_lb']:g} lb lighter, still {_times(best['safety'], about=True)}.", "Use it",
                    "lighten_use", run=done["id"], station=best["index"]))
        else:
            invites.append(_line("Lighten it with holes where the wood isn't working", "It takes a few minutes.",
                                 "Lighten it", "lighten"))
    return [{**ln, "part": pid} for ln in results + invites]
