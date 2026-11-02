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
