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
    ("we need a dog bed", "dog_bed"),
    ("let's make a kids table", "kids_table"),
    ("I would like a coat rack", "coat_rack"),
    # #262 review: a request word inside a name is part of the name, never where it ends
    ("build a trash can enclosure", "trash_can"),
    ("make a watering can stand", "watering_can"),
    ("add a soda can holder", "soda_can"),
    ("add a can crusher", "can_crusher"),
    ("add a like button", "like_button"),
    ("add an I-beam", "i_beam"),
    ("add a D-ring", "d_ring"),
    ("add a get-well card holder", "get_well"),
    ("can opener mount", "can_opener"),                         # "can" at the start, not "can you": the name's
])
def test_a_new_part_is_named_for_what_s_asked_for(message, pid):
    assert chat.part_id_from(message, set()) == pid


def test_on_an_empty_design_i_need_a_bench_authors_a_bench(tmp_path):
    """The first part of a design is named for what's asked for (#250 answers "I need it wider" there, which asks for nothing new)."""
    from caliper.design import DesignStore

    empty = DesignStore.create("nothing yet", base=str(tmp_path))
    got = chat.offline_classify(empty, "I need a bench", None)
    assert (got.action, got.part) == ("author", "bench")


@pytest.mark.parametrize("message", ["I want it taller", "I'd like it wider", "can you make it shorter", "I need it wider",
                                     "I need them painted", "could you please make them smaller", "let's make it taller"])
def test_on_an_empty_design_a_request_about_it_has_nothing_to_change(tmp_path, message):
    """#262 re-check: #250's rule caught "I need it wider" but not "I want it taller", which went to the designer. One request
    phrase (`_REQUEST`) for both rules, so they can't drift."""
    from caliper.design import DesignStore

    empty = DesignStore.create("nothing yet", base=str(tmp_path))
    assert chat.offline_classify(empty, message, None).action == "answer", message
    assert chat.offline_classify(empty, "I want a bench", None).action == "author"       # a new thing still is one
