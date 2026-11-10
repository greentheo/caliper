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
