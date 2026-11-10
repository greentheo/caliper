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
HALF_WAY = '{"name": "a push", "lb": 60, "factor": 2.0, "lo": (0, -20, 10), "hi": (20, 20, 12)}'
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
    assert got["why"] == "no_stress" and "too thin for its voxels" in got["carve"] and "goes straight into what holds it" in got["carve"]


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
