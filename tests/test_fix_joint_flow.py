"""#344 (Theo, on #316's FEA joints): a joint the check fails "ends up getting passed into the 'fixes' part of the UI, this
will be part of what makes our tool magical". So a failing joint row's fix is the one that passes: the fewest #8 screws,
by the number that governs, as the ``JOINTS`` entry that declares them, and what the joint would then read. Ticked, Fix
these hands it to the designer, checks the part again, and the joint reads what it said it would.

The flow is pinned end to end on the synthetic legged stool (``LEGGED``), its FEA real, its designer stubbed: the stub
writes only the entries the message names, so the message alone is enough to make the fix."""

import json
import re

import numpy as np
import pytest

from caliper import chat, design_api, fixes, fixing, load_study, marks, review, verdicts
from caliper import joint_check as JC
from caliper.design import DesignStore

from .test_joint_check import short_screws, studied  # noqa: F401 — fixtures
from .test_posts import LEGGED

pytest.importorskip("cadquery")
pytest.importorskip("whittle")

ENTRY = re.compile(r"its JOINTS entry (\{.*?\}); it would read")


@pytest.fixture(autouse=True)
def _no_findings(monkeypatch):
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [], "checks": 0})


class Writes:
    """refine_part, stubbed: writes the JOINTS entries its message names, and nothing else."""

    def __init__(self):
        self.calls = []

    def __call__(self, store, pid, message, **kw):
        from caliper.chat import TurnResult

        self.calls.append(message)
        entries = [json.loads(m) for m in ENTRY.findall(message)]
        v = store.write_part(pid, store.read_script(pid) + f"\nJOINTS = {entries!r}\n", intent="the joints' screws")
        return TurnResult(action="refine", reply="✓ revised", ok=True, part=pid, version=v)


def _rows(store):
    return fixes.listed(store, design_api.design_state(store), "stool")["rows"]


def _joint(case, key):
    return next(r for r in case["joints"]["rows"] if "|".join(r.get("pieces") or []) == key)


def test_a_joint_the_fea_fails_is_fixed_by_its_one_tick_and_reads_what_it_said(tmp_path, monkeypatch):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", LEGGED, intent="a four-legged stool with aprons")
    rec = load_study.study(store, "stool")
    need = rec["min_safety"]
    corner = next(c for c in rec["cases"] if c["name"].startswith("sitting"))
    assert not corner["holds"] and corner["governs"] == "joint" and corner["safety"] == pytest.approx(0.5, abs=0.01)

    rows = [r for r in _rows(store) if r["id"].startswith("joint:")]
    row = next(r for r in rows if r["id"] == "joint:front apron|front right leg")
    (pick,) = row["choices"]                          # only what the check credits: no glue block, no dado (#344)
    assert pick["kind"] == fixes.DESIGNER
    assert pick["entry"] == {"pieces": ["front apron", "front right leg"], "kind": "butt", "fix": ["glue", "screws"],
                             "screws": 4}
    # 2.02×: 2× before the legs were judged as lumber (#348)
    assert pick["fix"].startswith('4 #8 screws where the front right leg and the front apron meet, 3 more: its JOINTS '
                                  'entry {"pieces": ["front apron", "front right leg"], "kind": "butt", "fix": '
                                  '["glue", "screws"], "screws": 4}; it would read 2.02×'), pick["fix"]
    # four in its 3 in end: credited, and said (Theo's even spacing)
    assert pick["fix"].endswith("(4 screws 0.75 in apart in a 3 in joint: close enough to split the edge; consider a "
                                "longer joint or a bigger screw)")
    # one row a joint, its count the one every case it speaks for passes at: the corner's 3, not the rating's 2
    both = next(r for r in rows if r["id"] == "joint:back right leg|right apron")
    assert both["cases"] == [corner["name"], "its rating"] and both["choices"][0]["entry"]["screws"] == 3

    promised = {r["id"]: (r["choices"][0]["entry"]["screws"], r["choices"][0]["fix"], r["cases"]) for r in rows}
    designer = Writes()
    monkeypatch.setattr(chat, "refine_part", designer)
    out = fixing.apply(store, "stool", [{"id": r["id"], "choice": 0} for r in rows])

    assert len(designer.calls) == 1 and out["checked"]
    assert len(ENTRY.findall(designer.calls[0])) == len(rows)            # every ticked joint's entry, in the message
    assert {(r["id"], r["status"]) for r in out["results"]} == {(r["id"], "fixed") for r in rows}, out["results"]
    store = DesignStore.load(store.root)
    fresh = next(r for r in design_api.design_state(store)["load_runs"] if r["part"] == "stool")
    by = {c["name"]: c for c in fresh["cases"]}
    for rid, (n, said, cases) in promised.items():
        for name in cases:
            got = _joint(by[name], rid.split(":", 1)[1])
            assert verdicts.meets(got["safety"], need)["counts_as_pass"], (rid, name, got)
        reads = float(re.search(r"it would read ([\d.]+)×", said).group(1))
        assert min(_joint(by[n_], rid.split(":", 1)[1])["safety"] for n_ in cases) == pytest.approx(reads), rid
    assert by[corner["name"]]["safety"] >= need and not [r for r in _rows(store) if r["id"].startswith("joint:")]


def test_a_box_top_s_edge_joints_are_fixed_and_read_what_they_said(studied, short_screws, monkeypatch):  # noqa: F811
    """The same flow on a sheet's edge on a sheet's face (test_joint_check's box top, 1.6 by the FEA, on short screws),
    where the screws are laid along the joint and a moment goes to the farthest: what the fix-it promised is what the
    fresh check reads."""
    from .test_load_study import BOX_STOOL

    store, rec = studied(BOX_STOOL)
    rows = [r for r in _rows(store) if r["id"].startswith("joint:")]
    assert rows and not rec["cases"][0]["holds"]
    assert [r["choices"][0]["entry"]["screws"] for r in rows] == [4, 4, 3, 3]   # front, back by the FEA; sides by hand
    promised = {r["id"]: (r["choices"][0]["fix"], r["cases"]) for r in rows}
    monkeypatch.setattr(chat, "refine_part", Writes())
    out = fixing.apply(store, "stool", [{"id": r["id"], "choice": 0} for r in rows])
    assert {r["status"] for r in out["results"]} == {"fixed"}, out["results"]
    fresh = next(r for r in design_api.design_state(DesignStore.load(store.root))["load_runs"] if r["part"] == "stool")
    by = {c["name"]: c for c in fresh["cases"]}
    for rid, (said, cases) in promised.items():
        reads = float(re.search(r"it would read ([\d.]+)×", said).group(1))
        assert min(_joint(by[n], rid.split(":", 1)[1])["safety"] for n in cases) == pytest.approx(reads), (rid, said)


# --- the count, laid evenly ------------------------------------------------------------------------------------------

def test_a_declared_count_is_laid_evenly_keeping_its_end_distance():
    assert marks.spots(152.4, 3) == pytest.approx([38.1, 76.2, 114.3])              # step-stool-5's rail end: 1 1/2 in apart
    assert marks.spots(152.4) == pytest.approx([38.1, 114.3])                        # undeclared: as before
    assert marks.spots(152.4, 1) == [76.2]
    assert marks.spots(50.8, 2) == pytest.approx([12.7, 38.1])                       # no room for its ends: even across it
    assert marks.count(152.4, 9) == 9                                                # never refused


def test_screws_nearer_than_six_diameters_are_said_and_still_credited():
    assert marks.crowded(152.4, 3) is None and marks.crowded(76.2 + 25.4, 2) is None    # 1 1/2 in, and exactly 1 in
    assert marks.crowded(152.4, 5) == ("5 screws 0.75 in apart in a 6 in joint: close enough to split the edge; "
                                       "consider a longer joint or a bigger screw")
    assert marks.crowded(76.2 + 25.4 - 0.5, 2).startswith("2 screws 0.98 in apart in a 3.98 in joint")
    j = {"pieces": ["a", "b"], "edge": "a", "fix": ["glue", "screws"], "screws": 2, "length_mm": 152.4}
    got = JC.fix_it(j, 2.0, lambda n: 0.45 * n)                                     # 5 screws: 2.25
    assert (got["to"], got["more"], got["reads"]) == (5, 3, 2.25)
    assert got["said"] == ("3 more #8 screws at the a's edge, 5 in all, would read 2.25×, past 2 (5 screws 0.75 in "
                           "apart in a 6 in joint: close enough to split the edge; consider a longer joint or a bigger "
                           "screw)")


def test_the_fix_it_is_the_fewest_that_pass_and_none_where_screws_don_t_help():
    j = {"pieces": ["apron", "leg"], "edge": "apron", "fix": ["screws"], "screws": 1, "apron": True, "length_mm": 300.0}
    got = JC.fix_it(j, 2.0, lambda n: 0.95 * n)                                     # 2: 1.9, 3: 2.85
    assert (got["to"], got["more"]) == (3, 2) and "crowded" not in got
    assert got["said"] == "2 more #8 screws at the apron's end, 3 in all, would read 2.85×, past 2"
    assert got["entry"] == {"pieces": ["apron", "leg"], "kind": "butt", "fix": ["screws"], "screws": 3}
    assert JC.fix_it(j, 2.0, lambda n: 1.0) is None                                 # it bears: screws don't move it
    glued = {**j, "fix": ["glue"], "screws": 2}                                     # its screws, uncounted: from none
    assert JC.fix_it(glued, 2.0, lambda n: 1.0 * n)["more"] == 2
    assert JC.fix_it(glued, 2.0, lambda n: 1.0 * n)["entry"]["fix"] == ["glue", "screws"]


def test_a_joints_entry_s_count_is_the_one_every_reader_counts_and_must_be_whole_and_screwed(tmp_path):
    from caliper import joints

    from .test_joints import STOOL, _built

    right = '''    {"pieces": ["step", "right side"], "kind": "butt", "fix": ["glue", "screws"]},'''
    five = STOOL.replace(right, right.replace('"screws"]}', '"screws"], "screws": 5}'))
    store, d, pcs, tol, mesh = _built(tmp_path / "five", five)
    _, said = joints.readable(five)
    laid = marks.screws(pcs, tol, said)[("right side", "step")]
    assert laid["n"] == 5 and laid["declared"] == 5 and len(laid["points"]) == 5        # the patterns', the book's
    assert next(j for j in JC.setup(store, "stool")["joints"] if set(j["pieces"]) == {"right side", "step"})["screws"] == 5
    (ok,) = [x for x in joints.check(five, d, mesh) if x.id == "joints"]
    assert ok.status == "pass", ok.detail
    for bad, words in ((right.replace('"screws"]}', '"screws"], "screws": 2.5}'),
                        'JOINTS gives the step and the right side "screws": 2.5, which isn\'t a whole number of 1 or more'),
                       (right.replace('"screws"]}', '"screws"], "screws": 0}'),
                        'JOINTS gives the step and the right side "screws": 0, which isn\'t a whole number of 1 or more'),
                       (right.replace('["glue", "screws"]}', '["glue"], "screws": 3}'),
                        "JOINTS gives the step and the right side 3 screws, but its fix doesn't include screws")):
        script = STOOL.replace(right, bad)
        _, d2, _, _, mesh2 = _built(tmp_path / str(abs(hash(bad))), script)
        (r,) = [x for x in joints.check(script, d2, mesh2) if x.id == "joints"]
        assert r.status == "fail" and words in r.detail, r.detail


# --- what the count answers to (mutants that survived the flows, #344) -------------------------------------------------

def test_a_hand_row_carries_its_own_fix_where_no_fea_reads_it(tmp_path, short_screws):  # noqa: F811
    """The hand check alone (no FEA beside it): each failing row's count, from its own demand."""
    from .test_joint_check import _load, _pieces, _store
    from .test_load_study import BOX_STOOL

    store = _store(tmp_path, BOX_STOOL, "stool")
    _, _, held = _pieces(store)
    su = JC.setup(store, "stool")
    got = JC.check(su, _load(store), held, 2.0)
    failing = [r for r in got["rows"] if r.get("safety") is not None and r["safety"] < 2.0]
    assert failing
    for r in failing:
        j = next(j for j in su["joints"] if j["pieces"] == r["pieces"])
        more = r["more_screws"]
        assert r["fix"] == more["said"] and more["to"] > j["screws"]
        assert more["reads"] == JC._by_hand(j, r["demands_n"], su["screw_mm"])(more["to"]) >= 2.0
        assert JC._by_hand(j, r["demands_n"], su["screw_mm"])(more["to"] - 1) < 2.0       # the fewest


def test_a_raked_tie_s_count_passes_its_thrust_and_its_frame_load_both():
    """A raked leg's tie: the rake's thrust shears it where the frame's load hardly does. Its row keeps both demands, and
    its count passes the two."""
    leg = {"key": "leg", "name": "leg", "kind": "stick", "a": (0.0, 0.0, 400.0), "b": (-100.0, 0.0, 0.0)}   # 14°
    tie = {"pieces": ["apron", "leg"], "edge": "apron", "face": "leg", "apron": True, "kind": "butt",
           "out": np.array([0.0, 1.0, 0.0]), "normal": np.array([0.0, 1.0, 0.0]), "along": np.array([0.0, 0.0, 1.0]),
           "edge_t": 19.05, "face_t": 38.1, "length_mm": 76.2, "area_mm2": 76.2 * 19.05, "mid": np.zeros(3),
           "points": [], "screws": 1, "fix": ["glue", "screws"], "assumed": True, "sin": 0.0}
    frame = {"bearing": 0.0, "withdrawal": 0.0, "shear": 100.0}
    rows = [{"pieces": ["apron", "leg"], "between": "the leg and the apron", "mode": "shear", "safety": 50.0,
             "need": 2.0, "holds": True, "said": "by hand", "demands_n": [frame]}]
    JC.rake_rows([tie], {"leg": leg}, {"leg": np.array([0.0, 0.0, -4000.0])}, rows, [], 50.0, 2.0)
    (r,) = rows
    thrust = {"bearing": 0.0, "withdrawal": 0.0, "shear": pytest.approx(1000.0)}                # 4000 N × tan 14°
    assert r["demands_n"] == [frame, thrust] and r["safety"] < 2.0
    alone = JC.fix_it(tie, 2.0, JC._by_hand(tie, [r["demands_n"][1]], 50.0))
    assert r["more_screws"]["to"] == alone["to"] > 1                                          # the thrust's count


def test_a_sheet_edge_s_screws_are_laid_where_marks_lays_them_and_an_apron_end_s_aren_t():
    """What the fix-it reads at n screws is the fresh check's: a sheet's edge has its n screws where marks.spots puts
    them (its moment goes to the farthest); an apron's end has none (its moment goes over half its length)."""
    j = {"pieces": ["rail", "side"], "edge": "rail", "fix": ["glue", "screws"], "screws": 2, "length_mm": 152.4,
         "mid": np.array([0.0, 0.0, 100.0]), "along": np.array([0.0, 0.0, 1.0]),
         "points": [np.array([0.0, 0.0, 61.9]), np.array([0.0, 0.0, 138.1])]}
    got = JC.screwed(j, 3)
    assert got["screws"] == 3 and got["fix"] == ["glue", "screws"]
    assert np.allclose(got["points"], [[0, 0, 61.9], [0, 0, 100.0], [0, 0, 138.1]])
    assert JC.screwed({**j, "apron": True}, 3)["points"] == j["points"]
