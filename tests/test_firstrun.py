"""CALI-59 (#8) — first run: one sentence in, four answers out."""

import time

import pytest

from caliper import answers, firstrun, load_study
from caliper.design import DesignStore, short_name

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")

PROMPT = "A box step stool so my kid can reach the sink, from 3/4 in plywood. It has to hold me too (200 lb)."


def test_a_design_is_named_for_what_it_is_not_the_whole_sentence():
    assert short_name("A step stool so my 6-year-old can reach the bathroom sink. Made from 3/4 in plywood") \
        == "Step stool"
    assert short_name("A cargo box on the trailer hitch behind my Nissan Leaf.") == "Cargo box"
    assert short_name("I want a bird house for the garden") == "Bird house"
    assert short_name("gantry") == "Gantry" and short_name("") == "Untitled design"
    assert len(short_name("a " + "very " * 30 + "long thing")) <= 40


def _author(s, feedback=None, prior=None):
    return BOX_STOOL


@pytest.fixture
def quick(monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: quick, and it still has a verdict


def _cards(store, pid):
    from caliper.design_api import design_state

    return answers.answers(store, design_state(store), pid)


def test_one_sentence_in_four_answers_out(tmp_path, quick):
    store = DesignStore.create(PROMPT, base=str(tmp_path / "designs"))
    heard = []
    got = firstrun.build(store, emit=lambda k, t="", **d: heard.append((k, t, d)), use_llm=False,
                         author=_author, cards=_cards)
    assert got["ok"] and got["part"] == "box_step" and store.design.part("box_step").version == 1
    # each step said as it goes, in order
    steps = [d["step"] for k, _, d in heard if k == "step"]
    assert steps == ["goals", "build", "strength", "patterns", "score", "done"]
    assert got["steps"]["score"].endswith("fail")
    # its strength check, at the safety its checks ask for, and its patterns: on the version just built
    (run,) = load_study.list_runs(store, "box_step")
    assert run["version"] == 1 and run["safety"] and run["min_safety"] == firstrun._min_safety(store)
    from caliper import patterns

    (pat,) = patterns.list_runs(store, "box_step")
    assert pat["version"] == 1 and pat["pages"] > 0
    # the reply is the four answers, one line each
    reply = got["reply"]
    for q in ("What is it?", "Will it work?", "What do I buy?", "How do I make it?"):
        assert f"**{q}**" in reply
    assert "Holds an adult stepping up" in reply and "plywood" in reply
    log = store.log()
    assert any(e["kind"] == "firstrun" and e["action"] == "built" for e in log)
    assert log[-1]["kind"] == "reply" and log[-1]["firstrun"] and log[-1]["reply"] == reply
    # the verdict says what it promises, and what it doesn't
    work = next(c for c in _cards(store, "box_step") if c["key"] == "work")
    assert work["promise"] == answers.PROMISE and "not a certificate" in work["promise"]

    # --- and a kid can ask about it: in plain words, never read as a change to the part
    from caliper import chat

    assert chat.offline_classify(store, "Say that again in simpler words, for a kid.", scope="box_step").action \
        == "answer"
    assert chat.offline_classify(store, "make it simpler to cut", scope="box_step").action == "refine"
    asked = []

    class Fake:
        class messages:  # noqa: N801 — the Anthropic client's shape
            @staticmethod
            def create(**kw):
                asked.append(kw)
                return type("M", (), {"content": [type("B", (), {"type": "text", "text": "It could hold three of you."})]})

    got = chat.answer(store, "why only 3 times?", scope="box_step", use_llm=True, client=Fake)
    assert got.reply == "It could hold three of you." and got.action == "answer"
    facts = asked[0]["messages"][0]["content"]
    assert "Will it work? Holds an adult stepping up" in facts and "6-year-old" in asked[0]["system"]
    assert "question: why only 3 times?" in facts


def test_a_build_that_fails_says_so_and_adds_nothing(tmp_path):
    store = DesignStore.create(PROMPT, base=str(tmp_path / "designs"))
    got = firstrun.build(store, use_llm=False, author=lambda *a, **k: "def build(params):\n    raise RuntimeError('boom')\n")
    assert not got["ok"] and not store.design.parts and "couldn't build" in got["reply"]
    assert got["steps"]["build"].startswith("failed")


def test_no_strength_check_without_loads_or_without_whittle(tmp_path, quick):
    store = DesignStore.create(PROMPT, base=str(tmp_path / "designs"))
    heard = []
    got = firstrun.build(store, emit=lambda k, t="", **d: heard.append(d.get("step")), use_llm=False,
                         author=_author, strength=False)
    assert got["ok"] and "isn't installed" in got["steps"]["strength"] and "strength" not in heard


# --- through the API: the clarify answers start it, and the page can follow it -----------------------------
@pytest.fixture
def client(tmp_path, monkeypatch, quick):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper import authoring
    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(authoring, "author_script", lambda s, feedback=None, prior=None, client=None: BOX_STOOL)
    return TestClient(create_app())


def _follow(client, job_id, timeout=240.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.1)
    raise AssertionError("job never finished")


def test_answering_its_questions_builds_it(client):
    body = client.post("/api/designs", json={"prompt": PROMPT}).json()
    _follow(client, body["job_id"])
    slug = body["slug"]
    assert slug == "box-step-stool"
    state = client.post(f"/api/designs/{slug}/clarify", json={"skip": True, "build": True}).json()
    assert state["building"]
    done = _follow(client, state["building"])
    assert done["status"] == "done", done.get("error")
    state = client.get(f"/api/designs/{slug}").json()
    assert state["building"] is None and [p["id"] for p in state["parts"]] == ["box_step"]
    assert state["load_runs"] and state["pattern_runs"]
    cards = {c["key"]: c for c in client.get(f"/api/designs/{slug}/answers?part=box_step").json()["cards"]}
    assert any(ln["status"] == "ok" and "Holds" in ln["text"] for ln in cards["work"]["lines"])
    # built once: asking again is refused
    assert client.post(f"/api/designs/{slug}/build").status_code == 409


def test_answering_without_build_still_only_records_them(client):
    body = client.post("/api/designs", json={"prompt": PROMPT}).json()
    _follow(client, body["job_id"])
    state = client.post(f"/api/designs/{body['slug']}/clarify", json={"skip": True}).json()
    assert state["building"] is None and not state["parts"]
