"""CALI-29 — the chat turn handler: a message (+ optional scope) becomes a measured move.

Routing, logging and the honest-refusal paths are network- and OCCT-free. The tests that prove the
thing CALI-29 exists for — **refining a part that lives inside an assembly**, and **naming what the
change broke elsewhere in the design** — build real geometry and are gated on cadquery.
"""

import pytest

from caliper import chat
from caliper.assembly import Mate
from caliper.design import DesignStore
from caliper.spec import Assertion, Spec

BOX = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box({dx}, {dy}, 10).translate(({x}, {y}, 0))\n")


def _box(dx=40, dy=20, x=0, y=0):
    return BOX.format(dx=dx, dy=dy, x=x, y=y)


def _author(script):
    """An injected author: the LLM call, replaced by a fixed script."""
    return lambda spec, feedback, prior: script


@pytest.fixture
def store(tmp_path):
    return DesignStore.create("a 3D printer gantry", base=str(tmp_path / "designs"))


@pytest.fixture
def gantry(store):
    """A rail and a carriage beside it, with a mate asserting they don't collide."""
    store.write_part("rail", _box(dx=200, dy=12), intent="the linear rail")
    store.write_part("carriage", _box(dx=40, dy=20, y=40), intent="the X carriage")
    store.assembly.mates.append(Mate(id="carriage_misses_rail", between=["carriage", "rail"],
                                     kind="no_interference"))
    store.save()
    return store


# --- scope is the selection ------------------------------------------------
def test_scoped_message_refines_the_clicked_part(gantry):
    got = chat.offline_classify(gantry, "make it 5mm wider", scope="carriage")
    assert (got.action, got.part) == ("refine", "carriage")


def test_unscoped_message_that_names_a_part_refines_it(gantry):
    got = chat.offline_classify(gantry, "make the carriage 5mm wider")
    assert (got.action, got.part) == ("refine", "carriage")


def test_longest_part_name_wins(store):
    store.write_part("bar", _box(), intent="a bar")
    store.write_part("bar_v", _box(), intent="the vertical bar")
    assert chat.offline_classify(store, "make the bar_v taller").part == "bar_v"


def test_add_a_part_authors_a_new_one(gantry):
    got = chat.offline_classify(gantry, "add a belt tensioner")
    assert got.action == "author" and got.part == "belt_tensioner"
    assert got.intent == "add a belt tensioner"


def test_the_first_part_of_an_empty_design_needs_no_ceremony(store):
    got = chat.offline_classify(store, "a 2040 extrusion beam 400mm long")
    assert got.action == "author" and got.part


def test_questions_answer_rather_than_change_geometry(gantry):
    assert chat.offline_classify(gantry, "how wide is the carriage?").action == "answer"
    assert chat.offline_classify(gantry, "what parts exist").action == "answer"
    # even when scoped — a question about a part is still a question
    assert chat.offline_classify(gantry, "is it watertight?", scope="carriage").action == "answer"


def test_ambiguous_message_asks_instead_of_guessing(gantry):
    """A wrong guess spends a whole authoring run — so don't guess."""
    got = chat.offline_classify(gantry, "5mm wider please")
    assert got.action == "answer" and got.note.startswith("ambiguous")
    result = chat.answer(gantry, "5mm wider please", note=got.note)
    assert "click it in the viewer or name it" in result.reply


# --- LLM routing, with a fallback that can't hard-fail ---------------------
class _StubClient:
    def __init__(self, text):
        self._text = text
        self.messages = self

    def create(self, **kw):
        class _B:
            type, text = "text", self._text
        _B.text = self._text
        return type("M", (), {"content": [_B]})()


def test_llm_routing_parses_json_and_validates_the_target(gantry):
    client = _StubClient('{"action": "refine", "part": "carriage", "intent": ""}')
    got = chat.llm_classify(gantry, "widen the thing that rides the rail", client=client)
    assert (got.action, got.part, got.source) == ("refine", "carriage", "llm")


def test_llm_routing_to_an_unknown_part_is_rejected(gantry):
    client = _StubClient('{"action": "refine", "part": "flux_capacitor"}')
    with pytest.raises(ValueError):
        chat.llm_classify(gantry, "widen it", client=client)


def test_classify_falls_back_to_offline_when_the_llm_misbehaves(gantry, capsys):
    got = chat.classify(gantry, "make the carriage wider", client=_StubClient("not json at all"))
    assert (got.action, got.part, got.source) == ("refine", "carriage", "offline")
    assert "LLM routing failed" in capsys.readouterr().err


def test_an_injected_classifier_wins(gantry):
    fixed = chat.Intent(action="answer", note="stubbed")
    assert chat.classify(gantry, "anything", classifier=lambda *a: fixed).action == "answer"


# --- honest refusals -------------------------------------------------------
def test_refining_an_unknown_part_says_so(store):
    res = chat.refine_part(store, "nope", "wider")
    assert res.action == "error" and not res.ok
    assert "no part called 'nope'" in res.reply


def test_refining_imported_geometry_is_refused_honestly(store, tmp_path):
    run = tmp_path / "run_0001"
    run.mkdir()
    (run / "part.stl").write_text("solid x\nendsolid x\n")
    store.adopt_run(str(run), "legacy")
    res = chat.refine_part(store, "legacy", "make it wider")
    assert not res.ok and "no script behind it to revise" in res.reply


# --- the conversation is recorded -----------------------------------------
def test_the_turn_logs_both_the_message_and_the_reply(gantry):
    chat.turn(gantry, "what parts exist?", use_llm=False)
    kinds = [e["kind"] for e in gantry.log()]
    assert kinds[-2:] == ["message", "reply"]
    msg = [e for e in gantry.log() if e["kind"] == "message"][-1]
    assert msg["text"] == "what parts exist?" and msg["action"] == "answer"


def test_answer_reports_the_measured_state_without_touching_geometry(gantry):
    before = [p.version for p in gantry.design.parts]
    res = chat.turn(gantry, "what's in this design?", use_llm=False)
    assert res.action == "answer"
    assert "rail" in res.reply and "carriage" in res.reply
    assert [p.version for p in gantry.design.parts] == before


def test_events_narrate_the_turn(gantry):
    seen = []
    chat.turn(gantry, "what parts exist?", use_llm=False, on_event=seen.append)
    assert [e.kind for e in seen] == ["classified", "done"]


# --- the gap CALI-29 closes: refine a part INSIDE an assembly -------------
def test_refine_a_part_inside_an_assembly_rebuilds_and_remeasures(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "make it 60mm wide", scope="carriage", use_llm=False,
                    author=_author(_box(dx=60, dy=20, y=40)), max_rounds=2)
    assert res.action == "refine" and res.ok
    assert (res.part, res.version) == ("carriage", 2)
    assert "60" in gantry.read_script("carriage")          # the real script changed
    assert res.report is not None and res.report.all_pass  # the WHOLE design was re-measured
    assert gantry.history("carriage")[-1]["feedback"] == "make it 60mm wide"


def test_a_change_that_breaks_another_part_is_named_in_the_same_turn(gantry):
    """Widening the carriage into the rail must be reported, not silently accepted."""
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "make it much deeper", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=120, y=40)), max_rounds=2)
    assert res.broke == ["carriage_misses_rail"]
    assert not res.ok                                       # the part passes; the DESIGN does not
    assert "broke 1 design check" in res.reply
    assert "carriage_misses_rail" in res.reply
    assert "roll it back" in res.reply                      # and it offers the way out


def test_fixing_the_break_is_reported_too(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "make it much deeper", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=120, y=40)), max_rounds=2)
    res = chat.turn(gantry, "pull it back off the rail", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=20, y=40)), max_rounds=2)
    assert res.fixed == ["carriage_misses_rail"] and res.ok
    assert "still measures green" in res.reply


def test_a_revision_that_never_builds_leaves_the_part_alone(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "make it wider", scope="carriage", use_llm=False,
                    author=_author("def build(params):\n    raise RuntimeError('boom')\n"),
                    max_rounds=2)
    assert not res.ok and res.action == "refine"
    assert "couldn't get 'carriage' to build" in res.reply and "unchanged" in res.reply
    assert gantry.design.part("carriage").version == 1      # nothing was written
    assert "40" in gantry.read_script("carriage")


# --- authoring a new part into the design ---------------------------------
def test_authoring_adds_a_part_and_measures_the_design_with_it(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "add a motor mount", use_llm=False,
                    author=_author(_box(dx=30, dy=30, y=-60)), max_rounds=2)
    assert res.action == "author" and res.part == "motor_mount" and res.ok
    assert [p.id for p in gantry.assembly.parts] == ["rail", "carriage", "motor_mount"]
    assert res.report.all_pass
    # a new part gets the baseline contract so the author loop has something to pass
    assert [a.id for a in gantry.read_spec("motor_mount").assertions] == ["one_body", "watertight"]


def test_the_stored_spec_does_not_absorb_the_prompt_context(gantry):
    """`refine_authored` folds the instruction into spec.intent; that must not leak into spec.yaml."""
    pytest.importorskip("cadquery")
    chat.turn(gantry, "add a motor mount", use_llm=False,
              author=_author(_box(dx=30, dy=30, y=-60)), max_rounds=2)
    stored = gantry.read_spec("motor_mount")
    assert stored.intent == "add a motor mount"
    assert "design context" not in stored.intent


def test_a_new_part_that_never_builds_is_not_added(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "add a motor mount", use_llm=False,
                    author=_author("def build(params):\n    raise RuntimeError('boom')\n"),
                    max_rounds=2)
    assert not res.ok and "Nothing was added" in res.reply
    assert [p.id for p in gantry.design.parts] == ["rail", "carriage"]


# --- context reaches the author -------------------------------------------
def test_the_revision_sees_the_design_context(gantry):
    pytest.importorskip("cadquery")
    seen = {}

    def author(spec, feedback, prior):
        seen["intent"] = spec.intent
        seen["prior"] = prior
        return _box(dx=60, dy=20, y=40)

    chat.turn(gantry, "make it 60mm wide", scope="carriage", use_llm=False, author=author,
              max_rounds=2)
    assert "carriage_misses_rail" in seen["intent"]      # knows what must keep holding
    assert "the linear rail" in seen["intent"]           # knows what else exists
    assert "WORLD COORDINATES" in seen["intent"]         # knows the frame it must build in
    assert seen["prior"] and "40" in seen["prior"]       # edits the real part, not from scratch


def test_enforced_assertions_reach_the_author(gantry):
    pytest.importorskip("cadquery")
    spec = Spec(part="carriage", intent="the X carriage",
                assertions=[Assertion(id="fits_frame", expr="bbox.dx <= 80")])
    gantry.write_spec("carriage", spec)
    seen = {}

    def author(s, feedback, prior):
        seen["intent"] = s.intent
        return _box(dx=60, dy=20, y=40)

    chat.turn(gantry, "widen it", scope="carriage", use_llm=False, author=author, max_rounds=2)
    assert "fits_frame: bbox.dx <= 80" in seen["intent"]


# --- revert: the rollback the reply offers has to be real -----------------
def test_roll_it_back_is_routed_as_a_revert(gantry):
    assert chat.offline_classify(gantry, "roll it back", scope="carriage").action == "revert"
    assert chat.offline_classify(gantry, "undo that").action == "revert"
    # unscoped undo means the part we just touched
    assert chat.offline_classify(gantry, "undo that").part in {"rail", "carriage"}
    # but a question about reverting is still a question
    assert chat.offline_classify(gantry, "can I undo that?").action == "answer"


def test_revert_undoes_the_change_and_re_measures(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "make it much deeper", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=120, y=40)), max_rounds=2)
    assert not gantry.evaluate().all_pass

    res = chat.turn(gantry, "roll it back", scope="carriage", use_llm=False)
    assert res.action == "revert" and res.ok
    assert res.fixed == ["carriage_misses_rail"]
    assert "rolled **carriage** back to v1" in res.reply
    assert gantry.evaluate().all_pass


def test_revert_is_itself_a_revision_not_a_hole_in_the_history(gantry):
    pytest.importorskip("cadquery")
    chat.turn(gantry, "deeper", scope="carriage", use_llm=False,
              author=_author(_box(dx=40, dy=120, y=40)), max_rounds=2)
    chat.turn(gantry, "roll it back", scope="carriage", use_llm=False)
    assert gantry.versions("carriage") == [1, 2, 3]
    assert gantry.history("carriage")[-1]["restored_from"] == 1


def test_nothing_to_roll_back_to_says_so(gantry):
    res = chat.turn(gantry, "undo that", scope="carriage", use_llm=False)
    assert not res.ok and "nothing to roll back to" in res.reply


def test_the_break_reply_offers_a_verb_that_exists(gantry):
    pytest.importorskip("cadquery")
    res = chat.turn(gantry, "make it much deeper", scope="carriage", use_llm=False,
                    author=_author(_box(dx=40, dy=120, y=40)), max_rounds=2)
    assert "roll it back" in res.reply
    follow_up = chat.offline_classify(gantry, "roll it back", scope="carriage")
    assert follow_up.action == "revert"
