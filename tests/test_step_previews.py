"""CALI-186 (#297) part 2: a picked Lighten step's patterns and cut plan, seen before its holes are cut into the part.

Theo, 2026-11-14: "when I select a 'lighten', i selected 16 … it doesn't appear that I can then make the relevant cut plan".
The patterns and cut plan were of the part as it is; the only way to see the step's was to cut its holes in, a new version.
A preview builds them from the step's HOLES in a scratch copy of the design, never in its versions; every file it makes is
named and stamped preview; it's made once per (run, step); and the scratch folder goes when it's done (#304's lesson).
"""

import json
import os
import re
import tempfile

import pytest

from caliper import lighten, patterns, previews
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

#: A 2 x 2 in hole through the box stool's left wall, as a Lighten station keeps it (test_lighten's HOLES).
HOLE = [[[0, 100, 80], [0, 150.8, 80], [0, 150.8, 130.8], [0, 100, 130.8]]]


def _run_rec(rid="r1", version=1, **over):
    st = {"index": 2, "phase": "walls", "removed": 0.1, "holes": 1, "saved_lb": 0.2, "safety": 2.4, "holds": True,
          "panels": {"left": HOLE}}
    rec = {"id": rid, "kind": "lighten", "part": "stool", "version": version, "material": "softwood plywood",
           "min_safety": 2.0, "part_lb": 9.0,
           "panels": [{"name": "left", "normal": [1, 0, 0], "thickness_mm": 19.05}],
           "stations": [{"index": 0, "phase": "walls", "removed": 0, "holes": 0, "saved_lb": 0, "safety": 3.0,
                         "holds": True, "panels": {}}, st,
                        {"index": 3, "phase": "thinner", "estimate": True, "label": "5/8 in", "saved_lb": 1.0,
                         "safety": 2.1, "holds": True}]}
    rec.update(over)
    return rec


def _put(store, rec):
    d = os.path.join(lighten.runs_dir(store), rec["id"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump(rec, f)


@pytest.fixture
def stool(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))          # every scratch folder lands where we can see it
    os.makedirs(tmp_path / "tmp")
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    _put(store, _run_rec())
    return store


def _state(store):
    """Everything a preview mustn't change: the part's versions, script, history and the design's log."""
    pdir = store.part_dir("stool")
    with open(os.path.join(pdir, "history.jsonl")) as f:
        hist = f.read()
    with open(os.path.join(store.root, "log.jsonl")) as f:
        log = f.read()
    return store.versions("stool"), store.read_script("stool"), hist, log, DesignStore.load(store.root).design.part("stool").version


def _ours(tmp_path):
    """The preview's own scratch folders left behind. Not the sandbox's: that leak is #304's (CALI-191)."""
    return [n for n in os.listdir(tmp_path / "tmp") if n.startswith("caliper-preview-")]


def _files(root):
    return sorted(os.path.relpath(os.path.join(dp, f), root) for dp, _, fs in os.walk(root) for f in fs)


def test_a_step_s_patterns_preview_writes_no_version_and_shows_its_holes(stool, tmp_path):
    before = _state(stool)
    rec = previews.make(stool, "r1", 2, "patterns")
    assert _state(DesignStore.load(stool.root)) == before                      # no version, no history line, no log line
    assert not os.path.exists(patterns.runs_dir(stool))                        # not the design's patterns either
    left = next(p for p in rec["pieces"] if p["name"] == "left")
    assert left["holes"] == 1                                                  # the step's hole, which the part hasn't
    assert next(p for p in patterns.pieces(stool, "stool") if p["name"] == "left")["holes"] == []
    assert rec["preview"] == {"run": "r1", "station": 2, "what": "patterns", "of_version": 1}
    out = previews.folder(stool, "r1", 2, "patterns")
    assert out.startswith(os.path.join(stool.root, "previews") + os.sep)
    assert _ours(tmp_path) == []                                  # the scratch copy is gone (#304)


def test_every_patterns_file_is_named_and_stamped_preview(stool):
    rec = previews.make(stool, "r1", 2, "patterns")
    out = previews.folder(stool, "r1", 2, "patterns")
    names = _files(out)
    assert names and all(os.path.basename(n).startswith("preview") for n in names), names
    assert rec["index"] == "preview-index.html"
    page = open(os.path.join(out, "preview-index.html")).read()
    assert "PREVIEW, not the part yet: step 2 of lightening r1" in page
    for ref in re.findall(r"(?:href|src)='([^']+)'", page):                    # every link is a file it made
        assert ref in names, ref
    svg = open(os.path.join(out, next(n for n in names if n.endswith(".svg")))).read()
    assert "PREVIEW, not the part yet: step 2 of lightening r1" in svg


def test_the_pattern_pages_say_preview_across_their_tops():
    pc = {"name": "left", "label": "3/4 in plywood", "seen": "from the left", "preview": "step 2 of lightening r1"}
    for words in patterns.titles(pc, 2, 1, 0, 1).values():
        assert words.startswith("PREVIEW, not the part yet: step 2 of lightening r1. "), words
        assert words.isascii()                                                 # the pages' font (CALI-86)
    plain = patterns.titles({k: v for k, v in pc.items() if k != "preview"})
    assert not any("PREVIEW" in w for w in plain.values())


def test_it_is_made_once_per_run_and_step(stool, monkeypatch):
    made = []
    real = patterns.make

    def counted(*a, **k):
        made.append(k.get("stamp"))
        return real(*a, **k)

    monkeypatch.setattr(patterns, "make", counted)
    first = previews.make(stool, "r1", 2, "patterns")
    again = previews.make(stool, "r1", 2, "patterns")
    assert made == ["step 2 of lightening r1"] and again["cached"] and not first.get("cached")
    assert {k: v for k, v in again.items() if k != "cached"} == {k: v for k, v in first.items() if k != "cached"}


def test_a_kept_preview_is_made_again_when_the_design_under_it_changed(stool, monkeypatch):
    """Kept by (run, step), but a grain said since is in design.yaml, not the script: what it's made of is checked too."""
    made = []
    real = patterns.make
    monkeypatch.setattr(patterns, "make", lambda *a, **k: made.append(1) or real(*a, **k))
    previews.make(stool, "r1", 2, "patterns")
    with open(os.path.join(stool.root, "design.yaml"), "a") as f:
        f.write("# a grain said since\n")
    again = previews.make(stool, "r1", 2, "patterns")
    assert len(made) == 2 and not again.get("cached")


def test_a_preview_that_fails_leaves_nothing_behind(stool, tmp_path, monkeypatch):
    def broken(*a, **k):
        os.makedirs(k["out_dir"], exist_ok=True)
        open(os.path.join(k["out_dir"], "preview-half.png"), "w").close()
        raise ValueError("drawing went wrong")

    monkeypatch.setattr(patterns, "make", broken)
    with pytest.raises(ValueError, match="drawing went wrong"):
        previews.make(stool, "r1", 2, "patterns")
    assert _ours(tmp_path) == []
    assert not os.path.exists(previews.folder(stool, "r1", 2, "patterns"))     # no half a preview to serve as made
    monkeypatch.undo()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    assert previews.make(stool, "r1", 2, "patterns")["pieces"]                 # and the next try makes it


def test_it_refuses_what_cutting_the_holes_refuses(stool):
    from caliper.carve import Stale

    with pytest.raises(ValueError, match="estimate"):
        previews.make(stool, "r1", 3, "patterns")
    with pytest.raises(FileNotFoundError):
        previews.make(stool, "r1", 9, "patterns")
    with pytest.raises(FileNotFoundError):
        previews.make(stool, "nope", 2, "patterns")
    with pytest.raises(ValueError, match="patterns or cutplan"):
        previews.make(stool, "r1", 2, "pictures")
    with pytest.raises(ValueError, match="nothing to preview"):
        previews.make(stool, "r1", 0, "patterns")                              # step 0 is the part as it is
    _put(stool, _run_rec("r2", version=7))
    with pytest.raises(Stale, match="lighten it again"):
        previews.make(stool, "r2", 2, "patterns")
    _put(stool, _run_rec("r3", material="PETG (printed)"))
    with pytest.raises(ValueError, match="Not trusted"):
        previews.make(stool, "r3", 2, "patterns")
    with pytest.raises(ValueError):
        previews.folder(stool, "../r1", 2, "patterns")


def test_cutting_the_holes_in_still_writes_the_same_script(stool):
    """adopt and the preview share one station_script: what's previewed is what gets cut."""
    pid, script = lighten.station_script(stool, "r1", 2)
    assert pid == "stool" and "HOLES = [" in script
    got = lighten.adopt(stool, "r1", 2)
    assert got["version"] == 2 and stool.read_script("stool") == script


def test_old_previews_are_pruned(stool, monkeypatch):
    def quick(store, part_id, out_dir=None, stamp=None):
        os.makedirs(out_dir, exist_ok=True)
        open(os.path.join(out_dir, "preview-index.html"), "w").close()
        return {"id": "x", "part": part_id, "version": 1, "pieces": [], "pages": 0, "files": ["preview-index.html"],
                "index": "preview-index.html"}

    monkeypatch.setattr(patterns, "make", quick)
    stations = [{"index": 0, "panels": {}, "holds": True}] + [
        {"index": i, "phase": "walls", "removed": 0.1, "holes": 1, "saved_lb": 0.1 * i, "safety": 2.4, "holds": True,
         "panels": {"left": HOLE}} for i in range(1, previews.KEEP + 3)]
    _put(stool, _run_rec("r4", stations=stations))
    for i in range(1, previews.KEEP + 3):
        previews.make(stool, "r4", i, "patterns")
    kept = sorted(os.listdir(os.path.join(stool.root, "previews")))
    assert len(kept) == previews.KEEP and "r4-01" not in kept and f"r4-{previews.KEEP + 2:02d}" in kept


def test_the_copy_leaves_out_what_a_preview_doesn_t_read(stool, tmp_path):
    big = os.path.join(stool.root, "loads", "L1")
    os.makedirs(big)
    with open(os.path.join(big, "run.json"), "w") as f:
        f.write("{}")
    with open(os.path.join(big, "case_00.json"), "wb") as f:
        f.write(b"0" * (previews.SMALL + 1))                                    # a load case's voxels: megabytes
    dst = str(tmp_path / "copy")
    previews.copy_design(stool.root, dst)
    got = _files(dst)
    assert "loads/L1/run.json" in got and "loads/L1/case_00.json" not in got  # grain reads the run, not its voxels
    assert "parts/stool/part.py" in got and not any(n.startswith("parts/stool/versions") for n in got)
    assert not any(n.startswith("lighten/") for n in got)


# --- the cut plan ----------------------------------------------------------------------------------------------------
def test_a_step_s_cut_plan_preview_is_stamped_and_files_no_cut_plan(stool, tmp_path):
    from caliper import cutplan

    if cutplan.available():
        pytest.skip(cutplan.available())
    before = _state(stool)
    rec = previews.make(stool, "r1", 2, "cutplan")
    assert _state(DesignStore.load(stool.root)) == before
    assert cutplan.list_runs(stool) == []                                     # no cut plan filed with the design
    out = previews.folder(stool, "r1", 2, "cutplan")
    names = _files(out)
    assert names and all(os.path.basename(n).startswith("preview") for n in names), names
    assert rec["preview"]["station"] == 2 and rec["index"] == "preview.html"
    text = open(os.path.join(out, "preview-cutlist.txt")).read()
    assert text.startswith("PREVIEW, not the part yet: step 2 of lightening r1")
    for g in rec["sheets"]:                                                    # its record names the files as they are
        for f in g["files"]:
            assert os.path.join(f"preview-{g['key']}", f["name"]) in names, f["name"]
    page = open(os.path.join(out, "preview.html")).read()
    assert "PREVIEW, not the part yet" in page
    for ref in re.findall(r"(?:href|src)='([^']+)'", page):
        assert ref in names, ref
    assert _ours(tmp_path) == []


# --- the API -----------------------------------------------------------------------------------------------------------
@pytest.fixture
def api(stool, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(stool.root))
    return TestClient(create_app()), stool.design.slug


def test_the_preview_route_runs_it_as_a_job_and_serves_its_files(api, stool):
    from caliper import jobs

    from .test_carve_click import _wait

    c, slug = api
    got = c.post(f"/api/designs/{slug}/lighten/r1/stations/2/preview", json={"what": "patterns"})
    assert got.status_code == 200, got.text
    job = jobs.RUNNER.get(got.json()["job_id"])
    _wait(job, 120)
    assert job.status == "done", job.error
    assert job.result["url"] == f"/api/designs/{slug}/previews/r1/2/patterns/preview-index.html"
    page = c.get(job.result["url"])
    assert page.status_code == 200 and "PREVIEW" in page.text and page.headers["content-type"].startswith("text/html")
    assert c.get(f"/api/designs/{slug}/previews/r1/2/patterns/..%2F..%2F..%2Fdesign.yaml").status_code == 404
    assert c.get(f"/api/designs/{slug}/previews/r1/2/patterns/nothing.png").status_code == 404
    bad = c.post(f"/api/designs/{slug}/lighten/r1/stations/2/preview", json={"what": "pictures"})
    assert bad.status_code == 422
    assert c.post(f"/api/designs/{slug}/lighten/r1/stations/3/preview", json={"what": "patterns"}).status_code == 422
    assert c.post(f"/api/designs/{slug}/lighten/zz/stations/2/preview", json={"what": "patterns"}).status_code == 404


# --- the page ----------------------------------------------------------------------------------------------------------
def _note(station, runs=None, what="patterns"):
    from .test_carve_click import _page, _run

    return _run(_page(["previewNote"], consts=["esc"], extra=f"""
const S = {{station: {json.dumps(station)}, design: {{lighten_runs: {json.dumps(runs if runs is not None else [LRUN])}}}}};
out = previewNote({{id: 'stool', name: 'Step stool'}}, '{what}');"""))


LRUN = {"id": "l1", "part": "stool", "stations": [{"index": 0}, {"index": 3, "holes": 4},
                                                  {"index": 5, "estimate": True, "label": "5/8 in"}]}


def test_a_picked_step_offers_its_patterns_and_cut_plan_as_previews():
    html = _note({"part": "stool", "run": "l1", "index": 3}).replace("'", "&#39;")
    assert '<button data-preview="patterns">Preview step 3&#39;s patterns</button>' in html, html
    assert 'data-preview="cutplan"' not in html                              # each section its own: one button each
    cut = _note({"part": "stool", "run": "l1", "index": 3}, what="cutplan").replace("'", "&#39;")
    assert '<button data-preview="cutplan">Preview step 3&#39;s cut plan</button>' in cut and 'data-preview="patterns"' not in cut
    assert "These are of the Step stool as it is, without the step you&#39;re previewing." in html
    for station in ({"part": "stool", "run": "l1", "index": 0},             # the part as it is: nothing to preview
                    {"part": "stool", "run": "l1", "index": 5}):            # an estimate: no holes to cut
        assert "data-preview" not in _note(station)
    assert "data-preview" not in _note({"part": "stool", "run": "l1", "index": 3}, [dict(LRUN, not_trusted="PETG")])


def test_the_preview_buttons_are_wired_to_the_route_and_open_what_it_made():
    from .test_carve_click import _fn

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    body = _fn(src, "previewStep")
    assert "`/api/designs/${S.slug}/lighten/${st.run}/stations/${st.index}/preview`" in body
    assert "await follow(job_id" in body and 'target="_blank"' in body and "got.url" in body
    assert "document.querySelectorAll('[data-preview]')" in src
