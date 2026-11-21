"""CALI-215 (#362): a one-part design shows its part's own view at first look, so its action bar (Check it holds, #325) is
there, and the chat is exactly as it was.

Theo's live test on step-stool-5: the page opened on the design view, which has the part's Parameters but no action bar,
and he couldn't find "Check it holds". The first fix opened the design scoped to its part, and reviewer-3 found what that
cost: a scoped message is that part's revise, so "add a matching bench" rewrote the stool (#364 review). Now the panel shows
the part's view while the chat's scope stays null; "The whole design ▸" gives the design's view."""
import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _js(names, body, head=""):
    src = open(JS).read()
    script = head + "".join(_fn(src, n) for n in names) + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@pytest.mark.parametrize("parts,want", [
    ([{"id": "step_stool", "role": "movable"}], "step_stool"),
    ([{"id": "a", "role": "movable"}, {"id": "b", "role": "movable"}], None),
    ([{"id": "car", "role": "fixed"}], None),
    ([], None)])
def test_only_a_one_part_design_shows_its_part(parts, want):
    assert _js(("soleFor",), f"return {{ r: soleFor({json.dumps({'parts': parts})}) }};")["r"] == want


ONE = {"slug": "step-stool-5", "parts": [{"id": "step_stool", "role": "movable"}]}
TWO = {"slug": "camper", "parts": [{"id": "frame", "role": "movable"}, {"id": "box", "role": "movable"}]}


@pytest.mark.parametrize("state,want", [
    ({"scope": None, "whole": False, "design": ONE}, "step_stool"),     # first look: its part's view
    ({"scope": None, "whole": True, "design": ONE}, None),              # "The whole design ▸"
    ({"scope": "step_stool", "whole": True, "design": ONE}, "step_stool"),   # picked: always the picked part
    ({"scope": None, "whole": False, "design": TWO}, None),             # two parts: the design, as ever
    ({"scope": "box", "whole": False, "design": TWO}, "box"),
    ({"scope": None, "whole": False, "design": None}, None)])
def test_the_panel_shows_the_picked_part_else_the_one_part(state, want):
    assert _js(("soleFor", "shownPart"), f"return {{ r: shownPart() }};", head=f"const S = {json.dumps(state)};\n")["r"] == want


_OPEN = """
const calls = []; let S = { slug: 'step-stool-4', scope: 'side_left', piece: 'left side', focus: 'x', whole: true, station: null,
  fixes: {}, fixOpen: null, design: null };
const location = {}; const api = async () => (DESIGN);
const dropBuildFollow = () => {}, clearPick = () => {}, pickHint = () => {}, showLoading = () => {}, doneLoading = () => {}, sayMissed = () => {};
const loadFailed = () => {}; const render = () => calls.push(['render', S.scope, shownPart()]); const syncParts = async () => {};
"""


def _open(design):
    return _js(("soleFor", "shownPart", "openDesign"),
               "await openDesign('step-stool-5'); return { scope: S.scope, piece: S.piece, focus: S.focus, whole: S.whole, calls };",
               head=_OPEN.replace("DESIGN", json.dumps(design)))


def test_step_stool_5_shows_its_part_with_the_chat_unscoped():
    """The panel draws the part's view on the first draw, and the chat's scope stays null: a message goes as on main."""
    got = _open(ONE)
    assert got["calls"] == [["render", None, "step_stool"]]
    assert got["scope"] is None


def test_nothing_picked_on_the_last_design_comes_over():
    """#364 review: step-stool-4's "left side", picked on side_left, came over as "Step stool · left side"."""
    got = _open(ONE)
    assert got["piece"] is None and got["focus"] is None and got["whole"] is False


def test_a_two_part_design_still_shows_the_design():
    assert _open(TWO)["calls"] == [["render", None, None]]


def test_the_panel_draws_what_shownpart_says_and_both_views_lead_to_each_other():
    src = open(JS).read()
    assert "const shown = shownPart(), p = shown && d.parts.find((x) => x.id === shown);" in _fn(src, "renderInspector")
    assert "${partActions(p)}" in _fn(src, "partView") and "partActions" not in _fn(src, "designView")
    assert "const whole = !S.scope ? '<button class=\"linkish small\" data-whole=\"1\">The whole design ▸</button>' : '';" in _fn(src, "partView")
    assert 'data-whole="0">◂ ' in _fn(src, "designView") and "const back = soleFor(d) ?" in _fn(src, "designView")
    assert "b.onclick = () => { S.whole = b.dataset.whole === '1'; renderInspector(); };" in _fn(src, "wireInspector")


@pytest.mark.parametrize("fn,check", [
    ("paintFixAct", "shownPart() !== part"), ("loadAnswers", "shownPart() ? `?part="), ("answersKey", "[S.slug, shownPart(),"),
    ("paintCarve", "if (shownPart() !== pid) return;"), ("paintJobs", "shownPart() === t.part"),
    ("partView", "shownPart() && p.role !== 'fixed' && fixesSection(p.id)"),
    ("focusCard", "const pid = shownPart();"), ("cardsView", "S.focus === k && shownPart() ? ' focus' : ''"),
    ("cardsView", "${shownPart() ? ' title=\"show this in 3D\"' : ''}"), ("showMarks", "const shown = shownPart(), c = shown && S.built[shown];"),
    ("goTo", "} else if (id === 'relBox' && shownPart()) { S.whole = true; setScope(null); }")])
def test_every_panel_that_asks_whether_its_part_is_on_screen_asks_shownpart(fn, check):
    """The part's view drawn with no scope: its panels must still know they're on screen, or a carve's progress, a job's
    line and Things to fix would never paint there."""
    assert check in _fn(open(JS).read(), fn)


def test_the_history_s_preview_and_go_back_work_in_the_part_s_view_unpicked():
    """#364 re-check: in the unscoped part view, Preview and Go back did nothing: their click handler read S.scope."""
    src = open(JS).read()
    i = src.index("document.addEventListener('click', (e) => {     // the history's buttons")
    handler = src[i:src.index("});", i)]
    assert "shown = shownPart()" in handler and "if (pv && shown) showVersion(shown," in handler
    assert "goBackTo(shown || S.station.part," in handler and "S.scope" not in handler
    assert "const cardStore = () => `${S.slug}/${shownPart() || ''}`;" in src


def test_the_first_message_after_opening_goes_unscoped():
    """The composer sends with S.scope, which opening leaves null."""
    src = open(JS).read()
    assert "send(said, S.scope, pick, shown, text);" in src
    assert "S.scope = soleFor" not in src


# --- the chat routes "add a …" as it did on main ------------------------------------------------------------------------
pytest.importorskip("cadquery")


@pytest.fixture
def stool(tmp_path, monkeypatch):
    from caliper.design import DesignStore

    from .test_chat import _box

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = DesignStore.create("a step stool so I can water my plants", base=str(tmp_path / "designs"))
    s.write_part("step_stool", _box(dx=400, dy=300), intent="the stool")
    return s


@pytest.mark.parametrize("message", ["add a matching bench", "add a second step", "build a little side table to go with it"])
def test_add_a_new_thing_on_a_one_part_design_is_a_new_part(stool, message):
    """#364 review: scoped from the first look, these revised step_stool. Unscoped, as the page now sends them, they're new parts."""
    from caliper import chat

    got = chat.offline_classify(stool, message, scope=None)
    assert got.action == "author" and got.part != "step_stool"
