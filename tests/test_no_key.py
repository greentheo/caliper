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



# --- #372 review (reviewer-3) -----------------------------------------------------------------------------------------
from .test_chat import _box  # noqa: E402


@pytest.fixture
def two(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("side_left", _box(dx=20, dy=300, x=0), intent="the left side")
    s.write_part("side_right", _box(dx=20, dy=300, x=300), intent="the right side")
    return s


def test_a_stop_partway_through_several_parts_says_what_changed_first(two):
    """reviewer-3: the left side moved to v2, then Claude was cut off on the right; the reply said only "cut off"."""
    right = two.read_script("side_right")

    def author(spec, feedback, prior):
        if prior == right:
            raise llm.CutOff("Claude's reply was cut off at 8000 tokens, before it finished")
        return _box(dx=20, dy=300, x=0).replace("10)", "60)")
    res = chat.turn(two, "make both sides taller", use_llm=False, author=author)
    first = res.reply.splitlines()[0]
    assert first == ("! Changed side_left (now v2); then side_right stopped: Claude's reply was cut off at 8000 tokens, "
                     "before it finished."), res.reply
    assert not res.ok and two.design.part("side_left").version == 2 and two.design.part("side_right").version == 1


def test_a_stop_on_the_first_of_several_parts_is_said_alone(two):
    res = chat.turn(two, "make both sides taller")              # no key: the first designer call stops
    assert res.reply == SAID and not res.ok


def test_whatever_moved_before_a_stop_is_said_with_its_version(stool, monkeypatch):
    """Any path: the turn compares versions, so a revision that landed is never hidden behind the stop's words."""
    def landed_then_stopped(store, pid, message, **kw):
        store.write_part(pid, BOX.format(h=300), intent="a step stool")
        raise llm.Declined("Claude declined to answer this one")
    monkeypatch.setattr(chat, "refine_part", landed_then_stopped)
    res = chat.turn(stool, "make it 2 in taller", scope="stool")
    assert res.reply == "stool is now v2. Then: Claude declined to answer this one.", res.reply


def test_the_message_is_logged_once(stool):
    chat.turn(stool, "make it 2 in thicker", scope="stool")
    assert [r["kind"] for r in stool.log()].count("message") == 1


def test_with_no_key_the_classic_draft_and_refine_go_offline_as_before(monkeypatch):
    """The foreman's call: where main fell back to the offline draft, it still does, and the CLI says why."""
    from caliper import intake, refine

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    got = intake.draft_spec("an L bracket, 60 mm, four M5 holes")
    assert got.source == "offline"
    assert refine.apply_refinement(got.spec, "make it 80 mm").source == "offline"


def test_the_cli_says_the_offline_fallback(monkeypatch, capsys):
    """cli.py's hint, written for this fallback, fires again (#372 review: it couldn't)."""
    import types

    from caliper import cli
    from caliper.spec import Spec

    class _Stop(Exception):
        pass

    def stop(self):                              # the run stops at the draft: nothing is built
        raise _Stop()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(Spec, "to_yaml", stop)
    with pytest.raises(_Stop):
        cli._cmd_run(types.SimpleNamespace(intent="an L bracket, 60 mm, four M5 holes", machine=None, no_llm=False,
                                           yes=True, out=None))
    out = capsys.readouterr().out
    assert "── draft spec (offline) ──" in out and "LLM path unavailable — used offline. Set ANTHROPIC_API_KEY" in out


def test_an_auth_token_counts_as_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token-not-real")
    assert llm.client() is not None


def test_api_gen_with_no_key_is_a_422_said_once(monkeypatch):
    """#372 re-check: /api/gen answered 503, "authoring needs the Claude API: That needs Claude…", the words doubled."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    got = TestClient(create_app()).post("/api/gen", json={"intent": "an L bracket, 60 mm, four M5 holes"})
    assert got.status_code == 422 and got.json()["detail"] == llm.NO_KEY, got.json()


def test_every_gate_asks_the_one_has_a_key_check(monkeypatch):
    """#372 re-check: the client took ANTHROPIC_AUTH_TOKEN, but the page's gate and the routing asked for the API key."""
    from caliper import design_api, firstrun

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token-not-real")
    assert llm.has_key() and design_api._claude() and firstrun._llm(True, None)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN")
    assert not (llm.has_key() or design_api._claude() or firstrun._llm(True, None))
    here = os.path.join(os.path.dirname(chat.__file__), "*.py")
    asks = {os.path.basename(f) for f in glob.glob(here) if re.search(r'environ\.get\("ANTHROPIC_(API_KEY|AUTH_TOKEN)"\)',
                                                                       open(f).read())}
    assert asks == {"llm.py"}, asks


def test_review_it_with_no_key_says_so_and_keeps_nothing(stool):
    """#368 merged before #372: its one Claude call goes through llm.client(), and no key is its reply, not a crash."""
    from caliper import assess

    got = assess.run(stool)
    assert got == {"ok": False, "readings": [], "said": f"No reading: {llm.NO_KEY}"} and assess.count(stool) == 0
