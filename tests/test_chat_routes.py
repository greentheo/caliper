"""CALI-89 (#65): the chat router dropped and misrouted requests. A change inside an explain-request was dropped,
"say it simpler" typed started an authoring run, "make it look like a dinosaur" became a new part, and "add a dino
skid on the bottom" cut a T-rex into the front. A table of messages, each with its route, offline, scoped to the
sample stool's one part and not."""

import pytest

from caliper import chat, samples


@pytest.fixture(scope="module")
def stool(tmp_path_factory):
    return samples.open_sample("step-stool", base=str(tmp_path_factory.mktemp("designs")))


P = "step_stool"
#: message -> (route scoped to the part, route with nothing selected): (action, part)
ROUTES = {
    # 1: a change inside an explain-request goes to the change
    "I don't get it, make it 2 inches taller": (("refine", P), ("refine", P)),
    "explain why, and make the legs thicker": (("refine", P), ("refine", P)),
    # 2: simpler or plainer words, with no change in it, is a question
    "say it simpler": (("answer", P), ("answer", None)),
    "simpler please": (("answer", P), ("answer", None)),
    "in plain English": (("answer", P), ("answer", None)),
    "explain like I'm five": (("answer", P), ("answer", None)),
    "Say that again in simpler words, for a kid.": (("answer", P), ("answer", None)),   # the button's own words
    # 3: "make it look like X" is a question that offers the picture; a skid on the bottom is a part
    "make it look like a dinosaur": (("answer", P), ("answer", None)),
    "add a dino skid on the bottom": (("refine", P), ("author", "dino_skid")),
    "put a T-rex on the side": (("picture", P), ("picture", P)),
    # the rest, as they were
    "carve the sides": (("refine", P), ("answer", None)),               # a plywood stool: nothing to carve
    # "make it …" on a one-part design is that part, never a new part named "part"
    "make it 2 in wider": (("refine", P), ("refine", P)),
}


@pytest.mark.parametrize("message", list(ROUTES))
@pytest.mark.parametrize("scoped", [True, False])
def test_each_message_goes_where_it_was_meant_to(stool, message, scoped):
    got = chat.offline_classify(stool, message, P if scoped else None)
    want = ROUTES[message][0 if scoped else 1]
    assert (got.action, got.part) == want, (message, scoped, got)


def test_make_it_look_like_offers_the_picture_and_changes_nothing(stool):
    v = stool.design.part(P).version
    got = chat.answer(stool, "make it look like a dinosaur", P,
                      note=chat.offline_classify(stool, "make it look like a dinosaur", P).note)
    assert "put a dinosaur on the side" in got.reply and "Nothing's changed" in got.reply, got.reply
    assert stool.design.part(P).version == v


def test_a_new_thing_on_a_one_part_design_is_still_a_new_part(stool):
    got = chat.offline_classify(stool, "add a shelf under the step", None)
    assert got.action == "author"


def test_claudes_router_has_the_same_rules():
    s = chat._CLASSIFY_SYSTEM
    assert "make it 2 inches taller" in s and "say it simpler" in s and "look like" in s and "skid" in s
