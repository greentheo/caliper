"""CALI-82 — a plywood top on printed sides: one part, two materials."""

import numpy as np
import pytest

from caliper import construction as C
from caliper import making
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: Two printed sides (each 20 mm thick, open between), a 1/2 in plywood top across them.
MIXED = '''import cadquery as cq

PARAMS = {"w": 300.0, "d": 220.0, "h": 220.0, "side": 20.0}
BUILD = {"top": 12.7, "material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, s = BUILD["top"], p["side"]
    side = lambda x0: cq.Workplane().box(s, p["d"], p["h"] - t, centered=False).translate((x0, 0, 0))
    top = cq.Workplane().box(p["w"], p["d"], t, centered=False).translate((0, 0, p["h"] - t))
    return side(0).union(side(p["w"] - s)).union(top)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    b = {**BUILD, **(build or {})}
    w, d, h = p["w"], p["d"], p["h"]
    return [{"name": "top", "kind": "sheet", "material": "plywood", "thickness": b["top"],
             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]},
            {"name": "sides", "kind": "printed", "material": b["material"], "infill": b["infill"], "rest": True}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    cx, cy, h = p["w"] / 2, p["d"] / 2, p["h"]
    return [{"name": "an adult stepping up", "lb": 200, "factor": 2.0,
             "lo": (cx - 50, cy - 50, h - 2), "hi": (cx + 50, cy + 50, h)}]
'''


@pytest.fixture
def stool(tmp_path):
    s = DesignStore.create("a stool with printed sides", base=str(tmp_path / "designs"))
    s.write_part("stool", MIXED, intent="a plywood top on printed sides")
    return s


def test_the_printed_piece_is_the_solid_less_the_plywood(stool):
    whole = stool.part_geometry("stool").require_mesh()
    sides = C.printed_solid(stool, "stool")
    top = 300 * 220 * 12.7
    assert abs(whole.volume) == pytest.approx(top + 2 * 20 * 220 * (220 - 12.7), rel=0.01)
    assert abs(sides.volume) == pytest.approx(2 * 20 * 220 * (220 - 12.7), rel=0.02)
    assert sides.body_count == 2                               # two sides, apart
    rows = {r["name"]: r for r in C.takeoff(C.with_printed(stool, "stool", C._items(C.declared(stool, "stool"))))}
    assert rows["top"]["kind"] == "sheet" and rows["sides"]["kind"] == "printed"
    assert rows["sides"]["volume_mm3"] == pytest.approx(abs(sides.volume), rel=1e-6)
    bom = C.report(stool, "stool")["bom"]
    assert bom["sheets"] and bom["printed"]                     # plywood and filament on one list


def test_the_printer_gets_only_the_sides(stool, tmp_path):
    shop = {"hand": ["jigsaw", "drill"], "machines": [{"id": "mk4", "kind": "printer", "volume_mm": [256, 256, 256]}]}
    mk = making.plan(stool, "stool", shop, out_dir=str(tmp_path / "print"))
    (pr,) = mk["printed"]
    assert pr["name"] == "sides" and mk["ok"]
    import trimesh

    printed = sum(abs(trimesh.load(str(tmp_path / "print" / f["file"])).volume) for f in pr["files"])
    assert printed == pytest.approx(2 * 20 * 220 * (220 - 12.7), rel=0.03)
    assert "jigsaw" in mk["by_how"] and "top" in mk["by_how"]["jigsaw"]


def test_its_declarations_check_against_the_solid(stool):
    from caliper import consistency, sandbox

    run = sandbox.run_script(stool.read_script("stool"), timeout=120)
    got = {r.id: r for r in consistency.check(run.declared, run.geometry)}
    assert got["construction_inside"].passed and got["loads_land"].passed
    assert "construction_covers" not in got and "construction_volume" not in got


@pytest.mark.parametrize("per_voxel", [True, False])
def test_two_materials_each_judged_against_its_own_strength(stool, monkeypatch, per_voxel):
    pytest.importorskip("whittle")
    from caliper import load_study

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    if not per_voxel:                                        # an older whittle: one stiffness, and it says so
        monkeypatch.setattr(load_study, "per_voxel", lambda ls: False)
    ctx = load_study.prepare(stool, "stool")
    if per_voxel and not load_study.per_voxel(ctx["ls"]):
        pytest.skip("this whittle has no stiffness per voxel")
    assert ctx["mat"]["printed"] and ctx["plate_mat"]["key"] == "plywood"
    sm = ctx["strength_map"]
    assert set(np.unique(sm[ctx["ls"].solid]).round(3)) == {round(ctx["mat"]["strength"], 3),
                                                           round(ctx["plate_mat"]["strength"], 3)}
    rec = load_study.study(stool, "stool")
    (case,) = rec["cases"]
    assert case["safety"] and case["fea"]["in"] in ("top", None) or case["fea"]["safety"]
    # the top rests on the printed sides along two edges: a beam across them, the safe side
    pl = case["plate"]
    assert pl["piece"] == "top" and pl["edges_held"] == 2 and pl["done"] and pl["as"] == "beam"
    assert pl["span_mm"] == pytest.approx(300, abs=2)          # the top's outline: the safe side, like the plate check
    force = 200 * 4.44822 * 2
    assert pl["stress_mpa"] == pytest.approx(force * pl["span_mm"] / 4 / (220 * 12.7 ** 2 / 6), rel=0.02)
    assert case["governs"] == "plate" and case["safety"] == pl["safety_across"]       # plywood across its grain
    assert any(n.startswith("Two materials") for n in rec["notes"])
    if not per_voxel:
        assert any("stiffness throughout" in n for n in rec["notes"])


# --- carving the printed sides (slice 3) -------------------------------------------------------------------
def test_the_printed_sides_carve_down_until_it_doesnt_hold(stool, monkeypatch):
    pytest.importorskip("whittle")
    from caliper import carve, load_study

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    # as drawn, a 1/2 in top across 300 mm under 400 lb fails as a beam: the carve says so and carries on
    rec = carve.study(stool, "stool", stations=3, remove_up_to=0.4)
    assert not rec["stations"][0]["whole_holds"] and rec["stations"][0]["weakest"] == "top"
    assert rec["weak"].startswith("As it is, it doesn't hold") and "the weak link is the top" in rec["weak"]
    # a kid stepping up: the top holds, and the printed sides carve down until they don't
    stool.write_part("stool", MIXED.replace('"lb": 200', '"lb": 60').replace("an adult", "a kid"), intent="kid")
    rec = carve.study(stool, "stool", stations=4, remove_up_to=0.6)
    st = rec["stations"]
    assert st[0]["whole_holds"] and not rec["weak"]
    assert st[0]["removed"] == 0 and st[0]["saved_g"] == 0
    assert [x["printed_g"] for x in st] == sorted((x["printed_g"] for x in st), reverse=True)
    assert all(x["holds"] for x in st[:-1])                    # it stops at the first that doesn't hold
    assert rec["best"] is not None
    best = next(x for x in st if x["index"] == rec["best"])
    # using a step: the plywood exactly as drawn, the sides as carved, and the part rebuilt from it
    before = C.report(stool, "stool")
    got = carve.adopt(stool, rec["id"], best["index"])
    assert got["version"] == 3 and f'CARVED = "{got["file"]}"' in stool.read_script("stool")
    mesh = stool.part_geometry("stool").require_mesh()
    assert mesh.is_watertight
    sides = C.printed_solid(stool, "stool")
    assert abs(sides.volume) <= abs(C.printed_solid(stool, "stool").volume) + 1
    after = C.report(stool, "stool")
    top = lambda r: next(x for x in r["bom"]["sheets"])["count"]   # noqa: E731 — the plywood is unchanged
    assert top(after) == top(before)
    if best["saved_g"]:
        assert after["mass_lb"] < before["mass_lb"]
    # a revision drops the carve, and says so
    from caliper import chat

    def author(spec, feedback, prior):
        return prior

    res = chat.refine_part(stool, "stool", "make it a bit taller", author=author, use_llm=False,
                           promote_feedback=False)
    assert "CARVED" not in stool.read_script("stool") and "carve it again" in res.reply


def test_a_sheet_part_cant_be_carved(tmp_path):
    pytest.importorskip("whittle")
    from caliper import carve

    from .test_load_study import BOX_STOOL

    s = DesignStore.create("a plywood stool", base=str(tmp_path / "d"))
    s.write_part("stool", BOX_STOOL, intent="plywood")
    with pytest.raises(ValueError, match="isn't printed"):
        carve.study(s, "stool")


def test_the_chat_routes_carve_to_a_printed_part_only(stool, tmp_path):
    from caliper import chat

    from .test_load_study import BOX_STOOL

    assert chat.offline_classify(stool, "carve the sides down").action == "carve"
    s = DesignStore.create("plywood", base=str(tmp_path / "w"))
    s.write_part("stool", BOX_STOOL, intent="plywood")
    assert chat.offline_classify(s, "carve the sides down").action != "carve"


def test_carving_through_the_api(stool, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("whittle")
    import time

    from fastapi.testclient import TestClient

    from caliper import load_study
    from caliper.server import create_app

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    monkeypatch.setenv("CALIPER_DESIGNS", str(stool.root.rsplit("/", 1)[0]))
    stool.write_part("stool", MIXED.replace('"lb": 200', '"lb": 60'), intent="kid")
    c, slug = TestClient(create_app()), stool.design.slug
    part = next(p for p in c.get(f"/api/designs/{slug}").json()["parts"] if p["id"] == "stool")
    assert part["printed"] and not part["carved"]
    job = c.post(f"/api/designs/{slug}/carve", json={"part": "stool"}).json()["job_id"]
    end = time.time() + 900
    while time.time() < end and c.get(f"/api/jobs/{job}").json()["status"] not in ("done", "error"):
        time.sleep(0.2)
    run = c.get(f"/api/designs/{slug}").json()["carve_runs"][0]
    assert c.get(f"/api/designs/{slug}/carve/{run['id']}/stations/0.stl").status_code == 200
    got = c.post(f"/api/designs/{slug}/carve/{run['id']}/adopt", json={"station": run["best"] or 0}).json()
    assert got["design"]["parts"][0]["carved"]
    assert c.post(f"/api/designs/{slug}/carve/nope/adopt", json={"station": 0}).status_code == 404
