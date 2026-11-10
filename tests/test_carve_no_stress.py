"""CALI-149 (#202) — a real carve of a bracket failed with `float division by zero`. Its load goes straight down through the foot into the
floor that holds it, so the strength check reads no stress at all, and whittle divides by the peak stress. Real FEA: the part is small."""
import pytest

from caliper import carve, load_study as L
from caliper.design import DesignStore

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

BRACKET = """import cadquery as cq

def build(params):
    return cq.Workplane().box(120, 40, 12, centered=(True, True, False)).union(cq.Workplane().box(14, 40, 90, centered=(True, True, False)).translate((-53, 0, 0)))

def construction(params, build=None):
    return [{"name": "body", "kind": "printed", "material": "petg", "infill": 0.4}]

def loads(params, build=None):
    return [{"name": "a push", "lb": 60, "factor": 2.0, "lo": (40, -20, 10), "hi": (60, 20, 12)}]
"""


@pytest.fixture
def bracket(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a bracket", base=str(tmp_path / "designs"))
    s.write_part("p", BRACKET, intent="a bracket")
    L.study(s, "p")
    return s


def test_the_bracket_says_why_it_can_t_be_carved(bracket):
    with pytest.raises(ValueError, match="goes straight into what holds it"):
        carve.study(bracket, "p", stations=2)


def test_the_card_and_the_button_read_the_same_reason(bracket):
    got = L.blocked(bracket, "p")
    assert got["why"] == "no_stress" and got["carve"] == L.NO_STRESS


def test_a_step_that_reads_no_stress_is_said_too(monkeypatch, tmp_path):
    """Should the part as it stands read some stress and a step of the sweep none."""
    from whittle import LoadStudy

    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("a post", base=str(tmp_path / "designs"))
    s.write_part("p", BRACKET.replace('"lo": (40, -20, 10), "hi": (60, 20, 12)', '"lo": (-60, -20, 88), "hi": (-46, 20, 90)'), intent="a post")
    L.study(s, "p")
    assert L.blocked(s, "p") is None or L.blocked(s, "p")["why"] != "no_stress"

    def boom(self, *a, **k):
        raise ZeroDivisionError("float division by zero")

    monkeypatch.setattr(LoadStudy, "sweep", boom)
    with pytest.raises(ValueError, match="Can't carve it"):
        carve.study(s, "p", stations=2)
