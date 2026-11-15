"""CALI-183 (#294): right-click a part, in the 3D view or the part tree, for a menu of what can be done to it.

Theo, 2026-11-14: "I should also just be able to right click a part and delete it, or select it in the parts browser and do
the same … There should be a menu of options when right clicking on either."

The menu is the page's (design.js); each item reuses a route the page already has. Delete and Put back are the two new
routes: removal went only through the chat, and took Theo three tries on 11-13 (#287). Synthetic designs, no Claude call.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from caliper import trash
from caliper.design import DesignStore

from .test_chat import _box

pytest.importorskip("cadquery")

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from caliper.server import create_app

    s = DesignStore.create("step-stool-5", base=str(tmp_path / "designs"))
    s.write_part("step_stool", _box(dx=400, dy=300), intent="the stool")
    s.write_part("inside_corner_fillets", _box(dx=150, dy=5, y=100), intent="glue-on fillet strips")
    return TestClient(create_app()), os.path.basename(str(s.root)), s


def _parts(c, slug):
    return [p["id"] for p in c.get(f"/api/designs/{slug}").json()["parts"]]


# --- Delete and Put back ----------------------------------------------------------------------------------------------
def test_delete_moves_the_part_to_the_trash_and_put_back_restores_it(site):
    c, slug, s = site
    r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
    assert r.status_code == 200, r.text
    got = r.json()
    assert "inside_corner_fillets" not in [p["id"] for p in got["state"]["parts"]]
    assert got["said"] == "Deleted inside_corner_fillets: it's in the design's trash, so it can be put back."
    assert got["removed"] == {"part": "inside_corner_fillets", "id": got["removed"]["id"]}
    assert [t["part"] for t in trash.listing(DesignStore.load(s.root))] == ["inside_corner_fillets"]
    r = c.post(f"/api/designs/{slug}/trash/restore", json={"part": "inside_corner_fillets"})
    assert r.status_code == 200, r.text
    assert r.json()["said"] == "Put back inside_corner_fillets, as it was."
    assert _parts(c, slug) == ["step_stool", "inside_corner_fillets"]
    assert trash.listing(DesignStore.load(s.root)) == []


def test_the_chat_log_says_both(site):
    """Everything is said in the chat's log too, so the history shows what the menu did."""
    c, slug, s = site
    c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
    c.post(f"/api/designs/{slug}/trash/restore", json={"part": "inside_corner_fillets"})
    log = [e for e in DesignStore.load(s.root).log() if e.get("kind") in ("message", "reply")]
    assert [(e["kind"], e.get("action"), e.get("text") or e.get("reply")) for e in log] == [
        ("message", "remove", "Delete inside_corner_fillets (from its menu)"),
        ("reply", "remove", "Deleted inside_corner_fillets: it's in the design's trash, so it can be put back."),
        ("message", "restore", "Put back inside_corner_fillets (from its menu)"),
        ("reply", "restore", "Put back inside_corner_fillets, as it was."),
    ]


def test_a_part_that_isn_t_there_is_a_404_and_putting_back_nothing_says_so(site):
    c, slug, _ = site
    assert c.post(f"/api/designs/{slug}/parts/nope/remove", json={}).status_code == 404
    r = c.post(f"/api/designs/{slug}/trash/restore", json={"part": "nope"})
    assert r.status_code == 404 and r.json()["detail"] == "there's no 'nope' in the design's trash"


def test_a_delete_while_a_job_runs_on_that_part_is_refused_in_words(site, monkeypatch):
    from caliper import design_api

    c, slug, _ = site

    class Job:                                       # a strength check running on the strips
        id, kind, meta, stopping, started = "j1", "load", {"slug": slug, "part": "inside_corner_fillets"}, False, 0

        def since(self, n):
            return []
    monkeypatch.setattr(design_api.RUNNER, "active", lambda: [Job()])
    r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
    assert r.status_code == 409 and r.json()["detail"] == ("inside_corner_fillets is being checked: wait for it, or stop "
                                                           "that first.")
    assert "inside_corner_fillets" in _parts(c, slug)
    assert c.post(f"/api/designs/{slug}/parts/step_stool/remove", json={}).status_code == 200   # another part: fine


def test_a_mirror_s_source_names_what_follows_it(site):
    """Deleting a part another one mirrors asks: both, or break the mirror first."""
    from caliper import mirror

    c, slug, s = site
    s.write_part("side_right", _box(dx=19, x=300), intent="the right side")
    s.write_part("side_left", _box(dx=19, x=-300), intent="the left side")
    mirror.make(s, "side_left", "side_right")
    r = c.post(f"/api/designs/{slug}/parts/side_right/remove", json={})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {"said": "side_right is mirrored by side_left: delete both, or break the mirror first?",
                                  "mirrored_by": ["side_left"]}
    assert "side_right" in _parts(c, slug)
    r = c.post(f"/api/designs/{slug}/parts/side_right/remove", json={"also": ["side_left"]})
    assert r.status_code == 200, r.text
    assert r.json()["said"] == ("Deleted side_right and side_left, its mirror: they're in the design's trash, so they can "
                                "be put back.")
    assert not {"side_right", "side_left"} & set(_parts(c, slug))


def test_also_deletes_only_what_mirrors_it(site):
    c, slug, _ = site
    r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={"also": ["step_stool"]})
    assert r.status_code == 422 and "step_stool" in _parts(c, slug)


# --- the page: one menu, from the view and the tree -----------------------------------------------------------------
_DESIGN = """{ parts: [
  { id: 'step_stool', name: 'step_stool', label: 'Step stool', role: 'part', version: 3, study: 'lighten', pieces: [
    { key: 'top', name: 'top' }, { key: 'side', name: 'side' } ] },
  { id: 'inside_corner_fillets', name: 'inside_corner_fillets', role: 'part', version: 4, study: 'carve', pieces: [] },
  { id: 'side_left', name: 'side_left', role: 'part', version: 2, mirror_of: 'side_right', pieces: [] },
  { id: 'car', name: 'car', role: 'fixed', version: 1, pieces: [] },
  { id: 'strip', name: 'strip', role: 'part', version: 1, study: null, pieces: [] } ],
  tree: { order: [], parent: {} },
  studies: { menu: {
    step_stool: [{ kind: 'load', ready: true, why: '' },
                 { kind: 'lighten', ready: false, why: "check what it must hold first (its loads())" }],
    inside_corner_fillets: [{ kind: 'load', ready: true, why: '' }, { kind: 'carve', ready: true, why: '' }],
    side_left: [{ kind: 'load', ready: true, why: '' }, { kind: 'lighten', ready: false, why: 'it mirrors side_right' }],
    car: [{ kind: 'load', ready: false, why: "it's a reference (context, like the car), not something you build" }],
    strip: [{ kind: 'load', ready: true, why: '' }, { kind: 'lighten', ready: false, why: 'no' },
            { kind: 'carve', ready: false, why: 'no' }] } } }"""

_STUBS = """
const S = { slug: 'step-stool-5', scope: null, piece: null, design: DESIGN, menu: null };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const calls = [];
const store = {};
globalThis.localStorage = { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = v; } };
const TREE = { slug: undefined, parts: new Set(), pieces: new Set(), open: true, oneBody: false, rename: null, last: null,
  waiting: new Set(), missed: {} };
const WAITING = 'Waiting for the job on this design to finish…';
const pieceId = (pid, key) => `${pid}/${key}`;
const MSG = { value: '', focus() { calls.push('focus'); } };
const $ = (id) => (id === 'msg' ? MSG : null);
const paint = () => calls.push('paint');
const renderTree = () => calls.push('tree');
const render = () => calls.push('render');
const setScope = (p, k) => { calls.push(['scope', p, k ?? null]); S.scope = p; S.piece = k ?? null; };
const useBetter = (ln) => calls.push(['better', ln.part, ln.action]);
const unmirror = async (p) => calls.push(['unmirror', p]);
const goTo = (id) => calls.push(['goTo', id]);
const closeMenu = () => { calls.push('close'); S.menu = null; };
const menuConfirm = (html) => calls.push(['confirm', html]);
const putBack = (said, gone) => calls.push(['putBack', said, gone]);
const showErr = (m) => calls.push(['err', m]);
const plainly = (m) => m;
let answer = null;
const posted = [];
const api = async (method, url, body) => { posted.push([method, url, body]); if (answer instanceof Error) throw answer; return answer; };
Object.defineProperty(globalThis, 'navigator', { value: { clipboard: { writeText: async (t) => calls.push(['copied', t]) } } });
const say = (t) => calls.push(['say', t]);
const syncParts = async () => calls.push('sync');
const menuBack = () => calls.push('back');
"""


def _menu(body: str) -> dict:
    import json
    import re
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    names = ("seen", "keepTree", "underPart", "menuItems", "menuHtml", "confirmHtml", "toggleHidden", "showOnly",
             "menuDo", "deletePart")
    script = (_STUBS.replace("DESIGN", _DESIGN) + "\n".join(_fn(src, n) for n in names)
              + f"\nconst out = await (async () => {{ {body} }})();\nconsole.log(JSON.stringify(out));")
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _ids(items):
    return [i["id"] for i in items]


def test_a_part_s_menu_has_every_item_and_a_piece_s_only_what_applies():
    got = _menu("""return { part: menuItems(S.design, 'step_stool', null), piece: menuItems(S.design, 'step_stool', 'top'),
                         printed: menuItems(S.design, 'inside_corner_fillets', null) };""")
    assert _ids(got["part"]) == ["delete", "rename", "hide", "only", "ask", "check", "lighten", "mirror", "versions",
                                 "copyName"]
    assert [i["label"] for i in got["part"]][:5] == ["Delete…", "Rename…", "Hide", "Show only this", "Ask about this"]
    light = next(i for i in got["part"] if i["id"] == "lighten")
    assert light["off"] and light["why"] == "check what it must hold first (its loads())"   # the panels' own rule
    assert _ids(got["piece"]) == ["rename", "only", "ask"]
    assert "carve" in _ids(got["printed"]) and "lighten" not in _ids(got["printed"])       # by made_of
    neither = _menu("return menuItems(S.design, 'strip', null);")                        # made_of says neither
    assert "check" in _ids(neither) and not {"lighten", "carve"} & set(_ids(neither))


def test_a_mirror_breaks_and_a_reference_isn_t_renamed_or_checked():
    got = _menu("return { mirror: menuItems(S.design, 'side_left', null), car: menuItems(S.design, 'car', null) };")
    assert "mirror" not in _ids(got["mirror"])
    assert next(i for i in got["mirror"] if i["id"] == "unmirror")["label"] == "Break the mirror (of side_right)"
    assert "rename" not in _ids(got["car"]) and next(i for i in got["car"] if i["id"] == "check")["off"]


def test_hidden_parts_say_show_and_show_everything():
    got = _menu("seen().parts.add('step_stool'); return menuItems(S.design, 'step_stool', null);")
    assert next(i for i in got if i["id"] == "hide")["label"] == "Show" and "all" in _ids(got)


def test_the_menu_and_its_confirm_are_the_page_s_own():
    got = _menu("""return { menu: menuHtml('Step stool', menuItems(S.design, 'step_stool', null)),
                            plain: confirmHtml('inside_corner_fillets'),
                            both: confirmHtml('side_right', 'side_right is mirrored by side_left: delete both, or break the mirror first?', ['side_left']) };""")
    assert 'role="menuitem" data-menu="delete"' in got["menu"] and 'aria-disabled="true"' in got["menu"]
    assert "check what it must hold first" in got["menu"]
    assert "Delete inside_corner_fillets? It goes to the design&#39;s trash; you can put it back." in got["plain"] or \
        "Delete inside_corner_fillets? It goes to the design's trash; you can put it back." in got["plain"]
    assert 'data-menu="deleteYes"' in got["plain"] and 'data-menu="keep"' in got["plain"]
    assert 'data-menu="deleteBoth"' in got["both"] and 'data-menu="unmirrorThem"' in got["both"]
    src = open(JS).read()
    import re

    assert not re.search(r"(?<![\w.])confirm\(|window\.confirm", src)             # never the browser's own


def test_delete_confirms_in_the_page_then_posts_and_offers_put_back():
    got = _menu("""S.menu = { pid: 'inside_corner_fillets', piece: null };
      await menuDo('delete');
      answer = { state: S.design, said: 'Deleted inside_corner_fillets: it is in the trash.',
                 removed: { part: 'inside_corner_fillets', id: 't1' }, also: [] };
      await menuDo('deleteYes');
      return { calls, posted };""")
    assert got["calls"][0][0] == "confirm" and "Delete inside_corner_fillets?" in got["calls"][0][1]
    assert got["posted"] == [["POST", "/api/designs/step-stool-5/parts/inside_corner_fillets/remove", {"also": []}]]
    assert ["putBack", "Deleted inside_corner_fillets: it is in the trash.",
            [{"part": "inside_corner_fillets", "id": "t1"}]] in got["calls"]
    assert "sync" in got["calls"]                                                     # out of the 3D view too


def test_a_mirror_s_source_asks_both_and_a_refusal_is_said_in_the_menu():
    got = _menu("""S.menu = { pid: 'side_right', piece: null };
      const e = new Error(JSON.stringify({ said: 'side_right is mirrored by side_left: delete both, or break the mirror first?',
                                           mirrored_by: ['side_left'] }));
      e.refused = true; answer = e;
      await menuDo('deleteYes');
      const first = calls.slice(); calls.length = 0;
      answer = { state: S.design, said: 'Deleted both.', removed: { part: 'side_right', id: 't2' },
                 also: [{ part: 'side_left', id: 't3' }] };
      await menuDo('deleteBoth');
      const busy = new Error('inside_corner_fillets is being checked: wait for it, or stop that first.'); busy.refused = true;
      answer = busy; S.menu = { pid: 'inside_corner_fillets', piece: null };
      calls.length = 0; await menuDo('deleteYes');
      return { first, posted, refused: calls };""")
    assert "delete both, or break the mirror first?" in got["first"][0][1] and 'data-menu="deleteBoth"' in got["first"][0][1]
    assert got["posted"][1] == ["POST", "/api/designs/step-stool-5/parts/side_right/remove", {"also": ["side_left"]}]
    assert got["refused"][0][0] == "confirm" and "is being checked: wait for it" in got["refused"][0][1]


def test_each_item_does_what_its_panel_or_chat_route_does():
    got = _menu("""const did = {};
      const run = async (id, pid, piece) => { calls.length = 0; S.menu = { pid, piece: piece ?? null }; await menuDo(id); did[id] = calls.slice(); };
      await run('ask', 'step_stool', 'top');
      await run('check', 'step_stool'); await run('carve', 'inside_corner_fillets');
      await run('unmirror', 'side_left'); await run('history', 'step_stool');
      await run('mirror', 'step_stool'); did.msg = MSG.value;
      await run('copyName', 'inside_corner_fillets');
      await run('rename', 'step_stool', 'top'); did.renaming = TREE.rename;
      await run('only', 'inside_corner_fillets'); did.hidden = [...TREE.parts];
      await run('hide', 'inside_corner_fillets'); did.hiddenToo = [...TREE.parts];
      await run('all', 'step_stool'); did.none = [...TREE.parts];
      return did;""")
    assert ["scope", "step_stool", "top"] in got["ask"]
    assert ["better", "step_stool", "load"] in got["check"] and ["better", "inside_corner_fillets", "carve"] in got["carve"]
    assert ["unmirror", "side_left"] in got["unmirror"]
    assert ["scope", "step_stool", None] in got["history"] and ["goTo", "partHistory"] in got["history"]
    assert got["msg"] == "Make step_stool a mirror of " and "focus" in got["mirror"]
    assert ["copied", "inside_corner_fillets"] in got["copyName"]
    assert got["renaming"] == {"part": "step_stool", "key": "top", "draft": "top"} and "tree" in got["rename"]
    assert sorted(got["hidden"]) == ["car", "side_left", "step_stool", "strip"]
    assert sorted(got["hiddenToo"]) == ["car", "inside_corner_fillets", "side_left", "step_stool", "strip"]
    assert got["none"] == []


def test_right_click_long_press_and_the_keyboard_open_it():
    src = open(JS).read()
    assert "renderer.domElement.addEventListener('contextmenu'" in src and "$('tree').addEventListener('contextmenu'" in src
    assert "longPress(renderer.domElement," in src and "longPress($('tree')," in src
    assert "(e.key === 'F10' && e.shiftKey) || e.key === 'ContextMenu'" in src and "e.key === 'Delete'" in src
    assert "e.key === 'ArrowDown'" in src and "e.key === 'Escape'" in src


def test_a_long_press_on_a_phone_opens_it_and_a_drag_or_a_mouse_doesn_t():
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = "const LONG_PRESS_MS = 550;\n" + _fn(src, "longPress") + """
let clock = 0, timers = [];
globalThis.setTimeout = (f, ms) => { timers.push({ f, at: clock + ms }); return timers.length; };
globalThis.clearTimeout = (id) => { if (id) timers[id - 1] = null; };
const tick = (ms) => { clock += ms; timers.forEach((t, i) => { if (t && t.at <= clock) { timers[i] = null; t.f(); } }); };
function el() { const on = {}; return { dataset: {}, addEventListener: (k, f) => { on[k] = f; }, fire: (k, e) => on[k](e) }; }
const out = {};
for (const [name, steps] of Object.entries({
  hold: [['pointerdown', 'touch', 10, 10], ['wait', 600]],
  drag: [['pointerdown', 'touch', 10, 10], ['pointermove', 'touch', 40, 10], ['wait', 600]],
  lift: [['pointerdown', 'touch', 10, 10], ['wait', 200], ['pointerup', 'touch', 10, 10], ['wait', 600]],
  mouse: [['pointerdown', 'mouse', 10, 10], ['wait', 600]] })) {
  const e = el(); let opened = 0;
  longPress(e, () => { opened += 1; });
  for (const [k, kind, x, y] of steps) k === 'wait' ? tick(kind) : e.fire(k, { pointerType: kind, clientX: x, clientY: y });
  out[name] = { opened, pressed: !!e.dataset.pressed };
}
console.log(JSON.stringify(out));
"""
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    out = json.loads(got.stdout)
    assert out["hold"] == {"opened": 1, "pressed": True}
    assert out["drag"]["opened"] == 0 and out["lift"]["opened"] == 0 and out["mouse"]["opened"] == 0


def test_lighten_and_carve_aren_t_offered_on_a_mirror():
    """studies.menu, which the menu and the Studies page read, says so: the server refuses them on a mirror (#246)."""
    from caliper import studies

    said = "It mirrors side_right: change side_right and it follows, or break the mirror first"
    p = {"id": "side_left", "scripted": True, "built": True, "loads": True, "study": "lighten", "sheets": True,
         "printed": True, "mirror_of": "side_right",
         "blocked": {"why": "unchecked", "mirror": "side_right", "lighten": said, "carve": said}}
    got = {m["kind"]: m for m in studies.menu(p)}                     # from blocked(), the one rule (#302 review)
    assert not got["lighten"]["ready"] and got["lighten"]["why"] == said
    assert got["load"]["ready"]


# --- #302 review: every part job says its part; a design-wide job refuses in words; one rule for a mirror ---------------
PART_JOBS = {"load": "checked", "lighten": "lightened", "carve": "carved", "whittle": "whittled", "frame": "sized",
             "gussets": "given gussets", "aero": "shaped for drag", "picture": "given a picture",
             "cutplan": "planned for cutting", "preview": "previewed"}         # a step's preview copies the part (#297)


def test_every_part_job_is_submitted_saying_its_part():
    """One helper, so a new route can't forget it: each RUNNER.submit of a part's job passes meta=_on_part(...)."""
    import ast

    src = open(os.path.join(os.path.dirname(JS), "..", "..", "design_api.py")).read()
    kinds = {}
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "submit"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "RUNNER"):
            meta = next((k.value for k in node.keywords if k.arg == "meta"), None)
            kinds[node.args[0].value] = (isinstance(meta, ast.Call) and getattr(meta.func, "id", "") == "_on_part")
    assert {k for k, on in kinds.items() if on} == set(PART_JOBS), kinds
    assert set(kinds) - set(PART_JOBS) == {"chat", "firstrun", "release", "clarify", "goals", "scorecard"}


def _hold(kind, lock, meta, gate):
    from caliper.jobs import RUNNER

    return RUNNER.submit(kind, lambda j: gate.wait(20), label=f"a stand-in {kind}", lock=lock, meta=meta)


@pytest.mark.parametrize("kind", sorted(PART_JOBS))
def test_a_delete_while_each_kind_of_part_job_runs_is_refused_in_words(site, kind):
    import threading

    from caliper import design_api

    c, slug, _ = site
    gate = threading.Event()
    job = _hold(kind, f"{kind}:{slug}:stand-in", design_api._on_part(slug, "inside_corner_fillets"), gate)
    try:
        for _ in range(100):
            if job.status == "running":
                break
            time.sleep(0.02)
        r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == f"inside_corner_fillets is being {PART_JOBS[kind]}: wait for it, or stop that first."
    finally:
        gate.set()
    assert "inside_corner_fillets" in _parts(c, slug)


@pytest.mark.parametrize("kind,who", [("chat", "a chat turn"), ("firstrun", "the first build"),
                                      ("release", "the build package")])
def test_a_design_wide_job_refuses_at_once_in_words_never_a_silent_wait(site, kind, who):
    import threading

    from caliper import design_api

    c, slug, _ = site
    gate = threading.Event()
    job = _hold(kind, design_api._lock(slug), {"slug": slug}, gate)
    try:
        for _ in range(100):
            if job.status == "running":
                break
            time.sleep(0.02)
        t0 = time.time()
        r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
        assert time.time() - t0 < 2.0                                                 # it never waited behind the lock
        assert r.status_code == 409 and r.json()["detail"] == f"{who} is working on the design: wait for it, or stop it first."
        r = c.post(f"/api/designs/{slug}/trash/restore", json={"part": "inside_corner_fillets"})
        assert r.status_code == 409 and "is working on the design" in r.json()["detail"]
    finally:
        gate.set()


def test_the_delete_says_what_went_with_it_and_who_follows_it(site):
    from caliper.assembly import Mate

    c, slug, s = site
    s.write_part("cap", "FOLLOWS = {'w': ('inside_corner_fillets', 'w')}\n" + _box(dx=20, x=500), intent="a cap")
    s = DesignStore.load(s.root)
    s.assembly.mates.append(Mate(id="strips_clear_stool", between=["inside_corner_fillets", "step_stool"],
                                 kind="no_interference"))
    s.save()
    r = c.post(f"/api/designs/{slug}/parts/inside_corner_fillets/remove", json={})
    assert r.status_code == 200, r.text
    assert r.json()["said"] == ("Deleted inside_corner_fillets: it's in the design's trash, so it can be put back. Its mate "
                                "strips_clear_stool went with it. cap follows it: it keeps its numbers.")


def test_a_mirror_s_lighten_and_carve_are_refused_in_one_place_for_menu_card_and_panel(site):
    """#144's one rule: blocked() says it, and the menu (studies.menu), the card (better) and the panel (p.blocked) read it."""
    from caliper import design_api, load_study, mirror

    _, slug, s = site
    s.write_part("side_right", _box(dx=19, x=300), intent="the right side")
    s.write_part("side_left", _box(dx=19, x=-300), intent="the left side")
    mirror.make(s, "side_left", "side_right")
    said = "It mirrors side_right: change side_right and it follows, or break the mirror first"
    b = load_study.blocked(s, "side_left")
    assert b["mirror"] == "side_right" and b["lighten"] == said and b["carve"] == said
    st = design_api.design_state(DesignStore.load(s.root))
    p = next(x for x in st["parts"] if x["id"] == "side_left")
    assert p["blocked"]["lighten"] == said                                             # what the panel's button reads
    menu = {m["kind"]: m for m in st["studies"]["menu"]["side_left"]}
    assert not menu["lighten"]["ready"] and not menu["carve"]["ready"]
    assert menu["lighten"]["why"] == said and menu["carve"]["why"] == said            # the same words, before the rest
    from caliper import better

    offers = better.offers(DesignStore.load(s.root), st, "side_left")
    assert not [o for o in offers if (o.get("action") if isinstance(o, dict) else None) in ("lighten", "carve")], offers


# --- #302 review: the three page mutants reviewer-2 found survived ------------------------------------------------------
def _js(names, body):
    import json
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = "\n".join(_fn(src, n) for n in names) + "\n" + body
    got = subprocess.run([_node(), "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_a_right_click_opens_the_menu_and_a_right_drag_past_5_px_pans():
    out = _js(["swallowed", "viewUp"], """
const at = (x, y, button, ctrl) => ({ clientX: x, clientY: y, button, ctrlKey: !!ctrl });
const d = [100, 100, 2];
console.log(JSON.stringify({
  still: viewUp(d, at(103, 104, 2), {}), five: viewUp(d, at(105, 100, 2), {}), six: viewUp(d, at(106, 100, 2), {}),
  ctrl: viewUp([100, 100, 0], at(100, 100, 0, true), {}), left: viewUp([100, 100, 0], at(100, 100, 0), {}),
  none: viewUp(null, at(100, 100, 2), {}) }));""")
    assert out == {"still": "menu", "five": "menu", "six": "click", "ctrl": "menu", "left": "click", "none": "click"}


def test_a_long_press_s_lift_is_swallowed_once():
    out = _js(["swallowed", "viewUp"], """
const data = { pressed: '1' };
const first = viewUp([1, 1, 0], { clientX: 1, clientY: 1, button: 0 }, data);
const second = viewUp([1, 1, 0], { clientX: 1, clientY: 1, button: 0 }, data);
const tree = { pressed: '1' };
console.log(JSON.stringify({ first, second, tree: [swallowed(tree), swallowed(tree)] }));""")
    assert out == {"first": "swallow", "second": "click", "tree": [True, False]}
    src = open(JS).read()
    assert "if (swallowed($('tree').dataset)) return;" in src and "const act = viewUp(d, e, renderer.domElement.dataset);" in src


def test_a_cancelled_long_press_never_swallows_the_next_tap():
    out = _js(["longPress"], """
const LONG_PRESS_MS = 550;
let timers = [];
globalThis.setTimeout = (f) => { timers.push(f); return timers.length; };
globalThis.clearTimeout = (id) => { if (id) timers[id - 1] = null; };
const on = {}, el = { dataset: {}, addEventListener: (k, f) => { on[k] = f; } };
longPress(el, () => {});
on.pointerdown({ pointerType: 'touch', clientX: 1, clientY: 1 }); timers.forEach((f) => f && f());
const held = !!el.dataset.pressed;
on.pointercancel({});
const cancelled = !!el.dataset.pressed;
el.dataset.pressed = '1'; on.pointerdown({ pointerType: 'mouse', clientX: 1, clientY: 1 });
console.log(JSON.stringify({ held, cancelled, stale: !!el.dataset.pressed }));""")
    assert out == {"held": True, "cancelled": False, "stale": False}


def test_put_back_restores_the_source_first_and_names_both():
    out = _js(["putBack"], """
const S = { slug: 's', design: null }, posted = [], said = [];
const say = (t, act) => { said.push(t); if (act) globalThis.act = act; };
const api = async (m, u, b) => { posted.push(b.id); return { state: { parts: [] }, said: `Put back ${b.id}, as it was.` }; };
const render = () => {}, syncParts = async () => {}, showErr = () => {}, plainly = (m) => m;
putBack('Deleted both.', [{ part: 'side_right', id: 'r1' }, { part: 'side_left', id: 'l1' }]);
await globalThis.act();
console.log(JSON.stringify({ posted, said }));""")
    assert out["posted"] == ["r1", "l1"]                                              # its source first, then its mirror
    assert out["said"][-1] == "Put back r1, as it was. Put back l1, as it was."


def test_the_menu_key_works_from_an_empty_chat_box_and_focus_goes_back():
    src = open(JS).read()
    assert "const empty = a && a.id === 'msg' && !a.value.trim();" in src
    from .test_carve_click import _fn

    assert "menuBack(m)" in _fn(src, "closeMenu") and "menuBack({ ...m, from: null })" in _fn(src, "deletePart")
    assert "closeMenu(false); }, true);" in src                                        # a click elsewhere keeps its own focus



# --- #302 re-check: a mirror keeps its check's own why -------------------------------------------------------------------
@pytest.mark.parametrize("why", ["unchecked", "already_fails"])
def test_a_mirror_keeps_its_check_s_why(site, monkeypatch, why):
    """An unchecked mirror's card still offers Check it holds, as its menu does; a failing one still says why."""
    from caliper import better, load_study, mirror

    _, slug, s = site
    monkeypatch.setattr(mirror, "source_of", lambda store, pid: "side_right" if pid == "side_left" else None)
    monkeypatch.setattr(load_study, "_blocked", lambda store, pid: {"why": why, "carve": "it fails as it is",
                                                                     "lighten": "it fails as it is"})
    b = load_study.blocked(s, "side_left")
    assert b["why"] == why and b["mirror"] == "side_right"
    assert b["lighten"] == "It mirrors side_right: change side_right and it follows, or break the mirror first"
    if why == "unchecked":
        p = {"id": "side_left", "loads": True, "built": True, "role": "part", "blocked": b}
        monkeypatch.setattr(load_study, "default_check", lambda store, pid: None)
        got = better.offers(s, {"parts": [p]}, "side_left")
        assert [ln.get("action") for ln in got] == ["load"], got                      # Check it holds, as the menu has it
