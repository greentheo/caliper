"""A Lighten step's patterns and cut plan, seen before its holes are cut into the part (CALI-186, #297 part 2).

Theo, 2026-11-14: "when I select a 'lighten', i selected 16 … it doesn't appear that I can then make the relevant cut plan".
Cutting a step's holes in writes a version; to see what the step would be cut from, he'd have had to. A preview builds
the patterns or the cut plan from the script cutting them in would write (:func:`caliper.lighten.station_script`), in a
scratch copy of the design: never the design's versions, history, log, patterns or cut plans. Every file it makes is
named ``preview…`` and says on it that it isn't the part yet. It's made once per (run, step, what) and kept under the
design's ``previews/``, the newest :data:`KEEP` of them; the scratch copy goes whether it worked or not (#304's lesson).
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import tempfile
import uuid
from typing import Callable, Optional

from .design import DesignStore

#: What a step can be previewed as.
WHAT = ("patterns", "cutplan")
#: Previews kept per design, the most recently made or opened first.
KEEP = 6
#: A study's file bigger than this is its mesh or voxels, not its record: the scratch copy leaves it out. Grain reads a
#: strength check's run.json (its beam's span); a load case's voxels are megabytes (the bar stool's: 9 MB each).
SMALL = 1 << 20
#: The design's folders a preview never reads: what's made from it, and the runs whose records are big and beside the point.
LEAVE_OUT = {"previews", "patterns", "cutplans", "releases", "lighten", "trash"}


def stamp(rid: str, index: int) -> str:
    return f"step {int(index)} of lightening {rid}"


def folder(store: DesignStore, rid: str, index: int, what: str) -> str:
    """Where a preview is kept: ``previews/<run>-<step>/<what>/``."""
    if what not in WHAT:
        raise ValueError(f"a step is previewed as its patterns or cutplan, not {what!r}")
    if not rid or "/" in rid or "\\" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(store.root, "previews", f"{rid}-{int(index):02d}", what)


def station(store: DesignStore, rid: str, index: int, what: str) -> tuple[str, str]:
    """The part and the script a preview is built from, refusing what cutting the step in refuses, and step 0."""
    from . import lighten

    folder(store, rid, index, what)
    pid, script = lighten.station_script(store, rid, index)
    if int(index) == 0:
        raise ValueError("step 0 is the part as it is: nothing to preview")
    return pid, script


def copy_design(src: str, dst: str) -> None:
    """The design as a preview reads it: its files, its parts' scripts and specs without their versions, and its studies'
    records without their meshes."""
    for dp, dirs, files in os.walk(src):
        rel = os.path.relpath(dp, src)
        top = "" if rel == "." else rel.split(os.sep)[0]
        dirs[:] = sorted(d for d in dirs if d != "versions" and not (rel == "." and d in LEAVE_OUT))
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            p = os.path.join(dp, f)
            if top in ("", "parts") or os.path.getsize(p) <= SMALL:
                shutil.copy2(p, os.path.join(dst, rel, f))


def _made_from(store: DesignStore, script: str) -> str:
    """What a kept preview was made of: the step's script and the design's own file (grain, say, is kept there)."""
    h = hashlib.sha1(script.encode())
    try:
        with open(os.path.join(store.root, "design.yaml"), "rb") as f:
            h.update(f.read())
    except OSError:
        pass
    return h.hexdigest()


def make(store: DesignStore, rid: str, index: int, what: str, *, emit: Optional[Callable] = None,
         timeout: float = 180.0) -> dict:
    """The step's patterns or cut plan, made in a scratch copy and kept under ``previews/``. Returns its record, with
    ``preview`` (what it's of), ``index`` (the page to open) and ``cached`` when it was already made."""
    emit = emit or (lambda *a, **k: None)
    pid, script = station(store, rid, index, what)
    out = folder(store, rid, index, what)
    made_from = _made_from(store, script)
    kept = os.path.join(out, "preview.json")
    if os.path.exists(kept):
        with open(kept) as f:
            rec = json.load(f)
        if rec.get("made_from") == made_from:
            os.utime(os.path.dirname(out))                        # opened again: kept a while longer
            return {**rec, "cached": True}
    words = stamp(rid, index)
    tmp = tempfile.mkdtemp(prefix="caliper-preview-")
    landing = None
    try:
        root = os.path.join(tmp, "design")
        copy_design(store.root, root)
        with open(os.path.join(root, os.path.relpath(store.script_path(pid), store.root)), "w") as f:
            f.write(script)
        copy = DesignStore.load(root)
        stage = os.path.join(tmp, "out")
        emit("previewing", f"{words}: its {'cut plan' if what == 'cutplan' else 'patterns'}, in a scratch copy")
        if what == "patterns":
            from . import patterns

            rec = patterns.make(copy, pid, out_dir=stage, stamp=words)
        else:
            rec = _cutplan(copy, pid, stage, words, emit, timeout)
        rec["preview"] = {"run": rid, "station": int(index), "what": what, "of_version": store.design.part(pid).version}
        rec["made_from"] = made_from
        with open(os.path.join(stage, "preview.json"), "w") as f:
            json.dump(rec, f, indent=2)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        landing = os.path.join(os.path.dirname(out), f".{what}-{uuid.uuid4().hex[:6]}")
        shutil.copytree(stage, landing)                           # whole, then in place: never half a preview kept
        if os.path.exists(out):
            shutil.rmtree(out)
        os.replace(landing, out)
        landing = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if landing:
            shutil.rmtree(landing, ignore_errors=True)
    os.utime(os.path.dirname(out))
    _prune(store)
    return rec


def _prune(store: DesignStore) -> None:
    base = os.path.join(store.root, "previews")
    got = [d for d in os.listdir(base) if not d.startswith(".") and os.path.isdir(os.path.join(base, d))]
    got.sort(key=lambda d: (os.path.getmtime(os.path.join(base, d)), d), reverse=True)
    for d in got[KEEP:]:
        shutil.rmtree(os.path.join(base, d), ignore_errors=True)


def _cutplan(copy: DesignStore, pid: str, stage: str, words: str, emit: Callable, timeout: float) -> dict:
    """The cut plan of the copy, its every file renamed ``preview-…`` and its record and cut list saying so."""
    from . import cutplan

    rec = cutplan.run(copy, pid, emit=emit, timeout=timeout)
    src = os.path.join(cutplan.runs_dir(copy), rec["id"])
    os.makedirs(stage, exist_ok=True)
    for dp, _, files in os.walk(src):
        rel = os.path.relpath(dp, src)
        parts = [] if rel == "." else rel.split(os.sep)
        to = os.path.join(stage, *([f"preview-{parts[0]}"] + parts[1:] if parts else []))
        os.makedirs(to, exist_ok=True)
        for f in files:
            if f not in ("cutplan.json", "cutlist.txt") or parts:
                shutil.copy2(os.path.join(dp, f), os.path.join(to, f"preview-{f}"))
    for g in rec.get("sheets") or []:                             # its record names its files as they are now
        for f in g.get("files") or []:
            d, b = os.path.split(f["name"])
            f["name"] = os.path.join(d, f"preview-{b}") if d else f"preview-{b}"
    with open(os.path.join(src, "cutlist.txt")) as f:
        text = f.read()
    with open(os.path.join(stage, "preview-cutlist.txt"), "w") as f:
        f.write(f"PREVIEW, not the part yet: {words}. Cut its holes into the part to make this its cut plan.\n\n{text}")
    rec["index"] = "preview.html"
    with open(os.path.join(stage, "preview-cutplan.json"), "w") as f:
        json.dump(rec, f, indent=2)
    with open(os.path.join(stage, "preview.html"), "w") as f:
        f.write(_cutplan_page(stage, rec, words, text))
    return rec


def _cutplan_page(stage: str, rec: dict, words: str, text: str) -> str:
    """The preview's own page: the sheets as they'd be cut, every file it made, and the cut list."""
    e = html.escape
    files = sorted(os.path.relpath(os.path.join(dp, f), stage).replace(os.sep, "/")
                   for dp, _, fs in os.walk(stage) for f in fs if f != "preview.html")
    sheets = [f for f in files if "/sheets/" in f and f.endswith(".svg")]
    return (f"<!doctype html><meta charset='utf-8'><title>PREVIEW: cut plan of {e(rec.get('name') or rec['part'])}</title>"
            f"<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;color:#222;background:#fff}}"
            f"img{{width:100%;background:#fff;border:1px solid #ddd}}</style>"
            f"<p style='background:#fff3cd;border:2px solid #b8860b;padding:8px 12px'><b>PREVIEW, not the part yet: "
            f"{e(words)}.</b> This is its cut plan as it would be once its holes are cut into the part; cut them in to "
            f"make it the part's. Don't send these files to a machine.</p>"
            f"<h1>Cut plan: {e(rec.get('name') or rec['part'])}</h1>"
            + "".join(f"<p><a href='{e(s)}'><img src='{e(s)}' alt='{e(s)}'></a></p>" for s in sheets)
            + "<h2>Files</h2><ul>" + "".join(f"<li><a href='{e(f)}'>{e(f)}</a></li>" for f in files) + "</ul>"
            + f"<h2>Cut list</h2><pre>{e(text)}</pre>")


def file_path(store: DesignStore, rid: str, index: int, what: str, rel: str) -> str:
    """A file of a kept preview, refusing anything outside it."""
    base = os.path.realpath(folder(store, rid, index, what))
    path = os.path.realpath(os.path.join(base, rel))
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        raise FileNotFoundError(rel)
    return path


def url(slug: str, rid: str, index: int, what: str, name: str) -> str:
    return f"/api/designs/{slug}/previews/{rid}/{int(index)}/{what}/{name}"

