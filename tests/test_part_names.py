"""CALI-168 (#258) — "I need a bench" named its part `i_need`: the id came from the message's first words, not what's asked for."""

import pytest

from caliper import chat


@pytest.mark.parametrize("message, pid", [
    ("I need a bench", "bench"),
    ("I want a shelf for my garage", "shelf"),
    ("make me a stool", "stool"),
    ("can you make a step stool", "step_stool"),
    ("could you build me a planter box", "planter_box"),
    ("I'd like a bird house", "bird_house"),
    ("please add a corner bracket", "corner_bracket"),          # as before
])
def test_a_new_part_is_named_for_what_s_asked_for(message, pid):
    assert chat.part_id_from(message, set()) == pid


def test_on_an_empty_design_i_need_a_bench_authors_a_bench(tmp_path):
    """The first part of a design is named for what's asked for (#250 answers "I need it wider" there, which asks for nothing new)."""
    from caliper.design import DesignStore

    empty = DesignStore.create("nothing yet", base=str(tmp_path))
    got = chat.offline_classify(empty, "I need a bench", None)
    assert (got.action, got.part) == ("author", "bench")
