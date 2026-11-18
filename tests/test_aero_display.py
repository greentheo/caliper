"""CALI-201 (#330): Shape it for drag says its numbers as they are, and what's in use.

reviewer-2's aero walk on a copy of the camper sample:
- the results table rounded every number to a whole one, so a shoulder of 1–2.5 read "1" on all four designs;
- the range boxes showed float noise ("833.1200000000001");
- "volume" was said to be against the part as it stands, and stayed so after Use, with design 3 still offered;
- two runs read alike but for their build count;
- "Values in mm" beside inches; "station 3" in the history where the card says "design 3"; Use wrote 1.1 for a
  scored 1.061."""

import json
import os

import pytest

from caliper import aero
from caliper.design import DesignStore

from .test_aero import SCRIPT
from .test_carve_click import _fn, _page, _run

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


# --- the numbers: one rule for what's shown and what's written ---------------------------------------------------------

def test_a_searched_number_s_places_follow_its_range():
    assert aero.places(1, 2.5) == 2                 # the shoulder: 1.06, not 1
    assert aero.places(0, 600) == 1                 # a tail: 0.1 mm, as fine as foam board holds
    assert aero.places(0, 90) == aero.places(0, 50) == aero.places(0, 100) == 1
    assert aero.places(0, 5) == 2 and aero.places(0, 0.5) == 3 and aero.places(0, 0.01) == 3
    assert aero.places(2, 2) == 1


def test_suggested_ranges_are_tidy_numbers():
    """41 in across, 1041.4 mm: its range read 833.1200000000001 to 1249.68."""
    got = aero.suggest("width", 1041.4)["bounds"]
    assert got == [833.12, 1249.68] and json.dumps(got) == "[833.12, 1249.68]"
    assert aero.suggest("nose_r", 391.16)["bounds"] == [5.0, 1564.64]
    assert aero.suggest("width", 1041.4, {"width": (800.0000000000001, 1300)})["bounds"][0] == 800.0


@pytest.fixture
def ran(tmp_path):
    """A box and a run on it, as a study writes it: tail_drop searched over 0–1.5, so its places are 2."""
    store = DesignStore.create("a tunable box", base=str(tmp_path / "designs"))
    store.write_part("box", SCRIPT, intent="a box with a tunable tail")
    rec = {"id": "r1", "part": "box", "kind": "parametric", "created": 1795450000.0,
           "bounds": {"tail_len": [0, 90], "tail_drop": [0, 1.5]}, "start": aero.read_params(SCRIPT),
           "searched": ["tail_len", "tail_drop"], "script_sig": aero.shape_signature(SCRIPT), "notes": [],
           "obstacles": [], "builds": 40, "seconds": 3,
           "stations": [{"index": 0, "removed": 0.0, "metrics": {"drag": 1.0}, "design": {"tail_len": 0.0, "tail_drop": 0.0}},
                        {"index": 1, "removed": 0.05, "metrics": {"drag": 0.9},
                         "design": {"tail_len": 40.04, "tail_drop": 1.0612}}]}
    os.makedirs(os.path.join(aero.runs_dir(store), "r1"))
    with open(os.path.join(aero.runs_dir(store), "r1", "run.json"), "w") as f:
        json.dump(rec, f)
    return store


def test_a_run_says_each_design_as_use_writes_it(ran):
    rec = aero.load_run(ran, "r1")
    assert rec["places"] == {"tail_len": 1, "tail_drop": 2}
    assert [s["uses"] for s in rec["stations"]] == [{"tail_len": 0.0, "tail_drop": 0.0}, {"tail_len": 40.0, "tail_drop": 1.06}]
    assert rec["stations"][1]["design"]["tail_drop"] == 1.0612                   # what was scored, kept


def test_use_writes_what_the_table_shows_and_the_history_says_design(ran):
    pytest.importorskip("cadquery")
    got = aero.adopt(ran, "r1", 1)
    assert got["params"] == {"tail_len": 40.0, "tail_drop": 1.06}                # 1.1 before
    assert aero.read_params(ran.read_script("box"))["tail_drop"] == 1.06
    said = [h for h in ran.history("box") if h.get("aero_run") == "r1"][-1]
    assert "shaped for drag: design 1 (" in said["feedback"] and "station" not in said["feedback"]


def test_a_study_records_what_it_started_from_and_how_hard_it_looked(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("whittle")
    from .test_aero import _quick

    store = DesignStore.create("a tunable box", base=str(tmp_path / "designs"))
    store.write_part("box", SCRIPT, intent="a box with a tunable tail")
    said = []
    rec = _quick(store, emit=lambda k, t="", **d: said.append((k, t)))
    assert rec["version"] == store.design.part("box").version and rec["effort"] == 0.05
    steps = [t for k, t in said if k == "station"]
    assert steps and all(t.startswith("design ") for t in steps)


# --- the page ----------------------------------------------------------------------------------------------------------

PAGE = """
const S = { station: null, aeroRun: {} };
const inches = () => true;
const run = { id: 'r1', kind: 'parametric', searched: ['shoulder', 'tail_len'], version: 3, effort: 0.6, builds: 1440,
  created: 1795450000, seconds: 300, obstacles: [], notes: [], places: { shoulder: 2, tail_len: 1 },
  stations: [0, 1, 2, 3].map((i) => ({ index: i, removed: -0.05 * i, metrics: { drag: 1 - 0.05 * i },
    design: { shoulder: [1.4, 1.329, 1.026, 1.0612][i], tail_len: [0, 300.04, 412.55, 500][i] },
    uses: { shoulder: [1.4, 1.33, 1.03, 1.06][i], tail_len: [0, 300, 412.6, 500][i] } })) };
"""


def _aero(body):
    return _run(_page(["aeroResults", "aeroLabel", "aeroWhen", "aeroUses", "aeroInUse", "aeroNum", "aeroSame"],
                      consts=["pct", "fixed", "esc", "AERO_EFFORT"], extra=PAGE + body))


def test_the_table_says_each_number_to_its_range_s_places():
    html = _aero("out = aeroResults({ id: 'cargo_box', params: { shoulder: 1.4, tail_len: 0 } }, run, [run]);")
    import re

    rows = [re.findall(r"<td>([^<]*)</td>", r.split("</tr>", 1)[0])[-2:] for r in html.split('data-ast="')[1:]]
    assert rows == [["1.40", "0.0"], ["1.33", "300.0"], ["1.03", "412.6"], ["1.06", "500.0"]]   # "1" on every design before


def test_the_design_in_use_is_marked_and_volume_is_against_the_part_the_search_started_from():
    before = _aero("out = aeroResults({ id: 'cargo_box', params: { shoulder: 1.4, tail_len: 0 } }, run, [run]);")
    after = _aero("out = aeroResults({ id: 'cargo_box', params: { shoulder: 1.06, tail_len: 500 } }, run, [run]);")
    rows = lambda html: [r.split("</td>", 1)[0] for r in html.split('data-ast="')[1:]]   # noqa: E731
    assert ["in use" in r for r in rows(before)] == [True, False, False, False]
    assert ["in use" in r for r in rows(after)] == [False, False, False, True]
    assert "the change against the part this\n      search started from (v3)" in after and "as it stands" not in after
    assert "“in use” is the design the part has now" in after
    elsewhere = _aero("out = aeroResults({ id: 'cargo_box', params: { shoulder: 2, tail_len: 10 } }, run, [run]);")
    assert "in use" not in elsewhere                              # its own numbers since: no design is
    half = _aero("out = aeroResults({ id: 'cargo_box', params: { shoulder: 1.06, tail_len: 10 } }, run, [run]);")
    assert "in use" not in half                                   # design 3's shoulder, but not its tail: every number


def test_a_run_s_label_says_how_hard_it_searched_and_when():
    got = _aero("""out = [aeroLabel(run), aeroLabel({ ...run, effort: 1 }), aeroLabel({ ...run, effort: 0.45 }),
                       aeroLabel({ ...run, effort: undefined, created: undefined })];""")
    assert got[0].startswith("searched · 2 numbers · normal search · 1440 builds · ")
    import re

    assert re.search(r" · [A-Z][a-z]{2} \d{1,2} \d\d:\d\d$", got[0])
    assert "thorough search" in got[1] and "effort 0.45 search" in got[2]
    assert got[3] == "searched · 2 numbers · 1440 builds"           # a run from before says what it has


def test_the_bar_says_a_design_in_use_and_doesn_t_offer_it_again():
    got = _run(_page(["stationAction", "aeroUses", "aeroInUse"], consts=["esc"], extra=PAGE + """
let params = { shoulder: 1.06, tail_len: 500 };
const partOf = () => ({ version: 7, params });
const holdsHere = () => true;
out = { used: stationAction('cargo_box', run, 3, run.stations[3]), other: stationAction('cargo_box', run, 2, run.stations[2]) };"""))
    assert 'id="inUse"' in got["used"] and "In use: cargo_box v7 has these numbers." in got["used"]
    assert "adoptBtn" not in got["used"]
    assert 'id="adoptBtn"' in got["other"] and "Use these numbers for cargo_box" in got["other"]


def test_the_search_table_says_its_numbers_are_the_script_s():
    view = _fn(open(JS).read(), "aeroView")
    assert "Values in mm" not in view
    assert "The script's own numbers: lengths in mm, angles in degrees, whatever units\n      the rest shows." in view


# --- #341 review: design 0 is the part; a rounded number stays inside its range -----------------------------------------

def test_a_number_left_at_the_part_s_own_keeps_it_as_the_part_has_it():
    """15.25 in is 387.35 mm: design 0 read 387.4, wasn't in use, and Use on it wrote v15 with 387.4."""
    rec = {"searched": ["nose_len", "shoulder"], "bounds": {"nose_len": [0, 400], "shoulder": [1, 2.5]},
           "start": {"nose_len": 387.35, "shoulder": 1.4}}
    assert aero.uses(rec, {"design": {"nose_len": 387.35, "shoulder": 1.4}}) == {"nose_len": 387.35, "shoulder": 1.4}
    moved = aero.uses(rec, {"design": {"nose_len": 380.3721, "shoulder": 1.4}})
    assert moved == {"nose_len": 380.4, "shoulder": 1.4}                       # what moved is to its places


def test_a_rounded_number_never_lands_outside_its_range():
    """The sample's own width range, 1564.64–2346.96, wrote 1564.6 at its low end and 2347.0 at its high end."""
    rec = {"searched": ["width"], "bounds": {"width": [1564.64, 2346.96]}, "start": {"width": 2000.0}}
    at = lambda x: aero.uses(rec, {"design": {"width": x}})["width"]       # noqa: E731
    assert (at(1564.64), at(1564.6400001), at(2346.96), at(2346.9599)) == (1564.7, 1564.7, 2346.9, 2346.9)
    assert at(2000.04) == 2000.0 and at(1700.06) == 1700.1                     # inside: to its places, as before
    assert aero._inward(6.35, 6.35, 25.4, 1) == 6.4 and aero._inward(0.07, 0.07, 0.5, 2) == 0.07   # 1/4 in; 0.07 × 100 is 7.000000000000001
    assert aero._inward(1.0402, 1.0401, 1.0404, 3) == 1.0402                   # nothing of 3 places fits: as it is


def test_use_on_design_0_of_a_part_in_inches_writes_its_own_numbers(tmp_path):
    pytest.importorskip("cadquery")
    script = SCRIPT.replace('"tail_len": 0.0,   # 0 = square back', '"tail_len": 38.35,   # 0 = square back')
    store = DesignStore.create("an inch box", base=str(tmp_path / "designs"))
    store.write_part("box", script, intent="a box with a tunable tail")
    start = aero.read_params(script)
    rec = {"id": "r1", "part": "box", "kind": "parametric", "created": 1795450000.0,
           "bounds": {"tail_len": [0, 90], "tail_drop": [0, 50]}, "start": start, "searched": ["tail_len", "tail_drop"],
           "script_sig": aero.shape_signature(script), "notes": [], "obstacles": [], "builds": 9, "seconds": 1,
           "stations": [{"index": 0, "removed": 0.0, "metrics": {"drag": 1.0},
                         "design": {"tail_len": 38.35, "tail_drop": 0.0}}]}
    os.makedirs(os.path.join(aero.runs_dir(store), "r1"))
    with open(os.path.join(aero.runs_dir(store), "r1", "run.json"), "w") as f:
        json.dump(rec, f)
    assert aero.load_run(store, "r1")["stations"][0]["uses"] == {"tail_len": 38.35, "tail_drop": 0.0}
    assert aero.adopt(store, "r1", 0)["params"]["tail_len"] == 38.35
    assert aero.read_params(store.read_script("box"))["tail_len"] == 38.35       # 38.4 before


INCH = """
const inch = { ...run, searched: ['nose_len', 'shoulder'], places: { nose_len: 1, shoulder: 2 }, stations: [
  { index: 0, removed: 0, metrics: { drag: 1 }, design: { nose_len: 387.35, shoulder: 1.4 }, uses: { nose_len: 387.35, shoulder: 1.4 } },
  { index: 1, removed: -0.05, metrics: { drag: 0.9 }, design: { nose_len: 380.37, shoulder: 1.371 }, uses: { nose_len: 380.4, shoulder: 1.37 } },
  { index: 2, removed: -0.06, metrics: { drag: 0.88 }, design: { nose_len: 380.41, shoulder: 1.429 }, uses: { nose_len: 380.4, shoulder: 1.43 } },
  { index: 3, removed: -0.06, metrics: { drag: 0.88 }, design: { nose_len: 380.42, shoulder: 1.4302 }, uses: { nose_len: 380.4, shoulder: 1.43 } }] };
"""


def _rows(html):
    import re

    return [(r.split("</td>", 1)[0], re.findall(r"<td>([^<]*)</td>", r.split("</tr>", 1)[0])[-2:])
            for r in html.split('data-ast="')[1:]]


def test_design_0_of_a_part_in_inches_reads_its_own_numbers_and_in_use():
    rows = _rows(_aero(INCH + "out = aeroResults({ id: 'cargo_box', params: { nose_len: 387.35, shoulder: 1.4 } }, inch, [inch]);"))
    assert rows[0][1] == ["387.35", "1.40"] and "in use" in rows[0][0]           # 387.4, and not in use, before
    assert rows[1][1] == ["380.4", "1.37"] and "in use" not in rows[1][0]


def test_only_the_design_written_reads_in_use_not_one_close_to_it():
    """reviewer-2's survivor: "in use" within a whole unit marked 1.37 and 1.43 both. Designs 0.06 apart: one is."""
    rows = _rows(_aero(INCH + "out = aeroResults({ id: 'cargo_box', params: { nose_len: 380.4, shoulder: 1.43 } }, inch, [inch]);"))
    assert ["in use" in r[0] for r in rows] == [False, False, True, True]


def test_a_design_with_an_earlier_one_s_numbers_says_so():
    rows = _rows(_aero(INCH + "out = aeroResults({ id: 'cargo_box', params: {} }, inch, [inch]);"))
    assert ["same as" in r[0] for r in rows] == [False, False, False, True] and "same as 2" in rows[3][0]


def test_the_note_says_the_drag_was_found_at_the_unrounded_numbers():
    html = _aero("out = aeroResults({ id: 'cargo_box', params: {} }, run, [run]);")
    assert "Each design's drag was found at its unrounded numbers; Use writes them to the places shown, a hair off." in html
