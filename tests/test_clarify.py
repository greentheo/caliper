"""CALI-33 — the clarify round: bounded questions, answers become permanent requirements."""

import json

import pytest

from caliper import clarify
from caliper.clarify import Question
from caliper.design import DesignStore


@pytest.fixture
def store(tmp_path):
    return DesignStore.create("a hitch cargo box, 74in wide", base=str(tmp_path / "designs"))


class _StubClient:
    def __init__(self, text):
        self._text = text
        self.messages = self

    def create(self, **kw):
        blk = type("B", (), {"type": "text", "text": self._text})
        return type("M", (), {"content": [blk]})()


def test_inches_are_recognised_in_the_way_people_write_them():
    assert clarify.speaks_inches('74" wide and 41" high')
    assert clarify.speaks_inches("about 18 in from the car")
    assert clarify.speaks_inches("a 2 inch tube")
    assert not clarify.speaks_inches("a 60 mm bracket with four M5 holes")
    assert not clarify.speaks_inches("put it in the box")       # "in" the word, not the unit


def test_offline_questions_are_bounded_and_carry_defaults():
    qs = clarify.offline_questions("a bracket")
    assert 1 <= len(qs) <= clarify.MAX_QUESTIONS
    assert all(q.default for q in qs)
    assert any(q.id == "size" for q in qs)                         # no numbers given → ask size


def test_offline_does_not_ask_for_a_size_that_was_given():
    assert all(q.id != "size" for q in clarify.offline_questions("a 60 mm bracket"))


def test_llm_questions_are_parsed_capped_and_given_safe_ids():
    many = [{"id": f"Q {i}!", "question": f"question {i}?", "why": "w", "default": "d"}
            for i in range(9)]
    qs = clarify.llm_questions("a box", client=_StubClient("here:\n" + json.dumps(many)))
    assert len(qs) == clarify.MAX_QUESTIONS
    assert qs[0].id == "q_0" and qs[0].default == "d"


def test_llm_ids_are_kept_unique():
    dup = [{"id": "height", "question": "a?"}, {"id": "height", "question": "b?"}]
    qs = clarify.llm_questions("x", client=_StubClient(json.dumps(dup)))
    assert len({q.id for q in qs}) == 2


def test_a_misbehaving_llm_falls_back_to_the_offline_floor(capsys):
    qs, source = clarify.draft_questions("a bracket", client=_StubClient("no json here"))
    assert source == "offline" and qs
    assert "LLM questions failed" in capsys.readouterr().err


def test_an_injected_asker_wins():
    qs, source = clarify.draft_questions("x", asker=lambda p: [Question("a", "A?")])
    assert source == "injected" and [q.id for q in qs] == ["a"]


def test_questions_park_and_survive_a_reload(store):
    clarify.open_round(store, [Question("h", "Receiver height?", default="16 in")], "llm")
    assert [q.question for q in clarify.pending(DesignStore.load(store.root))] == ["Receiver height?"]
    assert store.log()[-1]["action"] == "asked"


def test_answers_become_requirements_and_blanks_become_labelled_assumptions(store):
    clarify.open_round(store, [Question("h", "Receiver height?", default="16 in"),
                               Question("c", "Receiver class?", default="Class III")])
    clarify.answer_round(store, {"h": "17 in", "c": "  "})
    reqs = {r.question: (r.answer, r.source) for r in store.design.requirements}
    assert reqs["Receiver height?"] == ("17 in", "answered")
    assert reqs["Receiver class?"] == ("Class III", "assumed")
    assert clarify.pending(store) == []                            # asked once — never again


def test_just_build_it_assumes_every_default(store):
    clarify.open_round(store, [Question("h", "Receiver height?", default="16 in")])
    clarify.answer_round(store, {"h": "this is ignored"}, skip=True)
    assert [(r.answer, r.source) for r in store.design.requirements] == [("16 in", "assumed")]
    assert store.log()[-1]["action"] == "skipped"


def test_the_answers_reach_every_later_revision(store):
    clarify.open_round(store, [Question("h", "Receiver height?", default="16 in")])
    clarify.answer_round(store, {"h": "17 in"})
    assert "Receiver height? -> 17 in" in store.prompt_context()


def test_a_corrupt_parking_file_does_not_wedge_the_design(store):
    open(clarify._path(store), "w").write("{nope")
    assert clarify.pending(store) == []
