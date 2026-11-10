"""CALI-90 (#66 item 4): a HOLES entry crossing its panel's edge wasn't refused, and became a stray cut. A hole
must lie inside its panel's outline, clear of the glued rim (lighten.RIM_MM, as lightening and pictures keep it):
refused when Caliper writes one, and flagged by the consistency check when a person does."""

import pytest

from caliper import consistency, lighten, pictures, sandbox

from .test_load_study import BOX_STOOL
from .test_pictures import stool  # noqa: F401  (the fixture)

SIDE = [[0.0, 0.0, 0.0], [300.0, 0.0, 0.0], [300.0, 0.0, 250.0], [0.0, 0.0, 250.0]]   # 300 x 250 mm, in y = 0


def _square(x0, z0, w):
    return [[x0, 0.0, z0], [x0 + w, 0.0, z0], [x0 + w, 0.0, z0 + w], [x0, 0.0, z0 + w]]


def _side(*holes):
    return {"kind": "sheet", "name": "side", "material": "plywood", "thickness": 19.05, "outline": SIDE,
            "holes": list(holes)}


def test_a_hole_inside_the_rim_is_fine_and_one_across_the_edge_isnt():
    rim = lighten.RIM_MM
    assert consistency.holes_outside([_side(_square(rim + 5, rim + 5, 50))]) == []
    got = consistency.holes_outside([_side(_square(250, 100, 65))])          # 65 mm, out past the 300 mm edge
    assert len(got) == 1 and "side" in got[0] and "edge" in got[0], got
    assert consistency.holes_outside([_side(_square(5, 100, 40))])            # inside the outline but in the rim


def test_the_consistency_check_flags_a_hand_written_hole_across_the_edge():
    # the box stool's left wall is x = 0, y 0-254 mm, z 0-228.6 mm: this one runs out past y = 254
    edge = [[0, 200, 150], [0, 300, 150], [0, 300, 210], [0, 200, 210]]
    script = BOX_STOOL + f'\n\nHOLES = [{{"piece": "left", "normal": [1, 0, 0], "depth": 19.05, "polygons": [{edge}]}}]\n'
    run = sandbox.run_script(script, timeout=120)
    got = {r.id: r for r in consistency.check(run.declared, run.geometry)}
    assert not got["holes_inside"].passed and "left" in got["holes_inside"].detail, got.get("holes_inside")
    base = sandbox.run_script(BOX_STOOL, timeout=120)
    clean = {r.id: r for r in consistency.check(base.declared, base.geometry)}
    assert "holes_inside" not in clean                     # no holes, nothing to say


def test_a_picture_that_would_cross_its_panels_edge_is_refused(stool, monkeypatch):  # noqa: F811
    from shapely.geometry import box

    real = pictures.fit
    monkeypatch.setattr(pictures, "fit", lambda shape, panel, scale=1.0: box(*[c + d for c, d in zip(
        panel["room"].bounds[2:] * 2, (-30, -30, 60, 60))]))
    with pytest.raises(ValueError, match="edge"):
        pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="the side",
                     strength=False)
    assert "HOLES" not in stool.read_script("stool")
    monkeypatch.setattr(pictures, "fit", real)
