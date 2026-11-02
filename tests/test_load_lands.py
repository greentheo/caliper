"""CALI-84 (#58) — one rule for where a load lands: the designer's check (loads_land) and the strength check
(load_study.prepare) agree on whether a box is on the part, at any voxel size, and say so in the same words."""

import pytest

from caliper import consistency, load_study, sandbox
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL
from .test_printed_strength import PRINTED

pytest.importorskip("cadquery")

#: The owner's walkthrough stool, shrunk: a printed shell with a 1/8 in recess for a mat in its top, and the
#: foot's box left at the top's un-recessed height, 1.2 mm above the floor of the recess.
RECESS = PRINTED.replace("    return outer.cut(inner)", '''    rec = cq.Workplane().box(p["w"] - 12, p["d"] - 12, 3.175, centered=(True, True, False))
    return outer.cut(inner).cut(rec.translate((0, 0, p["h"] - 3.175)))''')
#: The same box with a 70 mm slot through its top, right under the foot: nothing within reach of it.
SLOT = PRINTED.replace("    return outer.cut(inner)", '''    slot = cq.Workplane().box(70, 70, 3 * p["wall"]).translate((0, 0, p["h"]))
    return outer.cut(inner).cut(slot)''')
FOOT = '"lo": (cx - 50, cy - 50, h - 2), "hi": (cx + 50, cy + 50, h)'


def hover(mm: float) -> str:
    """The box stool with its foot's box ``mm`` above the top."""
    return BOX_STOOL.replace(FOOT, f'"lo": (cx - 50, cy - 50, h + {mm}), "hi": (cx + 50, cy + 50, h + {mm} + 2)')


def both(src: str, tmp_path, monkeypatch, through: int):
    """loads_land and the strength check's setup on the same script: (loads_land's result, prepare's context or
    None, prepare's error or None)."""
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    run = sandbox.run_script(src, timeout=120)
    lands = {r.id: r for r in consistency.check(run.declared, run.geometry)}["loads_land"]
    store = DesignStore.create("a part", base=str(tmp_path / f"designs{through}"))
    store.write_part("p", src, intent="a part")
    try:
        return lands, load_study.prepare(store, "p"), None
    except ValueError as e:
        return lands, None, str(e)


def test_the_fixtures_are_what_they_say():
    assert RECESS != PRINTED and SLOT != PRINTED and hover(7) != BOX_STOOL


@pytest.mark.parametrize("through", [2, 4])
def test_a_box_just_above_a_recess_pushes_on_its_floor(tmp_path, monkeypatch, through):
    """The walkthrough's bug: loads_land passed and the strength check found nothing to push on."""
    lands, ctx, err = both(RECESS, tmp_path, monkeypatch, through)
    assert lands.passed, lands.detail
    assert err is None, err
    if through == 2:                                       # one FEA is enough to show it pushes on something
        case, _ = load_study.check_load(ctx, 0, load_study.MIN_SAFETY)
        assert case["fea"]["supported"] and case["safety"] > 0


@pytest.mark.parametrize("through", [2, 4])
def test_a_box_over_a_slot_fails_both_in_the_same_words(tmp_path, monkeypatch, through):
    lands, ctx, err = both(SLOT, tmp_path, monkeypatch, through)
    assert not lands.passed and ctx is None
    assert "'a foot' doesn't touch the part — it pushes on thin air" in err
    assert err in lands.detail


@pytest.mark.parametrize("mm,through,on", [
    (1.0, 4, True),         # just above it, at any size
    (7.0, 2, True),         # 7 mm: within a coarse voxel (9.5 mm at 2 through 3/4 in), so it's on
    (7.0, 4, False),        # ...and off a fine one (4.8 mm): before CALI-84 the two checks split here
    (10.0, 2, False),       # 10 mm above a 3/4 in top: off at either size
    (10.0, 4, False),
])
def test_both_checks_agree_at_any_voxel_size(tmp_path, monkeypatch, mm, through, on):
    lands, ctx, err = both(hover(mm), tmp_path, monkeypatch, through)
    assert lands.passed is on and (ctx is not None) is on, (lands.detail, err)
    if not on:
        assert err in lands.detail and f"{mm:.1f} mm from its nearest surface" in err


def test_a_support_under_nothing_fails_both_in_the_same_words(tmp_path, monkeypatch):
    floating = BOX_STOOL + '''

def held(params, build=None):
    return [{"name": "a shelf under it", "lo": (0, 0, -30), "hi": (406.4, 254.0, -20)}]
'''
    lands, ctx, err = both(floating, tmp_path, monkeypatch, 2)
    assert not lands.passed and ctx is None
    assert "'a shelf under it' doesn't touch the part — nothing holds it there, 20.0 mm" in err
    assert err in lands.detail


def test_touches_says_how_far():
    import trimesh

    cube = trimesh.creation.box(extents=(100, 100, 100))            # -50..50
    assert load_study.touches(cube, ((-10, -10, 49), (10, 10, 51)), 2.0) == (True, 0.0)
    ok, gap = load_study.touches(cube, ((-10, -10, 51.5), (10, 10, 53)), 2.0)
    assert ok and gap == pytest.approx(1.5, abs=0.01)
    ok, gap = load_study.touches(cube, ((-10, -10, 60), (10, 10, 62)), 2.0)
    assert not ok and gap == pytest.approx(10, abs=0.01)
