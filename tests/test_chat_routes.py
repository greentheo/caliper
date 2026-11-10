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


# --- #212 review: what main routed right still routes right, both ways ---------------------------------------------

@pytest.fixture(scope="module")
def camper(tmp_path_factory):
    return samples.open_sample("camper", base=str(tmp_path_factory.mktemp("camper")))


#: a question stays a question, whatever words are in it (an authoring run for a question was #65's harm)
QUESTIONS = ["explain the build order", "explain the cut list", "I don't get how to put it together",
             "I don't understand which way to turn the panel", "explain what to use for the legs",
             "I don't understand the cut list", "explain how you would move it", "explain like I'm five how to build it",
             "ELI5", "eli5 the strength check"]


@pytest.mark.parametrize("message", QUESTIONS)
@pytest.mark.parametrize("scoped", [True, False])
def test_a_question_stays_a_question(stool, message, scoped):
    got = chat.offline_classify(stool, message, P if scoped else None)
    assert got.action == "answer", (message, scoped, got)


@pytest.mark.parametrize("message", QUESTIONS[:3])
def test_a_question_on_an_empty_design_never_authors_a_part(tmp_path, message):
    from caliper.design import DesignStore

    empty = DesignStore.create("a step stool", base=str(tmp_path))
    assert chat.offline_classify(empty, message, None).action == "answer"


#: changes main made, made still (scoped to the stool's one part)
@pytest.mark.parametrize("message", ["simpler legs", "a simpler joint", "simpler, with fewer pieces", "plainer finish",
                                     "make it look like a dinosaur and 2 in taller"])
def test_a_change_main_made_still_happens(stool, message):
    got = chat.offline_classify(stool, message, P)
    assert (got.action, got.part) == ("refine", P), (message, got)


@pytest.mark.parametrize("message", ["add two shelves under the step", "add shelves", "add legs", "add the lid",
                                     "add holes for the bolts", "add a shelf"])
def test_add_is_a_new_part_with_or_without_an_article_on_a_design_of_several(camper, message):
    got = chat.offline_classify(camper, message, None)
    assert got.action == "author", (message, got)


def test_on_a_design_of_several_an_unnamed_change_asks_which(camper):
    assert chat.offline_classify(camper, "make it 2 in wider", None).action == "answer"


@pytest.mark.parametrize("message", ["make it look like oak", "make it look like wood"])
def test_a_look_like_that_isnt_a_picture_offers_none(stool, message):
    got = chat.offline_classify(stool, message, P)
    assert not got.note.startswith("offer a picture"), got


def test_the_offer_says_an_before_a_vowel():
    assert "an owl" in chat._offer("owl") and "a dinosaur" in chat._offer("dinosaur")


def test_no_picture_offer_where_no_panel_can_take_one(tmp_path):
    from caliper.design import DesignStore

    from .test_printed_strength import PRINTED

    store = DesignStore.create("a printed box", base=str(tmp_path))
    store.write_part("box", PRINTED, intent="a printed box")
    got = chat.offline_classify(store, "make it look like a dinosaur", "box")
    assert not got.note.startswith("offer a picture"), got


def test_the_prompt_has_the_one_part_and_question_rules():
    s = chat._CLASSIFY_SYSTEM
    assert "on a design with one part changes that part" in s
    assert "A question stays a question" in s and "explain the build order" in s


# --- #212, round 2: a words request whatever verb starts it; a size added is a revision ----------------------------

@pytest.mark.parametrize("message", ["put it in plain English", "use plain words", "give it to me in plain English",
                                     "turn that into plain English", "say it in simpler words", "put that in plain words"])
@pytest.mark.parametrize("scoped", [True, False])
def test_a_words_request_is_a_question_whatever_verb_starts_it(stool, message, scoped):
    got = chat.offline_classify(stool, message, P if scoped else None)
    assert got.action == "answer", (message, scoped, got)


@pytest.mark.parametrize("message", ["add 2 inches to the height", "I need it 2 in wider", "add 10 mm to the depth"])
@pytest.mark.parametrize("scoped", [True, False])
def test_a_size_added_to_the_one_part_is_a_revision_not_a_new_part(stool, message, scoped):
    got = chat.offline_classify(stool, message, P if scoped else None)
    assert (got.action, got.part) == ("refine", P), (message, scoped, got)


def test_a_words_request_with_a_size_in_it_is_still_the_change(stool):
    got = chat.offline_classify(stool, "make it 2 in taller and put it in plain English", None)
    assert (got.action, got.part) == ("refine", P), got
