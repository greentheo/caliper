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
