"""CALI-179 (#287): "remove X" never goes to the designer. From Theo's step-stool-5 on 2026-11-13: "remove the inside_
inside_corner_fillets" (a typo, the part selected) didn't name a part exactly, fell through to the designer, and the reply
opened "✓ revised inside_corner_fillets" over nothing changed.

1. A remove that names a part closely (one edit away, its words in any order, an underscore astray) asks to remove that
   part; one that looks like a part's name but names none asks which. A feature ("the fillet on the top") still goes to
   the designer.
2. A single part's revision where nothing measured moved never opens with ✓ (#242's rule, on the one-part path).
3. "… superseded: remove this part" mid-sentence, on a selected part, asks to remove it.
Stubbed: no Claude call."""

import pytest

from caliper import awaiting, chat
from caliper.design import DesignStore

from .test_chat import _box

pytest.importorskip("cadquery")


def _never(*a, **k):
    raise AssertionError("a remove never goes to the router or the designer")


@pytest.fixture
def stool(tmp_path):
    s = DesignStore.create("step-stool-5", base=str(tmp_path / "designs"))
    s.write_part("step_stool", _box(dx=400, dy=300), intent="the stool")
    s.write_part("inside_corner_fillets", _box(dx=150, dy=5, y=100), intent="glue-on fillet strips")
    return s


ASK = "Remove inside_corner_fillets? Its files go to the design's trash, so it can be put back."


def test_theo_s_typo_with_the_part_selected_asks_to_remove_it(stool):
    got = chat.turn(stool, "remove the inside_ inside_corner_fillets", scope="inside_corner_fillets", use_llm=False,
                    classifier=_never, author=_never)
    assert got.action == "ask" and got.reply == ASK, got.reply
    assert stool.design.part("inside_corner_fillets").version == 1                    # asked, nothing revised
    assert awaiting.pending(stool)["kind"] == "remove"


@pytest.mark.parametrize("words", ["remove the inside_ inside_corner_fillets", "remove inside corner fillet",
                                   "delete the fillets_corner_inside", "remove the inside_corner_filets",
                                   "get rid of the inside corner fillets part", "remove the corner inside fillets"])
def test_a_close_name_resolves_with_nothing_selected(stool, words):
    got = chat.turn(stool, words, use_llm=False, classifier=_never, author=_never)
    assert got.action == "ask" and got.reply == ASK, (words, got.reply)


def test_a_name_that_matches_no_part_asks_which_and_the_answer_names_it(stool):
    got = chat.turn(stool, "remove the corner_strips", use_llm=False, classifier=_never, author=_never)
    assert got.action == "ask" and not got.ok
    assert got.reply == "Remove which part? step_stool, inside_corner_fillets", got.reply
    again = chat.turn(stool, "inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    assert again.action == "ask" and again.reply == ASK, again.reply


def test_a_close_name_beside_the_selected_one_takes_the_selected(tmp_path):
    s = DesignStore.create("two strips", base=str(tmp_path / "designs"))
    s.write_part("left_strip", _box(dx=10), intent="a strip")
    s.write_part("right_strip", _box(dx=10, x=50), intent="a strip")
    got = chat.turn(s, "remove the strip_", scope="right_strip", use_llm=False, classifier=_never, author=_never)
    assert got.reply.startswith("Remove right_strip?"), got.reply
    got = chat.turn(s, "remove the strip_", use_llm=False, classifier=_never, author=_never)
    assert got.reply == "Remove which part? left_strip, right_strip", got.reply


def test_two_close_names_take_the_selected_one(tmp_path):
    s = DesignStore.create("corner strips", base=str(tmp_path / "designs"))
    s.write_part("corner_strip_a", _box(dx=10), intent="a strip")
    s.write_part("corner_strip_b", _box(dx=10, x=50), intent="a strip")
    got = chat.turn(s, "remove corner_strip_c", scope="corner_strip_b", use_llm=False, classifier=_never, author=_never)
    assert got.reply.startswith("Remove corner_strip_b?"), got.reply


def test_a_short_id_one_letter_off_is_a_feature(tmp_path):
    s = DesignStore.create("a rail", base=str(tmp_path / "designs"))
    s.write_part("rail", _box(dx=200), intent="the rail")
    assert chat._remove_or_restore(s, "remove the tail", None, events=[], on_event=None) is None


def test_the_context_s_words_don_t_route_the_request(stool):
    """A piece's name can name parts ("glued between step_stool and inside_corner_fillets"): what was typed, on the
    selected strip, revises the strip alone, never the two parts the name says."""
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return _box(dx=160, dy=5, y=100)
    about = "About the strip (glued between step_stool and inside_corner_fillets)"
    got = chat.turn(stool, f"{about}: make it 10 mm longer", scope="inside_corner_fillets", use_llm=False, author=author,
                    max_rounds=1, promote_feedback=False)
    assert got.action == "refine" and got.part == "inside_corner_fillets", (got.action, got.part, got.reply)
    assert len(seen) == 1 and about in seen[0]                                       # the designer still hears which piece


def test_a_feature_still_goes_to_the_designer(stool):
    assert chat._remove_or_restore(stool, "remove the fillet on the top", None, events=[], on_event=None) is None
    assert chat._remove_or_restore(stool, "remove the holes", "step_stool", events=[], on_event=None) is None


@pytest.mark.parametrize("words", ["This one is superseded by the new strips: remove this part.",
                                   "these are superseded, please delete this part"])
def test_remove_this_part_mid_sentence_on_a_selected_part_asks(stool, words):
    got = chat.turn(stool, words, scope="inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    assert got.action == "ask" and got.reply == ASK, got.reply


def test_remove_this_part_mid_sentence_with_nothing_selected_isn_t_taken(stool):
    assert chat._remove_or_restore(stool, "it's superseded, remove this part", None, events=[], on_event=None) is None


def test_a_single_part_revision_where_nothing_moved_has_no_tick(stool):
    """Rule 6 (#242), on the one-part path: written, so nothing's lost, but "!" and not a success."""
    same = stool.read_script("inside_corner_fillets").replace("return cq.", "w = cq.").rstrip() + "\n    return w\n"
    got = chat.refine_part(stool, "inside_corner_fillets", "make the strips sit flush", author=lambda *a: same,
                           use_llm=False, max_rounds=1, promote_feedback=False)
    first = got.reply.splitlines()[0]
    assert first.startswith("! revised **inside_corner_fillets** → v2") and first.endswith(
        ": the code changed, but no number, size or position I measure moved"), first
    assert "✓ revised" not in got.reply and not got.ok and got.version == 2
    moved = chat.refine_part(stool, "inside_corner_fillets", "make it wider", author=lambda *a: _box(dx=150, dy=8, y=100),
                             use_llm=False, max_rounds=1, promote_feedback=False)
    assert moved.reply.startswith("✓ revised **inside_corner_fillets** → v3"), moved.reply


def test_two_letters_astray_isn_t_close_and_asks_which(stool):
    got = chat.turn(stool, "remove the inside_cornar_fullets", use_llm=False, classifier=_never, author=_never)
    assert got.reply == "Remove which part? step_stool, inside_corner_fillets", got.reply


# --- 4 and 5: the page's "About the …:" context, and an answer to the parked question ----------------------------------
STRIP = ("About the inside corner fillet strip (superseded: step_stool now prints these itself; delete this part from "
         "the design)")


@pytest.mark.parametrize("message,scope,pick,typed", [
    (f"{STRIP}: remove it", "inside_corner_fillets", None, "remove it"),
    ("About the seat disk: make it thicker", "seat", None, "make it thicker"),
    ("About this edge (at x 0, y 1.5, z 2 mm in the script's coordinates): About the seat disk: round it", "seat", None,
     "round it"),
    # a joint's chip has a colon of its own: the pick's own words are what was typed
    ("About this joint between the side and the top: the line 300 mm long (at x 19.05, y 150, z 381 mm in the script's "
     "coordinates): make that a rabbet", "stool", {"kind": "edge", "id": "e1", "text": "make that a rabbet"},
     "make that a rabbet"),
    ("About the top: make it thicker", None, None, "About the top: make it thicker"),       # typed by hand, nothing selected
    ("About the top:   ", "stool", None, "About the top:   "),                            # nothing after it: as it is
])
def test_what_was_typed_is_what_follows_the_page_s_context(message, scope, pick, typed):
    assert chat.bare(message, scope, pick) == typed


def test_theo_s_two_messages_remove_the_part(stool):
    """23:37 and 23:43: the typo asks, and his answer with the strip selected removes it. Before, the answer reached the
    designer as "About the inside corner fillet strip (…): remove it" and revised it again (v5, ✓)."""
    ask = chat.turn(stool, f"{STRIP}: remove the inside_ inside_corner_fillets", scope="inside_corner_fillets",
                    use_llm=False, classifier=_never, author=_never)
    assert ask.action == "ask" and ask.reply == ASK, ask.reply
    gone = chat.turn(stool, f"{STRIP}: remove it", scope="inside_corner_fillets", use_llm=False, classifier=_never,
                     author=_never)
    assert gone.action == "remove" and gone.ok, gone.reply
    assert DesignStore.load(stool.root).design.part("inside_corner_fillets") is None


@pytest.mark.parametrize("answer", ["yes", "remove it", "remove inside_corner_fillets"])
def test_a_parked_remove_is_answered_with_the_context_on(stool, answer):
    chat.turn(stool, "remove inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    got = chat.turn(stool, f"{STRIP}: {answer}", scope="inside_corner_fillets", use_llm=False, classifier=_never,
                    author=_never)
    assert got.action == "remove" and got.ok, (answer, got.reply)


def test_no_with_the_context_on_keeps_it(stool):
    chat.turn(stool, "remove inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    got = chat.turn(stool, f"{STRIP}: no", scope="inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    assert got.reply == "Kept inside_corner_fillets." and stool.design.part("inside_corner_fillets") is not None


def test_a_remove_of_another_part_doesn_t_answer_the_parked_one(stool):
    chat.turn(stool, "remove inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    got = chat.turn(stool, "remove the step_stool", use_llm=False, classifier=_never, author=_never)
    assert got.action == "ask" and got.reply.startswith("Remove step_stool?"), got.reply
    assert DesignStore.load(stool.root).design.part("inside_corner_fillets") is not None


def test_the_restore_reads_what_was_typed_too(stool):
    chat.turn(stool, "remove inside_corner_fillets", use_llm=False, classifier=_never, author=_never)
    chat.turn(stool, "yes", use_llm=False, classifier=_never, author=_never)
    back = chat.turn(stool, "About the top step: put back inside_corner_fillets", scope="step_stool", use_llm=False,
                     classifier=_never, author=_never)
    assert back.action == "restore" and back.ok, back.reply
