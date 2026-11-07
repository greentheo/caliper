"""CALI-126 (#150) — a sheet's grain makes its verdict greener only when the person states it, and the maker is told.

The test top (#106's beam fixture): a 1/2 in plywood top 900 wide across a 300 mm gap, on two sides. Plywood is half as
strong across its face grain, so the beam check reads it both ways and, the grain's way unknown, takes the worse. A
``"grain"`` the designer writes in ``construction()`` is only assumed: advice, never the verdict. One the person says
(in the chat, or keeping the advice) is the verdict's at the next check, and goes on the cut list and in the book.
Stubbed: no FEA, no Claude."""

import pytest

from caliper import answers, chat, cutplan, design_api, grain, load_study, release
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


#: the one phrase for this cut, everywhere it's said (#151 review: "along the gap" and "across the gap" read both ways)
PHRASE = "face grain running front to back, from one support to the other"


def test_an_assumed_grain_never_moves_the_verdict(tmp_path):
    """#149's first cut let the designer's own ``grain`` make the number greener; nobody told the maker."""
    unknown, assumed = _beam(_store(tmp_path / "a")), _beam(_store(tmp_path / "b", ASSUMED))
    assert assumed["grain"] is None and assumed["grain_assumed"] == "along"
    assert assumed["safety_across"] == unknown["safety_across"] < assumed["safety"]        # the worse grain's
    assert assumed["deflection_mm"] == unknown["deflection_mm"]
    assert f"Cut with its {PHRASE} and it's about" in assumed["why"]                        # the advice, not a claim
    assert assumed["span_axis"] == "y" and assumed["advice_phrase"] == PHRASE               # it spans front to back


def test_a_stated_grain_moves_it_and_is_on_the_cut_list(tmp_path):
    store = _store(tmp_path, ASSUMED)
    before = _beam(store)
    entry = grain.state(store, "bench", "top", "along", said="cut it along the span")
    assert entry == {"grain": "along", "runs": "", "said": "cut it along the span"}        # no check yet: no direction
    after = _beam(store)
    assert after["grain"] == "along" and after["safety_across"] == before["safety"] > before["safety_across"]
    assert after["deflection_mm"] == after["deflection_along_mm"]
    assert f"With its {PHRASE}, as you said" in after["why"] and after["grain_phrase"] == PHRASE
    # the maker is told: the part's state, the cut plan's lines
    (p,) = design_api.design_state(store)["parts"]
    assert p["grain"]["top"]["grain"] == "along"
    assert p["grain_notes"] == ["Cut the top with its face grain running from one support to the other."]
    assert store.history("bench")[-1]["kind"] == "grain"


def test_a_stated_grain_after_a_check_is_said_in_the_part_s_own_directions(tmp_path):
    store = _store(tmp_path)
    _run_with(store, _beam(store))
    entry = grain.state(store, "bench", "top", "across")
    assert entry["runs"] == "side to side"                     # across a front-to-back gap: side to side
    assert grain.notes(store, "bench") == ["Cut the top with its face grain running side to side, parallel to the "
                                           "supports."]


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
    assert advice["text"] == (f"Cut the top with its {PHRASE} and it's about {answers._times(pl['safety'])}, not "
                              f"{answers._times(pl['safety_across'])}: keep that under Will it hold? and it goes on "
                              f"the cut list.")
    assert advice["status"] == "info" and advice["study"] == "load"
    grain.state(store, "bench", "top", "along")
    work = next(c for c in answers.part(store, design_api.design_state(store), "bench") if c["key"] == "work")
    (again,) = [ln for ln in work["lines"] if "face grain" in ln["text"]]
    assert again["text"] == f"You said: cut the top with its {PHRASE}. Check it holds again to use it."
    assert again["status"] == "warn"


def test_advice_from_an_unsettled_case_quotes_no_number(tmp_path):
    """#151's survivor: the advice quoted any beam's number. Here the FEA governs a case too coarse to see its walls:
    no verdict, so no "about N times over" beside it."""
    store = _store(tmp_path)
    pl = _beam(store)
    rec = _run_with(store, pl)
    rec["cases"][0].update({"governs": "fea", "safety": 3.0, "holds": True})
    rec.update({"thinnest_mm": 1.0, "spacing_mm": 3.0, "across": 0.33})
    import json
    import os

    with open(os.path.join(load_study.runs_dir(store), rec["id"], "run.json"), "w") as f:
        json.dump(rec, f)
    work = next(c for c in answers.part(store, design_api.design_state(store), "bench") if c["key"] == "work")
    assert not [ln for ln in work["lines"] if "face grain" in ln["text"]], work["lines"]


def test_one_phrase_for_the_cut_everywhere_it_s_said(tmp_path):
    """#151 review, must-fix 1: the Beam check said "across the gap" and the cut list "along the gap" for the same
    cut. Every place says the one phrase, led by the part's own direction; none says "the gap"."""
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _store(tmp_path)
    pl = _beam(store)
    _run_with(store, pl)
    said = {"beam advice": pl["why"], "page advice": pl["advice_phrase"]}
    work = next(c for c in answers.part(store, design_api.design_state(store), "bench") if c["key"] == "work")
    said["card advice"] = next(ln["text"] for ln in work["lines"] if "face grain" in ln["text"])
    import os

    os.environ["CALIPER_DESIGNS"] = os.path.dirname(store.root)
    got = TestClient(create_app()).post(f"/api/designs/{os.path.basename(store.root)}/parts/bench/grain",
                                        json={"piece": "top", "grain": "along"})
    assert got.status_code == 200, got.text
    said["keep reply"] = got.json()["said"]
    store = DesignStore.load(store.root)
    said["cut list"] = grain.notes(store, "bench")[0]
    (p,) = design_api.design_state(store)["parts"]
    said["page's you said"] = p["grain"]["top"]["line"]
    said["beam after"] = _beam(store)["why"]
    said["chat"] = chat.turn(store, "cut the top with the grain front to back", use_llm=False).reply
    for where, text in said.items():
        assert PHRASE in text, (where, text)
        assert "along the gap" not in text and "across the gap" not in text, (where, text)


def test_the_chat_keeps_a_grain_the_person_states(tmp_path):
    store = _store(tmp_path)
    _run_with(store, _beam(store))

    def no_claude(*a, **k):
        raise AssertionError("a stated grain needs no Claude call")

    got = chat.turn(store, "cut the top with the grain front to back", use_llm=False, classifier=no_claude)
    assert got.action == "grain" and got.ok and got.part == "bench"
    assert got.reply == (f"Kept: cut the top with its {PHRASE}. It's on the cut list and in the build book; check it "
                         f"holds again and the Beam check uses it.")
    assert grain.stated(store, "bench")["top"]["grain"] == "along"
    side = chat.turn(store, "the top's grain should run side to side", use_llm=False, classifier=no_claude)
    assert side.ok and grain.stated(store, "bench")["top"]["grain"] == "across"
    lost = chat.turn(store, "cut the lid with the grain front to back", use_llm=False, classifier=no_claude)
    assert lost.action == "grain" and not lost.ok and lost.reply.startswith("I couldn't keep that grain: which sheet?")


def test_a_grain_with_no_way_is_asked_and_a_question_isn_t_kept(tmp_path):
    """#151 review: "cut the top with the grain" fell through to the designer, where an assumed grain comes from."""
    store = _store(tmp_path)
    _run_with(store, _beam(store))

    def no_claude(*a, **k):
        raise AssertionError("asked here, never sent on")

    got = chat.turn(store, "cut the top with the grain", use_llm=False, classifier=no_claude)
    assert got.action == "grain" and not got.ok
    assert got.reply == "I couldn't keep that grain: which way: front to back, or side to side?."
    assert grain.stated(store, "bench") == {}
    # a question about it is the chat's to answer: nothing kept
    assert grain.from_chat(store, "should the top's grain run front to back?") is None
    assert grain.stated(store, "bench") == {}


def test_a_sheet_named_in_two_parts_asks_which(tmp_path):
    store = _store(tmp_path)
    store.write_part("shelf", TOP, intent="a shelf")              # its sheet is a "top" too
    got = grain.from_chat(store, "cut the top with the grain front to back")
    assert got == {"why": "that names the top of the bench, the top of the shelf: say which one"}
    assert store.design.grain == {}
    # scoped to one part, it's that part's (the shelf has no check yet: "along the span", not "front to back")
    assert grain.from_chat(store, "cut the top with the grain along the span", scope="shelf")["part"] == "shelf"


def test_the_page_says_which_grain_the_beam_check_used():
    from .test_carve_click import _page, _run

    out = _run(_page(["beamGrain", "grainKeep"], consts=["esc"], extra=(
        "function sx(v) { return v + 'x'; }\n"
        f"const pl = {{piece: 'top', safety: 3.1, safety_across: 1.6, grain: null, advice_phrase: '{PHRASE}'}};\n"
        f"const said = {{top: {{grain: 'along', line: 'Cut the top with its {PHRASE}.'}}}};\n"
        "out = [beamGrain(pl), beamGrain({...pl, grain: 'along', grain_phrase: pl.advice_phrase}),\n"
        "       grainKeep({grain: {}}, pl), grainKeep({grain: said}, pl), grainKeep({grain: said}, {...pl, grain: 'along'})];")))
    assert out[0] == "the grain unknown: the weaker way"
    assert out[1] == f"with its {PHRASE}, as you said"
    assert 'data-grain="top"' in out[2] and f"Keep: cut it with its {PHRASE} (3.1x)" in out[2]
    assert out[3] == f" · <span class=\"muted\">you said: Cut the top with its {PHRASE}. Check it holds again to use it.</span>"
    assert out[4] == ""
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "with the grain unknown · sags" not in src                    # never a hard-coded "unknown"


# --- #151 review, must-fix 2: the layout follows the grain, or says it doesn't ---------------------------------------

needs_unfolder = pytest.mark.skipif(cutplan.available() is not None, reason=f"no cut plans here: {cutplan.available()}")


def _top_on_the_sheet(store, rec):
    """The top's width along the sheet's length and its height across it, from the drawn sheet."""
    import os
    import re

    g = next(g for g in rec["sheets"] if "top" in g["panels"])
    svg = open(os.path.join(cutplan.runs_dir(store), rec["id"], g["key"], "sheets", "sheet-01.svg")).read()
    paths = [[tuple(map(float, q.split())) for q in re.findall(r"[ML]([\d.]+ [\d.]+)", d)]
             for d in re.findall(r'<path d="(M[^"]*Z)"', svg)]
    top = [p for p in paths if p][1]                              # the sheet's own outline first, then the piece
    us, vs = [q[0] for q in top], [q[1] for q in top]
    return round(max(us) - min(us)), round(max(vs) - min(vs))


@needs_unfolder
def test_the_cut_plan_lays_a_stated_grain_along_the_sheet(tmp_path):
    """The top (900 side to side, 300 front to back) lies long way along the sheet as it unfolds. With its grain said
    front to back, it's turned so that runs along the sheet's length, as the sheet's own grain does, and said so."""
    store = _store(tmp_path)
    _run_with(store, _beam(store))
    assert _top_on_the_sheet(store, cutplan.run(store, "bench")) == (900, 300)
    grain.state(store, "bench", "top", "along")
    rec = cutplan.run(store, "bench")
    assert _top_on_the_sheet(store, rec) == (300, 900)
    assert rec["grain"] == [{"piece": "top", "line": f"Cut the top with its {PHRASE}.", "follows": True, "why": ""}]
    assert any("turning pieces end for end only" in n for n in rec["notes"])
    assert cutplan.cutlist_text(rec).splitlines()[2] == f"Cut the top with its {PHRASE}."


def test_a_layout_that_can_t_follow_the_grain_says_so_per_piece(tmp_path, monkeypatch):
    """Where the nester can't lay it with its grain along the sheet (or its way isn't known yet), the cut plan says so
    for that piece, beside the line: never the line alone over a layout that turned it."""
    store = _store(tmp_path)
    _run_with(store, _beam(store))
    grain.state(store, "bench", "top", "along")
    fake = {"sheets": 1, "pieces": 1, "utilisation": 0.1, "worst_edge_error": 0, "missing": [], "files": [],
            "joints": [], "piece_list": [], "scored": 0,
            "grain": [{"label": "P1", "name": "top", "fits": False,
                       "why": "it doesn't fit the sheet with its grain along the sheet's length"}]}
    monkeypatch.setattr(cutplan, "available", lambda: None)
    monkeypatch.setattr(cutplan, "_unfold", lambda *a, **k: dict(fake) if k.get("grain") else {**fake, "grain": []})
    rec = cutplan.run(store, "bench")
    (g,) = rec["grain"]
    assert not g["follows"] and g["why"] == "it doesn't fit the sheet with its grain along the sheet's length"
    assert "The layout doesn't follow it (it doesn't fit" in cutplan.cutlist_text(rec)
    from .test_carve_click import _page, _run

    import json

    out = _run(_page(["cutGrain"], consts=["esc"], extra=(
        f"const p = {{version: 1, grain: {{top: {{line: 'Cut the top with its {PHRASE}.'}}}}}};\n"
        f"out = [cutGrain(p, {json.dumps({**rec, 'version': 1})}), cutGrain(p, null), "
        f"cutGrain(p, {{version: 1, grain: []}})];")))
    assert "The layout below doesn&#39;t" in out[0] or "The layout below doesn't" in out[0]
    assert "lay it out by hand" in out[0]
    assert out[1].endswith(f"Cut the top with its {PHRASE}.</div>")
    assert "Make the cut plan again so its layout follows it." in out[2]


@needs_unfolder
def test_the_build_book_s_cut_lists_say_the_grain_end_to_end(tmp_path):
    """#151's survivor: nothing checked the book. A release of a part whose top's grain is said carries the line
    under Cut lists."""
    import os

    store = _store(tmp_path)
    _run_with(store, _beam(store))
    grain.state(store, "bench", "top", "along")
    rec = release.make(store, pdf=False)
    html = open(os.path.join(release.releases_dir(store), rec["id"], "index.html")).read()
    cut = html[html.index("<h2 class='page'>Cut lists</h2>"):]
    assert f"<b>bench:</b> Cut the top with its {PHRASE}." in cut
    assert "doesn't follow it" not in cut
