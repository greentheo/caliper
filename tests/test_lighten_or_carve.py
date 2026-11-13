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
    assert b["lighten"] == "Its check couldn't see the printed fillet strips (13 mm): check it again finer, or lighten without them"
    assert b["carve"] == "It's mostly sheet wood: it's lightened, not carved"


def test_a_lighten_says_the_printed_pieces_are_left_alone(tmp_path):
    import inspect

    from caliper import lighten

    s = DesignStore.create("a part", base=str(tmp_path / "designs"))
    s.write_part("p", WITH_STRIPS, intent="a part")
    s.write_part("q", BOX_STOOL, intent="a part")
    assert lighten.printed_untouched(s, "p") == "The printed fillet strip isn't touched: Lighten cuts holes in the sheets only."
    assert lighten.printed_untouched(s, "q") is None
    src = inspect.getsource(lighten.study)
    assert "untouched = printed_untouched(store, part_id)" in src and '"notes": [*([untouched] if untouched else []),' in src


def test_an_older_run_leads_with_whose_step_it_is():
    from .test_carve_click import JS, _fn

    view = _fn(open(JS).read(), "lightenView")
    assert "`v${run.version}'s lightest step that holds`" in view and "run.version !== p.version" in view
