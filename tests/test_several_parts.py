"""CALI-163 (#241) — an edit that names several parts changes each one, and says first which it didn't.

Theo's step-stool-4 (2026-11-11): "make both sides the right side; the stretcher doesn't fit snug; neither slot is sized
off the stretcher" went to side_left only, and the reply opened "✓ revised side_left → v2" over a request it half did.
Stubbed models only: no live call."""

import pytest

from caliper import chat
from caliper.assembly import Mate
from caliper.design import DesignStore

from .test_chat import _StubClient, _box

pytest.importorskip("cadquery")

THEO = "make both sides the right side; the stretcher doesn't fit snug; neither slot is sized off the stretcher"


@pytest.fixture
def stool(tmp_path):
    """Two sides and a stretcher between them, the way step-stool-4's plan laid them out."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("side_left", _box(dx=20, dy=300, x=0), intent="the left side")
    s.write_part("side_right", _box(dx=20, dy=300, x=300), intent="the right side")
    s.write_part("stretcher", _box(dx=280, dy=19, x=150), intent="the stretcher between the sides")   # boxes are centred
    s.assembly.mates.append(Mate(id="stretcher_meets_left", between=["stretcher", "side_left"], kind="touch"))
    s.assembly.mates.append(Mate(id="stretcher_misses_right", between=["stretcher", "side_right"], kind="no_interference"))
    s.save()
    return s


# --- routing by the request, not the selection --------------------------------------------------------------------------
@pytest.mark.parametrize("message,want", [
    ("make both sides 2 in taller", ["side_left", "side_right"]),
    ("neither side is tall enough: make them 2 in taller", ["side_left", "side_right"]),
    (THEO, ["side_left", "side_right", "stretcher"]),
    ("make the stretcher and the left side thicker", ["side_left", "stretcher"]),
])
def test_a_message_that_names_several_parts_routes_to_each(stool, message, want):
    got = chat.offline_classify(stool, message)
    assert got.action == "refine" and got.parts == want and got.part == want[0]


def test_the_selection_doesn_t_narrow_a_message_that_names_several(stool):
    """Theo had a side selected: the request still names both."""
    got = chat.offline_classify(stool, "make both sides 2 in taller", scope="side_left")
    assert got.parts == ["side_left", "side_right"]


def test_one_part_named_still_routes_as_before(stool):
    got = chat.offline_classify(stool, "make the stretcher thicker")
    assert (got.action, got.part, got.parts) == ("refine", "stretcher", ["stretcher"])
    assert chat.offline_classify(stool, "make it 5 mm wider", scope="stretcher").parts == ["stretcher"]


def test_claude_s_routing_returns_every_part_it_names(stool):
    client = _StubClient('{"action": "refine", "part": "side_left", "parts": ["side_left", "side_right", "stretcher"]}')
    got = chat.llm_classify(stool, THEO, client=client)
    assert got.parts == ["side_left", "side_right", "stretcher"] and got.part == "side_left"
    seen = []
    create = client.create
    client.create = lambda **kw: seen.append(kw) or create(**kw)
    chat.llm_classify(stool, THEO, client=client)
    assert '"parts"' in seen[0]["system"] and "both sides" in seen[0]["system"]


def test_claude_naming_an_unknown_part_among_several_is_rejected(stool):
    client = _StubClient('{"action": "refine", "part": "side_left", "parts": ["side_left", "flux_capacitor"]}')
    with pytest.raises(ValueError):
        chat.llm_classify(stool, THEO, client=client)


# --- each named part is edited, and the reply says first what wasn't ----------------------------------------------------
def _by_part(stool, changes):
    """An author that changes each named part as ``changes`` says, and hands any other back as it was."""
    scripts = {pid: stool.read_script(pid) for pid in ("side_left", "side_right", "stretcher")}
    owner = {v: k for k, v in scripts.items()}
    return lambda spec, feedback, prior: changes.get(owner.get(prior), prior)


def test_every_named_part_is_changed_and_the_reply_says_so_first(stool):
    taller = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)"),
              "side_right": _box(dx=20, dy=300, x=300).replace("10)", "60)")}
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, taller))
    assert res.ok and res.action == "refine"
    assert res.reply.splitlines()[0] == "✓ Changed side_left and side_right."
    assert stool.design.part("side_left").version == 2 and stool.design.part("side_right").version == 2
    assert stool.design.part("stretcher").version == 1


def test_a_named_part_left_as_it_was_gets_no_tick_and_is_named(stool):
    """The stub changes side_left only, as the live revision did."""
    one = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)")}
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, one))
    first = res.reply.splitlines()[0]
    assert not res.ok and "✓" not in first
    assert first.startswith("! Changed side_left; side_right not changed:")
    assert "✓ Changed" not in res.reply


def test_no_tick_when_nothing_named_changed(stool):
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, {}))
    assert not res.ok and res.reply.splitlines()[0].startswith("✗ Nothing changed: side_left and side_right")


def test_each_revision_is_told_it_is_for_that_part_only(stool):
    told = []
    taller = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)"),
              "side_right": _box(dx=20, dy=300, x=300).replace("10)", "60)")}
    author = _by_part(stool, taller)
    chat.turn(stool, "make both sides taller", use_llm=False, author=lambda s, f, p: told.append(f) or author(s, f, p))
    assert any("side_left only" in f for f in told) and any("side_right only" in f for f in told)


def test_mirroring_is_said_as_not_done_yet(stool):
    taller = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)"),
              "side_right": _box(dx=20, dy=300, x=300).replace("10)", "60)")}
    res = chat.turn(stool, "mirror both sides and make them taller", use_llm=False, author=_by_part(stool, taller))
    assert "Mirroring one part from another isn't something I can do yet" in res.reply.splitlines()[1]
    assert not res.ok and "✓" not in res.reply.splitlines()[0]


# --- "still measures green" says what was measured ------------------------------------------------------------------------
def test_green_says_which_checks_ran_and_that_fit_isn_t_measured(stool):
    report, _ = chat._measure_design(stool)
    line = chat._design_line(report)
    assert "touch" in line and "no overlap" in line and "fits snug in its pocket isn't measured" in line
    assert "measures green" not in line


def test_no_tick_over_a_change_that_broke_a_check(stool):
    """Both sides changed, but the right one now runs into the stretcher: changed, said, and no ✓."""
    into = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)"),
            "side_right": _box(dx=20, dy=300, x=280).replace("10)", "60)")}
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, into))
    assert res.reply.splitlines()[0] == "! Changed side_left and side_right." and not res.ok
    assert "stretcher_misses_right" in res.broke
