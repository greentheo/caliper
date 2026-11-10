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
    assert got["log"] == [["render", "quick"], ["sync", "quick"]]


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
