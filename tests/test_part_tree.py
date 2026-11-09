"""CALI-102 (#94, slice a) — the part tree: every part and its pieces, named, coloured, shown or hidden. Names are labels:
the id that scripts, history, runs and files key on never changes. Stubbed: no FEA, no Claude."""

import os

import pytest
import trimesh

from caliper import answers, design_api, firstrun, release, tree
from caliper.design import DesignStore

from .test_beam_width import TOP
from .test_mixed import MIXED
from .test_resolved import TUBE

pytest.importorskip("cadquery")


def _store(tmp_path, src=TOP, pid="bench"):
    s = DesignStore.create(f"a {pid}", base=str(tmp_path / "designs"))
    s.write_part(pid, src, intent=f"a {pid}")
    return s


def _load(data):
    import io

    return trimesh.load(io.BytesIO(data), file_type="stl")


# --- the pieces, their colours and the legend --------------------------------------------------------------------------

def test_a_part_s_pieces_come_with_their_material_and_colour(tmp_path):
    store = _store(tmp_path)
    got = tree.pieces(store, "bench")
    assert [p["key"] for p in got] == ["top", "front", "back"] and all(p["kind"] == "sheet" for p in got)
    assert got[0] == {"key": "top", "name": "top", "labelled": False, "kind": "sheet", "material": "softwood plywood",
                      "legend": "1/2 in softwood plywood", "color": tree.COLOURS["plywood"]}
    state = design_api.design_state(store)
    assert state["parts"][0]["pieces"] == got
    assert state["legend"] == [{"label": "1/2 in softwood plywood", "color": tree.COLOURS["plywood"], "count": 1},
                               {"label": "3/4 in softwood plywood", "color": tree.COLOURS["plywood"], "count": 2}]


def test_a_printed_part_is_one_piece_in_its_own_colour(tmp_path):
    store = _store(tmp_path, TUBE, "tube")
    (pc,) = tree.pieces(store, "tube")
    assert (pc["key"], pc["kind"], pc["material"], pc["color"]) == ("tube", "printed", "PETG", tree.COLOURS["petg"])


def test_two_pieces_with_one_name_keep_apart(tmp_path):
    src = TOP.replace('{"name": "back", "kind": "sheet"', '{"name": "front", "kind": "sheet"')
    store = _store(tmp_path, src)
    assert [p["key"] for p in tree.pieces(store, "bench")] == ["top", "front", "front 2"]


# --- each piece's solid, for the viewport ------------------------------------------------------------------------------

def test_each_piece_has_a_solid_where_it_sits(tmp_path):
    store = _store(tmp_path)
    top = tree.mesh(store, "bench", "top")
    (x0, y0, z0), (x1, y1, z1) = top.bounds
    assert (x1 - x0, y1 - y0) == pytest.approx((900, 300), abs=0.5) and z1 - z0 == pytest.approx(12.7, abs=0.01)
    assert z0 == pytest.approx(200 - 12.7, abs=0.5)                                   # the top's under its outside face


def test_the_printed_rest_is_the_part_less_its_sheets(tmp_path):
    store = _store(tmp_path, MIXED, "stool")
    keys = {p["kind"]: p["key"] for p in tree.pieces(store, "stool")}
    whole = store.part_geometry("stool").require_mesh()
    rest, sheet = tree.mesh(store, "stool", keys["printed"]), tree.mesh(store, "stool", keys["sheet"])
    assert rest.volume < whole.volume and rest.volume + sheet.volume == pytest.approx(whole.volume, rel=0.05)


def test_a_piece_goes_with_the_part_s_pose(tmp_path):
    store = _store(tmp_path)
    next(p for p in store.assembly.parts if p.id == "bench").position = (0.0, 0.0, 500.0)
    store.save()
    assert tree.mesh(store, "bench", "top").bounds[1][2] == pytest.approx(700, abs=0.5)


def test_the_route_serves_a_piece_or_says_it_has_none(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/bench/piece.stl", params={"key": "top"})
    assert got.status_code == 200 and _load(got.content).is_watertight
    assert c.get(f"/api/designs/{slug}/parts/bench/piece.stl", params={"key": "lid"}).status_code == 404


# --- names are labels, not ids -----------------------------------------------------------------------------------------

def test_a_rename_round_trips_and_the_id_stays(tmp_path):
    store = _store(tmp_path)
    script, folder = store.read_script("bench"), store.part_dir("bench")
    tree.set_label(store, "bench", "  Garden   bench ")
    tree.set_label(store, "bench", "seat", piece="top")
    store = DesignStore.load(store.root)
    assert store.design.part("bench").label == "Garden bench" and store.part_dir("bench") == folder
    assert store.read_script("bench") == script and store.design.part("bench").version == 1
    (p,) = design_api.design_state(store)["parts"]
    assert (p["id"], p["label"], p["name"]) == ("bench", "Garden bench", "Garden bench")
    assert [x["name"] for x in p["pieces"]] == ["seat", "front", "back"] and p["pieces"][0]["key"] == "top"
    tree.set_label(store, "bench", "")                                                # back to its id
    tree.set_label(store, "bench", "top", piece="top")
    (p,) = design_api.design_state(DesignStore.load(store.root))["parts"]
    assert (p["label"], p["name"]) == (None, "bench") and not p["pieces"][0]["labelled"]


def test_a_design_from_before_labels_reads_as_it_did(tmp_path):
    import yaml

    store = _store(tmp_path)
    path = os.path.join(store.root, "design.yaml")
    data = yaml.safe_load(open(path))
    data.pop("piece_labels", None)
    for p in data["parts"]:
        p.pop("label", None)
    yaml.safe_dump(data, open(path, "w"))
    store = DesignStore.load(store.root)
    (p,) = design_api.design_state(store)["parts"]
    assert p["name"] == "bench" and p["label"] is None and store.design.piece_labels == {}


@pytest.mark.parametrize("pid,label,piece,why", [
    ("nope", "x", None, "there's no part 'nope'"), ("bench", "x", "lid", "bench has no piece 'lid'"),
    ("bench", "y" * 61, None, "a name is at most 60 characters"),
])
def test_a_rename_that_can_t_be_is_refused(tmp_path, pid, label, piece, why):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match=f"^{why}$"):
        tree.set_label(store, pid, label, piece)


def test_a_reference_can_t_be_renamed(tmp_path):
    store = _store(tmp_path)
    next(p for p in store.assembly.parts if p.id == "bench").role = "fixed"
    store.save()
    with pytest.raises(ValueError, match="is a reference"):
        tree.set_label(store, "bench", "my car")


def test_the_route_renames(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.post(f"/api/designs/{slug}/parts/bench/label", json={"label": "Garden bench"})
    assert got.status_code == 200 and got.json()["parts"][0]["name"] == "Garden bench"
    assert c.post(f"/api/designs/{slug}/parts/bench/label", json={"label": "x", "piece": "lid"}).status_code == 422


def test_the_cards_and_the_build_book_read_the_label(tmp_path):
    store = _store(tmp_path, TUBE, "i_want")
    tree.set_label(store, "i_want", "Bar stool")
    state = design_api.design_state(store)
    assert answers.part_name(state["parts"][0]) == "Bar stool"
    store.write_part("other", TUBE, intent="other")
    state = design_api.design_state(store)
    design = next(c for c in answers.design(store, state) if c["key"] == "what")
    assert any(ln["text"] == "2 parts: Bar stool, other" for ln in design["lines"]), design["lines"]
    book = release.book({"id": "r1", "created": 0, "design": "a stool", "versions": {"i_want": 1},
                         "names": {"i_want": "Bar stool"}},
                        {"summary": {"pass": 0, "fail": 0, "unknown": 1}, "checks": [], "metrics": {}},
                        {"usd": 0, "groups": [], "basis": ""}, {}, [], [])
    assert "Bar stool v1" in book and "i_want v1" not in book


def test_a_one_part_design_s_part_is_called_what_the_design_is(tmp_path):
    from .test_chat import _author, _box

    store = DesignStore.create("I want to make a bar stool to hold 250 lb.", base=str(tmp_path / "designs"))
    assert store.design.name == "Bar stool"
    got = firstrun.build(store, use_llm=False, author=_author(_box()), strength=False)
    assert got["ok"] and store.design.part(got["part"]).label == "Bar stool"
