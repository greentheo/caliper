"""CALI-79 (#47) — a build book a kid can follow: pictures first, one step a page.

The build package's book is for the shop: the scorecard, the shopping list, cut lists, then the assembly
in a few big stages. Showcase 1 (#10) asks for one a kid can read, so a wooden build gets a second book:

1. **Get your things:** what to buy and the tools, to tick off.
2. **Draw the pieces:** each piece's pattern (print it full size, or measure and mark it).
3. **Cut them out**: a grown-up clamps and cuts (and drills a start hole inside a hole or a picture) while
   the kid stands back in safety glasses. A kid's hands are never at the work while a tool runs.
4. **Sand the edges.**
5. **One page a piece**, in the order they go together: the build so far in pale, the new piece in colour, the
   same view every page. It says what it goes against and how many screws hold it.
6. **Paint it**, if it's painted.
7. **Test it:** a grown-up stands on it first while the kid watches, then the kid; and what the numbers do
   and don't promise.

The steps come from the pieces themselves: which touch which (the joints the shopping list counts screws
for), and how high each one sits. Only for a build that's all wood, glued and screwed; a welded frame stays
in the shop's book.
"""

from __future__ import annotations

import html
import math
import os
import re
from typing import Optional

from .design import DesignStore
from .fasteners import PILOT_BIT

IN = 25.4
WOOD = ("plywood", "lumber")


def suits(store: DesignStore, part_ids: list[str]) -> bool:
    """A kid's book is for a build that's all wood pieces (sheets or sticks), glued and screwed."""
    from . import construction as C

    seen = False
    for pid in part_ids:
        if not store.is_scripted(pid) or "def members(" in store.read_script(pid):
            return False
        for it in C._items(C.declared(store, pid)) or []:
            if it.get("kind") in ("sheet", "stick"):
                if it.get("material") not in WOOD:
                    return False
                seen = True
            elif it.get("kind") not in ("covering", "lump"):
                return False
    return seen


def _name(n: str) -> str:
    return (n or "piece").replace("_", " ")


_NTH = ["first", "second", "third", "fourth", "fifth", "sixth"]


def _words(seq: list) -> dict:
    """What each piece is called on the pages, by key: its name, or, for pieces that share one, "first side" and
    "other side" (or "second side", "third side" ...) in the order they go on (CALI-87)."""
    count: dict = {}
    for pc, _ in seq:
        count[pc["name"]] = count.get(pc["name"], 0) + 1
    seen: dict = {}
    out = {}
    for pc, _ in seq:
        n = pc["name"]
        seen[n] = seen.get(n, 0) + 1
        if count[n] == 1:
            out[pc["key"]] = _name(n)
        else:
            k = seen[n] - 1
            nth = "other" if count[n] == 2 and k == 1 else (_NTH[k] if k < len(_NTH) else f"#{k + 1}")
            out[pc["key"]] = f"{nth} {_name(n)}"
    return out


def _together(against: list, wood: list, words: dict) -> str:
    """The pieces a piece goes against, in words: "both sides, the back and the front" when every piece sharing a
    name is among them."""
    name_of = {w["key"]: w["name"] for w in wood}
    parts, done = [], set()
    for a in against:
        n = name_of[a]
        same = [w["key"] for w in wood if w["name"] == n]
        if len(same) == 2 and set(same) <= set(against):
            if n not in done:
                parts.append(f"both {_name(n)}s")
                done.add(n)
        else:
            parts.append(f"the {words[a]}")
    parts.sort(key=lambda w: not w.startswith("both "))   # "both sides" first, then the rest as they went on
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def order(pcs: list[dict], joints: dict) -> list[tuple[dict, list[str]]]:
    """The pieces in the order they go together: the lowest standing piece first, then each one that meets what's
    already there, lowest and biggest first. Each with the pieces it goes against."""
    def low(pc):
        return min(q[2] for poly in pc["polys"] for q in poly)

    def size(pc):
        from . import construction as C

        return sum(C.polygon([list(q) for q in poly])[0] for poly in pc["polys"]) if pc["kind"] == "sheet" else 0.0

    left = sorted(pcs, key=lambda pc: (round(low(pc)), -size(pc)))
    done: list[dict] = []
    out = []
    while left:
        names = [d["key"] for d in done]                 # each piece by its own key, in the order they went on
        meets = [pc for pc in left if any(tuple(sorted((pc["key"], n))) in joints for n in names)]
        nxt = min(meets or left, key=lambda pc: (round(low(pc)), -size(pc)))
        out.append((nxt, [n for n in names if tuple(sorted((nxt["key"], n))) in joints]))
        done.append(nxt)
        left = [pc for pc in left if pc is not nxt]   # by identity: == compares the pieces' arrays (CALI-87)
    return out


def facing(every: list[dict], pictured: set) -> float:
    """Where to look from: at the side with a picture on it (and the front with it), else the shop book's view."""
    from .release import _normal

    pts = [q for p in every for poly, _ in p["polys"] for q in poly]
    if not pts or not pictured:
        return 35.0
    mid = [sum(q[k] for q in pts) / len(pts) for k in range(3)]

    def out(p):                                            # a panel's outward normal, across the floor
        poly = p["polys"][0][0]
        n = _normal(poly)
        c = [sum(q[k] for q in poly) / len(poly) for k in range(3)]
        sign = 1.0 if sum(n[k] * (c[k] - mid[k]) for k in range(3)) >= 0 else -1.0
        return [sign * n[0], sign * n[1]]

    pic = next((p for p in every if p["name"] in pictured), None)
    if pic is None:
        return 35.0
    nx, ny = out(pic)
    centre = math.degrees(math.atan2(ny, nx))
    front = next((p for p in every if "front" in (p["name"] or "").lower() and p["name"] not in pictured), None)
    if front is None:
        return centre - 35.0
    fx, fy = out(front)
    return max((centre + 40.0, centre - 40.0),
               key=lambda a: math.cos(math.radians(a)) * fx + math.sin(math.radians(a)) * fy)


def screws_for(mm: float) -> int:
    """A joint's screws, as the shopping list counts them: one every 6 in, at least two."""
    from .fasteners import SCREW_EVERY_IN

    return max(2, math.ceil(mm / IN / SCREW_EVERY_IN))


def make(store: DesignStore, root: str, rec: dict, part_ids: list[str], shop: dict) -> Optional[str]:
    """``kids.html`` (and its drawings in ``kids/``) in the release folder ``root``; None if it doesn't suit."""
    from . import answers, fasteners, release
    from . import construction as C
    from . import holes as H
    from . import shop as S
    from .consistency import _sides, shapes, tolerance

    if not suits(store, part_ids):
        return None
    os.makedirs(os.path.join(root, "kids"), exist_ok=True)
    pages: list[dict] = []
    every = [p for pid in part_ids for p in release.pieces(store, pid)]
    pictured = {h["piece"] for pid in part_ids for h in H.read(store.read_script(pid)) if h.get("picture")}
    view = release.View(every, azimuth=facing(every, pictured))
    # what to get
    things = [re.sub(r"\s*\([^)]*\)", "", f"{r['qty']} {r['item']}") for g in shop["groups"] for r in g["rows"]]
    tools = ["a pencil and a long ruler", "sandpaper"]
    hand = set(S.read().get("hand") or [])
    tools += [t for t in ("jigsaw", "drill") if t in hand or not hand]
    if any(r for g in shop["groups"] for r in g["rows"] if "screw" in r["item"]):
        tools.append(f"a {PILOT_BIT} drill bit for the pilot holes")      # (#64 item 8)
    tools += ["two clamps", "safety glasses (everyone)", "ear defenders (a jigsaw is loud)",
              "a grown-up for the saw and the drill"]
    pages.append({"title": "Get your things", "say": "Tick each one off when you have it.",
                  "check": things + tools, "img": None})
    # draw the pieces: the patterns, by name
    thumbs = []
    for pid in part_ids:
        hand_dir = os.path.join(root, "hand", pid)
        if os.path.isdir(hand_dir):
            thumbs += [(f, f"hand/{pid}/{f}") for f in sorted(os.listdir(hand_dir)) if f.endswith(".png")]
    holes = sum(len(it.get("holes") or []) for pid in part_ids for it in C._items(C.declared(store, pid)) or [])
    pictures = [h["picture"] for pid in part_ids for h in H.read(store.read_script(pid)) if h.get("picture")]
    pages.append({"title": "Draw the pieces", "img": None, "thumbs": thumbs,
                  "say": "Print the patterns at full size and tape them on the wood, or measure and mark them with "
                         "a ruler. Write each piece's name on it in pencil.",
                  "link": [(f"hand/{pid}/print-full-size.pdf", "Print the patterns full size") for pid in part_ids]})
    # a kid's hands are never at the work while a tool runs (CALI-86, rule 6): the grown-up clamps and cuts
    cut = ("A grown-up clamps the wood to the table with the line hanging past the table's edge (so the blade "
           "doesn't cut the table), then cuts along the lines with the jigsaw. You stand an arm's length behind the "
           "grown-up, never in front of the saw, with your safety glasses and ear defenders on, and watch the line: "
           "say if the blade wanders off it.")
    if holes:
        cut += (f" For {'the ' + ' and the '.join(pictures) if pictures else 'each hole'}, the grown-up drills a "
                "hole just inside the line first: the jigsaw blade goes in through it.")
    pages.append({"title": "Cut them out", "say": cut, "grownup": True, "img": None})
    pages.append({"title": "Sand the edges", "say": "Sand every edge until it's smooth to touch, so nobody gets a "
                                                     "splinter. Round the corners a little.", "img": None})
    # one piece at a time
    done: list[dict] = []
    for pid in part_ids:
        declared = C.declared(store, pid)
        mesh = store.part_geometry(pid).require_mesh()
        pcs = shapes(declared)
        _sides(mesh, pcs)
        wood = [pc for pc in pcs if pc.get("material") in WOOD]
        joints = fasteners.joints(wood, tolerance(mesh))
        # each drawing by the piece's own key, numbered as fasteners.keys numbers the wood (CALI-87)
        drawn_wood = [p for p in release.pieces(store, pid) if p.get("material") in WOOD and p["kind"] in ("sheet", "stick")]
        fasteners.keys(drawn_wood)
        drawn = {p["key"]: p for p in drawn_wood}
        seq = order(wood, joints)
        words = _words(seq)
        for k, (pc, against) in enumerate(seq):
            new = drawn.get(pc["key"])
            if new is None:
                continue
            if not against:
                say = f"Stand the {words[pc['key']]} up where the picture shows. This one is the start."
                n_screws = 0
            else:
                n_screws = sum(screws_for(joints[tuple(sorted((pc["key"], a)))]) for a in against)
                say = (f"Put glue on the edges where the {words[pc['key']]} touches {_together(against, wood, words)}. "
                       f"A grown-up clamps it and drills a {PILOT_BIT} pilot hole for each screw, so the wood won't "
                       f"split. Then the grown-up drives in {n_screws} screws. You stand an arm's length behind, in "
                       f"your safety glasses and ear defenders.")      # short sentences, read aloud (#209 review)
            img = f"kids/step-{len(pages) + 1:02d}.png"
            with open(os.path.join(root, img), "wb") as f:
                f.write(release.draw(view, [(done, "done"), ([new], "now")]))
            pages.append({"title": f"Add the {words[pc['key']]}" if against else f"Start with the {words[pc['key']]}",
                          "say": say, "img": img, "grownup": bool(n_screws), "screws": n_screws})
            done.append(new)
    if any("paint" in (p.get("covers") or []) for p in every):
        img = "kids/painted.png"
        with open(os.path.join(root, img), "wb") as f:
            f.write(release.draw(view, [(every, "now")]))
        pages.append({"title": "Paint it", "say": "Let the glue dry overnight, then paint it any colour you like. "
                                                   "Two coats, and let the first one dry.", "img": img})
    with open(os.path.join(root, "kids", "finished.png"), "wb") as f:
        f.write(release.draw(view, [(every, "now")]))
    pages.append(_strength_page(rec.get("strength") or {}, part_ids))
    with open(os.path.join(root, "kids.html"), "w") as f:
        f.write(page(release.title(rec["design"]), pages))
    return "kids.html"



def _strength_page(strength: dict, parts: Optional[list] = None) -> dict:
    """The kid's book's last page, from each case's one verdict (CALI-112): a promise only from a case that holds,
    nothing over it; any other case, no standing on it. Every part the book covers must hold: one with no check at
    the released version (none run, an error, no loads()) is "not checked", so never "your turn" (#132 review)."""
    from . import answers

    cases = [c for cs in strength.values() for c in cs]
    kinds = [(c.get("verdict") or {}).get("kind", "waiting") for c in cases]
    kinds += ["waiting" for pid in (parts or []) if not strength.get(pid)]      # a part left out: not checked
    if not kinds:
        kinds = ["waiting"]                              # nothing checked at all: not checked
    held = [f"It should hold {c['name'].lower()}, {answers._times(c['safety'])}." for c, k in zip(cases, kinds)
            if k == "holds"]
    if "fails" in kinds:
        # it failed its check: not a kid's to try at all (rule 6), and not "it should hold" (CALI-112's audit)
        return {"title": "Don't stand on it yet", "img": "kids/finished.png",
                "say": "Don't stand on it yet. It isn't strong enough yet, so a grown-up makes it stronger first and "
                       "checks it again, before anyone stands on it.", "grownup": True}
    if any(k != "holds" for k in kinds):
        # its strength hasn't been checked on the stool as built: no standing on it at all (#96 rework, item 4;
        # CALI-110: nor where the check was too coarse to see its walls)
        return {"title": "Don't stand on it yet", "img": "kids/finished.png",
                "say": "Don't stand on it yet. Its strength hasn't been checked on it as it's built, so a grown-up "
                       "checks it first, before anyone stands on it.", "grownup": True}
    return {"title": "Test it", "img": "kids/finished.png",
            # trying a new stool is a grown-up's step (rule 6): they go first, the kid watches
            "say": "A grown-up stands on it first, gently, while you watch. Then it's your turn, with the grown-up "
                   "right beside you. " + " ".join(held),
            "note": answers.PROMISE, "grownup": True}

CSS = """
:root { color-scheme: light; }
body { font: 22px/1.4 "Avenir Next", "Trebuchet MS", system-ui, sans-serif; color: #1d232a; background: #fff;
  margin: 0; }
.cover, .step { min-height: 96vh; padding: 28px 36px; box-sizing: border-box; page-break-after: always; }
.cover h1 { font-size: 44px; margin: 40px 0 10px; } .cover img { max-width: 100%; }
.step h2 { font-size: 34px; margin: 0 0 12px; display: flex; align-items: center; gap: 14px; }
.n { display: inline-flex; width: 52px; height: 52px; border-radius: 50%; background: #2f6fd6; color: #fff;
  align-items: center; justify-content: center; font-size: 28px; flex: none; }
.step img.big { width: 100%; max-height: 62vh; object-fit: contain; border: 2px solid #e3e7ec; border-radius: 14px; }
.say { font-size: 26px; margin: 16px 0; }
.grownup { display: inline-block; background: #fff3d6; border: 2px solid #f0b400; border-radius: 10px;
  padding: 4px 12px; font-size: 20px; }
ul.check { list-style: none; padding: 0; columns: 2; } ul.check li { margin: 8px 0; break-inside: avoid; }
ul.check li::before { content: "☐  "; font-size: 26px; }
.thumbs { display: flex; flex-wrap: wrap; gap: 14px; } .thumbs figure { margin: 0; width: 30%; }
.thumbs img { width: 100%; border: 1px solid #ccd; border-radius: 8px; } figcaption { font-size: 18px; }
.note { font-size: 16px; color: #5b6570; margin-top: 18px; } a.btn { font-size: 20px; }
@media print { a.btn { display: none; } }
"""


def page(title: str, pages: list[dict]) -> str:
    e = html.escape
    out = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
           f"<title>{e(title)}: let's build it</title><style>{CSS}</style></head><body>",
           f"<section class='cover'><h1>Let's build: {e(title)}</h1><p class='say'>{len(pages)} steps. Do one page "
           "at a time, and tick things off as you go.</p>"
           + "<img src='kids/finished.png' alt='what it will look like'></section>"]
    for i, p in enumerate(pages, 1):
        out.append(f"<section class='step'><h2><span class='n'>{i}</span>{e(p['title'])}</h2>")
        if p.get("grownup"):
            out.append("<div class='grownup'>👩‍🔧 with a grown-up</div>")
        if p.get("img"):
            out.append(f"<img class='big' src='{e(p['img'])}' alt='{e(p['title'])}'>")
        out.append(f"<p class='say'>{e(p['say'])}</p>")
        if p.get("check"):
            out.append("<ul class='check'>" + "".join(f"<li>{e(c)}</li>" for c in p["check"]) + "</ul>")
        if p.get("thumbs"):
            out.append("<div class='thumbs'>" + "".join(
                f"<figure><img src='{e(src)}' alt=''><figcaption>{e(os.path.splitext(f)[0].replace('-', ' '))}"
                "</figcaption></figure>" for f, src in p["thumbs"]) + "</div>")
        for href, label in p.get("link") or []:
            out.append(f"<p><a class='btn' href='{e(href)}'>{e(label)}</a></p>")
        if p.get("note"):
            out.append(f"<p class='note'>{e(p['note'])}</p>")
        out.append("</section>")
    out.append("</body></html>")
    return "\n".join(out)
