"""CALI-30 — feedback becomes a test.

The rules this suite exists to hold: a proposal is **validated before it is ever offered**, it is
**proposed and confirmed, never silent**, unmeasurable feedback is **labelled honestly** rather than
faked into a number, and once accepted it **catches the regression** on a later revision.
"""

import json
import os

import pytest

from caliper import chat, promote
from caliper.assembly import Mate
from caliper.design import DesignStore
from caliper.spec import Assertion, Spec

BOX = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box({dx}, {dy}, {dz}).translate((0, {y}, 0))\n")


def _box(dx=40, dy=20, dz=10, y=0):
    return BOX.format(dx=dx, dy=dy, dz=dz, y=y)


def _author(script):
    return lambda spec, feedback, prior: script


@pytest.fixture
def gantry(tmp_path):
    """rail at the origin; carriage 24mm clear of it in Y."""
    s = DesignStore.create("a 3D printer gantry", base=str(tmp_path / "designs"))
    s.write_part("rail", _box(dx=200, dy=12), intent="the linear rail")
    s.write_part("carriage", _box(dx=40, dy=20, y=40), intent="the X carriage")
    s.assembly.mates.append(Mate(id="carriage_misses_rail", between=["carriage", "rail"],
                                 kind="no_interference"))
    s.save()
    return s


# --- drafting: the phrasings that come up constantly ----------------------
def test_a_clearance_rule_becomes_a_pairwise_assertion(gantry):
    pytest.importorskip("cadquery")
    got = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm")
    assert got.proposal is not None
    p = got.proposal
    assert p.level == "design"                      # relates two parts
    assert p.expr == "min_clearance(carriage, rail) >= 2.0"
    assert p.holds_now                              # the gap is 24mm today


def test_a_size_limit_becomes_a_part_assertion(gantry):
    pytest.importorskip("cadquery")
    got = promote.offline_draft(gantry, "carriage", "it must be no taller than 40mm")
    assert got.proposal.level == "part"             # one part's own geometry
    assert got.proposal.expr == "bbox.dz <= 40.0 + 0.1"         # what measuring a size can be off by (#28)


def test_a_no_collision_rule_is_recognised(gantry):
    pytest.importorskip("cadquery")
    got = promote.offline_draft(gantry, "carriage", "it must never touch the rail")
    assert got.proposal.expr == "interference(carriage, rail) <= 0"


def test_a_wall_minimum_is_recognised(gantry):
    pytest.importorskip("cadquery")
    got = promote.offline_draft(gantry, "carriage", "walls of at least 2mm please")
    assert got.proposal.expr == "min_wall >= 2.0 - 0.15"


def test_a_rule_about_something_that_is_not_a_part_is_not_invented(gantry):
    """'clear the gantry by 2mm' names nothing measurable — don't fabricate a probe for it."""
    got = promote.offline_draft(gantry, "carriage", "it must clear the flux_ring by at least 2mm")
    assert got.proposal is None and not got.measurable


def test_vague_feedback_is_not_faked_into_a_number(gantry):
    got = promote.offline_draft(gantry, "carriage", "make it look less chunky")
    assert got.proposal is None and not got.measurable
    assert "measure" in got.reason


# --- validation: never offer a test that doesn't measure ------------------
def test_validate_accepts_a_real_expression(gantry):
    pytest.importorskip("cadquery")
    v = promote.validate(gantry, "min_clearance(carriage, rail) >= 2.0", "design")
    assert v.ok and v.holds and v.actual == pytest.approx(24.0, abs=0.5)


def test_validate_rejects_an_unknown_probe(gantry):
    pytest.importorskip("cadquery")
    v = promote.validate(gantry, "flux_density(carriage) <= 3", "design")
    assert not v.ok and v.error


def test_validate_rejects_an_unparseable_expression(gantry):
    pytest.importorskip("cadquery")
    assert not promote.validate(gantry, "bbox.dz <=", "part", "carriage").ok


def test_a_candidate_that_will_not_evaluate_is_never_offered(gantry):
    pytest.importorskip("cadquery")
    got = promote._candidate(gantry, "bad", "nonsense_probe() <= 1", "design", "carriage", "why")
    assert got.proposal is None
    assert "doesn't measure cleanly" in got.reason and got.rejected


def test_a_proposal_that_does_not_hold_yet_is_offered_but_flagged(gantry):
    """Stating a goal the part doesn't meet is legitimate — implying it already complies is not."""
    pytest.importorskip("cadquery")
    got = promote.offline_draft(gantry, "carriage", "it must be no taller than 4mm")
    assert got.proposal is not None and not got.proposal.holds_now
    assert "does **not** hold right now" in got.proposal.describe()


def test_a_promoted_id_never_shadows_a_mate(gantry):
    """Two assertions sharing an id makes 'what did this break?' ambiguous — it's keyed by id."""
    pytest.importorskip("cadquery")
    gantry.assembly.mates.append(Mate(id="carriage_clears_rail", between=["carriage", "rail"],
                                      kind="clearance", value=1.0))
    gantry.save()
    got = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm")
    assert got.proposal.id == "carriage_clears_rail_2"


# --- parking: acceptance is a separate turn -------------------------------
def test_a_proposal_parks_and_reads_back(gantry):
    pytest.importorskip("cadquery")
    p = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm").proposal
    promote.park(gantry, p)
    assert os.path.exists(promote.pending_path(gantry))
    assert promote.pending(gantry).expr == p.expr
    promote.clear(gantry)
    assert promote.pending(gantry) is None


def test_a_corrupt_parking_slot_does_not_break_the_conversation(gantry):
    with open(promote.pending_path(gantry), "w") as f:
        f.write("{not json")
    assert promote.pending(gantry) is None


def test_yes_and_no_are_recognised_and_everything_else_is_not():
    assert promote.reads_as_yes("yes") is True
    assert promote.reads_as_yes("lock it in") is True
    assert promote.reads_as_yes("no, leave it") is False
    assert promote.reads_as_yes("skip that") is False
    assert promote.reads_as_yes("make it 5mm wider") is None
    assert promote.reads_as_yes("") is None


# --- acceptance: where the assertion actually lands -----------------------
def test_accepting_a_design_rule_puts_it_on_the_assembly(gantry):
    pytest.importorskip("cadquery")
    p = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm").proposal
    promote.park(gantry, p)
    where = promote.accept(gantry, p)
    assert where == "the design"
    assert [a.id for a in gantry.assembly.assertions] == ["carriage_clears_rail"]
    assert promote.pending(gantry) is None
    # and it survives a reload — it's in assembly.yaml, not just memory
    assert [a.expr for a in DesignStore.load(gantry.root).assembly.assertions] == [p.expr]


def test_accepting_a_part_rule_puts_it_on_the_part_spec(gantry):
    pytest.importorskip("cadquery")
    p = promote.offline_draft(gantry, "carriage", "it must be no taller than 40mm").proposal
    promote.accept(gantry, p)
    assert [a.expr for a in gantry.read_spec("carriage").assertions] == ["bbox.dz <= 40.0 + 0.1"]


def test_accepting_records_why_the_rule_exists(gantry):
    pytest.importorskip("cadquery")
    p = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm").proposal
    promote.accept(gantry, p)
    entry = gantry.history("carriage")[-1]
    assert entry["kind"] == "assertion" and entry["action"] == "promoted"
    assert entry["from_feedback"] == "it must clear the rail by at least 2mm"
    assert gantry.log()[-1]["action"] == "promoted"


def test_re_promoting_the_same_id_replaces_rather_than_duplicates(gantry):
    pytest.importorskip("cadquery")
    first = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm").proposal
    promote.accept(gantry, first)
    second = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 5mm").proposal
    promote.accept(gantry, second)
    assert len(gantry.assembly.assertions) == 1
    assert gantry.assembly.assertions[0].expr.endswith(">= 5.0")


def test_declining_records_that_the_choice_was_deliberate(gantry):
    pytest.importorskip("cadquery")
    p = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 2mm").proposal
    promote.park(gantry, p)
    promote.decline(gantry, p)
    assert gantry.assembly.assertions == []
    assert gantry.history("carriage")[-1]["action"] == "declined"
    assert promote.pending(gantry) is None


# --- the conversation: propose → confirm → enforced -----------------------
def test_a_rule_is_offered_after_the_change_lands(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage",
                    use_llm=False, author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    assert res.proposal is not None
    assert "I can lock that in as a test" in res.reply
    assert "min_clearance(carriage, rail) >= 2.0" in res.reply
    assert promote.pending(gantry) is not None      # parked for the next turn


def test_saying_yes_enforces_it(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    res = chat.turn(gantry, "yes", use_llm=False)
    assert res.action == "accept" and res.ok
    assert "Locked in on the design" in res.reply
    assert [a.id for a in gantry.assembly.assertions] == ["carriage_clears_rail"]


def test_saying_no_leaves_it_a_one_off(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    res = chat.turn(gantry, "no, leave it", use_llm=False)
    assert res.action == "decline" and res.ok
    assert "not** enforced" in res.reply
    assert gantry.assembly.assertions == []


def test_yes_is_not_misread_as_a_request_to_change_geometry(gantry):
    """Without the parked-proposal short-circuit, "yes" would route to refine and author a revision."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    before = gantry.design.part("carriage").version
    chat.turn(gantry, "yes", scope="carriage", use_llm=False)
    assert gantry.design.part("carriage").version == before


def test_the_accepted_rule_catches_the_regression_on_a_later_revision(gantry):
    """The whole point: a promoted rule survives the conversation that created it."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    chat.turn(gantry, "yes", use_llm=False)

    # a later change slides the carriage to 1mm off the rail — still no collision, so the MATE
    # stays green; only the promoted rule catches it.
    res = chat.turn(gantry, "move it closer to the rail", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=20, y=17)), max_rounds=2)
    assert res.broke == ["carriage_clears_rail"]
    assert "carriage_misses_rail" not in res.broke       # the collision mate is still fine
    assert "broke 1 design check" in res.reply


def test_an_unenforced_rule_would_have_missed_that_regression(gantry):
    """The control for the test above — decline, and the same change sails through."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    chat.turn(gantry, "no", use_llm=False)
    res = chat.turn(gantry, "move it closer to the rail", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=20, y=17)), max_rounds=2)
    assert res.broke == [] and res.ok


def test_an_unmeasurable_rule_is_labelled_not_faked(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "it must look less chunky", scope="carriage", use_llm=False,
                    author=_author(_box(dx=30, dy=20, y=40)), max_rounds=2)
    assert res.proposal is None
    assert "phrased that as a rule, but I can't make it one" in res.reply
    assert "could undo it" in res.reply


def test_an_ordinary_tweak_is_not_pestered_with_an_offer(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "make it a bit wider", scope="carriage", use_llm=False,
                    author=_author(_box(dx=50, dy=20, y=40)), max_rounds=2)
    assert res.proposal is None
    assert "lock that in" not in res.reply and "can't make it one" not in res.reply


def test_a_new_change_supersedes_a_stale_offer(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    chat.turn(gantry, "make it wider", scope="carriage", use_llm=False,
              author=_author(_box(dx=60, dy=20, y=40)), max_rounds=2)
    assert promote.pending(gantry) is None          # the old offer is gone, not silently accepted
    assert gantry.assembly.assertions == []


def test_a_rollback_drops_a_pending_offer(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    chat.turn(gantry, "roll it back", scope="carriage", use_llm=False)
    assert promote.pending(gantry) is None


def test_promotion_can_be_switched_off(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage",
                    use_llm=False, author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2,
                    promote_feedback=False)
    assert res.proposal is None and promote.pending(gantry) is None


# --- the LLM path is held to exactly the same standard --------------------
class _StubClient:
    def __init__(self, text):
        self._text = text
        self.messages = self

    def create(self, **kw):
        blk = type("B", (), {"type": "text", "text": self._text})
        return type("M", (), {"content": [blk]})()


def test_an_llm_draft_is_validated_like_any_other(gantry):
    pytest.importorskip("cadquery")
    client = _StubClient(json.dumps({"measurable": True, "level": "design", "id": "keeps_its_gap",
                                     "expr": "min_clearance(carriage, rail) >= 3"}))
    got = promote.llm_draft(gantry, "carriage", "keep a gap", client=client)
    assert got.proposal.id == "keeps_its_gap" and got.proposal.source == "llm"
    assert got.proposal.holds_now


def test_an_llm_draft_that_invents_a_probe_is_rejected(gantry):
    pytest.importorskip("cadquery")
    client = _StubClient(json.dumps({"measurable": True, "level": "design", "id": "nope",
                                     "expr": "stiffness(carriage) >= 3"}))
    got = promote.llm_draft(gantry, "carriage", "make it stiff", client=client)
    assert got.proposal is None and "doesn't measure cleanly" in got.reason


def test_the_llm_may_say_it_is_not_measurable(gantry):
    client = _StubClient(json.dumps({"measurable": False, "reason": "aesthetic preference"}))
    got = promote.llm_draft(gantry, "carriage", "prettier please", client=client)
    assert got.proposal is None and got.reason == "aesthetic preference"


def test_drafting_falls_back_to_patterns_when_the_llm_misbehaves(gantry, capsys):
    pytest.importorskip("cadquery")
    got = promote.draft(gantry, "carriage", "it must clear the rail by at least 2mm",
                        client=_StubClient("not json"))
    assert got.proposal is not None and got.proposal.source == "offline"
    assert "LLM drafting failed" in capsys.readouterr().err


def test_an_injected_drafter_wins(gantry):
    fixed = promote.Draft(measurable=False, reason="stubbed")
    got = promote.draft(gantry, "carriage", "anything", drafter=lambda *a: fixed)
    assert got.reason == "stubbed"


def test_a_failed_draft_never_loses_the_users_edit(gantry):
    """Drafting is a bonus on top of the change — it must not be able to sink it."""
    pytest.importorskip("cadquery")

    def explode(*a):
        raise RuntimeError("drafting is broken")

    res = chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage",
                    use_llm=False, author=_author(_box(dx=60, dy=20, y=40)), max_rounds=2,
                    drafter=explode)
    assert res.ok and res.version == 2 and "60" in gantry.read_script("carriage")
    assert res.proposal is None
    assert any(e.kind == "error" and "draft" in e.text for e in res.events)


# --- the spec surface CALI-28 left for this ------------------------------
def test_promotion_does_not_cut_a_geometry_revision(gantry):
    pytest.importorskip("cadquery")
    spec = Spec(part="carriage", intent="the X carriage",
                assertions=[Assertion(id="existing", expr="body_count == 1")])
    gantry.write_spec("carriage", spec)
    before = gantry.design.part("carriage").version
    p = promote.offline_draft(gantry, "carriage", "it must be no taller than 40mm").proposal
    promote.accept(gantry, p)
    assert gantry.design.part("carriage").version == before
    assert [a.id for a in gantry.read_spec("carriage").assertions] == ["existing", "carriage_height"]


def test_an_accepted_part_rule_fails_a_later_revision_that_violates_it(gantry):
    """Design-level rules surface as `broke`; part-level ones fail the part's own report."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must be no taller than 12mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, dz=10, y=40)), max_rounds=2)
    res = chat.turn(gantry, "yes", use_llm=False)
    assert res.action == "accept"

    # now revise it to 30mm tall — the author can't satisfy the rule, and the turn says so
    res = chat.turn(gantry, "make it much taller", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=20, dz=30, y=40)), max_rounds=2)
    assert not res.ok
    failing = [r.id for r in res.part_report.results if r.status != "pass"]
    assert "carriage_height" in failing
    assert "carriage_height" in res.reply


def test_a_promoted_design_rule_reaches_the_author_of_a_later_revision(gantry):
    """Enforcing a rule after the fact is the safety net; telling the author up front is the fix."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "it must clear the rail by at least 2mm", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    chat.turn(gantry, "yes", use_llm=False)

    seen = {}

    def author(spec, feedback, prior):
        seen["intent"] = spec.intent
        return _box(dx=60, dy=20, y=40)

    chat.turn(gantry, "make it wider", scope="carriage", use_llm=False, author=author, max_rounds=2)
    assert "DESIGN RULES IN FORCE" in seen["intent"]
    assert "min_clearance(carriage, rail) >= 2.0" in seen["intent"]


def test_a_proposal_that_does_not_hold_says_the_edit_missed_the_ask(gantry):
    """Seen live: the author 'succeeded' while not doing what was asked. The offer must not gloss it."""
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "it must be no taller than 4mm", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=20, dz=10, y=40)), max_rounds=2)
    assert "didn't actually achieve what you asked for" in res.reply
    assert "I'll have to make the part satisfy it" in res.reply


# --- conflicting rules: two rules that can't both hold --------------------
def test_bounds_only_reads_the_shapes_it_can_reason_about():
    assert promote._bounds("min_clearance(a, b) >= 3")[1] == 3.0
    assert promote._bounds("bbox.dz <= 40")[2] == 40.0
    assert promote._bounds("0.1 <= x <= 0.3") is None      # a band — don't guess
    assert promote._bounds("is_watertight") is None        # not a comparison
    assert promote._bounds("bbox.dz <=") is None           # not even parseable


def test_a_contradicting_rule_is_named_not_silently_stacked(gantry):
    """Seen live: 'move it within 1mm' after locking in '>= 3mm'. Both can't hold."""
    pytest.importorskip("cadquery")
    gantry.assembly.assertions.append(
        Assertion(id="carriage_gap", expr="min_clearance(carriage, rail) >= 3.0"))
    gantry.save()
    found = promote.conflicts(gantry, "min_clearance(carriage, rail) <= 1.0", "design", "carriage")
    assert [c[1] for c in found] == ["carriage_gap"]


def test_compatible_rules_are_not_flagged_as_conflicts(gantry):
    pytest.importorskip("cadquery")
    gantry.assembly.assertions.append(
        Assertion(id="carriage_gap", expr="min_clearance(carriage, rail) >= 3.0"))
    gantry.save()
    assert promote.conflicts(gantry, "min_clearance(carriage, rail) <= 50", "design", "carriage") == []
    # a rule about a different measurement never conflicts
    assert promote.conflicts(gantry, "max_interference() <= 0", "design", "carriage") == []


def test_accepting_a_conflicting_rule_retires_the_one_it_replaces(gantry):
    pytest.importorskip("cadquery")
    first = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 20mm").proposal
    promote.accept(gantry, first)

    second = promote._candidate(gantry, "carriage_hugs_rail",
                                "min_clearance(carriage, rail) <= 1.0", "design", "carriage",
                                "hug the rail").proposal
    assert [c[1] for c in second.conflicts] == [first.id]
    assert "Both can't hold" in second.describe()

    promote.accept(gantry, second)
    assert [a.id for a in gantry.assembly.assertions] == ["carriage_hugs_rail"]
    assert gantry.history("carriage")[-1]["replaced"] == [first.id]


def test_the_accept_reply_says_what_it_retired(gantry):
    pytest.importorskip("cadquery")
    first = promote.offline_draft(gantry, "carriage", "it must clear the rail by at least 20mm").proposal
    promote.accept(gantry, first)
    second = promote._candidate(gantry, "carriage_hugs_rail",
                                "min_clearance(carriage, rail) <= 1.0", "design", "carriage",
                                "hug it").proposal
    promote.park(gantry, second)
    res = chat.turn(gantry, "yes", use_llm=False)
    assert f"Retired **{first.id}**" in res.reply


def test_conflicts_survive_the_parking_slot(gantry):
    pytest.importorskip("cadquery")
    gantry.assembly.assertions.append(
        Assertion(id="carriage_gap", expr="min_clearance(carriage, rail) >= 3.0"))
    gantry.save()
    p = promote._candidate(gantry, "carriage_hugs_rail", "min_clearance(carriage, rail) <= 1.0",
                           "design", "carriage", "hug it").proposal
    promote.park(gantry, p)
    assert promote.pending(gantry).conflicts == [("design", "carriage_gap",
                                                  "min_clearance(carriage, rail) >= 3.0")]


def test_a_strength_requirement_is_sent_to_the_strength_check_not_refused(gantry):
    """CALI-54: "it has to hold 200 lb" can't be a rule on the shape, but it isn't lost either: the designer
    writes it into loads(), and the reply says where it's checked."""
    pytest.importorskip("cadquery")
    with_loads = _box(dx=40, dy=20, y=40) + (
        "\n\ndef loads(params, build=None):\n"
        "    return [{'name': 'a person', 'lb': 200, 'factor': 2, 'lo': (-5, 35, 3), 'hi': (5, 45, 5)}]\n")
    res = chat.turn(gantry, "it has to hold me, 200 lb, standing on it", scope="carriage", use_llm=False,
                    author=_author(with_loads), max_rounds=2)
    assert res.proposal is None
    assert "can't make it one" not in res.reply
    assert "`loads()` now" in res.reply and "Check it holds" in res.reply


# --- CALI-68 (#28): a rule pinning a measured size allows for what measuring it can be off by ----------------
def test_three_quarter_ply_measured_at_18_98_holds_three_quarter_inch_walls():
    from caliper.evaluate import evaluate_assertion

    expr = promote.allow_for_measuring("min_wall >= 19.05")
    assert expr == "min_wall >= 19.05 - 0.15"
    assert evaluate_assertion(Assertion(id="w", expr=expr), {"min_wall": 18.98}).status == "pass"
    assert evaluate_assertion(Assertion(id="w", expr="min_wall >= 19.05"), {"min_wall": 18.98}).status == "fail"
    # a real miss is still a miss
    assert evaluate_assertion(Assertion(id="w", expr=expr), {"min_wall": 15.88}).status == "fail"


def test_only_measured_sizes_are_allowed_for():
    a = promote.allow_for_measuring
    assert a("bbox.dz <= 228.6") == "bbox.dz <= 228.6 + 0.1"
    assert a("bbox(stool).dx == 406.4") == "406.4 - 0.1 <= bbox(stool).dx <= 406.4 + 0.1"
    for same in ("min_clearance(a, b) >= 2.0", "body_count == 1", "220 <= bbox.dz <= 235", "is_watertight"):
        assert a(same) == same
    # and a rule with the allowance still reads as a bound, so contradictions are still caught
    assert promote._bounds("min_wall >= 19.05 - 0.15") == ("min_wall", pytest.approx(18.9), float("inf"))


def test_a_drafted_wall_rule_carries_the_allowance_and_says_so(gantry):
    got = promote.offline_draft(gantry, "carriage", "walls at least 9.95 mm")
    p = got.proposal
    assert p.expr == "min_wall >= 9.95 - 0.15" and p.holds_now          # a 10 mm block
    assert "what measuring it can be off by" in p.describe()
