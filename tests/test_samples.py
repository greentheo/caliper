"""CALI-59 (#8) — the sample designs: the stool and the camper, opened as copies with their cards full."""

import json
import os

import pytest

from caliper import samples
from caliper.design import DesignStore


def test_the_stool_and_the_camper_ship_as_samples():
    listed = samples.available()
    assert [x["name"] for x in listed][:2] == ["step-stool", "camper"]          # the small one first
    got = {x["name"]: x for x in listed}
    assert got["step-stool"]["title"] == "Step stool" and got["step-stool"]["parts"] == ["step_stool"]
    assert "cargo_box" in got["camper"]["parts"] and "frame" in got["camper"]["parts"]
    # nobody's home folder rides along
    home = os.path.expanduser("~")
    for here, _, files in os.walk(samples.SAMPLES_DIR):
        for f in files:
            if f.endswith(samples.TEXT):
                with open(os.path.join(here, f), errors="ignore") as fh:
                    assert home not in fh.read(), os.path.join(here, f)


def test_opening_one_copies_it_into_your_designs(tmp_path):
    base = str(tmp_path / "designs")
    a = samples.open_sample("step-stool", base=base)
    b = samples.open_sample("step-stool", base=base)
    assert (a.design.slug, b.design.slug) == ("step-stool", "step-stool-2")
    assert DesignStore.load("step-stool", base=base).design.parts[0].id == "step_stool"
    assert a.log()[-1] == {**a.log()[-1], "kind": "sample", "action": "opened", "sample": "step-stool"}
    # the studies came with it, so its cards read full
    from caliper import load_study, patterns

    assert load_study.list_runs(a, "step_stool") and patterns.list_runs(a, "step_stool")
    # and the sample itself is untouched
    assert DesignStore.load(os.path.join(samples.SAMPLES_DIR, "step-stool")).design.slug != "step-stool-2"
    with pytest.raises(KeyError):
        samples.open_sample("../step-stool", base=base)


def test_saving_one_keeps_the_newest_run_of_each_study_per_part(tmp_path):
    base = str(tmp_path / "designs")
    store = DesignStore.create("a stool", base=base)
    store.write_part("stool", "def build(params):\n    return None\n", intent="a stool")
    for rid in ("20260101-000000-aaaa", "20260102-000000-bbbb"):
        os.makedirs(os.path.join(store.root, "loads", rid))
        with open(os.path.join(store.root, "loads", rid, "run.json"), "w") as f:
            json.dump({"part": "stool", "note": os.path.expanduser("~/x")}, f)
    out = samples.save(store.design.slug, "mine", base=base, out=str(tmp_path / "samples"))
    assert os.listdir(os.path.join(out, "loads")) == ["20260102-000000-bbbb"]
    with open(os.path.join(out, "loads", "20260102-000000-bbbb", "run.json")) as f:
        assert json.load(f)["note"] == "~/x"
    assert [x["name"] for x in samples.available(str(tmp_path / "samples"))] == ["mine"]


@pytest.mark.parametrize("name", ["", "..", "a/b", ".", "Mine", "mine/../.."])
def test_saving_under_a_name_that_isnt_a_plain_slug_is_refused_and_removes_nothing(tmp_path, name):
    """CALI-86 (#62, finding 4): `caliper sample save` with no name removed the whole samples folder."""
    base = str(tmp_path / "designs")
    store = DesignStore.create("a stool", base=base)
    store.write_part("stool", "def build(params):\n    return None\n", intent="a stool")
    out = tmp_path / "area" / "samples"
    (out / "step-stool").mkdir(parents=True)
    (out / "step-stool" / "design.yaml").write_text("kept")
    with pytest.raises(ValueError, match="plain name"):
        samples.save(store.design.slug, name, base=base, out=str(out))
    assert (out / "step-stool" / "design.yaml").read_text() == "kept"
    assert sorted(os.listdir(out)) == ["step-stool"]


@pytest.mark.parametrize("name", ["..", ".", "", "a/b", "step-stool/..", "../step-stool"])
def test_opening_a_name_that_isnt_a_sample_is_refused(tmp_path, name):
    """CALI-86 (#62, finding 12): os.path.basename("..") is "..", so open_sample("..") copied Caliper's package."""
    base = tmp_path / "designs"
    with pytest.raises(KeyError):
        samples.open_sample(name, base=str(base))
    assert not base.exists() or os.listdir(base) == []


@pytest.mark.parametrize("name", ["%2E%2E", "%2E", "a%2Fb"])
def test_the_api_refuses_them_too(tmp_path, monkeypatch, name):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    base = tmp_path / "designs"
    monkeypatch.setenv("CALIPER_DESIGNS", str(base))
    got = TestClient(create_app()).post(f"/api/samples/{name}")
    assert got.status_code in (404, 405), got.status_code
    assert not base.exists() or os.listdir(base) == []


def test_the_camper_s_verdicts_carry_the_promise(tmp_path):
    """CALI-86 (#62, finding 13): a strength verdict always says what it promises, and the camper's scorecard
    verdicts ("safe to tow") rest on the frame's model as much as a load study's do."""
    from caliper import answers, design_api

    store = samples.open_sample("camper", base=str(tmp_path / "designs"))
    work = answers.answers(store, design_api.design_state(store), None)[1]
    assert any(ln["status"] in ("ok", "bad") and ln["text"][:1] in "✓✗" for ln in work["lines"]), work["lines"]
    # worded for what it's made of (#64 item 14): steel, foam and plywood, not "Real wood" alone
    assert work.get("promise") == answers.promise(store, [p.id for p in store.design.parts])
    assert work["promise"] != answers.PROMISE and "materials" in work["promise"], work["promise"]


def test_a_save_that_fails_leaves_the_old_sample_whole(tmp_path):
    """CALI-86 (#69 rework, item 4): save() removed the sample before copying, so a design with no parts/ saved over
    step-stool left only three files and lost its loads, patterns and cut plans."""
    import shutil

    out = tmp_path / "samples"
    shutil.copytree(os.path.join(samples.SAMPLES_DIR, "step-stool"), out / "step-stool")
    before = sorted(os.listdir(out / "step-stool"))
    base = str(tmp_path / "designs")
    store = DesignStore.create("no parts", base=base)
    shutil.rmtree(os.path.join(store.root, "parts"), ignore_errors=True)
    with pytest.raises(OSError):
        samples.save(store.design.slug, "step-stool", base=base, out=str(out))
    assert sorted(os.listdir(out / "step-stool")) == before
    assert sorted(os.listdir(out)) == ["step-stool"]                   # and no half-made folder beside it


def test_each_sample_guard_refuses_on_its_own(tmp_path):
    """CALI-86 (#71 rework, item 10): a plain name that isn't a sample, and a sample whose folder name isn't plain."""
    import shutil

    base = tmp_path / "designs"
    with pytest.raises(KeyError):                         # plain, but not one of the samples there are
        samples.open_sample("nosuch", base=str(base))
    root = tmp_path / "samples"
    shutil.copytree(os.path.join(samples.SAMPLES_DIR, "step-stool"), root / "Step_Stool")
    assert [x["name"] for x in samples.available(str(root))] == ["Step_Stool"]
    with pytest.raises(KeyError):                         # one of them, but not a plain name
        samples.open_sample("Step_Stool", base=str(base), root=str(root))
    assert not base.exists() or os.listdir(base) == []


def test_an_unknown_sample_is_a_404_with_no_path(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    got = TestClient(create_app(), raise_server_exceptions=False).post("/api/samples/nosuch")
    assert got.status_code == 404 and "/" not in got.json()["detail"]
