"""CALI-176 (#280): Lighten's rim reads the one contact finder, and three wordings after #275 and #276.

1. ``lighten.panels`` takes its joint cells from ``joints.contacts`` at its own cells (reach tol + 0.75 x a cell), so the joint
   list, the shopping list and the rim can't disagree. The finder now sees a piece lying on a sheet's face (a cleat), which
   Lighten's own probes saw and the edge probes never did.
2. A run made with #272's code reads its undeclared strips on main, with #275's wood joints: not checked, said.
3. The build book's cell gives the card's reason, not "too coarse".
4. A pass whose only unchecked brace is glued trim says "glued trim", not "joints", and a run's short keeps "close".
Synthetic parts and runs, never Theo's.
"""

import pytest

from caliper import answers, verdicts

#: Two plywood sides, a step, and a 2x2 cleat lying on the left side's inner face.
CLEATED = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 406.4, "d": 304.8, "h": 457.2, "c": 38.1, "z": 300.0}


def _boxes(p):
    t, w, d, h, c, z = p["t"], p["w"], p["d"], p["h"], p["c"], p["z"]
    return [((0, 0, 0), (t, d, h)), ((w - t, 0, 0), (w, d, h)), ((0, 0, h), (w, d, h + t)),
            ((t, 0, z - c / 2), (t + c, d, z + c / 2))]


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p):
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, c, z = p["t"], p["w"], p["d"], p["h"], p["c"], p["z"]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)]},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]},
            {"name": "cleat", "kind": "stick", "material": "lumber", "size": "2x2",
             "a": (t + c / 2, 0, z), "b": (t + c / 2, d, z)}]
'''


@pytest.fixture
def cleated(tmp_path):
    pytest.importorskip("cadquery")
    from caliper import construction as C
    from caliper import fasteners
    from caliper.consistency import _sides, shapes, tolerance
    from caliper.design import DesignStore

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", CLEATED, intent="a stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = shapes(C.declared(s, "stool"))
    _sides(mesh, pcs)
    fasteners.keys(pcs)
    return pcs, tolerance(mesh)


# --- 1 ---------------------------------------------------------------------------------------------------------------------
def test_a_cleat_on_a_face_is_a_contact_the_edge_probes_miss(cleated):
    from caliper import fasteners, joints

    pcs, tol = cleated
    assert ("cleat", "left side") not in fasteners.edge_joints(pcs, tol)
    got = joints.contacts(pcs, tol)
    assert got[("cleat", "left side")]["how"] == "face", got.get(("cleat", "left side"))
    assert ("cleat", "right side") not in got                                      # across the stool: no contact
    on = got[("cleat", "left side")]["on"]["left side"]
    assert on and min(p[1] for p in on) > 300.0 - 38.1 and max(p[1] for p in on) < 300.0 + 38.1, on   # under it, only


def test_the_rim_s_cells_are_the_finder_s_at_the_cells_given(cleated):
    import numpy as np

    from caliper import joints

    pcs, tol = cleated
    g = np.stack(np.meshgrid(np.arange(2.5, 305, 5.0), np.arange(2.5, 457, 5.0), indexing="ij"), -1).reshape(-1, 2)
    got = joints.contacts(pcs, tol, reach=tol + 0.75 * 5.0, at={"left side": g})
    pts = np.asarray(got[("cleat", "left side")]["on"]["left side"])
    assert len(pts) and all(any(np.allclose(p, q) for q in g) for p in pts[:20])   # its own cells, not a grid of the finder's
    assert pts[:, 1].min() > 300.0 - 38.1 - 5.0 and pts[:, 1].max() < 300.0 + 38.1 + 5.0, pts
    assert len(joints.contacts(pcs, tol, reach=tol + 0.75 * 5.0)[("cleat", "left side")]["on"]["left side"]) != len(pts)


def test_lighten_s_rim_reads_the_finder():
    import inspect

    from caliper import lighten

    src = inspect.getsource(lighten)
    assert "def _contacts(" not in src                                              # its own probes are gone
    assert 'J.contacts(ctx["pieces"], ctx["tol"], reach=ctx["tol"] + 0.75 * s,' in inspect.getsource(lighten._met)
    assert "met = _met(ctx," in inspect.getsource(lighten.panels)


def test_a_piece_in_reach_but_not_touching_is_no_joint(tmp_path):
    """A pair is a joint by the tolerance alone: Lighten's wider reach finds where a piece is near, never a new joint."""
    pytest.importorskip("cadquery")
    from caliper import construction as C
    from caliper import fasteners, joints
    from caliper.consistency import _sides, shapes, tolerance
    from caliper.design import DesignStore

    gap = 8.0
    script = CLEATED.replace('((t, 0, z - c / 2), (t + c, d, z + c / 2))', f'((t + {gap}, 0, z - c / 2), (t + {gap} + c, d, z + c / 2))').replace(
        '"a": (t + c / 2, 0, z), "b": (t + c / 2, d, z)', f'"a": (t + {gap} + c / 2, 0, z), "b": (t + {gap} + c / 2, d, z)')
    assert script.count(f"{gap}") == 4
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = shapes(C.declared(s, "stool"))
    _sides(mesh, pcs)
    fasteners.keys(pcs)
    tol = tolerance(mesh)
    assert tol < gap / 2, tol                                                      # off the face by more than the probe and tol
    assert ("cleat", "left side") not in joints.contacts(pcs, tol)
    assert ("cleat", "left side") not in joints.contacts(pcs, tol, reach=tol + 20.0)


def test_a_face_contact_is_listed_and_bought_for(tmp_path, cleated):
    from caliper import fasteners

    pcs, tol = cleated
    assert ("cleat", "left side") in fasteners.joints(pcs, tol)                    # glue and screws for it


# --- 2, 3: #272's unsized strips, read on main --------------------------------------------------------------------------
STRIPS = "inside corner fillet strips"


def _unsized(**more):
    case = {"name": "Stepping on the front edge of the top", "safety": 2.15, "holds": True, "lb": 250, "factor": 2,
            "governs": "plate", "fea": {"supported": True, "safety": 10.08}, "plate": {"done": True, "piece": "step", "safety": 2.15}}
    return {"id": "r", "part": "stool", "version": 4, "min_safety": 2.0, "safety": 2.15, "cut": True, "cases": [case],
            "unsized": [STRIPS], "unseen": [{"mm": None, "piece": STRIPS}], "thinnest_mm": 19.05, "spacing_mm": 4.76, **more}


def test_a_run_with_unsized_strips_and_wood_joints_reads_not_checked():
    """#275's review: on its branch, #272's run read its unsized strips as nothing ("holds 2.1x, joints not checked")."""
    run = _unsized(wood_joints=4)
    v = verdicts.case(run, run["cases"][0])
    assert v["kind"] == "unchecked" and not v["counts_as_pass"], v
    assert "the inside corner fillet strips aren't checked: their size isn't declared" in v["why"], v
    assert "holds" not in verdicts.run(run)["short"], verdicts.run(run)
    line = answers._case_line("stool", run, run["cases"][0], None, False, False)
    assert line["status"] == "warn" and "their size isn't declared" in line["text"], line
    assert not line["text"].startswith("Holds"), line


def test_the_book_cell_gives_the_card_s_reason():
    from caliper import release

    run = _unsized(wood_joints=4)
    c = {**run["cases"][0], "min_safety": 2.0, "verdict": verdicts.case(run, run["cases"][0])}
    cell, breaks = release._safety_cell(c)
    import html

    assert html.unescape(cell) == ("not checked: the step's plate check holds 2.15 times over; the inside corner fillet strips "
                                   "aren't checked: their size isn't declared"), cell
    assert breaks == "—"
    plain = {**c, "verdict": {**c["verdict"], "why": ""}}
    assert release._safety_cell(plain)[0] == "not resolved: too coarse to see its walls"


# --- 4 ---------------------------------------------------------------------------------------------------------------------
def _held(safety=3.1, **more):
    case = {"name": "Stepping up", "safety": safety, "holds": True, "lb": 200, "factor": 2, "governs": "fea",
            "fea": {"supported": True, "safety": safety}}
    return {"id": "r", "part": "stool", "version": 1, "min_safety": 2.0, "safety": safety, "cut": True, "cases": [case], **more}


def test_trim_alone_says_trim_not_joints():
    from caliper import kidbook, release, trials  # noqa: F401

    run = _held(trim=["fillet strip"])
    v = verdicts.case(run, run["cases"][0])
    assert v["joints"] and v["word"] == "holds, glued trim not checked" and v["short"] == "holds 3.1x, glued trim not checked", v
    assert v["why"] == "glued trim not checked"
    assert verdicts.run(run)["short"] == "holds 3.1x, glued trim not checked"
    assert answers.if_braced(v) == ", its glued trim not checked"
    c = {**run["cases"][0], "min_safety": 2.0, "verdict": v}
    assert release._safety_cell(c)[0] == "3.1x, its glued trim not checked"
    say = kidbook._strength_page({"stool": [c]}, ["stool"])["say"]
    assert "It should hold stepping up, 3.1 times over 400 lb (200 lb, twice over), its glued trim not checked." in say, say
    g = verdicts.goal(True, joints="The fillet strip isn't checked: it's glued trim", brace={"trim": ["fillet strip"]})
    assert g["word"] == "holds, glued trim not checked" and answers.if_braced(g) == ", its glued trim not checked", g


@pytest.mark.parametrize("more", [{"wood_joints": 4}, {"trim": ["fillet strip"], "wood_joints": 4}], ids=["wood", "both"])
def test_wood_joints_still_say_joints(more):
    run = _held(**more)
    v = verdicts.case(run, run["cases"][0])
    assert v["word"] == "holds, joints not checked" and answers.if_braced(v) == answers.IF_JOINTS, v


def test_a_run_s_short_keeps_close_with_a_note():
    run = _held(2.1, wood_joints=4)
    assert verdicts.case(run, run["cases"][0])["short"] == "holds 2.1x, close to the line, and joints not checked"
    assert verdicts.run(run)["short"] == "holds 2.1x, close to the line, and joints not checked", verdicts.run(run)


# --- 5: the rim sees every material; the joint list, wood (#281 review) -----------------------------------------------------
def _pieces(script, tmp_path):
    pytest.importorskip("cadquery")
    from caliper import construction as C
    from caliper import fasteners
    from caliper.consistency import _sides, shapes, tolerance
    from caliper.design import DesignStore

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = shapes(C.declared(s, "stool"))
    _sides(mesh, pcs)
    fasteners.keys(pcs)
    return pcs, tolerance(mesh)


def _rim(pcs, tol, name, s=5.0):
    """Lighten's rim on one panel, as panels() reads it: its cells, and each cell's centre in 3D."""
    import numpy as np

    from caliper import lighten
    from caliper.consistency import _frame

    pc = next(p for p in pcs if p["name"] == name)
    o, u, v, _, flat = _frame(pc["polys"][0])
    lo = flat.min(axis=0)
    shape = tuple(int(x) for x in np.ceil(np.ptp(flat, axis=0) / s))
    ij = np.stack(np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij"), -1).reshape(-1, 2)
    g = lo + (ij + 0.5) * s
    met = lighten._met({"pieces": pcs, "tol": tol}, [pc], {id(pc): (lo, shape, g)}, s)[id(pc)]
    return met, o + g[:, :1] * u + g[:, 1:] * v


STEEL = CLEATED.replace('"c": 38.1', '"c": 25.4').replace(
    '{"name": "cleat", "kind": "stick", "material": "lumber", "size": "2x2",',
    '{"name": "tube", "kind": "stick", "material": "steel", "outer": 25.4, "wall": 1.65,')
XPS = CLEATED.replace('{"name": "left side", "kind": "sheet", "material": "plywood",',
                      '{"name": "left side", "kind": "sheet", "material": "xps",')


@pytest.mark.parametrize("script, other, c", [(STEEL, "tube", 25.4), (XPS, "cleat", 38.1)], ids=["steel tube", "xps side"])
def test_the_rim_keeps_a_piece_of_any_material(script, other, c, tmp_path):
    """A steel tube on a plywood side, or a lumber brace on a foam side: the rim keeps the wood (the foam) under it, and the
    foam side keeps its joint rim under the step, while the joint list and the shopping list stay wood's."""
    from caliper import fasteners, joints

    assert script != CLEATED and script.count(other) >= 1
    pcs, tol = _pieces(script, tmp_path)
    met, xyz = _rim(pcs, tol, "left side")
    under = abs(xyz[:, 2] - 300.0) < c / 2 - 5.0                                    # cells under the tube or brace
    assert under.sum() > 20 and met[under].all(), (under.sum(), met[under].sum())
    top = xyz[:, 2] > 457.2 - 2.0                                                    # its top edge, under the step
    assert top.sum() > 5 and met[top].all(), (top.sum(), met[top].sum())
    assert not met[(abs(xyz[:, 2] - 150.0) < 20.0)].any()                           # its middle, free to cut
    pair = tuple(sorted((other, "left side")))
    assert pair not in joints.contacts(pcs, tol)                                     # the joint list: wood to wood
    assert pair not in fasteners.joints(pcs, tol)
    assert pair in joints.contacts(pcs, tol, materials=None)                         # every material: the rim's


def test_lighten_s_rim_passes_every_material():
    import inspect

    from caliper import lighten

    assert "materials=None" in inspect.getsource(lighten._met)
