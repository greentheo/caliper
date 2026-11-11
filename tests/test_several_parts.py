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
    (THEO, ["side_left", "side_right"]),                     # the stretcher is what they're sized off, not a change
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
    client = _StubClient('{"action": "refine", "part": "side_left", "parts": ["side_left", "side_right"]}')
    got = chat.llm_classify(stool, THEO, client=client)
    assert got.parts == ["side_left", "side_right"] and got.part == "side_left"
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
    scripts = {pid: stool.read_script(pid) for pid in ("side_left", "side_right", "stretcher") if stool.design.part(pid)}
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


@pytest.mark.parametrize("message", ["make the stretcher clear the left side by 2 mm", "move the stretcher up to the right side"])
def test_a_part_named_only_as_a_reference_isn_t_changed(stool, message):
    """Two names, no shared word and no "and" between them: one part is changed, the other is where it's measured from."""
    assert len(chat.offline_classify(stool, message).parts) == 1


# --- #242 review --------------------------------------------------------------------------------------------------------
LEGS = ["top", "leg_front_left", "leg_front_right", "leg_back_left", "leg_back_right"]


@pytest.mark.parametrize("parts,message,want", [
    (LEGS, "make the top thicker so the legs don't wobble", ["top"]),
    (["side_left", "side_right", "top"], "thicken the top; it flexes between the sides", ["top"]),
    (["side_left", "side_right", "top"], "make the top overhang the sides by 1 in", ["top"]),
    (["top", "apron_front", "apron_back"], "both aprons need a groove for the top's buttons", ["apron_front", "apron_back"]),
])
def test_a_part_named_as_a_reference_stays_out(parts, message, want):
    """Item 1: a shared word brings in only the parts it groups; a part named beside it is where it's measured from."""
    assert chat.named_parts(message, parts) == want


@pytest.mark.parametrize("parts,message,want", [
    (LEGS, "make the front legs longer", ["leg_front_left", "leg_front_right"]),
    (LEGS, "make both front legs longer", ["leg_front_left", "leg_front_right"]),
    (LEGS, "it rocks on the left legs", ["leg_front_left", "leg_back_left"]),
    (LEGS, "all the legs 2 in longer", LEGS[1:]),
    (["top", "corner_bracket_left", "corner_bracket_right"], "round the corners", []),
    (["top", "corner_bracket_left", "corner_bracket_right"], "round the corners of the top", ["top"]),
    (["lid", "lid_hinge"], "make the lids thicker", ["lid"]),
    (["shelf_1", "shelf_2", "shelf_3"], "make the shelves deeper", ["shelf_1", "shelf_2", "shelf_3"]),
])
def test_a_plural_groups_only_true_siblings(parts, message, want):
    """Item 2: ids that leave only position words or numbers once the stem is out; a position word narrows them."""
    assert chat.named_parts(message, parts) == want


TALLER = {"side_left": _box(dx=20, dy=300, x=0).replace("10)", "60)"),
          "side_right": _box(dx=20, dy=300, x=300).replace("10)", "60)")}


@pytest.mark.parametrize("message", ["make both sides the right side, and taller", "use the left side for both sides, taller",
                                     "make the left side match the other, and both sides taller"])
def test_theo_s_own_words_for_a_mirror_get_no_tick(stool, message):
    """Item 3: "make both sides the right side" is a mirror in other words: said as not done yet (#239), and no ✓."""
    res = chat.turn(stool, message, use_llm=False, author=_by_part(stool, TALLER))
    lines = res.reply.splitlines()
    assert lines[0].startswith("! Changed") and "✓" not in lines[0] and not res.ok
    assert lines[1].startswith("Mirroring one part from another isn't something I can do yet")


def test_a_comment_only_edit_isn_t_a_change(stool):
    """Item 3: a comment or a layout change is the same code (by its parsed tree): no change, and no version."""
    note = {"side_left": TALLER["side_left"],
            "side_right": "# the right side\n" + stool.read_script("side_right")}
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, note))
    assert res.reply.splitlines()[0] == "! Changed side_left; side_right not changed: its code came back as it was."
    assert stool.design.part("side_right").version == 1


PARAMS_SIDE = ('import cadquery as cq\n\nPARAMS = {{"h": {h}}}\n\n\ndef build(params):\n    p = {{**PARAMS, **(params or {{}})}}\n'
               '    return cq.Workplane().box(20, 300, p["h"]).translate(({x}, 0, 0))\n')


def test_the_second_designer_is_told_what_the_first_part_became(tmp_path):
    """Item 4: side_right's designer sees side_left's moved numbers, so a size they share can follow."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("side_left", PARAMS_SIDE.format(h=10, x=0), intent="the left side")
    s.write_part("side_right", PARAMS_SIDE.format(h=10, x=300), intent="the right side")
    told = []

    def author(spec, feedback, prior):
        told.append(feedback)
        return prior.replace('"h": 10', '"h": 60')
    chat.turn(s, "make both sides taller", use_llm=False, author=author)
    assert "Already revised for it" not in told[0]
    assert "Already revised for it: side_left h 10 → 60." in told[1]


def test_the_count_is_said_up_front_and_each_part_s_place(stool):
    """Item 5: one event before the first part, then "1 of 2", "2 of 2"."""
    seen = []
    chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, TALLER),
              on_event=lambda ev: seen.append(ev.text))
    said = [t for t in seen if t.startswith("revising")]
    assert said[:3] == ["revising 2 parts: side_left, side_right", "revising side_left (1 of 2)…",
                        "revising side_right (2 of 2)…"]


def test_a_pick_goes_with_the_part_it_was_made_on(stool, monkeypatch):
    """Item 6: the several-parts path kept no pick; it goes to the selected part's revision only."""
    got = {}
    real = chat.refine_part

    def spy(store, pid, message, **kw):
        got[pid] = kw.get("pick")
        return real(store, pid, message, **kw)
    monkeypatch.setattr(chat, "refine_part", spy)
    pick = {"kind": "edge", "id": "e0", "text": "round it"}
    chat.turn(stool, "make both sides taller", scope="side_right", pick=pick, use_llm=False, author=_by_part(stool, TALLER))
    assert got == {"side_left": None, "side_right": pick}


# --- #242 re-check ------------------------------------------------------------------------------------------------------
def test_a_move_written_as_literals_is_a_change(stool):
    """Item 1: "move both sides out 20 mm", each side's translate moved: the same numbers and volume, not the same box."""
    out = {"side_left": _box(dx=20, dy=300, x=0, y=20), "side_right": _box(dx=20, dy=300, x=300, y=20)}   # every mate kept
    res = chat.turn(stool, "move both sides back 20 mm", use_llm=False, author=_by_part(stool, out))
    assert res.reply.splitlines()[0] == "✓ Changed side_left and side_right." and res.ok
    assert stool.design.part("side_left").version == 2 and stool.design.part("side_right").version == 2


HOLED = ("import cadquery as cq\n\n\ndef build(params):\n"
         "    return cq.Workplane('XY').box(20, 300, 10).translate(({x}, 0, 0)).faces('>Z')"
         ".workplane(centerOption='CenterOfBoundBox').center(0, {cy}).hole(6)\n")


def test_a_hole_moved_as_a_literal_is_a_change(tmp_path):
    """Item 1: "move the hole in both sides 100 mm toward the back": its centre moved, the volume didn't."""
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("side_left", HOLED.format(x=0, cy=0), intent="the left side")
    s.write_part("side_right", HOLED.format(x=300, cy=0), intent="the right side")
    back = {"side_left": HOLED.format(x=0, cy=100), "side_right": HOLED.format(x=300, cy=100)}
    res = chat.turn(s, "move the hole in both sides 100 mm toward the back", use_llm=False, author=_by_part(s, back))
    assert res.reply.splitlines()[0] == "✓ Changed side_left and side_right."


def test_code_that_changed_with_nothing_measured_moving_is_kept_and_said(stool):
    """Item 1: written, so nothing's lost, but no ✓: "the code changed, but no number, size or position I measure moved"."""
    same_shape = {"side_left": TALLER["side_left"],
                  "side_right": stool.read_script("side_right").replace("return cq.", "w = cq.").rstrip()
                  .replace("translate((300, 0, 0))", "translate((300, 0, 0))\n    return w") + "\n"}
    res = chat.turn(stool, "make both sides taller", use_llm=False, author=_by_part(stool, same_shape))
    assert res.reply.splitlines()[0] == ("! Changed side_left; side_right: the code changed, but no number, size or "
                                         "position I measure moved.")
    assert stool.design.part("side_right").version == 2 and not res.ok


@pytest.mark.parametrize("message,mirror", [("make both sides taller to match the top", False),
                                            ("make both sides taller, the same as the stretcher", False),
                                            ("make the left side match the right side, and both sides taller", True),
                                            ("make both sides match each other and taller", True)])
def test_match_is_a_mirror_only_before_a_part_asked_of_or_the_other(stool, message, mirror):
    """Item 2: "taller to match the top" isn't a mirror; "match the right side" (both sides asked of) is."""
    assert chat._mirror_asked(message, ["side_left", "side_right"]) is mirror


@pytest.mark.parametrize("message,want", [
    ("make the legs longer; the top wobbles", LEGS[1:]),
    ("make the legs 2 in longer and the top thicker", LEGS),
    ("make the top thicker so the legs don't wobble", ["top"]),
])
def test_the_verb_s_object_wins(message, want):
    """Item 3: a plural target beside a named part: the one the request's first clause acts on."""
    assert chat.targets(message, LEGS) == (want, "")


def test_when_it_can_t_tell_it_asks(stool):
    got = chat.targets("the top over the legs is too thin", LEGS)
    assert got == ([], "Which do you want changed: the legs, or the top? Say which (or both), and I'll change it.")
    s = DesignStore.create("a table", base=str(stool.root) + "-table")
    for pid in LEGS:
        s.write_part(pid, _box(), intent=pid)
    res = chat.turn(s, "the top over the legs is too thin", use_llm=False, author=lambda *a: pytest.fail("asked, not edited"))
    assert res.action == "answer" and res.reply == got[1]


@pytest.mark.parametrize("parts,message,want", [
    (["wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"], "make the wheels bigger", ["wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"]),
    (LEGS, "lengthen the rear legs", ["leg_back_left", "leg_back_right"]),
    (["side_panel", "back_panel"], "the panels are too thin, make them thicker", ["side_panel", "back_panel"]),
])
def test_rear_rl_rr_and_panels(parts, message, want):
    """Item 4: rl/rr are positions, "rear" is "back", and "the panels" are both panels."""
    assert chat.named_parts(message, parts) == want


def test_a_pick_on_a_part_this_doesn_t_change_is_said(stool):
    pick = {"kind": "edge", "id": "e0", "text": "round it"}
    res = chat.turn(stool, "make both sides taller", scope="stretcher", pick=pick, use_llm=False, author=_by_part(stool, TALLER))
    assert "What you picked is on stretcher, which this doesn't change: the pick wasn't used." in res.reply


def test_a_plural_that_finds_one_part_by_elimination_finds_none():
    """Item 4: "the panels" with panel_door and back_panel isn't back_panel alone (door is no position word)."""
    assert chat.named_parts("the panels are too thin, make them thicker", ["panel_door", "back_panel"]) == []


def test_a_change_of_size_that_keeps_the_volume_and_the_middle_is_a_change(stool):
    """Item 1: twice as thick and half as long, in place: the same numbers, volume and centre of mass, another box."""
    reshaped = {"side_left": _box(dx=40, dy=150, x=0), "side_right": _box(dx=40, dy=150, x=300)}
    res = chat.turn(stool, "make both sides thicker and shorter", use_llm=False, author=_by_part(stool, reshaped))
    assert res.reply.splitlines()[0].startswith("! Changed side_left and side_right")   # a mate broke: "!" not "✓"
    assert "the code changed, but no number" not in res.reply.splitlines()[0]


# --- #242, the last round ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("message", ["make both sides identical, and taller", "make both sides like the right one, and taller",
                                     "make both sides the same, and taller"])
def test_identical_and_like_the_right_one_are_a_mirror(stool, message):
    """Item 1: no ✓, and the line that mirroring isn't done yet."""
    res = chat.turn(stool, message, use_llm=False, author=_by_part(stool, TALLER))
    lines = res.reply.splitlines()
    assert "✓" not in lines[0] and not res.ok
    assert lines[1].startswith("Mirroring one part from another isn't something I can do yet")


@pytest.mark.parametrize("message,mirror", [("copy the right side onto both sides", True),
                                            ("make both sides the same thickness as the top", False),
                                            ("make both sides taller, the same as the stretcher", False)])
def test_the_same_as_a_size_isn_t_a_mirror(message, mirror):
    assert chat._mirror_asked(message, ["side_left", "side_right"]) is mirror


@pytest.mark.parametrize("message,want", [("make the top thicker and the legs wobble", (["top"], "")),
                                          ("make the legs 2 in longer and the top thicker", (LEGS, ""))])
def test_and_joins_two_requests_not_a_request_and_a_complaint(message, want):
    """Item 2: the part with the request is changed; a complaint beside it isn't."""
    assert chat.targets(message, LEGS) == want


def test_two_complaints_joined_by_and_are_asked_about():
    assert chat.targets("the top is too thin and the legs wobble", LEGS) == (
        [], "Which do you want changed: the legs, or the top? Say which (or both), and I'll change it.")
