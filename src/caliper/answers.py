"""The four questions, answered in a line anyone can read (``specs/caliper-four-questions-spec.md``, step 1).

What is it? Will it work? What do I buy? How do I make it? Each card's top line is the answer: a verdict and
the one or two numbers that carry it, in the person's units, never an internal name. The numbers behind it
(today's panels) open beneath it in the app. A card with nothing to say yet says what to tell Caliper.

Every line comes from what's already measured: the part's description and size, its strength check and
rules, the scorecard, what it's built from and what that costs, how the shop makes it. A card never runs a
study to draw itself. A verdict from an older version says so.
"""

from __future__ import annotations

import math
import re
from typing import Optional

from . import construction as C
from . import verdicts
from .design import DesignStore

IN = 25.4
#: Card status, worst first: something fails, something isn't checked yet, all good, just information.
ORDER = ("bad", "warn", "ok", "info")
#: What a strength verdict promises and what it doesn't (CALI-59), said wherever one is shown.
PROMISE = ("A prediction, not a certificate: it rests on the loads it was given and on textbook strengths for "
           "the material. Real wood varies and so do joints, so test it gently before you trust it with a person.")
#: A chat reply that quotes a strength number points to the promise (CALI-88, #64 item 16).
PROMISE_POINTER = "That's a prediction, not a certificate: its card says what it rests on."


#: Wood, for what a promise says varies (a sheet or a stick of these).
WOODS = ("plywood", "lumber", "softwood", "hardwood", "mdf", "osb")


def promise(store: DesignStore, parts) -> str:
    """:data:`PROMISE`, worded for what the parts are made of (CALI-88, #64 item 14): wood, a print, both, or any
    other material. An all-printed box's began "Real wood varies"."""
    made = set()
    for pid in parts:
        try:
            items = C.declared(store, pid).get("construction") or []
        except Exception:  # noqa: BLE001 — a part whose script won't say: the general words, never a wrong one
            items = []
        for it in items:
            if not isinstance(it, dict):
                continue
            made.add("printed" if it.get("kind") == "printed" else "wood" if it.get("material") in WOODS else "other")
    if made == {"wood"} or not made:
        return PROMISE
    wood, printed, other = "wood" in made, "printed" in made, "other" in made
    # what it rests on; "rough" is said where a verdict is (a line's own ``rough``), not here: a mixed part whose
    # plywood governs isn't rough (CALI-97)
    rests = []
    if wood or other:
        rests.append("textbook strengths for the " + ("materials" if wood and other else "wood" if wood else "material"))
    if printed:
        rests.append("a model of the print")
    if wood:
        also = (["prints"] if printed else []) + (["the other materials"] if other else []) + ["joints"]
        varies = "Real wood varies, and so do " + (", ".join(also[:-1]) + " and " + also[-1] if len(also) > 1 else also[0])
    elif printed and not other:
        varies = "Printers, infill and the bond between a print's layers vary"
    elif printed:
        varies = "Prints, materials and joints vary"
    else:
        varies = "The material and its joints vary"
    return (f"A prediction, not a certificate: it rests on the loads it was given and on {' and '.join(rests)}. "
            f"{varies}, so test it gently before you trust it with a person.")


def _len(mm: float, inches: bool) -> str:
    return f"{mm / IN:.1f} in".replace(".0 in", " in") if inches else f"{mm:.0f} mm"


#: Within this share of its limit, either way, a safety is said to two places (CALI-88, #64 item 1).
NEAR_LIMIT = 1.1


def _times(x: float, about: bool = False, need: Optional[float] = None) -> str:
    """3.1 -> "3.1 times over"; the kid's reading of a safety factor. ``about``: the printed model's rough number
    (CALI-97), "about 3.1 times over"; 10.0 or more is "more than 10 times over" either way, never "about more than"
    (#144 review). ``need``: the limit it's judged against. Within 10% of it either way, it's said to two places,
    cut, so a fail never reads as its limit (rule 6: 1.96 against 2 read "only 2 times over, and it needs 2"); a
    fail further under is cut to one place. Nothing under 10 rounds up to "more than 10" (CALI-88, #64 item 1)."""
    if x >= 10:
        return "more than 10 times over"
    return ("about " if about else "") + f"{safety_num(x, need)} times over"


def safety_num(x: float, need: Optional[float] = None) -> str:
    """A safety factor's number, as every reader says it (#208 review: one formatter, server and page; the page's
    ``safetyNum`` is the same rule): within 10% of ``need`` either way, two places, cut; a fail further under, one
    place, cut (1.67 is 1.6, not 1.7); else one place, rounded, but never up to 10. So no reader rounds a fail up
    to its limit: 1.995 against 2 is 1.99, 0.999 against 1 is 0.99."""
    if need is not None and need / NEAR_LIMIT < x < need * NEAR_LIMIT:
        n = math.floor(x * 100 + 1e-9) / 100           # near the line: the places that tell it from the line
    elif need is not None and x < need:
        n = math.floor(x * 10 + 1e-9) / 10             # a fail well under: one place, cut
    else:
        n = math.floor(x * 10 + 0.5) / 10                 # half up, as the page's Math.floor: the same float ops
        if n >= 10 and x < 10:
            n = math.floor(x * 10) / 10
    return f"{n:g}"


def over(c: dict, need: Optional[float] = None, about: bool = False) -> str:
    """A case's safety as every reader says it (CALI-88, #64 item 9): "3.1 times over", against the load with its
    factor, and, where the factor isn't 1, what that is: "3.1 times over 400 lb (200 lb, twice over)". So a reader
    who multiplies 3.1 by Dad's 200 lb isn't misled: the card, the kid's book, the trial panel and the build book
    quote the same number against the same thing. (Against the load itself, 6.2 here, is the owner's to switch to.)"""
    return _times(c["safety"], about, need) + against(c)


def against(c: dict, also: str = "") -> str:
    """What "N times over" is against, where a case's factor isn't 1: " 400 lb (200 lb, twice over)", with ``also``
    inside the brackets ("; it needs 2, assumed"). The design card says it as the part card does (#208 review)."""
    lb, factor = c.get("lb"), c.get("factor") or 1.0
    if not lb or factor == 1:
        return f" ({also.lstrip('; ')})" if also else ""
    return f" {lb * factor:,.0f} lb ({lb:g} lb, {'twice' if factor == 2 else f'{factor:g} times'} over{also})"


def _sentence(text: str, most: int = 120) -> str:
    """The first sentence, ending in a full stop, for a top line: a description can be a paragraph of build
    instructions."""
    first = (text or "").strip().split(". ")[0].rstrip(".")
    if len(first) <= most:
        return first + "."
    # cut where a phrase ends ("…, built from five panels (two sides, …" -> "…, built from five panels…")
    for sep in (" (", " — ", "; ", ", "):                   # an aside first, then a clause
        cut = first.rfind(sep, 0, most - 1)
        if cut > most // 2:
            return first[:cut].rstrip(",;") + "…"
    return first[:most - 1].rsplit(" ", 1)[0].rstrip(",;") + "…"


def part_name(p: dict) -> str:
    """The name a person reads for a part in a sentence: its label, or its id in words (#94)."""
    return p.get("label") or p["id"].replace("_", " ")


def _worst(lines: list[dict]) -> str:
    return min((ln["status"] for ln in lines), key=ORDER.index, default="info")


def _carve_offer(store: DesignStore, state: dict, p: dict, mk: dict) -> Optional[dict]:
    """A printed part, on a design whose objective is its print time or its weight, with a carve to try (#89 item 6:
    165 h of printing "as fast as possible", and nothing offered the carve): one line that offers it. Not on a part
    already carved, nor one with nothing it must hold (a carve keeps what it holds), nor where the Carve button refuses
    it (#144 review: ``load_study.blocked``, the one test both read: it already fails, or its walls are too thin)."""
    from . import load_study as L

    if not mk.get("printed") or not p.get("loads") or p.get("carved"):
        return None
    aims = [o.get("metric") or "" for o in (state.get("goals") or {}).get("objectives") or []]
    if not any(m.startswith(("print.", "weight.")) for m in aims):
        return None
    stop = L.blocked(store, p["id"])
    if stop and stop["why"] != "unchecked":
        return None
    try:
        name = next((it.get("name") for it in C.declared(store, p["id"]).get("construction") or []
                     if isinstance(it, dict) and it.get("kind") == "printed"), None)
    except Exception:  # noqa: BLE001 — the offer is said with the part's own name
        name = None
    what = {pc["key"]: pc["name"] for pc in p.get("pieces") or []}.get(name, name) or part_name(p)    # as renamed (#94)
    if stop:                                     # no check of this version: the button says the same (#144)
        return _line(f"Check it holds first, then carve the {what} where it isn't working, to print less of it.",
                     "info", action="load")
    return _line(f"Carve the {what} where it isn't working, to print less of it: try Carve it.", "info",
                 action="carve")


def _strays(meta: dict, inches: bool) -> str:
    """What the mesh left out, its height in the design's units (#89, #137 P2 item 11: "at z 14.0–15.6 mm" on an inch
    design); measure's own words where it didn't say where."""
    n, z = meta.get("strays_n"), meta.get("strays_z")
    if not n or not z:
        return meta["strays"]
    lo, hi = _len(z[0], inches), _len(z[1], inches)
    return (f"left out {n} stray face{'s' if n != 1 else ''} from the CAD's meshing (at z {lo}"
            + (f"–{hi}" if hi != lo else "") + ")")


def _wall(mm: float, inches: bool = False) -> str:
    """A wall's thickness, or a voxel's size: in mm, whatever the design's units (#139 review: walls in mm everywhere,
    heights and positions in the design's), two places under 1 mm (0.25 mm, #137 item 2)."""
    return (f"{mm:.2f}".rstrip("0").rstrip(".") if mm < 1 else
            f"{mm:.1f}".removesuffix(".0") if mm < 10 else f"{mm:.0f}") + " mm"


def _small_len(mm: float, inches: bool) -> str:
    """A small length in inches to the nearest 1/32 (5/32 in), and in mm where that would round to nothing, never
    "0 in" (CALI-97, #100 item 5): what the chat says beside a number in mm."""
    from math import gcd

    if inches and mm >= IN:
        return _len(mm, True)
    n = round(mm / IN * 32)
    if inches and n >= 1:
        g = gcd(n, 32)
        return f"{n // g}/{32 // g} in"
    # under 1 mm, two places: a 0.25 mm wall is that, not "0.2" here and "0.3" on the page (#137 item 2)
    return (f"{mm:.2f}".rstrip("0").rstrip(".") if mm < 1 else
            f"{mm:.1f}".removesuffix(".0") if mm < 10 else f"{mm:.0f}") + " mm"


def fail_hedge(run: dict, c: dict, v: dict, inches: bool) -> str:
    """What a ✗ adds about where it fails and how sure (#137 item 2), the same words on the part card and the design
    card (#139 review: the design card named the 0.25 mm webs, the part card the 5.2 mm wall at the peak). "" when
    there's nothing to add. Where the hand buckling check decides it, the wall that folds, never the FEA's peak (#235 review)."""
    if c.get("governs") == "buckling":
        rows = [r for r in c.get("buckling") or [] if r.get("done")]
        if rows:
            wall = min(rows, key=lambda r: r["safety"])["piece"]
            return (f" The {wall} folds first: it's too slender for the load running down it (a hand buckling check, "
                    f"its edges and stiffness taken on the safe side, and the whole load on it).")
    where, thin_here = worst_at(run, c, inches)
    wall = _wall(c["fea"]["wall_mm"], inches) if where else ""
    if v.get("coarse") and thin_here:                # among walls the voxels can't see: the fail may be the model's
        return (f" Its worst stress, in one run at {_wall(run['spacing_mm'])} voxels, is {where}, where its wall is "
                f"{wall}, too thin for the voxels to see: the fail may be the model's. "
                + ("Check it again finer." if run.get("finer") else
                   "A hand check or a printed test piece is the way to know."))
    if where:                                        # the voxels see the wall where it's worst
        return (f" Its worst stress is {where}."
                + (f" Separately, its thinnest walls, {_wall(run['thinnest_mm'])}{_thin_at(run, inches)}, are too "
                   f"thin for the voxels to see." if v.get("coarse") else ""))  # said apart, not as its cause
    if v.get("coarse"):                              # an older run: where isn't known (CALI-97's words)
        return " " + coarse(run, inches, holds=False)
    return ""


def _grain_lines(store: DesignStore, pid: str, run: dict, stale: bool, filled: Optional[str] = None,
                 edge: bool = False) -> list[dict]:
    """A beam's face grain (CALI-126): the advice where the person hasn't said which way it's cut (a grain the designer
    wrote is only assumed: it never moves the verdict), and "check it again" where they have and the check predates
    it. Never a greener number from a grain nobody said, and the advice's number only from a case whose own verdict
    is settled (it holds or fails): never one checked in the middle only, too coarse, on a block or an older version."""
    from . import grain as G

    said, out, seen = G.stated(store, pid), [], set()
    for c in run.get("cases") or []:
        pl = c.get("plate") or {}
        piece = pl.get("piece")
        if pl.get("as") != "beam" or not pl.get("done") or piece in seen:
            continue
        if c.get("safety") is None or verdicts.case(run, c, filled=filled, stale=stale, edge=edge)["kind"] not in (
                verdicts.SETTLED):
            continue
        seen.add(piece)
        mine = said.get(piece)
        if mine and pl.get("grain") != mine["grain"]:
            out.append(_line(f"You said: {G.line(piece, mine)[0].lower()}{G.line(piece, mine)[1:]} Check it holds "
                             f"again to use it.", "warn", study="load"))
        elif not mine and not stale and pl.get("safety") is not None and pl.get("safety_across") is not None \
                and pl["safety"] > pl["safety_across"]:
            way = G.phrase(G.runs(pl.get("span_axis"), "along"), "along")      # the one phrase (#151 review)
            out.append(_line(f"Cut the {piece} with its {way} and it's about {_times(pl['safety'])}, not "
                             f"{_times(pl['safety_across'])}: keep that under Will it hold? and it goes on the cut "
                             f"list.", "info", study="load"))
    return out


def _case_line(pid: str, run: dict, c: dict, filled: Optional[str], stale: bool, inches: bool,
               edge: bool = False) -> dict:
    """The part card's line for one load case: its words from its one verdict (CALI-112)."""
    from . import load_study as L

    older = " (Checked on an older version: check again.)" if stale else ""
    v = verdicts.case(run, c, filled=filled, stale=stale, edge=edge)   # an older run's ✓ is "older version" (#132)
    if v["kind"] == "untrusted":                     # ran on a block: no ✓ from it (CALI-96); this wins
        return _line(untrusted(pid, filled) if filled else (f"Not trusted yet: the last strength check ran on a filled-in shape"   # the number: the panel, badged
                     f"{', on an older version' if stale else ''}. Check it again."), "warn", study="load")   # the run's own record, the part since changed
    if v["kind"] == "unchecked" and (c.get("fea") or {}).get("supported") is False:     # couldn't run (#138 item 3)
        return _line(f"{c['name'][:1].upper() + c['name'][1:]}: not checked: {v['why']}. Check where it's held and "
                     f"pushed, then check it again." + older, v["status"], study="load")
    if v["kind"] in ("unresolved", "unchecked"):     # an FEA that can't see the wall is no ✓ (CALI-97)
        if v.get("why"):                             # which check holds, and what couldn't be seen, said once (#244, #248)
            return _line(f"{c['name'][:1].upper() + c['name'][1:]}: {unseen_said(run, v)}" + older, "warn", study="load")
        return _line(coarse(run, inches) + older, "warn", study="load")
    if v["kind"] == "span":                          # the FEA alone, between its holds: no ✓ and no number (CALI-153)
        return _line(f"{c['name'][:1].upper() + c['name'][1:]}: not settled: {v['why']}." + older, "warn", study="load")
    if v["kind"] == "edge":                          # the middle only: no ✓ for where people stand (CALI-94)
        from .consistency import MIDDLE_ONLY

        # never "holds" for it (#132's guard): the case, then what was and wasn't checked
        return _line(f"{c['name'][:1].upper() + c['name'][1:]}: {MIDDLE_ONLY}." + older, "warn", study="load")
    # a verdict on the printed model says so in a word, and why one click down by the promise (CALI-86)
    rough, need = L.rough(run, c), run.get("min_safety")
    if v["kind"] == "holds":
        text = f"Holds {c['name'].lower()}, {over(c, need, rough)}."
    elif v["kind"] == "close":                       # amber: it holds, near the line (CALI-88, #64 item 2)
        text = f"Holds {c['name'].lower()}, {over(c, need, rough)}: close to the {need:g} it needs."
    elif v["kind"] == "fails":
        text = f"Doesn't hold {c['name'].lower()}: only {over(c, need, rough)}, and it needs {run['min_safety']:g}."
        if filled:                                   # a ✗ stays a ✗: the block failed, the part is weaker
            text += filled_fail(filled)
        else:                                        # where it fails first, and how sure (#137 item 2)
            text += fail_hedge(run, c, v, inches)
        pl = c.get("plate") or {}
        if pl.get("done") and c.get("governs") != "plate" and pl.get("safety_across") is not None:
            # a second opinion by hand on the panel it lands on (#137 item 7: the seat on its ring)
            how = (f", as a round plate held at its ring's outer edge ({_len(pl['ring_mm'], inches)} across)"
                   if pl.get("support") == "ring" else "")
            text += f" By hand, the {pl['piece']} on its own{how}: {_times(pl['safety_across'], need=need)}."
    elif v["kind"] == "recheck":                     # its reason, not "older version" (#214 review)
        text = f"{c['name'][:1].upper() + c['name'][1:]}: check it again, {over(c, need, rough)}: {v['why']}."
    else:                                            # any other kind: its word, never a ✓ (CALI-112)
        text = f"{c['name'][:1].upper() + c['name'][1:]}: {v['word']}, {_times(c['safety'], rough, need)}."
    return _line(text + older, v["status"], study="load", **({"close": True} if v["kind"] == "close" else {}),
                 **({"rough": L.ROUGH} if rough else {}))


def _rules_line(rules: list[dict]) -> dict:
    """A part's own rules in a line: "all pass" only when every rule ran and passed (#132 review); an error is a
    fail, and a rule that waits (deferred) is said, never counted."""
    bad = [r for r in rules if r["status"] in ("fail", "error")]
    waits = [r for r in rules if r["status"] not in ("pass", "fail", "error")]
    return _line(f"{len(bad)} of its rules fail: {', '.join(r['id'] for r in bad[:3])}." if bad else
                 f"{len(rules) - len(waits)} of its {len(rules)} rules pass; {len(waits)} not checked yet: "
                 f"{', '.join(r['id'] for r in waits[:3])}." if waits else
                 f"Its {len(rules)} rule{'s' if len(rules) != 1 else ''} all pass.",
                 "bad" if bad else "warn" if waits else "ok")


def _why_not(rel: dict) -> str:
    """Why a build package isn't ready, in its own words (CALI-96: not trusted; CALI-110: not resolved)."""
    return verdicts.summary((rel.get("card") or {}).get("summary"))["why"] or "a check isn't settled"


def _thin_at(run: dict, inches: bool) -> str:
    """Where a run's thinnest wall is, as it recorded it (#136): " around z 16.1 in", " in the seat top", or ""."""
    w = run.get("thinnest_where") or {}
    return (f" in the {w['piece']}" if w.get("piece") else
            f" around z {_len(w['at'][2], inches)}" if w.get("at") else "")


def worst_at(run: dict, c: dict, inches: bool) -> tuple[str, Optional[bool]]:
    """Where a case's worst stress is in its run ("in the cone around z 15.3 in"), and whether the wall there is too
    thin for its voxels (None where the run didn't record it: older runs, whose ``in`` named the nearest wood even for
    a printed part, #137 item 2)."""
    from . import load_study as L

    fea = c.get("fea") or {}
    if "wall_mm" not in fea or not fea.get("at"):
        return "", None
    where = (f"in the {fea['in']} " if fea.get("in") else "") + f"around z {_len(fea['at'][2], inches)}"
    s = run.get("spacing_mm")
    return where, (not L._sees(fea["wall_mm"] / s)) if s else None


def unseen_said(run: dict, v: dict) -> str:
    """A pass that rests on another check while the FEA couldn't see a wall (#244): "not checked: the seat's plate check holds
    3.3 times over; the printed walls are too thin to check at this size (…). A hand check or …", each said once (#248)."""
    return (f"not checked: {v['why']}. " + ("Check it again finer." if run.get("finer") else
                                             "A hand check or a printed test piece is the way to know."))


def coarse(run: dict, inches: bool = True, holds: bool = True) -> str:
    """What a verdict says when the FEA that governs it couldn't see the wall it's checking (CALI-97). A ✓ is no
    verdict then: not resolved yet (a finer run can see it) or not checked (none a study may make can). A ✗ stays a
    ✗, and says the fail may be the model's."""
    from . import load_study as L

    if any(L.blind(run, c) for c in run.get("cases") or []):    # not its walls: it saw no stress at all (#202)
        return L.BLIND
    walls = f"thinnest walls, {_wall(run.get('thinnest_mm') or 0)}{_thin_at(run, inches)}"   # which, and where (#139)
    if not holds:
        return (f"The fail may be the model's: the voxels can't see its {walls}. "
                + ("Check it again finer." if run.get("finer") else
                   "A hand check or a printed test piece is the way to know."))
    if run.get("finer"):
        return f"Not resolved yet: the check was too coarse to see its {walls}. Check it again finer."
    return L.NOT_CHECKED
def filled_fail(why: Optional[str]) -> str:
    """What a ✗ adds when its check didn't run on the part as built (#89, #100's merge checks): on a filled-in shape,
    the part as built is *likely* weaker (taking material away can, rarely, lower a peak); where its shape couldn't
    be checked against its pieces, that is said, not "a filled-in shape", which isn't known."""
    if (why or "").startswith(("couldn't", "Not trusted yet: I couldn't")):     # filled()'s, or untrusted()'s
        return " Its shape couldn't be checked against its pieces, so this number may not be the part's."
    # both causes, as the volume check says them (#64 item 12, #209 review): with a piece missing from construction()
    # the solid may be the part as built
    return (" It ran on a solid with more in it than its pieces: filled in, the part as built is likely weaker; or a "
            "piece is missing from its construction.")


def untrusted(pid: str, why: str = "") -> str:
    """What a strength verdict on a filled-in solid says instead of holding (CALI-96), or one whose shape couldn't
    be checked against its pieces at all (which fails closed: never holding)."""
    if why.startswith("couldn't"):
        return f"Not trusted yet: I {why}, so I can't say the strength check ran on the part as built. Check it again."
    from .consistency import PANEL_SAID

    if PANEL_SAID in why:                            # the shape's right, the pieces aren't (CALI-155): not "fix its shape"
        return f"Not trusted yet: {why}. Say \"{fix_piece(pid)}\"."
    return (f"Not trusted yet: the strength check ran on a solid with more in it than the {pid.replace('_', ' ')}'s "
            f"pieces: its shape is filled in, or a piece is missing from its construction. Say \"{fix_shape(pid)}\" or "
            f"\"{fix_piece(pid)}\".")


#: The two fixes for a solid with more in it than its pieces (#209 review): the shape, or the construction.
def consistency_no_make() -> str:
    from .consistency import NO_MAKE

    return NO_MAKE


def fix_shape(pid: str) -> str:
    """The words to say to fix a part's shape, naming the part, so they reach it with nothing selected (#209 review:
    "add the missing piece" typed from the design card authored a part named missing_piece)."""
    return f"fix the shape of the {pid.replace('_', ' ')} to match its pieces"


def fix_piece(pid: str) -> str:
    return f"add the missing piece to the {pid.replace('_', ' ')}"


def fix_for(check_id: str, detail: str, pid: str = "part") -> str:
    """What to say to fix a shape that doesn't match its pieces: both fixes where the volume check can't tell which
    it is (#209 review), the outline's own where a sheet is off its face, else the shape."""
    from . import consistency

    if check_id == "construction_on_its_face":
        return f'Say "{consistency.remedy(detail)}"'
    if consistency.PANEL_SAID in detail:             # the solid has a panel its pieces left out: fixing "the shape" would delete it (CALI-155)
        return f'Say "{fix_piece(pid)}"'
    if check_id == "construction_volume":
        return f'Say "{fix_shape(pid)}" (it\'s filled in) or "{fix_piece(pid)}" (one isn\'t in its construction)'
    return f'Say "{fix_shape(pid)}"'


def rests_on_model(metric: str) -> bool:
    """Whether a scorecard check's number comes from a strength or frame model (and so carries the promise): not a
    weight, a cost, or whether the pieces fit a sheet (CALI-86)."""
    m = metric or ""
    return m.startswith(("strength.", "frame.")) or m.endswith("safety") or "yield" in m


def _card(key: str, q: str, lines: list[dict], hint: str = "", promised: str = PROMISE) -> dict:
    card = {"key": key, "q": q, "status": _worst(lines) if lines else "info", "lines": lines, "hint": hint}
    # any verdict resting on a model (a strength or frame study, or the scorecard's checks) says what it promises
    # (a close pass is amber, and a verdict all the same: #208 review)
    if any((ln.get("study") in ("load", "frame") or ln.get("model")) and (ln["status"] in ("ok", "bad") or ln.get("close"))
           for ln in lines):
        card["promise"] = promised + "".join(f" {r}" for r in dict.fromkeys(ln["rough"] for ln in lines if ln.get("rough")))
    return card


def _line(text: str, status: str = "info", **kw) -> dict:
    # a verdict with nothing to go on (its status "unknown") reads as a warning on a card: a tipping case with no weight crashed the card (CALI-155)
    return {"text": text, "status": "warn" if status == "unknown" else status, **kw}


# ---------------------------------------------------------------------------
# One part
# ---------------------------------------------------------------------------
def part(store: DesignStore, state: dict, pid: str) -> list[dict]:
    from . import load_study, making

    p = next(x for x in state["parts"] if x["id"] == pid)
    inches = state.get("display_units", "in") == "in"
    report = None
    if p.get("built"):
        try:
            report = C.report(store, pid)
        except Exception:  # noqa: BLE001 — the card says what it can without it
            report = None
    # how it's made, asked once: its printed filament is the one figure the card gives (#70 item 23)
    mk = None
    if report and not report.get("not_accounted") and p.get("role") != "fixed":
        try:
            mk = making.plan(store, pid, wait=False)       # the slicer never holds a card (#97)
        except Exception:  # noqa: BLE001
            mk = None
        report = making.filament(report, mk)

    # What is it?
    what = [_line(_sentence(p.get("intent") or pid))]
    if p.get("bbox"):
        x, y, z = p["bbox"]["size"]
        a, b = max(x, y), min(x, y)
        bom = (report or {}).get("bom") or {}
        made = ", ".join(dict.fromkeys(g["label"] for g in bom.get("sheets", []) + bom.get("sticks", [])
                                       + bom.get("printed", []))) if report else ""
        what.append(_line(f"{_len(a, inches)[:-3]} × {_len(b, inches)}, {_len(z, inches)} tall"
                          + (f", from {made}" if made else "") + "."))
    else:
        what.append(_line("It won't build right now: say what's wrong with it, or roll it back.", "bad"))
    if report:
        # its shape and its pieces disagree (CALI-83: a stool built as a filled box): every study reads one or the other
        try:
            from . import consistency

            geom = store.part_geometry(pid)                  # cached by the assembly (path, mtime)
            said = consistency.checked(store, pid)
            smaller = consistency.plan_differs(C.declared(store, pid), geom)
            off = sorted((r for r in said if r.status == "fail" and r.detail), key=lambda r: r.id != "construction_volume")
            edge = next((r.detail for r in said if r.id == "loads_edge" and r.detail), "")   # (CALI-94)
            meta = geom.require_mesh().metadata
            strays = _strays(meta, inches) if meta.get("strays") else None
        except Exception:  # noqa: BLE001 — the card says what it can
            off, strays, edge, smaller = [], None, "", []
        if strays:                                   # what the mesh left out, said once (CALI-118)
            what.append(_line(f"I {strays}: it enclosed nothing and weighs nothing.", "info"))
        if off:
            detail = report.get("not_accounted") or off[0].detail
            what.append(_line(f"Its 3D shape and its pieces don't match: {detail}. {fix_for(off[0].id, off[0].detail, pid)} "
                              f"and I'll revise it.", "bad"))
        for s in smaller:                      # cut smaller than it's drawn: the cut list follows the outline (#183)
            what.append(_line(consistency.plan_said(s, inches), "warn"))
        if edge:                               # a load case it's missing: a warning, the round passed (CALI-94)
            what.append(_line(edge[0].upper() + edge[1:] + ".", "warn", study="load"))

    # Will it work?
    work = []
    if p.get("role") == "fixed":
        work.append(_line("It's a reference (like the car): nothing to check."))
    work += _broken(p)                                     # a rule of its own it breaks, first (#137 item 1)
    runs = [r for r in state.get("load_runs") or [] if r["part"] == pid]
    if runs:
        run, stale = runs[0], runs[0].get("version") != p["version"]
        from . import consistency
        from . import load_study as L

        filled = consistency.filled(store, pid)              # the check ran on a block, not the part (CALI-96)
        edge = consistency.bare_edge(store, pid)             # where people stand wasn't loaded (CALI-94)
        for c in run["cases"]:
            if L.blind(run, c):                 # named, beside any that did read: one reason (#202)
                work.append(_line(f"! {c['name'][:1].upper()}{c['name'][1:]}: {L.BLIND}", "warn", study="load"))
            elif c.get("safety") is not None:
                work.append(_case_line(part_name(p), run, c, filled, stale, inches, edge=bool(edge)))
        work += _grain_lines(store, pid, run, stale, filled, bool(edge))
    elif p.get("loads"):
        failed = next((h for h in reversed(p.get("history") or []) if h.get("kind") == "load"
                       and h.get("action") == "failed" and h.get("version") == p["version"]), None)
        work.append(_line(f"I couldn't check it holds: {failed['why']}." if failed else
                          "Not checked yet: check it when it looks right.", "warn", study="load"))
    elif p.get("built") and p.get("role") != "fixed" and not p.get("framed"):
        work.append(_line("Not checked yet: say what it has to hold (\"it has to hold me, 200 lb\").", "warn",
                          study="load"))
    if p.get("loads") and p.get("role") != "fixed":
        from . import trials

        tried = trials.summary(store, pid, inches)            # what the real one did (CALI-80)
        if tried:
            if tried["status"] in ("bad", "warn"):
                # a test that went against the prediction outranks it: no ✓ left above a failed test (CALI-86)
                work = [ln for ln in work if not (ln.get("study") == "load" and ln["status"] == "ok")]
            work.append(_line(tried["text"], tried["status"], study="trial"))
    if p.get("loads") and p.get("role") != "fixed" and p.get("built"):
        from . import tipping

        try:                                    # will it tip over? statics (CALI-98)
            cases = tipping.check(store, pid)
            for case in cases:
                text, status = tipping.line(case)
                work.append(_line(text, status, study="tip"))
            # a way it could tip that nothing pushes, where its base is no wider: said, not passed over (#141 review)
            ways = tipping.undeclared_ways(store, pid) if cases else []
            if ways:
                work.append(_line(f"Not checked yet: {' or '.join(ways)} (no push is declared that way, and its base "
                                  f"is no wider that way).", "warn", study="tip"))
            missing = tipping.unchecked(C.declared(store, pid), p.get("intent") or "")
        except Exception as e:  # noqa: BLE001 — said, never a crash of the card
            work.append(_line(f"Tipping: not checked ({e}).", "warn", study="tip"))
            missing = []
        if missing:                             # a seat's cases nobody checked, said (#86 item 3)
            work.append(_line("Not checked yet for a seat: " + "; ".join(missing) + ".", "warn", study="tip"))
    frames = [r for r in state.get("frame_runs") or [] if r["part"] == pid]
    if frames:
        d = frames[0].get("drawn") or {}
        if d.get("safety") is not None:
            # an older frame run (or one from before it recorded its version) isn't the frame as it is (#132 review)
            v = verdicts.meets(d["safety"], frames[0].get("min_safety"),
                               stale=frames[0].get("version") != p["version"],
                               recheck=verdicts.old_on_limit(frames[0], d["safety"], frames[0].get("min_safety")))   # (#214)
            work.append(_line(f"The frame holds, {_times(d['safety'], need=frames[0].get('min_safety'))}"
                              + (f": close to the {frames[0].get('min_safety'):g} it needs." if v["kind"] == "close" else ".")
                              if v["kind"] in ("holds", "close") else
                              f"The frame read {_times(d['safety'], need=frames[0].get('min_safety'))} on an older version: check it again." if v["kind"] == "stale" else
                              f"The frame read {_times(d['safety'], need=frames[0].get('min_safety'))}: check it again, {v['why']}." if v["kind"] == "recheck" else
                              f"The frame is too weak as drawn: {_times(d['safety'], need=frames[0].get('min_safety'))}, it needs "
                              f"{frames[0].get('min_safety')}.", v["status"], study="frame"))
    mine = {r["id"] for r in p.get("rules") or []}
    rules = [r for r in (state.get("report") or {}).get("results", []) if r.get("id") in mine]
    if len([x for x in state["parts"] if x.get("role") != "fixed"]) == 1 and p.get("role") != "fixed":
        # the only part: what the design is held to is what it's held to (the strength lines say it already)
        work += [ln for ln in held_to(state, measured(store, state)) if ln.get("study") != "load"]
    if rules:
        work.append(_rules_line(rules))

    # What do I buy?
    buy = []
    from .consistency import NO_MAKE

    wrong = (report or {}).get("not_accounted")          # pieces that aren't the part: nothing from them (CALI-155)
    if wrong:
        buy.append(_line(f"{NO_MAKE[:1].upper()}{NO_MAKE[1:]}.", "warn"))
    elif report:
        b = report["bom"]
        items = [f"{g['count']} sheet{'s' if g['count'] != 1 else ''} of {g['label']}" for g in b["sheets"]]
        items += [f"{g['count']} × {g['label']}" for g in b["sticks"]]
        if b.get("fasteners"):
            items.append(f"{b['fasteners']['screws']} screws and wood glue")
        items += [f"{g['filament_g']:.0f} g of {g['label'].split(' ')[0]} filament ({g['filament_from']})"
                  for g in b.get("printed") or []]
        items += [g["label"].split(" (")[0].lower() for g in b["coverings"]]
        usd = _cost(store, pid, report)
        buy.append(_line(", ".join(items[:5]) + (f": about ${usd:,.0f}." if usd else ".")))
        lb = report["mass_lb"]
        if lb is None:                                   # unknown, never the rest's weight (#125 review)
            buy.append(_line(f"Its weight isn't known: {report.get('unweighed') or C.UNWEIGHED}.", "warn"))
        else:
            buy.append(_line(f"It weighs {lb:g} lb" + (", easy for a kid to carry." if lb <= 10 else ".")))
    elif p.get("role") != "fixed":
        buy.append(_line("Not known yet: it doesn't say what it's built from. Ask for it from plywood, lumber "
                         "or tube and the designer lists the pieces.", "warn"))

    # How do I make it?
    how = []
    if wrong:
        how.append(_line(f"No patterns or cut list yet: {NO_MAKE}. {fix_for('construction_covers', wrong, pid)} and I'll revise it.", "warn"))
    elif report and p.get("role") != "fixed":
        if mk:
            tools = [t for t in mk["by_how"] if t != "printer"]
            n = sum(len(v) for k, v in mk["by_how"].items() if k != "printer")
            holes = sum(x.get("holes", 0) for x in mk["pieces"])
            if tools:
                how.append(_line(f"With {_and(['your ' + t for t in tools])}: {n} piece{'s' if n != 1 else ''}"
                                 + (f", {holes} hole{'s' if holes != 1 else ''}" if holes else "") + ".", "ok"))
            for pr in mk["printed"]:
                n = f"{pr['pieces']} piece{'s' if pr['pieces'] != 1 else ''}"
                how.append(_line(f"Print it in {pr['material'].upper()}: {n}; print time: working it out…", "info",
                                 working=True) if pr.get("pending") else       # the slicer's still at it (#97)
                           _line(f"Print it in {pr['material'].upper()}: {n}; print time: the slicer couldn't work it "
                                 f"out: {_why(pr)}.", "warn") if pr.get("hours") is None else
                           _line(f"Print it in {pr['material'].upper()}: {n}, about {pr['hours']:g} h"
                                 + (f" ({pr['rough_said']})" if pr.get("rough_said") else "") + "."
                                 + (f" It's {pr['mirror_said']}." if pr.get("mirror_said") else ""),
                                 "warn" if pr.get("rough_said") else "ok"))        # a guess is never green (rule 6)
            why: dict = {}
            for x in mk["missing"]:
                why.setdefault(x["why"], []).append(x["name"])
            for reason, names in why.items():
                listed = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
                how.append(_line(f"Your shop can't make {'the ' + listed if len(names) == 1 else listed}: {reason}.",
                                 "bad"))
            if mk["shop_default"]:
                how.append(_line("Planned for a jigsaw, a drill and a circular saw: say what's in your shop.", "info"))
            offer = _carve_offer(store, state, p, mk)
            if offer:
                how.append(offer)
        pats = [r for r in state.get("pattern_runs") or [] if r["part"] == pid]
        if any(x["kind"] == "sheet" for x in (mk or {}).get("pieces", [])):        # patterns are for flat pieces
            if pats and pats[0].get("version") == p["version"]:
                url = f"/api/designs/{state['slug']}/patterns/{pats[0]['id']}/"
                how.append(_line(f"Patterns ready: {pats[0]['pages']} pages to print full size, or project and trace.",
                                 "ok", action="patterns",
                                 links=[{"label": "Print full size", "url": url + "print-full-size.pdf"},
                                        {"label": "Measure and mark", "url": url + "measure-and-mark.pdf"},
                                        {"label": "Project", "url": url + "index.html"}]))
            else:
                how.append(_line("Make the patterns to print or project.", "info", action="patterns"))
    elif p.get("role") != "fixed":
        how.append(_line("Not known yet: it doesn't say what it's built from.", "warn"))
    from . import better

    work += better.offers(store, state, pid)        # Make it better, where the person looks (#92)
    from . import tree

    for ln in what + work + buy + how:                 # what the person renamed a piece to (#185)
        if isinstance(ln, dict) and ln.get("text"):
            ln["text"] = tree.relabelled(store, pid, ln["text"])
    return [_card("what", "What is it?", what),
            _card("work", "Will it work?", work, "Say what it must do and I'll check it.", promise(store, [pid])),
            _card("buy", "What do I buy?", buy),
            _card("make", "How do I make it?", how, "Say what it's built from and I'll plan the making.")]


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _cost(store: DesignStore, pid: str, report: dict) -> Optional[float]:
    from . import cutplan, scorecard

    try:
        report = {**report, "pieces_raw": C.takeoff(C._items(C.declared(store, pid)))}
        plans = cutplan.list_runs(store, pid)
        plan = plans[0] if plans and plans[0].get("version") == store.design.part(pid).version else None
        return scorecard.cost_and_waste(store, {pid: report}, {pid: plan})["usd"]
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# What it's held to (step 2): the conversation's checks, judged on what's already measured
# ---------------------------------------------------------------------------
def ran_safety(run: dict) -> Optional[float]:
    """A strength run's number from the cases that ran: a case whose load never reached a support is no 0x (#138
    item 3), and a run with none that ran has no number."""
    got = [c["safety"] for c in run.get("cases") or []
           if c.get("safety") is not None and (c.get("fea") or {}).get("supported") is not False]
    return min(got) if got else None


def measured(store: DesignStore, state: dict) -> dict:
    """What the checks can be judged by without running anything: the strength checks on each part's current
    version, its weight and cost, what the shop can't make, and print time. ``{metric: value}``."""
    from . import making

    out: dict = {}
    current = {p["id"]: p["version"] for p in state["parts"]}
    safeties, breaks = [], []
    for pid in current:
        run = next((r for r in state.get("load_runs") or [] if r["part"] == pid), None)
        if run and run.get("version") == current[pid] and ran_safety(run) is not None:
            safeties.append(ran_safety(run))
            breaks += [c["breaks_lb"] for c in run["cases"] if c.get("breaks_lb")]
    from . import load_study as L

    latest = [next((r for r in state.get("load_runs") or [] if r["part"] == pid), None) for pid in current]
    cases = [(r, c) for r in latest if r and r.get("version") == current.get(r["part"])
             for c in r.get("cases") or [] if c.get("safety") is not None or L.blind(r, c)]
    inches = (state.get("display_units") or "in") == "in"
    said = [(r, verdicts.case(r, c)) for r, c in cases]
    if any(not r.get("cut") for r, _ in cases):
        out["strength.uncut"] = True                   # made before the rounding fix (#214 review)
    if any(v["kind"] == "recheck" for _, v in said):
        out["strength.recheck"] = verdicts.UNCUT
    if any(v["kind"] == "span" for _, v in said):
        out["strength.span"] = verdicts.SPAN_WHY       # (CALI-153)
    held = [(r, v) for r, v in said if v["kind"] in ("unresolved", "unchecked")]
    if held:                                           # a ✓ can't rest on an FEA that can't see the wall (CALI-97)
        r, v = held[0]                                 # or on another check while the FEA couldn't see a wall (#244, #248)
        out["strength.unresolved"] = (unseen_said(r, v)[:1].upper() + unseen_said(r, v)[1:]) if v.get("why") else coarse(r, inches)
    failed = [(r, c, v) for (r, c), (_, v) in zip(cases, said) if v["kind"] == "fails" and v.get("coarse")]
    if failed:                                         # ...and a ✗ on one says it, as the part card does (#139)
        out["strength.coarse_fail"] = fail_hedge(*failed[0], inches).strip() or coarse(failed[0][0], inches, holds=False)
    # a breaking load from a run that can't see its walls isn't one to read, and never the rest's smallest (#191 review)
    gone = next(((r, v) for (r, c), (_, v) in zip(cases, said) if c.get("breaks_lb") and (v["kind"] not in verdicts.SETTLED or v.get("coarse"))), None)
    if gone:
        out["strength.no_breaks"] = (f"not settled: {verdicts.SPAN_WHY}" if gone[1]["kind"] == "span"
                                     else coarse(gone[0], inches, holds=gone[1]["kind"] != "fails"))
    if any(L.rough(r, c) for r, c in cases):
        out["strength.rough"] = True                   # the printed model's number: "about", as the part card says
    from . import consistency

    # a design's strength never leaves a part out (#132 review): a part with loads() and no check of this version is
    # unchecked, or older; its number isn't in the min above, so the rest can't read as holding for it
    loaded = [p for p in state["parts"] if p.get("loads") and p.get("role") != "fixed"]
    runs = {pid: next((r for r in state.get("load_runs") or [] if r["part"] == pid), None) for pid in current}
    unchecked = [p["id"] for p in loaded if runs.get(p["id"]) is None
                 or (ran_safety(runs[p["id"]]) is None and not any(L.blind(runs[p["id"]], c) for c in runs[p["id"]].get("cases") or []))]
    said = {p["id"]: part_name(p) for p in state["parts"]}          # the names a person reads (#94)
    older = [p["id"] for p in loaded if p["id"] not in unchecked and runs[p["id"]].get("version") != p["version"]]
    # the newest strength run of a part changed since, with its verdict and age: what the design card says over an
    # older scorecard's number (#138 item 1: "2.58x" from v1 over v4's 1.7x ✗)
    last = [{"part": pid, "version": runs[pid]["version"], "now": current[pid], "safety": ran_safety(runs[pid]),
             "edge": consistency.middle_only(store, pid, runs[pid])}           # the middle only (CALI-94, #106 sweep)
            for pid in older]
    if last:
        out["strength.last"] = min(last, key=lambda x: x["safety"])
    if unchecked:
        out["strength.unchecked"] = ("not checked yet on the " + " and the ".join(said[x] for x in unchecked)
                                     + ": Check it holds")
    if older:
        out["strength.stale"] = ("the " + " and the ".join(said[x] for x in older)
                                 + " changed since its strength check: check it again")
    filled = [pid for pid in current if any(r["part"] == pid and r.get("version") == current[pid]
                                            for r in state.get("load_runs") or []) and consistency.filled(store, pid)]
    if filled:                                         # a verdict measured on a filled-in solid isn't one (CALI-96)
        out["strength.filled"] = untrusted(filled[0], consistency.filled(store, filled[0]) or "")
    edged = [pid for pid in current if any(r["part"] == pid and r.get("version") == current[pid]
                                           for r in state.get("load_runs") or []) and consistency.bare_edge(store, pid)]
    if edged:                                          # loaded in the middle only (CALI-94, #106 review)
        out["strength.edge"] = consistency.MIDDLE_ONLY[0].upper() + consistency.MIDDLE_ONLY[1:] + "."
    # a run made before the rounding fix: its number on a goal's limit isn't settled either (#214 review)
    if safeties:
        out["strength.safety"] = min(safeties)
        # the case that number is, for what it's against (#208 review: the design card as the part card says it)
        worst = min(((r, c) for r, c in cases if c.get("safety") is not None
                     and (c.get("fea") or {}).get("supported") is not False), key=lambda rc: rc[1]["safety"], default=None)
        if worst is not None and abs(worst[1]["safety"] - out["strength.safety"]) < 1e-9:
            out["strength.case"] = {"lb": worst[1].get("lb"), "factor": worst[1].get("factor")}
    if breaks:
        if "strength.no_breaks" not in out:
            out["strength.breaks_lb"] = min(breaks)
    from . import trials

    tested = [t for t in (trials.summary(store, pid) for pid in current) if t and t["status"] in ("bad", "warn")]
    if tested:                                         # the worst real test, which outranks the prediction (CALI-86)
        out["strength.test"] = min(tested, key=lambda t: ORDER.index(t["status"]))
    weight = usd = missing = hours = 0.0
    slicing, unsliced, guessed, all_pieces, rough_pieces = False, "", "", 0, 0
    unprintable, cant = "", []                     # a printed piece the shop can't make: no total (#179 review, rule 6)
    weighed, unweighed, unpriced = False, None, None
    reps: list = []                                # each part's report, by its one filament figure
    for p in state["parts"]:
        if not p.get("built") or p.get("role") == "fixed":
            continue
        try:
            rep = C.report(store, p["id"])
        except Exception as e:  # noqa: BLE001 — a part that can't be weighed is unknown, never left out (#132)
            weighed, unweighed = True, unweighed or f"not checked: the {part_name(p)} couldn't be weighed ({e})"
            continue
        weighed = True
        mk = None
        if not rep.get("not_accounted"):           # no plan for pieces that aren't the part (CALI-155)
            try:
                mk = making.plan(store, p["id"], wait=False)   # the slicer never holds a card (#97)
            except Exception:  # noqa: BLE001
                mk = None
        rep = making.filament(rep, mk)             # its weight and cost by the one filament figure (#70 item 23)
        reps.append(rep)
        if rep.get("mass_lb") is None:             # one part unknown: the total is too, never the rest's (#125)
            unweighed = unweighed or rep.get("unweighed") or C.UNWEIGHED
        else:
            weight += rep["mass_lb"]
        unpriced = unpriced or rep.get("not_accounted")          # no total from a part whose pieces aren't it (CALI-155)
        if rep.get("not_accounted"):
            continue
        usd += _cost(store, p["id"], rep) or 0.0
        try:
            if mk is None:
                raise ValueError("no making plan")
            missing += len(mk["missing"])
            unprintable = unprintable or making.no_print_total(mk)
            cant += [f"the {part_name(p)}'s {m['name']}: {m['why']}" for m in mk["missing"]]
            if mk.get("pending"):
                slicing = True
            gone = next((x for x in mk["printed"] if x.get("hours") is None and x.get("slicer_failed")), None)
            if gone is not None:                  # no number for one part: the total is unknown, said (rule 6)
                unsliced = unsliced or f"print time: the slicer couldn't work it out: {_why(gone)}"
            hours += sum(x["hours"] for x in mk["printed"] if x.get("hours") is not None)
            guessed = guessed or next((x["rough_said"] for x in mk["printed"] if x.get("rough_said")), "")
            all_pieces += sum(x["pieces"] for x in mk["printed"] if x.get("hours") is not None)
            rough_pieces += sum(x.get("rough", 0) for x in mk["printed"] if x.get("hours") is not None)
        except Exception:  # noqa: BLE001
            pass
    if weighed:
        out.update({"weight.total_lb": None if unweighed else round(weight, 1), "cost.usd": None if unpriced else round(usd, 2),
                    "make.not_in_shop": None if unpriced else missing})
        if cant:
            out["make.cant"] = cant
        if unpriced:
            out["pieces.short"] = unpriced
        if unweighed:
            out["weight.unweighed"] = unweighed
        guess, slicing_now = making.filament_said(reps)   # a goal on a guessed or still-slicing figure (#237 review)
        if guess:
            out["filament.rough"] = guess
        if slicing_now:
            out["filament.pending"] = slicing_now
        if unprintable:                            # first: it stays this way however long the slicer takes
            out["print.unknown"] = unprintable
        elif slicing:                              # a part still slicing: no total, said (#97, rule 6)
            out["print.pending"] = "print time: working it out…"
        elif unsliced:
            out["print.unknown"] = unsliced
        elif hours:
            out["print.hours"] = round(hours, 1)
            if guessed:                            # any piece a guess: the total is never a ✓ (#166, rule 6)
                out["print.rough"] = f"{'partly ' if rough_pieces < all_pieces else ''}a guess ({guessed})"
    return out


def _why(pr: dict) -> str:
    """Why the slicer gave no number, from its own words ("walls + infill at rough speeds (the slicer timed out)")."""
    said = pr.get("from") or ""
    return said[said.rfind("(") + 1:].rstrip(")") if "(" in said else said or "no reason given"


def _against(c: dict, failed: bool, unit: str = "") -> str:
    """A goal's own limit beside its number (#137 item 5: "13.1 lb" never said it was over a 10 lb cap)."""
    lim = c.get("limit")
    if not isinstance(lim, (int, float)) or isinstance(lim, bool) or c["metric"].startswith("strength"):
        return ""                                  # a strength goal's label says what it needs ("2 times over")
    cap, said = c.get("op", ">=") in ("<=", "<"), _num(c["metric"], float(lim), unit)
    if cap:
        return f", over its {said} cap" if failed else f", within its {said} cap"
    return f", short of the {said} it needs" if failed else f", against the {said} it needs"


_NEED = re.compile(r",\s*(?:(?:twice|\d+(?:\.\d+)?\s*(?:times|×))\s*over|\d+(?:\.\d+)?\s*[×x]\s*safety)\s*$", re.I)


def _without_need(label: str) -> str:
    """A strength goal's label without the factor it needs ("holds Dad (200 lb), 2 times over" -> "holds Dad
    (200 lb)"): its line says the factor after the number it does, so it isn't read as the number (#64 item 15)."""
    return _NEED.sub("", label).rstrip()


def _num(metric: str, v: float, unit: str = "", about: bool = False, need: Optional[float] = None) -> str:
    from .goals import METRICS

    unit = METRICS.get(metric, ("", unit, ""))[1] or unit
    if unit == "$":
        return f"${v:,.0f}"
    if unit == "×":                                         # as the part card says it (#144: "0.5 times over")
        return _times(v, about, need)
    if v == 1 and unit.endswith("s") and unit not in ("lbs",):
        unit = unit[:-1]                                    # 1 sheet, 1 piece
    return ("about " if about else "") + f"{v:g} {unit}".strip()


def held_to(state: dict, now: dict) -> list[dict]:
    """One line per check the design is held to: a verdict (from what's measured now, else the last
    scorecard, said so if a part has changed since), or what it needs to be checked."""
    card = (state.get("scorecards") or [None])[0]
    scored = {k: m.get("value") for k, m in ((card or {}).get("metrics") or {}).items()
              if isinstance(m.get("value"), (int, float)) and not isinstance(m.get("value"), bool)}
    units = {k: m.get("unit", "") for k, m in ((card or {}).get("metrics") or {}).items()}
    rough_scored = {k: m.get("source") for k, m in ((card or {}).get("metrics") or {}).items() if m.get("trust") == "rough"}
    stale = bool(card) and (bool(card.get("outdated")) or any(
        card.get("versions", {}).get(p["id"]) not in (None, p["version"]) for p in state["parts"]))
    out = []
    for c in (state.get("goals") or {}).get("checks") or []:
        label = c.get("label") or c["id"]
        label = label[0].upper() + label[1:]
        if c.get("source") == "proposed":
            out.append(_line(f"Proposed: {label}. Keep or drop it under the numbers.", "info", goal=c["id"]))
            continue
        test = now.get("strength.test") if c["metric"].startswith("strength") else None
        if test:                                       # what a real test did, over what the check predicted
            out.append(_line(f"{'✗' if test['status'] == 'bad' else '!'} {label}: {test['text']}", test["status"],
                             study="load", model="scorecard"))
            continue
        assumed = " (assumed)" if c.get("source") == "assumed" else ""
        short = now.get("pieces.short")                # its pieces leave a panel out: no number comes from them (CALI-155)
        unknown = (now.get("weight.unweighed") if c["metric"].startswith("weight")
                   else f"it can't be priced yet: {short}" if short and c["metric"].startswith(("cost", "waste"))
                   else f"its cuts can't be checked yet: {short}" if short and c["metric"].startswith("make") else None)
        if unknown:            # unknown now: never the last card's lower total (#125, #132): one verdict, said
            verdict = verdicts.goal(None, incomplete=unknown)
            out.append(_line(f"{label}{assumed}: {verdict.get('why') or unknown}.", "warn"))
            continue
        v, late = now.get(c["metric"]), False
        last = now.get("strength.last") if c["metric"] == "strength.safety" and v is None else None
        if last and (not card or last["version"] >= ((card.get("versions") or {}).get(last["part"]) or 0)):
            # the newest run, with its age, over an older card's number: never greener than it (#138 item 1)
            verdict = verdicts.goal(verdicts.compare(last["safety"], c.get("op", ">="), c["limit"]), stale=True)
            out.append(_line(f"{'✗' if verdict['kind'] == 'fails' else '!'} {label}{assumed}: last checked on "
                             f"v{last['version']}: {_times(last['safety'], need=c['limit'])}"
                             + (f", needs {c['limit']:g}" if verdict["kind"] == "fails" else
                                ", checked in the middle only" if last.get("edge") else "")
                             + f" · v{last['now']} not checked yet.", verdict["status"], study="load",
                             model=rests_on_model(c["metric"])))
            continue
        if v is None and c["metric"] == "strength.breaks_lb" and now.get("strength.no_breaks"):
            out.append(_line(f"! {label}{assumed}: {now['strength.no_breaks']}", "warn", study="load", model=rests_on_model(c["metric"])))
            continue
        if v is None and c["metric"] in scored:
            v, late = scored[c["metric"]], stale
        if v is None and c["metric"].startswith("print.") and now.get("print.pending"):
            out.append(_line(f"{label}{assumed}: {now['print.pending']}", "info", working=True))
            continue
        if v is None and c["metric"].startswith("print.") and now.get("print.unknown"):
            out.append(_line(f"{label}{assumed}: {now['print.unknown']}.", "warn"))
            continue
        if v is None and c["metric"].startswith("strength") and now.get("strength.unresolved"):   # it was checked, and can't say (#202)
            out.append(_line(f"! {label}{assumed}: {now['strength.unresolved']}", "warn", study="load", model=rests_on_model(c["metric"])))
            continue
        if v is None:
            how = ("Check it holds" if c["metric"].startswith("strength") else "Score it")
            out.append(_line(f"{label}{assumed}: not checked yet. {how}.", "warn",
                             study="load" if c["metric"].startswith("strength") else None))
            continue
        if c["metric"].startswith(("weight.", "cost.")) and c["metric"] in now and now.get("filament.pending"):
            out.append(_line(f"{label}{assumed}: {now['filament.pending']}", "info", working=True))   # not the solid's red (#237 review)
            continue
        met = verdicts.compare(v, c.get("op", ">="), c["limit"])
        strength = c["metric"].startswith("strength")
        untrue = now.get("strength.filled") if strength else None
        # one verdict (CALI-112): a ✗ stays a ✗, then not trusted (CALI-96), then not resolved (CALI-97)
        older = now.get("strength.stale") if strength else None
        guess = None
        if c["metric"].startswith(("weight.", "cost.")):   # a guessed filament figure: no ✓ on it (#237 review)
            guess = now.get("filament.rough") if c["metric"] in now else rough_scored.get(c["metric"])
        if c["metric"].startswith("print."):           # a rough print time runs low: no ✓ on it (#166)
            guess = now.get("print.rough") if c["metric"] in now else (
                f"{'partly ' if re.match(r'[0-9]+ of ', rough_scored[c['metric']]) else ''}a guess "
                f"({rough_scored[c['metric']]})" if c["metric"] in rough_scored else None)
        verdict = verdicts.goal(met, untrusted=untrue, unresolved=(now.get("strength.unresolved") or now.get("strength.coarse_fail")) if strength else None,
                                edge=bool(now.get("strength.edge")) if strength else False,       # (CALI-94)
                                stale=late or bool(older),
                                incomplete=now.get("strength.unchecked") if strength else None, estimate=guess,
                                close=c["metric"] == "strength.safety" and c.get("op", ">=") == ">="    # amber (CALI-88)
                                and verdicts.near(v, c["limit"]),
                                # an old number on its limit, the run's or this goal's own (#214 review)
                                recheck=(now.get("strength.recheck") or (verdicts.UNCUT if verdicts.goal_on_limit(
                                    bool(now.get("strength.uncut")), c["metric"], v, c.get("limit"), c.get("op", ">="))
                                    else None)) if strength else None,
                                span=now.get("strength.span") if strength else None)
        if verdict["kind"] == "estimate":
            out.append(_line(f"! {label}{assumed}: {_num(c['metric'], v, units.get(c['metric'], ''))}, {guess}.", "warn"))
            continue
        if verdict["kind"] == "untrusted":             # the verdict first; which check it is follows (#96 item 5)
            out.append(_line(f"{untrue} ({label[:1].lower() + label[1:]}{', assumed' if c.get('source') == 'assumed' else ''})", "warn",
                             study="load", model=rests_on_model(c["metric"])))
            continue
        if verdict["kind"] == "edge":                  # the middle only: no ✓ for where people stand (CALI-94)
            out.append(_line(f"! {label}{assumed}: {now['strength.edge']}", "warn", study="load",
                             model=rests_on_model(c["metric"])))
            continue
        if verdict["kind"] in ("unresolved", "span"):  # no ✓ on an FEA that can't see the wall (CALI-97) or the span (CALI-153)
            out.append(_line(f"! {label}{assumed}: {verdict['why']}", "warn",
                             study="load", model=rests_on_model(c["metric"])))
            continue
        # the printed model's number says "about", as the part card says it (CALI-97); _times owns it (#144 review)
        num = _num(c['metric'], v, units.get(c['metric'], ''), about=bool(strength and now.get("strength.rough")),
                   need=c.get("limit") if isinstance(c.get("limit"), (int, float)) else None)
        failed = verdict["kind"] == "fails"
        why = (filled_fail(untrue) if failed and untrue   # still ✗
               else f" {now['strength.coarse_fail']}" if failed and strength and now.get("strength.coarse_fail") else "")
        if verdict["kind"] == "waiting":               # a part left out isn't covered by the rest (#132 review)
            out.append(_line(f"! {label}{assumed}: {num} for the rest, but {verdict['why']}.", "warn",
                             study="load" if strength else None, model=rests_on_model(c["metric"])))
            continue
        # never a ✓ for an older check or score (#132 review): it says when, and what to do
        later = (" (scored before the last change: score it again)." if late
                 else f" ({older})." if verdict["kind"] == "stale" and older
                 else f": check it again, {verdict['why']}." if verdict["kind"] == "recheck" else "." + why)
        mark = '✗' if failed else '✓' if verdict['kind'] == 'holds' else '!'
        if c["metric"] == "strength.safety" and isinstance(c.get("limit"), (int, float)):
            # what it does, then what it needs: "2 times over (assumed): 3.11x" read as holding 2 times over (#64 item 15)
            need = f"; it needs {c['limit']:g}{', assumed' if assumed else ''}"
            said = f"{mark} {_without_need(label)}, {num}" + against(now.get("strength.case") or {}, need)
        else:
            said = f"{mark} {label}{assumed}: {num}" + _against(c, failed, units.get(c['metric'], ''))
        out.append(_line(said + later,
                         "warn" if late else verdict["status"], **({"close": True} if verdict["kind"] == "close" else {}),
                         study="load" if c["metric"].startswith("strength") else None,
                         model=rests_on_model(c["metric"])))
    return out


# ---------------------------------------------------------------------------
# The whole design
# ---------------------------------------------------------------------------
def _broken(p: dict, named: bool = False) -> list[dict]:
    """A part's own rules it breaks as built now, each a line from its verdict (#137 item 1: the bar stool's locked
    shell wall, broken, and no card said so)."""
    from . import part_rules

    who = f"The {part_name(p)} breaks" if named else "Breaks"
    return [_line(f"✗ {who} its rule {r['said']}.", r["verdict"]["status"], study="rule")
            for r in part_rules.failing(p.get("rules") or [])]


def design(store: DesignStore, state: dict) -> list[dict]:
    parts = [p for p in state["parts"] if p.get("role") != "fixed"]
    # a design that's one part (the stool) answers with that part's own list and plan (CALI-59)
    solo = {c["key"]: c for c in part(store, state, parts[0]["id"])} if len(parts) == 1 else {}
    what = [_line(_sentence(state.get("prompt") or state["name"]))]
    if solo:
        # the part's own description, as What do I buy? already reads it (#89 item 3: the raw "I want to make…")
        what = list(solo["what"]["lines"][:1]) + solo["what"]["lines"][1:]
    elif parts:
        what.append(_line(f"{len(parts)} part{'s' if len(parts) != 1 else ''}: " + ", ".join(p.get("label") or p["id"] for p in parts)))
    elif state.get("building"):
        what.append(_line("Building it now: these fill in as it goes.", "info"))
    elif state.get("plan"):                   # planned, not built: the person reviews it first (CALI-35, #3a)
        pl = state["plan"]
        what.append(_line(pl["headline"], "warn"))
        # with no key the page shows the key's note where Build it would be: the line says so, never "press" (#89)
        what.append(_line("That's the plan, before anything's drawn: its numbers and the checks between the parts are "
                          "under the numbers. " + ("Say what to change, or press Build it." if state.get("claude", True)
                                                   else "Building it needs Claude, which isn't set up here."), "info"))
    else:
        what.append(_line("Not built yet: answer its questions and press Build it.", "warn"))
    assumed = sum(1 for r in state.get("requirements") or [] if r.get("source") == "assumed")
    if assumed:
        what.append(_line(f"{assumed} answer{'s' if assumed != 1 else ''} assumed: check them under the numbers.", "warn"))

    now = measured(store, state) if parts else {}
    # a part's own rule it breaks leads the design's answer too (#137 item 1)
    broken = [ln for p in parts for ln in _broken(p, named=len(parts) > 1)]
    work = held_to(state, now) if parts else []
    card = (state.get("scorecards") or [None])[0]
    if card and not work:
        s = card["summary"]
        fails = [c for c in card["checks"] if c["status"] == "fail"]
        stale = bool(card.get("outdated")) or any(card.get("versions", {}).get(p["id"]) not in (None, p["version"])
                                                  for p in parts)
        # never a pass: a check that couldn't run (#103 review), nor one measured on a filled-in shape (CALI-96)
        untrusted, unresolved = s.get("untrusted") or 0, s.get("unresolved") or 0     # never a pass (CALI-110)
        edge = s.get("edge") or 0                                                      # nor middle only (CALI-94)
        span = s.get("span") or 0                                                      # nor not settled (CALI-153)
        waits = (s.get("unknown") or 0) - untrusted - unresolved - edge - span
        said = (f"{s['pass']} check{'s' if s['pass'] != 1 else ''} pass" if s["pass"] or fails
                else "No check has run yet" if waits and not untrusted and not unresolved and not edge and not span
                else "No check passes yet")
        rest = ([f"{untrusted} not trusted"] * bool(untrusted) + [f"{unresolved} not resolved"] * bool(unresolved)
                + [f"{edge} middle only"] * bool(edge) + [f"{span} not settled"] * bool(span) + [f"{waits} not checked yet"] * bool(waits)
                + [f"{s.get('estimate')} a guess"] * bool(s.get("estimate")))
        work.append(_line(said + (
            f", {s['fail']} fail" + (f" ({s['unsettled']} not settled: too coarse to see its walls)" if s.get("unsettled") else "") + ": " + "; ".join((c.get("label") or c["id"]) for c in fails[:2]) if fails else "")
            + (f"{',' if s['pass'] or fails else ':'} " + ", ".join(rest) if rest else "") + "."
            + (" (A part has changed since: score it again.)" if stale else ""),
            "bad" if fails else "warn" if stale or rest or not verdicts.summary(s)["counts_as_pass"] else "ok"))
    elif not work and not broken:
        work.append(_line("Nothing to hold it to yet: say what it must do.", "warn"))
    work = broken + work
    if solo:                                         # one part: its Make it better here too, no selecting first (#92)
        work += [ln for ln in solo["work"]["lines"] if ln.get("better")]

    buy = list(solo["buy"]["lines"]) if solo else []
    if now.get("cost.usd") and not solo:
        buy.append(_line(f"About ${now['cost.usd']:,.0f} for everything"
                         + (f" (${card['cost']['waste_usd']:,.0f} of it offcut, when last scored)."
                            if card and card.get("cost", {}).get("waste_usd") else ".")))
    if now.get("weight.total_lb") is not None and not solo:
        lb = now["weight.total_lb"]
        buy.append(_line(f"It all weighs {lb:g} lb" + (", easy for a kid to carry." if lb <= 10 else ".")))
    if not buy:
        buy.append(_line("Not known yet: no part says what it's built from.", "info"))

    make = [ln for ln in solo["make"]["lines"]] if solo else []
    if now.get("make.not_in_shop") and not solo:   # the part's own card says this, and solo is that card
        said = "; ".join(now["make.cant"][:3]) + (f"; and {len(now['make.cant']) - 3} more" if len(now["make.cant"]) > 3 else "")
        make.append(_line(f"Your shop can't make {said}.", "bad"))
    rel = (state.get("releases") or [None])[0]
    if rel:
        url = f"/api/designs/{state['slug']}/releases/{rel['id']}/files/"
        v = verdicts.release(rel, {p["id"]: p["version"] for p in state["parts"]})    # one verdict (#132 review)
        make.append(_line(f"Build package {rel['id']}: {len(rel['steps'])} steps, "
                          + (("ready to cut; print time is a guess." if ((rel.get("card") or {}).get("summary") or {}).get("estimate")
                              else "ready to cut.") if v["kind"] == "holds" else
                             "ready to cut as it was, but a part has changed since: make it again." if v["kind"] == "stale"
                             else f"not ready: {_why_not(rel)}."),
                          v["status"], action="release",
                          links=[{"label": "Open the build book", "url": url + "index.html"}]
                          + ([{"label": "The kids' build book", "url": url + rel["kids"]}] if rel.get("kids") else [])))
    elif not solo:
        make.append(_line(f"No build package yet: {consistency_no_make()}.", "warn") if now.get("pieces.short")
                    else _line("No build package yet: make one when it's ready.", "info", action="release"))
    else:
        make.append(_line(f"No build package yet: {consistency_no_make()}.", "warn") if now.get("pieces.short")
                    else _line("Or make the whole build package: the build book, cut lists and drawings.", "info", action="release"))
    return [_card("what", "What is it?", what),
            _card("work", "Will it work?", work,
                  promised=promise(store, [p.id for p in store.design.parts]) if store is not None else PROMISE),
            _card("buy", "What do I buy?", buy), _card("make", "How do I make it?", make)]


def answers(store: DesignStore, state: dict, part_id: Optional[str] = None) -> list[dict]:
    """The four cards for the design, or for one of its parts."""
    return part(store, state, part_id) if part_id else design(store, state)
