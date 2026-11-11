"""CALI-92 (#70): the reviews' findings that #62-#66 don't cover, one test each."""

import json
import os
import re
import subprocess

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _run(script):
    out = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout
    return json.loads(out)


def test_say_it_simpler_is_only_offered_with_a_key():
    """Item 13: offline, "Say it simpler" was a fact dump: simpler words need Claude, so no key, no button."""
    fn = _fn(open(JS).read(), "simplerOffered")
    got = _run(fn + """
const S = { busy: false, claude: false };
const reply = { kind: 'reply', reply: 'It holds.' };
console.log(JSON.stringify([
  simplerOffered({ claude: true, log: [reply] }), simplerOffered({ claude: false, log: [reply] }),
  simplerOffered({ claude: true, log: [{ kind: 'message' }] }), simplerOffered({ claude: true, proposal: {}, log: [reply] })]));
""")
    assert got == [True, False, False, False], got


def test_a_report_too_long_for_a_link_keeps_the_line_that_failed():
    """Item 16: the page cut a long report from its end, which is the trace's last line, the one that failed."""
    fn = _fn(open(JS).read(), "trimReport")
    got = _run(fn + r"""
const trace = Array.from({length: 600}, (_, k) => `  File "x.py", line ${k}, in f`).join('\n') + '\nValueError: the line that failed';
const body = '**What broke:** a thing\n\n```\n' + trace + '\n```\nI was carving it.\n';
const cut = trimReport(body, 6500);
const short = trimReport('nothing to cut', 6500);
const noFence = trimReport('x'.repeat(9000), 6500);
console.log(JSON.stringify({ fits: encodeURIComponent(cut).length <= 6500, last: cut.includes('ValueError: the line that failed'),
  head: cut.startsWith('**What broke:** a thing'), fences: (cut.match(/```/g) || []).length, closed: /\n```\nI was carving it\.\n$/.test(cut),
  middle: cut.includes('…'), short, noFence: encodeURIComponent(noFence).length <= 6500 }));
""")
    assert got == {"fits": True, "last": True, "head": True, "fences": 2, "closed": True, "middle": True,
                   "short": "nothing to cut", "noFence": True}, got


def _goto_page(src):
    return ("const GOTO = { patterns: 'patternBox', load: 'loadBox', release: 'relBox' };\n"
            + re.search(r"^const PART_PANELS = .*$", src, re.M).group(0) + "\n" + _fn(src, "gotoFor") + _fn(src, "goTo"))


def test_a_goto_line_reaches_its_panel_from_either_view_or_isnt_a_link():
    """Item 19: the design card's "Make the patterns…" pointed at a panel only the part view has: the click did
    nothing. A goto selects the part first, if there's one to select; with several it isn't drawn as a link."""
    src = open(JS).read()
    got = _run(_goto_page(src) + r"""
const boxes = {}; let scoped = [];
const $ = (id) => boxes[id] || null;
const S = { scope: null, design: { parts: [{ id: 'stool', role: 'part' }] } };
function setScope(p) { scoped.push(p); S.scope = p; boxes.patternBox = p ? { previousElementSibling: null, closest: () => null, classList: { add() {}, remove() {} }, scrollIntoView() { boxes.scrolled = true; } } : undefined; }
const one = gotoFor({ study: 'patterns' });
goTo('patternBox');
setTimeout(() => {
  const clicked = [...scoped], reached = !!boxes.scrolled;
  S.scope = null; S.design.parts.push({ id: 'lid', role: 'part' });
  const several = gotoFor({ study: 'patterns' });
  scoped = []; boxes.patternBox = undefined; goTo('patternBox');
  const release = gotoFor({ action: 'release' });
  S.scope = 'stool';
  console.log(JSON.stringify({ one, clicked, reached, several, none: scoped, release, relFromPart: gotoFor({ action: 'release' }) }));
}, 120);
""")
    assert got == {"one": "patternBox", "clicked": ["stool"], "reached": True, "several": "", "none": [],
                   "release": "relBox", "relFromPart": "relBox"}, got


def test_only_a_body_cut_to_fit_the_bed_is_pinned():
    """Item 22: "2 pieces pinned together", when two printed sides were simply apart and nothing was cut."""
    import trimesh

    from caliper import printing

    bed = (200.0, 200.0, 200.0)
    a = trimesh.creation.box((20, 100, 100))
    b = trimesh.creation.box((20, 100, 100))
    b.apply_translation((400, 0, 0))                     # apart: 420 mm across a 200 mm bed, nothing joining them
    apart = trimesh.util.concatenate([a, b])
    parts = printing.split(apart, bed)
    assert len(parts) >= 2 and not printing.pinned(parts), [p.metadata for p in parts]
    bar = trimesh.creation.box((420, 60, 60))             # one body too long for the bed: cut, and pinned
    cut = printing.split(bar, bed)
    assert len(cut) >= 2 and printing.pinned(cut)
    whole = printing.split(trimesh.creation.box((50, 50, 50)), bed)
    assert len(whole) == 1 and not printing.pinned(whole)


def test_a_panels_glue_line_comes_from_its_material():
    """Item 15: every non-wood panel was told "foam-safe adhesive": acrylic and aluminium need other words, and where
    the right words aren't known, there are none."""
    from caliper import release

    foam = release.fasten_panels([{"material": "xps"}, {"material": "plywood"}])
    assert "foam-safe adhesive" in foam and "trim the inside corners" in foam
    other = release.fasten_panels([{"material": "acrylic"}])
    assert "adhesive" not in other and "glue" not in other.lower() and "Fasten them" in other, other


def test_the_shopping_allowance_says_foam_safe_only_where_foam_is_glued(tmp_path, monkeypatch):
    """#215 review: the hardware allowance said "foam-safe adhesive" whatever the part was made of."""
    from caliper import construction as C
    from caliper import release
    from caliper.design import DesignStore

    store = DesignStore.create("a box", base=str(tmp_path))
    made = {"foamy": [{"kind": "sheet", "material": "xps"}], "plain": [{"kind": "sheet", "material": "plywood"}]}
    monkeypatch.setattr(C, "declared", lambda s, pid, *a, **k: {"construction": made[pid]})
    rows = release.shopping(store, {}, {}, {p: [{"label": "glue, screws & hardware"}] for p in made}, {})
    said = [r["for"] for g in rows["groups"] for r in g["rows"] if "hardware" in r["item"]]
    assert len(said) == 2 and "foam-safe adhesive" in said[0] and "foam" not in said[1] and "screws" in said[1], said
