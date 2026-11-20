"""CALI-204 (#336): Delete's off switch reads a declared tube as its walls, its bore open.

When Delete's off switch checks what else a number changes, each other declared piece is a solid to measure against
(``pieces._prisms``). A tube was a solid rod there: a plug in its bore read as part of the tube ("plug_l turns it off but
also changes the tube"), a false red that sent the Delete to the designer for nothing. Now a tube that declares its
``outer`` and ``wall`` is its walls, the bore open through its ends. A tube declares only its centreline, so its turn about
it is read off the build. A stick with no wall stays a solid rod.

Synthetic: a 1 in square steel tube, 16 ga, 300 mm long, turned ``turn`` degrees about its length."""

import numpy as np
import pytest

from caliper import consistency, pieces
from caliper.design import DesignStore

pytest.importorskip("cadquery")

FRAME = '''import cadquery as cq

PARAMS = {"turn": 0.0, "plug_l": 20.0, "clip_l": 0.0}
O, W, L = 25.4, 1.651, 300.0


def build(params):
    p = {**PARAMS, **(params or {})}
    out = cq.Workplane("YZ").rect(O, O).extrude(L).cut(cq.Workplane("YZ").rect(O - 2 * W, O - 2 * W).extrude(L))
    if p["plug_l"] > 0:                       # a printed end plug, filling the bore
        out = out.union(cq.Workplane("YZ").rect(O - 2 * W, O - 2 * W).extrude(p["plug_l"]))
    if p["clip_l"] > 0:                       # a printed clip on top, its tab cut into the tube's top wall
        c = p["clip_l"]
        out = out.cut(cq.Workplane().box(c, 6, W, centered=(False, True, False)).translate((140, 0, O / 2 - W)))
        out = out.union(cq.Workplane().box(c, 10, 8, centered=(False, True, False)).translate((140, 0, O / 2)))
    return out.rotate((0, 0, 0), (1, 0, 0), p["turn"])


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    items = [{"name": "tube", "kind": "stick", "material": "steel", "outer": O, "wall": W,
              "a": (0, 0, 0), "b": (L, 0, 0)}]
    if p["plug_l"] > 0:
        items.append({"name": "plug", "kind": "printed", "material": "petg"})
    if p["clip_l"] > 0:
        items.append({"name": "clip", "kind": "printed", "material": "petg"})
    return items
'''


def _src(turn=0.0, plug_l=20.0, clip_l=0.0):
    return (FRAME.replace('"turn": 0.0', f'"turn": {turn}').replace('"plug_l": 20.0', f'"plug_l": {plug_l}')
            .replace('"clip_l": 0.0', f'"clip_l": {clip_l}'))


def _part(tmp_path, src):
    s = DesignStore.create("a frame", base=str(tmp_path / "designs"))
    s.write_part("frame", src, intent="a tube with an end plug")
    return s


@pytest.mark.parametrize("turn", [0.0, 30.0])
def test_a_plug_in_a_tube_s_bore_is_turned_off_by_its_own_number(tmp_path, turn):
    src = _src(turn)
    assert pieces._also(pieces._build(src), pieces._build(src, {"plug_l": 0}), "plug") is None
    assert pieces.off_switch(_part(tmp_path, src), "frame", "plug") == {"param": "plug_l", "value": 0, "unit": "mm"}


@pytest.mark.parametrize("turn", [0.0, 30.0])
def test_a_clip_that_also_cuts_the_tube_wall_isn_t_the_off_switch(tmp_path, turn):
    src = _src(turn, plug_l=0.0, clip_l=30.0)
    assert pieces._also(pieces._build(src), pieces._build(src, {"clip_l": 0}), "clip") == "changes the tube"
    assert pieces.off_switch(_part(tmp_path, src), "frame", "clip") is None


def _tube(turn):
    built = pieces._build(_src(turn, plug_l=0.0))
    (sh,) = [x for x in consistency.shapes(built["declared"]) if x["name"] == "tube"]
    return built, sh


@pytest.mark.parametrize("turn", [0.0, 30.0, 75.0])
def test_a_tube_s_prism_is_its_walls_turned_as_built(turn):
    built, sh = _tube(turn)
    assert sh["outer"] == 25.4 and sh["wall"] == 1.651
    ((name, pr),) = pieces._prisms([sh], built["mesh"])
    o, w, m, L = 25.4, 1.651, 0.5, 300.0
    assert name == "tube"
    assert pr.volume == pytest.approx(((o - 2 * m) ** 2 - (o - 2 * w + 2 * m) ** 2) * (L - 2 * m), rel=0.01)
    t = np.radians(turn)
    up = np.array([0.0, -np.sin(t), np.cos(t)])               # the top wall's normal, turned as built
    side = np.array([0.0, np.cos(t), np.sin(t)])
    mid = np.array([150.0, 0.0, 0.0])
    corner = mid + (up + side) * (o / 2 - w / 2)              # in the steel at a corner: only the right turn has it
    assert pr.contains([mid + up * (o / 2 - w / 2), corner])[:2].tolist() == [True, True]
    assert pr.contains([mid, mid + up * (o / 2 - w - 0.2)]).tolist() == [False, False]   # the bore, to its face


def test_a_tube_whose_turn_the_build_doesn_t_show_and_a_plain_stick_stay_solid_rods():
    built, sh = _tube(0.0)
    rod = np.pi * (25.4 / 2 - 0.5) ** 2 * (300 - 1.0)
    away = {**sh, "a": sh["a"] + [0, 200.0, 0], "b": sh["b"] + [0, 200.0, 0]}     # nothing built there
    ((_, pr),) = pieces._prisms([away], built["mesh"])
    assert pr.volume == pytest.approx(rod, rel=0.02)
    plain = {k: v for k, v in sh.items() if k not in ("outer", "wall")}
    ((_, pr),) = pieces._prisms([plain], built["mesh"])
    assert pr.volume == pytest.approx(rod, rel=0.02)


def test_a_lumber_stick_declares_no_bore():
    (sh,) = consistency.shapes({"construction": [{"name": "leg", "kind": "stick", "material": "lumber", "size": "2x2",
                                                  "a": (0, 0, 0), "b": (0, 0, 400)}]})
    assert "wall" not in sh and "outer" not in sh
