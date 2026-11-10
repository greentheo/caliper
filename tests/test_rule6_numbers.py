"""CALI-88 (#64; rule 6): the numbers a person reads are never greener than the check behind them."""

import pytest

from caliper import answers, verdicts


# --- item 1: a failing safety never rounds up to its limit ----------------------------------------------------------

@pytest.mark.parametrize("x, need, said", [
    (1.96, 2, "1.96 times over"),          # a fail: "only 2 times over, and it needs 2" read as a pass
    (1.999, 2, "1.99 times over"),         # cut, never rounded onto the limit
    (2.04, 2, "2.04 times over"),          # within 10% of the limit: the places that tell it from the limit
    (0.96, 2, "0.9 times over"),           # a fail well under: one place, cut
    (1.67, 2, "1.6 times over"),           # not the greener 1.7
    (2.4, 2, "2.4 times over"),            # clear of the limit: one place, as before
    (3.11, 2, "3.1 times over"),
    (9.96, 2, "9.9 times over"),           # not "more than 10"
    (10.0, 2, "more than 10 times over"),  # only from 10.0
])
def test_a_safety_is_said_to_the_places_that_keep_it_on_its_side_of_the_limit(x, need, said):
    assert answers._times(x, need=need) == said


def test_without_a_limit_it_never_rounds_up_to_ten():
    assert answers._times(9.96) == "9.9 times over" and answers._times(10.0) == "more than 10 times over"
    assert answers._times(3.11) == "3.1 times over"


def test_a_fail_line_never_says_the_limit_it_missed():
    run = {"min_safety": 2.0, "spacing_mm": 3.0, "cases": [{"name": "Dad stepping up", "lb": 200, "factor": 2.0,
                                                            "safety": 1.96, "holds": False,  # producer: a fail
                                                            "fea": {"supported": True, "safety": 1.96}, "governs": "fea"}]}
    c = run["cases"][0]
    v = verdicts.case(run, c)
    assert v["kind"] == "fails" and v["short"] == "doesn't hold 1.9x", v["short"]   # the badge, cut not rounded
    text = answers._case_line("stool", run, c, None, False, True)["text"]
    assert "only 1.96 times over 400 lb (200 lb, twice over), and it needs 2" in text, text


# --- item 2: a pass close to the line is amber ----------------------------------------------------------------------

def _run(safety, need=2.0):
    return {"min_safety": need, "spacing_mm": 3.0, "safety": safety,
            "cases": [{"name": "Dad stepping up", "lb": 200, "factor": need, "safety": safety,
                       "holds": safety >= need,  # producer: the study's own number
                       "fea": {"supported": True, "safety": safety}, "governs": "fea"}]}


@pytest.mark.parametrize("safety, kind, status", [(2.4, "close", "warn"), (2.5, "close", "warn"), (2.6, "holds", "ok"),
                                                  (1.9, "fails", "bad")])
def test_a_pass_within_a_quarter_of_its_limit_is_amber(safety, kind, status):
    run = _run(safety)
    v = verdicts.run(run)
    assert (v["kind"], v["status"]) == (kind, status)
    assert v["counts_as_pass"] == (safety >= 2)                     # close to the line still holds
    assert verdicts.meets(safety, 2.0)["kind"] == kind


def test_the_card_line_says_how_close():
    run = _run(2.4)
    line = answers._case_line("stool", run, run["cases"][0], None, False, True)
    assert line["status"] == "warn" and line["text"] == "Holds dad stepping up, 2.4 times over 400 lb (200 lb, twice over): close to the 2 it needs.", line
    far = _run(2.6)
    assert answers._case_line("stool", far, far["cases"][0], None, False, True)["status"] == "ok"


# --- item 15: the design card's strength line says what it does, then what it needs ---------------------------------

def test_the_design_cards_strength_line_reads_as_the_parts_does(tmp_path):
    """"✓ Holds Dad (200 lb), 2 times over (assumed): 3.11x" read as if it held 2 times over: the 2 is what it
    needs, 3.1 what it does (the foreman's walk at ea6adf1)."""
    from caliper import design_api, samples

    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    lines = [ln["text"] for c in answers.answers(store, design_api.design_state(store)) for ln in c["lines"]]
    assert "✓ Holds Dad (200 lb), 3.1 times over (it needs 2, assumed)." in lines, lines
    assert not [t for t in lines if "2 times over (assumed)" in t], lines


@pytest.mark.parametrize("label, head", [("holds Dad (200 lb), 2 times over", "holds Dad (200 lb)"),
                                         ("holds Dad (200 lb), twice over", "holds Dad (200 lb)"),
                                         ("holds Dad (200 lb), 2.5 times over", "holds Dad (200 lb)"),
                                         ("Holds a 250 lb person sitting, 2× safety", "Holds a 250 lb person sitting"),
                                         ("strong enough for the kids", "strong enough for the kids")])
def test_a_strength_goals_label_loses_only_its_own_need(label, head):
    assert answers._without_need(label) == head


# --- item 16: a chat reply's strength number rounds as the cards do, and carries the promise ------------------------

def _picture(safety):
    return {"ok": True, "subject": "T-rex", "panel": "front", "size_in": [6, 8], "safety": safety, "min_safety": 2.0,
            "holds": safety >= 2.0}  # producer: the picture's re-check, as pictures.put returns it


def test_a_pictures_reply_rounds_as_the_card_does_and_points_to_the_promise():
    from caliper import pictures

    held = pictures.reply(_picture(3.11))
    assert "It still holds, 3.1 times over (it needs 2)." in held and answers.PROMISE_POINTER in held, held
    near = pictures.reply(_picture(2.04))
    assert "2.04 times over" in near and answers.PROMISE_POINTER in near, near
    failed = pictures.reply(_picture(1.96))
    assert "it reads 1.96 times over and needs 2" in failed, failed      # never "2 times over and needs 2"


def test_a_carves_reply_rounds_as_the_card_does_and_points_to_the_promise(monkeypatch, tmp_path):
    from caliper import carve, chat
    from caliper.design import DesignStore

    from .test_studies import _carve

    rec = {**_carve([2.5, 2.4, 2.3, 1.2]), "share": "printed", "id": "x", "part": "p", "notes": []}
    rec["stations"][2]["safety"] = 2.04                           # the step it offers, close to its limit
    monkeypatch.setattr(carve, "study", lambda *a, **k: rec)
    store = DesignStore.create("a stool", base=str(tmp_path))
    store.write_part("p", "def build(params):\n    return None\n", intent="x")
    said = chat.carve_part(store, "p").reply
    assert "about 2.04 times over" in said and answers.PROMISE_POINTER in said, said


# --- item 9: one way of saying it, everywhere a person reads it -----------------------------------------------------

def test_the_card_the_kids_book_the_trial_panel_and_the_build_book_say_the_same(tmp_path):
    """The kids' test page said "3.1 times over" while the trial page said ~6.2x of 200 lb: one number, against one
    thing. The foreman's pick (#64, option B): the safety against the load with its factor, as the cards always said
    it, with what that is said beside it, so 3.1 x 200 lb isn't read as where it breaks."""
    from caliper import design_api, kidbook, release, samples, trials

    store = samples.open_sample("step-stool", base=str(tmp_path / "designs"))
    said = "3.1 times over 400 lb (200 lb, twice over)"
    card = [ln["text"] for ln in answers.answers(store, design_api.design_state(store), "step_stool")[1]["lines"]]
    assert f"Holds 200 lb adult stepping up, {said}." in card, card
    strength = release._strength(store, {p.id: p.version for p in store.design.parts})
    assert said in kidbook._strength_page(strength, ["step_stool"])["say"]
    assert trials.predict(store, "step_stool")["over"] == said
    (c,) = strength["step_stool"]
    assert release._safety_cell(c)[0] == "3.1x" and (c["lb"], c["factor"]) == (200, 2)   # its row says "200 lb × 2"
