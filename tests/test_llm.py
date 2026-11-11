"""CALI-157 (#223), part 1 — Opus 5.5 from one constant, and every request as that model needs it. No live call: a fake client records each."""

import os
import re
import time
from types import SimpleNamespace as NS

import pytest

from caliper import authoring, chat, clarify, goals, intake, llm, pictures, plan, promote, refine
from caliper.design import DesignStore
from caliper.spec import Assertion, Spec

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
    assert llm.DEFAULT_MODEL == "claude-opus-5-5" and llm.QUICK_MODEL == "claude-haiku-5-5"
    for name, text in _sources():
        if name == "llm.py":
            continue
        assert not re.search(r"claude-(opus|sonnet|haiku|fable)-\d", re.sub(r"#.*", "", text)), name
        assert "DEFAULT_MODEL =" not in text, name
        assert ".messages.create(" not in text and ".messages.stream(" not in text and "api.stream" not in text, name


def test_nothing_sends_what_opus_5_5_refuses():
    for name, text in _sources():
        code = re.sub(r"#.*", "", text)
        for word in ("tool_choice", "budget_tokens", "temperature=", "top_p=", "top_k=", '"thinking":'):
            assert word not in code, (name, word)


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    for key in [k for k in os.environ if k.startswith("CALIPER_MODEL")]:
        monkeypatch.delenv(key)
    llm.log_to(None)


def test_each_job_has_its_model_from_one_table():
    assert llm.JOBS["classify"].model == llm.JOBS["describe"].model == llm.JOBS["clarify"].model == "claude-haiku-5-5"
    for job in ("author", "plan", "explain", "refine"):
        assert llm.JOBS[job].model == "claude-opus-5-5", job
    for job in ("classify", "describe", "clarify"):
        assert llm.JOBS[job].effort == "low" and llm.JOBS[job].max_tokens >= 2000


def test_a_job_can_be_moved_by_env_and_all_of_them_too(monkeypatch):
    monkeypatch.setenv("CALIPER_MODEL_CLASSIFY", "claude-x")
    c = Client()
    llm.ask(c, "classify", messages=[])
    assert c.calls[0]["model"] == "claude-x"
    assert llm.model_for("describe") == "claude-haiku-5-5"
    monkeypatch.setenv("CALIPER_MODEL", "claude-sonnet-4-6")
    assert llm.model_for("describe") == "claude-sonnet-4-6" and llm.model_for("classify") == "claude-x"
    assert llm.model_for("author", "claude-y") == "claude-y"


def test_effort_goes_in_output_config(monkeypatch):
    c = Client()
    llm.ask(c, "author", messages=[])
    assert c.calls[0]["output_config"] == {"effort": "high"}
    c = Client()
    llm.ask(c, "classify", messages=[])
    assert c.calls[0]["output_config"] == {"effort": "low"} and c.calls[0]["model"] == "claude-haiku-5-5"
    c = Client()
    llm.ask(c, "author", messages=[], model="claude-haiku-4-5")
    assert "output_config" not in c.calls[0]


def _refused(category="cyber"):
    return NS(content=[], stop_reason="refusal", stop_details=NS(category=category), usage=None)


def test_a_refusal_is_said_in_words_before_the_content_is_read():
    with pytest.raises(llm.Declined, match=r"safety checks stopped this request \(cyber\)"):
        llm.ask(Client(_refused()), "author", messages=[])


def test_a_refusal_on_haiku_goes_to_opus_once():
    class Twice(Client):
        def __init__(self):
            super().__init__()
            replies = iter([_refused(), _text("{}")])
            self.messages = NS(create=lambda **kw: (self.calls.append(kw), next(replies))[1])

    c = Twice()
    llm.ask(c, "classify", messages=[])
    assert [k["model"] for k in c.calls] == ["claude-haiku-5-5", "claude-opus-5-5"]


def test_a_refusal_on_opus_too_is_said():
    c = Client(_refused())
    with pytest.raises(llm.Declined):
        llm.ask(c, "classify", messages=[])
    assert len(c.calls) == 2


def test_a_reply_cut_off_is_a_failure_unless_the_caller_reads_it():
    cut = _text("{", stop="max_tokens")
    with pytest.raises(llm.CutOff, match="cut off at 2000 tokens"):
        llm.ask(Client(cut), "classify", messages=[])
    assert llm.ask(Client(cut), "classify", messages=[], cut_off_ok=True) is cut


def test_fallbacks_go_by_the_beta_on_a_model_that_has_them():
    c = Client(beta=True)
    llm.ask(c, "plan", messages=[])
    assert c.calls[0]["betas"] == ["server-side-fallback-2026-07-01"] and c.calls[0]["fallbacks"] == "default"
    for job, model in (("plan", "claude-sonnet-4-6"), ("classify", None)):
        c = Client(beta=True)
        llm.ask(c, job, messages=[], model=model)
        assert "fallbacks" not in c.calls[0] and "betas" not in c.calls[0]


def _spec():
    return Spec(part="block", intent="a block")


CODE = "```python\ndef build(params):\n    pass\n```"


@pytest.mark.parametrize("job, least", [("author", 64000), ("plan", 32000), ("promote", 8000), ("goals", 8000), ("intake", 8000), ("draw", 8000),
                                        ("refine", 8000), ("clarify", 4000), ("explain", 4000)])
def test_the_caps_leave_room_for_thinking(job, least):
    assert llm.JOBS[job].max_tokens >= least


def test_long_replies_are_streamed():
    assert llm.JOBS["author"].stream and llm.JOBS["plan"].stream


def test_authoring_works_hard_caches_its_prompt_and_streams():
    c = Client(_text(CODE), streams=True)
    authoring.author_script(_spec(), client=c)
    (kw,) = c.streamed
    assert kw["output_config"] == {"effort": "high"} and kw["max_tokens"] >= 64000
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


@pytest.mark.parametrize("call, job", [
    (lambda s, c: chat.llm_classify(s, "make it taller", client=c), "classify"),
    (lambda s, c: chat.redescribe("a stool", "taller", "x", client=c), "describe"),
])
def test_routing_and_short_descriptions_go_to_the_quick_model(tmp_path, call, job, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    c = Client(_text('{"action": "answer"}'))
    try:
        call(_store(tmp_path), c)
    except Exception:  # noqa: BLE001 — only the request is under test
        pass
    assert c.calls and c.calls[0]["model"] == llm.JOBS[job].model and c.calls[0]["output_config"]["effort"] == "low"


def test_the_planner_is_asked_not_forced():
    c = Client(NS(content=[], stop_reason="end_turn", usage=None))
    with pytest.raises(plan.PlanError):
        plan._ask(c, None, "a stool", "")
    assert "tool_choice" not in c.calls[0] and c.calls[0]["output_config"]["effort"] == "high" and c.calls[0]["max_tokens"] >= 16000
    assert "plan tool" in c.calls[0]["messages"][0]["content"]


# --- a refusal or a cut-off is said, wherever it happens ------------------------------------------------------------
GOOD = "import cadquery as cq\n\n\ndef build(params):\n    return cq.Workplane().box(10, 10, 10)\n"


def test_a_refusal_after_a_round_that_built_keeps_the_part():
    pytest.importorskip("cadquery")
    calls = []

    def author(spec, feedback, prior):
        calls.append(1)
        if len(calls) > 1:
            raise llm.Declined("Claude's safety checks stopped this request: try saying it another way")
        return GOOD

    spec = Spec(part="block", intent="a block", assertions=[Assertion(id="big", expr="bbox.dx >= 500")])
    got = authoring.improve(spec, author=author)
    assert got.geometry is not None and got.script == GOOD and "safety checks stopped" in got.error


STOP = llm.Declined("Claude's safety checks stopped this request: try saying it another way")


def _raises(*a, **k):
    raise STOP


def test_intake_and_refine_dont_quietly_make_something_else(monkeypatch):
    monkeypatch.setattr(intake, "llm_intake", _raises, raising=False)
    monkeypatch.setattr(intake, "llm_draft", _raises, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(llm.Stopped):
        intake.draft_spec("a block", client=Client(_refused()))
    with pytest.raises(llm.Stopped):
        refine.apply_refinement(_spec(), "make it taller", client=Client(_refused()))


def _said(store):
    return " ".join(e.get("reply", "") for e in store.log())


def test_goals_say_it(tmp_path, monkeypatch):
    s = _store(tmp_path)
    goals.update(s, "it has to hold me", client=Client(_refused()))
    assert "safety checks stopped" in _said(s)


def test_a_rule_draft_says_it(tmp_path):
    s = _store(tmp_path)
    monkeypatch_draft = promote.llm_draft
    try:
        promote.llm_draft = _raises
        promote.draft(s, "a", "keep it 2 in wide", client=Client())
    finally:
        promote.llm_draft = monkeypatch_draft
    assert "safety checks stopped" in _said(s)


def test_clarify_says_it():
    got, source = clarify.draft_questions("a stool", client=Client(_refused()))
    assert got and source.startswith(clarify.STOPPED) and "safety checks stopped" in source


def test_an_explanation_says_it_then_the_facts(tmp_path):
    got = chat.answer(_store(tmp_path), "why?", use_llm=True, client=Client(_refused()))
    assert got.reply.startswith("Claude's safety checks stopped this request") and "measured" in got.reply


def test_a_picture_gives_the_real_reason():
    with pytest.raises(ValueError, match="safety checks stopped"):
        pictures.draw("a giraffe", client=Client(_refused()))


def test_a_cut_off_is_said_the_same_way(tmp_path):
    got = chat.answer(_store(tmp_path), "why?", use_llm=True, client=Client(_text("x", stop="max_tokens")))
    assert "cut off" in got.reply


# --- which model answered -------------------------------------------------------------------------------------------
def test_each_call_goes_on_the_designs_log_with_the_model_that_answered(tmp_path):
    s = _store(tmp_path)
    llm.log_to(s)
    reply = NS(content=[], stop_reason="end_turn", model="claude-opus-5", usage=NS(cache_read_input_tokens=4100))
    llm.ask(Client(reply), "author", messages=[])
    entry = next(e for e in s.log() if e.get("kind") == "model")
    assert entry["job"] == "author" and entry["model"] == "claude-opus-5" and entry["cache_read"] == 4100 and entry["seconds"] >= 0


def test_a_job_keeps_the_requests_design_for_its_log(tmp_path):
    from caliper import jobs

    s = _store(tmp_path)
    llm.log_to(s)
    runner = jobs.JobRunner()
    seen = []
    job = runner.submit("x", lambda j: seen.append(llm._LOG_TO.get()))
    for _ in range(300):
        if job.over:
            break
        time.sleep(0.01)
    assert seen == [s]


def test_loading_a_design_for_a_request_points_the_log_at_it():
    import inspect

    from caliper import design_api

    assert "llm.log_to(store)" in inspect.getsource(design_api.router)
    assert "llm.log_to(store)" in inspect.getsource(design_api._submit_first)


def test_a_refusal_on_the_classic_api_is_a_422_in_words(monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import server

    monkeypatch.setattr(server, "draft_spec", _raises)
    got = TestClient(server.create_app(), raise_server_exceptions=False).post("/api/gen", json={"intent": "a block"})
    assert got.status_code == 422 and "safety checks stopped" in got.json()["detail"]


def test_a_refusal_on_the_command_line_is_said_and_exits_plainly(monkeypatch, capsys):
    from caliper import cli

    monkeypatch.setattr(cli, "draft_spec", _raises)
    assert cli.main(["run", "a block"]) == 3
    assert "safety checks stopped" in capsys.readouterr().err
