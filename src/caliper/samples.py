"""CALI-59 (#8) — sample designs to open: the step stool and the camper, as they were built.

A sample is a design folder shipped inside Caliper (``caliper/samples/<name>/``). It holds the parts with
every version, the conversation, what the design is held to, and the newest run of each study and plan,
so its four cards read full as soon as it opens. Opening one copies it into your designs: what you change
is yours, and the sample stays as it was.

``save()`` makes one from a design of yours (``caliper sample save <slug> <name>``). It keeps the newest
run per study and part, leaves out build packages (one button remakes them) and writes your home folder
as ``~``.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Optional

from .design import DesignStore, designs_dir, slugify

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")
#: The files a design is, and the folders of runs it keeps (each a folder per run, or a file per run).
FILES = ("design.yaml", "assembly.yaml", "log.jsonl", "scorecard.yaml")
RUNS = ("loads", "lighten", "patterns", "cutplans", "frames", "aero", "gussets", "whittle", "searches",
        "scorecards")
TEXT = (".json", ".jsonl", ".yaml", ".txt", ".html", ".svg", ".py", ".csv")
#: The order they're offered in: the small one first.
FIRST = ("step-stool", "camper")


def available(root: Optional[str] = None) -> list[dict]:
    """The samples there are: ``[{"name", "title", "about", "parts"}]``."""
    root = root or SAMPLES_DIR
    out = []
    names = sorted(os.listdir(root)) if os.path.isdir(root) else []
    for name in sorted(names, key=lambda n: (FIRST.index(n) if n in FIRST else len(FIRST), n)):
        try:
            store = DesignStore.load(os.path.join(root, name))
        except Exception:  # noqa: BLE001 — not a design folder
            continue
        about = (store.design.prompt or "").strip().split(". ")[0].rstrip(".") + "."
        out.append({"name": name, "title": store.design.name, "about": about,
                    "parts": [p.id for p in store.design.parts]})
    return out


def open_sample(name: str, base: Optional[str] = None, root: Optional[str] = None) -> DesignStore:
    """A copy of the sample in your designs, under a slug of its own."""
    src = os.path.join(root or SAMPLES_DIR, name)
    if name != os.path.basename(name) or not os.path.isdir(src):
        raise KeyError(f"no sample {name!r}")
    base = base or designs_dir()
    os.makedirs(base, exist_ok=True)
    slug, n = slugify(name), 1
    unique = slug
    while os.path.exists(os.path.join(base, unique)):
        n += 1
        unique = f"{slug}-{n}"
    shutil.copytree(src, os.path.join(base, unique))
    store = DesignStore.load(os.path.join(base, unique))
    store.design.slug = unique
    store.save()
    store.append_log({"kind": "sample", "action": "opened", "sample": name})
    return store


def _part_of(path: str) -> str:
    """Which part a run is of (its record says), so the newest is kept for each."""
    files = [path] if os.path.isfile(path) else [os.path.join(path, f) for f in sorted(os.listdir(path))]
    for f in files:
        if f.endswith(".json"):
            try:
                with open(f) as fh:
                    return str(json.load(fh).get("part") or "")
            except (OSError, ValueError, AttributeError):
                continue
    return ""


def save(slug: str, name: str, base: Optional[str] = None, out: Optional[str] = None) -> str:
    """Snapshot one of your designs as a sample. Returns where it went."""
    store = DesignStore.load(slug, base=base)
    dest = os.path.join(out or SAMPLES_DIR, name)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    for f in FILES:
        if os.path.exists(os.path.join(store.root, f)):
            shutil.copy2(os.path.join(store.root, f), os.path.join(dest, f))
    shutil.copytree(os.path.join(store.root, "parts"), os.path.join(dest, "parts"))
    for kind in RUNS:
        folder = os.path.join(store.root, kind)
        if not os.path.isdir(folder):
            continue
        newest: dict = {}
        for run in sorted(os.listdir(folder)):            # named by time: the last of each part is the newest
            newest[_part_of(os.path.join(folder, run))] = run
        for run in newest.values():
            a, b = os.path.join(folder, run), os.path.join(dest, kind, run)
            os.makedirs(os.path.dirname(b), exist_ok=True)
            (shutil.copytree if os.path.isdir(a) else shutil.copy2)(a, b)
    home = os.path.expanduser("~")
    for here, _, files in os.walk(dest):
        for f in files:
            if f.endswith(TEXT):
                p = os.path.join(here, f)
                with open(p, encoding="utf-8", errors="surrogateescape") as fh:
                    text = fh.read()
                if home in text:
                    with open(p, "w", encoding="utf-8", errors="surrogateescape") as fh:
                        fh.write(text.replace(home, "~"))
    return dest
