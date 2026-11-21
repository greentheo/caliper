"""CALI-220 (#375): the studies read a part in its own frame, wherever it sits in the design (#374's must-fix).

The strength check voxelized the POSED mesh (``store.part_geometry``), while a script's loads(), HELD and construction()
pieces are in the script's own frame. Every checked part sat at pose 0 until Copy…/Move… (#374), so it never showed. A
moved part would have been pushed in the wrong place, or refused. Now every study that pairs the build with what the
script declares reads ``store.part_local``: the part unposed, where its declarations are."""

import json
import os
import re

import pytest

from caliper import load_study as L
from caliper.design import DesignStore

from .test_posts import LEGGED

pytest.importorskip("cadquery")
pytest.importorskip("whittle")


def _stool(tmp_path, position=None, rotation=None):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    if position or rotation:
        part = next(p for p in store.assembly.parts if p.id == "stool")
        part.position, part.rotation = list(position or [0, 0, 0]), list(rotation or [0, 0, 0])
        store.save()
        store = DesignStore.load(store.root)
    return store


def _said(rec):
    """What a check says, case by case: its numbers, what governs, and each joint's."""
    out = []
    for c in rec["cases"]:
        joints = [(r.get("between"), r.get("mode"), r.get("safety")) for r in (c.get("joints") or {}).get("rows") or []]
        out.append((c["name"], c["safety"], c["holds"], c["governs"], (c.get("fea") or {}).get("safety"),
                    (c.get("plate") or {}).get("safety_across"), joints))
    return out


def test_a_moved_and_turned_part_checks_as_it_does_where_it_was_drawn(tmp_path):
    here = L.study(_stool(tmp_path / "a"), "stool")
    moved = _stool(tmp_path / "b", position=[300.0, 0.0, 0.0], rotation=[0.0, 0.0, 90.0])
    pose = moved.part_pose("stool")
    assert pose[0][3] == pytest.approx(300.0) and abs(pose[0][0]) < 1e-9                 # moved, and a quarter turn
    there = L.study(moved, "stool")
    assert len(here["cases"]) == 2 and _said(there) == _said(here)
    assert there["safety"] == here["safety"] and there["holds"] == here["holds"]


def test_a_part_s_own_frame_is_its_unposed_build(tmp_path):
    import numpy as np

    moved = _stool(tmp_path, position=[300.0, 0.0, 0.0], rotation=[0.0, 0.0, 90.0])
    local = moved.part_local("stool").require_mesh()
    posed = moved.part_geometry("stool").require_mesh()
    assert not np.allclose(local.bounds, posed.bounds)                          # the design's mesh moved; its own didn't
    assert np.allclose(local.copy().apply_transform(moved.part_pose("stool")).bounds, posed.bounds, atol=1e-6)


# --- the viewer: a run's overlay, made in the part's frame, drawn where the part is now --------------------------------

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
THREE_JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "vendor", "three",
                        "three.module.js")


def test_a_run_made_before_a_move_draws_on_the_moved_part():
    """A load run's heat, box and arrow, and a Lighten or Carve station, are in the part's own frame. The viewer gives
    them the part's pose now, as the server poses the part: a point on the drawn part lands on the moved part's."""
    import numpy as np

    from caliper.measure import pose_matrix

    from .test_carve_click import _fn, _node, _run

    src = open(JS).read()
    part_frame = re.search(r"^const PART_FRAME = .*?;\n", src, re.M).group(0)
    script = (f"import * as THREE from {json.dumps(os.path.abspath(THREE_JS))};\n" + part_frame
              + "const S = { design: { parts: [{ id: 'stool', position: [300, 0, 0], rotation: [0, 0, 90] },"
                " { id: 'plain' }] } };\n"
              "const partOf = (pid) => (S.design && S.design.parts.find((x) => x.id === pid)) || {};\n"
              + "\n".join(_fn(src, n) for n in ("partPose", "overlayPose")) + """
const m = overlayPose('stool', 'load');
const pt = new THREE.Vector3(10, 20, 30).applyMatrix4(m);
const out = { m: m.elements, pt: pt.toArray(),
  kinds: ['load', 'lighten', 'carve', 'frame', 'parametric', 'whittle'].map((k) => overlayPose('stool', k) !== null),
  plain: overlayPose('plain', 'load').elements };
console.log(JSON.stringify(out));""")
    got = _run(script)
    T = pose_matrix([300, 0, 0], [0, 0, 90])
    assert np.allclose(np.asarray(got["m"]).reshape(4, 4).T, T, atol=1e-9)          # three's column-major, the server's
    assert np.allclose(got["pt"], (T @ [10, 20, 30, 1])[:3], atol=1e-9)
    assert got["kinds"] == [True, True, True, True, False, False]                     # the drag studies run posed
    assert np.allclose(np.asarray(got["plain"]).reshape(4, 4), np.eye(4))
    show_heat, show_station = _fn(src, "showHeat"), _fn(src, "showStation")
    assert "const pose = overlayPose(pid, 'load');" in show_heat and "stationMesh.applyMatrix4(pose)" in show_heat
    assert show_station.index("if (pose) geom.applyMatrix4(pose);") < show_station.index("geom.computeVertexNormals();")
    assert "stationMesh.applyMatrix4" not in show_station                               # its ghost is posed already


def _plain(x):
    """A check's result as data: an assertion as its name, pass and words; numbers to 6 places."""
    if hasattr(x, "passed") and hasattr(x, "name"):
        return ("assert", x.name, x.passed, getattr(x, "message", None))
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in sorted(x.items())}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    try:
        import numpy as np

        if isinstance(x, np.ndarray):
            return _plain(x.tolist())
        if isinstance(x, np.generic):
            return _plain(x.item())
    except ImportError:  # pragma: no cover
        pass
    return x


def test_every_check_that_reads_the_part_against_its_script_reads_the_same_moved(tmp_path):
    """The pieces against the build, the joints, the marks, the tip check, the shopping list and the panels: each pairs the
    build with what the script declares, so each reads the part in its own frame, moved or not."""
    from caliper import consistency, construction, joints, marks, pictures, tipping

    def read(store):
        return {"checked": consistency.checked(store, "stool"), "joints": joints.listed(store, "stool"),
                "marks": marks.of(store, "stool"), "tipping": tipping.check(store, "stool"),
                "report": construction.report(store, "stool"), "panels": pictures.panels(store, "stool")}

    here = _plain(read(_stool(tmp_path / "a")))
    there = _plain(read(_stool(tmp_path / "b", position=[300.0, 0.0, 0.0], rotation=[0.0, 0.0, 90.0])))
    for k in here:
        assert there[k] == here[k], k


def test_a_scenario_saved_on_a_moved_part_is_on_the_part(tmp_path):
    """The editor's boxes are the part's own frame (the viewer draws them under its pose). Saved on a moved part, a case
    touches the part, as it does unmoved, and the check reads it."""
    from caliper import scenarios

    moved = _stool(tmp_path, position=[1000.0, 0.0, 0.0], rotation=[0.0, 0.0, 90.0])     # clear of where it was drawn
    got = scenarios.get(moved, "stool")
    rows = [dict(r) for r in got["scenarios"]]
    rows[0]["amount"] = float(rows[0].get("amount") or 100.0) * 1.1           # an edit: a heavier load, same place
    scenarios.put(moved, "stool", rows, got["supports"])                       # on main: "doesn't touch the part"
    rec = L.study(DesignStore.load(moved.root), "stool")
    assert len(rec["cases"]) == 2 and all(c.get("safety") is not None for c in rec["cases"])


#: the modules that pair a part's build with what its script declares: the part's own frame, never the posed mesh
OWN_FRAME = ("load_study", "lighten", "carve", "coupons", "pictures", "trials", "consistency", "construction", "joints",
             "joint_check", "marks", "tipping", "scenarios")


def test_no_check_that_reads_a_part_against_its_script_reads_the_posed_mesh():
    """A guard: a new read of ``part_geometry`` in one of these would put the part where it sits in the design while its
    loads and pieces stay in its own frame. Where a part sits is for the fit, the drag and the build plan."""
    src = os.path.join(os.path.dirname(__file__), "..", "src", "caliper")
    found = [m for m in OWN_FRAME if "part_geometry(" in open(os.path.join(src, f"{m}.py")).read()]
    assert found == [], found
