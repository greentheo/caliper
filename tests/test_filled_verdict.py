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
    assert held and all(ln["status"] == "warn" and ln["text"].startswith(UNTRUSTED) for ln in held), held   # leads
    assert held[0]["text"] == UNTRUSTED + " (holds Dad (200 lb), 2 times over, assumed)"
    assert not any(ln["text"].startswith("✓") for ln in held)
    # the number is still there, one click down, labelled as the filled solid's
    assert consistency.filled(store, "stool") and "filled in" in consistency.filled(store, "stool")
    text, ok = studies._headline("load", rec)
    assert ok is not True and text.startswith("not trusted: it ran on a filled-in shape"), text


def test_the_books_dont_print_a_holding_line_for_it(tmp_path, monkeypatch):
    from caliper import cutplan

    if cutplan.available() is not None:
        pytest.skip(cutplan.available())
    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    strength = release._strength(store, {"stool": store.design.part("stool").version})
    assert all(c["verdict"]["kind"] in ("untrusted", "fails") for c in strength["stool"])   # one verdict (CALI-112)
    made = release.make(store, pdf=False)
    root = os.path.join(release.releases_dir(store), made["id"])
    row = open(os.path.join(root, "index.html")).read().split("Will it hold?")[1].split("</table>")[0]
    assert "not trusted" in row and "x</td>" not in row, row
    import html

    book = html.unescape(open(os.path.join(root, "kids.html")).read())
    assert "It should hold" not in book and "times over" not in book
    # no stand-on-it steps at all: a grown-up checks it first (#96 rework, item 4)
    assert "stands on it first" not in book and "your turn" not in book and "Test it" not in book
    assert "Don't stand on it yet" in book and "a grown-up checks it first" in book


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


def test_studies_and_the_page_read_the_part_as_it_is_now(tmp_path, monkeypatch):
    """CALI-96 (#96 rework, items 2 and 6): Studies read the flag a run kept, so a run from before CALI-96 on a filled
    part read "holds"; the page's badges and callout had no word to go on. Both read the part as it is now."""
    import json

    store, rec = _checked(tmp_path, monkeypatch, FILLED)
    path = os.path.join(load_study.runs_dir(store), rec["id"], "run.json")
    old = {k: v for k, v in rec.items() if k != "filled"}                  # a run saved before the flag existed
    with open(path, "w") as f:
        json.dump(old, f)
    state = design_api.design_state(store)
    assert next(p for p in state["parts"] if p["id"] == "stool")["untrusted"]
    rows = [r for r in state["studies"]["runs"] if r["kind"] == "load"]
    assert rows and rows[0]["headline"].startswith("not trusted: it ran on a filled-in shape") and rows[0]["ok"] is not True
    text, ok = studies._headline("lighten", {"filled": True, "stations": [
        {"index": 0, "holds": True, "saved_lb": 0.0, "safety": 3.0}, {"index": 1, "holds": True, "saved_lb": 1.2, "safety": 2.5}]})
    assert text.startswith("not trusted, on a filled-in shape:") and ok is None
    # the hollow box isn't flagged
    hollow, _ = _checked(tmp_path / "h", monkeypatch, BOX_STOOL)
    assert not next(p for p in design_api.design_state(hollow)["parts"] if p["id"] == "stool")["untrusted"]


def test_the_studies_rows_and_the_book_say_not_trusted_in_their_own_words():
    """CALI-96 (#96 re-review): the Studies scorecard row read "1 pass · 0 fail" in green, the strength row "on a
    filled-in shape: holds — …", the release row "a check fails" when none did, and the book "1 unknown"."""
    text, ok = studies._headline("scorecard", {"summary": {"pass": 1, "fail": 0, "unknown": 1, "untrusted": 1}})
    assert text == "1 pass · 0 fail · 1 not trusted" and ok is False
    text, ok = studies._headline("load", {"filled": True, "holds": True, "safety": 3.1, "min_safety": 2,
                                          "cases": [{"name": "a foot", "safety": 3.1, "holds": True}]})
    assert text == "not trusted: it ran on a filled-in shape (the block read 3.1x)" and ok is None
    assert "holds" not in text
    rec = {"id": "001", "ready": False, "shopping_usd": 40,
           "card": {"summary": {"pass": 1, "fail": 0, "unknown": 1, "untrusted": 1}}}
    assert studies._headline("release", rec)[0] == "release 001 · not ready: a check isn't trusted yet · ~$40 to buy"
    rec["card"]["summary"].update({"fail": 1})
    assert "not ready: a check fails" in studies._headline("release", rec)[0]
    head = release._status({"summary": {"pass": 1, "fail": 0, "unknown": 1, "untrusted": 1}, "checks": [{}, {}]})
    assert "1 not trusted" in head and "unknown" not in head


# --- #96 and #100 together (the merge): a filled-in shape wins over "not resolved", and a ✗ stays a ✗ -----------
def _goal_state():
    return {"goals": {"checks": [{"id": "strength_dad", "label": "holds Dad (200 lb), 2 times over",
                                  "metric": "strength.safety", "op": ">=", "limit": 2.0, "source": "assumed"}]},
            "parts": [], "scorecards": []}


def test_on_the_design_card_a_filled_in_shape_wins_and_a_fail_stays_a_fail():
    both = {"strength.filled": "Not trusted yet: the strength check ran on a filled-in shape.",
            "strength.unresolved": "Not resolved yet: the check was too coarse to see its 4 mm walls."}
    (line,) = answers.held_to(_goal_state(), {**both, "strength.safety": 3.0})
    assert line["status"] == "warn" and line["text"].startswith("Not trusted yet"), line
    (line,) = answers.held_to(_goal_state(), {**both, "strength.safety": 1.2})
    assert line["status"] == "bad" and line["text"].startswith("✗ Holds Dad"), line
    assert line["text"].endswith("It ran on a filled-in shape, so the part as built is weaker still."), line


def test_on_the_studies_page_a_filled_in_fail_is_still_a_fail():
    held = {"filled": True, "holds": True, "safety": 3.1, "min_safety": 2,
            "cases": [{"name": "Dad", "safety": 3.1, "holds": True, "governs": "fea"}]}
    assert studies._headline("load", held)[1] is None
    failed = {**held, "holds": False, "safety": 1.2, "cases": [{"name": "Dad", "safety": 1.2, "holds": False,
                                                              "governs": "fea"}]}
    text, ok = studies._headline("load", failed)
    assert ok is False and text.startswith("doesn't hold") and "on a filled-in shape" in text
