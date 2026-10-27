"""CALI-32 — the design session's HTTP surface: designs, clarify, chat jobs, SSE, whittle.

Runs offline: ``ANTHROPIC_API_KEY`` is cleared so routing and clarify take their deterministic
paths, and whittle is the in-process fake from ``test_whittle_bridge``.
"""

import json
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from caliper import whittle_bridge as wb  # noqa: E402
from caliper.design import DesignStore  # noqa: E402
from caliper.server import create_app  # noqa: E402

from .test_whittle_bridge import FakeWhittle, _box  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return TestClient(create_app())


def _follow(client, job_id, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.05)
    raise AssertionError("job never finished")


def _new(client, prompt="a hitch cargo box, 74in wide"):
    r = client.post("/api/designs", json={"prompt": prompt})
    assert r.status_code == 200
    body = r.json()
    _follow(client, body["job_id"])
    return body["slug"]


# --- the pages -------------------------------------------------------------
def test_the_design_session_is_the_home_page_and_the_old_panel_lives_on(client):
    home = client.get("/")
    assert home.status_code == 200 and "design.js" in home.text
    classic = client.get("/classic")
    assert classic.status_code == 200 and "app.js" in classic.text


# --- creating a design, and the clarify round -----------------------------
def test_a_new_design_asks_its_questions_in_the_background(client):
    slug = _new(client)
    state = client.get(f"/api/designs/{slug}").json()
    assert state["prompt"] == "a hitch cargo box, 74in wide"
    assert state["clarify"] and all(q["default"] for q in state["clarify"])


def test_a_prompt_in_inches_shows_inches_but_models_in_mm(client):
    state = client.get(f"/api/designs/{_new(client)}").json()
    assert (state["display_units"], state["units"]) == ("in", "mm")


def test_a_metric_prompt_stays_metric(client):
    state = client.get(f"/api/designs/{_new(client, 'a 60 mm bracket')}").json()
    assert state["display_units"] == "mm"


def test_answering_the_round_records_requirements_and_closes_it(client):
    slug = _new(client)
    qs = client.get(f"/api/designs/{slug}").json()["clarify"]
    state = client.post(f"/api/designs/{slug}/clarify",
                        json={"answers": {qs[0]["id"]: "my answer"}}).json()
    assert state["clarify"] == []
    sources = {r["question"]: r["source"] for r in state["requirements"]}
    assert sources[qs[0]["question"]] == "answered"
    assert all(sources[q["question"]] == "assumed" for q in qs[1:])


def test_skipping_assumes_everything(client):
    slug = _new(client)
    state = client.post(f"/api/designs/{slug}/clarify", json={"skip": True}).json()
    assert state["requirements"] and all(r["source"] == "assumed" for r in state["requirements"])


def test_the_units_toggle(client):
    slug = _new(client)
    assert client.patch(f"/api/designs/{slug}", json={"display_units": "mm"}).json()[
        "display_units"] == "mm"
    assert client.patch(f"/api/designs/{slug}", json={"display_units": "ft"}).status_code == 422


def test_an_unknown_design_is_a_404(client):
    assert client.get("/api/designs/nope").status_code == 404
    assert client.post("/api/designs/nope/chat", json={"message": "hi"}).status_code == 404


def test_designs_are_listed(client):
    slug = _new(client)
    assert slug in [d["slug"] for d in client.get("/api/designs").json()["designs"]]


# --- chat turns run as jobs ----------------------------------------------
def test_a_chat_turn_runs_as_a_job_and_returns_the_reply(client):
    slug = _new(client)
    job = client.post(f"/api/designs/{slug}/chat", json={"message": "what parts exist?"}).json()
    done = _follow(client, job["job_id"])
    assert done["status"] == "done"
    assert done["result"]["action"] == "answer" and "No parts yet" in done["result"]["reply"]
    assert any(e["kind"] == "classified" for e in done["events"])
    # and the conversation is in the design's log, for the page to redraw on reload
    kinds = [e["kind"] for e in client.get(f"/api/designs/{slug}").json()["log"]]
    assert kinds[-2:] == ["message", "reply"]


def test_an_empty_message_is_refused(client):
    slug = _new(client)
    assert client.post(f"/api/designs/{slug}/chat", json={"message": "  "}).status_code == 422


def test_the_event_stream_replays_the_turn_and_ends_with_the_result(client):
    slug = _new(client)
    job = client.post(f"/api/designs/{slug}/chat", json={"message": "what parts exist?"}).json()
    _follow(client, job["job_id"])
    with client.stream("GET", f"/api/jobs/{job['job_id']}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        payloads = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert payloads[0]["kind"] == "started"
    assert payloads[-1]["kind"] == "end" and payloads[-1]["result"]["action"] == "answer"


def test_an_expired_job_is_a_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404


# --- parts on the wire (OCCT) ----------------------------------------------
@pytest.fixture
def hitch(client, tmp_path):
    s = DesignStore.create("a hitch cargo box", base=str(tmp_path / "designs"), slug="hitch")
    s.write_part("car", _box(dx=1500, dy=1790, dz=1300, x=750, z=750), intent="the car's rear")
    s.write_part("box", _box(), intent="the cargo box")
    return s


def test_state_carries_each_parts_size_rules_and_history(client, hitch):
    pytest.importorskip("cadquery")
    state = client.get("/api/designs/hitch").json()
    box = next(p for p in state["parts"] if p["id"] == "box")
    assert box["bbox"]["size"] == pytest.approx([1000, 1800, 1000], abs=0.5)
    assert box["scripted"] and box["history"][-1]["action"] == "author"
    assert box["stl_url"].startswith("/api/designs/hitch/parts/box.stl")


def test_a_part_is_served_as_stl(client, hitch):
    pytest.importorskip("cadquery")
    r = client.get("/api/designs/hitch/parts/box.stl")
    assert r.status_code == 200 and len(r.content) > 84
    assert client.get("/api/designs/hitch/parts/nope.stl").status_code == 404


def test_a_parts_script_is_there_for_the_advanced_drawer(client, hitch):
    body = client.get("/api/designs/hitch/parts/box/script").json()
    assert "def build" in body["script"] and body["scripted"]


# --- whittle over the API --------------------------------------------------
@pytest.fixture
def fake(monkeypatch):
    f = FakeWhittle()
    monkeypatch.setattr(wb, "WHITTLE_URL", f.url)
    yield f
    f.close()


def test_whittle_health_is_reported(client, fake):
    assert client.get("/api/whittle/health").json()["ok"]


def test_a_whittle_study_runs_files_and_brings_a_station_back(client, hitch, fake):
    pytest.importorskip("cadquery")
    job = client.post("/api/designs/hitch/whittle",
                      json={"part": "box", "carve": "tail", "remove_up_to": 0.2}).json()
    done = _follow(client, job["job_id"])
    assert done["status"] == "done", done["error"]
    wid = done["result"]["id"]
    assert fake.jobs[-1]["surfaces"]                        # only the tail may change

    runs = client.get("/api/designs/hitch/whittle?part=box").json()["runs"]
    assert [r["id"] for r in runs] == [wid]
    st = client.get(f"/api/designs/hitch/whittle/{wid}/stations/2.stl")
    assert st.status_code == 200 and len(st.content) > 84

    back = client.post(f"/api/designs/hitch/whittle/{wid}/adopt", json={"station": 2}).json()
    assert back["version"] == 2 and back["grew_mm"] == {}
    box = next(p for p in back["design"]["parts"] if p["id"] == "box")
    assert box["origin"] == "whittled" and not box["scripted"]
    assert back["design"]["log"][-1]["action"] == "adopted"


def test_a_whittle_failure_reaches_the_page_named(client, hitch, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.setattr(wb, "WHITTLE_URL", "http://127.0.0.1:9")
    job = client.post("/api/designs/hitch/whittle", json={"part": "box"}).json()
    done = _follow(client, job["job_id"])
    assert done["status"] == "error" and "is it running" in done["error"]


def test_whittle_on_an_unknown_part_is_a_404(client, hitch):
    assert client.post("/api/designs/hitch/whittle", json={"part": "nope"}).status_code == 404


def test_adopting_a_missing_station_is_a_404(client, hitch):
    r = client.post("/api/designs/hitch/whittle/nope/adopt", json={"station": 0})
    assert r.status_code == 404


def test_a_part_can_be_marked_as_a_reference(client, hitch):
    state = client.patch("/api/designs/hitch/parts/car", json={"role": "fixed"}).json()
    assert next(p for p in state["parts"] if p["id"] == "car")["role"] == "fixed"
    assert client.patch("/api/designs/hitch/parts/car", json={"role": "x"}).status_code == 422
    assert client.patch("/api/designs/hitch/parts/nope", json={"role": "fixed"}).status_code == 404
