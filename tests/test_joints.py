"""CALI-156 (#222) slice A: Caliper reads a part's joints. A module-level ``JOINTS`` list (data, like ``HOLES``) names two
pieces and a kind; it's read from the script's text, never run. Each entry's pieces must exist and touch; every contact with
no entry is a joint too, an assumed butt with glue and screws. A piece that runs through another's outline is a through
tenon, and the outline needs the mortise (Theo's step-stool-5: the stringer "through the left and right side", drawn
through plain side panels). A synthetic stool, not Theo's."""

import pytest

pytest.importorskip("cadquery")

from caliper import construction as C  # noqa: E402
from caliper import fasteners, joints  # noqa: E402
from caliper.consistency import _sides, shapes, tolerance  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

#: Two sides, a step resting on them, and a stringer through both sides, flush with their outer faces: no mortise drawn.
STOOL = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 406.4, "d": 304.8, "h": 457.2, "mortise": 0}

JOINTS = [
    {"pieces": ["step", "left side"], "kind": "bevel", "fix": ["glue", "screws"]},
    {"pieces": ["step", "right side"], "kind": "butt", "fix": ["glue", "screws"]},
]


def _boxes(p):
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    return {"left side": ((0, 0, 0), (t, d, h)), "right side": ((w - t, 0, 0), (w, d, h)),
            "step": ((0, 0, h), (w, d, h + t)),
            "bottom stringer": ((0, d / 2 - t / 2, 50.8), (w, d / 2 + t / 2, 50.8 + 76.2))}


def build(params):
    p = {**PARAMS, **(params or {})}
    out = None
    for lo, hi in _boxes(p).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    y0, y1, z0, z1 = d / 2 - t / 2, d / 2 + t / 2, 50.8, 50.8 + 76.2
    hole = lambda x: [[(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]] if p["mortise"] else []
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)], "holes": hole(0)},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)], "holes": hole(w)},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]},
            {"name": "bottom stringer", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, y0, z0), (w, y0, z0), (w, y0, z1), (0, y0, z1)]}]
'''
MORTISED = STOOL.replace('"mortise": 0', '"mortise": 1')
BAD = STOOL.replace('''    {"pieces": ["step", "right side"], "kind": "butt", "fix": ["glue", "screws"]},''',
                    '''    {"pieces": ["step", "right side"], "kind": "butt", "fix": ["glue", "screws"]},
    {"pieces": ["shelf", "left side"], "kind": "dado", "fix": ["glue"]},
    {"pieces": ["step", "bottom stringer"], "kind": "butt", "fix": ["glue"]},
    {"pieces": ["left side", "right side"], "kind": "weld", "fix": ["tape"]},''')


def _built(tmp_path, script):
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a stool")
    d = C.declared(s, "stool")
    mesh = s.part_geometry("stool").require_mesh()
    pcs = shapes(d)
    _sides(mesh, pcs)
    return s, d, pcs, tolerance(mesh), mesh


def test_joints_are_read_from_the_script_s_text_never_run():
    assert joints.read(STOOL) == [{"pieces": ["step", "left side"], "kind": "bevel", "fix": ["glue", "screws"]},
                                  {"pieces": ["step", "right side"], "kind": "butt", "fix": ["glue", "screws"]}]
    assert joints.read("PARAMS = {}") == []
    assert joints.read("JOINTS = [{'pieces': ['a', 'b'], 'kind': __import__('os').getcwd()}]") == []   # not literal: unread


def test_a_piece_through_another_is_found_and_its_mortise_wanted(tmp_path):
    """The stringer runs through both sides: through tenons. fasteners.joints probed edges only and missed them (#272's
    review), so the shopping list had no glue or screws there."""
    _, _, pcs, tol, _ = _built(tmp_path, STOOL)
    got = joints.contacts(pcs, tol)
    assert got[("bottom stringer", "left side")]["how"] == "through" and got[("bottom stringer", "right side")]["how"] == "through"
    assert got[("left side", "step")]["how"] == "edge" and got[("right side", "step")]["how"] == "edge"
    assert fasteners.estimate(pcs, tol)["joints"] == 4                                  # the two through tenons count


def test_a_through_piece_with_no_mortise_in_the_outline_fails_in_words(tmp_path):
    _, d, pcs, tol, mesh = _built(tmp_path, STOOL)
    (r,) = [x for x in joints.check(STOOL, d, mesh) if x.id == "mortises"]
    assert r.status == "fail"
    assert ("the bottom stringer passes through the left side, but the left side's outline has no hole where it goes: cut "
            "the mortise into the left side's outline") in r.detail, r.detail
    assert "the right side's outline has no hole" in r.detail


def test_a_mortise_in_the_outline_clears_it(tmp_path):
    _, d, pcs, tol, mesh = _built(tmp_path, MORTISED)
    (r,) = [x for x in joints.check(MORTISED, d, mesh) if x.id == "mortises"]
    assert r.status == "pass", r.detail


def test_each_entry_s_pieces_exist_touch_and_say_a_kind_and_fix_it_knows(tmp_path):
    _, d, pcs, tol, mesh = _built(tmp_path, BAD)
    (r,) = [x for x in joints.check(BAD, d, mesh) if x.id == "joints"]
    assert r.status == "fail"
    for said in ("JOINTS names the shelf, which isn't one of its pieces",
                 "JOINTS joins the step and the bottom stringer, which don't touch",
                 "JOINTS gives the left side and the right side the kind \"weld\", which isn't one of butt, bevel",
                 "and the fix \"tape\", which isn't glue, screws or dowels"):
        assert said in r.detail, r.detail
    _, d2, _, _, mesh2 = _built(tmp_path / "ok", STOOL)
    (ok,) = [x for x in joints.check(STOOL, d2, mesh2) if x.id == "joints"]
    assert ok.status == "pass", ok.detail


def test_every_contact_without_an_entry_is_listed_as_an_assumed_butt(tmp_path):
    s, *_ = _built(tmp_path, STOOL)
    got = {tuple(j["pieces"]): j for j in joints.listed(s, "stool")}
    assert got[("left side", "step")] == {"pieces": ["left side", "step"], "kind": "bevel", "fix": ["glue", "screws"],
                                         "assumed": False}
    assert got[("bottom stringer", "left side")] == {"pieces": ["bottom stringer", "left side"], "kind": "through tenon",
                                                     "fix": ["glue", "screws"], "assumed": True}
    assert len(got) == 4


def test_a_round_checks_the_joints(tmp_path):
    """The designer's round fails on a through piece with no mortise, and is told where to cut it."""
    from caliper import chat

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return STOOL if len(seen) == 1 else MORTISED
    res = chat.author_part(s, "stool", "a step stool with a stringer through both sides", author=author, use_llm=False,
                           promote_feedback=False, max_rounds=3)
    assert len(seen) == 2 and "mortises" in seen[1] and "cut the mortise into the left side's outline" in seen[1], seen[1]
    assert res.ok, res.reply


# --- listed in Built-from and the book --------------------------------------------------------------------------------------
def test_built_from_lists_the_joints(tmp_path):
    s, *_ = _built(tmp_path, STOOL)
    got = C.report(s, "stool")["joints"]
    assert {tuple(j["pieces"]) for j in got} == {("left side", "step"), ("right side", "step"),
                                                 ("bottom stringer", "left side"), ("bottom stringer", "right side")}


def test_the_page_says_each_joint_and_that_none_is_checked():
    from .test_carve_click import _page, _run

    out = _run(_page(["jointsHtml"], consts=["esc"], extra="""
out = jointsHtml({joints: [{pieces: ['left side', 'step'], kind: 'bevel', fix: ['glue', 'screws'], assumed: false},
                           {pieces: ['bottom stringer', 'left side'], kind: 'through tenon', fix: ['glue', 'screws'], assumed: true}]});"""))
    said = " ".join(out.split())
    assert "left side and step: bevel, glue and screws" in said
    assert 'bottom stringer and left side: through tenon <span class="muted">(assumed: none was said)</span>, glue and screws' \
        in said, said
    assert "The strength check takes these joints as solid wood: they aren't checked." in said


def test_the_book_says_each_joint_and_that_none_is_checked():
    import inspect

    from caliper import release

    html = "".join(release.joints_html({"joints": {"stool": [
        {"pieces": ["left side", "step"], "kind": "bevel", "fix": ["glue", "screws"], "assumed": False},
        {"pieces": ["bottom stringer", "left side"], "kind": "through tenon", "fix": ["glue", "screws"], "assumed": True}]}}))
    assert "<h2>How it joins</h2>" in html and "<td>left side and step</td><td>bevel</td><td>glue and screws</td>" in html
    assert "<td>through tenon (assumed: none was said)</td>" in html
    assert "The strength check takes these joints as solid wood: they aren't checked." in html
    assert "out += joints_html(rec, name)" in inspect.getsource(release.book)
    assert release.joints_html({}) == []


# --- the verdict says it: #265's JOINT_CAP path, Theo's ✓ with a note (#222 Q1) -------------------------------------------
LOADED = MORTISED + '''

def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    w, d, h, t = p["w"], p["d"], p["h"], p["t"]
    return [{"name": "standing on the step", "lb": 100, "factor": 2.0,
             "lo": (w / 2 - 50, d / 2 - 50, h + t - 2), "hi": (w / 2 + 50, d / 2 + 50, h + t)}]
'''


def _case(safety=5.0):
    return {"name": "standing on the step", "lb": 100, "factor": 2.0, "safety": safety, "holds": safety >= 2.0,
            "governs": "fea", "fea": {"supported": True, "safety": safety}}


def test_a_pass_on_a_multi_piece_wood_part_says_its_joints_aren_t_checked():
    from caliper import answers, verdicts

    run = {"min_safety": 2.0, "cut": True, "wood_joints": 4}
    v = verdicts.case(run, _case())
    assert v["kind"] == verdicts.JOINT_CAP and v["joints"] is True and v["why"] == "joints not checked", v
    text = answers._case_line("p", {**run, "cases": []}, _case(), None, False, False)["text"]
    assert "Its joints aren't checked: the check takes its 4 joints as solid wood." in text, text
    assert verdicts.case({"min_safety": 2.0, "cut": True}, _case()).get("joints") is None       # one piece: nothing to say
    assert verdicts.case(run, _case(1.0))["kind"] == "fails"                                     # a ✗ stays a ✗


def test_the_page_says_it_too():
    from .test_carve_click import _page, _run

    line = _run(_page(["jointsLine", "safetyNum"], consts=["esc"], extra="""
out = jointsLine({verdict: {joints: true, brace: {joints_n: 4}}}, {min_safety: 2});"""))
    assert "<b>Joints not checked:</b> the check takes its 4 joints as solid wood." in " ".join(line.split()), line


def test_a_strength_run_records_how_many_joints_it_took_as_solid(tmp_path):
    from caliper import load_study

    pytest.importorskip("whittle")
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", LOADED, intent="a stool")
    rec = load_study.study(s, "stool")
    assert rec["wood_joints"] == 4, rec.get("wood_joints")


# --- what the first tests didn't reach ------------------------------------------------------------------------------------
#: The stringer standing 1 in proud of each side: its ends are outside the sides, so only the through finder sees it.
PROUD = STOOL.replace('''"bottom stringer": ((0, d / 2 - t / 2, 50.8), (w, d / 2 + t / 2, 50.8 + 76.2))}''',
                      '''"bottom stringer": ((-25.4, d / 2 - t / 2, 50.8), (w + 25.4, d / 2 + t / 2, 50.8 + 76.2))}''').replace(
    '''"outline": [(0, y0, z0), (w, y0, z0), (w, y0, z1), (0, y0, z1)]}]''',
    '''"outline": [(-25.4, y0, z0), (w + 25.4, y0, z0), (w + 25.4, y0, z1), (-25.4, y0, z1)]}]''')
#: A shelf set 6 mm into each side (a dado), not through it.
DADO = STOOL.replace('''            "bottom stringer": ''', '''            "shelf": ((t - 6, 0, 228.6), (w - t + 6, d, 228.6 + t)),
            "bottom stringer": ''').replace(
    '''            {"name": "bottom stringer", "kind": "sheet"''',
    '''            {"name": "shelf", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t - 6, 0, 228.6), (w - t + 6, 0, 228.6), (w - t + 6, d, 228.6), (t - 6, d, 228.6)]},
            {"name": "bottom stringer", "kind": "sheet"''')
#: A hole in each side, but not where the stringer goes.
ELSEWHERE = MORTISED.replace("hole = lambda x: [[(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]]",
                             "hole = lambda x: [[(x, 30, 300), (x, 60, 300), (x, 60, 350), (x, 30, 350)]]")


def test_only_the_through_finder_sees_a_proud_stringer_and_the_shopping_list_has_it(tmp_path):
    assert PROUD != STOOL
    _, _, pcs, tol, _ = _built(tmp_path, PROUD)
    assert ("bottom stringer", "left side") not in fasteners.edge_joints(pcs, tol)
    assert joints.contacts(pcs, tol)[("bottom stringer", "left side")]["how"] == "through"
    assert fasteners.estimate(pcs, tol)["joints"] == 4


def test_a_piece_set_into_another_is_a_joint_but_wants_no_mortise(tmp_path):
    assert DADO != STOOL
    _, d, pcs, tol, mesh = _built(tmp_path, DADO)
    got = joints.contacts(pcs, tol)
    assert got[("left side", "shelf")]["how"] == "into" and got[("right side", "shelf")]["how"] == "into"
    (r,) = [x for x in joints.check(DADO, d, mesh) if x.id == "mortises"]
    assert "shelf" not in r.detail, r.detail


def test_a_hole_elsewhere_isn_t_the_mortise(tmp_path):
    assert ELSEWHERE != MORTISED
    _, d, pcs, tol, mesh = _built(tmp_path, ELSEWHERE)
    (r,) = [x for x in joints.check(ELSEWHERE, d, mesh) if x.id == "mortises"]
    assert r.status == "fail" and "the left side's outline has no hole where it goes" in r.detail, r.detail


def test_a_kind_it_doesn_t_know_is_said_with_a_fix_it_does(tmp_path):
    odd = STOOL.replace('"kind": "butt", "fix": ["glue", "screws"]}', '"kind": "weld", "fix": ["glue", "screws"]}')
    assert odd != STOOL
    _, d, _, _, mesh = _built(tmp_path, odd)
    (r,) = [x for x in joints.check(odd, d, mesh) if x.id == "joints"]
    assert r.status == "fail" and "the kind \"weld\", which isn't one of butt" in r.detail and "fix" not in r.detail, r.detail


def test_built_from_draws_the_list():
    from .test_carve_click import JS, _fn

    assert "${jointsHtml(r)}" in open(JS).read()


# --- #275 review -----------------------------------------------------------------------------------------------------------
def test_a_proud_through_tenon_reads_one_way_mortises_in_the_sides_only(tmp_path):
    """The stringer stands 1 in proud of each side: it's the tenon. The mortise goes in each side, never in the stringer."""
    _, d, pcs, tol, mesh = _built(tmp_path, PROUD)
    (r,) = [x for x in joints.check(PROUD, d, mesh) if x.id == "mortises"]
    assert r.status == "fail"
    assert r.detail.count("cut the mortise into") == 2, r.detail
    assert "cut the mortise into the left side's outline" in r.detail and "cut the mortise into the right side's outline" in r.detail
    assert "the stringer's outline" not in r.detail and "into the bottom stringer's outline" not in r.detail, r.detail


@pytest.mark.parametrize("written", [
    'JOINTS = [{"pieces": ["step", s], "kind": "bevel", "fix": ["glue"]} for s in ("left side", "right side")]',
    'JOINTS = []\nfor _s in ("left side", "right side"):\n    JOINTS.append({"pieces": ["step", _s], "kind": "bevel", "fix": ["glue"]})',
], ids=["a comprehension", "a loop's appends"])
def test_joints_that_aren_t_plain_data_fail_the_round_in_words(tmp_path, written):
    script = STOOL.replace(STOOL[STOOL.index("JOINTS = ["):STOOL.index("]\n\n\ndef _boxes")] + "]", written)
    assert script != STOOL and "JOINTS" in script
    _, d, _, _, mesh = _built(tmp_path, script)
    (r,) = [x for x in joints.check(script, d, mesh) if x.id == "joints"]
    assert r.status == "fail" and "JOINTS isn't plain data: write it as a list of dicts" in r.detail, r.detail


def test_annotated_joints_are_read(tmp_path):
    script = STOOL.replace("JOINTS = [", "JOINTS: list = [")
    assert script != STOOL
    assert [j["kind"] for j in joints.read(script)] == ["bevel", "butt"]


def test_a_said_joint_is_never_listed_as_unsaid_when_it_can_t_be_read(tmp_path):
    script = STOOL.replace(STOOL[STOOL.index("JOINTS = ["):STOOL.index("]\n\n\ndef _boxes")] + "]",
                           'JOINTS = [{"pieces": ["step", s], "kind": "bevel"} for s in ("left side", "right side")]')
    s, *_ = _built(tmp_path, script)
    got = joints.listed(s, "stool")
    assert got and all(j["assumed"] and j.get("unread") for j in got), got


def test_an_unlisted_set_in_contact_is_an_assumed_dado(tmp_path):
    s, *_ = _built(tmp_path, DADO)
    got = {tuple(j["pieces"]): j for j in joints.listed(s, "stool")}
    assert got[("left side", "shelf")]["kind"] == "dado" and got[("left side", "shelf")]["assumed"], got


def test_no_bare_tick_on_a_multi_piece_wood_part(tmp_path):
    """#275 review: a run made before slice A, an uncounted one, a Lighten step: each reads ✓ with "joints not checked"."""
    import json
    import os

    from caliper import answers, lighten, load_study, verdicts

    s, *_ = _built(tmp_path, LOADED)
    case = _case()
    old = {"id": "20261101-000000-old0", "part": "stool", "kind": "load", "version": 1, "created": 1.0, "min_safety": 2.0,
           "cut": True, "cases": [case], "safety": 5.0, "holds": True}
    d = os.path.join(load_study.runs_dir(s), old["id"])
    os.makedirs(d)
    json.dump(old, open(os.path.join(d, "run.json"), "w"))
    rec = load_study.load_run(s, old["id"])
    assert rec["wood_joints"] == "uncounted"
    v = verdicts.case(rec, case)
    assert v["joints"] is True and v["brace"] == {"joints_n": None, "wood": True}, v
    text = answers._case_line("stool", {**rec, "cases": []}, case, None, False, False)["text"]
    assert "Its joints aren't checked: the check takes its joints as solid wood." in text, text
    # a Lighten step, from the run it comes from
    st = {"index": 1, "holds": True, "safety": 5.0, "saved_lb": 1.0, "cases": [{"name": "c", "safety": 5.0, "governs": "fea"}]}
    step = verdicts.lighten_step(st, None, {"min_safety": 2.0, "wood_joints": "uncounted"})
    assert step["joints"] is True and "joints not checked" in step["short"], step
    # one piece of wood: nothing to say
    assert not joints.wooden("PARAMS = {}\\ndef construction(p, b=None):\\n    return [{'kind': 'sheet', 'material': 'plywood'}]")
    assert joints.wooden(LOADED)


def test_the_page_says_an_uncounted_part_s_joints():
    from .test_carve_click import _page, _run

    line = _run(_page(["jointsLine", "safetyNum"], consts=["esc"], extra="""
out = jointsLine({verdict: {joints: true, brace: {joints_n: null, wood: true}}}, {min_safety: 2});"""))
    assert "<b>Joints not checked:</b> the check takes its joints as solid wood." in " ".join(line.split()), line



def test_contacts_say_where_on_each_piece_with_one_reach(tmp_path):
    """#275: one finder for the joint list, the shopping list and Lighten's rim, so each piece's contact has a place."""
    import numpy as np

    _, _, pcs, tol, _ = _built(tmp_path, PROUD)
    c = joints.contacts(pcs, tol)[("bottom stringer", "left side")]
    on = np.asarray(c["on"]["left side"])
    assert len(on) and on[:, 0].min() >= 304.8 / 2 - 19.05 and on[:, 0].max() <= 304.8 / 2 + 19.05, on   # where it passes
    assert on[:, 1].min() >= 50.8 - 19.05 and on[:, 1].max() <= 50.8 + 76.2 + 19.05
    step = joints.contacts(pcs, tol)[("left side", "step")]["on"]["left side"]
    assert step and min(p[1] for p in step) > 457.2 - 25.0                          # the step meets the side at its top
    wide = joints.contacts(pcs, tol, reach=tol + 10.0)[("bottom stringer", "left side")]["on"]["left side"]
    assert len(wide) > len(on)                                                     # a wider reach takes in more of the face
