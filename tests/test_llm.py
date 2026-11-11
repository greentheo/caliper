"""CALI-157 (#223), part 1 — Opus 5.5 from one constant, and every request as that model needs it. No live call: a fake client records each."""

import os
import re
from types import SimpleNamespace as NS

import pytest

from caliper import authoring, chat, llm, plan
from caliper.design import DesignStore
from caliper.spec import Spec

SRC = os.path.dirname(llm.__file__)


def _text(text, stop="end_turn", **kw):
    return NS(content=[NS(type="thinking", thinking=""), NS(type="text", text=text)], stop_reason=stop, usage=None, **kw)


class Client:
    """The API's shape, enough of it; ``beta=True`` adds the beta namespace a real client has."""

    def __init__(self, reply=None, beta=False, streams=False):
        self.calls, self.streamed = [], []
        make = lambda **kw: (self.calls.append(kw), reply or _text("{}"))[1]            # noqa: E731
        ns = _Streams(make, self.streamed, reply or _text("{}")) if streams else NS(create=make)
        self.messages = ns
        if beta:
            self.beta = NS(messages=ns)


class _Streams:
    def __init__(self, create, seen, final):
        self.create, self.seen, self.final = create, seen, final

    def stream(self, **kw):
        self.seen.append(kw)
        final = self.final

        class Running:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return final

        return Running()


def _sources():
    for name in sorted(os.listdir(SRC)):
        if name.endswith(".py"):
            with open(os.path.join(SRC, name)) as f:
                yield name, f.read()


def test_one_constant_and_one_door():
    assert llm.DEFAULT_MODEL == "claude-opus-5-5"
    for name, text in _sources():
        if name == "llm.py":
            continue
        assert not re.search(r"claude-(opus|sonnet|haiku|fable)-\d", re.sub(r"#.*", "", text)), name
        assert "DEFAULT_MODEL =" not in text, name
        assert ".messages.create(" not in text and ".messages.stream(" not in text, name


def test_nothing_sends_what_opus_5_5_refuses():
    for name, text in _sources():
        code = re.sub(r"#.*", "", text)
        for word in ("tool_choice", "budget_tokens", "temperature=", "top_p=", "top_k=", '"thinking":'):
            assert word not in code, (name, word)


def test_caliper_model_overrides_and_is_read_when_asked(monkeypatch):
    monkeypatch.setenv("CALIPER_MODEL", "claude-sonnet-4-6")
    c = Client()
    llm.ask(c, max_tokens=10, effort="low", messages=[])
    assert c.calls[0]["model"] == "claude-sonnet-4-6"
    monkeypatch.delenv("CALIPER_MODEL")
    assert llm.model_name() == "claude-opus-5-5" and llm.model_name("claude-x") == "claude-x"


def test_effort_goes_in_output_config(monkeypatch):
    monkeypatch.delenv("CALIPER_MODEL", raising=False)
    c = Client()
    llm.ask(c, max_tokens=10, effort="high", messages=[])
    assert c.calls[0]["output_config"] == {"effort": "high"}
    c = Client()
    llm.ask(c, max_tokens=10, effort="high", messages=[], model="claude-haiku-4-5")
    assert "output_config" not in c.calls[0]


def test_a_refusal_is_said_in_words_before_the_content_is_read():
    msg = NS(content=[], stop_reason="refusal", stop_details=NS(category="cyber"), usage=None)
    with pytest.raises(llm.Declined, match=r"safety checks stopped this request \(cyber\)"):
        llm.ask(Client(msg), max_tokens=10, effort="low", messages=[])


def test_a_reply_cut_off_is_a_failure_unless_the_caller_reads_it():
    cut = _text("{", stop="max_tokens")
    with pytest.raises(llm.CutOff, match="cut off at 10 tokens"):
        llm.ask(Client(cut), max_tokens=10, effort="low", messages=[])
    assert llm.ask(Client(cut), max_tokens=10, effort="low", messages=[], cut_off_ok=True) is cut


def test_fallbacks_go_by_the_beta_on_a_model_that_has_them(monkeypatch):
    monkeypatch.delenv("CALIPER_MODEL", raising=False)
    c = Client(beta=True)
    llm.ask(c, max_tokens=10, effort="low", messages=[])
    assert c.calls[0]["betas"] == ["server-side-fallback-2026-07-01"] and c.calls[0]["fallbacks"] == "default"
    c = Client(beta=True)
    llm.ask(c, max_tokens=10, effort="low", messages=[], model="claude-sonnet-4-6")
    assert "fallbacks" not in c.calls[0] and "betas" not in c.calls[0]


def _spec():
    return Spec(part="block", intent="a block")


CODE = "```python\ndef build(params):\n    pass\n```"


def test_authoring_works_hard_caches_its_prompt_and_streams(monkeypatch):
    monkeypatch.delenv("CALIPER_MODEL", raising=False)
    c = Client(_text(CODE), streams=True)
    authoring.author_script(_spec(), client=c)
    (kw,) = c.streamed
    assert kw["output_config"] == {"effort": "high"} and kw["max_tokens"] >= 32000
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and kw["system"][0]["text"] == authoring.system_prompt()


def test_authoring_still_turns_a_cut_off_script_into_feedback():
    code = authoring.author_script(_spec(), client=Client(_text(CODE, stop="max_tokens")))
    assert "this script was cut off" in code


def test_a_refusal_while_authoring_ends_the_rounds_in_words():
    msg = NS(content=[], stop_reason="refusal", stop_details=NS(category=None), usage=None)
    got = authoring.improve(_spec(), client=Client(msg))
    assert not got.ok and "safety checks stopped" in got.error and got.rounds == 1


def _store(tmp_path):
    return DesignStore.create("a stool", base=str(tmp_path))


@pytest.mark.parametrize("call, effort, least", [
    (lambda s, c: chat.llm_classify(s, "make it taller", client=c), "low", 2000),
    (lambda s, c: chat.redescribe("a stool", "taller", "x", client=c), "low", 2000),
])
def test_routing_and_short_descriptions_have_room_to_think(tmp_path, call, effort, least, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    c = Client(_text('{"action": "answer"}'))
    try:
        call(_store(tmp_path), c)
    except Exception:  # noqa: BLE001 — only the request is under test
        pass
    assert c.calls and c.calls[0]["output_config"]["effort"] == effort and c.calls[0]["max_tokens"] >= least


def test_the_planner_is_asked_not_forced():
    c = Client(NS(content=[], stop_reason="end_turn", usage=None))
    with pytest.raises(plan.PlanError):
        plan._ask(c, None, "a stool", "")
    assert "tool_choice" not in c.calls[0] and c.calls[0]["output_config"]["effort"] == "high" and c.calls[0]["max_tokens"] >= 16000
    assert "plan tool" in c.calls[0]["messages"][0]["content"]


def test_the_rest_are_set_for_thinking_inside_max_tokens():
    text = dict(_sources())
    for name, least in (("clarify.py", 4000), ("goals.py", 8000), ("intake.py", 8000), ("pictures.py", 8000), ("refine.py", 8000)):
        got = [int(x) for x in re.findall(r"max_tokens=(\d+)", text[name])]
        assert got and min(got) >= least, name
