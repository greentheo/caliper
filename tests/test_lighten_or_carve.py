"""#272 review (the foreman's call): one rule, read by the part's panel, Make it better's offer and ``blocked()``, decides
Lighten or Carve for a part, never both, by where its volume is. Printed pieces under half of it: a sheet part, lightened
(step-stool-5 v4, its PLA fillet strips a sliver of it). Most of it printed: a printed part, carved (the bar stool's PETG cone
under a plywood seat). Synthetic parts in each shape, not Theo's."""

import pytest

pytest.importorskip("cadquery")

from caliper import load_study as L  # noqa: E402
from caliper import studies  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

from .test_load_study import BOX_STOOL  # noqa: E402

#: A box stool with a small printed strip glued in one inside corner: a sheet part with a little print in it.
WITH_STRIPS = BOX_STOOL.replace('''            "top": ((t, t, h - t), (w - t, d - t, h))}''', '''            "top": ((t, t, h - t), (w - t, d - t, h)),
            "strip": ((t, t, h - t - 5), (t + 5, d - t, h - t))}''').replace(
    '''    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k, v in face.items()]''',
    '''    return [{"name": k, "kind": "sheet", "material": "plywood", "thickness": t, "outline": v} for k, v in face.items()] + [
        {"name": "fillet strip", "kind": "printed", "material": "pla", "infill": 0.2, "rest": True}]''')

#: A printed cone-ish block under a thin plywood seat: a printed part with a little wood on it.
PRINTED_BASE = '''import cadquery as cq

PARAMS = {"w": 300.0, "h": 400.0, "t": 12.7}


def build(params):
    p = {**PARAMS, **(params or {})}
    base = cq.Workplane().box(p["w"], p["w"], p["h"], centered=False)
    seat = cq.Workplane().box(p["w"], p["w"], p["t"], centered=False).translate((0, 0, p["h"]))
    return base.union(seat)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, h, t = p["w"], p["h"], p["t"]
    return [{"name": "seat", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, w, h + t), (0, w, h + t)]},
            {"name": "base", "kind": "printed", "material": "petg", "infill": 0.2, "rest": True}]
'''

ALL_PRINTED = PRINTED_BASE.replace('''    return [{"name": "seat", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, w, h + t), (0, w, h + t)]},
            {"name": "base"''', '''    return [{"name": "base"''')


@pytest.mark.parametrize("script,want", [(BOX_STOOL, "lighten"), (WITH_STRIPS, "lighten"), (PRINTED_BASE, "carve"),
                                         (ALL_PRINTED, "carve")],
                         ids=["all sheet", "sheet with printed strips", "printed with a plywood seat", "all printed"])
def test_a_part_is_lightened_or_carved_by_where_its_volume_is(tmp_path, script, want):
    assert WITH_STRIPS != BOX_STOOL and ALL_PRINTED != PRINTED_BASE
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", script, intent="a part")
    got = studies.made_of(s, "p")
    assert got["study"] == want, got
    if script is WITH_STRIPS:
        assert 0 < got["printed_share"] < 0.05, got
    if script is PRINTED_BASE:
        assert got["printed_share"] > 0.9, got


@pytest.mark.parametrize("script,off", [(WITH_STRIPS, "carve"), (PRINTED_BASE, "lighten")])
def test_blocked_turns_the_other_study_off_in_words(tmp_path, script, off):
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", script, intent="a part")
    b = L.blocked(s, "p") or {}
    assert b.get(off), b
    assert ("It's mostly sheet wood: it's lightened, not carved" if off == "carve"
            else "It's mostly printed: it's carved, not lightened") in b[off], b


def test_the_card_and_the_panel_read_the_rule_not_whether_anything_is_printed():
    import inspect

    from caliper import better

    from .test_carve_click import JS, _fn

    src = inspect.getsource(better.offers)
    assert 'p.get("study") == "carve"' in src and 'p.get("study") == "lighten"' in src
    assert 'p.get("printed") and not p.get("carved")' not in src
    view = _fn(open(JS).read(), "loadView")
    assert "p.study === 'carve'" in view, view
    shown = _fn(open(JS).read(), "lightenShown")
    assert "p.study === 'lighten'" in shown and "p.printed" not in shown, shown


def test_lighten_waits_for_a_check_that_can_see_its_walls(tmp_path, monkeypatch):
    """step-stool-5 v4's check read "not resolved": its PLA fillet strips' 13 mm walls against 4.4 mm voxels. A Lighten would
    run 50 minutes to no step that can hold. It says so first, naming the piece."""
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    rec = {"part": "p", "version": 1, "cases": [{"name": "c", "safety": 3.0, "fea": {"supported": True}}], "safety": 3.0,
           "resolved": False, "thinnest_mm": 13.14, "thinnest_where": {"piece": "printed fillet strips"}, "finer": {}}
    monkeypatch.setattr(L, "default_check", lambda store, pid: rec)
    monkeypatch.setattr(L, "already_fails", lambda store, pid: None)
    b = L.blocked(s, "p")
    assert b["lighten"] == "Its check couldn't see the printed fillet strips (13 mm): check it again finer"
    assert b["carve"] == "It's mostly sheet wood: it's lightened, not carved"


def test_a_lighten_says_the_printed_pieces_are_left_alone(tmp_path):
    import inspect

    from caliper import lighten

    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    s.write_part("q", BOX_STOOL, intent="a part")
    assert lighten.printed_untouched(s, "p") == "The fillet strip is left out of this study and isn't cut: it's glued trim."
    assert lighten.printed_untouched(s, "q") is None
    src = inspect.getsource(lighten.study)
    assert "untouched = printed_untouched(store, part_id)" in src and '"notes": [*([untouched] if untouched else []),' in src


def test_an_older_run_leads_with_whose_step_it_is():
    from .test_carve_click import JS, _fn

    view = _fn(open(JS).read(), "lightenView")
    assert "`v${run.version}'s lightest step that holds`" in view and "run.version !== p.version" in view



def test_lighten_waits_for_a_check_as_carve_does(tmp_path, monkeypatch):
    """#272 re-check: v4 had no strength check, and Lighten was live while Make it better said "Check it holds first"."""
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    monkeypatch.setattr(L, "default_check", lambda store, pid: None)
    monkeypatch.setattr(L, "already_fails", lambda store, pid: None)
    b = L.blocked(s, "p")
    assert b["why"] == "unchecked" and b["lighten"] == "Check it holds first: a lightening starts from its strength check"


def test_an_older_run_offers_no_step_to_choose():
    from .test_carve_click import JS, _fn

    view = _fn(open(JS).read(), "lightenView")
    assert "${run.offer && (run.version == null || run.version === p.version) ?" in view



# --- #272 re-check: a sheet part's printed trim, measured on its own, named, and left out of a Lighten ---------------------
@pytest.fixture(scope="module")
def checked(tmp_path_factory):
    """A real strength check of the sheet stool with a printed strip glued in a corner, as step-stool-5 v4 is."""
    pytest.importorskip("whittle")
    s = DesignStore.create("a part", base=str(tmp_path_factory.mktemp("strips") / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    return s, L.study(s, "p")


def test_a_sheet_part_s_printed_piece_of_no_declared_size_isn_t_checked(checked):
    """step-stool-5 v4: its strips were measured off the boolean of the whole less the sheets (a 13 mm foot tip, then a 0.13 mm
    feather edge, then films). Now a printed piece on a sheet part goes by the size it declares; with none, it's not checked,
    said by name, and the voxels go by the sheets (the foreman's call)."""
    s, rec = checked
    assert rec["unsized"] == ["fillet strip"] and rec["resolved"] is False
    assert {"mm": None, "piece": "fillet strip"} in rec["unseen"], rec["unseen"]
    assert rec["thinnest_mm"] == pytest.approx(19.05) and rec["spacing_mm"] == pytest.approx(19.05 / 4, rel=0.05)
    from caliper import verdicts

    v = verdicts.run(rec)
    assert not v["counts_as_pass"], v
    assert L.unseen(rec, rec["cases"][0]) == "the fillet strip isn't checked: its size isn't declared"


def test_lighten_isn_t_held_back_by_trim_it_leaves_out(checked, monkeypatch):
    s, rec = checked
    monkeypatch.setattr(L, "default_check", lambda store, pid: rec)
    b = L.blocked(s, "p")
    assert b["why"] in ("unresolved", "too_thin") and b["lighten"] == "", b      # the strip alone is too thin for any run


def test_a_lighten_studies_the_sheets_and_resolves_on_them(checked):
    from caliper import lighten

    s, _ = checked
    ctx = L.prepare(s, "p")
    base, seen = lighten.sheets_only(ctx)
    assert seen["trimmed"] > 0 and int(base.sum()) == int(ctx["ls"].solid.sum()) - seen["trimmed"]
    assert L.resolution(seen)["resolved"] is True


def test_a_wall_said_as_a_point_is_named_by_its_piece(tmp_path):
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    assert L.piece_at(s, "p", (9.0, 100.0, 50.0)) == "left"                         # inside the left wall
    assert L.piece_at(s, "p", (21.5, 100.0, 207.0)) == "fillet strip"              # in the strip, off every sheet



def test_a_plural_piece_name_reads_are():
    """step-stool-5 v4's verdict read "the inside corner fillet strips is too thin to check"."""
    run = {"spacing_mm": 4.76, "unseen": [{"mm": 0.13, "piece": "inside corner fillet strips"}], "thinnest_mm": 0.13,
           "resolved": False}
    case = {"plate": {"done": True, "piece": "step"}, "governs": "plate", "safety": 2.15, "fea": {"supported": True, "safety": 3.0}}
    said = L.unseen(run, case)
    assert said.startswith("the inside corner fillet strips are too thin to check at this size (0.13 mm"), said
    run["unseen"] = [{"mm": 0.13, "piece": "fillet strip"}]
    assert L.unseen(run, case).startswith("the fillet strip is too thin"), L.unseen(run, case)


def test_lighten_s_wait_names_a_wall_given_as_a_point_by_its_piece(tmp_path, monkeypatch):
    """An older record gives its thinnest wall as a point: the wait names the piece it's in, not "its thinnest walls"."""
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    rec = {"part": "p", "version": 1, "cases": [{"name": "c", "safety": 3.0, "fea": {"supported": True}}], "safety": 3.0,
           "resolved": False, "thinnest_mm": 13.14, "thinnest_where": {"at": [9.0, 100.0, 50.0]},
           "unseen": [{"mm": 13.14, "at": [9.0, 100.0, 50.0]}], "finer": {}}
    monkeypatch.setattr(L, "default_check", lambda store, pid: rec)
    monkeypatch.setattr(L, "already_fails", lambda store, pid: None)
    assert L.blocked(s, "p")["lighten"] == "Its check couldn't see the left (13 mm): check it again finer"



def test_a_printed_piece_s_declared_section_is_its_size_never_a_measure(tmp_path):
    from caliper import construction as C
    from caliper.consistency import shapes

    sized = WITH_STRIPS.replace('"infill": 0.2, "rest": True}]', '"infill": 0.2, "rest": True, "section": 5.0}]')
    assert sized != WITH_STRIPS
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", sized, intent="a part")
    d = C.declared(s, "p")
    rest = C.printed_solid(s, "p", d)
    thins, walls, where, _ = L._thin(d, s.part_geometry("p").require_mesh(), shapes(d), rest)
    assert walls == 5.0 and where == {"piece": "fillet strip"} and min(thins) == 5.0


def test_declared_trim_is_left_out_with_a_note_and_a_pass_reads_tick_with_it(tmp_path):
    """The script says what the piece is for: "trim": true. It's left out of what the check must see, and a ✓ carries the note
    on every surface the joints note travels to (#265's path)."""
    from caliper import answers, verdicts

    run = {"min_safety": 2.0, "cut": True, "trim": ["fillet strip"]}
    case = {"name": "standing", "lb": 200, "factor": 2.0, "safety": 3.1, "holds": True, "governs": "fea",
            "fea": {"supported": True, "safety": 3.1}}
    v = verdicts.case(run, case)
    assert v["kind"] == "holds" and v["joints"] is True and v["brace"] == {"trim": ["fillet strip"]}, v
    text = answers._case_line("p", {**run, "cases": []}, case, None, False, False)["text"]
    assert "The fillet strip isn't checked: it's glued trim." in text, text
    from .test_carve_click import _page, _run

    line = _run(_page(["jointsLine", "safetyNum"], consts=["esc"], extra="""
out = jointsLine({verdict: {joints: true, brace: {trim: ['inside corner fillet strips']}}}, {min_safety: 2});"""))
    assert "the inside corner fillet strips are glued trim, left out of the check" in " ".join(line.split()), line


def test_declared_trim_is_carried_by_the_real_check(tmp_path):
    pytest.importorskip("whittle")
    trim = WITH_STRIPS.replace('"infill": 0.2, "rest": True}]', '"infill": 0.2, "rest": True, "trim": True}]')
    assert trim != WITH_STRIPS
    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", trim, intent="a part")
    rec = L.study(s, "p")
    assert rec["trim"] == ["fillet strip"] and "unsized" not in rec and rec.get("resolved") is True, rec


def test_the_designer_is_asked_for_a_section_and_trim():
    import inspect

    from caliper import materials

    src = inspect.getsource(materials)
    assert 'give it \\"section\\": its working size in mm' in src and '\\"trim\\": true when it\'s decorative' in src
