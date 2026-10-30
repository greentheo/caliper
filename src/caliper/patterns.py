"""CALI-48 (#4) — patterns for hand tools: measure and mark, print and tape, project and trace.

Most people who'd build a stool have a jigsaw, a drill and a tape measure, not a CNC router. The router's
DXF is no use to them. They need the piece where they can trace it or mark it out on the board. So every
flat sheet piece, holes and all, comes three ways:

1. **Measure and mark** (``measure-and-mark.pdf``): one page per piece, on a 1 in grid, with its overall
   size, the corners of anything that isn't a plain rectangle, and each hole's position and size, all
   from the piece's two square edges (bottom and left). A curve is copied square by square from a grid
   drawn on the board.
2. **Print and tape** (``print-full-size.pdf``): the piece at full size across letter pages. Each page
   overlaps the next by 1/2 in and is labelled with where it goes (a map page first). A 3 in ruler sits in
   every top margin, to check it printed at 100%.
3. **Project and trace** (``project-<piece>.svg``): the piece at full size, white on black, beside a 4 in
   calibration square. Zoom the projector until the square measures 4 in on the board, then trace.

Pieces are drawn as seen from the face their outline gives (the outside, for a box), with their longest
edge along the bottom. Pages are rasters at :data:`DPI`, so they print at true size anywhere, without a
PDF library.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import time
import uuid
from typing import Optional

import numpy as np

from . import construction as C
from . import materials as M
from .design import DesignStore

IN = 25.4
DPI = 150
PAGE = (8.5, 11.0)              # letter, inches, portrait
MARGIN = 0.4                    # what a home printer can't print, inches
OVERLAP = 0.5                   # each page overlaps the next by this much, inches
BORDER = 0.1 * IN               # room round a piece on the full-size pages (just off the line), mm
CALIBRATE_IN = 4.0              # the projector's calibration square


def inches(mm: float) -> str:
    from .release import inches as _inches

    return _inches(mm)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "piece"


# ---------------------------------------------------------------------------
# The pieces, flat
# ---------------------------------------------------------------------------
def pieces(store: DesignStore, part_id: str) -> list[dict]:
    """Every flat sheet piece of a part in its own plane, mm, longest edge along the bottom, its lowest-left
    corner at (0, 0); and its holes in the same frame."""
    from .consistency import _frame

    d = C.declared(store, part_id)
    out = []
    for it in d.get("construction") or []:
        if it.get("kind") != "sheet" or not it.get("outline"):
            continue
        poly = np.asarray(it["outline"], float)
        o, u, v, n, flat = _frame(poly)
        holes = [np.stack([(np.asarray(h, float) - o) @ u, (np.asarray(h, float) - o) @ v], axis=1)
                 for h in it.get("holes") or []]
        edges = np.roll(flat, -1, axis=0) - flat
        k = int(np.argmax(np.linalg.norm(edges, axis=1)))
        a = -math.atan2(edges[k][1], edges[k][0])
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        pts, holes = flat @ R.T, [h @ R.T for h in holes]
        if pts[:, 1].mean() < pts[k, 1]:          # the long edge at the bottom, the piece above it
            pts, holes = pts * [1, -1], [h * [1, -1] for h in holes]
        lo = pts.min(axis=0)
        pts, holes = pts - lo, [h - lo for h in holes]
        t = float(it["thickness"])
        out.append({"name": it.get("name") or "piece", "material": it.get("material"), "thickness": t,
                    "label": f"{M.nominal(t)} {M.sheet(it['material'])['name']}" if it.get("material") in M.SHEETS
                    else f"{M.nominal(t)} sheet", "outline": pts, "holes": holes, "size": pts.max(axis=0)})
    return out


def _rectangle(pts: np.ndarray, size) -> bool:
    return len(pts) == 4 and all(min(abs(x), abs(x - size[0])) < 0.5 and min(abs(y), abs(y - size[1])) < 0.5
                                 for x, y in pts)


# ---------------------------------------------------------------------------
# Drawing (Pillow)
# ---------------------------------------------------------------------------
def _font(px: int):
    from PIL import ImageFont

    return ImageFont.load_default(size=px)


def _page(landscape: bool = False):
    from PIL import Image, ImageDraw

    w, h = (PAGE[1], PAGE[0]) if landscape else PAGE
    img = Image.new("RGB", (round(w * DPI), round(h * DPI)), "white")
    return img, ImageDraw.Draw(img)


def _ruler(dr, x0: float, y0: float):
    """A 3 in ruler with 1/4 in ticks at (x0, y0) px: the scale check on every full-size page."""
    px = DPI
    dr.line([(x0, y0), (x0 + 3 * px, y0)], fill="black", width=2)
    for q in range(13):
        tall = 14 if q % 4 == 0 else 7
        dr.line([(x0 + q * px / 4, y0), (x0 + q * px / 4, y0 - tall)], fill="black", width=2 if q % 4 == 0 else 1)
    dr.text((x0 + 3 * px + 8, y0 - 16), "3 in: measure it. If it isn't, print at 100% (no fit to page).",
            fill="black", font=_font(13))


def measure_page(pc: dict):
    """Measure and mark: the piece to fit a landscape page, on its 1 in grid, dimensioned from its square
    edges."""
    img, dr = _page(landscape=True)
    W, H = img.size
    left, top, right, bottom = 1.0 * DPI, 1.35 * DPI, W - 0.6 * DPI, H - 1.0 * DPI
    sx, sy = pc["size"]
    k = min((right - left) / sx, (bottom - top) / sy)          # px per mm
    X = lambda x: left + x * k                                  # noqa: E731
    Y = lambda y: bottom - y * k                                # noqa: E731
    f, small, big = _font(15), _font(12), _font(24)
    # the 1 in grid, numbered from the bottom-left corner
    for i in range(int(sx // IN) + 1):
        dr.line([(X(i * IN), Y(0)), (X(i * IN), Y(sy))], fill=(215, 215, 215), width=1)
        dr.text((X(i * IN) - 4, Y(0) + 6), str(i), fill=(120, 120, 120), font=small)
    for j in range(int(sy // IN) + 1):
        dr.line([(X(0), Y(j * IN)), (X(sx), Y(j * IN))], fill=(215, 215, 215), width=1)
        dr.text((X(0) - 22, Y(j * IN) - 7), str(j), fill=(120, 120, 120), font=small)
    dr.polygon([(X(x), Y(y)) for x, y in pc["outline"]], outline="black", width=4)
    for n, h in enumerate(pc["holes"], 1):
        dr.polygon([(X(x), Y(y)) for x, y in h], fill=(235, 235, 235), outline="black", width=3)
        cx, cy = h.mean(axis=0)
        dr.text((X(cx) - 10, Y(cy) - 14), f"H{n}", fill="black", font=big)
    # overall size: dimension lines along the bottom and up the left
    _dimension(dr, (X(0), Y(0) + 40), (X(sx), Y(0) + 40), inches(sx), f)
    _dimension(dr, (X(0) - 60, Y(0)), (X(0) - 60, Y(sy)), inches(sy), f)
    # the title and how to read it
    dr.text((0.6 * DPI, 0.35 * DPI), f"{pc['name']}: {pc['label']}", fill="black", font=big)
    lines = ["Measure everything from the bottom-left corner: the bottom edge and the left edge are straight "
             "and square. Grid lines are 1 in."]
    if not _rectangle(pc["outline"], pc["size"]):
        lines.append("Corners: " + "; ".join(f"({inches(x)}, {inches(y)})" for x, y in pc["outline"]))
    for n, h in enumerate(pc["holes"], 1):
        lo, hi = h.min(axis=0), h.max(axis=0)
        c = h.mean(axis=0)
        r = np.linalg.norm(h - c, axis=1)
        if len(h) >= 12 and r.std() < 0.02 * r.mean():            # round: a hole saw, from its centre
            lines.append(f"H{n}: a {inches(2 * r.mean())} hole saw, centred {inches(c[0])} from the left and "
                         f"{inches(c[1])} up.")
            continue
        lines.append(f"H{n}: {inches(lo[0])} from the left, {inches(lo[1])} up; {inches(hi[0] - lo[0])} wide, "
                     f"{inches(hi[1] - lo[1])} tall. Draw the grid there and copy its curve square by square, or "
                     f"trace it from the full-size pages. Drill a 3/8 in hole inside the line to start the jigsaw.")
    import textwrap

    wrapped = [w for ln in lines for w in textwrap.wrap(ln, 175)]
    for i, ln in enumerate(wrapped[:7]):
        dr.text((0.6 * DPI, 0.72 * DPI + i * 16), ln, fill=(60, 60, 60), font=small)
    return img


def _dimension(dr, a, b, text: str, font):
    """A dimension line from a to b (px) with arrowheads and its length written beside it."""
    (x0, y0), (x1, y1) = a, b
    dr.line([a, b], fill="black", width=2)
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    for (px, py), s in ((a, 1), (b, -1)):
        tip = [(px, py), (px + s * (12 * ux - 5 * uy), py + s * (12 * uy + 5 * ux)),
               (px + s * (12 * ux + 5 * uy), py + s * (12 * uy - 5 * ux))]
        dr.polygon(tip, fill="black")
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    w = dr.textlength(text, font=font)
    if abs(ux) > abs(uy):                       # horizontal: the text on a white gap in the line
        dr.rectangle([mx - w / 2 - 6, my - 10, mx + w / 2 + 6, my + 10], fill="white")
        dr.text((mx - w / 2, my - 9), text, fill="black", font=font)
    else:
        dr.rectangle([mx - w / 2 - 6, my - 10, mx + w / 2 + 6, my + 10], fill="white")
        dr.text((mx - w / 2, my - 9), text, fill="black", font=font)


def tiles(pc: dict) -> tuple[list, tuple[int, int], bool]:
    """Print and tape: the piece at full size across letter pages, a map page first. Returns
    ``(pages, (cols, rows), landscape)``."""
    sx, sy = pc["size"] + 2 * BORDER
    best = None
    for landscape in (False, True):
        pw, ph = (PAGE[1], PAGE[0]) if landscape else PAGE
        step = ((pw - 2 * MARGIN - OVERLAP) * IN, (ph - 2 * MARGIN - OVERLAP) * IN)
        cols = max(1, math.ceil((sx - OVERLAP * IN) / step[0]))
        rows = max(1, math.ceil((sy - OVERLAP * IN) / step[1]))
        if best is None or cols * rows < best[0] * best[1]:
            best = (cols, rows, landscape, step)
    cols, rows, landscape, step = best
    k = DPI / IN                                                 # px per mm, at true size
    pages = [_map(pc, cols, rows, step)]
    for r in range(rows):
        for c in range(cols):
            img, dr = _page(landscape)
            W, H = img.size
            x0 = c * step[0] - BORDER                            # piece mm at the page's printable left
            y0 = (rows - 1 - r) * step[1] - BORDER               # and at its printable bottom (row 1 on top)
            X = lambda x: MARGIN * DPI + (x - x0) * k            # noqa: E731
            Y = lambda y: H - MARGIN * DPI - (y - y0) * k        # noqa: E731
            # the overlap with the next page right and the next page down, shaded
            ov = OVERLAP * DPI
            if c < cols - 1:
                dr.rectangle([W - MARGIN * DPI - ov, MARGIN * DPI, W - MARGIN * DPI, H - MARGIN * DPI], fill=(242, 242, 242))
            if r < rows - 1:
                dr.rectangle([MARGIN * DPI, H - MARGIN * DPI - ov, W - MARGIN * DPI, H - MARGIN * DPI], fill=(242, 242, 242))
            for i in range(int(x0 // IN), int((x0 + step[0] + OVERLAP * IN) // IN) + 2):     # 1 in grid
                dr.line([(X(i * IN), MARGIN * DPI), (X(i * IN), H - MARGIN * DPI)], fill=(225, 225, 225), width=1)
            for j in range(int(y0 // IN), int((y0 + step[1] + OVERLAP * IN) // IN) + 2):
                dr.line([(MARGIN * DPI, Y(j * IN)), (W - MARGIN * DPI, Y(j * IN))], fill=(225, 225, 225), width=1)
            dr.polygon([(X(x), Y(y)) for x, y in pc["outline"]], outline="black", width=3)
            for h in pc["holes"]:
                dr.polygon([(X(x), Y(y)) for x, y in h], outline="black", width=3)
            # the margins: printers don't print there, so it's blank again
            for box in ([0, 0, W, MARGIN * DPI], [0, H - MARGIN * DPI, W, H], [0, 0, MARGIN * DPI, H],
                        [W - MARGIN * DPI, 0, W, H]):
                dr.rectangle(box, fill="white")
            label = f"{chr(65 + r)}{c + 1}"
            dr.text((MARGIN * DPI, 6), f"{pc['name']}, page {label} ({r * cols + c + 1} of {rows * cols})"
                    + (f" · overlaps {chr(65 + r)}{c + 2} on the right" if c < cols - 1 else "")
                    + (f" · overlaps {chr(66 + r)}{c + 1} below" if r < rows - 1 else ""),
                    fill="black", font=_font(13))
            _ruler(dr, W - MARGIN * DPI - 3 * DPI - 330, MARGIN * DPI - 6)
            pages.append(img)
    return pages, (cols, rows), landscape


def _map(pc: dict, cols: int, rows: int, step) -> object:
    """The first page for a piece: how its pages go together."""
    img, dr = _page(landscape=True)
    W, H = img.size
    sx, sy = pc["size"] + 2 * BORDER
    k = min((W - 2 * DPI) / (cols * step[0] + OVERLAP * IN), (H - 2.6 * DPI) / (rows * step[1] + OVERLAP * IN))
    ox, oy = DPI, H - 0.8 * DPI
    X = lambda x: ox + (x + BORDER) * k                          # noqa: E731
    Y = lambda y: oy - (y + BORDER) * k                          # noqa: E731
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * step[0] - BORDER, (rows - 1 - r) * step[1] - BORDER
            box = [X(x0), Y(y0 + step[1] + OVERLAP * IN), X(x0 + step[0] + OVERLAP * IN), Y(y0)]
            dr.rectangle(box, outline=(150, 150, 150), width=2)
            dr.text((box[0] + 8, box[1] + 6), f"{chr(65 + r)}{c + 1}", fill=(110, 110, 110), font=_font(22))
    dr.polygon([(X(x), Y(y)) for x, y in pc["outline"]], outline="black", width=3)
    for h in pc["holes"]:
        dr.polygon([(X(x), Y(y)) for x, y in h], outline="black", width=2)
    dr.text((0.6 * DPI, 0.35 * DPI), f"{pc['name']}: {pc['label']}, full size on {cols * rows} page(s)",
            fill="black", font=_font(24))
    import textwrap

    say = ("Print at 100% (no fit to page) and check the 3 in ruler on each page. Trim each page's right and "
           "bottom margins, lay it over the next page so its grey strip covers the matching strip and the grid "
           "lines meet, and tape. Then tape the pattern to the board, or prick through the line every inch with "
           "an awl and join the dots. A hole: drill a 3/8 in hole inside its line to start the jigsaw.")
    for i, ln in enumerate(textwrap.wrap(say, 175)):
        dr.text((0.6 * DPI, 0.75 * DPI + i * 16), ln, fill=(60, 60, 60), font=_font(12))
    return img


def project_svg(pc: dict) -> str:
    """Project and trace: the piece at full size, white on black, and a calibration square."""
    sx, sy = pc["size"]
    cal = CALIBRATE_IN * IN
    pad = 1.0 * IN
    w, h = sx + cal + 3 * pad, max(sy, cal) + 2 * pad + 0.6 * IN
    fmt = lambda pts: " ".join(f"{x + pad:.2f},{h - pad - y:.2f}" for x, y in pts)   # noqa: E731
    grid = "".join(f'<line x1="{pad + i * IN:.1f}" y1="{h - pad:.1f}" x2="{pad + i * IN:.1f}" y2="{h - pad - sy:.1f}"/>'
                   for i in range(int(sx // IN) + 1))
    grid += "".join(f'<line x1="{pad:.1f}" y1="{h - pad - j * IN:.1f}" x2="{pad + sx:.1f}" y2="{h - pad - j * IN:.1f}"/>'
                    for j in range(int(sy // IN) + 1))
    cx = pad * 2 + sx
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w / IN:.3f}in" height="{h / IN:.3f}in" '
            f'viewBox="0 0 {w:.2f} {h:.2f}">'
            f'<rect width="100%" height="100%" fill="black"/>'
            f'<g stroke="#3a3a3a" stroke-width="0.5">{grid}</g>'
            f'<polygon points="{fmt(pc["outline"])}" fill="none" stroke="white" stroke-width="1.2"/>'
            + "".join(f'<polygon points="{fmt(hp)}" fill="none" stroke="white" stroke-width="1.2"/>' for hp in pc["holes"])
            + f'<rect x="{cx:.2f}" y="{h - pad - cal:.2f}" width="{cal:.2f}" height="{cal:.2f}" fill="none" '
              f'stroke="#ffd166" stroke-width="1.2"/>'
            f'<text x="{cx:.2f}" y="{h - pad - cal - 4:.2f}" fill="#ffd166" font-size="7" font-family="sans-serif">'
            f'zoom until this is {CALIBRATE_IN:g} in square</text>'
            f'<text x="{pad:.2f}" y="{0.5 * IN:.2f}" fill="white" font-size="9" font-family="sans-serif">'
            f'{html.escape(pc["name"])}: {html.escape(pc["label"])}. Line the board\'s corner up with the bottom-left '
            f'corner, then trace.</text></svg>')


# ---------------------------------------------------------------------------
# Making them, and keeping them with the design
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "patterns")


def make(store: DesignStore, part_id: str, out_dir: Optional[str] = None) -> dict:
    """Every flat sheet piece of a part, three ways. Returns the record (its files relative to its folder)."""
    pcs = pieces(store, part_id)
    if not pcs:
        raise ValueError(f"'{part_id}' has no flat sheet pieces to make patterns of")
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    root = out_dir or os.path.join(runs_dir(store), rid)
    os.makedirs(root, exist_ok=True)
    measure, full, files, listed = [], [], [], []
    for pc in pcs:
        page = measure_page(pc)
        measure.append(page)
        thumb = f"{_slug(pc['name'])}.png"
        page.resize((page.width // 3, page.height // 3)).save(os.path.join(root, thumb))
        pages, (cols, rows), _ = tiles(pc)
        full += pages
        svg = f"project-{_slug(pc['name'])}.svg"
        with open(os.path.join(root, svg), "w") as f:
            f.write(project_svg(pc))
        listed.append({"name": pc["name"], "label": pc["label"], "size_in": [round(v / IN, 3) for v in pc["size"]],
                       "holes": len(pc["holes"]), "pages": cols * rows, "project": svg, "thumb": thumb})
        files += [thumb, svg]
    measure[0].save(os.path.join(root, "measure-and-mark.pdf"), save_all=True, append_images=measure[1:],
                    resolution=DPI)
    full[0].save(os.path.join(root, "print-full-size.pdf"), save_all=True, append_images=full[1:], resolution=DPI)
    files += ["measure-and-mark.pdf", "print-full-size.pdf", "index.html"]
    rec = {"id": rid, "part": part_id, "version": store.design.part(part_id).version, "created": time.time(),
           "pieces": listed, "pages": len(full), "files": files}
    with open(os.path.join(root, "index.html"), "w") as f:
        f.write(index_html(store.design.name, part_id, listed, len(full)))
    with open(os.path.join(root, "run.json"), "w") as f:
        json.dump(rec, f, indent=2)
    if out_dir is None:
        store.append_history(part_id, {"kind": "patterns", "action": "made", "run": rid, "pieces": len(listed)})
        store.append_log({"kind": "patterns", "action": "made", "part": part_id, "run": rid})
    return rec


def index_html(design: str, part_id: str, listed: list[dict], pages: int) -> str:
    e = html.escape
    rows = "".join(f"<tr><td><img src='{e(p['thumb'])}' width='220'></td><td><b>{e(p['name'])}</b><br>{e(p['label'])}"
                   f"<br>{p['size_in'][0]:g} × {p['size_in'][1]:g} in · {p['holes']} hole(s) · {p['pages']} page(s) full size"
                   f"<br><a href='{e(p['project'])}'>project and trace</a></td></tr>" for p in listed)
    return (f"<!doctype html><meta charset='utf-8'><title>Patterns: {e(part_id)}</title>"
            f"<style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:24px auto;color:#222}}"
            f"td{{padding:8px;vertical-align:top;border-bottom:1px solid #ddd}}</style>"
            f"<h1>{e(design)}: {e(part_id)}, for hand tools</h1>"
            f"<p><a href='measure-and-mark.pdf'><b>Measure and mark</b></a>: one page a piece, dimensioned from "
            f"its square edges, on a 1 in grid.<br><a href='print-full-size.pdf'><b>Print and tape</b></a>: full size, "
            f"{pages} letter pages; print at 100% and check the ruler.<br><b>Project and trace</b>: open a piece's "
            f"pattern full screen on a projector, zoom until the yellow square is 4 in, and trace.</p>"
            f"<table>{rows}</table>")


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        p = os.path.join(root, rid, "run.json")
        if os.path.exists(p):
            with open(p) as f:
                rec = json.load(f)
            if part_id is None or rec.get("part") == part_id:
                out.append(rec)
    return out


def file_path(store: DesignStore, rid: str, name: str) -> str:
    if not rid or "/" in rid or ".." in rid or "/" in name or ".." in name:
        raise ValueError("bad path")
    return os.path.join(runs_dir(store), rid, name)
