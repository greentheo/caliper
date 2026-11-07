"""CALI-126 (#150) — a sheet's grain makes its verdict greener only when the person states it, and the maker is told.

The test top (#106's beam fixture): a 1/2 in plywood top 900 wide across a 300 mm gap, on two sides. Plywood is half as
strong across its face grain, so the beam check reads it both ways and, the grain's way unknown, takes the worse. A
``"grain"`` the designer writes in ``construction()`` is only assumed: advice, never the verdict. One the person says
(in the chat, or keeping the advice) is the verdict's at the next check, and goes on the cut list and in the book.
Stubbed: no FEA, no Claude."""

import pytest

from caliper import answers, chat, design_api, grain, load_study, release
from caliper.design import DesignStore

from .test_beam_width import TOP

pytest.importorskip("cadquery")

#: the same top, its designer having written that the grain runs along the span (the greener way)
ASSUMED = TOP.replace('"thickness": T,\n             "outline": [(0, 0, H)', '"thickness": T, "grain": "along",\n'
                                                                           '             "outline": [(0, 0, H)')


def _store(tmp_path, src=TOP):
    store = DesignStore.create("a bench", base=str(tmp_path / "designs"))
    store.write_part("bench", src, intent="a bench")
    return store


def _beam(store):
    """The beam check on the top, through the strength check's own set-up (its pieces, the person's grain)."""
    ctx = load_study.prepare(store, "bench")
    (load,) = ctx["loads"]
    got = load_study.plate_check(ctx["pieces"], load, ctx.get("plate_mat") or ctx["mat"], ctx["tol"],
                                 under=ctx.get("under"))
    assert got and got["as"] == "beam" and got["piece"] == "top"
    return got


def _run_with(store, pl):
    """A strength run on this version whose one case the beam governs, as load_study writes one (no FEA)."""
    import json
    import os

    rid = "20261107-000000-bench"
    os.makedirs(os.path.join(load_study.runs_dir(store), rid), exist_ok=True)
    rec = {"id": rid, "part": "bench", "version": store.design.part("bench").version, "created": 1.0,
           "min_safety": 2, "safety": pl["safety_across"], "spacing_mm": 3.0, "thinnest_mm": 12.7,
           "cases": [{"name": "a foot", "lb": 200, "factor": 2.0, "safety": pl["safety_across"], "governs": "plate",
                      "holds": pl["safety_across"] >= 2, "plate": pl,
                      "fea": {"supported": True, "safety": 50.0, "deflection_mm": 0.1}}]}
    with open(os.path.join(load_study.runs_dir(store), rid, "run.json"), "w") as f:
        json.dump(rec, f)
    return rec


def test_an_assumed_grain_never_moves_the_verdict(tmp_path):
    """#149's first cut let the designer's own ``grain`` make the number greener; nobody told the maker."""
    unknown, assumed = _beam(_store(tmp_path / "a")), _beam(_store(tmp_path / "b", ASSUMED))
    assert assumed["grain"] is None and assumed["grain_assumed"] == "along"
    assert assumed["safety_across"] == unknown["safety_across"] < assumed["safety"]        # the worse grain's
    assert assumed["deflection_mm"] == unknown["deflection_mm"]
    assert "Cut with its face grain running across the gap" in assumed["why"]                 # the advice, not a claim
    assert assumed["span_axis"] == "y"                                                       # the gap runs front to back


def test_a_stated_grain_moves_it_and_is_on_the_cut_list(tmp_path):
    store = _store(tmp_path, ASSUMED)
    before = _beam(store)
    entry = grain.state(store, "bench", "top", "along", said="cut it along the span")
    assert entry == {"grain": "along", "runs": "", "said": "cut it along the span"}        # no check yet: no direction
    after = _beam(store)
    assert after["grain"] == "along" and after["safety_across"] == before["safety"] > before["safety_across"]
    assert after["deflection_mm"] == after["deflection_along_mm"]
    assert "With its face grain along the gap, as you said" in after["why"]
    # the maker is told: the part's state, the cut plan's lines, the build book's cut list
    (p,) = design_api.design_state(store)["parts"]
    assert p["grain"]["top"]["grain"] == "along"
    assert p["grain_notes"] == ["Cut the top with its face grain along the gap it spans."]
    assert store.history("bench")[-1]["kind"] == "grain"
    book = release.book({"id": "r1", "created": 0, "design": "a bench", "versions": {"bench": 1},
                         "grain": {"bench": p["grain_notes"]}},
                        {"summary": {"pass": 0, "fail": 0, "unknown": 1}, "checks": [], "metrics": {}},
                        {"usd": 0, "groups": [], "basis": ""}, {}, [], [])
    assert "<b>bench:</b> Cut the top with its face grain along the gap it spans." in book


def test_a_stated_grain_after_a_check_is_said_in_the_part_s_own_directions(tmp_path):
    store = _store(tmp_path)
    _run_with(store, _beam(store))
    entry = grain.state(store, "bench", "top", "across")
    assert entry["runs"] == "side to side"                     # across a front-to-back gap: side to side
    assert grain.notes(store, "bench") == ["Cut the top with its face grain running side to side (across the gap it "
                                           "spans)."]


def test_a_grain_is_along_or_across_and_on_a_sheet_the_part_has(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="^a sheet's grain is along or across the gap it spans, not 'sideways'$"):
        grain.state(store, "bench", "top", "sideways")
    with pytest.raises(ValueError, match=r"^the bench has no sheet 'lid' \(its sheets: top, front, back\)$"):
        grain.state(store, "bench", "lid", "along")
    assert store.design.grain == {}


def test_the_card_gives_the_advice_until_it_s_said_then_check_again(tmp_path):
    store = _store(tmp_path, ASSUMED)
    pl = _beam(store)
    _run_with(store, pl)
    work = next(c for c in answers.part(store, design_api.design_state(store), "bench") if c["key"] == "work")
    (advice,) = [ln for ln in work["lines"] if "face grain" in ln["text"]]
    assert advice["text"] == (f"Cut the top with its face grain running front to back and it's about "
                              f"{answers._times(pl['safety'])}, not {answers._times(pl['safety_across'])}: keep that "
                              f"under Will it hold? and it goes on the cut list.")
    assert advice["status"] == "info" and advice["study"] == "load"
    grain.state(store, "bench", "top", "along")
    work = next(c for c in answers.part(store, design_api.design_state(store), "bench") if c["key"] == "work")
    (again,) = [ln for ln in work["lines"] if "face grain" in ln["text"]]
    assert again["text"] == ("You said: cut the top with its face grain running front to back (along the gap it "
                             "spans). Check it holds again to use it.") and again["status"] == "warn"
    # the run's own number never moved: it predates what was said
    assert next(c for c in work["lines"] if c.get("study") == "load" and "a foot" in c["text"].lower())


def test_the_chat_keeps_a_grain_the_person_states(tmp_path):
    store = _store(tmp_path)
    _run_with(store, _beam(store))

    def no_claude(*a, **k):
        raise AssertionError("a stated grain needs no Claude call")

    got = chat.turn(store, "cut the top with the grain front to back", use_llm=False, classifier=no_claude)
    assert got.action == "grain" and got.ok and got.part == "bench"
    assert got.reply == ("Kept: cut the top with its face grain running front to back (along the gap it spans). It's on "
                         "the cut list and in the build book; check it holds again and the Beam check uses it.")
    assert grain.stated(store, "bench")["top"]["grain"] == "along"
    side = chat.turn(store, "the top's grain should run side to side", use_llm=False, classifier=no_claude)
    assert side.ok and grain.stated(store, "bench")["top"]["grain"] == "across"
    lost = chat.turn(store, "cut the lid with the grain front to back", use_llm=False, classifier=no_claude)
    assert lost.action == "grain" and not lost.ok and lost.reply.startswith("I couldn't keep that grain: which sheet?")


def test_the_page_says_which_grain_the_beam_check_used():
    from .test_carve_click import _page, _run

    out = _run(_page(["beamGrain", "grainKeep"], consts=["esc"], extra=(
        "function sx(v) { return v + 'x'; }\n"
        "const pl = {piece: 'top', safety: 3.1, safety_across: 1.6, grain: null};\n"
        "out = [beamGrain(pl), beamGrain({...pl, grain: 'along'}), grainKeep({grain: {}}, pl),\n"
        "       grainKeep({grain: {top: {grain: 'along'}}}, pl), grainKeep({grain: {top: {grain: 'along'}}}, {...pl, grain: 'along'})];")))
    assert out[0] == "the grain unknown: the weaker way"
    assert out[1] == "with the grain along the span, as you said"
    assert 'data-grain="top"' in out[2] and "Keep: cut it with the grain along the span (3.1x)" in out[2]
    assert out[3] == " · <span class=\"muted\">you said along the span: check it holds again to use it</span>"
    assert out[4] == ""
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "with the grain unknown · sags" not in src                    # never a hard-coded "unknown"
