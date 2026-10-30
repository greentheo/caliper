"""CALI-51 — the build package: a released, versioned bundle for the shop."""

import json
import os
import struct
import zipfile
import zlib

import pytest

from caliper import cutplan
from caliper import release as R
from caliper.design import DesignStore

from .test_construction import BOX


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("A crate for the garage. It holds tools", base=str(tmp_path / "designs"))
    s.write_part("crate", BOX, intent="an open crate")
    return s


def _pixels(png: bytes):
    """Width, height and an (x, y) → (r, g, b) lookup for the PNGs ``draw`` writes (8-bit RGB, filter 0)."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    pos, data = 8, b""
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        if png[pos + 4:pos + 8] == b"IDAT":
            data += png[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(data)
    row = 1 + 3 * w

    def at(x, y):
        i = y * row + 1 + 3 * x
        return tuple(raw[i:i + 3])

    return w, h, at


def test_lengths_read_the_way_a_shop_reads_them():
    assert R.inches(304.8) == "12 in"
    assert R.inches(1039.4) == "40 15/16 in"
    assert R.inches(6.35) == "1/4 in"
    assert R.inches(1016.0, sixteenths=False) == "40.0 in"
    assert R.title("A crate for the garage. It holds tools") == "A crate for the garage"


def test_plates_are_bought_as_one_piece_they_nest_on():
    w, h = R._plate_stock([(229, 203)] * 4)
    assert (w, h) == (19, 17)                       # two rows of two, not one strip 37 in long
    assert R._plate_stock([(100, 50)]) == (5, 3)


def test_a_drawing_puts_the_near_piece_in_front():
    # two flat squares, one above the other, seen from above: the higher (nearer) one shows where they overlap
    sq = lambda z, s: [([[-s, -s, z], [s, -s, z], [s, s, z], [-s, s, z]], [])]       # noqa: E731
    far = {"name": "far", "layer": "floor", "kind": "sheet", "color": "#0000ff", "polys": sq(0.0, 400)}
    near = {"name": "near", "layer": "panels", "kind": "sheet", "color": "#ff0000", "polys": sq(200.0, 150)}
    view = R.View([far, near], elevation=70)
    for order in ([far, near], [near, far]):        # whatever order they're handed over in
        w, h, at = _pixels(R.draw(view, [(order, "now")], supersample=1))
        assert (w, h) == (view.w * 2, view.h * 2)
        cx, cy = (int(v * 2) for v in view.xy([0, 0, 200]))
        r, g, b = at(cx, cy)
        assert r > 150 and b < 100                  # the near square, in red
    # a piece that's already on is drawn pale: the step's own pieces stand out
    w, h, at = _pixels(R.draw(view, [([far], "done")], supersample=1))
    r, g, b = at(*(int(v * 2) for v in view.xy([0, 0, 0])))
    assert min(r, g, b) > 120


def test_a_stick_is_a_box_round_its_centreline():
    faces = R._box([0, 0, 0], [0, 0, 1000], 38.1, 88.9)       # a 2x4 standing up
    assert len(faces) == 6
    xs = [q[0] for f, _ in faces for q in f]
    ys = [q[1] for f, _ in faces for q in f]
    assert max(xs) - min(xs) == pytest.approx(88.9, abs=0.01) or max(xs) - min(xs) == pytest.approx(38.1, abs=0.01)
    assert {round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)} == {38.1, 88.9}


needs_unfolder = pytest.mark.skipif(cutplan.available() is not None,
                                    reason=f"no build packages here: {cutplan.available()}")


@needs_unfolder
def test_a_release_files_everything_the_shop_needs(store):
    rec = R.make(store, pdf=False)
    assert rec["id"] == "001" and rec["versions"] == {"crate": 1}
    root = os.path.join(R.releases_dir(store), "001")
    files = set(rec["files"])
    assert {"index.html", "cutlist.txt", "shopping.txt", "shopping.csv", "scorecard.json", "release.json",
            "assembly/finished.png", "source/crate-v001.py", "source/design.yaml"} <= files
    # the sheets, by machine: every nested sheet as DXF, with the 1:1 pattern
    assert any(f.startswith("router/crate-plywood-") and f.endswith("sheet-01.dxf") for f in files)
    assert any(f.startswith("router/crate-xps-") and f.endswith("pattern.pdf") for f in files)
    assert not any(f.endswith("panels.obj") for f in files)
    # the assembly order: the floor, then the posts, then the walls — each with its drawing
    titles = [s["title"] for s in rec["steps"]]
    assert titles[:3] == ["The floor", "The skeleton", "End and side panels"] and titles[-1] == "Finish"
    for s in rec["steps"]:
        with open(os.path.join(root, s["img"]), "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"
    # what to buy, rounded up to what's sold
    with open(os.path.join(root, "shopping.txt")) as f:
        shop = f.read()
    assert "1 sheet" in shop and "1/2 in softwood plywood" in shop and "2x2 SPF lumber" in shop
    assert rec["shopping_usd"] > 0
    book = open(os.path.join(root, "index.html")).read()
    assert "<h1>A crate for the garage</h1>" in book and "Shopping list" in book and "Assembly" in book
    # a scorecard as released: the design here has no goals, so only its own rules — and nothing fails
    assert rec["ready"] is True
    with zipfile.ZipFile(os.path.join(root, rec["zip"])) as z:
        names = z.namelist()
    assert f"{rec['slug']}-release-001/index.html" in names and not any(n.endswith(".zip") for n in names)
    with open(os.path.join(root, "release.json")) as f:
        assert json.load(f)["id"] == "001"
    assert store.history("crate")[-1]["kind"] == "release"


@needs_unfolder
def test_releases_are_numbered_and_reuse_whats_current(store):
    first = R.make(store, pdf=False)
    second = R.make(store, pdf=False)
    assert second["id"] == "002"
    assert second["cutplans"] == first["cutplans"]              # nothing changed: the same cut plan
    assert [r["id"] for r in R.list_releases(store)] == ["002", "001"]
    store.write_part("crate", BOX.replace('"w": 1219.2', '"w": 1000.0'), intent="narrower")
    third = R.make(store, pdf=False)
    assert third["versions"] == {"crate": 2} and third["cutplans"]["crate"] != first["cutplans"]["crate"]


@needs_unfolder
def test_release_files_stay_inside_the_release(store):
    rec = R.make(store, pdf=False)
    assert R.file_path(store, rec["id"], "index.html").endswith("index.html")
    for bad in ("../../design.yaml", "/etc/passwd", "nope.txt"):
        with pytest.raises(FileNotFoundError):
            R.file_path(store, rec["id"], bad)
    assert R.load_release(store, "../x") is None


def test_nothing_to_build_from_is_refused(tmp_path):
    s = DesignStore.create("plain", base=str(tmp_path / "designs"))
    s.write_part("box", "PARAMS = {'w': 1.0}\n\ndef build(params):\n    import cadquery as cq\n"
                        "    return cq.Workplane().box(1, 1, 1)\n")
    if cutplan.available() is None:
        with pytest.raises(ValueError, match="nothing to cut"):
            R.make(s, pdf=False)


@needs_unfolder
def test_the_book_keeps_where_it_should_break_with_room_for_where_it_did(store):
    """CALI-71: the strength check's prediction goes to the shop with the release, ready for the break test."""
    from caliper import load_study

    run = os.path.join(load_study.runs_dir(store), "20261030-000000-test")
    os.makedirs(run)
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({"id": "20261030-000000-test", "part": "crate", "version": 1, "created": 1.0,
                   "cases": [{"name": "Dad standing", "lb": 200, "factor": 2, "safety": 3.11,
                              "breaks_lb": 1240, "governs": "plate"}]}, f)
    rec = R.make(store, pdf=False)
    assert rec["strength"]["crate"][0]["breaks_lb"] == 1240
    book = open(os.path.join(R.releases_dir(store), rec["id"], "index.html")).read()
    assert "Will it hold?" in book and "about 1,240 lb" in book and "______ lb" in book
    # and the patterns for hand tools go with it (CALI-48)
    assert any(f.startswith("hand/crate/") and f.endswith("print-full-size.pdf") for f in rec["files"])
    assert "hand/" in book
