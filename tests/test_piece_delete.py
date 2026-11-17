"""CALI-196 (#324): a piece's Delete… and Hide from its menu, as Theo's step_stool v6 needed for its fillet strips.

Synthetic: a top and its fillet strips, the strips skipped where ``fillet_r`` is 0 (as step_stool's ``fillet_r`` does), and a
``fillet_gap`` whose name looks right but turns nothing off."""

import os

import pytest

from caliper import pieces
from caliper.design import DesignStore

pytest.importorskip("cadquery")

STRIPPED = '''import cadquery as cq

PARAMS = {"w": 200.0, "t": 19.05, "fillet_gap": 2.0, "fillet_r": 6.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = cq.Workplane().box(p["w"], p["w"], p["t"], centered=(True, True, False))
    if p["fillet_r"] > 0:
        r, g = p["fillet_r"], p["fillet_gap"]
        out = out.union(cq.Workplane().box(p["w"] - 2 * g, r, r, centered=(True, False, False))
                        .translate((0, -p["w"] / 2, -r)))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, t = p["w"], p["t"]
    items = [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(-w / 2, -w / 2, t), (w / 2, -w / 2, t), (w / 2, w / 2, t), (-w / 2, w / 2, t)]}]
    if p["fillet_r"] > 0:
        items.append({"name": "fillet strips", "kind": "printed", "material": "pla"})
    return items
'''

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", STRIPPED, intent="a top with fillet strips")
    return s


def test_a_number_that_turns_a_piece_off_is_found_by_building_it(store):
    assert [e["name"] for e in pieces.named(store, "stool", "fillet strips")] == ["fillet_gap", "fillet_r"]   # by name
    assert pieces.off_switch(store, "stool", "fillet strips") == {"param": "fillet_r", "value": 0, "unit": "mm"}
    assert pieces.off_switch(store, "stool", "top") is None            # nothing named for it: the designer's


def test_delete_by_its_number_is_a_new_version_at_once_and_says_what_went(store):
    p = pieces.plan(store, "stool", "fillet strips")
    assert p["how"] == "number" and not p["designer_call"]
    assert p["said"] == ("Delete the fillet strips: fillet_r to 0 turns them off. A number change, at once (no Claude): "
                         "a new version of stool, rolled back as any other.")
    got = pieces.delete(store, "stool", "fillet strips")
    assert got["version"] == 2 and got["said"] == ("Deleted the fillet strips from stool: fillet_r to 0 (v2). Roll it "
                                                   "back to put them back.")
    from caliper.tree import pieces as rows

    assert [r["key"] for r in rows(DesignStore.load(store.root), "stool")] == ["top"]


def test_a_piece_no_number_turns_off_is_the_designer_s_with_its_cost(store):
    p = pieces.plan(store, "stool", "top")
    assert p["how"] == "designer" and p["designer_call"]
    assert p["said"].startswith("Delete the top: that changes stool's code, so it asks the designer (one Claude call")
    with pytest.raises(ValueError, match="designer's to take out"):
        pieces.delete(store, "stool", "top")


def test_the_routes_plan_then_delete_and_refuse_while_busy(store, monkeypatch):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from caliper import design_api
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(str(store.root)))
    c = TestClient(create_app())
    base = f"/api/designs/{store.design.slug}/parts/stool/pieces/fillet%20strips/delete"
    assert c.get(base).json()["how"] == "number"
    assert c.get(f"/api/designs/{store.design.slug}/parts/stool/pieces/nope/delete").status_code == 404

    def busy(slug, parts):
        raise HTTPException(409, "stool is being checked: wait for it, or stop that first.")

    with monkeypatch.context() as m:
        m.setattr(design_api, "_refuse_while_busy", busy)
        assert c.post(base).status_code == 409
    got = c.post(base).json()
    assert got["said"].startswith("Deleted the fillet strips from stool") and got["version"] == 2
    assert [pc["key"] for pc in next(p for p in got["design"]["parts"] if p["id"] == "stool")["pieces"]] == ["top"]
