"""CALI-232 (#238's page part): the Review it / Review again button, and its route.

#368 built Claude's reading (`assess.run`, one call on the person's press) and its rows under Things to fix; the button and
its route were the page lane's. Above Things to fix (and under the design's own checks), Review it says what it does and what
it costs, in the server's words (`assess.offer`); pressed, it runs as a job (one Claude call), its rows are read again, and
the button becomes Review again. Never without a key: nothing is sent. Claude is a stub in every test: no live call."""
import json
import os

import pytest

from .test_carve_click import JS, _fn, _page, _run

OFFER = {"label": "Review it", "cost": "one Claude call, about 30–60 s", "note": "", "stale": {}, "unread": [], "count": 0}


def _view(assess, claude=True):
    head = f"""const S = {{ slug: 's', claude: {json.dumps(claude)}, assess: {json.dumps({**assess, 'slug': 's'})},
      design: {{ parts: [{{ id: 'step_stool', name: 'Step stool' }}] }} }};
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {{}};"""
    return _run(_page(["assessHere", "assessSince", "assessView", "reviewSection"], consts=["esc"],
                      extra=head + "\nout = { html: assessView(), head: reviewSection() };"))


def test_it_says_what_it_does_and_costs_in_the_server_s_words():
    got = _view({"offer": OFFER})
    assert '<button id="assessGo">Review it</button>' in got["html"] and "one Claude call, about 30–60 s" in got["html"]
    assert "That's a reading, not a check" in got["html"]
    assert got["head"]["answer"] == "one Claude call, about 30–60 s" and got["head"]["tone"] == "info"


def test_review_again_says_what_s_changed_since_and_the_count():
    o = {**OFFER, "label": "Review again", "stale": {"step_stool": 3}, "count": 3, "note": "4th reading on this design"}
    got = _view({"offer": o})
    assert '<button id="assessGo">Review again</button>' in got["html"] and "4th reading on this design" in got["html"]
    assert "read on Step stool v3; changed since" in got["html"] and got["head"]["answer"] == "read on Step stool v3; changed since"
    assert _view({"offer": {**o, "stale": {}}})["head"]["answer"] == "3 readings so far"


def test_the_header_says_a_part_s_name_as_text():
    o = {**OFFER, "label": "Review again", "stale": {"step_stool": 3}, "count": 1}
    head = f"""const S = {{ slug: 's', claude: true, assess: {{ slug: 's', offer: {json.dumps(o)} }},
      design: {{ parts: [{{ id: 'step_stool', name: '<i>Step</i> & stool' }}] }} }};
const partOf = (pid) => S.design.parts.find((x) => x.id === pid) || {{}};"""
    got = _run(_page(["assessHere", "assessSince", "assessView", "reviewSection"], consts=["esc"], extra=head + "\nout = reviewSection().answer;"))
    assert got == "read on &lt;i&gt;Step&lt;/i&gt; &amp; stool v3; changed since"


_PAINT = """
const sum = { innerHTML: 'before' }, sec = { querySelector: () => sum };
const els = { assessBox: { innerHTML: '', closest: (q) => (q === 'details.ssec[data-ssec="review"]' ? sec : null) } };
const $ = (id) => els[id] || null;
const S = { slug: 's', claude: true, assess: { slug: 's', offer: OFFER }, design: { parts: [] } };
const partOf = () => ({}), subHead = (x) => `HEAD ${x.answer}`, loadAssess = () => {};
"""


def test_its_header_is_drawn_again_once_the_offer_comes():
    """The walk: the header said "one Claude call, on your press" beside a body that had read its offer."""
    o = {**OFFER, "label": "Review again", "count": 2}
    got = _run(_page(["assessHere", "assessSince", "assessView", "reviewSection", "paintAssess", "wireAssess"], consts=["esc"],
                     extra=_PAINT.replace("OFFER", json.dumps(o)) + "paintAssess(); out = sum.innerHTML;"))
    assert got == "HEAD 2 readings so far"


def test_with_no_key_it_s_said_and_never_pressed():
    got = _view({"offer": OFFER}, claude=False)
    assert '<button id="assessGo" disabled>' in got["html"] and "Reviewing it needs Claude, which isn't set up here." in got["html"]


def test_what_it_said_is_shown_as_text_line_by_line():
    said = "Claude's reading of 2 parts (1 thing; read, not measured):\n- The <b>step</b> is thin (step). Make it 25 mm."
    got = _view({"offer": OFFER, "said": said, "ok": True})
    assert "white-space:pre-line" in got["html"] and "The &lt;b&gt;step&lt;/b&gt; is thin" in got["html"]
    assert "color:var(--amber)" in _view({"offer": OFFER, "said": "No reading: x", "ok": False})["html"]


_PRESS = """
const calls = [], said = [];
const els = { assessBox: { innerHTML: '', closest: () => null }, assessGo: { disabled: false } };
const $ = (id) => els[id] || null;
const S = { slug: 's', claude: true, assess: { slug: 's', offer: OFFER }, fixes: { 's/step_stool': { rows: [] } }, fixReading: { x: 1 },
  design: { parts: [] } };
const partOf = () => ({});
const api = async (m, url) => { calls.push([m, url]); return m === 'POST' ? { job_id: 'j1' } : { offer: { ...OFFER, label: 'Review again', count: 1 }, latest: { n: 1 } }; };
const trackJob = (id, info) => { calls.push(['track', id, info.kind, info.part]); return { done: RESULT }; };
const say = (t) => said.push(t); const render = () => calls.push(['render']); const plainly = (m) => m;
"""


def _press(result):
    head = _PRESS.replace("OFFER", json.dumps(OFFER), 1).replace("OFFER", json.dumps(OFFER)).replace("RESULT", result)
    return _run(_page(["assessHere", "assessSince", "assessView", "loadAssess", "paintAssess", "wireAssess"], consts=["esc"],
                      extra=head + "\nwireAssess(); await els.assessGo.onclick();\nout = { calls, said, assess: S.assess, fixes: S.fixes };"))


def test_pressed_it_runs_as_a_job_reads_its_rows_again_and_offers_review_again():
    got = _press("Promise.resolve({ ok: true, said: \"Claude's reading of 1 part\" })")
    assert ["POST", "/api/designs/s/assess"] in got["calls"] and ["track", "j1", "assess", None] in got["calls"]
    assert got["calls"][-2:] == [["GET", "/api/designs/s/assess"], ["render"]]
    assert got["fixes"] == {}                                                  # Things to fix is read again: its rows
    assert got["assess"]["offer"]["label"] == "Review again" and got["assess"]["said"] == "Claude's reading of 1 part"
    assert got["said"] == ["Claude read it: what it reads wrong is under Things to fix, as Claude's reading."]


def test_a_reading_that_fails_is_said_and_keeps_things_to_fix_as_it_was():
    got = _press("Promise.reject(new Error('the job failed'))")
    assert got["assess"]["said"] == "No reading: the job failed" and got["assess"]["ok"] is False
    assert got["fixes"] == {"s/step_stool": {"rows": []}} and got["said"] == ["No reading: the job failed"]


def test_it_sits_above_things_to_fix_and_under_the_design_s_checks():
    src = open(JS).read()
    part = _fn(src, "partView")
    assert part.index("reviewSection()") < part.index("fixesSection(p.id)")
    assert "<h4>Claude's reading</h4><div id=\"assessBox\">${assessView()}</div>" in _fn(src, "designView")
    assert "wireAssess();" in _fn(src, "wireCards") and "wireCards();" in _fn(src, "wireInspector")


# --- the route ---------------------------------------------------------------------------------------------------------------
pytest.importorskip("cadquery")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper import assess, review
    from caliper.design import DesignStore
    from caliper.server import create_app

    from .test_assess import SIDE, STEP, Claude

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("A step stool 16 in tall that holds 200 lb", base=str(tmp_path / "designs"))
    s.write_part("side", SIDE, intent="a plywood side")
    s.write_part("step", STEP, intent="the step, on the side")
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [], "checks": 3})
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(s.root))
    claude = Claude([{"parts": ["step"], "said": "the step is 19 mm ply over a 400 mm span for 200 lb",
                      "fix": "Make the step 25 mm, or add a rail under it."}])
    real = assess.run
    monkeypatch.setattr(assess, "run", lambda store, **kw: real(store, client=claude))      # the stub, never Anthropic()
    return TestClient(create_app()), os.path.basename(s.root), claude


def test_the_offer_and_the_last_reading(app):
    c, slug, _ = app
    got = c.get(f"/api/designs/{slug}/assess").json()
    assert got == {"offer": {**OFFER, "unread": []}, "latest": None}


def test_with_no_key_nothing_is_sent(app):
    c, slug, claude = app
    got = c.post(f"/api/designs/{slug}/assess")
    assert got.status_code == 409 and got.json()["detail"] == "Reviewing it needs Claude, which isn't set up here."
    assert claude.seen == []


def test_pressed_it_reads_once_as_a_job_and_its_rows_are_under_things_to_fix(app, monkeypatch):
    from caliper import design_api, fixes, jobs
    from caliper.design import DesignStore

    from .test_carve_click import _wait

    c, slug, claude = app
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a stub's: never sent")
    jid = c.post(f"/api/designs/{slug}/assess").json()["job_id"]
    job = jobs.RUNNER.get(jid)
    _wait(job)
    assert job.kind == "assess" and job.status == "done" and job.result["ok"] and len(claude.seen) == 1
    assert job.result["said"].startswith("Claude's reading of 2 parts (1 thing; read, not measured):")
    offer = c.get(f"/api/designs/{slug}/assess").json()
    assert offer["offer"]["label"] == "Review again" and offer["offer"]["count"] == 1 and offer["latest"]["n"] == 1
    store = DesignStore.load(slug)
    got = fixes.listed(store, design_api.design_state(store), "step")
    (row,) = [r for r in got["rows"] if r["id"].startswith("reading:")]
    assert row["measured"] is False and got["counts"]["readings"] == 1 and got["counts"]["measured"] == 0


def test_nothing_built_nothing_to_read(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.design import DesignStore
    from caliper.server import create_app

    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(s.root))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a stub's: never sent")
    got = TestClient(create_app()).post(f"/api/designs/{os.path.basename(s.root)}/assess")
    assert got.status_code == 409 and got.json()["detail"] == "Nothing's built to read yet: build it first."


def test_two_presses_at_once_make_one_call_and_the_second_is_told_it_s_running(app, monkeypatch):
    """#396 review: two tabs' POSTs both got 200 and ran back to back: two Claude calls, never "busy". The job is
    exclusive now: while a reading of the design is queued or running, another press is refused with assess.BUSY."""
    import threading

    from caliper import assess, jobs

    from .test_assess import Claude
    from .test_carve_click import _wait

    c, slug, _ = app
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a stub's: never sent")
    inside, go = threading.Event(), threading.Event()

    class Slow(Claude):
        def create(self, **kw):
            inside.set()
            assert go.wait(10), "never let go"
            return super().create(**kw)

    slow = Slow([], [])
    real = assess._run
    monkeypatch.setattr(assess, "run", lambda store, **kw: real(store, client=slow))
    first = c.post(f"/api/designs/{slug}/assess")
    assert first.status_code == 200 and inside.wait(10)                      # the first is asking Claude
    second = c.post(f"/api/designs/{slug}/assess")
    assert second.status_code == 409 and second.json()["detail"] == assess.BUSY
    go.set()
    _wait(jobs.RUNNER.get(first.json()["job_id"]))
    assert len(slow.seen) == 1
    again = c.post(f"/api/designs/{slug}/assess")                            # once it's over, it can be pressed again
    assert again.status_code == 200
    _wait(jobs.RUNNER.get(again.json()["job_id"]))
