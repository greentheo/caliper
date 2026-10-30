"""CALI-55 (#2) — what a design is held to, written from the conversation."""

import json
import os

import pytest
import yaml

from caliper import chat, goals, load_study, scorecard
from caliper.design import DesignStore

BOX = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box(400, 250, 230)\n")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("A step stool so my kid can reach the sink. It has to hold me too (200 lb).",
                           base=str(tmp_path / "designs"))
    s.write_part("stool", BOX, intent="a step stool")
    return s


class _Claude:
    """A stand-in that answers with a fixed list of checks, and records what it was shown."""

    def __init__(self, checks):
        self.checks, self.seen = checks, []
        self.messages = self

    def create(self, **kw):
        self.seen.append(kw)
        text = json.dumps({"checks": self.checks, "objectives": []})
        return type("M", (), {"content": [type("B", (), {"type": "text", "text": text})()]})()


def test_offline_a_load_in_the_goal_becomes_a_strength_check(store):
    got = goals.update(store, "make it a bit taller", use_llm=False)
    data = yaml.safe_load(open(goals.path(store)))
    assert data["written_by"] == "caliper"
    (c,) = data["checks"]
    assert (c["metric"], c["op"], c["limit"], c["source"]) == ("strength.safety", ">=", 2.0, "assumed")
    assert "200 lb" in c["quote"] and got["added"] == [c]
    # said again, nothing new
    assert goals.update(store, "it has to hold me", use_llm=False) == {"added": [], "changed": [], "proposed": []}


def test_a_goals_file_written_by_hand_is_never_rewritten(store):
    with open(goals.path(store), "w") as f:
        f.write("# mine\nchecks:\n  - {id: light, metric: weight.total_lb, op: '<=', limit: 10}\n")
    assert goals.update(store, "it has to hold 300 lb", use_llm=False) is None
    assert open(goals.path(store)).read().startswith("# mine")
    with pytest.raises(ValueError, match="by hand"):
        goals.decide(store, "light", True)


def test_claude_writes_stated_assumed_and_proposed_checks_and_the_person_decides(store):
    claude = _Claude([
        {"id": "holds_dad", "label": "holds Dad (200 lb) at 2x", "metric": "strength.safety", "op": ">=",
         "limit": 2, "source": "assumed", "quote": "It has to hold me too (200 lb)"},
        {"id": "under_50", "label": "under $50", "metric": "cost.usd", "op": "<=", "limit": 50,
         "source": "stated", "quote": "keep it under $50"},
        {"id": "kid_carries", "label": "light enough for a 6-year-old to carry (10 lb)", "metric": "weight.total_lb",
         "op": "<=", "limit": 10, "source": "proposed", "why": "your kid will move it to the sink and back"},
        {"id": "bogus", "label": "x", "metric": "not.a.metric", "op": ">=", "limit": 1, "source": "stated"},
    ])
    got = goals.update(store, "keep it under $50", client=claude)
    shown = claude.seen[0]["messages"][0]["content"]
    assert "It has to hold me too (200 lb)" in shown and "strength.safety" in shown and "keep it under $50" in shown
    ids = [c["id"] for c in goals.read(store)["checks"]]
    assert ids == ["holds_dad", "under_50", "kid_carries"]                  # an unknown metric is dropped
    assert [c["id"] for c in got["proposed"]] == ["kid_carries"]
    reply = goals.reply(got)
    assert "Now on the scorecard" in reply and "under $50" in reply and "I'd also check" in reply

    goals.decide(store, "under_50", True)
    goals.decide(store, "kid_carries", False)
    data = goals.read(store)
    assert {c["id"]: c["source"] for c in data["checks"]} == {"holds_dad": "assumed", "under_50": "confirmed"}
    assert data["declined"] == ["kid_carries"]
    # Claude proposes it again and says the kept one is only assumed: the drop and the keep both stand
    claude.checks[1]["source"] = "assumed"
    goals.update(store, "make it 10 in tall", client=claude)
    data = goals.read(store)
    assert "kid_carries" not in [c["id"] for c in data["checks"]]
    assert next(c for c in data["checks"] if c["id"] == "under_50")["source"] == "confirmed"


def test_a_proposed_check_is_shown_but_doesnt_count_until_its_kept(store):
    pytest.importorskip("cadquery")
    goals.write(store, {"checks": [
        {"id": "holds", "label": "holds 200 lb at 2x", "metric": "strength.safety", "op": ">=", "limit": 2,
         "source": "assumed"},
        {"id": "light", "label": "under 1 lb", "metric": "strength.safety", "op": "<=", "limit": 1,
         "source": "proposed"}]})
    # the part says what it must hold, and its strength check on this version says 3.1x
    store.write_part("stool", BOX + "\n\ndef loads(params, build=None):\n    return []\n", intent="a step stool")
    run = os.path.join(load_study.runs_dir(store), "20261030-000000-test")
    os.makedirs(run)
    with open(os.path.join(run, "run.json"), "w") as f:
        json.dump({"id": "x", "part": "stool", "version": 2, "created": 1.0, "safety": 3.1,
                   "cases": [{"name": "Dad", "safety": 3.1, "breaks_lb": 1240}]}, f)
    card = scorecard.compute(store)
    by = {c["id"]: c for c in card["checks"]}
    assert by["holds"]["status"] == "pass" and by["holds"]["value"] == 3.1
    assert by["light"]["status"] == "proposed"
    assert card["summary"]["proposed"] == 1 and card["summary"]["fail"] == 0
    assert card["metrics"]["strength.breaks_lb"]["value"] == 1240


def test_a_turn_that_says_what_it_must_do_updates_the_checks(store):
    res = chat.turn(store, "what's it made of? it has to hold 250 lb", use_llm=False)
    assert "Now on the scorecard" in res.reply
    assert goals.read(store)["checks"][0]["metric"] == "strength.safety"
    # a turn that doesn't is left alone
    before = open(goals.path(store)).read()
    chat.turn(store, "what parts exist?", use_llm=False)
    assert open(goals.path(store)).read() == before
