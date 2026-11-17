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


# --- #332 review: a number is the off switch only if it changes nothing else ----------------------------------------------

TWO_JOB = '''import cadquery as cq

PARAMS = {"w": 200.0, "t": 19.05, "fillet_r": 6.0, "strip_w": 6.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    w, t = p["w"], p["t"]
    out = cq.Workplane().box(w, w, t, centered=(True, True, False))
    if p["fillet_r"] > 0:                       # it rounds the top's corners, and it draws the strips
        out = out.edges("|Z").fillet(p["fillet_r"])
        if p["strip_w"] > 0:
            s = p["strip_w"]
            out = out.union(cq.Workplane().box(w - 40, s, s, centered=(True, False, False)).translate((0, -w / 2 + 20, -s)))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, t = p["w"], p["t"]
    items = [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(-w / 2, -w / 2, t), (w / 2, -w / 2, t), (w / 2, w / 2, t), (-w / 2, w / 2, t)]}]
    if p["fillet_r"] > 0 and p["strip_w"] > 0:
        items.append({"name": "fillet strips", "kind": "printed", "material": "pla"})
    return items
'''

#: fillet_r alone, with both jobs: no number only takes the strips away.
ONE_JOB = TWO_JOB.replace('"fillet_r": 6.0, "strip_w": 6.0', '"fillet_r": 6.0, "lip_w": 6.0').replace(
    'p["strip_w"]', 'p["lip_w"]')

#: fillet_r at 0 also drops a printed cleat: taken from no sheet, so only the names say it went.
CLEATED = STRIPPED.replace('''        out = out.union(cq.Workplane().box(p["w"] - 2 * g, r, r, centered=(True, False, False))
                        .translate((0, -p["w"] / 2, -r)))''', '''        out = out.union(cq.Workplane().box(p["w"] - 2 * g, r, r, centered=(True, False, False))
                        .translate((0, -p["w"] / 2, -r)))
        out = out.union(cq.Workplane().box(20, 20, 10, centered=(True, True, False)).translate((0, 50, -10)))''').replace(
    '''        items.append({"name": "fillet strips", "kind": "printed", "material": "pla"})''',
    '''        items.append({"name": "fillet strips", "kind": "printed", "material": "pla"})
        items.append({"name": "cleat", "kind": "printed", "material": "pla"})''')


def _part(tmp_path, script, name="stool"):
    s = DesignStore.create(f"a {name}", base=str(tmp_path / name / "designs"))
    s.write_part("stool", script, intent="a top")
    return s


def test_a_number_that_also_changes_another_piece_isn_t_the_off_switch(tmp_path):
    """caliper-reviewer's part: fillet_r draws the strips and rounds the top's corners; at 0 the top gets its square corners
    back. strip_w only sizes the strips: it's the switch."""
    s = _part(tmp_path, TWO_JOB)
    assert [e["name"] for e in pieces.named(s, "stool", "fillet strips")] == ["fillet_r", "strip_w"]
    assert pieces.off_switch(s, "stool", "fillet strips") == {"param": "strip_w", "value": 0, "unit": "mm"}


def test_where_the_only_number_does_two_jobs_the_designer_takes_it_out_and_says_why(tmp_path):
    s = _part(tmp_path, ONE_JOB, "one")
    assert pieces.off_switch(s, "stool", "fillet strips") is None
    p = pieces.plan(s, "stool", "fillet strips")
    assert p["how"] == "designer" and p["designer_call"]
    assert p["said"].startswith("Delete the fillet strips: fillet_r turns them off but also changes the top, so it asks "
                                "the designer (one Claude call"), p["said"]


def test_a_number_that_also_drops_another_piece_isn_t_the_off_switch(tmp_path):
    """The names check, pinned (the reviewer's any-build mutant): fillet_r at 0 also drops the cleat, a printed piece no
    sheet holds, so its shape alone wouldn't say."""
    s = _part(tmp_path, CLEATED, "cleat")
    assert pieces.off_switch(s, "stool", "fillet strips") is None
    assert "fillet_r turns them off but also takes away the cleat" in pieces.plan(s, "stool", "fillet strips")["said"]


# --- #332 review: a piece's designer Delete is a revise of its part, never the part remove ---------------------------------

PIECED = STRIPPED.replace('"fillet strips"', '"inside corner fillet strips"')


@pytest.mark.parametrize("piece, said", [("top", "Remove the top from step_stool."),
                                         ("inside corner fillet strips",
                                          "Remove the inside corner fillet strips from step_stool."),
                                         # the part selected, the piece named alone, an underscore as a part's name has
                                         ("inside corner fillet strips", "remove the inside_corner fillet strips")])
def test_remove_a_piece_from_its_part_goes_to_the_designer_never_the_part_remove(tmp_path, piece, said):
    from caliper import chat

    s = DesignStore.create("step-stool-5", base=str(tmp_path / "designs"))
    s.write_part("step_stool", PIECED, intent="a top with fillet strips")
    asked = []

    def author(spec, feedback, prior):
        asked.append(feedback)
        return prior.replace("# the strips", "# the strips, revised") if prior else PIECED

    got = chat.turn(s, said, scope="step_stool", use_llm=False, author=author, max_rounds=1)
    assert "Remove which part" not in got.reply and "trash" not in got.reply, got.reply
    assert asked and any(said.rstrip(".") in str(a) for a in asked), asked
    assert s.design.part("step_stool") is not None


#: fillet_r at 0 also builds the top 6 mm thinner (its declared thickness unchanged): material taken from another piece.
THINS = TWO_JOB.replace('''    out = cq.Workplane().box(w, w, t, centered=(True, True, False))
    if p["fillet_r"] > 0:                       # it rounds the top's corners, and it draws the strips
        out = out.edges("|Z").fillet(p["fillet_r"])
        if p["strip_w"] > 0:''', '''    out = cq.Workplane().box(w, w, t if p["fillet_r"] > 0 else t - 6, centered=(True, True, False)).translate(
        (0, 0, 0 if p["fillet_r"] > 0 else 6))
    if p["fillet_r"] > 0:
        if p["strip_w"] > 0:''').replace('"fillet_r": 6.0, "strip_w": 6.0', '"fillet_r": 6.0, "lip_w": 6.0').replace(
    'p["strip_w"]', 'p["lip_w"]')


def test_a_number_that_also_thins_another_piece_isn_t_the_off_switch(tmp_path):
    s = _part(tmp_path, THINS, "thin")
    assert pieces.off_switch(s, "stool", "fillet strips") is None
    assert pieces.off_why(s, "stool", "fillet strips") == "fillet_r turns them off but also changes the top"
