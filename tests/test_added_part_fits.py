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
        "edge." in res.reply, res.reply


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
