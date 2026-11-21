"""CALI-241 (#413): a joint nothing checked is named, with why, and offered only a fix the check credits.

caliper-reviewer's review of #407 on step-stool-5: its 17 placed joints are all unread, because the FEA waives a pull
their fixings can't give, and the hand rule can't follow its load path. The row's one fix, "say how each is made in its
JOINTS entry", was already done for 11, and adding the other 6 left it reading "19 joints not checked". Theo's fix loop
(every red has a one-tick fix a re-check confirms) and the foreman's rule, as for the glue block: offer only what the
check credits.
- **A fixing the table credits** for that joint's pull: its own row, the fixing named, one tick, and the re-check
  clears it.
- **Nothing credits it** (a screw or glue in an edge's grain: none, #301): a known limit that names the joints and says
  why, with no tick.
- **The FEA's words** match its count: a joint it gave no number isn't "checked by the FEA".

Synthetic joints and runs only."""

import numpy as np
import pytest

from caliper import answers, design_api, fixes, verdicts
from caliper import fea_joints as FJ
from caliper import joint_check as JC

from .test_fea_joints import JOINT, SCREWED, _hand, _reading, _setup

pytest.importorskip("cadquery")

PULLED = _reading([0, 0, -200.0])                       # the apron pulled off the top: a pull its glue can't give


def _beside(*joints, reading=PULLED, chain=False):
    hand = _hand([], chain=chain, unchecked=[] if chain else [JC.UNEVEN])
    return FJ.beside(hand, reading, _setup(*joints), 2.0)


# --- what the FEA's reading keeps of each joint nothing checked -------------------------------------------------------

def test_every_joint_nothing_checked_is_kept_by_name_with_why():
    tenon = {"pieces": ["leg", "rail"], "kind": "butt", "fix": ["glue"], "assumed": False, "unplaced": "a through tenon"}
    got = _beside(JOINT, tenon)
    assert [(o["between"], o["why"]) for o in got["open"]] == [
        ("the apron and the top", FJ.PULL_UNCREDITED), ("the leg and the rail", "a through tenon")]
    assert not any(o.get("fix") for o in got["open"])                    # nothing the table credits takes either


def test_a_notch_a_kind_with_no_rule_and_an_unbalanced_reading_each_say_why():
    notch = {**JOINT, "pieces": ["leg", "top"], "edge": "leg", "notch": True}
    dowel = {**JOINT, "pieces": ["rail", "top"], "edge": "rail", "kind": "dowel"}
    got = _beside(notch, dowel)
    assert [(o["between"], o["why"]) for o in got["open"]] == [
        ("the leg and the top", "a notch, which only the hand rule reads, and it couldn't follow the load to it"),
        ("the rail and the top", "a dowel, which the check has no rule for yet")]
    why = FJ.UNBALANCED.format(piece="top", pct=3.2)
    off = _beside(JOINT, reading=_reading([0, 0, 200.0], residual=0.032, unbalanced=why))
    assert [(o["between"], o["why"]) for o in off["open"]] == [("the apron and the top", why)]


def test_more_screws_aren_t_offered_where_they_pass_only_with_the_pull_waived():
    """Screwed, its shear passes and its pull is waived: more screws would read past only by the waiver, so none is
    offered (the foreman: the waiver isn't a check)."""
    (o,) = _beside(SCREWED, reading=_reading([5.0, 0, -200.0]))["open"]
    assert o["why"] == FJ.PULL_UNCREDITED and "fix" not in o


def test_a_joint_the_fea_checked_isn_t_kept():
    got = _beside(SCREWED, reading=_reading([0, 0, 200.0]))
    assert got["open"] == [] and verdicts.checked(got["rows"][0])


def test_where_a_fixing_is_credited_it_s_offered_and_the_re_check_clears_it(monkeypatch):
    """No fixing the table credits today takes a pull at an edge. Credited one, the count is what the fresh check reads
    past its need, and its JOINTS entry, applied, clears the joint."""
    monkeypatch.setattr(JC, "WITHDRAW_EDGE_LB", 50.0)
    (o,) = _beside(JOINT)["open"]
    fix = o["fix"]
    assert fix["entry"] == {"pieces": ["apron", "top"], "kind": "butt", "fix": ["glue", "screws"], "screws": fix["to"]}
    assert o["why"] == FJ.NO_PULL.format(edge="apron", face="top")
    again = _beside(JC.screwed(JOINT, fix["to"]))                        # its JOINTS entry, as the fresh check reads it
    assert again["open"] == []
    (r,) = again["rows"]
    assert verdicts.checked(r) and r["safety"] >= 2.0 and r["safety"] == fix["reads"]
    (less,) = _beside(JC.screwed(JOINT, fix["to"] - 1))["rows"]          # the fewest: one fewer reads short of it
    assert verdicts.checked(less) and less["safety"] < 2.0


def test_a_joint_the_fea_gave_no_number_isn_t_said_checked_by_it():
    """The reviewer: a joint the FEA reads carrying nothing had "checked by the FEA" while checked() was False."""
    got = _beside(SCREWED, reading=_reading([0, 0, 0.0]))
    (r,) = got["rows"]
    assert not verdicts.checked(r) and FJ.CHECKED_BY_FEA not in r["said"] and r["said"] == "not checked by hand"
    assert [(o["between"], o["why"]) for o in got["open"]] == [("the apron and the top", FJ.NO_FORCE)]


def test_an_fea_checked_row_keeps_its_crowded_words():
    crowded = {**SCREWED, "crowded": "they come within 1/2 in of each other"}
    (r,) = _beside(crowded, reading=_reading([0, 0, 200.0]))["rows"]
    assert r["said"].startswith(FJ.CHECKED_BY_FEA + ": ") and r["said"].endswith("; they come within 1/2 in of each other")


# --- the case's count and words --------------------------------------------------------------------------------------

def _case(open_, n=19, name="standing on it"):
    return {"name": name, "safety": 3.8, "holds": True, "governs": "fea", "fea": {"safety": 3.8},
            "joints": {"chain": False, "n": n, "rows": [], "unchecked": [JC.UNEVEN], "open": open_}}


PULL = [{"pieces": [f"p{i}", "side"], "between": f"the p{i} and the side", "why": FJ.PULL_UNCREDITED} for i in range(5)]


def test_the_count_is_the_joints_kept_and_says_not_checked():
    c = _case(PULL)
    b = verdicts.wood_brace({}, c)
    assert b["joints_n"] == 5 and verdicts.brace_why(b) == "5 joints not checked"


# --- Things to fix, flipped (#383 rule 2) ----------------------------------------------------------------------------

def _rows(tmp_path, cases, **more):
    from .test_check_own_frame import _stool

    store = _stool(tmp_path)
    p = {"id": "stool", "version": store.design.part("stool").version}
    run = {"min_safety": 2.0, "safety": 3.8, "spacing_mm": 3.0, "thinnest_mm": 19.05, "across": 6.35, "cases": cases,
           "version": p["version"], **more}
    return fixes._run_rows(store, p, run, "the designer")


def test_nothing_credited_is_a_known_limit_naming_the_joints_never_a_tick(tmp_path, monkeypatch):
    """step-stool-5's shape: every joint declared, every one unread for a pull nothing credits."""
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")
    tenon = {"pieces": ["leg", "rail"], "between": "the leg and the rail", "why": "a through tenon"}
    rows, limits = _rows(tmp_path, [_case(PULL + [tenon])])
    assert not [r for r in rows if r["id"].startswith("joints_unchecked")]
    assert not [c for r in rows for c in r["choices"] if "JOINTS entry (glue" in c["fix"]]
    assert limits == [
        f"6 joints not checked, by hand ({JC.UNEVEN}) or by the FEA, and nothing the check credits clears them yet: "
        f"the p0 and the side, the p1 and the side, the p2 and the side and 2 more ({FJ.PULL_UNCREDITED}); "
        "the leg and the rail (a through tenon)"]


ENTRY = {"pieces": ["apron", "top"], "kind": "butt", "fix": ["glue", "screws"], "screws": 3}
HELD = {"pieces": ["apron", "top"], "between": "the apron and the top", "why": FJ.NO_PULL.format(edge="apron", face="top"),
        "fix": {"pieces": ["apron", "top"], "edge": "apron", "side": "edge", "to": 3, "more": 3, "reads": 2.4,
                "said": "3 more #8 screws", "entry": ENTRY}}


def test_a_credited_fixing_is_its_own_row_with_one_tick_the_rest_a_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")
    entry, held = ENTRY, HELD
    rows, limits = _rows(tmp_path, [_case(PULL[:1] + [held])])
    (row,) = [r for r in rows if r["id"].startswith("joints_unchecked")]
    assert row["id"] == "joints_unchecked:apron|top" and row["measured"] is False and row["badge"] == "not checked"
    assert row["problem"] == f"The joint between the apron and the top isn't checked: {held['why']}"
    (c,) = row["choices"]
    assert c["entry"] == entry and c["kind"] == "designer" and c["fix"].startswith("3 #8 screws where the apron and the top meet")
    assert limits == [f"1 joint not checked, by hand ({JC.UNEVEN}) or by the FEA, and nothing the check credits clears "
                      f"it yet: the p0 and the side ({FJ.PULL_UNCREDITED})"]


def test_the_case_with_the_most_joints_open_is_the_one_said(tmp_path, monkeypatch):
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")
    _, limits = _rows(tmp_path, [_case(PULL[:1], name="a"), _case(PULL, name="b"), _case(PULL[:2], name="c")])
    assert len(limits) == 1 and limits[0].startswith("5 joints not checked")


def test_at_holds_it_reads_as_it_did(tmp_path):
    """Theo's #222 answer stands: the joints a known limit in the card's words, no row."""
    rows, limits = _rows(tmp_path, [_case(PULL + [HELD])])
    assert not [r for r in rows if r["id"].startswith("joints_unchecked")]
    assert limits == [f"Not checked by hand: {JC.UNEVEN}"]


def test_glued_trim_alone_is_never_a_joints_row_flipped(tmp_path, monkeypatch):
    """A part whose only unchecked piece is glued trim (#272): that's said on its card, never a joints row."""
    monkeypatch.setattr(verdicts, "JOINT_CAP", "unchecked")
    case = {"name": "standing on it", "safety": 3.8, "holds": True, "governs": "fea", "fea": {"safety": 3.8}}
    rows, limits = _rows(tmp_path, [case], trim=["corner fillets"])
    assert not [r for r in rows if r["id"].startswith("joints_unchecked")]
    assert not [x for x in limits if "joint" in x], limits


# --- the design's card names the part where there are several --------------------------------------------------------

def test_the_design_s_card_names_each_part_where_there_s_more_than_one(tmp_path):
    from .test_check_own_frame import _stool
    from .test_posts import LEGGED

    store = _stool(tmp_path)
    store.write_part("bench", LEGGED, intent="a four-legged stool with aprons")
    state = design_api.design_state(store)
    lines = [ln["text"] for ln in next(c for c in answers.design(store, state) if c["key"] == "work")["lines"]]
    assert sorted(x.split(":")[0] for x in lines if "checked yet for a seat" in x) == ["The bench", "The stool"], lines
