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
    assert line["status"] == "ok" and line["text"].startswith("Tested: it held 400 lb, sagging 0.0")
    assert "we predicted" in line["text"] and line["text"].endswith(" in).")
    work = answers.answers(checked, design_api.design_state(checked), "stool")[1]
    assert any(ln.get("study") == "trial" and ln["text"] == line["text"] for ln in work["lines"])
    # and where it broke
    trials.record(checked, "stool", 1100, broke=True)
    assert trials.summary(checked, "stool")["text"] == (
        f"Tested: it broke at 1,100 lb (we predicted about {pr['breaks_lb']:,.0f}): before we predicted, so the "
        f"check reads strong here.")
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
    assert got["status"] == "bad" and "less than the 400 lb it must hold" in got["text"]
    got = line((must + 50, {"broke": True}))
    assert got["status"] == "warn" and "before we predicted" in got["text"]
    got = line((pr["breaks_lb"] + 50, {"broke": True}))
    assert got["status"] == "ok"
    got = line((200, {"sag_mm": hi * 200 * 15}))
    assert got["status"] == "warn" and "sagged more than we predicted" in got["text"]
    got = line((200, {"sag_mm": lo * 200 / 15}))
    assert got["status"] == "warn" and "sagged less than we predicted" in got["text"]
    got = line((200, {"sag_mm": (lo + hi) / 2 * 200}))
    assert got["status"] == "ok" and "predicted" in got["text"]
