"""CALI-135 (#168) — choosing another design while the first is loading. The first response landed last and overwrote the
state: one page showed one design's tree and heading and acted on the other. A response for a design no longer open is
dropped, and so is a part's mesh or piece that arrives after the switch. Stubbed: node, no server."""

import json
import os
import re
import subprocess

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")

HEAD = """
const S = { slug: null, scope: null, station: null, design: null, buildBubble: null };
guardDesign(S);
const later = {};
const answer = (key, value) => later[key](value);
const api = (m, url) => new Promise((r) => { later[url.split('/').pop()] = r; });
const log = [];
const render = () => log.push(['render', S.design && S.design.slug]);
const syncParts = async (d) => log.push(['sync', d.slug]);
const clearStation = () => {};
const showLoading = (slug) => { S.opening = slug; S.design = null; log.push(['loading', slug]); };
const doneLoading = () => { S.opening = null; };
const failed = []; const loadFailed = (slug, e) => failed.push([slug, e.message]);
const meshes = new Map(), scene = { add() {}, remove() {} };
const location = {};
const design = (slug) => ({ slug, parts: [] });
"""


def _run(names, body: str, head: str = HEAD) -> dict:
    src = open(JS).read()
    script = "".join(_fn(src, n) for n in ("guardDesign", *names)) + head + \
        f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_slow_design_arrives_last_and_is_dropped():
    got = _run(("openDesign",), """const a = openDesign('slow'), b = openDesign('quick');
        answer('quick', design('quick')); await b;
        answer('slow', design('slow')); await a;
        return { open: S.slug, shown: S.design.slug, log };""")
    assert got["open"] == "quick" and got["shown"] == "quick"
    assert got["log"] == [["loading", "slow"], ["loading", "quick"], ["render", "quick"], ["sync", "quick"]]


def test_back_to_the_first_design_shows_the_first_design():
    got = _run(("openDesign",), """const a = openDesign('one'), b = openDesign('two'), c = openDesign('one');
        answer('one', design('one')); await c;
        return { shown: S.design.slug };""")
    assert got == {"shown": "one"}


def test_a_refresh_for_the_design_left_is_dropped():
    got = _run(("openDesign", "refresh"), """S.slug = 'old'; S.design = design('old');
        const r = refresh();
        S.slug = 'new'; S.design = null;
        answer('old', design('old')); await r;
        return { shown: S.design, log };""")
    assert got == {"shown": None, "log": []}


def test_nothing_else_can_put_another_design_on_the_page():
    """The other writes are a POST's answer, say a rename: the guard is on the state itself."""
    got = _run((), """S.slug = 'b';
        S.design = design('a'); const stale = S.design;
        S.design = design('b'); const here = S.design.slug;
        S.design = null; const cleared = S.design;
        return { stale, here, cleared };""")
    assert got == {"stale": None, "here": "b", "cleared": None}


_LOADS = """
const S = { slug: 'a', design: null };
guardDesign(S);
const later = [];
const fetch = (u) => new Promise((r) => later.push(r));
const buf = { ok: true, arrayBuffer: async () => new ArrayBuffer(1) };
const added = [], removed = [];
const scene = { add: (m) => added.push(m.userData.partId), remove: () => removed.push(1) };
const meshes = new Map();
const loader = { parse: () => ({ computeVertexNormals() {} }) };
const THREE = { Mesh: function (g) { this.geometry = g; } };
const material = () => ({}), showErr = () => {}, paint = () => {}, refreshBuilt3d = () => {}, frame = () => {};
const syncPieces = async () => {};
"""


def test_a_part_s_mesh_landing_after_the_switch_is_dropped():
    got = _run(("syncParts",), """const d = { parts: [{ id: 'p', version: 1, stl_url: 'x' }] };
        const go = syncParts(d, false);
        S.slug = 'b';
        later[0](buf); await go;
        return { added, kept: meshes.size };""", _LOADS)
    assert got == {"added": [], "kept": 0}


def test_a_part_s_mesh_for_the_open_design_is_kept():
    got = _run(("syncParts",), """const d = { parts: [{ id: 'p', version: 1, stl_url: 'x' }] };
        const go = syncParts(d, false);
        later[0](buf); await go;
        return { added, kept: meshes.size };""", _LOADS)
    assert got == {"added": ["p"], "kept": 1}


_PIECES = """
const S = { slug: 'a', design: { slug: 'a', parts: [{ id: 'p', version: 1 }] } };
let finish, fail;
const loadPieces = () => new Promise((r, x) => { finish = r; fail = x; });
const pieces3d = new Map(), noPieces = new Map(), added = [];
const dropPieces = (p) => pieces3d.delete(p), scene = { add: (m) => added.push(m) }, plainly = (m) => m;
let told = 0; const renderTree = () => { told += 1; };
let piecesOf = 'a';
const d = { parts: [{ id: 'p', version: 1, role: 'part', pieces: [{ key: 'a' }] }] };
"""


def test_pieces_landing_after_the_switch_are_dropped():
    """Two designs can each have a part called i_want at v8: the part's id and version don't tell them apart."""
    got = _run(("syncPieces",), """const go = syncPieces(d);
        S.slug = 'b';
        finish(new Map([['a', { x: 1 }]])); await go;
        return { added: added.length, drawn: pieces3d.size };""", _PIECES)
    assert got == {"added": 0, "drawn": 0}


def test_a_piece_failing_after_the_switch_says_nothing_about_the_new_design():
    got = _run(("syncPieces",), """const go = syncPieces(d);
        S.slug = 'b';
        fail(new Error('no')); await go;
        return { why: noPieces.size, told };""", _PIECES)
    assert got == {"why": 0, "told": 0}


def test_every_design_write_goes_through_the_guard():
    src = open(JS).read()
    assert re.search(r"^guardDesign\(S\);$", src, re.M)


# --- #173 review: while it loads --------------------------------------------------------------------------------------
_LOADING = """
const S = { slug: 'old', scope: null, station: null, design: { slug: 'old', parts: [] }, opening: null, busy: false };
const el = () => ({ innerHTML: '', hidden: false, textContent: '', disabled: false });
const parts = { designPick: { selectedOptions: [{ value: 'new', textContent: 'New <stool>' }] }, inspector: el(), thread: el(), tree: el(),
                scopeRow: el(), viewHint: el(), msg: el(), send: el() };
const $ = (id) => parts[id];
const esc = (s) => String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');
const meshes = new Map([['p', {}]]), removed = [], scene = { remove: (m) => removed.push(m) };
const clearStation = () => {};
const pieces3d = new Map([['p', {}]]); const dropPieces = (p) => pieces3d.delete(p);
const plainly = (m) => m;
"""


def test_the_new_design_s_name_goes_up_at_once_and_nothing_of_the_old_stays():
    got = _run(("showLoading", "doneLoading", "pickedName"), """S.slug = 'new'; showLoading('new');
        return { h: parts.inspector.innerHTML, design: S.design, thread: parts.thread.innerHTML, meshes: meshes.size + pieces3d.size,
                 msg: parts.msg.disabled, send: parts.send.disabled, tree: parts.tree.hidden };""", _LOADING)
    assert "New &lt;stool&gt;" in got["h"] and "loading" in got["h"]
    assert got["design"] is None and got["thread"] == "" and got["meshes"] == 0 and got["tree"] is True
    assert got["msg"] is True and got["send"] is True


def test_the_chat_comes_back_when_it_lands():
    got = _run(("showLoading", "doneLoading", "pickedName"), """S.slug = 'new'; showLoading('new'); doneLoading();
        return { msg: parts.msg.disabled, send: parts.send.disabled, opening: S.opening };""", _LOADING)
    assert got == {"msg": False, "send": False, "opening": None}


def test_the_send_stays_off_while_a_message_is_going():
    got = _run(("showLoading", "doneLoading", "pickedName"), """S.busy = true; showLoading('new'); doneLoading();
        return { send: parts.send.disabled };""", _LOADING)
    assert got == {"send": True}


_SEND = """
const S = { slug: 'new', opening: 'new', busy: false };
const posts = [];
const liveTurn = () => ({ step() {}, fail() {} });
const api = async (m, u, b) => { posts.push([u, b.message]); return { job_id: 'j' }; };
const follow = async () => {}, refresh = async () => {}, createDesign = () => {};
const $ = () => ({ disabled: false });
"""


def test_a_held_message_can_t_go_to_a_design_not_on_screen():
    got = _run(("send",), """await send('make it taller', null);
        const held = posts.length;
        S.opening = null;
        await send('make it taller', null);
        return { held, after: posts };""", _SEND)
    assert got == {"held": 0, "after": [["/api/designs/new/chat", "make it taller"]]}


def test_pieces_don_t_start_for_a_design_that_was_left():
    got = _run(("syncParts",), """let pieces = 0;
        const d = { parts: [{ id: 'p', version: 1, stl_url: 'x' }] };
        const go = syncParts(d, false);
        S.slug = 'b';
        later[0](buf); await go;
        return { asked };""", _LOADS.replace("const syncPieces = async () => {};", "let asked = 0; const syncPieces = async () => { asked += 1; };"))
    assert got == {"asked": 0}


def test_a_load_that_fails_says_why():
    got = _run(("loadFailed", "doneLoading", "showLoading", "pickedName"), """loadFailed('new', new Error('no such design'));
        return { h: parts.inspector.innerHTML, hint: parts.viewHint.textContent };""", _LOADING)
    assert "Couldn't open it: no such design" in got["h"] and got["hint"] == ""


def test_opening_a_design_that_fails_doesn_t_throw_and_is_said():
    got = _run(("openDesign",), """const go = openDesign('bad');
        later.bad; const k = later['bad'];
        return { waiting: typeof k };""")
    assert got == {"waiting": "function"}
    head = HEAD.replace("const api = (m, url) => new Promise((r) => { later[url.split('/').pop()] = r; });",
                        "const api = async () => { throw new Error('gone'); };")
    got = _run(("openDesign",), "await openDesign('bad'); return { failed, opening: S.opening };", head)
    assert got == {"failed": [["bad", "gone"]], "opening": "bad"}


def test_a_failure_for_a_design_left_says_nothing():
    head = HEAD.replace("const api = (m, url) => new Promise((r) => { later[url.split('/').pop()] = r; });",
                        "const api = async () => { S.slug = 'other'; throw new Error('gone'); };")
    assert _run(("openDesign",), "await openDesign('bad'); return { failed };", head) == {"failed": []}


def test_new_design_during_a_load_ends_the_load():
    from .test_carve_click import _fn as fn

    src = fn(open(JS).read(), "startNew")
    assert src.index("S.slug = null;") < src.index("doneLoading();") and "dropPieces" in src
