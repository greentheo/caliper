"""CALI-107 (#107; rule 6) — a requested feature builds or the script says why not, and the reply never lets "the
checks pass" stand for "what you asked for happened".

On Theo's bar stool (v5) the designer clamped a fillet below what was asked, wrapped it in ``try/except: pass``,
returned the cone uncut when the openings came out small and on any error, and each reply said "✓ revised … Every
check on this part passes"."""

import pytest

from caliper import chat, fallbacks
from caliper.design import DesignStore

from .test_resolved import TUBE

pytest.importorskip("cadquery")

#: The bar stool's patterns, written afresh (Theo's design stays on his machine): a clamped fillet in a try that
#: passes, and mesh cut-outs skipped when small and on any error.
PATTERNS = '''import cadquery as cq

PARAMS = {"foot_fillet_r": 12.7, "foot_h": 14.0, "open_w": 20.0, "rows": 6}


def _add_foot_fillet(solid, p):
    r = p["foot_fillet_r"]
    if r <= 0:
        return solid                                       # not asked for: fine
    r = min(r, p["foot_h"] * 0.45)
    try:
        solid = solid.edges("<Z").fillet(r)
    except Exception:
        pass
    return solid


def _add_cutouts(solid, p):
    w = min(p["open_w"], 12.0)
    if w < 6.0:
        return solid
    try:
        return solid.cut(cq.Workplane().box(w, w, 50))
    except Exception:
        return solid


def build(params):
    p = {**PARAMS, **(params or {})}
    return _add_cutouts(_add_foot_fillet(cq.Workplane().box(80, 80, 40), p), p)
'''


def test_each_way_a_feature_was_silently_dropped_is_named_by_its_line():
    got = fallbacks.find(PATTERNS)
    lines = sorted(int(f.split(":")[0].split()[1]) for f in got)
    assert lines == [10, 13, 19, 20, 24], got
    assert any("min(foot_fillet_r, …)" in f for f in got)                  # the clamp, through a local copy
    assert any("an except that passes" in f for f in got)
    assert any("returns solid unchanged when w < 6.0" in f for f in got)
    assert any("an except that returns solid unchanged" in f for f in got)
    assert not any("line 8:" in f for f in got)                           # r <= 0: not asked for, not flagged


@pytest.mark.parametrize("ok", [
    'def build(params):\n    p = {**PARAMS, **(params or {})}\n    return cq.Workplane().box(min(p["w"], p["d"]), 1, 1)\n',
    'def build(params):\n    try:\n        import x\n    except ImportError:\n        pass\n    return 1\n',
    'def build(params):\n    s = cq.Workplane().box(1, 1, 1)\n    try:\n        s = s.fillet(1)\n'
    '    except Exception:\n        raise ValueError("the 1 mm fillet doesn\'t fit")\n    return s\n',
])
def test_what_isn_t_a_silent_fallback_isn_t_flagged(ok):
    """Two requested sizes compared, an import guarded, a failure re-raised with words."""
    assert fallbacks.find("PARAMS = {}\n" + ok) == []


def test_the_suite_s_parts_and_the_samples_are_clean():
    import glob
    import importlib
    import os

    import caliper

    root = os.path.dirname(caliper.__file__)
    for f in glob.glob(os.path.join(root, "samples", "*", "parts", "*", "part.py")):
        assert fallbacks.find(open(f).read()) == [], f
    for mod, name in (("test_consistency", "STOOL"), ("test_load_study", "BOX_STOOL"), ("test_mixed", "MIXED"),
                      ("test_printed_strength", "PRINTED"), ("test_resolved", "TUBE")):
        assert fallbacks.find(getattr(importlib.import_module(f"tests.{mod}"), name)) == [], name


def _store(tmp_path, src=TUBE):
    store = DesignStore.create("a tube", base=str(tmp_path / "designs"))
    store.write_part("tube", src, intent="a printed tube")
    return store


def test_a_revision_that_swallows_a_fillet_fails_the_round_naming_the_line(tmp_path):
    store = _store(tmp_path)
    swallowed = TUBE.replace('''    return cq.Workplane().circle(p["r"]).circle(p["r"] - p["wall"]).extrude(p["h"])''',
                             '''    tube = cq.Workplane().circle(p["r"]).circle(p["r"] - p["wall"]).extrude(p["h"])
    try:
        tube = tube.edges(">Z").fillet(p["wall"] * 3)
    except Exception:
        return tube
    return tube''')
    got = chat.refine_part(store, "tube", "round the top edge", author=lambda *a: swallowed, use_llm=False,
                           promote_feedback=False, max_rounds=1)
    assert not got.ok and got.reply.startswith("✗ revised")
    assert "an except that returns tube unchanged hides a feature that didn't build" in got.reply
    assert "line 12:" in got.reply and "Its shape didn't change" in got.reply, got.reply


def test_a_clamped_size_fails_the_round_too(tmp_path):
    store = _store(tmp_path)
    clamped = TUBE.replace('"wall": 4.0', '"wall": 8.0').replace(
        'circle(p["r"] - p["wall"])', 'circle(p["r"] - min(p["wall"], 5.0))')
    got = chat.refine_part(store, "tube", "make the wall 8 mm", author=lambda *a: clamped, use_llm=False,
                           promote_feedback=False, max_rounds=1)
    assert not got.ok and "min(wall, …) holds a requested size under a limit without saying so" in got.reply


def test_the_reply_says_what_was_asked_what_changed_and_what_nothing_measures(tmp_path):
    store = _store(tmp_path)
    thicker = TUBE.replace('"wall": 4.0', '"wall": 6.0')
    got = chat.refine_part(store, "tube", "make the wall 6 mm", author=lambda *a: thicker, use_llm=False,
                           promote_feedback=False)
    assert got.ok
    lines = got.reply.splitlines()
    assert lines[1] == "Asked for: make the wall 6 mm"
    assert lines[2] == "Changed: wall 4 mm → 6 mm"
    assert lines[3].startswith("Measured: its volume went from ") and "cm³" in lines[3]
    assert lines[4].startswith("Not measured: whether that's what you meant.")
    assert "Every check on this part passes" not in got.reply and "The part's own checks pass." in got.reply


def test_a_request_that_changed_nothing_says_so(tmp_path):
    store = _store(tmp_path)
    same = TUBE.replace('BUILD = {', '# the fillet is on the inside corner now\nBUILD = {')
    got = chat.refine_part(store, "tube", "round the inside corner", author=lambda *a: same, use_llm=False,
                           promote_feedback=False)
    assert "Changed: no number in its PARAMS; the change is in how it's built" in got.reply
    assert "Its shape didn't change (the same volume" in got.reply and "may not have happened" in got.reply


def test_in_inches_a_size_is_said_in_both(tmp_path):
    store = _store(tmp_path)
    store.design.display_units = "in"
    store.save()
    fillet = TUBE.replace('PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0}', 'PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0, "fillet_r": 6.35}')
    store.write_part("tube", fillet, intent="a printed tube")
    bigger = fillet.replace('"fillet_r": 6.35', '"fillet_r": 12.7')
    got = chat.refine_part(store, "tube", "make the fillet 1/2 in", author=lambda *a: bigger, use_llm=False,
                           promote_feedback=False)
    assert "Changed: fillet_r 6.35 mm (1/4 in) → 12.7 mm (1/2 in)" in got.reply, got.reply
