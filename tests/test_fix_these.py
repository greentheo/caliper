"""CALI-189 (#300) slice B — Fix these: the ticked rows done, cheapest first, then measured again.

The cost said first (pressing Fix these is the person's word for any designer call it names); numbers through the
Parameters route, no model call; the designer's items as one revise of the part; the strength check again where it's
out of date; then the list again, each row Fixed only where a measurement says so, Still open, or Not done (the designer
left the part as it was). The designer is stubbed in every test: no live call."""

import json

import pytest

from caliper import design_api, fixes, fixing, review
from caliper.design import DesignStore

from .test_fix_list import _resave, _run
from .test_load_study import BOX_STOOL
from .test_make_it_better import _check, _plate, _store

pytest.importorskip("cadquery")


@pytest.fixture(autouse=True)
def _no_findings(monkeypatch):
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [], "checks": 0})


def _rows(store, pid="stool"):
    return fixes.listed(store, design_api.design_state(store), pid)["rows"]


def _failing_plate(tmp_path):
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4, plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {"top": "t"}})
    return store


class Designer:
    """refine_part, stubbed: records each message; writes a new version (the same script, marked) unless told not to."""

    def __init__(self, change=True):
        self.calls, self.change = [], change

    def __call__(self, store, pid, message, **kw):
        from caliper.chat import TurnResult

        self.calls.append(message)
        self.kw = kw
        if self.change:
            v = store.write_part(pid, store.read_script(pid) + f"\n# revised {len(self.calls)}\n", intent="revised")
            return TurnResult(action="refine", reply="✓ revised", ok=True, part=pid, version=v)
        return TurnResult(action="refine", reply="I left it as it was.", ok=True, part=pid,
                          version=store.design.part(pid).version)


def _holds_after(monkeypatch):
    """The strength check, stubbed: a run of this version that holds, its plate fine."""
    from caliper import load_study

    def study(store, pid, **kw):
        _check(store, pid, 3.1, rid=f"20261116-1{store.design.part(pid).version:05d}-check")
        return _run(store)

    monkeypatch.setattr(load_study, "study", study)


def test_the_cost_is_said_first_naming_the_designer_call(tmp_path):
    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    p = fixing.plan(store, design_api.design_state(store), "stool", [{"id": row["id"], "choice": 0}],
                   own=[{"fix": "round the top's corners"}])
    assert [c["param"] for c in p["numbers"]] == ["t"] and [d["fix"] for d in p["designer"]] == ["round the top's corners"]
    fix = row["choices"][0]["fix"]
    assert p["said"] == (f"1 number change, at once (t: {fix[:1].lower() + fix[1:]}); 1 designer edit on the stool "
                         "(one Claude call); then a check, about 1 min")               # what it moves, at Go ahead
    assert p["designer_call"] is True


def test_numbers_go_through_parameters_with_no_model_call_and_a_measured_fix_reads_fixed(tmp_path, monkeypatch):
    from caliper import chat, params

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    seen = []

    def set_values(store, pid, changes):
        seen.append(changes)
        return {"version": store.write_part(pid, store.read_script(pid) + "\n# t\n", intent="t"), "said": "set"}

    monkeypatch.setattr(params, "set_values", set_values)
    monkeypatch.setattr(chat, "refine_part", lambda *a, **k: pytest.fail("no designer for a number"))
    _holds_after(monkeypatch)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    assert seen == [[{"name": "t", "value": 15.875, "unit": "mm"}]]
    (r,) = got["results"]
    assert r["id"] == "plate:top" and r["status"] == "fixed", r                      # gone from a fresh check's list


def test_the_designer_s_items_go_as_one_revise_and_own_rows_are_never_fixed(tmp_path, monkeypatch):
    from caliper import chat

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1)
    found = [{"kind": "fit", "parts": ["stool"], "said": "the rail has 19.1 mm of play", "fix": "Size the pocket to it.",
              "measured": True},
             {"kind": "mirror", "parts": ["stool"], "said": "its sides aren't mirrors", "fix": "Mirror the left side.",
              "measured": True}]
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": list(found)})
    rows = _rows(store)
    designer = Designer()
    monkeypatch.setattr(chat, "refine_part", designer)
    _holds_after(monkeypatch)

    def after(store, report=None):                                    # the designer fixed the fit, not the mirror
        return {"findings": [found[1]]}

    picked = [{"id": r["id"], "choice": 0} for r in rows]
    monkeypatch.setattr(review, "findings", lambda store, report=None: after(store) if designer.calls else {"findings": found})
    got = fixing.apply(store, "stool", picked, own=[{"fix": "round the top's corners"}])
    assert len(designer.calls) == 1                                               # one revise, everything in it
    assert designer.kw.get("keep_same") is False                     # the same code back writes no version (#322)
    msg = designer.calls[0]
    assert "Size the pocket to it" in msg and "Mirror the left side" in msg and "round the top's corners" in msg
    status = {r["fix"]: r["status"] for r in got["results"]}
    assert status["Size the pocket to it"] == "fixed" and status["Mirror the left side"] == "still open"
    assert status["round the top's corners"] == "done, not measured"               # the person's words: never "fixed"


def test_an_item_the_designer_left_as_it_was_reads_not_done(tmp_path, monkeypatch):
    from caliper import chat

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 3.1)
    monkeypatch.setattr(review, "findings", lambda store, report=None: {"findings": [
        {"kind": "fit", "parts": ["stool"], "said": "play", "fix": "Size the pocket.", "measured": True}]})
    (row,) = _rows(store)
    designer = Designer(change=False)
    monkeypatch.setattr(chat, "refine_part", designer)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    (r,) = got["results"]
    assert len(designer.calls) == 1 and r["status"] == "not done", r


def test_a_row_the_check_couldn_t_measure_again_is_never_fixed(tmp_path, monkeypatch):
    from caliper import load_study, params

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setattr(params, "set_values", lambda store, pid, ch: {"version": store.write_part(
        pid, store.read_script(pid) + "\n# t\n", intent="t")})

    def broke(*a, **k):
        raise RuntimeError("the check fell over")

    monkeypatch.setattr(load_study, "study", broke)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    (r,) = got["results"]
    assert r["status"] == "still open" and "not checked again" in r["why"], r          # gone only for want of a check


@pytest.mark.parametrize("words", ["Make the top from 1 in", None])
def test_a_row_whose_piece_was_renamed_is_still_open_not_fixed(tmp_path, monkeypatch, words):
    """reviewer-2's must-fix 2: the designer renamed the step to the top and left it 3/4 in. Its row's id changed, so it
    was "off the list": "fixed". Fixed is the cases it spoke for passing, or no new row covering them."""
    from caliper import chat, load_study, params

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    assert row["id"] == "plate:top" and row["cases"] == ["a foot"]
    monkeypatch.setattr(params, "set_values", lambda store, pid, ch: {"version": store.write_part(
        pid, store.read_script(pid) + "\n# t\n", intent="t")})              # its own choice, the number, or yours
    designer = Designer()
    monkeypatch.setattr(chat, "refine_part", designer)

    def study(store, pid, **kw):                                   # the same panel, renamed: still 1.4x
        _check(store, pid, 1.4, rid=f"20261116-1{store.design.part(pid).version:05d}-check",
               plate={**_plate(t=12.7), "piece": "seat", "safety_across": 1.4}, sheet={"pieces": {"seat": "t"}})

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": words}])
    assert [r["id"] for r in _rows(store)] == ["plate:seat"]
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "it's measured as 'the seat' now"), r


def test_a_row_whose_case_isn_t_checked_any_more_is_still_open(tmp_path, monkeypatch):
    """reviewer-2's rule, its gap (the foreman's must-fix on #322): the designer renamed the case, so the fresh run has no
    'a foot' and no row speaks for it. That's not a fix: every case it spoke for must be in the fresh run, and pass."""
    from caliper import chat, load_study

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setattr(chat, "refine_part", Designer())

    def study(store, pid, **kw):                                   # the same panel, its case now called 'a hand'
        _check(store, pid, 3.1, rid=f"20261116-1{store.design.part(pid).version:05d}-check")
        run = _run(store)
        run["cases"][0]["name"] = "a hand"
        _resave(store, run)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Make the top from 1 in"}])
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "'a foot' isn't checked any more"), r


def test_a_joint_fixed_while_its_case_fails_on_the_plate_is_fixed_and_says_the_case_still_fails(tmp_path, monkeypatch):
    """reviewer-2's small ask: a fixed joint read "measured as 'the top' now", blaming the joint for the plate. A row looks
    only at rows of its own kind."""
    from caliper import chat, load_study

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4)
    run = _run(store)
    weak = {"pieces": ["front rail", "left side"], "between": "the front rail and the left side", "mode": "withdrawal",
            "safety": 1.4, "need": 2.0, "holds": False, "said": "two #8 screws pulled out of the front rail's edge"}
    run["cases"][0].update(governs="joint", joints={"chain": True, "n": 1, "unchecked": [], "governing": weak, "rows": [weak]})
    _resave(store, run)
    (row,) = _rows(store)
    assert row["id"] == "joint:front rail|left side"
    monkeypatch.setattr(chat, "refine_part", Designer())

    def study(store, pid, **kw):                                   # the joint holds now (2.4x); the top fails by the plate
        _check(store, pid, 1.4, rid=f"20261116-1{store.design.part(pid).version:05d}-check",
               plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {"top": "t"}})
        fresh = _run(store)                                         # a real run lists every joint it checks, holding too
        held = {**weak, "safety": 2.4, "holds": True}
        fresh["cases"][0]["joints"] = {"chain": True, "n": 1, "unchecked": [], "governing": held, "rows": [held]}
        _resave(store, fresh)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    assert [r["id"] for r in _rows(store)] == ["plate:top"]
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("fixed", "fixed (the joint), and the case still fails: the top's plate"), r


def test_a_row_whose_cases_now_pass_is_fixed_though_another_row_speaks_of_them(tmp_path, monkeypatch):
    """The foreman's rule, its first half: the cases it spoke for pass in the fresh check, so it's fixed, though a joint
    in the same case is a row of its own."""
    from caliper import load_study, params

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setattr(params, "set_values", lambda store, pid, ch: {"version": store.write_part(
        pid, store.read_script(pid) + "\n# t\n", intent="t")})
    weak = {"pieces": ["leg", "top"], "between": "the top and the leg", "mode": "shear", "safety": 1.5, "need": 2.0,
            "holds": False, "said": "two #8 screws in shear"}

    def study(store, pid, **kw):
        _check(store, pid, 3.1, rid=f"20261116-1{store.design.part(pid).version:05d}-check")
        run = _run(store)
        run["cases"][0]["joints"] = {"chain": True, "n": 1, "unchecked": [], "governing": weak, "rows": [weak]}
        _resave(store, run)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    assert [(r["id"], r["cases"]) for r in _rows(store)] == [("joint:leg|top", ["a foot"])]
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("fixed", "measured: it's off the list now"), r      # its cases pass: nothing more


def test_a_rule_is_known_by_its_own_id_so_fixing_another_never_credits_it(tmp_path, monkeypatch):
    """reviewer-2's must-fix 3: rules A and B failing, B ticked, the designer's change fixed A. By position B became
    rule:0 and rule:1 read "fixed"."""
    from caliper import chat, part_rules

    store = _store(tmp_path, BOX_STOOL, "stool")
    designer = Designer()
    monkeypatch.setattr(chat, "refine_part", designer)
    a, b = {"id": "wall", "said": "A: the wall is at least 3 mm"}, {"id": "width", "said": "B: it's 400 mm wide"}
    monkeypatch.setattr(part_rules, "failing", lambda rules: [b] if designer.calls else [a, b])
    rows = {r["problem"]: r for r in _rows(store)}
    assert [r["id"] for r in rows.values()] == ["rule:wall", "rule:width"]
    got = fixing.apply(store, "stool", [{"id": "rule:width", "choice": 0}], check=False)
    (r,) = got["results"]
    assert (r["id"], r["status"]) == ("rule:width", "still open"), r


def test_keep_mine_settles_an_open_question_with_no_designer(tmp_path, monkeypatch):
    from caliper import chat
    from caliper import scenarios as S

    from .test_scenarios import RAISED, RATED

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a step stool")
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, got["scenarios"][1]], got["supports"])
    store.write_part("stool", RAISED, intent="heavier")
    (row,) = [r for r in _rows(store) if r["id"].startswith("asked:")]
    keep = next(i for i, c in enumerate(row["choices"]) if c["take"] == "mine")
    monkeypatch.setattr(chat, "refine_part", lambda *a, **k: pytest.fail("no designer for a load"))
    res = fixing.apply(store, "stool", [{"id": row["id"], "choice": keep}], check=False)
    assert S.asked(store, "stool") == []                                           # settled at 260 lb
    (r,) = res["results"]
    assert r["status"] == "fixed", r


def test_an_open_question_left_unticked_is_named_and_left_as_it_is(tmp_path, monkeypatch):
    """#318: an untouched question never settles itself: Fix these says it's left open, by name, and leaves it."""
    from caliper import scenarios as S

    from .test_scenarios import RAISED, RATED

    store = DesignStore.create("a step stool", base=str(tmp_path / "designs"))
    store.write_part("stool", RATED, intent="a step stool")
    got = S.get(store, "stool")
    S.put(store, "stool", [{**got["scenarios"][0], "amount": 260}, got["scenarios"][1]], got["supports"])
    store.write_part("stool", RAISED, intent="heavier")
    p = fixing.plan(store, design_api.design_state(store), "stool", [], own=[])
    assert p["left"] == ["You'd edited 'stepping on the front edge' to 260 lb; " + p["left"][0].split("; ", 1)[1]]
    assert p["said"].startswith("nothing to do; left open: you'd edited 'stepping on the front edge' to 260 lb")
    fixing.apply(store, "stool", [], check=False)
    (still,) = S.asked(store, "stool")
    assert still.startswith("you'd edited 'stepping on the front edge' to 260 lb")             # still asked


def test_the_route_plans_then_runs_a_fix_job_and_needs_claude_for_the_designer(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    c = TestClient(create_app())
    base = f"/api/designs/{store.design.slug}/parts/stool/fixes"
    p = c.post(base + "/plan", json={"picked": [{"id": row["id"], "choice": 0}], "own": []}).json()
    assert p["said"].startswith("1 number change, at once") and p["designer_call"] is False
    monkeypatch.setattr(design_api, "_claude", lambda: False)
    no = c.post(base, json={"picked": [], "own": [{"fix": "round the corners"}]})
    assert no.status_code == 409 and "Claude" in no.json()["detail"]
    assert design_api.DOING["fix"] == "fixed"


# --- the page ---------------------------------------------------------------------------------------------------------

def _page(extra):
    from .test_carve_click import _page as page, _run

    return _run(page(["fixesView", "fixRow", "fixGo", "fixTicked"], consts=["esc", "fixRowKey"], extra=extra))


LIST = {"part": "stool", "rows": [{"id": "plate:top", "problem": "The top fails", "part": "stool", "measured": True,
                                   "choices": [{"fix": "Make the top from 5/8 in", "kind": "number", "cost": "x"}]}],
        "limits": []}


def test_the_page_says_the_cost_before_it_runs_and_each_row_s_status_after():
    html = _page(f"out = fixesView({json.dumps(LIST)}, {{}});")
    assert 'data-fix-plan="1"' in html and "Fix these" in html and "Go ahead" not in html
    planned = {"plan": {"said": "1 number change, at once; then a check, about 1 min"}}
    html = _page(f"out = fixesView({json.dumps(LIST)}, {json.dumps(planned)});")
    assert "It takes 1 number change, at once; then a check, about 1 min." in html and 'data-fix-go="1"' in html
    done = {"results": [{"id": "plate:top", "fix": "Make the top from 5/8 in", "status": "fixed", "why": "measured"},
                        {"id": None, "fix": "round the corners", "status": "done, not measured", "why": "your words"}]}
    html = _page(f"out = fixesView({json.dumps(LIST)}, {json.dumps(done)});")
    assert "Make the top from 5/8 in: <b>fixed</b>" in html and "round the corners: <b>done, not measured</b>" in html


def test_the_page_sends_rows_by_id_and_choice_through_the_plan_then_the_job():
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")).read()
    assert "api('POST', `/api/designs/${S.slug}/parts/${part}/fixes/plan`, fixPicked(part))" in src
    assert "api('POST', `/api/designs/${S.slug}/parts/${part}/fixes`, fixPicked(part))" in src
    assert "trackJob(job_id, { kind: 'fix', part, text: 'fixing…' }).done" in src
    assert "id: r.id, choice: mine.pick[fixRowKey(r)] || 0," in src            # never a value, but the person's words


def test_the_page_badges_your_loads_and_leaves_an_open_question_unticked_until_you_tick_it():
    rows = {"part": "stool", "limits": [], "rows": [
        {"id": "asked:x", "problem": "You'd edited x", "part": "stool", "measured": False, "badge": "your loads",
         "ticked": False, "choices": [{"fix": "Keep mine", "kind": "loads", "cost": "c"}]}]}
    html = _page(f"out = fixesView({json.dumps(rows)}, {{}});")
    assert "your loads" in html and ">measured<" not in html
    tick = html.split('data-fix-tick="', 1)[1].split(">", 1)[0]
    assert " checked" not in tick                                                  # unticked until you tick it
    html = _page(f"out = fixesView({json.dumps(rows)}, {{tick: ['asked:x|You\\'d edited x']}});")
    assert " checked" in html.split('data-fix-tick="', 1)[1].split(">", 1)[0]         # ticked once you tick it
    src = open(__file__.replace("tests/test_fix_these.py", "src/caliper/web/static/design.js")).read()
    assert "picked: (got.rows || []).filter((r) => fixTicked(r, mine))" in src


def test_two_rows_on_one_parameter_are_one_change_and_the_other_is_said_not_done(tmp_path, monkeypatch):
    """reviewer-2: two number rows on one parameter counted "2 number changes" and set only the first's value."""
    from caliper import params

    store = _failing_plate(tmp_path)
    two = [{"id": f"plate:{n}", "problem": f"The {n} fails", "part": "stool", "measured": True, "cases": ["a foot"],
            "choices": [{"fix": f"Make the {n} from {lab}", "kind": "number", "cost": "x", "param": "t", "value": v,
                         "unit": "mm"}]} for n, lab, v in (("top", "5/8 in", 15.875), ("seat", "1 in", 25.4))]
    monkeypatch.setattr(fixing, "listed", lambda *a, **k: {"part": "stool", "rows": list(two), "limits": []})
    seen = []
    monkeypatch.setattr(params, "set_values", lambda store, pid, ch: seen.append(ch) or {"version": store.write_part(
        pid, store.read_script(pid) + "\n# t\n", intent="t")})
    picked = [{"id": "plate:top", "choice": 0}, {"id": "plate:seat", "choice": 0}]
    p = fixing.plan(store, design_api.design_state(store), "stool", picked)
    assert p["said"].startswith("1 number change, at once (t: make the top from 5/8 in); ")
    assert "“Make the seat from 1 in” isn't done: it sets t too, and the first one's 15.875 mm goes" in p["said"]
    got = fixing.apply(store, "stool", picked, check=False)
    assert seen == [[{"name": "t", "value": 15.875, "unit": "mm"}]]
    r = {x["id"]: x for x in got["results"]}
    assert (r["plate:seat"]["status"], r["plate:seat"]["why"]) == ("not done", "it sets t too: the first one's value went")


def test_the_fix_route_refuses_while_a_job_works_on_the_part(tmp_path, monkeypatch):
    """reviewer-2's survivor: a fix started while a check, a Lighten or a carve works on the part refuses in words, never
    queues silently behind it (#302)."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))

    def busy(slug, parts):
        assert parts == ["stool"]
        raise HTTPException(409, "stool is being checked: wait for it, or stop that first.")

    monkeypatch.setattr(design_api, "_refuse_while_busy", busy)
    r = TestClient(create_app()).post(f"/api/designs/{store.design.slug}/parts/stool/fixes",
                                      json={"picked": [{"id": row["id"], "choice": 0}], "own": []})
    assert r.status_code == 409 and "being checked" in r.json()["detail"]


# --- round four: "fixed (the X)" is the row's own measurement in the fresh run (#322, reviewer-2 at 03a312a) -----------
WEAK = {"pieces": ["front rail", "left side"], "between": "the front rail and the left side", "mode": "withdrawal",
        "safety": 1.62, "need": 2.0, "holds": False, "said": "two #8 screws pulled out of the front rail's edge"}


def _fresh(plate_piece="top", across=1.91):
    """The 500 lb run's shape: one case, the plate at ``across``, a front-rail joint at 1.62x governing it."""
    def study(store, pid, **kw):
        _check(store, pid, 1.62, rid=f"20261116-1{store.design.part(pid).version:05d}-check",
               plate={**_plate(t=12.7), "piece": plate_piece, "safety_across": across},
               sheet={"pieces": {plate_piece: "t"}})
        run = _run(store)
        run["cases"][0].update(governs="joint", joints={"chain": True, "n": 1, "unchecked": [], "governing": WEAK,
                                                        "rows": [WEAK]})
        _resave(store, run)
    return study


def test_a_plate_still_failing_under_a_joint_that_governs_now_is_still_open(tmp_path, monkeypatch):
    """reviewer-2's real run: step-stool-5 at 500 lb, every panel thickened, the step's plate 1.91x and the front rail's
    joints at 1.62x governing. The plate row went (it's made only where the plate governs) and read "fixed (the plate)"."""
    from caliper import chat, load_study

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    assert row["id"] == "plate:top"
    monkeypatch.setattr(chat, "refine_part", Designer())
    monkeypatch.setattr(load_study, "study", _fresh())
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Make every panel 1 in"}])
    assert [r["id"] for r in _rows(store)] == ["joint:front rail|left side"]        # no plate row: the joint governs
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "measured: the top's plate is still 1.91× where it needs 2×"), r


def test_a_plate_whose_piece_isn_t_in_the_fresh_run_is_not_measured_as_fixed(tmp_path, monkeypatch):
    from caliper import chat, load_study

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setattr(chat, "refine_part", Designer())
    monkeypatch.setattr(load_study, "study", _fresh(plate_piece="seat", across=2.5))   # renamed, and the seat holds
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Make the top from 1 in"}])
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "not measured as fixed"), r


def test_a_plate_fixed_while_a_joint_fails_its_case_says_the_joint_in_its_own_words(tmp_path, monkeypatch):
    """The small ask: "the joint between the front rail and the left side's joint" said the joint twice."""
    from caliper import chat, load_study

    store = _failing_plate(tmp_path)
    (row,) = _rows(store)
    monkeypatch.setattr(chat, "refine_part", Designer())
    monkeypatch.setattr(load_study, "study", _fresh(across=2.3))                       # the plate holds now
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Make the top from 1 in"}])
    (r,) = got["results"]
    assert (r["status"], r["why"]) == (
        "fixed", "fixed (the plate), and the case still fails: the joint between the front rail and the left side"), r


def test_a_joint_the_fresh_run_doesn_t_check_is_not_measured_as_fixed(tmp_path, monkeypatch):
    """Its own joint by its pieces, not the first joint listed: another joint holding says nothing of this one."""
    from caliper import chat, load_study

    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4)
    run = _run(store)
    weak = {**WEAK, "safety": 1.4}
    run["cases"][0].update(governs="joint", joints={"chain": True, "n": 1, "unchecked": [], "governing": weak, "rows": [weak]})
    _resave(store, run)
    (row,) = _rows(store)
    monkeypatch.setattr(chat, "refine_part", Designer())

    def study(store, pid, **kw):                     # the back rail's joint now, holding; the front rail's not checked
        _check(store, pid, 1.4, rid=f"20261116-1{store.design.part(pid).version:05d}-check",
               plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {"top": "t"}})
        fresh = _run(store)
        other = {**WEAK, "pieces": ["back rail", "left side"], "between": "the back rail and the left side",
                 "safety": 2.4, "holds": True}
        fresh["cases"][0]["joints"] = {"chain": True, "n": 1, "unchecked": [], "governing": other, "rows": [other]}
        _resave(store, fresh)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0}])
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "not measured as fixed"), r


def test_a_panel_that_still_buckles_while_the_plate_governs_is_still_open(tmp_path, monkeypatch):
    from caliper import chat, load_study

    side = {"done": True, "piece": "left side", "thickness_mm": 12.7, "safety": 1.4, "down": True}
    store = _store(tmp_path, BOX_STOOL, "stool")
    _check(store, "stool", 1.4)
    run = _run(store)
    run["cases"][0].update(governs="buckling", buckling=[side])
    _resave(store, run)
    (row,) = _rows(store)
    assert row["id"] == "buckling:left side"
    monkeypatch.setattr(chat, "refine_part", Designer())

    def study(store, pid, **kw):                     # the top's plate governs now; the side still buckles at 1.5x
        _check(store, pid, 1.4, rid=f"20261116-1{store.design.part(pid).version:05d}-check",
               plate={**_plate(t=12.7), "safety_across": 1.4}, sheet={"pieces": {"top": "t"}})
        fresh = _run(store)
        fresh["cases"][0]["buckling"] = [{**side, "safety": 1.5}]
        _resave(store, fresh)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Brace the left side"}])
    assert "buckling:left side" not in [r["id"] for r in _rows(store)]           # the plate governs: no buckling row
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "measured: the left side's buckling is still 1.5× where it needs 2×"), r


def test_a_plate_row_for_two_cases_is_fixed_only_where_it_holds_in_both(tmp_path, monkeypatch):
    """Its worst case decides: the plate holding under one case says nothing of the other (reviewer-2's two stepping cases)."""
    from caliper import chat, load_study

    store = _failing_plate(tmp_path)
    run = _run(store)
    run["cases"].append({**run["cases"][0], "name": "a hand"})
    _resave(store, run)
    (row,) = _rows(store)
    assert row["cases"] == ["a foot", "a hand"]
    monkeypatch.setattr(chat, "refine_part", Designer())

    def study(store, pid, **kw):                     # both cases fail by the joint; the plate holds under 'a foot' only
        _fresh(across=2.3)(store, pid)
        fresh = _run(store)
        fresh["cases"].append({**fresh["cases"][0], "name": "a hand",
                               "plate": {**fresh["cases"][0]["plate"], "safety_across": 1.91}})
        _resave(store, fresh)

    monkeypatch.setattr(load_study, "study", study)
    got = fixing.apply(store, "stool", [{"id": row["id"], "choice": 0, "words": "Make the top from 1 in"}])
    (r,) = got["results"]
    assert (r["status"], r["why"]) == ("still open", "measured: the top's plate is still 1.91× where it needs 2×"), r


#: the other front joint of the pair: the stool is symmetric, and the list makes each its own row
RIGHT = {**WEAK, "pieces": ["front rail", "right side"], "between": "the front rail and the right side"}


def _pair(left):
    """One stepping case: the left front joint at ``left``, the right one at 1.62x governing, and the fresh list's row for
    the right joint speaking for the case."""
    run = {"min_safety": 2.0, "cases": [{"name": "a foot", "safety": 1.62, "governs": "joint",
                                         "joints": {"governing": RIGHT, "rows": [{**WEAK, "safety": left}, RIGHT]}}]}
    rows = [{"id": "joint:front rail|right side", "cases": ["a foot"], "what": "the joint between the front rail and the right side",
             "problem": "The joint between the front rail and the right side gives too"}]
    item = {"id": "joint:front rail|left side", "cases": ["a foot"], "what": "the joint between the front rail and the left side"}
    return fixing._moved(item, run, rows)


def test_one_joint_of_a_pair_fixed_is_fixed_never_measured_as_the_other():
    """caliper-reviewer at 28b0707: the left front joint fixed at 2.4x read "still open: it's measured as 'the joint between
    the front rail and the right side' now". The other joint of a pair isn't a rename: the left one's own number decides."""
    assert _pair(2.4) == {"status": "fixed", "why": "fixed (the joint), and the case still fails: the joint between the "
                                                    "front rail and the right side"}
    assert _pair(1.7) == {"status": "still open", "why": "measured: the joint between the front rail and the left side is "
                                                         "still 1.7× where it needs 2×"}


def test_a_joint_not_measured_any_more_beside_its_pair_is_not_measured_never_renamed():
    """The reviewer's glue block: the left joint out of the check, the right one governing. Not "measured as" the right."""
    run = {"min_safety": 2.0, "cases": [{"name": "a foot", "safety": 1.8, "governs": "joint",
                                         "joints": {"governing": RIGHT, "rows": [{**RIGHT, "safety": 1.8}]}}]}
    rows = [{"id": "joint:front rail|right side", "cases": ["a foot"], "what": "the joint between the front rail and the right side",
             "problem": "The joint between the front rail and the right side gives too"}]
    item = {"id": "joint:front rail|left side", "cases": ["a foot"], "what": "the joint between the front rail and the left side"}
    assert fixing._moved(item, run, rows) == {"status": "still open", "why": "not measured as fixed"}


def test_a_case_s_own_row_is_read_by_its_own_number():
    """A ``fails:`` row (the FEA's, or a check with no thickness to offer) is the case's safety in the fresh run, said."""
    run = {"min_safety": 2.0, "cases": [{"name": "a foot", "safety": 1.6, "governs": "plate",
                                         "plate": {"done": True, "piece": "top", "safety_across": 1.6}}]}
    rows = [{"id": "plate:top", "cases": ["a foot"], "what": "the top", "problem": "The top fails by the plate check"}]
    item = {"id": "fails:a foot", "cases": ["a foot"], "what": "'a foot'"}          # as fixes._spoke words it
    assert fixing._moved(item, run, rows) == {"status": "still open", "why": "measured: 'a foot' is still 1.6× where it needs 2×"}
    passing = {**run, "cases": [{**run["cases"][0], "safety": 2.3}]}
    assert fixing._moved(item, passing, []) is None


def test_a_plate_renamed_is_measured_as_the_new_panel():
    """Where the row's own isn't measured, a plate row of its kind for the case is the panel by another name."""
    run = {"min_safety": 2.0, "cases": [{"name": "a foot", "safety": 1.91, "governs": "plate",
                                         "plate": {"done": True, "piece": "step", "safety_across": 1.91}}]}
    rows = [{"id": "plate:step", "cases": ["a foot"], "what": "the step", "problem": "The step fails by the plate check"}]
    item = {"id": "plate:top", "cases": ["a foot"], "what": "the top"}
    assert fixing._moved(item, run, rows) == {"status": "still open", "why": "it's measured as 'the step' now"}


def test_a_number_change_whose_words_name_its_number_says_it_once():
    """caliper-reviewer at 28b0707: "1 number change, at once (fillet_r: remove the inside corner fillet strips: fillet_r to 0)"."""
    assert fixing._said_number({"param": "fillet_r", "fix": "Remove the inside corner fillet strips: fillet_r to 0"}) == \
        "remove the inside corner fillet strips: fillet_r to 0"
    assert fixing._said_number({"param": "t", "fix": "Make the top from 5/8 in"}) == "t: make the top from 5/8 in"
