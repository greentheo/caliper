"""CALI-80 (#48) — record the test: what the strength check predicted, against what the real one did."""

import os

import pytest

from caliper import answers, design_api, load_study, trials
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


@pytest.fixture
def checked(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    store.design.display_units = "in"
    store.save()
    load_study.study(store, "stool")
    return store


def test_the_prediction_goes_from_the_load_to_where_it_breaks_as_a_range(checked):
    pr = trials.predict(checked, "stool")
    assert pr["case"] == "an adult stepping up" and pr["lb"] == 200 and pr["breaks_lb"] > 400
    lo, hi = pr["per_lb_mm"]
    assert 0 < lo <= hi                                        # the FEA (stiff) to the plate check (free edges)
    loads = [s["lb"] for s in pr["steps"]]
    assert loads[0] == 50 and 200 in loads and loads[-1] >= pr["breaks_lb"]
    at200 = next(s for s in pr["steps"] if s["lb"] == 200)["sag_mm"]
    assert at200 == [pytest.approx(lo * 200, abs=1e-3), pytest.approx(hi * 200, abs=1e-3)]
    # a sag of a few tenths of a millimetre: say what will see it
    assert "dial indicator" in pr["measure_with"] and "tape measure won't" in pr["measure_with"]
    assert trials.measure_with(10).startswith("a tape measure")


def test_no_prediction_without_a_strength_check_on_this_version(checked):
    checked.write_part("stool", BOX_STOOL, intent="the same, again")
    assert trials.predict(checked, "stool") is None


def test_each_step_is_kept_and_set_beside_the_prediction(checked):
    pr = trials.predict(checked, "stool")
    lo, hi = pr["per_lb_mm"]
    trials.record(checked, "stool", 200, sag_mm=(lo + hi) / 2 * 200)
    trials.record(checked, "stool", 400, sag_mm=hi * 400 * 1.5, note="a bit soft")
    got = trials.compared(checked, "stool")
    assert [r["load_lb"] for r in got["rows"]] == [200, 400]
    assert got["rows"][0]["predicted_mm"] == [round(lo * 200, 3), round(hi * 200, 3)]
    assert got["rows"][1]["ratio"] > 1.4
    # the card: the heaviest it held, its sag against the prediction, in inches
    line = trials.summary(checked, "stool", inches=True)
    assert line["status"] == "ok" and line["text"].startswith("Tested: it held 400 lb; at 400 lb it sagged 0.0")
    assert "we predicted" in line["text"] and line["text"].endswith(" in).")
    work = answers.answers(checked, design_api.design_state(checked), "stool")[1]
    assert any(ln.get("study") == "trial" and ln["text"] == line["text"] for ln in work["lines"])
    # and where it broke
    trials.record(checked, "stool", 1100, broke=True)
    assert trials.summary(checked, "stool")["text"] == (           # more than 10% short of the prediction
        f"It broke sooner than we predicted, so our check was too hopeful. It still held the 400 lb it must hold "
        f"(200 lb, twice over for an adult stepping up). (It broke at 1,100 lb; we predicted about "
        f"{pr['breaks_lb']:,.0f}.)")
    # a test of an older version reads as one
    checked.write_part("stool", BOX_STOOL, intent="v2")
    assert all(r["stale"] for r in trials.compared(checked, "stool")["rows"])
    assert trials.summary(checked, "stool") is None
    with pytest.raises(ValueError):
        trials.record(checked, "stool", 0)


def test_through_the_api(checked, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(checked.root.rsplit("/", 1)[0]))
    c = TestClient(create_app())
    slug = checked.design.slug
    assert c.get(f"/api/designs/{slug}/parts/stool/trial").json()["prediction"]["lb"] == 200
    got = c.post(f"/api/designs/{slug}/parts/stool/trial", json={"load_lb": 200, "sag_mm": 0.1}).json()
    assert got["rows"][-1]["load_lb"] == 200 and got["rows"][-1]["predicted_mm"]
    assert c.post(f"/api/designs/{slug}/parts/stool/trial", json={"load_lb": -5}).status_code == 422
    assert c.post(f"/api/designs/{slug}/parts/nope/trial", json={"load_lb": 5}).status_code == 404


@pytest.fixture
def plain(tmp_path, monkeypatch):
    """A part with no strength check: enough to record steps against, and cheap."""
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    return store


@pytest.mark.parametrize("load,sag", [(float("nan"), None), (float("inf"), None), (200, float("nan")),
                                      (200, float("inf")), (200, -0.5), (200, 0.0)])
def test_a_step_must_be_a_real_number_more_than_nothing(plain, load, sag):
    """CALI-86 (#62, finding 5): a NaN slipped past `not load or load <= 0` and broke the design's page."""
    with pytest.raises(ValueError):
        trials.record(plain, "stool", load, sag_mm=sag)
    assert trials.rows(plain, "stool") == []


def test_the_api_refuses_nan_and_a_nan_already_on_file_doesnt_break_the_page(plain):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    c = TestClient(create_app())
    slug = plain.design.slug
    for body in ('{"load_lb": NaN}', '{"load_lb": Infinity}', '{"load_lb": 200, "sag_mm": NaN}'):
        got = c.post(f"/api/designs/{slug}/parts/stool/trial", content=body,
                     headers={"content-type": "application/json"})
        assert got.status_code == 422, body
    # a trials file someone wrote by hand, with a NaN in it, beside a good line and one that isn't JSON
    trials.record(plain, "stool", 200, sag_mm=0.4)
    with open(trials.path(plain, "stool"), "a") as f:
        f.write('{"at": 1, "version": 1, "load_lb": NaN, "sag_mm": null, "broke": false, "note": ""}\n')
        f.write("not json\n")
    got = trials.compared(plain, "stool")
    assert [r["load_lb"] for r in got["rows"]] == [200] and got["skipped"] == 2
    assert "2 lines" in got["skipped_note"]
    assert c.get(f"/api/designs/{slug}").status_code == 200
    assert c.get(f"/api/designs/{slug}/parts/stool/trial").status_code == 200
    assert c.get(f"/api/designs/{slug}/answers?part=stool").status_code == 200


def test_the_test_record_s_verdicts_are_the_right_colour(checked):
    """CALI-86 (#62, finding 11; rule 6): "broke at 150 lb" on a part that must hold 400 was `info`, and a sag 15x
    the prediction was a green tick."""
    pr = trials.predict(checked, "stool")
    lo, hi = pr["per_lb_mm"]
    must = pr["lb"] * pr["factor"]
    assert must == 400

    def line(*steps):
        if os.path.exists(trials.path(checked, "stool")):
            os.remove(trials.path(checked, "stool"))
        for load, kw in steps:
            trials.record(checked, "stool", load, **kw)
        return trials.summary(checked, "stool")

    got = line((150, {"broke": True}))
    # what it had to hold, and what we predicted: both numbers, the second the one #42's calibration needs (#64 item 13)
    assert got["status"] == "bad" and got["text"] == (
        f"It broke at 150 lb in your test. It had to hold 400 (200 lb, twice over for {pr['case'].lower()}), and we "
        f"predicted about {pr['breaks_lb']:,.0f}."), got["text"]
    got = line((must + 50, {"broke": True}))
    assert got["status"] == "warn" and "sooner than we predicted" in got["text"]
    got = line((pr["breaks_lb"] + 50, {"broke": True}))
    assert got["status"] == "ok"
    got = line((200, {"sag_mm": hi * 200 * 15}))
    assert got["status"] == "warn" and "sagged more than we predicted" in got["text"]
    got = line((200, {"sag_mm": lo * 200 / 15}))
    assert got["status"] == "warn" and "sagged less than we predicted" in got["text"]
    got = line((must, {"sag_mm": (lo + hi) / 2 * must}))
    assert got["status"] == "ok" and "predicted" in got["text"]
    # held, but short of what it must hold: not a pass for it (#132 review)
    got = line((200, {"sag_mm": (lo + hi) / 2 * 200}))
    assert got["status"] == "warn" and "short of the 400 lb it must hold" in got["text"]


@pytest.mark.parametrize("line", [
    '{"at": 1, "load_lb": 200, "sag_mm": 0.4, "broke": false, "note": ""}',                   # no version
    '{"at": 1, "version": 1, "load_lb": "200", "sag_mm": null, "broke": false, "note": ""}',  # a load as a string
    '{"at": 1, "version": 1, "load_lb": true, "sag_mm": null, "broke": false, "note": ""}',   # true isn't a number
    '{"at": 1, "version": 1, "load_lb": 200, "sag_mm": NaN, "broke": false, "note": ""}',     # the sag checked too
    '{"at": 1, "version": 1, "load_lb": 200, "sag_mm": "0.4", "broke": false, "note": ""}',
    '[200, 0.4]',
])
def test_a_line_on_file_that_isnt_a_step_is_left_out_never_a_500(plain, line):
    """CALI-86 (#69 rework, item 3): a line with no version, or a load written as a string, made /trial and /answers
    a 500; a NaN sag got past the read."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    trials.record(plain, "stool", 200, sag_mm=0.4)
    with open(trials.path(plain, "stool"), "a") as f:
        f.write(line + "\n")
    got = trials.compared(plain, "stool")
    assert [r["load_lb"] for r in got["rows"]] == [200] and got["skipped"] == 1
    c = TestClient(create_app(), raise_server_exceptions=False)
    slug = plain.design.slug
    for url in (f"/api/designs/{slug}/parts/stool/trial", f"/api/designs/{slug}/answers?part=stool",
                f"/api/designs/{slug}"):
        assert c.get(url).status_code == 200, url


def test_the_api_takes_true_for_no_number(plain):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    c = TestClient(create_app())
    for body in ({"load_lb": True}, {"load_lb": 200, "sag_mm": True}):
        assert c.post(f"/api/designs/{plain.design.slug}/parts/stool/trial", json=body).status_code == 422, body
    assert trials.rows(plain, "stool") == []


def test_a_nan_already_in_the_conversation_log_doesnt_break_the_design(plain):
    """CALI-86 (#69 rework, item 3): append_log wrote a NaN before CALI-86, and nothing read log.jsonl defensively."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    with open(plain.log_path, "a") as f:
        f.write('{"kind": "trial", "action": "recorded", "part": "stool", "load_lb": NaN, "broke": false}\n')
    got = TestClient(create_app(), raise_server_exceptions=False).get(f"/api/designs/{plain.design.slug}")
    assert got.status_code == 200 and got.json()["log_skipped"] == 1


def _only(store, *steps):
    """The card's line for exactly these steps."""
    if os.path.exists(trials.path(store, "stool")):
        os.remove(trials.path(store, "stool"))
    for load, kw in steps:
        trials.record(store, "stool", load, **kw)
    return trials.summary(store, "stool")


def test_every_edge_of_the_verdict_is_pinned(checked):
    """CALI-86 (#71 rework, items 4 and 7): a test at each edge the reviewer listed, so moving one fails."""
    pr = trials.predict(checked, "stool")
    lo, hi = pr["per_lb_mm"]
    must, breaks = pr["lb"] * pr["factor"], pr["breaks_lb"]
    # what it must hold: at it isn't a fail, one below is
    assert _only(checked, (must, {"broke": True}))["status"] == "warn"
    got = _only(checked, (must - 1, {"broke": True}))
    assert got["status"] == "bad"
    assert got["text"].startswith(f"It broke at {must - 1:,.0f} lb in your test. It had to hold {must:,.0f} (")
    assert got["text"].endswith(f"and we predicted about {breaks:,.0f}.")
    # the prediction: within 10% of it counts as matching it, just under that is too hopeful
    assert _only(checked, (breaks, {"broke": True}))["status"] == "ok"
    assert _only(checked, (0.9 * breaks, {"broke": True}))["status"] == "ok"
    got = _only(checked, (0.9 * breaks - 5, {"broke": True}))
    assert got["status"] == "warn" and got["text"].startswith("It broke sooner than we predicted, so our check was "
                                                              "too hopeful. It still held the 400 lb it must hold")
    assert "(200 lb, twice over for an adult stepping up)" in got["text"]
    # the sag: up to 2x outside the predicted range is fine, past it isn't (the range as the card rounds it)
    # (loaded to what it must hold: a test short of it is a warning whatever the sag, #132 review)
    a, b = round(lo * must, 3), round(hi * must, 3)
    assert _only(checked, (must, {"sag_mm": 2 * b}))["status"] == "ok"
    assert _only(checked, (must, {"sag_mm": 2 * b * 1.01}))["status"] == "warn"
    assert _only(checked, (must, {"sag_mm": a / 2}))["status"] == "ok"
    got = _only(checked, (must, {"sag_mm": a / 2 * 0.99}))
    assert got["status"] == "warn" and "sagged less than we predicted, so it's stiffer than our check said" in got["text"]


def test_every_step_is_judged_and_the_worst_governs(checked):
    """CALI-86 (#71 rework, item 3; #70 #1): only the heaviest step was judged, so a heavier step with no sag hid a
    lighter one that sagged 15x the prediction."""
    pr = trials.predict(checked, "stool")
    lo, hi = pr["per_lb_mm"]
    got = _only(checked, (200, {"sag_mm": hi * 200 * 15}), (400, {}))
    assert got["status"] == "warn" and "at 200 lb it sagged" in got["text"] and "more than we predicted" in got["text"]
    got = _only(checked, (200, {"sag_mm": (lo + hi) / 2 * 200}), (400, {"sag_mm": hi * 400 * 15}))
    assert got["status"] == "warn" and "at 400 lb" in got["text"]


def test_a_failed_test_where_the_break_wasnt_settled_says_so(checked, monkeypatch):
    """CALI-88 (#64 item 13): with no settled prediction (a coarse check), the line says what it had to hold and
    that where it would break wasn't settled, never a number we didn't predict."""
    real = trials.predict
    monkeypatch.setattr(trials, "predict", lambda store, pid: {**real(store, pid), "breaks_lb": None})
    got = _only(checked, (150, {"broke": True}))
    assert got["status"] == "bad" and got["text"].startswith("It broke at 150 lb in your test. It had to hold 400 (")
    assert got["text"].endswith("; where it would break wasn't settled."), got["text"]
