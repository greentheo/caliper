"""CALI-79 (#47) — a build book a kid can follow: pictures first, one step a page.

The build package's book is for the shop: the scorecard, the shopping list, cut lists, then the assembly
in a few big stages. Showcase 1 (#10) asks for one a kid can read, so a wooden build gets a second book:

1. **Get your things:** what to buy and the tools, to tick off.
2. **Draw the pieces:** each piece's pattern (print it full size, or measure and mark it).
3. **Cut them out**, with a grown-up: and for a hole or a picture, drill a start hole inside it first.
4. **Sand the edges.**
5. **One page a piece**, in the order they go together: the build so far in pale, the new piece in colour, the
   same view every page. It says what it goes against and how many screws hold it.
6. **Paint it**, if it's painted.
7. **Test it:** gently, with a grown-up holding it, and what the numbers do and don't promise.

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
        names = {d["name"] for d in done}
        meets = [pc for pc in left if any(tuple(sorted((pc["name"], n))) in joints for n in names)]
        nxt = min(meets or left, key=lambda pc: (round(low(pc)), -size(pc)))
        out.append((nxt, [n for n in names if tuple(sorted((nxt["name"], n))) in joints]))
        done.append(nxt)
        left.remove(nxt)
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
    tools += ["safety glasses (everyone)", "a grown-up for the saw and the drill"]
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
    cut = "A grown-up cuts along the lines with the jigsaw while you hold the pattern still and call out the line."
    if holes:
        cut += (f" For {'the ' + ' and the '.join(pictures) if pictures else 'each hole'}, drill a hole just inside "
                "the line first: the jigsaw blade goes in through it.")
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
        drawn = {p["name"]: p for p in release.pieces(store, pid)}
        for k, (pc, against) in enumerate(order(wood, joints)):
            new = drawn.get(pc["name"])
            if new is None:
                continue
            if not against:
                say = f"Stand the {_name(pc['name'])} up where the picture shows. This one is the start."
                n_screws = 0
            else:
                n_screws = sum(screws_for(joints[tuple(sorted((pc["name"], a)))]) for a in against)
                say = (f"Put glue on the edges where the {_name(pc['name'])} touches the "
                       f"{' and the '.join(_name(a) for a in against)}. Hold it in place and put in "
                       f"{n_screws} screws.")
            img = f"kids/step-{len(pages) + 1:02d}.png"
            with open(os.path.join(root, img), "wb") as f:
                f.write(release.draw(view, [(done, "done"), ([new], "now")]))
            pages.append({"title": f"Add the {_name(pc['name'])}" if against else f"Start with the {_name(pc['name'])}",
                          "say": say, "img": img, "grownup": bool(n_screws), "screws": n_screws})
            done.append(new)
    if any("paint" in (p.get("covers") or []) for p in every):
        img = "kids/painted.png"
        with open(os.path.join(root, img), "wb") as f:
            f.write(release.draw(view, [(every, "now")]))
        pages.append({"title": "Paint it", "say": "Let the glue dry overnight, then paint it any colour you like. "
                                                   "Two coats, and let the first one dry.", "img": img})
    held = []
    for cases in (rec.get("strength") or {}).values():
        for c in cases:
            if c.get("safety"):
                held.append(f"It should hold {c['name'].lower()}, {answers._times(c['safety'])}.")
    with open(os.path.join(root, "kids", "finished.png"), "wb") as f:
        f.write(release.draw(view, [(every, "now")]))
    pages.append({"title": "Test it", "img": "kids/finished.png",
                  "say": "Stand on it gently, with a grown-up holding it. Then let a grown-up try. " + " ".join(held),
                  "note": answers.PROMISE, "grownup": True})
    with open(os.path.join(root, "kids.html"), "w") as f:
        f.write(page(release.title(rec["design"]), pages))
    return "kids.html"


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
