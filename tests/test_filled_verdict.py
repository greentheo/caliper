"""CALI-96 (#78; rule 6) — a strength verdict on a filled-in solid isn't trusted: it reads warn, never ✓.

Found on the owner's step-stool-2: What is it? said the solid was filled in (61% of it in no piece), while Will it
work? read "✓ Holds kid + dad (250 lb), 2 times over: 2x" from a check that ran on that block."""

import os

import pytest

from caliper import answers, consistency, design_api, load_study, release, studies
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

#: The box stool with build() a solid block round its panels, as test_consistency builds it.
FILLED = BOX_STOOL.replace('''    out = None
    for lo, hi in _boxes(p, BUILD["t"]).values():
        b = cq.Workplane().box(*(b - a for a, b in zip(lo, hi)), centered=False).translate(lo)
        out = b if out is None else out.union(b)
    return out''', '''    return cq.Workplane().box(p["w"], p["d"], p["h"], centered=False)''')
#: What it's held to, as the conversation writes it (the sample stool's own check).
GOALS = """written_by: caliper
checks:
- id: strength_adult
  label: holds Dad (200 lb), 2 times over
  metric: strength.safety
  op: '>='
  limit: 2.0
  source: assumed
"""
UNTRUSTED = ('Not trusted yet: the strength check ran on a filled-in shape, not the stool as built. Fix its shape '
             'first (say "fix its shape to match its pieces").')


def _checked(tmp_path, monkeypatch, src):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", src, intent="a box step stool")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(GOALS)
    rec = load_study.study(store, "stool")
    return store, rec


def test_a_filled_part_s_strength_reads_warn_on_both_cards(tmp_path, monkeypatch):
    assert FILLED != BOX_STOOL
    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    assert rec["holds"]                                     # the solid block holds, of course: that's the trouble
    state = design_api.design_state(store)
    part = answers.answers(store, state, "stool")[1]
    strength = [ln for ln in part["lines"] if ln.get("study") == "load"]
    assert strength and all(ln["status"] == "warn" and ln["text"] == UNTRUSTED for ln in strength), strength
    assert not any(ln["status"] == "ok" for ln in strength)
    design = answers.answers(store, state, None)[1]
    held = [ln for ln in design["lines"] if ln.get("study") == "load"]
    assert held and all(ln["status"] == "warn" and UNTRUSTED in ln["text"] for ln in held), held
    assert not any(ln["text"].startswith("✓") for ln in held)
    # the number is still there, one click down, labelled as the filled solid's
    assert consistency.filled(store, "stool") and "filled in" in consistency.filled(store, "stool")
    text, ok = studies._headline("load", rec)
    assert ok is not True and text.startswith("on a filled-in shape:"), text


def test_the_books_dont_print_a_holding_line_for_it(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    strength = release._strength(store, {"stool": store.design.part("stool").version})
    assert all(c["filled"] for c in strength["stool"])
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    row = open(os.path.join(root, "index.html")).read().split("Will it hold?")[1].split("</table>")[0]
    assert "not trusted" in row and "x</td>" not in row, row
    book = open(os.path.join(root, "kids.html")).read()
    assert "It should hold" not in book and "times over" not in book
    assert "We haven&#x27;t checked it holds yet" in book or "We haven't checked it holds yet" in book


def test_the_same_box_built_hollow_still_reads_as_it_holds(tmp_path, monkeypatch):
    store, rec = _checked(tmp_path, monkeypatch, BOX_STOOL)
    assert consistency.filled(store, "stool") is None
    part = answers.answers(store, design_api.design_state(store), "stool")[1]
    strength = [ln for ln in part["lines"] if ln.get("study") == "load"]
    assert strength and strength[0]["text"].startswith("Holds ") and strength[0]["status"] in ("ok", "bad")


def test_a_check_that_raises_isnt_kept_and_never_reads_holding(tmp_path, monkeypatch):
    """CALI-96 (#96 rework, item 3): filled() cached None when its check raised: a part whose shape couldn't be
    checked read as trusted from then on. It fails closed now, for that render, and asks again next time."""
    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    consistency._FILLED.clear()
    real, calls = consistency.check, []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("the sandbox died")
        return real(*a, **k)

    monkeypatch.setattr(consistency, "check", flaky)
    why = consistency.filled(store, "stool")
    assert why and why.startswith("couldn't check its shape")
    part = answers.answers(store, design_api.design_state(store), "stool")[1]
    assert not any(ln["status"] == "ok" for ln in part["lines"] if ln.get("study") == "load")
    assert "filled in" in consistency.filled(store, "stool")             # asked again, and this time it can tell


def test_the_scorecard_doesnt_pass_it_and_the_package_isnt_ready_to_cut(tmp_path, monkeypatch):
    """CALI-96 (#96 rework, item 1): the scorecard scored the filled block's strength as a pass, so the build book
    said "ready to cut"."""
    from caliper import cutplan, scorecard

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    card = scorecard.compute(store)
    (check,) = [c for c in card["checks"] if c["id"] == "strength_adult"]
    assert check["status"] == "untrusted" and card["summary"]["untrusted"] == 1
    assert card["summary"]["pass"] == sum(c["status"] == "pass" for c in card["checks"])     # not counted as one
    made = release.make(store, pdf=False)
    assert made["ready"] is False
    root = os.path.join(release.releases_dir(store), made["id"])
    row = open(os.path.join(root, "index.html")).read().split("Scorecard, as released")[1].split("</table>")[0]
    assert "not trusted" in row
    make = answers.answers(store, design_api.design_state(store), None)[3]
    assert not any("ready to cut" in ln["text"] for ln in make["lines"]), make["lines"]
