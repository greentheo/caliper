"""CALI-157 (#223), part 3 — a revision is a small edit to the script, applied exactly, with a full rewrite only if that can't be done."""

import difflib
import json
from types import SimpleNamespace as NS

import pytest

from caliper import authoring, chat, llm
from caliper.design import DesignStore
from caliper.spec import Spec

pytest.importorskip("cadquery")

SCRIPT = '''import cadquery as cq

WIDTH = 100.0
DEPTH = 50.0


def build(params):
    # the top
    top = cq.Workplane().box(WIDTH, DEPTH, 10)
    # the leg, kept exactly as it is, comments, spacing and all
    leg   =  cq.Workplane().box(10, 10,    40).translate((0, 0, -25))
    return top.union(leg)
'''
ONE_LINE = {"old": "WIDTH = 100.0", "new": "WIDTH = 120.0"}


def _spec():
    return Spec(part="p", intent="a thing")


def _changed(a, b):
    return [ln for ln in difflib.ndiff(a.splitlines(), b.splitlines()) if ln[:2] in ("- ", "+ ")]


def test_a_one_line_revision_changes_one_line_and_leaves_the_rest_byte_for_byte():
    got = authoring.refine_authored(_spec(), SCRIPT, "make it 120 wide", editor=lambda s, f, p, e: [ONE_LINE])
    assert got.geometry is not None and got.script == SCRIPT.replace("WIDTH = 100.0", "WIDTH = 120.0")
    assert _changed(SCRIPT, got.script) == ["- WIDTH = 100.0", "+ WIDTH = 120.0"]


def test_an_edit_that_doesnt_apply_is_retried_once_with_the_error():
    errors = []

    def editor(s, f, p, error):
        errors.append(error)
        return [{"old": "WIDHT = 100.0", "new": "x"}] if len(errors) == 1 else [ONE_LINE]

    got = authoring.refine_authored(_spec(), SCRIPT, "wider", editor=editor)
    assert errors[0] is None and "isn't in the script" in errors[1] and "WIDHT" in errors[1]
    assert got.script == SCRIPT.replace("WIDTH = 100.0", "WIDTH = 120.0")
    assert [t["how"] for t in got.tries] == ["edit failed", "edit"]


@pytest.mark.parametrize("edits, said", [([{"old": "cq", "new": "x"}], "times"), ([], "no edits"), ("not a list", "no edits")])
def test_an_edit_that_cant_be_applied_exactly_isnt_guessed(edits, said):
    with pytest.raises(authoring.NoEdit, match=said):
        authoring.apply_edits(SCRIPT, edits)


def test_after_two_misses_it_falls_back_to_a_full_rewrite_and_says_so():
    calls = []

    def editor(s, f, p, error):
        calls.append(error)
        return [{"old": "nothing like this", "new": "x"}]

    whole = SCRIPT.replace("WIDTH = 100.0", "WIDTH = 130.0")
    got = authoring.refine_authored(_spec(), SCRIPT, "wider", editor=editor, author=lambda s, f, p: whole)
    assert len(calls) == 2 and got.script == whole
    assert [t["how"] for t in got.tries] == ["edit failed", "edit failed", "rewrite"]
    assert all(t["seconds"] >= 0 for t in got.tries)


def test_a_round_that_fails_to_build_is_edited_too():
    seen = []

    def editor(s, f, p, error):
        seen.append((f, p))
        return [{"old": "WIDTH = 100.0", "new": "WIDTH = 1 / 0"}] if len(seen) == 1 else [{"old": "WIDTH = 1 / 0", "new": "WIDTH = 120.0"}]

    got = authoring.refine_authored(_spec(), SCRIPT, "wider", editor=editor)
    assert got.geometry is not None and "WIDTH = 120.0" in got.script and "1 / 0" in seen[1][1]


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return NS(content=[NS(type="text", text=self.replies.pop(0))], stop_reason="end_turn", usage=None)


def test_the_real_path_asks_for_edits_and_keeps_its_prompt_cached():
    c = Fake(json.dumps({"edits": [ONE_LINE]}))
    got = authoring.refine_authored(_spec(), SCRIPT, "make it 120 wide", client=c)
    assert got.script == SCRIPT.replace("WIDTH = 100.0", "WIDTH = 120.0")
    (kw,) = c.calls
    assert kw["system"][0]["text"] == authoring.system_prompt() and kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    asked = kw["messages"][0]["content"]
    assert SCRIPT in asked and "make it 120 wide" in asked and '"edits"' in asked
    assert kw["output_config"] == {"effort": "high"}


def test_a_reply_thats_not_edits_falls_back():
    c = Fake("sorry", "still no", "```python\n" + SCRIPT.replace("100.0", "140.0") + "```")
    got = authoring.refine_authored(_spec(), SCRIPT, "wider", client=c)
    assert "WIDTH = 140.0" in got.script and [t["how"] for t in got.tries] == ["edit failed", "edit failed", "rewrite"]


def test_a_refusal_isnt_turned_into_a_rewrite():
    def editor(s, f, p, error):
        raise llm.Declined("Claude's safety checks stopped this request")

    got = authoring.refine_authored(_spec(), SCRIPT, "wider", editor=editor, author=lambda s, f, p: pytest.fail("no rewrite"))
    assert "safety checks stopped" in got.error


def test_a_stub_author_alone_still_rewrites():
    whole = SCRIPT.replace("100.0", "150.0")
    assert authoring.refine_authored(_spec(), SCRIPT, "wider", author=lambda s, f, p: whole).script == whole


def test_tries_and_seconds_go_on_the_designs_log(tmp_path, monkeypatch):
    s = DesignStore.create("a thing", base=str(tmp_path / "designs"))
    s.write_part("p", SCRIPT, intent="a thing")
    monkeypatch.setattr(authoring, "edit_script", lambda *a, **k: [ONE_LINE])
    chat.refine_part(s, "p", "make it 120 wide", client=Fake(), use_llm=False, promote_feedback=False)
    entry = next(e for e in s.log() if e.get("kind") == "revise")
    assert entry["part"] == "p" and entry["rounds"] == 1 and entry["tries"][0]["how"] == "edit" and entry["tries"][0]["seconds"] >= 0


# ---------------------------------------------------------------------------
# The #232 review
# ---------------------------------------------------------------------------
def test_the_shared_rules_say_code_unless_asked_for_edits():
    # one system prompt for a write and an edit, so its cache holds: it can't say "only code" to the edit
    rules = authoring.system_prompt()
    assert "unless\n  you're asked for edits to a script: then output only the JSON" in rules


@pytest.mark.parametrize("edits", [
    [{"old": "# the top", "new": "# the top, 20 thick"}],                  # a comment
    [{"old": "WIDTH = 100.0", "new": "WIDTH = 100.0"}],                    # the same
    [{"old": "leg   =  cq", "new": "leg = cq"}],                           # spacing
])
def test_an_edit_that_leaves_the_code_as_it_was_isnt_a_revision(edits):
    with pytest.raises(authoring.NoEdit, match="leave the code as it was"):
        authoring.apply_edits(SCRIPT, edits)


def test_a_comment_only_edit_goes_round_with_that_error():
    errors = []

    def editor(s, f, p, error):
        errors.append(error)
        return [{"old": "# the top", "new": "# the top, 120 wide"}] if len(errors) == 1 else [ONE_LINE]

    got = authoring.refine_authored(_spec(), SCRIPT, "make it 120 wide", editor=editor)
    assert errors[1] == authoring.UNCHANGED and "WIDTH = 120.0" in got.script


def test_edits_dont_chain_and_dont_overlap():
    # each old is looked up in the script as given: one only an earlier edit wrote isn't there
    with pytest.raises(authoring.NoEdit, match="isn't in the script"):
        authoring.apply_edits(SCRIPT, [ONE_LINE, {"old": "WIDTH = 120.0", "new": "WIDTH = 130.0"}])
    with pytest.raises(authoring.NoEdit, match="overlap"):
        authoring.apply_edits(SCRIPT, [ONE_LINE, {"old": "100.0\nDEPTH", "new": "90.0\nDEPTH"}])
    both = authoring.apply_edits(SCRIPT, [{"old": "DEPTH = 50.0", "new": "DEPTH = 60.0"}, ONE_LINE])     # any order
    assert "WIDTH = 120.0" in both and "DEPTH = 60.0" in both
    assert "not as your other edits leave it" in authoring.EDIT_ASK and "no two edits may overlap" in authoring.EDIT_ASK


def test_a_reply_with_raw_newlines_in_its_strings_is_read():
    raw = '{"edits": [{"old": "WIDTH = 100.0\nDEPTH = 50.0", "new": "WIDTH = 120.0\nDEPTH = 50.0"}]}'
    got = authoring.refine_authored(_spec(), SCRIPT, "make it 120 wide", client=Fake(raw))
    assert "WIDTH = 120.0" in got.script and [t["how"] for t in got.tries] == ["edit"]


def test_a_reply_that_isnt_json_says_why_in_the_retry():
    c = Fake('{"edits": [{"old": "WIDTH = 100.0", "new": }]}', json.dumps({"edits": [ONE_LINE]}))
    got = authoring.refine_authored(_spec(), SCRIPT, "wider", client=c)
    assert "Expecting value" in got.tries[0]["why"]
    assert "Expecting value" in c.calls[1]["messages"][0]["content"]


def test_a_cut_off_reply_is_an_edit_that_failed_not_a_half_edit():
    class CutOff(Fake):
        def _create(self, **kw):
            self.calls.append(kw)
            return NS(content=[NS(type="text", text='{"edits": [{"old": "WIDTH')], stop_reason="max_tokens", usage=None)

    with pytest.raises(authoring.NoEdit, match="cut off"):
        authoring.edit_script(_spec(), SCRIPT, "wider", client=CutOff())


def test_the_edit_request_has_the_spec_the_rewrite_has():
    spec = Spec(part="p", intent="a thing", parameters={"width": {"type": "fixed", "value": 100.0, "unit": "mm"}},
                assertions=[{"id": "wide_enough", "expr": "bbox.dx >= 100"}])
    c = Fake(json.dumps({"edits": [ONE_LINE]}))
    authoring.edit_script(spec, SCRIPT, "wider", client=c)
    asked = c.calls[0]["messages"][0]["content"]
    assert asked.startswith(authoring._the_spec(spec)) and "width" in asked and "wide_enough: bbox.dx >= 100" in asked


def test_a_failed_builds_error_reaches_the_next_edit_and_each_try_has_its_round():
    seen = []

    def editor(s, f, p, error):
        seen.append(f)
        return [{"old": "WIDTH = 100.0", "new": "WIDTH = 1 / 0"}] if len(seen) == 1 else [{"old": "WIDTH = 1 / 0", "new": "WIDTH = 120.0"}]

    got = authoring.refine_authored(_spec(), SCRIPT, "wider", editor=editor)
    assert "ZeroDivisionError" in seen[1] or "division by zero" in seen[1]
    assert [(t["round"], t["how"]) for t in got.tries] == [(1, "edit"), (2, "edit")]


def test_a_revision_that_never_builds_still_logs_its_tries(tmp_path, monkeypatch):
    s = DesignStore.create("a thing", base=str(tmp_path / "designs"))
    s.write_part("p", SCRIPT, intent="a thing")
    breaks = {"old": "def build(params):", "new": "def build(params):\n    raise RuntimeError('not today')"}
    monkeypatch.setattr(authoring, "edit_script", lambda *a, **k: [breaks])
    got = chat.refine_part(s, "p", "make it 120 wide", client=Fake(), use_llm=False, promote_feedback=False, max_rounds=2)
    assert not got.ok
    entry = next(e for e in s.log() if e.get("kind") == "revise")
    assert entry["built"] is False and [(t["round"], t["how"]) for t in entry["tries"]] == [(1, "edit"), (2, "edit")]


def test_a_failed_builds_error_is_in_the_next_edit_request():
    c = Fake(json.dumps({"edits": [{"old": "WIDTH = 100.0", "new": "WIDTH = 1 / 0"}]}),
             json.dumps({"edits": [{"old": "WIDTH = 1 / 0", "new": "WIDTH = 120.0"}]}))
    got = authoring.refine_authored(_spec(), SCRIPT, "wider", client=c)
    assert got.geometry is not None and "WIDTH = 120.0" in got.script
    asked = c.calls[1]["messages"][0]["content"]
    assert "division by zero" in asked.split("--- what to change ---")[1]


def test_the_change_points_at_the_script_above_it():
    # the model reads it literally: in both requests the script comes first and the change after it (#232)
    c = Fake(json.dumps({"edits": [ONE_LINE]}))
    authoring.refine_authored(_spec(), SCRIPT, "make it 120 wide", client=c)
    asked = c.calls[0]["messages"][0]["content"]
    assert "the script above" in asked and "below" not in asked.split("--- what to change ---")[1]
    assert asked.index(SCRIPT) < asked.index("the script above")
