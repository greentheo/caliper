"""CALI-171 (#266), Theo's step-stool-5: the fillet strips added to fit the stool copied its sizes (stool_h 508, a 20 in stool)
when he'd made it 16 in through Parameters, and a later change wouldn't have moved them anyway. A part added to fit another
reads that part's numbers live: ``FOLLOWS = {"stool_h": ("stool", "h")}``, its PARAMS holding the current values, and writing
the source writes its followers (as a mirror follows its source, #246, and the skeleton drives its readers, #143). A synthetic
stool and strip, not Theo's."""

import pytest

pytest.importorskip("cadquery")

from caliper import aero, chat, follows, params  # noqa: E402
from caliper.design import DesignStore  # noqa: E402

STOOL = '''import cadquery as cq

PARAMS = {
    "t": 19.05,     # 3/4 in plywood
    "d": 200.0,     # depth
    "h": 406.4,     # 16 in, floor to the step
    "w": 300.0,     # width
}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, d, h, w = p["t"], p["d"], p["h"], p["w"]
    side = cq.Workplane().box(t, d, h, centered=False)
    step = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h))
    return side.union(step)
'''

#: A 5 mm strip in the corner under the step, at the stool's height, read through FOLLOWS.
STRIP = '''import cadquery as cq

FOLLOWS = {"stool_h": ("stool", "h"), "ply_t": ("stool", "t")}
PARAMS = {"r": 5.0, "stool_h": 406.4, "ply_t": 19.05}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().box(p["r"], 200.0, p["r"], centered=False).translate((p["ply_t"], 0, p["stool_h"] - p["r"]))
'''


@pytest.fixture
def two(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    s.write_part("stool", STOOL, intent="a side and a step")
    s.write_part("inside_fillets", STRIP, intent="fillet strips under the step")
    return s


def test_what_a_script_follows_is_read():
    assert follows.declared(STRIP) == {"stool_h": ("stool", "h"), "ply_t": ("stool", "t")}
    assert follows.declared(STOOL) == {}


def test_a_parameters_change_on_the_source_moves_its_follower(two):
    """Theo's: the stool's height through Parameters, and the strips move with it, in the same turn."""
    s = two
    was = s.design.part("inside_fillets").version
    got = params.set_value(s, "stool", "h", 18, "in")
    assert s.design.part("inside_fillets").version == was + 1
    assert aero.read_params(s.read_script("inside_fillets"))["stool_h"] == pytest.approx(457.2)
    top = s.part_geometry("inside_fillets").require_mesh().bounds[1][2]
    assert top == pytest.approx(457.2, abs=1e-6)                                   # it moved: under the step again
    assert "the inside fillets follow the stool: stool_h now 457.2 mm" in got["said"], got["said"]
    h = s.history("inside_fillets")[-1]
    assert h["action"] == "follow" and h.get("followed") == "stool" and "stool_h set to 457.2 mm by the stool" in h["feedback"]


def test_an_unchanged_follow_writes_nothing(two):
    s = two
    was = s.design.part("inside_fillets").version
    params.set_value(s, "stool", "w", 320, "mm")                                   # nothing it follows
    assert s.design.part("inside_fillets").version == was


def test_a_cycle_is_refused_in_words(two):
    s = two
    looped = STOOL.replace("PARAMS = {", 'FOLLOWS = {"t": ("inside_fillets", "ply_t")}\nPARAMS = {', 1)
    with pytest.raises(ValueError, match="the stool can't follow the inside fillets: the inside fillets follow the stool"):
        s.write_part("stool", looped)


def test_a_follower_says_when_what_it_follows_isn_t_there():
    """A source removed or renamed: said on its next build, and it keeps its last values."""
    r = follows.check(STRIP.replace('("stool", "h")', '("stool_v2", "h")'), {"stool": aero.read_params(STOOL)}, "inside_fillets")
    assert r.status == "pass" and "follows stool_v2's h, but there's no stool_v2 in the design now: it keeps 406.4 mm" \
        in r.detail, r.detail
    r = follows.check(STRIP.replace('("stool", "t")', '("stool", "ply")'), {"stool": aero.read_params(STOOL)}, "inside_fillets")
    assert r.status == "pass" and "the stool has no ply now: it keeps 19.05 mm" in r.detail, r.detail


def test_a_followed_number_that_isn_t_the_source_s_fails_the_round():
    """Theo's: stool_h 508, a 20 in stool, against the 16 in he'd made it."""
    r = follows.check(STRIP.replace('"stool_h": 406.4', '"stool_h": 508.0'), {"stool": aero.read_params(STOOL)}, "inside_fillets")
    assert r.status == "fail" and "stool_h is 508 mm, but the stool's h is 406.4 mm now" in r.detail, r.detail


def test_a_copied_number_is_a_note_unless_its_name_is_the_source_s():
    """Equal values happen by chance (19.05, 25.4, 50.8): a note. Named as the source's own number, it's a copy: a fail."""
    chance = STRIP.replace('FOLLOWS = {"stool_h": ("stool", "h"), "ply_t": ("stool", "t")}\n', "FOLLOWS = {}\n")
    chance = chance.replace('"stool_h": 406.4, "ply_t": 19.05', '"stool_h": 406.4, "lip_t": 19.05').replace('p["ply_t"]', 'p["lip_t"]')
    r = follows.check(chance, {"stool": aero.read_params(STOOL)}, "inside_fillets", on="stool")
    assert r.status == "fail" and "stool_h copies the stool's h (406.4 mm): read it through FOLLOWS" in r.detail, r.detail
    assert "lip_t is the stool's t (19.05 mm) too: if it's the same thing, read it through FOLLOWS" in r.detail
    only_chance = chance.replace('"stool_h": 406.4', '"lift": 400.0').replace('p["stool_h"]', 'p["lift"]')   # no name match
    r = follows.check(only_chance, {"stool": aero.read_params(STOOL)}, "inside_fillets", on="stool")
    assert r.status == "pass" and "lip_t is the stool's t (19.05 mm) too" in r.detail, r.detail


def test_a_part_added_on_another_is_told_its_numbers_and_to_follow_them(two):
    """The designer reads the stool's PARAMS (its comments true), and a copy fails the round until it follows."""
    s = two
    copied = STRIP.replace('FOLLOWS = {"stool_h": ("stool", "h"), "ply_t": ("stool", "t")}\n', "").replace(
        '"stool_h": 406.4', '"stool_h": 508.0')
    seen = []

    def author(spec, feedback, prior):
        seen.append((spec.intent, feedback))
        return copied if len(seen) == 1 else STRIP
    res = chat.author_part(s, "more_fillets", "fillet strips under the step", author=author, use_llm=False,
                           promote_feedback=False, on="stool", max_rounds=3)
    asked = seen[0][0]
    assert "The stool's numbers (its PARAMS, in mm):" in asked and '"h": 406.4,     # 16 in, floor to the step' in asked, asked
    assert 'FOLLOWS = {"your_name": ("stool", "t")}' in asked
    assert len(seen) == 2 and "stool_h is the stool's h by its name, at 508 mm against 406.4 mm on it: read it through " \
        "FOLLOWS" in seen[1][1], seen[1][1]
    assert res.ok and follows.declared(s.read_script("more_fillets"))


def test_a_change_asked_in_the_chat_says_what_followed(two):
    s = two

    def author(spec, feedback, prior):
        return STOOL.replace('"h": 406.4,     # 16 in, floor to the step', '"h": 457.2,     # 18 in, floor to the step')
    res = chat.refine_part(s, "stool", "make it 18 in tall", author=author, use_llm=False, promote_feedback=False)
    assert "The inside fillets follow the stool: stool_h now 457.2 mm." in res.reply, res.reply
    assert aero.read_params(s.read_script("inside_fillets"))["stool_h"] == pytest.approx(457.2)
    assert follows.said(s) == ""                                                   # said once, in its own turn
