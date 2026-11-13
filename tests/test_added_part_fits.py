"""CALI-171 (#266), Theo's live step-stool-5: he picked an inside-corner edge and asked for a printed fillet strip "I can glue onto
this edge". A new part was added that floated 76.75 mm off the stool, and the reply opened "✓ built … Every check on this part
passes". A part added with a pick has the picked edge as a requirement: its surface must touch that edge, measured each round
(the round fails and repairs); a miss after the last round leads the reply, with no ✓ over it. A new part the drafted test
says doesn't sit on another (``min_clearance`` measured off it) leads with that too. A synthetic L of a stool, not Theo's."""

import pytest

pytest.importorskip("cadquery")

from caliper import chat, features  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

#: A side and a step over it: the inside corner where they meet runs along y at x 19.05, z 300.
STOOL = '''import cadquery as cq

PARAMS = {"t": 19.05, "d": 200.0, "h": 300.0, "w": 300.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, d, h, w = p["t"], p["d"], p["h"], p["w"]
    side = cq.Workplane().box(t, d, h, centered=False)
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side.union(step)
'''

#: A 5 mm strip along the corner, its corner on the picked edge; ``lift`` raises it off (81.75 leaves its foot 76.75 above).
STRIP = '''import cadquery as cq

PARAMS = {{"r": 5.0}}


def build(params):
    p = {{**PARAMS, **(params or {{}})}}
    return cq.Workplane().box(p["r"], 200.0, p["r"], centered=False).translate((19.05, 0, 300.0 - p["r"] + {lift}))
'''


@pytest.fixture
def stool(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", STOOL, intent="a side and a step")
    feats = features.for_part(s, "stool")
    edge = next(e for e in feats["edges"] if e.get("corner") == "inside" and abs(e["length"] - 200.0) < 1e-6
                and abs(e["centre"][0] - 19.05) < 1e-6)
    pick = {"part": "stool", "kind": "edge", "id": edge["id"], "said": "the line between two flat faces (inside corner)",
            "version": feats["version"]}
    return s, pick


def _author(*lifts):
    seen = []

    def author(spec, feedback, prior):
        seen.append((spec.intent, feedback))
        return STRIP.format(lift=lifts[min(len(seen) - 1, len(lifts) - 1)])
    return author, seen


def test_the_picked_edge_is_a_requirement_the_designer_is_told(stool):
    s, pick = stool
    author, seen = _author(0.0)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool")
    asked = seen[0][0]
    assert "the edge picked on stool" in asked and "(19.05, 0, 300)" in asked and "(19.05, 200, 300)" in asked, asked
    assert "within 0.5 mm" in asked, asked
    assert res.ok and res.reply.startswith("✓ built **fillet_strip**"), res.reply
    assert "sits on the edge you picked on stool" in res.reply, res.reply


def test_a_strip_that_misses_the_pick_fails_its_round_and_is_repaired(stool):
    s, pick = stool
    author, seen = _author(81.75, 0.0)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool", max_rounds=3)
    assert len(seen) == 2, seen
    assert "on_the_pick" in seen[1][1] and "76.75 mm off the edge picked on stool" in seen[1][1], seen[1][1]
    assert res.ok and res.reply.startswith("✓"), res.reply


def test_a_miss_after_the_last_round_leads_the_reply_and_isn_t_a_success(stool):
    """Theo's: "✓ built inside_corner_fillets … Every check on this part passes" over a measured 76.75 mm miss."""
    s, pick = stool
    author, _ = _author(81.75)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool", max_rounds=2)
    assert not res.ok
    assert res.reply.startswith("✗ Built fillet_strip, but it sits 76.75 mm off the edge you picked on stool: not where you "
                                "asked."), res.reply
    assert "✓" not in res.reply.split("\n")[0] and "Every check on this part passes" not in res.reply, res.reply
    assert s.design.part("fillet_strip") is not None          # it's kept, said: the person decides


def test_a_turn_with_a_pick_that_adds_a_part_passes_the_pick_on(stool, monkeypatch):
    s, pick = stool
    got = {}

    def fake(store, part_id, intent, **kw):
        got.update(kw, part=part_id)
        return chat.TurnResult(action="author", ok=True, part=part_id, reply="built")
    monkeypatch.setattr(chat, "author_part", fake)
    chat.turn(s, "add a 5 mm printed fillet strip on this edge", scope="stool", pick=pick, use_llm=False,
              classifier=lambda *a, **k: chat.Intent(action="author", part="fillet_strip", intent="a fillet strip",
                                                       source="injected"))
    assert got["part"] == "fillet_strip" and got["pick"] == pick and got["on"] == "stool", got


def test_a_new_part_the_drafted_test_finds_off_its_neighbour_leads_with_the_miss(stool, monkeypatch):
    """No pick: the promote job drafted ``min_clearance(new, stool) <= 0.2`` and measured 76.75 off. That's the reply's first
    line, not a ✓."""
    from caliper.promote import Proposal

    s, _ = stool
    author, _ = _author(81.75)
    drafted = Proposal(id="seated", expr="min_clearance(fillet_strip, stool) <= 0.2", level="design", part="fillet_strip",
                       holds_now=False, actual=76.75)
    monkeypatch.setattr(chat, "_offer_promotion", lambda *a, **k: (drafted, "💡 I can lock that in as a test"))
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip", author=author, use_llm=False)
    assert not res.ok
    assert res.reply.startswith("✗ Built fillet_strip, but it sits 76.75 mm off stool: not where you asked."), res.reply
    # one that holds says nothing new
    drafted.holds_now, drafted.actual = True, 0.0
    res = chat.author_part(s, "fillet_strip_2", "a 5 mm printed fillet strip", author=_author(0.0)[0], use_llm=False)
    assert res.ok and res.reply.startswith("✓ built"), res.reply


def test_a_strip_on_half_the_edge_doesn_t_sit_on_it(stool):
    """Touching it somewhere isn't sitting on it: the whole length is measured, and the worst point is what's said."""
    s, pick = stool

    def author(spec, feedback, prior):
        return STRIP.format(lift=0.0).replace("box(p[\"r\"], 200.0,", "box(p[\"r\"], 100.0,")
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool", max_rounds=1)
    assert not res.ok and res.reply.startswith("✗ Built fillet_strip, but it sits 100 mm off the edge you picked"), res.reply


def test_a_pick_from_an_older_version_is_said_first_and_not_used(stool):
    """The pick's ids were that version's: after the stool changes, its edge may be another one. Not used, said at the top
    with why, and no ✓ over where it went (#269 review)."""
    s, pick = stool
    s.write_part("stool", STOOL.replace('"h": 300.0', '"h": 350.0'), intent="a side and a step")
    author, seen = _author(0.0)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool")
    assert "the edge picked on stool" not in seen[0][0] and "sits on the edge you picked" not in res.reply, res.reply
    assert not res.ok and res.reply.startswith("! Built fillet_strip, but I couldn't place it against your pick: you picked "
                                               "it on v1, and stool is v2 now: pick it again."), res.reply
    assert "✓" not in res.reply.split("\n\n")[1].split("\n")[0], res.reply


def test_a_face_picked_where_an_edge_is_needed_is_said_first(stool):
    s, pick = stool
    face = {**pick, "kind": "face", "id": "f0"}
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip here", author=_author(0.0)[0], use_llm=False,
                           promote_feedback=False, pick=face, on="stool")
    assert not res.ok and res.reply.startswith("! Built fillet_strip, but I couldn't place it against your pick: you picked a "
                                               "face, and a part that sits on an edge needs the edge: pick it."), res.reply


def test_a_pick_whose_part_s_edges_can_t_be_worked_out_is_said_first(stool, monkeypatch):
    s, pick = stool
    monkeypatch.setattr(chat, "_features_of", lambda store, pid: None)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=_author(0.0)[0],
                           use_llm=False, promote_feedback=False, pick=pick, on="stool")
    assert not res.ok and res.reply.startswith("! Built fillet_strip, but I couldn't place it against your pick: I couldn't "
                                               "work out stool's edges."), res.reply


#: (#269 review) Touching the edge from inside isn't sitting on it: a block centred on the corner, half in the side and the
#: step, and a strip inside the side panel with its corner on the edge.
HALF_IN = STRIP.format(lift=0.0).replace('translate((19.05, 0, 300.0 - p["r"] + 0.0))',
                                         'translate((19.05 - p["r"] / 2, 0, 300.0 - p["r"] / 2))')
IN_PANEL = STRIP.format(lift=0.0).replace('translate((19.05, 0, 300.0 - p["r"] + 0.0))',
                                          'translate((19.05 - p["r"], 0, 300.0 - p["r"]))')


#: how deep each goes: the half-inside block's buried corner is 2.5 mm in each way from the L's inside corner, 2.5√2 from it
@pytest.mark.parametrize("script,depth", [(HALF_IN, 2.5 * 2 ** 0.5), (IN_PANEL, 5.0)], ids=["half inside", "inside the panel"])
def test_a_strip_that_goes_into_the_picked_part_doesn_t_sit_on_it(stool, script, depth):
    assert script != STRIP.format(lift=0.0)
    s, pick = stool
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return script if len(seen) == 1 else STRIP.format(lift=0.0)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                           promote_feedback=False, pick=pick, on="stool", max_rounds=3)
    assert len(seen) == 2 and "goes" in seen[1] and "into stool: it should sit on it" in seen[1], seen[1]
    assert res.ok, res.reply                                       # repaired: seated from outside
    # and one that stays in: said first, never a ✓
    res = chat.author_part(s, "fillet_strip_2", "a 5 mm printed fillet strip on this edge", author=lambda *a: script,
                           use_llm=False, promote_feedback=False, pick=pick, on="stool", max_rounds=1)
    assert not res.ok and res.reply.startswith("✗ Built fillet_strip_2, but it goes "), res.reply
    said = float(res.reply.split("it goes ")[1].split(" mm")[0])
    assert said == pytest.approx(depth, abs=0.6) and "into stool: it should sit on it." in res.reply.split("\n")[0], res.reply


# --- "this edge and the opposite edge": a mirrored second strip ------------------------------------------------------------
#: Two sides under a step: inside corners along y at x 19.05 and x 280.95, both at z 300.
TWO_SIDES = STOOL.replace('''    side = cq.Workplane().box(t, d, h, centered=False)
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side.union(step)''', '''    side = lambda x0: cq.Workplane().box(t, d, h, centered=False).translate((x0, 0, 0))
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side(0).union(side(w - t)).union(step)''')
assert TWO_SIDES != STOOL


@pytest.fixture
def two_sides(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", TWO_SIDES, intent="two sides and a step")
    feats = features.for_part(s, "stool")
    edge = next(e for e in feats["edges"] if e.get("corner") == "inside" and abs(e["length"] - 200.0) < 1e-6
                and abs(e["centre"][0] - 19.05) < 1e-6)
    return s, {"part": "stool", "kind": "edge", "id": edge["id"], "said": "the inside corner", "version": feats["version"]}


ASKED = "a 5 mm printed fillet strip I can glue onto this edge and the opposite edge"


def test_this_edge_and_the_opposite_one_is_a_strip_and_its_mirror_each_seated(two_sides):
    from caliper import mirror

    s, pick = two_sides
    author, seen = _author(0.0)
    res = chat.author_part(s, "fillet_strip", ASKED, author=author, use_llm=False, promote_feedback=False, pick=pick, on="stool",
                           asked=ASKED)
    assert len(seen) == 1 and "the opposite one is made as its mirror" in seen[0][0], seen[0][0]   # one strip designed
    assert mirror.source_of(s, "fillet_strip_opposite") == "fillet_strip"
    other = s.part_geometry("fillet_strip_opposite").require_mesh().bounds
    assert other[0][0] == pytest.approx(300.0 - 19.05 - 5.0, abs=1e-6) and other[1][0] == pytest.approx(300.0 - 19.05, abs=1e-6)
    assert res.ok and "It sits on the edge you picked on stool, and its mirror fillet_strip_opposite sits on the opposite " \
        "edge, the line from (280.95, 0, 300) to (280.95, 200, 300)." in res.reply, res.reply      # which, said (#270 review)


def test_one_edge_asked_is_one_strip(two_sides):
    s, pick = two_sides
    author, seen = _author(0.0)
    chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=author, use_llm=False,
                     promote_feedback=False, pick=pick, on="stool", asked="a 5 mm printed fillet strip on this edge")
    assert s.design.part("fillet_strip_opposite") is None and "opposite" not in seen[0][0]


def test_an_opposite_edge_that_isn_t_there_is_said_first(stool):
    """The L has one side: no edge mirrors the picked one, so there's one strip, and the reply leads with why."""
    s, pick = stool
    author, _ = _author(0.0)
    res = chat.author_part(s, "fillet_strip", ASKED, author=author, use_llm=False, promote_feedback=False, pick=pick, on="stool",
                           asked=ASKED)
    assert not res.ok and s.design.part("fillet_strip_opposite") is None
    assert res.reply.startswith("! Built fillet_strip on the edge you picked, but I found no edge on stool opposite it, so "
                                "there's one strip."), res.reply


def test_a_turn_passes_the_person_s_own_words(stool, monkeypatch):
    """The classifier's summary of a new part can drop "and the opposite edge": what was asked goes along too."""
    s, pick = stool
    got = {}
    monkeypatch.setattr(chat, "author_part", lambda store, pid, intent, **kw: got.update(kw) or chat.TurnResult(
        action="author", ok=True, part=pid, reply="built"))
    chat.turn(s, ASKED, scope="stool", pick=pick, use_llm=False,
              classifier=lambda *a, **k: chat.Intent(action="author", part="fillet_strip", intent="a fillet strip",
                                                       source="injected"))
    assert got["asked"] == ASKED, got


def test_the_person_s_words_decide_it_when_the_summary_drops_them(two_sides):
    s, pick = two_sides
    chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip", author=_author(0.0)[0], use_llm=False,
                     promote_feedback=False, pick=pick, on="stool", asked=ASKED)
    assert s.design.part("fillet_strip_opposite") is not None


def test_a_mirror_measured_off_the_opposite_edge_leads_the_reply(two_sides, monkeypatch):
    """The mirror is measured on its edge as the first is on the pick, not assumed to land: a gap there is said first."""
    s, pick = two_sides
    real = chat._seat_gap
    monkeypatch.setattr(chat, "_seat_gap", lambda g, seat: 3.0 if seat["said"] == "the opposite edge" else real(g, seat))
    res = chat.author_part(s, "fillet_strip", ASKED, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=ASKED)
    assert not res.ok and res.reply.startswith("✗ Built fillet_strip and its mirror fillet_strip_opposite, but "
                                               "fillet_strip_opposite sits 3 mm off the opposite edge."), res.reply


def test_a_mirror_that_goes_into_the_part_leads_the_reply(two_sides, monkeypatch):
    """The mirror is held to the first strip's rule too: from outside the part (#269 review, merged into the opposite edge)."""
    s, pick = two_sides
    real = chat._into
    monkeypatch.setattr(chat, "_into", lambda g, store, on: 3.0 if g.require_mesh().bounds[0][0] > 150 else real(g, store, on))
    res = chat.author_part(s, "fillet_strip", ASKED, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=ASKED)
    assert not res.ok and res.reply.startswith("✗ Built fillet_strip and its mirror fillet_strip_opposite, but "
                                               "fillet_strip_opposite goes 3 mm into stool."), res.reply


# --- #238's findings after any added part, not only after a plan's build --------------------------------------------------
def test_the_findings_run_after_an_added_part_and_say_nothing_is_not_right(stool):
    s, pick = stool
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=_author(0.0)[0], use_llm=False,
                           promote_feedback=False, pick=pick, on="stool")
    assert res.ok and "Measured after the build: nothing found in " in res.reply, res.reply
    assert "That's what the checks see, not that it's right: look at it." in res.reply


def test_a_finding_about_the_new_part_leads_the_reply(stool, monkeypatch):
    from caliper import review

    s, pick = stool
    found = {"findings": [{"kind": "fit", "parts": ["fillet_strip", "stool"], "said": "the fillet strip is 2 mm into the stool",
                           "fix": "Move it out.", "measured": 2.0}], "checks": 3, "unmeasured": [], "notes": []}
    monkeypatch.setattr(review, "findings", lambda store, report=None: found)
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=_author(0.0)[0], use_llm=False,
                           promote_feedback=False, pick=pick, on="stool")
    assert not res.ok and res.reply.startswith("! Built fillet_strip, but the checks after it found 1 thing to fix with it: "
                                               "the fillet strip is 2 mm into the stool."), res.reply
    assert "- The fillet strip is 2 mm into the stool (fillet_strip, stool). Move it out." in res.reply
    # one about another part is listed, and isn't this part's miss
    found["findings"][0]["parts"] = ["stool"]
    res = chat.author_part(s, "fillet_strip_2", "a 5 mm printed fillet strip on this edge", author=_author(0.0)[0],
                           use_llm=False, promote_feedback=False, pick=pick, on="stool")
    assert res.ok and res.reply.startswith("✓ built") and "(stool). Move it out." in res.reply, res.reply


# --- #270 review ---------------------------------------------------------------------------------------------------------------
def test_words_about_the_strip_itself_make_one_strip(two_sides):
    s, pick = two_sides
    asked = "a 5 mm fillet strip rounded on both sides, on this edge"
    res = chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=asked)
    assert s.design.part("fillet_strip_opposite") is None and res.ok, res.reply


# --- #273: words that might mean a mirror ask; "say which" has an answer --------------------------------------------------------
@pytest.mark.parametrize("asked", ["a 5 mm fillet strip on this edge; mirror it on the other side",
                                   "a fillet strip on this edge and the one opposite",
                                   "a 5 mm fillet strip on this edge; I'll sand the other side smooth",
                                   "a fillet strip on this edge, mirror the profile so it's symmetric"])
def test_words_that_might_mean_a_mirror_ask_never_a_tick_over_one(two_sides, asked):
    """#241's pattern: "mirror it on the other side" missed the matcher and made one strip under a ✓."""
    s, pick = two_sides
    res = chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=asked)
    assert s.design.part("fillet_strip_opposite") is None and not res.ok
    assert res.reply.startswith("! Built fillet_strip on the edge you picked: one strip. Do you want its mirror on the "
                                "opposite edge too, the line from (280.95, 0, 300) to (280.95, 200, 300)? Say yes."), res.reply
    from caliper import awaiting

    assert awaiting.pending(s)["kind"] == "mirror_edge"


def test_yes_makes_the_mirror_it_asked_about(two_sides):
    s, pick = two_sides
    asked = "a 5 mm fillet strip on this edge; mirror it on the other side"
    chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=asked)
    res = chat.turn(s, "yes", use_llm=False)
    assert s.design.part("fillet_strip_opposite") is not None and res.ok, res.reply
    assert res.reply.startswith("Made fillet_strip's mirror fillet_strip_opposite: it sits on the opposite edge, the line "
                                "from (280.95, 0, 300) to (280.95, 200, 300)."), res.reply


def test_no_leaves_one_strip(two_sides):
    s, pick = two_sides
    asked = "a 5 mm fillet strip on this edge; mirror it on the other side"
    chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=asked)
    res = chat.turn(s, "no", use_llm=False)
    assert s.design.part("fillet_strip_opposite") is None and res.reply == "Left it: one strip.", res.reply


def _box4(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX4, intent="four walls")
    feats = features.for_part(s, "stool")
    edge = next(e for e in feats["edges"] if e.get("corner") == "inside" and abs(e["centre"][0] - 19.05) < 1e-6
                and abs(e["centre"][1] - 19.05) < 1e-6)
    pick = {"part": "stool", "kind": "edge", "id": edge["id"], "said": "an inside corner", "version": feats["version"]}
    strip = """import cadquery as cq

PARAMS = {"r": 5.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["r"], p["r"], 300.0, centered=False).translate((19.05, 19.05, 0))
"""
    chat.author_part(s, "fillet_strip", ASKED, author=lambda *a: strip, use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=ASKED)
    return s


@pytest.mark.parametrize("answer,at", [("across the width", (280.95, 19.05)), ("across x", (280.95, 19.05)),
                                       ("across the depth", (19.05, 280.95)), ("mirror it across y", (19.05, 280.95))])
def test_say_which_has_an_answer(tmp_path, monkeypatch, answer, at):
    s = _box4(tmp_path, monkeypatch)
    res = chat.turn(s, answer, use_llm=False)
    assert s.design.part("fillet_strip_opposite") is not None, res.reply
    lo, hi = s.part_geometry("fillet_strip_opposite").require_mesh().bounds
    assert ((lo[0] + hi[0]) / 2 - at[0]) ** 2 + ((lo[1] + hi[1]) / 2 - at[1]) ** 2 < (5.0 ** 2), (lo, hi)
    assert res.reply.startswith("Made fillet_strip's mirror fillet_strip_opposite: it sits on the opposite edge"), res.reply


def test_say_which_is_parked_so_the_answer_reads_against_it(tmp_path, monkeypatch):
    from caliper import awaiting

    s = _box4(tmp_path, monkeypatch)
    aw = awaiting.pending(s)
    assert aw["kind"] == "mirror_edge" and aw["part"] == "fillet_strip" and len(aw["twins"]) == 2


def test_an_answer_that_names_no_axis_lets_the_question_lapse(tmp_path, monkeypatch):
    s = _box4(tmp_path, monkeypatch)
    from caliper import awaiting

    assert chat._awaited(s, "make it blue", None, events=[], on_event=None) is None and awaiting.pending(s) is None


@pytest.mark.parametrize("asked", ["a fillet strip on this edge and the opposite edge", "fillet strips in both corners",
                                   "a fillet strip here and on the other side's edge", "strips on this edge and its twin"])
def test_edge_or_corner_wording_makes_the_mirror(two_sides, asked):
    s, pick = two_sides
    chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=asked)
    assert s.design.part("fillet_strip_opposite") is not None, asked


def test_the_reply_says_which_edge_it_mirrored_to(two_sides):
    s, pick = two_sides
    res = chat.author_part(s, "fillet_strip", ASKED, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=ASKED)
    assert ("its mirror fillet_strip_opposite sits on the opposite edge, the line from (280.95, 0, 300) to (280.95, 200, 300)"
            in res.reply), res.reply


#: The two sides with their construction: the opposite edge is named by the piece it's on.
NAMED = TWO_SIDES + '''

def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, d, h, w = p["t"], p["d"], p["h"], p["w"]
    return [{"name": "left side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h), (0, 0, h)]},
            {"name": "right side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w, 0, 0), (w, d, 0), (w, d, h), (w, 0, h)]},
            {"name": "step", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h + t), (w, 0, h + t), (w, d, h + t), (0, d, h + t)]}]
'''


def test_a_host_with_pieces_names_the_piece_the_mirror_is_on(two_sides):
    s, pick = two_sides
    s.write_part("stool", NAMED, intent="two sides and a step")
    feats = features.for_part(s, "stool")
    pick = {**pick, "version": feats["version"]}
    res = chat.author_part(s, "fillet_strip", ASKED, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=ASKED)
    assert "its mirror fillet_strip_opposite sits on the opposite edge, the right side's inside corner" in res.reply, res.reply


#: Four walls round a step: the left-front inside corner has a twin across x (right-front) and across y (left-back).
BOX4 = STOOL.replace('''    side = cq.Workplane().box(t, d, h, centered=False)
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side.union(step)''', '''    side = lambda x0: cq.Workplane().box(t, w, h, centered=False).translate((x0, 0, 0))
    rail = lambda y0: cq.Workplane().box(w - 2 * t, t, h, centered=False).translate((t, y0, 0))
    return side(0).union(side(w - t)).union(rail(0)).union(rail(w - t))''')


def test_twins_on_two_axes_are_asked_about_not_guessed(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX4, intent="four walls")
    feats = features.for_part(s, "stool")
    edge = next(e for e in feats["edges"] if e.get("corner") == "inside" and abs(e["centre"][0] - 19.05) < 1e-6
                and abs(e["centre"][1] - 19.05) < 1e-6)
    pick = {"part": "stool", "kind": "edge", "id": edge["id"], "said": "an inside corner", "version": feats["version"]}
    strip = '''import cadquery as cq

PARAMS = {"r": 5.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["r"], p["r"], 300.0, centered=False).translate((19.05, 19.05, 0))
'''
    res = chat.author_part(s, "fillet_strip", ASKED, author=lambda *a: strip, use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=ASKED)
    assert s.design.part("fillet_strip_opposite") is None and not res.ok
    assert res.reply.startswith("! Built fillet_strip on the edge you picked, but it has an opposite edge across the width "
                                "(x), the line from (280.95, 19.05, 0) to (280.95, 19.05, 300), and one across the depth (y), "
                                "the line from (19.05, 280.95, 0) to (19.05, 280.95, 300). Say \"across the width\" or "
                                "\"across the depth\"."), res.reply   # an answer it reads (#273)


@pytest.mark.parametrize("asked", ["a fillet strip on this edge and this edge", "fillet strips on these two edges",
                                   "a strip on this edge and that one"])
def test_two_edges_asked_with_one_picked_is_said(two_sides, asked):
    s, pick = two_sides
    res = chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                           on="stool", asked=asked)
    assert not res.ok and s.design.part("fillet_strip_opposite") is None
    assert res.reply.startswith("! Built fillet_strip on the edge you picked, but I have one edge picked: pick the other "
                                "one too, or say \"the opposite edge\"."), res.reply


def test_a_depth_that_can_t_be_measured_is_said_never_taken_as_outside(stool, monkeypatch):
    """#269's note: the depth measure swallowed an error as 0, which read as outside, a pass."""
    from caliper import spatial

    s, pick = stool
    monkeypatch.setattr(spatial, "contains", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no kernel")))
    res = chat.author_part(s, "fillet_strip", "a 5 mm printed fillet strip on this edge", author=_author(0.0)[0], use_llm=False,
                           promote_feedback=False, pick=pick, on="stool", max_rounds=1)
    assert not res.ok and res.reply.startswith("! Built fillet_strip, but I couldn't measure whether it goes into stool, so "
                                               "it isn't known to sit on it."), res.reply
    assert [r.status for r in res.part_report.results if r.id == "outside_the_pick"] == ["deferred"]   # waits, never a pass


def test_every_check_passes_never_sits_under_a_bang(two_sides):
    s, pick = two_sides
    res = chat.author_part(s, "fillet_strip", "a fillet strip on this edge and this edge", author=_author(0.0)[0],
                           use_llm=False, promote_feedback=False, pick=pick, on="stool",
                           asked="a fillet strip on this edge and this edge")
    assert res.reply.startswith("!") and "Every check on this part passes" not in res.reply, res.reply


# --- #274 review -----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("answer,at", [("the depth one", (19.05, 280.95)), ("depth", (19.05, 280.95)),
                                       ("the width one", (280.95, 19.05)), ("width please", (280.95, 19.05))])
def test_a_short_answer_naming_the_axis_is_read(tmp_path, monkeypatch, answer, at):
    s = _box4(tmp_path, monkeypatch)
    res = chat.turn(s, answer, use_llm=False)
    lo, hi = s.part_geometry("fillet_strip_opposite").require_mesh().bounds
    assert ((lo[0] + hi[0]) / 2 - at[0]) ** 2 + ((lo[1] + hi[1]) / 2 - at[1]) ** 2 < 25.0, (answer, res.reply)


def test_a_short_answer_naming_no_axis_is_said_not_understood_and_the_question_stays(tmp_path, monkeypatch):
    from caliper import awaiting

    s = _box4(tmp_path, monkeypatch)
    res = chat.turn(s, "that one", use_llm=False)
    assert res.reply == 'I didn\'t catch which: say "across the width" or "across the depth".', res.reply
    assert awaiting.pending(s)["kind"] == "mirror_edge" and s.design.part("fillet_strip_opposite") is None


def test_a_stale_answer_is_refused_in_words(two_sides):
    """The strip or the host changed since it asked: its edges may be others now."""
    s, pick = two_sides
    asked = "a 5 mm fillet strip on this edge; mirror it on the other side"
    chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=asked)
    s.write_part("stool", TWO_SIDES.replace('"h": 300.0', '"h": 320.0'), intent="two sides and a step")
    res = chat.turn(s, "yes", use_llm=False)
    assert s.design.part("fillet_strip_opposite") is None
    assert res.reply == ("I didn't make the mirror: stool has changed since I asked (it was v1, it's v2 now), so its "
                         "opposite edge may be another. Pick the edge again and ask."), res.reply


def _offers_a_test(pid):
    """A drafter that always offers to lock in a fit test, as the promote job does."""
    from caliper import promote

    return lambda *a, **k: promote.Draft(proposal=promote.Proposal(id="seated", expr=f"min_clearance({pid}, stool) <= 0.2",
                                                                   level="design", part=pid, holds_now=True))


def test_no_test_is_offered_while_a_mirror_question_is_open(two_sides):
    """One parked question at a time: a "yes" can only mean the mirror."""
    from caliper import awaiting, promote

    s, pick = two_sides
    asked = "a 5 mm fillet strip on this edge; mirror it on the other side"
    res = chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, pick=pick, on="stool", asked=asked,
                           drafter=_offers_a_test("fillet_strip"))
    assert awaiting.pending(s)["kind"] == "mirror_edge"
    assert "lock that in as a test" not in res.reply and promote.pending(s) is None, res.reply


def test_an_earlier_test_offer_doesn_t_take_the_mirror_question_s_yes(two_sides):
    """#274 re-check: an unanswered test offer from an earlier turn survived the mirror question, and "yes" locked the test."""
    from caliper import promote

    s, pick = two_sides
    chat.author_part(s, "first_strip", "a strip", author=_author(0.0)[0], use_llm=False, pick=pick, on="stool",
                     drafter=_offers_a_test("first_strip"))
    assert promote.pending(s) is not None                                         # offered, not answered
    asked = "a 5 mm fillet strip on this edge; mirror it on the other side"
    chat.author_part(s, "fillet_strip", asked, author=_author(0.0)[0], use_llm=False, promote_feedback=False, pick=pick,
                     on="stool", asked=asked)
    assert promote.pending(s) is None
    res = chat.turn(s, "yes", use_llm=False)
    assert s.design.part("fillet_strip_opposite") is not None and res.reply.startswith("Made fillet_strip's mirror"), res.reply
