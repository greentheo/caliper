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
    pieces.off_switch(store, "stool", "fillet strips")                # built: its Delete… clicked once (#332)
    p = pieces.plan(store, "stool", "fillet strips")
    assert p["how"] == "number" and p["checked"] and not p["designer_call"]
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
    got = pieces.delete(store, "stool", "top")                         # the plan back, nothing set (#332)
    assert got == p and DesignStore.load(store.root).design.part("stool").version == 1


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


# --- #332 round two: the off switch measured exactly; decided on the Delete click; the piece's key, not its words ---------

#: caliper-reviewer's case, at step_stool's size (406 × 559 × 406): nose_r rounds the step's corners and draws the nose strip.
#: At 3 mm the corners it squares back are 147 mm³, under one cell of the 200k-point grid this replaced.
NOSED = '''import cadquery as cq

PARAMS = {"w": 406.0, "d": 559.0, "h": 406.0, "t": 19.05, "nose_r": 3.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    w, d, h, t = p["w"], p["d"], p["h"], p["t"]
    out = cq.Workplane().box(w, d, t, centered=(True, True, False)).translate((0, 0, h - t))
    if p["nose_r"] > 0:                       # it rounds the step's corners, and it draws the nose strip
        out = out.edges("|Z").fillet(p["nose_r"])
    out = out.union(cq.Workplane().box(t, d, h - t, centered=(True, True, False)).translate((-w / 2 + t / 2, 0, 0)))
    if p["nose_r"] > 0:
        out = out.union(cq.Workplane().box(w - 2 * t, 30, t, centered=(True, False, False)).translate((t / 2, -d / 2, h - 2 * t)))
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h, t = p["w"], p["d"], p["h"], p["t"]
    items = [{"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(-w / 2, -d / 2, h), (w / 2, -d / 2, h), (w / 2, d / 2, h), (-w / 2, d / 2, h)]},
             {"name": "side", "kind": "sheet", "material": "plywood", "thickness": t,
              "outline": [(-w / 2, -d / 2, 0), (-w / 2, d / 2, 0), (-w / 2, d / 2, h - t), (-w / 2, -d / 2, h - t)]}]
    if p["nose_r"] > 0:
        items.append({"name": "nose strip", "kind": "printed", "material": "pla"})
    return items
'''

#: The same with a nose_w that only sizes the strip: it's the switch, tried after nose_r.
NOSE_W = (NOSED.replace('"nose_r": 3.0}', '"nose_r": 3.0, "nose_w": 30.0}')
          .replace('''    if p["nose_r"] > 0:
        out = out.union(cq.Workplane().box(w - 2 * t, 30,''', '''    if p["nose_r"] > 0 and p["nose_w"] > 0:
        out = out.union(cq.Workplane().box(w - 2 * t, p["nose_w"],''')
          .replace('''    if p["nose_r"] > 0:
        items.append''', '''    if p["nose_r"] > 0 and p["nose_w"] > 0:
        items.append'''))


def test_a_3_mm_rounding_is_seen_wherever_the_part_is_big(tmp_path, monkeypatch):
    """The reviewer's step_stool: nose_r at 0 squares the step's corners back (147 mm³), so it isn't the switch."""
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, NOSED, "nose")
    assert pieces.off_switch(s, "stool", "nose strip") is None
    assert pieces.off_why(s, "stool", "nose strip") == "nose_r turns it off but also changes the step"


def test_with_a_number_that_only_sizes_it_that_one_is_the_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, NOSE_W, "nosew")
    assert [e["name"] for e in pieces.named(s, "stool", "nose strip")] == ["nose_r", "nose_w"]
    assert pieces.off_switch(s, "stool", "nose strip") == {"param": "nose_w", "value": 0, "unit": "mm"}


def test_what_else_a_build_changes_is_measured_exactly():
    """The two builds' difference is the booleans', to the mm³: the 3 mm rounding at any size, and nothing where the
    number only took the piece away."""
    import math

    run = pieces._build(NOSED)
    at0 = pieces._build(NOSED, {"nose_r": 0})
    added = pieces._exact(at0).cut(*pieces._exact(run).Solids()).Volume()          # the solids, not their meshes
    assert added == pytest.approx(4 * (1 - math.pi / 4) * 9 * 19.05, rel=0.001)    # 147.14 mm³ by hand
    assert pieces._also(run, at0, "nose strip") == "changes the step"
    assert pieces._also({**run, "declared": {}}, at0, "nose strip") == "adds to the part where nothing is declared"
    w = pieces._build(NOSE_W)
    assert pieces._also(w, pieces._build(NOSE_W, {"nose_w": 0}), "nose strip") is None
    assert 1.0 <= pieces.CHANGE_MM3 < 147                                             # near a mm³, under the rounding


def _no_builds(monkeypatch):
    monkeypatch.setattr(pieces, "_FOUND", {})

    def built(*a, **k):
        raise AssertionError("built")

    monkeypatch.setattr(pieces, "_build", built)


def test_the_plan_builds_nothing_and_says_the_click_builds_it(store, monkeypatch):
    """The menu's GET: names only (the reviewer timed 37–110 s of builds and compares on step_stool)."""
    _no_builds(monkeypatch)
    p = pieces.plan(store, "stool", "fillet strips")
    assert p["how"] == "number" and p["params"] == ["fillet_gap", "fillet_r"] and not p["checked"]
    assert not p["designer_call"] and "param" not in p                 # fillet_gap only looks right: none named as it
    assert p["said"] == ("Delete the fillet strips: fillet_gap or fillet_r at 0 may turn them off. Each is built first to "
                         "be sure (a few seconds, no Claude); where none only does that, it's the designer's instead. A "
                         "new version of stool, rolled back as any other.")
    assert pieces.plan(store, "stool", "top")["how"] == "designer"                    # nothing named for it: no build


def test_the_delete_click_decides_and_a_number_that_does_two_jobs_goes_back_to_the_designer(tmp_path, monkeypatch):
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, ONE_JOB, "one")
    assert pieces.plan(s, "stool", "fillet strips")["how"] == "number"               # by its name, not yet built
    got = pieces.delete(s, "stool", "fillet strips")
    assert got["how"] == "designer" and got["designer_call"] and "version" not in got
    assert got["said"].startswith("Delete the fillet strips: fillet_r turns them off but also changes the top, so it "
                                  "asks the designer")
    assert DesignStore.load(s.root).design.part("stool").version == 1                 # nothing set
    assert pieces.plan(s, "stool", "fillet strips") == {k: v for k, v in got.items()}  # known now: said as found


def test_the_delete_route_says_the_designer_s_way_without_a_new_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, ONE_JOB, "one")
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(str(s.root)))
    got = TestClient(create_app()).post(f"/api/designs/{s.design.slug}/parts/stool/pieces/fillet%20strips/delete")
    assert got.status_code == 200 and got.json()["how"] == "designer"
    assert DesignStore.load(s.root).design.part("stool").version == 1
    assert not any("from its menu" in str(e.get("text")) for e in DesignStore.load(s.root).log())   # nothing done, nothing said


#: Pieces named as step-stool-5 names them, in plain words with of/on in them (the reviewer's table).
WORDY = STRIPPED.replace('{"name": "top",', '{"name": "top of the step",').replace(
    '"fillet strips"', '"strip on the front"')


def _wordy(tmp_path):
    s = DesignStore.create("step-stool-5", base=str(tmp_path / "designs"))
    s.write_part("step_stool", WORDY, intent="a top with a strip")
    return s


def _designer(asked):
    def author(spec, feedback, prior):
        asked.append(feedback)
        return prior or WORDY
    return author


@pytest.mark.parametrize("said", ["Remove the top of the step from step_stool.",
                                  "Remove the strip on the front from step_stool."])
@pytest.mark.parametrize("scope", [None, "step_stool"])
@pytest.mark.parametrize("waiting", [None, "remove_which"])
def test_a_piece_with_of_or_on_in_its_name_is_its_part_s_revise(tmp_path, said, scope, waiting):
    from caliper import awaiting, chat

    s = _wordy(tmp_path)
    if waiting:
        awaiting.park(s, waiting)
    asked = []
    got = chat.turn(s, said, scope=scope, use_llm=False, author=_designer(asked), max_rounds=1)
    assert "Remove which part" not in got.reply and "trash" not in got.reply, got.reply
    assert asked and s.design.part("step_stool") is not None


def test_the_page_s_delete_sends_the_piece_s_key_and_no_words_are_read(tmp_path, monkeypatch):
    from caliper import chat

    s = _wordy(tmp_path)
    monkeypatch.setattr(chat, "_names_a_piece", lambda *a, **k: False)              # whatever the words would say
    got = chat.turn(s, "Remove the top of the step from step_stool.", scope="step_stool", use_llm=False,
                    author=_designer([]), max_rounds=1)
    assert "Remove which part" in got.reply or "trash" in got.reply                  # the control: words alone, read wrong
    from caliper import awaiting

    awaiting.park(s, "remove_which")
    asked = []
    got = chat.turn(s, "Remove the top of the step from step_stool.", scope="step_stool", piece="top of the step",
                    use_llm=False, author=_designer(asked), max_rounds=1)
    assert "Remove which part" not in got.reply and "trash" not in got.reply and asked, got.reply
    assert awaiting.pending(s) is None                                                # the question it waited on lapsed


def test_the_chat_route_passes_the_piece_on():
    import inspect

    from caliper import design_api

    assert "piece: Optional[str] = None" in inspect.getsource(design_api.ChatMessage)
    assert "piece=req.piece" in inspect.getsource(design_api)


def test_a_part_whose_name_has_of_in_it_is_found_at_an_earlier_split(tmp_path):
    """Every split, not only the last: "the top of the step from rack of shelves" is the top of the step, of
    rack_of_shelves (its last "of" would read "shelves")."""
    from caliper import chat

    s = DesignStore.create("a rack", base=str(tmp_path / "designs"))
    s.write_part("rack_of_shelves", WORDY, intent="a top with a strip")
    asked = []
    got = chat.turn(s, "Remove the top of the step from the rack of shelves part.", use_llm=False,
                    author=_designer(asked), max_rounds=1)          # "… part": read as a part's name, were it split wrong
    assert "Remove which part" not in got.reply and "trash" not in got.reply and asked, got.reply


#: The top built 0.3 mm thinner from below than it's declared (19.05 declared, as a designer rounds), the strips against
#: its built underside: inside the declared top's solid by 0.3 mm, so only its inset keeps them the strips' own.
OFF_BY = STRIPPED.replace(
    'out = cq.Workplane().box(p["w"], p["w"], p["t"], centered=(True, True, False))',
    'out = cq.Workplane().box(p["w"], p["w"], p["t"] - 0.3, centered=(True, True, False)).translate((0, 0, 0.3))').replace(
    '.translate((0, -p["w"] / 2, -r)))', '.translate((0, -p["w"] / 2, -r + 0.3)))')


def test_a_sheet_declared_a_little_off_its_build_isn_t_changed_by_the_switch(tmp_path, monkeypatch):
    assert OFF_BY.count("+ 0.3") == 1 and OFF_BY.count("translate((0, 0, 0.3))") == 1
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, OFF_BY, "off")
    assert pieces.off_switch(s, "stool", "fillet strips") == {"param": "fillet_r", "value": 0, "unit": "mm"}


# --- #332 re-check: exact solids, a failure is never "no change", a stale key is said ------------------------------------

#: caliper-reviewer's tube: a round steel tube sunk 1 mm into a plywood plate (one solid), a printed clip cut to its round
#: and unioned onto it.
#: clip_w at 0 skips the clip and nothing else, but the tube's round face is tessellated differently with the clip on it:
#: mesh booleans read 4–9 mm³ "added" there.
TUBED = '''import cadquery as cq

PARAMS = {"L": 400.0, "od": 50.8, "clip_w": 20.0}


def _tube(p):
    return cq.Workplane("YZ").circle(p["od"] / 2).extrude(p["L"]).translate((-p["L"] / 2, 0, 11.7 + p["od"] / 2))


def build(params):
    p = {**PARAMS, **(params or {})}
    out = cq.Workplane().box(p["L"], 100, 12.7, centered=(True, True, False)).union(_tube(p))
    if p["clip_w"] > 0:
        clip = cq.Workplane().box(p["clip_w"], p["od"], p["od"] / 2 + 6, centered=(True, True, False)).translate(
            (0, 0, 11.7 + p["od"] / 2)).cut(_tube(p))
        out = out.union(clip)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    L, od = p["L"], p["od"]
    items = [{"name": "plate", "kind": "sheet", "material": "plywood", "thickness": 12.7,
              "outline": [(-L / 2, -50, 12.7), (L / 2, -50, 12.7), (L / 2, 50, 12.7), (-L / 2, 50, 12.7)]},
             {"name": "tube", "kind": "stick", "material": "steel", "outer": od, "wall": 1.6,
              "a": (-L / 2, 0, 11.7 + od / 2), "b": (L / 2, 0, 11.7 + od / 2)}]
    if p["clip_w"] > 0:
        items.append({"name": "clip", "kind": "printed", "material": "pla"})
    return items
'''

#: clip_w at 0 also cuts 40 mm off the tube's end: taken from the tube, a stick, which only its solid in _prisms sees
TUBE_CUT = TUBED.replace('''def _tube(p):
    return cq.Workplane("YZ").circle(p["od"] / 2).extrude(p["L"])''', '''def _tube(p):
    return cq.Workplane("YZ").circle(p["od"] / 2).extrude(p["L"] if p["clip_w"] > 0 else p["L"] - 40)''')


#: the tube resting on the plate, touching it along a line: the build is two solids, a compound
RESTING = TUBED.replace("11.7 + ", "12.7 + ")


@pytest.mark.parametrize("src", [TUBED, RESTING], ids=["sunk into the plate", "resting on it, two solids"])
def test_a_switch_beside_a_round_tube_is_the_switch(tmp_path, monkeypatch, src):
    """The re-check's tube: the exact solids read 0.000000 mm³ added where the meshes read 8.77. Two solids are cut by
    each other's, one by one: cut by the compound whole, all of the plate read as taken."""
    assert RESTING.count("12.7 + ") == 4
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, src, "tube")
    assert pieces.off_switch(s, "stool", "clip") == {"param": "clip_w", "value": 0, "unit": "mm"}, pieces.off_why(
        s, "stool", "clip")


@pytest.mark.parametrize("src", [TUBE_CUT, TUBE_CUT.replace("11.7 + ", "12.7 + ")],
                         ids=["sunk into the plate", "resting on it, two solids"])
def test_a_number_that_also_cuts_a_stick_isn_t_the_switch(tmp_path, monkeypatch, src):
    """Resting, the builds are two solids each: cut by the other's compound whole, all of the plate read as taken."""
    assert TUBE_CUT.count("p[\"L\"] - 40") == 1
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, src, "cut")
    assert pieces.off_switch(s, "stool", "clip") is None
    assert pieces.off_why(s, "stool", "clip") == "clip_w turns it off but also changes the tube"


@pytest.mark.parametrize("where", ["a mesh that throws", "no solid", "no mesh"])
def test_a_compare_that_fails_is_never_no_change(tmp_path, monkeypatch, where):
    """A boolean that throws, or a build with no solid to cut: not compared, so the number isn't offered and the Delete
    is the designer's, said why."""
    monkeypatch.setattr(pieces, "_FOUND", {})
    s = _part(tmp_path, STRIPPED, "fail")

    def broken(*a, **k):
        raise RuntimeError("the kernel gave up")

    if where == "no solid":
        monkeypatch.setattr(pieces, "_exact", lambda build: None)
    elif where == "no mesh":                                  # nothing to place the other pieces' solids by
        built = pieces._build
        monkeypatch.setattr(pieces, "_build", lambda *a, **k: {**built(*a, **k), "mesh": None})
    else:
        monkeypatch.setattr(pieces, "_meshed", broken)
    assert pieces.off_switch(s, "stool", "fillet strips") is None
    assert pieces.off_why(s, "stool", "fillet strips") == "fillet_r turns them off but also its shape couldn't be compared"
    got = pieces.delete(s, "stool", "fillet strips")
    assert got["how"] == "designer" and "version" not in got


@pytest.mark.parametrize("key", ["inside corner strips", "seat strip"], ids=["gone since the menu opened", "forged"])
def test_a_key_that_isn_t_one_of_the_part_s_pieces_is_said_never_read_as_words(tmp_path, key):
    """The re-check's stale key: the words alone asked "Remove which part?", with trash two answers away."""
    from caliper import chat

    s = _wordy(tmp_path)
    asked = []
    got = chat.turn(s, "Remove step_stool.", scope="step_stool", piece=key, use_llm=False, author=_designer(asked),
                    max_rounds=1)
    assert got.reply == f"step_stool has no {key} now: nothing was changed." and not asked
    assert "trash" not in got.reply and s.design.part("step_stool") is not None
