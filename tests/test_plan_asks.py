"""CALI-231 (#371's page part): a plan's open question is said above Build it, and Build it waits for the answer.

#371: a part named for what a design stands on ("box_floor") that's neither marked fixed nor said how it's made is asked
of the person; the plan keeps the question, and Build it builds nothing while it's open: it only replies with the question.
The page showed a live Build it with no question beside it. Now the question is said above the button and in the plan's
section, and the button waits."""
import json

import pytest

from .test_carve_click import JS, _fn, _page, _run

Q = "Is the box floor something to make? Say how it's made, or that it's what it stands on (then it's left out)."

_THREAD = """
const els = { thread: { innerHTML: '', scrollTop: 0, scrollHeight: 0, append() {}, querySelectorAll: () => [] } };
const $ = (id) => els[id] || (els.thread.innerHTML.includes(`id="${id}"`) ? (els[id] = { id, disabled: /id="buildFirst" disabled/.test(els.thread.innerHTML) }) : null);
const S = { busy: false, design: DESIGN };
const simplerOffered = () => false, wireClarify = () => {}, paintSendNote = () => {}, send = () => {}, md = (x) => x;
"""


def _thread(plan):
    design = {"log": [], "parts": [], "clarify": [], "building": None, "claude": True, "plan": plan}
    return _run(_page(["asksHtml", "renderThread"], consts=["esc", "planAsks"], extra=_THREAD.replace("DESIGN", json.dumps(design))
                      + "renderThread(); out = { html: els.thread.innerHTML, disabled: $('buildFirst').disabled };"))


def test_the_question_is_said_above_build_it_and_build_it_waits():
    got = _thread({"questions": [Q], "parts": [], "numbers": [], "checks": []})
    html = got["html"]
    assert html.index(f"<b>Before I build it:</b> {Q}") < html.index('id="buildFirst"')
    assert got["disabled"] is True and "say it below, and I'll change the plan" in html


def test_with_nothing_to_ask_build_it_is_as_it_was():
    got = _thread({"questions": [], "parts": [], "numbers": [], "checks": []})
    assert "Before I build it" not in got["html"] and got["disabled"] is False
    assert "or say what to build first" in got["html"]


def test_no_plan_yet_build_it_is_as_it_was():
    got = _thread(None)
    assert "Before I build it" not in got["html"] and got["disabled"] is False


def test_a_question_is_text_not_html():
    got = _run(_page(["asksHtml"], consts=["esc"], extra="out = asksHtml(['Is the <b>x</b> & y made?']);"))
    assert "Is the &lt;b&gt;x&lt;/b&gt; &amp; y made?" in got and "<b>x</b>" not in got


def test_the_plan_s_section_says_it_too():
    assert "${asksHtml(planAsks(d))}" in _fn(open(JS).read(), "designView")


# --- the server carries it ------------------------------------------------------------------------------------------------
pytest.importorskip("cadquery")


def test_the_design_s_plan_carries_its_questions(tmp_path):
    from caliper import design_api
    from caliper import plan as P
    from caliper.design import DesignStore

    from .test_plan_live import STOOL

    plan = json.loads(json.dumps(STOOL).replace("bathroom_floor", "box_floor"))
    plan["parts"][1]["role"] = "movable"
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    P.save(store, P.validate(plan, ask=True))
    assert design_api._plan(store)["questions"] == [Q]
    P.save(store, P.validate(STOOL))
    assert design_api._plan(store)["questions"] == []


def test_what_is_it_asks_the_question_and_never_says_press_build_it_over_it():
    """The card said "Say what to change, or press Build it." beside a Build it that waits for the answer."""
    from caliper import answers

    plan = {"headline": "A step stool in 2 parts", "questions": [Q], "parts": [], "numbers": [], "checks": []}
    state = {"name": "Step stool", "prompt": "a step stool", "parts": [], "requirements": [], "plan": plan, "claude": True}
    lines = [ln["text"] for ln in next(c for c in answers.design(None, state) if c["key"] == "what")["lines"]]
    assert f"Before I build it: {Q}" in lines and not any("press Build it" in ln for ln in lines), lines
    assert any(ln.endswith("Answer its question first: Build it waits for it.") for ln in lines)
