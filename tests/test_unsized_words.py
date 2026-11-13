"""CALI-174 (#276): after #272, a printed piece of no declared size is said the same way on every surface, and two smaller
wordings from #275's review. Synthetic runs and a synthetic stool, never Theo's.

1. The study headline says what the card says (``unseen_said``), not "its walls are too thin for the voxels".
2. A two-material part's buckling notes judge each piece: its sheets are checked, its printed pieces named as not.
3. The Lighten panel leads with the unsized pieces' line, so its live button beside a "not checked" check is explained.
4. A pass near the line that also carries the joints or trim note says both.
5. A standard's name keeps its case ("EN 14183"), in the kid's book and on the card.
"""

import pytest

from caliper import answers, load_study as L, verdicts

STRIPS = "inside corner fillet strips"


def _unsized_run():
    case = {"name": "Stepping on the front edge of the top", "safety": 2.15, "holds": True, "lb": 250, "factor": 2, "governs": "plate",
            "fea": {"supported": True, "safety": 10.08}, "plate": {"done": True, "piece": "step", "safety": 2.15}}
    return {"id": "r", "part": "stool", "version": 4, "min_safety": 2.0, "safety": 2.15, "cases": [case],
            "unsized": [STRIPS], "unseen": [{"mm": None, "piece": STRIPS}], "thinnest_mm": 19.05, "spacing_mm": 4.76}


# --- 1 ---------------------------------------------------------------------------------------------------------------------
def test_the_headline_says_the_strips_size_isn_t_declared():
    from caliper import studies

    run = _unsized_run()
    head, good = studies._headline("load", run)
    assert "the inside corner fillet strips aren't checked: their size isn't declared" in head, head
    assert "too thin for the voxels" not in head and good is None, head
    v = verdicts.run(run)
    assert head.startswith(answers.unseen_said(run, v["cases"][0]).split(". ")[0]), head       # the card's words
    done = L.done_words(1, v, 2.15)
    assert "their size isn't declared" in done and "too thin for the voxels" not in done, done


# --- 2 ---------------------------------------------------------------------------------------------------------------------
#: Two plywood sides and a step on them: walls the load runs down.
STOOL = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 406.4, "d": 304.8, "h": 457.2}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    out = None
    for lo, hi in [((0, 0, 0), (t, d, h)), ((w - t, 0, 0), (w, d, h)), ((0, 0, h), (w, d, h + t))]:
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)]},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]}]
'''


@pytest.fixture
def stool(tmp_path):
    pytest.importorskip("cadquery")
    from caliper import construction as C
    from caliper.consistency import _sides, shapes, tolerance
    from caliper.design import DesignStore

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", STOOL, intent="a stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = shapes(C.declared(s, "stool"))
    _sides(mesh, pcs)
    tol = tolerance(mesh)
    load = {"name": "standing on the step", "force": (0.0, 0.0, -1000.0), "factor": 2.0,
            "lo": (0.0, 0.0, 476.25), "hi": (406.4, 304.8, 476.25)}
    return pcs, [load], tol


def test_a_two_material_part_s_buckling_is_judged_per_piece(stool):
    pcs, loads, tol = stool
    wood = L.material(pcs)
    printed = {**wood, "name": "PLA", "printed": True}
    alone = L.buckling_notes(pcs, loads, wood, tol, wood)
    assert alone == [L.BUCKLING_CHECKED], alone
    got = L.buckling_notes(pcs, loads, printed, tol, wood, printed_names=[STRIPS])
    assert got[0].startswith(L.BUCKLING_CHECKED), got
    assert "The inside corner fillet strips aren't checked for buckling: they're printed, and only sheets are." in got[0], got
    assert L.buckling_notes(pcs, loads, printed, tol, printed) == [L.BUCKLING]          # all printed: as it was
    assert L.buckling_notes(pcs, loads, printed, tol) == [L.BUCKLING]
    assert L.buckling_notes(pcs, loads, printed, tol, wood) == [L.BUCKLING]   # a mostly printed part (a carve): its printed walls carry it


def test_the_study_passes_its_printed_pieces_names():
    import inspect

    src = inspect.getsource(L.study)
    assert 'printed_names=[p["name"] for p in printed_pieces(ctx["declared"])]\n' in src
    assert 'if ctx.get("rest") is not None else None)]' in src                       # a sheet part's only


# --- 3 ---------------------------------------------------------------------------------------------------------------------
def test_lighten_s_lead_is_the_unsized_line(monkeypatch):
    from caliper import studies

    run = _unsized_run()
    assert L.unseen_lead(run) == ("The inside corner fillet strips aren't checked: their size isn't declared. Lighten leaves "
                                  "them out and cuts only the sheets.")
    assert L.unseen_lead({**run, "unsized": ["fillet strip"], "unseen": [{"mm": None, "piece": "fillet strip"}]}) == (
        "The fillet strip isn't checked: its size isn't declared. Lighten leaves it out and cuts only the sheets.")
    assert L.unseen_lead({"unseen": []}) == ""
    monkeypatch.setattr(studies, "made_of", lambda store, pid: {"study": "lighten"})
    monkeypatch.setattr(L, "_blocked", lambda store, pid: {"why": "unresolved", "lighten": "x", "carve": "y"})
    monkeypatch.setattr(L, "_only_trim_unseen", lambda store, pid: True)
    monkeypatch.setattr(L, "default_check", lambda store, pid: run)
    got = L.blocked(None, "stool")
    assert got["lighten"] == "" and got["lead"] == L.unseen_lead(run), got
    monkeypatch.setattr(L, "_only_trim_unseen", lambda store, pid: False)
    assert "lead" not in L.blocked(None, "stool")


def test_the_lighten_panel_leads_with_it():
    from .test_carve_click import JS, _page, _run

    out = _run(_page(["lightenLeadLine"], consts=["esc"], extra="""
out = lightenLeadLine({blocked: {lead: "The fillet strip isn't checked: its size isn't declared."}}) + '|' + lightenLeadLine({});"""))
    lead, none = out.split("|")
    assert "The fillet strip isn&#39;t checked: its size isn&#39;t declared." in lead or \
        "The fillet strip isn't checked: its size isn't declared." in lead, lead
    assert none.strip() == ""
    src = open(JS).read()
    view = src[src.index("function lightenView(p)"):]
    assert view.index("${lightenLeadLine(p)}") < view.index("Down until the safety runs out")


# --- 4 ---------------------------------------------------------------------------------------------------------------------
def _close_case(**more):
    return {"name": "Stepping up", "safety": 2.1, "holds": True, "lb": 200, "factor": 2, "governs": "fea",
            "fea": {"supported": True, "safety": 2.1}, **more}


#: A wall held square at its top by a joint nothing checks, that would fold under its limit if it gave (#265, on main).
BRACED = {"buckling": [{"done": True, "piece": "left side", "braced_by": "step", "safety": 6.0, "sway_safety": 1.5}]}


@pytest.mark.parametrize("more, extra, note, what", [
    (BRACED, {}, "its joints aren't checked: the left side is held square at its top by its joint to the step, which isn't "
                 "checked; if that joint gives, it racks (leans over with the walls beside it) and folds at 1.5 times over",
     "joints"),
    ({}, {"trim": ["fillet strip"]}, "the fillet strip isn't checked: it's glued trim", "glued trim"),   # trim alone: #280
], ids=["joints", "trim"])
def test_a_close_pass_with_a_note_says_both(more, extra, note, what):
    from caliper import studies

    run = {"id": "r", "part": "stool", "version": 1, "min_safety": 2.0, "safety": 2.1, "cut": True,
           "cases": [_close_case(**more)], **extra}
    v = verdicts.case(run, run["cases"][0])
    assert v["kind"] == "close" and v["joints"], v
    assert v["word"] == f"holds, close to the line, and {what} not checked", v
    assert v["short"] == f"holds 2.1x, close to the line, and {what} not checked", v
    text = answers._case_line("stool", run, run["cases"][0], None, False, False)["text"]
    assert text == f"Holds stepping up, 2.1 times over 400 lb (200 lb, twice over): close to the 2 it needs, and {note}.", text
    head, _ = studies._headline("load", run)
    assert head.startswith(f"holds, close to the line, and {what} not checked — weakest"), head


def test_close_by_the_cap_isn_t_close_to_the_line(monkeypatch):
    """JOINT_CAP set to "close" makes a 5.6x pass amber, not near its line: it never says "close to the line" (#265's rule)."""
    monkeypatch.setattr(verdicts, "JOINT_CAP", "close")
    run = {"min_safety": 2.0, "cut": True, "cases": [_close_case(**BRACED)]}
    far = {**run["cases"][0], "safety": 5.6, "fea": {"supported": True, "safety": 5.6}}
    v = verdicts.case(run, far)
    assert v["kind"] == "close" and "close to the line" not in v["word"] + v["short"], v
    assert "close to the line" in verdicts.case(run, run["cases"][0])["word"]


def test_a_plain_pass_with_a_note_is_unchanged():
    v = verdicts._make("holds", 3.1, joints=True)
    assert v["word"] == "holds, joints not checked" and v["short"] == "holds 3.1x, joints not checked"
    assert verdicts._make("close", 2.1)["word"] == "holds, close to the line"


# --- 5 ---------------------------------------------------------------------------------------------------------------------
def test_a_standard_s_name_keeps_its_case():
    from caliper import kidbook

    assert answers.lowered("EN 14183 load, 150 kg") == "EN 14183 load, 150 kg"
    assert answers.lowered("Adult stepping up") == "adult stepping up"
    assert answers.lowered("Dad stands on the ASTM F2057 top") == "dad stands on the ASTM F2057 top"
    c = {"name": "EN 14183 load", "safety": 3.1, "holds": True, "lb": 330, "factor": 2, "min_safety": 2.0, "verdict": {"kind": "holds"}}
    say = kidbook._strength_page({"stool": [c]}, ["stool"])["say"]
    assert "It should hold EN 14183 load," in say, say
    run = {"min_safety": 2.0, "cut": True, "cases": [c]}
    text = answers._case_line("stool", run, {**c, "governs": "fea", "fea": {"supported": True, "safety": 3.1}}, None, False,
                              False)["text"]
    assert text.startswith("Holds EN 14183 load,"), text
