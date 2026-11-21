"""CALI-217 (#366) — with no Claude key, a change asked in the chat says it needs Claude and where to set the key, never
"Something went wrong".

Reviewer-3's seat had no ``ANTHROPIC_API_KEY``: "make it 2 in thicker" built an Anthropic client anyway, which failed inside
the request with a TypeError, and the chat job recorded it as a crash with an error id and "report what broke". Now every
client is made through :func:`llm.client`, which says it (:class:`llm.NoKey`) before anything is sent; a chat turn
replies with it, and the job runner says any Claude stop in words, unrecorded. Nothing here calls Claude."""

import glob
import os
import re
import time

import pytest

from caliper import chat, errors, llm
from caliper.design import DesignStore
from caliper.jobs import JobRunner

pytest.importorskip("cadquery")

BOX = ("def build(params):\n    import cadquery as cq\n"
       "    return cq.Workplane('XY').box(400, 250, {h})\n")
SAID = llm.NO_KEY + "."


@pytest.fixture
def stool(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX.format(h=230), intent="a step stool")
    return s


def test_the_words_say_it_needs_claude_and_where_to_set_the_key():
    assert "needs Claude" in llm.NO_KEY and "ANTHROPIC_API_KEY" in llm.NO_KEY and ".env" in llm.NO_KEY
    assert "went wrong" not in llm.NO_KEY and "error" not in llm.NO_KEY


def test_no_key_is_said_before_any_client_is_made(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.NoKey, match="ANTHROPIC_API_KEY"):
        llm.client()
    assert issubclass(llm.NoKey, llm.Stopped)


@pytest.mark.parametrize("message,scope", [("make it 2 in thicker", "stool"), ("make the stool 2 in taller", None),
                                           ("add a shelf under the step", None)])
def test_a_change_asked_with_no_key_says_so_and_changes_nothing(stool, message, scope):
    before = len(errors.recent(100))
    res = chat.turn(stool, message, scope=scope)
    assert res.reply == SAID and not res.ok, res.reply
    assert stool.design.part("stool").version == 1 and [p.id for p in stool.design.parts] == ["stool"]
    assert len(errors.recent(100)) == before                     # no crash recorded: there's nothing to report
    assert stool.log()[-1]["reply"] == SAID


def test_the_paths_that_need_no_claude_still_work_with_no_key(stool):
    stool.write_part("stool", BOX.format(h=280), intent="a step stool")
    res = chat.turn(stool, "undo that", scope="stool")
    assert res.ok and res.action == "revert", res.reply
    assert chat.turn(stool, "how tall is it?", scope="stool").action == "answer"


def test_a_job_that_needs_claude_with_no_key_is_said_and_not_recorded(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    before = len(errors.recent(100))
    job = JobRunner().submit("chat", lambda j: llm.client())
    end = time.time() + 5
    while not job.over and time.time() < end:
        time.sleep(0.01)
    assert job.status == "error" and job.error == llm.NO_KEY
    assert not getattr(job, "error_id", None) and len(errors.recent(100)) == before
    assert job.events[-1]["kind"] == "error" and job.events[-1].get("stopped") is True


def test_every_client_is_made_through_the_one_door():
    """A client made anywhere else is the bug again."""
    here = os.path.join(os.path.dirname(chat.__file__), "*.py")
    made = {os.path.basename(f) for f in glob.glob(here) if re.search(r"\bAnthropic\(\)", open(f).read())}
    assert made == {"llm.py"}, made
