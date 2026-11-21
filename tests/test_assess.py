"""CALI-160 (#238) slice B — Review it: Claude reads every part against the request, on the person's press.

Each reading names its parts, says what's wrong and proposes the change; it's never a measurement (rule 6): badged
Claude's reading under Things to fix, done (never fixed) after Fix these, and an empty one says it's a reading, not a check.
Saved with the part versions it read, stale when they move. Claude is an injected stub in every test: no live call."""

import json
import os

import pytest

from caliper import assess, chat, design_api, fixes, fixing, llm, review
from caliper.design import DesignStore

pytest.importorskip("cadquery")

SIDE = ("def build(params):\n"
        "    import cadquery as cq\n"
        "    return cq.Workplane('XY').box(19, 300, 400, centered=False)\n")
STEP = ("def build(params):\n"
        "    import cadquery as cq\n"
        "    return cq.Workplane('XY').box(400, 300, 19, centered=False).translate((0, 0, 400))\n")
FIT = {"kind": "fit", "parts": ["side", "step"], "measured": True,
       "said": "the step has 19.1 mm of play in side's pocket", "fix": "Size side's pocket to the step: 0.2 mm a side."}


class Claude:
    """A stand-in that answers with fixed readings (or text), one reply per call, and records what it was shown."""

    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []
        self.messages = self

    def create(self, **kw):
        self.seen.append(kw)
        got = self.replies.pop(0)
        text = got if isinstance(got, str) else json.dumps({"readings": got})
        return type("M", (), {"content": [type("B", (), {"type": "text", "text": text})()], "stop_reason": "end_turn"})()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("A step stool 16 in tall that holds 200 lb", base=str(tmp_path / "designs"))
    s.write_part("side", SIDE, intent="a plywood side")
    s.write_part("step", STEP, intent="the step, on the side")
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [FIT], "checks": 3})
    return s


def _rows(store, pid):
    return fixes.listed(store, design_api.design_state(store), pid)["rows"]


def test_the_reading_reads_the_request_the_parts_and_what_s_measured_and_is_kept_with_their_versions(store):
    claude = Claude([{"parts": ["step"], "said": "the step is 19 mm ply over a 400 mm span for 200 lb",
                      "fix": "Make the step 25 mm, or add a rail under it."}])
    got = assess.run(store, client=claude)
    shown = claude.seen[0]["messages"][0]["content"]
    assert "A step stool 16 in tall that holds 200 lb" in shown
    assert "### side (v1): a plywood side" in shown and "box(19, 300, 400" in shown
    assert "measured size: 19.0 x 300.0 x 400.0 mm" in shown, shown
    assert "ALREADY MEASURED WRONG" in shown and "the step has 19.1 mm of play in side's pocket" in shown
    assert got["ok"] and got["n"] == 1 and got["versions"] == {"side": 1, "step": 1}
    (r,) = got["readings"]
    assert r == {"parts": ["step"], "said": "the step is 19 mm ply over a 400 mm span for 200 lb",
                 "fix": "Make the step 25 mm, or add a rail under it.", "id": "r1"}
    assert got["said"].startswith("Claude's reading of 2 parts (1 thing; read, not measured):")
    assert assess.latest(store)["readings"] == got["readings"]
    assert os.path.exists(os.path.join(store.root, "reviews", "assess-1.json"))
    assert llm.JOBS["assess"].model == llm.DEFAULT_MODEL and llm.JOBS["assess"].effort == "high"


def test_a_point_naming_no_part_or_saying_the_same_measured_finding_is_set_aside_and_said(store):
    claude = Claude([
        {"parts": ["rail"], "said": "the rail is missing", "fix": "Add one."},                       # no such part
        {"parts": ["side", "step"], "said": "the step is loose in the side's pocket", "fix": "Size the pocket.",
         "same_as": "m1"},                                                                           # Claude: it's m1
        {"parts": ["side", "step"], "said": "the step's screws miss the side", "fix": "Move them 10 mm in."},
        {"parts": ["side"], "said": "", "fix": "x"},                                                   # says nothing
    ])
    got = assess.run(store, client=claude)
    assert [r["said"] for r in got["readings"]] == ["the step's screws miss the side"]
    assert (got["dropped"], got["repeats"]) == (2, 1)
    assert [(a["why"], a["said"]) for a in got["set_aside"]] == [
        ("named no part here", "the rail is missing"), ("repeated a measured finding", "the step is loose in the side's pocket"),
        ("said nothing to change", "")]
    assert got["said"].endswith("3 of Claude's 4 points were left out: 1 named no part here, 1 repeated a measured "
                                "finding, 1 said nothing to change."), got["said"]
    assert "found nothing more" not in got["said"]


def test_a_reply_that_isn_t_readings_is_said_and_nothing_is_kept(store):
    got = assess.run(store, client=Claude("I think it looks fine overall."))
    assert not got["ok"] and got["said"] == "No reading: the reading didn't come back in a form I can use."
    assert assess.latest(store) is None and assess.count(store) == 0


def test_an_empty_reading_is_a_reading_not_a_check(store):
    got = assess.run(store, client=Claude([]))
    assert got["said"] == "Claude read 2 parts and found nothing more. That's a reading, not a check: look at it."
    assert "right" not in got["said"] and "✓" not in got["said"]


def test_a_reading_is_a_row_badged_claude_s_and_says_when_its_part_has_moved_on(store):
    assert not [r for r in _rows(store, "step") if r["id"].startswith(fixes.READING)]     # nothing read: no row, no call
    assess.run(store, client=Claude([{"parts": ["step", "side"], "said": "the step's screws miss the side",
                                      "fix": "Move them 10 mm in."}]))
    (row,) = [r for r in _rows(store, "step") if r["id"].startswith(fixes.READING)]
    assert row["id"] == "reading:1:r1" and row["problem"] == "The step's screws miss the side"
    assert row["measured"] is False and row["badge"] == "Claude's reading" and not row["stale"]
    assert row["choices"][0]["fix"] == "Move them 10 mm in" and row["choices"][0]["kind"] == fixes.DESIGNER
    assert [r["id"] for r in _rows(store, "side") if r["id"].startswith(fixes.READING)] == ["reading:1:r1"]
    store.write_part("step", STEP + "\n# moved\n", intent="the step, on the side")
    (row,) = [r for r in _rows(store, "step") if r["id"].startswith(fixes.READING)]
    assert row["badge"] == "Claude's reading · read on v1; it's changed since" and row["stale"]
    assert assess.stale(store, assess.latest(store)) == {"step": 1}


def test_fix_these_on_a_reading_says_it_done_never_fixed(store, monkeypatch):
    from .test_fix_these import Designer

    assess.run(store, client=Claude([{"parts": ["step"], "said": "the step overhangs the side by 381 mm",
                                      "fix": "Center the step on the side."}]))
    designer = Designer()
    monkeypatch.setattr(chat, "refine_part", designer)
    got = fixing.apply(store, "step", [{"id": "reading:1:r1", "choice": 0}], check=False)
    assert "Center the step on the side" in designer.calls[0]
    (res,) = got["results"]
    assert res["status"] == "done, not measured" and res["status"] != "fixed"
    assert res["why"] == "Claude's reading: nothing measures it. Review again to have it read"
    left = Designer(change=False)
    monkeypatch.setattr(chat, "refine_part", left)
    (res,) = fixing.apply(store, "step", [{"id": "reading:1:r1", "choice": 0}], check=False)["results"]
    assert res["status"] == "not done"                           # the designer left it: never "done"


def test_the_offer_says_its_cost_again_after_a_reading_and_the_count_from_the_fourth(store):
    o = assess.offer(store)
    assert o == {"label": "Review it", "cost": "one Claude call, about 30–60 s", "note": "", "stale": {}, "unread": [],
                 "count": 0}
    for _ in range(3):
        assess.run(store, client=Claude([]))
    o = assess.offer(store)
    assert o["label"] == "Review again" and o["count"] == 3 and o["note"] == "4th reading on this design"
    store.write_part("side", SIDE + "\n# thicker\n", intent="a plywood side")
    assert assess.offer(store)["stale"] == {"side": 1}


def test_rounds_end_in_nothing_measured_and_nothing_more_read(store, monkeypatch):
    """Slice D's done-when, stubbed: the measured list empties as the parts change, and a reading after it finds nothing
    more, in two Fix-these rounds."""
    from .test_fix_these import Designer

    monkeypatch.setattr(review, "findings", lambda store, report=None: {
        "findings": [FIT] if store.design.part("side").version < 2 else [], "checks": 3})
    claude = Claude([{"parts": ["step"], "said": "the step's screws miss the side", "fix": "Move them 10 mm in."}], [])
    monkeypatch.setattr(chat, "refine_part", Designer())
    got = fixing.apply(store, "side", [{"id": next(r["id"] for r in _rows(store, "side") if r["id"].startswith("finding:")),
                                        "choice": 0}], check=False)
    assert [r["status"] for r in got["results"]] == ["fixed"]                     # measured: off the list
    assess.run(store, client=claude)
    got = fixing.apply(store, "step", [{"id": "reading:1:r1", "choice": 0}], check=False)
    assert [r["status"] for r in got["results"]] == ["done, not measured"]
    assert assess.offer(store)["stale"] == {"step": 1}
    again = assess.run(store, client=claude)
    assert not review.findings(store)["findings"] and again["readings"] == [] and "found nothing more" in again["said"]
    assert not [r for r in _rows(store, "step") + _rows(store, "side") if r["id"].startswith(("finding:", "reading:"))]


def test_a_reading_lists_at_most_eight_each_said_short(store):
    many = [{"parts": ["side"], "said": f"thing {i} " + "x" * 600, "fix": "y"} for i in range(10)]
    got = assess.parse(json.dumps({"readings": many}), store, {"findings": []})
    assert len(got["readings"]) == 8 and got["dropped"] == 2 and [r["id"] for r in got["readings"]][-1] == "r8"
    assert all(len(r["said"]) == assess.LONGEST for r in got["readings"])



# --- #368 review (reviewer-3) ---------------------------------------------------------------------------------------------
def test_a_part_named_as_the_person_sees_it_is_that_part(store):
    """step-stool-5's part is step_stool, labelled "Step stool": all three readings naming it were dropped."""
    store.design.part("step").label = "Step stool"
    store.save()
    got = assess.run(store, client=Claude([
        {"parts": ["Step stool"], "said": "the step is thin", "fix": "Make it 25 mm."},
        {"parts": ["the step"], "said": "it sags", "fix": "Add a rail."},
        {"parts": ["stool"], "said": "it tips", "fix": "Widen it."},
        {"parts": ["Side"], "said": "the side splits", "fix": "Glue it."}]))
    assert [r["parts"] for r in got["readings"]] == [["step"], ["step"], ["step"], ["side"]], got
    assert not got["set_aside"] and got["said"].startswith("Claude's reading of 2 parts (4 things")


def test_every_point_set_aside_is_never_found_nothing_more(store):
    got = assess.run(store, client=Claude(["the step is thin"]))                    # a bare sentence, no parts
    assert got["ok"] and got["readings"] == [] and got["set_aside"][0]["said"] == "the step is thin"
    assert got["said"] == ("Claude read 2 parts, and none of what it said could be kept: 1 of Claude's 1 point was left "
                           "out: 1 named no part here. Look at it yourself."), got["said"]


STOOL4 = [{"kind": "fit", "parts": ["step", "side"], "measured": True, "said": "the step is 0.1 mm too big for side's pocket",
           "fix": "Size side's pocket."}]


@pytest.mark.parametrize("reading", [
    {"parts": ["step", "side"], "said": "the step is held to the side by glue alone and will work loose as it racks",
     "fix": "Add a screw."},
    {"parts": ["step", "side"], "said": "the side's pocket leaves 20 mm at a tight corner that will split",
     "fix": "Move the pocket in."},
    {"parts": ["step"], "said": "the step is 19 mm over its full length, too thin for a 300 lb step", "fix": "Make it 25 mm."},
])
def test_a_different_problem_on_the_same_parts_is_kept(store, reading):
    """reviewer-3's step-stool-4 cases: a racking joint, a splitting pocket and a thin step were dropped as repeats."""
    got = assess.run(store, client=Claude([reading]), found={"findings": STOOL4})
    (kept,) = got["readings"]
    assert kept["said"] == reading["said"] and not got["set_aside"]
    if set(reading["parts"]) == {"step", "side"}:                # may say the fit again: badged, never dropped
        assert kept["may_repeat"] == "the step is 0.1 mm too big for side's pocket"
        assert "May repeat what's measured" in got["said"]


def test_same_as_on_other_parts_keeps_the_reading(store):
    got = assess.run(store, client=Claude([{"parts": ["step"], "said": "too big", "fix": "Trim.", "same_as": "m1"}]),
                     found={"findings": STOOL4})
    assert len(got["readings"]) == 1 and not got["set_aside"]


def test_the_list_counts_readings_apart_from_what_s_measured(store, monkeypatch):
    assess.run(store, client=Claude([{"parts": ["step"], "said": "a", "fix": "b"}, {"parts": ["step"], "said": "c", "fix": "d"}]))
    got = fixes.listed(store, design_api.design_state(store), "step")
    assert got["counts"] == {"measured": 1, "readings": 2, "other": 0}             # the fit finding, and two readings
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [], "checks": 3})
    got = fixes.listed(store, design_api.design_state(store), "step")
    assert got["counts"] == {"measured": 0, "readings": 2, "other": 0}             # only readings: none measured wrong
    assert fixes.counts([{"id": "off:x", "measured": False}]) == {"measured": 0, "readings": 0, "other": 1}


def test_one_reading_at_a_time_and_never_the_same_file(store, monkeypatch):
    lock = assess._one_at_a_time(store)
    lock.acquire()
    try:
        got = assess.run(store, client=Claude([]))
        assert got == {"ok": False, "busy": True, "readings": [], "said": assess.BUSY}
    finally:
        lock.release()
    assert assess.count(store) == 0
    monkeypatch.setattr(assess, "_files", lambda store: [])         # both presses see no readings yet
    a, b = assess._save(store, {"readings": []}), assess._save(store, {"readings": []})
    assert (a["n"], b["n"]) == (1, 2)


def test_a_brace_after_the_object_is_prose(store):
    got = assess.parse('{"readings": []}\nNote: see {above}.', store, {"findings": []})
    assert got["readings"] == [] and got["set_aside"] == []


def test_the_offer_names_parts_added_since_and_parts_gone(store):
    assess.run(store, client=Claude([]))
    store.write_part("rail", SIDE, intent="a rail")
    assert assess.offer(store)["unread"] == ["rail"]
    store.design.parts = [p for p in store.design.parts if p.id != "side"]
    store.save()
    assert assess.offer(store)["stale"] == {"side": 1}


def test_a_name_two_parts_share_words_with_is_read_exactly_or_not_at_all(store):
    """An exact id, spoken name or label wins; a word two parts both have names neither, and is said."""
    store.design.part("step").label = "Step stool"
    store.save()
    store.write_part("step_stool", STEP, intent="another step")
    got = assess.run(store, client=Claude([
        {"parts": ["step stool"], "said": "it's the other step", "fix": "x"},
        {"parts": ["Step stool"], "said": "it's labelled", "fix": "y"},
        {"parts": ["stool"], "said": "which one?", "fix": "z"}]))
    assert [r["parts"] for r in got["readings"]] == [["step_stool"], ["step_stool"]], got
    assert [(a["why"], a["named"]) for a in got["set_aside"]] == [("named no part here", ["stool"])]
    store.design.part("side").label = "Stool"                 # a label whose word two other parts' names have too
    store.save()
    got = assess.parse(json.dumps({"readings": [{"parts": ["Stool"], "said": "a", "fix": "b"}]}), store, {"findings": []})
    assert got["readings"][0]["parts"] == ["side"]
