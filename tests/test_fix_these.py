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
    assert p["said"] == ("1 number change, at once; 1 designer edit on the stool (one Claude call); then a check, "
                         "about 1 min")
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

    return _run(page(["fixesView", "fixRow", "fixGo"], consts=["esc", "fixRowKey"], extra=extra))


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
