"""CALI-149 (#202) — a real carve of a bracket failed with `float division by zero`. The strength check saw no stress in its 12 mm foot, because the
load sits straight over the floor that holds it and the foot is thin against the voxels. Loaded half way along, the same foot read 54,956,221
times over and "Holds". Real FEA where it says: the parts are small."""
import pytest

from caliper import answers, carve, design_api, load_study as L, verdicts
from caliper.design import DesignStore

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

_PART = """import cadquery as cq

def build(params):
    return cq.Workplane().box(120, 40, FOOT, centered=(True, True, False)).union(cq.Workplane().box(14, 40, 90, centered=(True, True, False)).translate((-53, 0, 0)))

def construction(params, build=None):
    return [{"name": "body", "kind": "printed", "material": "petg", "infill": 0.4}]

def loads(params, build=None):
    return [LOADS]
"""
AT_THE_END = '{"name": "a push", "lb": 60, "factor": 2.0, "lo": (40, -20, 10), "hi": (60, 20, 12)}'
HALF_WAY = '{"name": "a push", "lb": 60, "factor": 2.0, "lo": (-10, -20, 10), "hi": (10, 20, 12)}'
ON_THE_UPRIGHT = '{"name": "a shove", "lb": 20, "factor": 2.0, "lo": (-60, -20, 88), "hi": (-46, 20, 90), "dir": (1, 0, 0)}'


def _part(tmp_path, monkeypatch, loads, foot=12):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a bracket", base=str(tmp_path / "designs"))
    s.write_part("p", _PART.replace("FOOT", str(foot)).replace("LOADS", loads), intent="a bracket")
    return s, L.study(s, "p")


def test_the_bracket_says_why_it_can_t_be_carved_before_it_sweeps(tmp_path, monkeypatch):
    from whittle import LoadStudy

    s, _ = _part(tmp_path, monkeypatch, AT_THE_END)

    def no(self, *a, **k):
        raise AssertionError("it spent the sweep to reach the same refusal")

    monkeypatch.setattr(LoadStudy, "sweep", no)
    with pytest.raises(ValueError, match="couldn't see any stress"):
        carve.study(s, "p", stations=2)


def test_the_words_name_both_things_to_look_at(tmp_path, monkeypatch):
    s, _ = _part(tmp_path, monkeypatch, AT_THE_END)
    got = L.blocked(s, "p")
    assert got["why"] == "no_stress" and "too thin for its voxels" in got["carve"] and "go straight into what holds it" in got["carve"]
    assert "patch may be smaller than the voxels" in got["carve"]


def test_the_foot_loaded_half_way_isn_t_holds(tmp_path, monkeypatch):
    """54,956,221 times over: noise over nothing."""
    s, run = _part(tmp_path, monkeypatch, HALF_WAY)
    v = verdicts.run(run)
    assert v["kind"] == "unresolved" and not v["counts_as_pass"]
    assert L.blocked(s, "p")["why"] == "no_stress"
    work = next(c for c in answers.part(s, design_api.design_state(s), "p") if c["key"] == "work")
    text = " ".join(ln["text"] for ln in work["lines"])
    assert "Holds" not in text and "couldn't see any stress" in text and not [ln for ln in work["lines"] if ln.get("action") == "carve" and not ln.get("disabled")]


def test_a_thicker_foot_reads_as_it_did(tmp_path, monkeypatch):
    s, run = _part(tmp_path, monkeypatch, AT_THE_END.replace("10)", "18)").replace("12)", "20)"), foot=20)
    assert not any(L.blind(run, c) for c in run["cases"]) and (L.blocked(s, "p") or {}).get("why") != "no_stress"


def test_one_case_that_read_stress_is_enough_to_carve_by():
    run = {"material": {"strength": 30.0}, "cases": [_case(None), _case(20.0)]}
    assert [L.blind(run, c) for c in run["cases"]] == [True, False]


def _case(safety, lb=120.0, area=(40, 20)):
    return {"force_n": [0, 0, -lb * 4.448], "lo": [0, 0, 10], "hi": [area[0], area[1], 12], "governs": "fea",
            "fea": {"supported": True, "safety": safety}, "safety": safety, "holds": True}


def _blocked_on(monkeypatch, cases):
    run = {"material": {"strength": 30.0}, "cases": cases}
    monkeypatch.setattr(L, "already_fails", lambda *a: None)
    monkeypatch.setattr(L, "default_check", lambda *a: run)
    return L.blocked(None, "p")


def test_blocked_only_when_no_case_read_stress(monkeypatch):
    assert _blocked_on(monkeypatch, [_case(None), _case(20.0)]) is None
    assert _blocked_on(monkeypatch, [_case(None), _case(5.0e7)])["why"] == "no_stress"


@pytest.mark.parametrize("safety,lb,seen", [(5.5e7, 120.0, False), (20.0, 120.0, True),
                                            (4705.0, 0.1, True)])          # a tiny load, a real low stress: its number is fine
def test_it_goes_by_the_load_s_own_stress_not_the_safety_factor(safety, lb, seen):
    run = {"material": {"strength": 30.0}}
    assert L.blind(run, _case(safety, lb=lb)) is (not seen)


def test_a_case_the_plate_check_decides_isn_t_judged_by_this():
    c = {**_case(None), "governs": "plate"}
    assert not L.blind({"material": {"strength": 30.0}}, c)


def test_a_case_that_never_reached_a_support_is_its_own_verdict():
    c = _case(None)
    c["fea"]["supported"] = False
    assert not L.blind({"material": {"strength": 30.0}}, c)


def test_a_step_that_reads_no_stress_says_so_in_its_own_words(monkeypatch, tmp_path):
    """The part as drawn read stress and a step of the sweep didn't: the load isn't the thing to blame."""
    from whittle import LoadStudy

    s, _ = _part(tmp_path, monkeypatch, ON_THE_UPRIGHT)
    assert (L.blocked(s, "p") or {}).get("why") != "no_stress"

    def boom(self, *a, **k):
        raise ZeroDivisionError("float division by zero")

    monkeypatch.setattr(LoadStudy, "sweep", boom)
    with pytest.raises(ValueError, match="a step of the carve read no stress"):
        carve.study(s, "p", stations=2)


def test_the_disabled_line_doesn_t_quote_a_time_first():
    src = open(__import__("caliper.better", fromlist=["x"]).__file__).read()
    assert '"" if blocked["why"] == "no_stress" else takes' in src


# --- the second round -------------------------------------------------------------------------------------------------------
def test_the_real_foot_reads_a_huge_number_and_the_card_doesn_t_hang(tmp_path, monkeypatch):
    import time

    from caliper import trials

    s, run = _part(tmp_path, monkeypatch, HALF_WAY)
    assert run["cases"][0]["safety"] and run["cases"][0]["safety"] > 1e6       # the case the review found: a number, and an absurd one
    assert trials.predict(s, "p") is None
    t = time.time()
    answers.part(s, design_api.design_state(s), "p")
    assert time.time() - t < 60


@pytest.mark.parametrize("breaks,most", [(1e10, 41), (5000, 41), (220, 5)])
def test_a_test_plan_is_never_longer_than_a_person_could_do(tmp_path, monkeypatch, breaks, most):
    import json
    import os

    from caliper import trials

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("x", base=str(tmp_path / "designs"))
    s.write_part("p", _PART.replace("FOOT", "12").replace("LOADS", AT_THE_END), intent="x")
    d = os.path.join(L.runs_dir(s), "r")
    os.makedirs(d)
    fea = {"supported": True, "deflection_mm": 1.5, "safety": 5.0, "wall_mm": 12.0, "at": [0, 0, 5], "in": "body", "peak_mpa": 5.0}
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r", "part": "p", "version": 1, "created": 1.0, "safety": 5.0, "min_safety": 2.0, "spacing_mm": 3.0, "thinnest_mm": 12.0, "across": 4.0,
                   "material": {"strength": 30.0}, "cases": [{"name": "x", "lb": 100, "factor": 2.0, "safety": 5.0, "holds": True, "governs": "fea", "breaks_lb": breaks,
                                                              "force_n": [0, 0, -889], "lo": [0, 0, 0], "hi": [40, 40, 2], "fea": fea}]}, f)
    assert len(trials.predict(s, "p")["steps"]) <= most


def test_an_unresolved_number_isn_t_planned_up_to(tmp_path, monkeypatch):
    """Too coarse to see its walls: the steps go by the load applied, not by a breaking load nobody can read."""
    import json
    import os

    from caliper import trials

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("x", base=str(tmp_path / "designs"))
    s.write_part("p", _PART.replace("FOOT", "12").replace("LOADS", AT_THE_END), intent="x")
    d = os.path.join(L.runs_dir(s), "r")
    os.makedirs(d)
    fea = {"supported": True, "deflection_mm": 1.5, "safety": 20.0, "wall_mm": 12.0, "at": [0, 0, 5], "in": "body", "peak_mpa": 1.0}
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"id": "r", "part": "p", "version": 1, "created": 1.0, "safety": 20.0, "min_safety": 2.0, "spacing_mm": 5.0, "thinnest_mm": 1.0, "across": 0.2, "finer": True,
                   "material": {"strength": 30.0}, "cases": [{"name": "x", "lb": 100, "factor": 2.0, "safety": 20.0, "holds": True, "governs": "fea", "breaks_lb": 4000,
                                                              "force_n": [0, 0, -889], "lo": [0, 0, 0], "hi": [40, 40, 2], "fea": fea}]}, f)
    got = trials.predict(s, "p")
    assert got["breaks_lb"] is None and max(st["lb"] for st in got["steps"]) <= 400


@pytest.mark.parametrize("loads", [AT_THE_END, HALF_WAY], ids=["no number", "a huge number"])
def test_one_reason_on_the_card_and_the_scorecard(tmp_path, monkeypatch, loads):
    from caliper import goals, scorecard

    s, _ = _part(tmp_path, monkeypatch, loads)
    goals.write(s, {"checks": [{"id": "h", "label": "holds it", "metric": "strength.safety", "op": ">=", "limit": 2, "source": "assumed"}]})
    state = design_api.design_state(s)
    (line,) = [ln for ln in answers.held_to(state, answers.measured(s, state)) if "holds it" in ln["text"].lower()]
    assert "couldn't see any stress" in line["text"] and "Check it holds." not in line["text"] and "✓" not in line["text"]
    work = next(c for c in answers.part(s, state, "p") if c["key"] == "work")
    assert any(ln["text"].startswith("! A push: Not resolved: the check couldn't see any stress") for ln in work["lines"])
    card = scorecard.compute(s)
    (c,) = [x for x in card["checks"] if x["id"] == "h"]
    assert c["status"] == "unresolved" and c["trust"] == scorecard.NOT_SEEN and "couldn't see any stress" in c["note"] and "too coarse" not in c["trust"]


def test_the_book_gives_the_same_reason():
    from caliper import release

    got = release._safety_cell({"safety": 5e7, "breaks_lb": 1e9, "verdict": {"kind": "unresolved", "blind": True}})
    assert got == ("not resolved: the check couldn't see any stress", "—")


def test_the_verdict_marks_it():
    run = {"material": {"strength": 30.0}, "cases": []}
    assert verdicts.case(run, _case(5.5e7))["blind"] is True


def test_a_blind_load_is_named_beside_a_real_one(tmp_path, monkeypatch):
    s, run = _part(tmp_path, monkeypatch, AT_THE_END + ", " + ON_THE_UPRIGHT)
    assert [L.blind(run, c) for c in run["cases"]] == [True, False] and verdicts.run(run)["kind"] == "unresolved"
    work = next(c for c in answers.part(s, design_api.design_state(s), "p") if c["key"] == "work")
    assert any(ln["text"].startswith("! A push: Not resolved") for ln in work["lines"])


@pytest.mark.parametrize("share,seen", [(0.0099, False), (0.0101, True), (0.5, True), (0.00002, False)])
def test_the_line_is_one_percent_of_the_load_s_own_stress(share, seen):
    c, strength = _case(1.0), 30.0
    nominal = L._nominal(c)
    c["fea"]["safety"] = strength / (share * nominal)
    assert L.blind({"material": {"strength": strength}}, c) is (not seen)


def test_blind_counts_as_unresolved():
    assert L.unresolved({"material": {"strength": 30.0}}, _case(5.5e7)) is True


def test_the_card_s_words_are_the_blind_ones():
    run = {"material": {"strength": 30.0}, "cases": [_case(5.5e7)]}
    assert answers.coarse(run) == L.BLIND


def test_a_case_that_doesn_t_say_isn_t_one_that_saw_nothing():
    """Every real run writes the FEA's safety, None where it read no stress. A record without it says nothing either way."""
    c = _case(None)
    del c["fea"]["safety"]
    assert not L.blind({"material": {"strength": 30.0}}, c)
    assert L.blind({"material": {"strength": 30.0}}, _case(None))


def test_a_safety_that_rounds_to_nothing_is_a_part_that_broke():
    """Zero is the opposite of a check that saw nothing: the stress was so high the number rounded away."""
    run = {"material": {"strength": 30.0}, "min_safety": 2.0, "cases": []}
    c = {**_case(0.0), "holds": False}
    assert not L.blind(run, c) and verdicts.case(run, c)["kind"] == "fails"


def test_the_bracket_under_a_huge_shove_reads_as_the_fail_it_is(tmp_path, monkeypatch):
    """Real FEA: a load big enough that the safety rounds to 0.00, which raised ZeroDivisionError out of the study."""
    s, run = _part(tmp_path, monkeypatch, ON_THE_UPRIGHT.replace('"lb": 20', '"lb": 2000000'))
    c = run["cases"][0]
    assert c["fea"]["safety"] == 0.0 and not L.blind(run, c)
    assert verdicts.run(run)["kind"] == "fails" and L.blocked(s, "p")["why"] == "already_fails"

