"""CALI-70 — every study a design has, in one list, and what each part could have next."""

import datetime as dt

from caliper import studies
from caliper.design import DesignStore

BOX = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box(10, 10, 10)\n")


def _iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()


def test_a_run_knows_the_version_it_saw_even_when_it_didnt_record_one():
    history = [{"kind": "revision", "version": 1, "ts": _iso(100)}, {"kind": "load", "ts": _iso(150)},
               {"kind": "revision", "version": 2, "ts": _iso(200)}]
    assert studies.version_at(history, 50) == 1           # before any revision: the first
    assert studies.version_at(history, 150) == 1
    assert studies.version_at(history, 250) == 2
    assert studies.version_at(history, None) is None


def test_every_run_is_listed_newest_first_with_what_it_came_to(tmp_path):
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX, intent="a stool")
    parts = [{"id": "stool", "version": 2, "scripted": True, "built": True, "loads": True}]
    runs = {
        "load": [{"id": "L1", "part": "stool", "created": 300, "version": 2, "holds": True, "min_safety": 2,
                  "cases": [{"name": "me stepping up", "safety": 3.1}, {"name": "sitting", "safety": 8}]}],
        "cutplan": [{"id": "C1", "part": "stool", "created": 200, "version": 1,
                     "sheets": [{"sheets": 1, "utilisation": 0.12}]}],
        "scorecard": [{"created": 100, "versions": {"stool": 1}, "summary": {"pass": 3, "fail": 1}}],
    }
    got = studies.index(s, runs, parts)
    load, cut, card = got["runs"]
    assert (load["kind"], cut["kind"], card["kind"]) == ("load", "cutplan", "scorecard")
    assert load["headline"] == "holds — weakest me stepping up: 3.1x" and load["ok"] is True
    assert load["stale"] is False and cut["stale"] is True and cut["version"] == 1
    assert cut["headline"] == "1 sheet(s), 12% used"
    assert card["headline"] == "3 pass · 1 fail" and card["ok"] is False and card["stale"] is True


def test_a_failing_strength_check_says_what_it_needed():
    head, ok = studies._headline("load", {"holds": False, "min_safety": 2,
                                          "cases": [{"name": "books", "safety": 1.4}]})
    assert head == "doesn't hold — weakest books: 1.4x (needs 2x)" and ok is False


def test_the_menu_says_why_a_study_cant_run_yet():
    stool = {"id": "stool", "scripted": True, "built": True, "loads": False, "params": {"w": 1}}
    menu = {m["kind"]: m for m in studies.menu(stool)}
    assert not menu["load"]["ready"] and "loads()" in menu["load"]["why"]
    assert menu["cutplan"]["ready"] and menu["aero"]["ready"]
    assert not menu["frame"]["ready"] and "tube frame" in menu["frame"]["why"]

    frame = {"id": "frame", "scripted": True, "framed": True, "built": True, "gussets": ["corner"]}
    menu = {m["kind"]: m for m in studies.menu(frame)}
    assert menu["frame"]["ready"] and menu["gussets"]["ready"]
    assert not menu["load"]["ready"] and "frame sizing" in menu["load"]["why"]
    assert not menu["aero"]["ready"]

    mesh = {"id": "box", "scripted": False, "built": False}
    assert "roll it back" in {m["kind"]: m for m in studies.menu(mesh)}["cutplan"]["why"]

    car = {"id": "car", "role": "fixed", "scripted": False}
    assert all(not m["ready"] and "reference" in m["why"] for m in studies.menu(car))


class _Design:
    def __init__(self, prompt, requirements=()):
        self.prompt = prompt
        self.requirements = [type("R", (), {"question": q, "answer": a})() for q, a in requirements]


def test_drag_studies_are_offered_only_to_what_moves_through_air():
    """CALI-67: a bathroom stool isn't asked about 65 mph; a cargo box on a hitch is."""
    stool = _Design("A step stool so my 6-year-old can reach the bathroom sink, from 3/4 in plywood",
                    [("Where will it live?", "next to the towel rack, by the window")])
    air = studies.in_air(stool, [{"id": "step_stool", "intent": "a plywood step stool"}])
    assert not air["yes"] and "moves through air" in air["why"]
    part = {"id": "step_stool", "scripted": True, "built": True, "params": {"w": 1}}
    menu = {m["kind"]: m for m in studies.menu(part, air)}
    assert not menu["aero"]["ready"] and not menu["whittle"]["ready"]
    assert menu["aero"]["why"] == air["why"] and menu["cutplan"]["ready"]

    box = _Design("a cargo box on my car's trailer hitch, 74 in wide")
    assert studies.in_air(box, [])["yes"]
    turbine = _Design("a vertical-axis wind turbine for the garden")
    assert studies.in_air(turbine, [])["yes"]
    behind = studies.in_air(_Design("a box"), [{"id": "car", "role": "fixed"}])
    assert behind == {"yes": True, "why": "it rides behind car"}
    assert studies.in_air(_Design("a box"), [], has_runs=True)["yes"]
