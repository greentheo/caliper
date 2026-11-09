"""CALI-105 (#98) — Caliper's own prompts route to what they mean, a part can be removed and put back, and a repeated
request asks first. From Theo's bar stool on 11/05: "have a go" after a rule that didn't hold authored a new part; a
second cone would have had no way out; the foot flange widened by 1 in twice. Stubbed: no Claude call."""

import os
import re

import pytest

from caliper import awaiting, chat, promote, trash
from caliper.assembly import Mate
from caliper.design import DesignStore

from .test_chat import _author, _box

pytest.importorskip("cadquery")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a gantry", base=str(tmp_path / "designs"))
    s.write_part("rail", _box(dx=200, dy=12), intent="the linear rail")
    s.write_part("carriage", _box(dx=40, dy=20, y=40), intent="the X carriage")
    s.assembly.mates.append(Mate(id="carriage_misses_rail", between=["carriage", "rail"], kind="no_interference"))
    s.save()
    return s


def _never(*a, **k):
    raise AssertionError("routed by what Caliper asked, never by the router")


# --- 1. "have a go" after a rule that doesn't hold ---------------------------------------------------------------------

def _accept_a_failing_rule(store):
    promote.park(store, promote.Proposal(id="carriage_wide", expr="bbox.dx >= 60", level="part", part="carriage",
                                         holds_now=False, why="make it at least 60 wide"))
    got = chat.turn(store, "yes, lock it in", use_llm=False, classifier=_never)
    assert got.action == "accept" and "Tell me to have a go." in got.reply
    return got


@pytest.mark.parametrize("go", ["have a go", "Go ahead", "try it", "yes", "fix it"])
def test_have_a_go_after_a_rule_that_doesn_t_hold_refines_that_part(store, go):
    _accept_a_failing_rule(store)
    seen = {}

    def author(spec, feedback, prior):
        seen["intent"] = spec.intent
        return _box(dx=60, dy=20, y=40)

    got = chat.turn(store, go, use_llm=False, classifier=_never, author=author, max_rounds=2)
    assert got.action == "refine" and got.part == "carriage" and got.ok, got.reply
    assert "carriage_wide" in seen["intent"] and "bbox.dx >= 60" in seen["intent"]
    assert [p.id for p in store.design.parts] == ["rail", "carriage"]                 # never a new part
    (msg,) = [e for e in store.log() if e.get("kind") == "message" and e.get("text") == go]
    assert msg["routed_by"] == "pending"
    assert awaiting.pending(store) is None


def test_anything_else_lets_the_question_lapse(store):
    _accept_a_failing_rule(store)
    got = chat.turn(store, "what's the rail made of?", use_llm=False)
    assert got.action == "answer" and awaiting.pending(store) is None


def test_every_tell_me_to_or_say_in_chat_names_its_routing(store):
    """Each instruction Caliper writes in its replies is routed to what it means: a new one without a row here fails."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "chat.py")).read()
    found = set(re.findall(r"Tell me to ([a-z ]+)", src)) | set(re.findall(r"Say \*\*([a-z ]+)\*\*", src)) \
        | set(re.findall(r'say \\"(put back) ', src))
    routed = {"have a go": "the parked fix_rule (test above)", "roll it back": "revert", "put back": "restore"}
    assert found == set(routed), found
    # the routings themselves: "have a go" is pinned above; "roll it back" reverts; "put back …" restores
    assert chat.offline_classify(store, "roll it back", scope="rail").action == "revert"
    assert awaiting.reads("have a go") is True and awaiting.reads("no, leave it") is False
    assert awaiting.reads("have a go at making it red and twice as tall please") is None    # its own request
    assert chat._RESTORE.match("put back conical_skirt") and chat._RESTORE.match("put the conical skirt back")


# --- 2. a part can be removed, and put back ----------------------------------------------------------------------------

def test_a_part_is_removed_after_asking_once_and_put_back(store):
    script = store.read_script("carriage")
    ask = chat.turn(store, "get rid of the carriage", use_llm=False, classifier=_never)
    assert ask.action == "ask" and ask.reply == "Remove carriage? Its files go to the design's trash, so it can be put back."
    assert store.design.part("carriage") is not None                                  # asked, not done
    gone = chat.turn(store, "yes", use_llm=False, classifier=_never)
    assert gone.action == "remove" and gone.ok
    assert gone.reply.startswith("Removed carriage: its files are in the design's trash, and its mate "
                                 'carriage_misses_rail went with it (say "put back carriage" to restore them all).')
    store = DesignStore.load(store.root)
    assert store.design.part("carriage") is None
    assert [p.id for p in store.assembly.parts] == ["rail"] and store.assembly.mates == []   # its mate went with it
    assert not os.path.exists(store.part_dir("carriage"))
    (t,) = trash.listing(store)
    assert t["part"] == "carriage" and os.path.exists(os.path.join(trash.root(store), t["id"], "part", "part.py"))
    from caliper import answers, design_api

    assert [p["id"] for p in design_api.design_state(store)["parts"]] == ["rail"]      # the cards don't have it
    assert not any("carriage" in str(c) for c in answers.answers(store, design_api.design_state(store)))
    back = chat.turn(store, "put back carriage", use_llm=False, classifier=_never)
    assert back.action == "restore" and back.ok
    store = DesignStore.load(store.root)
    assert store.design.part("carriage").version == 1 and store.read_script("carriage") == script
    assert [m.id for m in store.assembly.mates] == ["carriage_misses_rail"] and trash.listing(store) == []


def test_no_keeps_it_and_a_name_that_isn_t_a_part_isn_t_taken(store):
    chat.turn(store, "remove the rail", use_llm=False, classifier=_never)
    kept = chat.turn(store, "no", use_llm=False, classifier=_never)
    assert kept.reply == "Kept rail." and store.design.part("rail") is not None
    assert chat._remove_or_restore(store, "remove the fillet on the top", None, events=[], on_event=None) is None


def test_a_reference_part_is_removed_the_same_way(store):
    """A fixed reference (a mesh, like the car) has no script and no version to roll back: removed the same way."""
    import trimesh

    store.write_mesh_part("car", trimesh.creation.box(extents=(100, 50, 40)).export(file_type="stl"), origin="imported")
    next(p for p in store.assembly.parts if p.id == "car").role = "fixed"           # a reference, drawn as context
    store.save()
    chat.turn(store, "delete car", use_llm=False, classifier=_never)
    assert chat.turn(store, "ok", use_llm=False, classifier=_never).action == "remove"
    store = DesignStore.load(store.root)
    assert store.design.part("car") is None and [t["part"] for t in trash.listing(store)] == ["car"]
    trash.restore(store, pid="car")                                                  # and it comes back as fixed
    assert next(p for p in DesignStore.load(store.root).assembly.parts if p.id == "car").role == "fixed"


# --- 3. a repeated request asks first ---------------------------------------------------------------------------------

def test_v2_s_instruction_again_on_v2_asks_and_doesn_t_make_v3(store):
    first = chat.turn(store, "make the carriage 10 mm wider", scope="carriage", use_llm=False,
                      author=_author(_box(dx=50, dy=20, y=40)), max_rounds=2)
    assert first.action == "refine" and first.version == 2
    again = chat.turn(store, "make the carriage 10 mm wider", scope="carriage", use_llm=False,
                      author=_author(_box(dx=60, dy=20, y=40)), max_rounds=2)
    assert again.action == "ask" and store.design.part("carriage").version == 2
    assert again.reply.startswith('v2 already did that ("make the carriage 10 mm wider"). Do it again, on top of v2?')
    # the same numbers and direction in other words is the same request
    assert chat._repeats(store, "carriage", "please widen it: 10 mm wider") is not None
    assert chat._repeats(store, "carriage", "make it 10 mm taller") is None
    yes = chat.turn(store, "yes", use_llm=False, author=_author(_box(dx=60, dy=20, y=40)), max_rounds=2,
                    classifier=_never)
    assert yes.action == "refine" and yes.version == 3                                # said yes: done again


# --- beside #151's grain: what Caliper's waiting on is read first, and a grain request isn't an answer to it ------------

@pytest.fixture
def bench(tmp_path):
    from .test_beam_width import TOP

    s = DesignStore.create("a bench", base=str(tmp_path / "designs"))
    s.write_part("bench", TOP, intent="a bench")
    return s


def test_a_grain_request_lets_the_question_lapse_and_still_asks_which_way(bench):
    awaiting.park(bench, "fix_rule", part="bench", rule="wide", expr="bbox.dx >= 1000")
    got = chat.turn(bench, "cut the top with the grain", use_llm=False, classifier=_never)
    assert got.action == "grain" and not got.ok
    assert got.reply == "I couldn't keep that grain: which way: front to back, or side to side?."
    assert awaiting.pending(bench)["kind"] == "grain_way"                       # the rule's question lapsed; this one's parked


def test_have_a_go_still_routes_by_what_s_pending_on_a_design_with_sheets(bench):
    from .test_beam_width import TOP

    awaiting.park(bench, "fix_rule", part="bench", rule="wide", expr="bbox.dx >= 1000")
    got = chat.turn(bench, "have a go", use_llm=False, classifier=_never, author=_author(TOP), max_rounds=1)
    assert got.action == "refine" and got.part == "bench"
    (msg,) = [e for e in bench.log() if e.get("kind") == "message" and e.get("text") == "have a go"]
    assert msg["routed_by"] == "pending"


def test_a_stated_grain_goes_to_the_trash_with_its_part_and_comes_back(bench):
    from caliper import grain

    grain.state(bench, "bench", "top", "along", said="along the span")
    said = grain.stated(bench, "bench")
    trash.remove(bench, "bench")
    bench = DesignStore.load(bench.root)
    assert bench.design.grain == {}
    trash.restore(bench, pid="bench")
    assert grain.stated(DesignStore.load(bench.root), "bench") == said



# --- #153 review: only a bare answer counts; removal covers the plan and says what went; restore never overwrites ------

@pytest.mark.parametrize("said,means", [
    ("yes", True), ("Yes.", True), ("ok", True), ("go ahead", True), ("have a go", True), ("yes please", True),
    ("yes, please", True), ("no", False), ("No!", False), ("no, leave it", False), ("no thanks", False),
    ("yes, but make it taller", None), ("no, make it wider", None), ("ok thanks", None),
    ("keep it but make it wider", None), ("do it with the grain", None),
])
def test_only_a_bare_answer_counts(said, means):
    assert awaiting.reads(said) is means


@pytest.mark.parametrize("said", ["yes, but make it taller", "no, make it wider", "ok thanks"])
def test_a_qualified_answer_removes_nothing_and_goes_on_as_a_request(store, said):
    chat.turn(store, "remove the rail", use_llm=False, classifier=_never)
    got = chat.turn(store, said, use_llm=False, author=_author(_box(dx=200, dy=12)), max_rounds=1)
    assert got.action not in ("remove", "ask") and "Kept rail" not in got.reply
    assert store.design.part("rail") is not None and trash.listing(store) == []
    assert awaiting.pending(store) is None


def test_removal_covers_the_plan_and_says_what_went(store):
    """"Build it again" authors any planned part with no built version: a removed one has to leave the plan."""
    from caliper import plan as P
    from caliper.spec import Assertion

    store.design.plan = {"status": "built", "parts": [{"id": "rail", "what": "the rail"},
                                                      {"id": "carriage", "what": "the carriage", "mounts_on": ["rail"]}],
                         "rules": [{"id": "above", "expr": "bbox(rail).max_z < bbox(carriage).max_z"},
                                   {"id": "short", "expr": "bbox(carriage).max_z < 100"}]}
    store.assembly.assertions.append(Assertion(id="clear", expr="min_clearance(carriage, rail) >= 1"))
    store.save()
    was = store.design.plan
    chat.turn(store, "remove rail", use_llm=False, classifier=_never)
    gone = chat.turn(store, "yes", use_llm=False, classifier=_never)
    assert ("and its rule clear, rule above and mate carriage_misses_rail went with it (say \"put back rail\" to restore "
            "them all).") in gone.reply
    store = DesignStore.load(store.root)
    assert [p["id"] for p in store.design.plan["parts"]] == ["carriage"]
    assert [r["id"] for r in store.design.plan["rules"]] == ["short"] and store.assembly.assertions == []
    assert P.order(P.load(store)) == ["carriage"]                                     # Build it again won't author it
    chat.turn(store, "put back rail", use_llm=False, classifier=_never)
    store = DesignStore.load(store.root)
    assert store.design.plan == was and [a.id for a in store.assembly.assertions] == ["clear"]
    assert [m.id for m in store.assembly.mates] == ["carriage_misses_rail"]


def test_put_back_never_overwrites_a_part_of_that_name(store):
    trash.remove(store, "rail")
    mine = _box(dx=77, dy=12)
    store.write_part("rail", mine, intent="a new rail")
    got = chat.turn(store, "put back rail", use_llm=False, classifier=_never)
    assert got.action == "restore" and not got.ok and "already has a part 'rail'" in got.reply
    assert store.read_script("rail") == mine and store.design.part("rail").version == 1
    assert [t["part"] for t in trash.listing(store)] == ["rail"]                      # still there to put back later


# --- #153: "which way?" is parked too: a bare direction answers it, for that piece, for one turn ------------------------

@pytest.fixture
def checked(bench):
    from .test_grain import _beam, _run_with

    _run_with(bench, _beam(bench))                                                # its span runs front to back
    return bench


@pytest.mark.parametrize("said,grain_is", [("front to back", "along"), ("Side to side.", "across"), ("along", "along"),
                                           ("across", "across"), ("along the span", "along")])
def test_a_bare_direction_answers_which_way_for_that_piece(checked, said, grain_is):
    from caliper import grain

    asked = chat.turn(checked, "cut the top with the grain", use_llm=False, classifier=_never)
    assert asked.reply == "I couldn't keep that grain: which way: front to back, or side to side?."
    got = chat.turn(checked, said, use_llm=False, classifier=_never)
    assert got.action == "grain" and got.ok and got.part == "bench" and got.reply.startswith("Kept: cut the top with its")
    assert grain.stated(checked, "bench")["top"]["grain"] == grain_is
    (msg,) = [e for e in checked.log() if e.get("kind") == "message" and e.get("text") == said]
    assert msg["routed_by"] == "pending" and awaiting.pending(checked) is None


def test_a_direction_and_a_request_isn_t_an_answer(checked):
    from caliper import grain

    from .test_beam_width import TOP

    chat.turn(checked, "cut the top with the grain", use_llm=False, classifier=_never)
    got = chat.turn(checked, "front to back, and make it taller", use_llm=False, author=_author(TOP), max_rounds=1)
    assert got.action != "grain" and grain.stated(checked, "bench") == {}
    assert awaiting.pending(checked) is None


def test_which_way_lasts_one_turn(checked):
    from caliper import grain

    from .test_beam_width import TOP

    chat.turn(checked, "cut the top with the grain", use_llm=False, classifier=_never)
    chat.turn(checked, "what's it made of?", use_llm=False)
    assert awaiting.pending(checked) is None
    got = chat.turn(checked, "front to back", use_llm=False, author=_author(TOP), max_rounds=1)
    assert got.action != "grain" and grain.stated(checked, "bench") == {}


def test_a_direction_with_no_measured_span_says_so(bench):
    from caliper import grain

    chat.turn(bench, "cut the top with the grain", use_llm=False, classifier=_never)
    got = chat.turn(bench, "front to back", use_llm=False, classifier=_never)
    assert got.action == "grain" and not got.ok and "Check it holds first" in got.reply
    assert grain.stated(bench, "bench") == {}
