"""CALI-91 (#68; rule 6) — words leave the machine only when the person sends them.

The 🎤 button used the browser's speech recognition, which sends the audio to its maker (Google, in Chrome), as
soon as it was pressed. And nothing on the page said that what's typed goes to Claude."""

import json
import os
import re
import shutil
import subprocess

import pytest

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
HTML = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "index.html")


def _node():
    for n in (os.path.expanduser("~/.nvm/versions/node/v22.17.1/bin/node"), shutil.which("node")):
        if n and os.path.exists(n):
            return n
    pytest.skip("no node")


def _fn(src, name):
    """One top-level function, as written: a one-liner, or up to its closing brace at the start of a line."""
    line = re.search(rf"^(async )?function {name}\(.*$", src, re.M)
    assert line, name
    if line.group(0).count("{") == line.group(0).count("}"):
        return line.group(0) + "\n"
    return re.search(rf"^(async )?function {name}\(.*?^}}\n", src, re.S | re.M).group(0)


def _const(src, name):
    return re.search(rf"^const {name} = .*?;\n", src, re.M).group(0)


#: A browser: a speech recognizer that records starts, local storage, and just enough DOM for the ask.
BROWSER = """
const setTimeout = () => 0, clearTimeout = () => {};      // the tip's 9 s fade: not waited for here
const started = [];
let localAvailable = 'unavailable', storageBroken = false;
const store = {};
const localStorage = {
  getItem: (k) => { if (storageBroken) throw new Error('blocked'); return k in store ? store[k] : null; },
  setItem: (k, v) => { if (storageBroken) throw new Error('blocked'); store[k] = v; },
};
class Speech {
  static async available(opts) { return opts.processLocally ? localAvailable : 'available'; }
  start() { started.push({ local: !!this.processLocally }); }
  stop() {}
}
const navigator = { language: 'en-US' };
let listening = null;
const esc = (s) => String(s);
function el() {
  const kids = [];
  const node = { className: '', innerHTML: '', textContent: '', classList: { add() {}, remove() {} }, focus() {},
                 append: (c) => kids.push(c), remove() { const i = parent.kids.indexOf(node); if (i >= 0) parent.kids.splice(i, 1); },
                 querySelector: (sel) => {
                   if (sel === '.mic-ask') return kids.find((k) => k.className.includes('mic-ask')) || null;
                   if (sel === '.mic-tip') return kids.find((k) => k.className.includes('mic-tip')) || null;
                   return null; } };
  return node;
}
const parent = { kids: [], append(c) { this.kids.push(c); },
                 querySelector(sel) { return this.kids.find((k) => k.className.split(' ').includes(sel.slice(1))) || null; } };
const document = { createElement: () => {
  const n = el();
  n.querySelector = (sel) => {
    const m = /data-(talk|type)/.exec(sel);
    if (!m || !n.innerHTML.includes(`data-${m[1]}`)) return null;
    n[m[1]] = n[m[1]] || {};
    return n[m[1]];
  };
  n.remove = () => { const i = parent.kids.indexOf(n); if (i >= 0) parent.kids.splice(i, 1); };
  return n;
} };
const btn = { parentElement: parent, classList: { add() {}, remove() {} } };
const box = { value: '', focus() {} };
const asked = () => parent.kids.find((k) => k.className.includes('mic-ask'));
"""


def _script(body):
    src = open(JS).read()
    parts = [_const(src, n) for n in ("DICTATION", "MIC_ASK", "MIC_KEY")]
    parts += [_fn(src, n) for n in ("micTip", "micAnswer", "micRemember", "onDevice", "dictate", "micAsk", "listen")]
    return BROWSER + "\n".join(parts) + "\nconst out = {};\n" + body + "\nconsole.log(JSON.stringify(out));"


def _run(body):
    got = subprocess.run([_node(), "--input-type=module", "-e", _script(body)], capture_output=True, text=True,
                         timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_the_browser_listens_only_after_a_yes():
    out = _run("""
await dictate(box, btn);
out.first = { started: started.length, asked: !!asked(), text: asked() && asked().innerHTML };
asked().type.onclick();                        // Type instead
out.typed = { started: started.length, asked: !!asked(), kept: store['caliper.mic'] };
await dictate(box, btn);                       // pressed again after "Type instead": it doesn't listen
out.again = { started: started.length, text: asked() && asked().innerHTML };
asked().talk.onclick();                        // Talk
out.talked = { started: started.length, kept: store['caliper.mic'] };
listening = null;
await dictate(box, btn);                       // the second press after Talk: no question
out.second = { started: started.length, asked: !!asked() };
for (const k of Object.keys(store)) delete store[k];   // site data cleared
listening = null;
await dictate(box, btn);
out.cleared = { started: started.length, asked: !!asked() };
""")
    assert out["first"]["started"] == 0 and out["first"]["asked"]
    assert out["first"]["text"].startswith("Your browser turns speech into words by sending it to its maker (Google, "
                                           "in Chrome). Talk anyway?")
    assert out["typed"] == {"started": 0, "asked": False, "kept": "no"}
    assert out["again"]["started"] == 0 and out["again"]["text"].startswith("Use your computer's dictation")
    assert out["talked"] == {"started": 1, "kept": "yes"}
    assert out["second"] == {"started": 2, "asked": False}
    assert out["cleared"] == {"started": 2, "asked": True}


def test_on_the_device_it_listens_without_asking_and_nothing_leaves():
    out = _run("""
localAvailable = 'available';
await dictate(box, btn);
out.got = { started, asked: !!asked() };
""")
    assert out["got"] == {"started": [{"local": True}], "asked": False}


def test_with_storage_blocked_it_still_asks_and_never_breaks():
    out = _run("""
storageBroken = true;
await dictate(box, btn);
out.first = { started: started.length, asked: !!asked() };
asked().talk.onclick();
out.talked = started.length;
listening = null;
await dictate(box, btn);
out.again = { started: started.length, asked: !!asked() };
""")
    assert out["first"] == {"started": 0, "asked": True} and out["talked"] == 1
    assert out["again"] == {"started": 1, "asked": True}          # forgotten: it just asks again


def test_rec_start_is_only_in_listen_and_listen_only_after_a_yes_or_on_the_device():
    """The check on design.js the issue asks for, by reading it: one rec.start(), inside listen(); listen() is called
    from the Talk button, and from dictate() only past the on-device-or-yes gate."""
    src = open(JS).read()
    assert src.count("rec.start()") == 1 and "rec.start()" in _fn(src, "listen")
    d = _fn(src, "dictate")
    assert "if (!local && micAnswer() !== 'yes') return micAsk(box, btn, lang);" in d
    assert d.index("return micAsk(") < d.index("listen(box, btn, lang, local)")
    assert "listen(" not in src.replace(_fn(src, "listen"), "").replace(d, "").replace(
        "micRemember('yes'); ask.remove(); listen(box, btn, lang, false);", "")
    assert "your Mac types" not in src                            # the fallback names no machine it can't see


def test_the_page_says_what_goes_to_claude_and_the_script_is_new():
    src = open(JS).read()
    assert "What you type goes to Claude (Anthropic's AI) to design it." in src
    assert re.search(r'design\.js\?v=(\d+)', open(HTML).read()).group(1) != "43"
    out = subprocess.run([_node(), "--input-type=module", "-e", _const(src, "TO_CLAUDE") + _fn(src, "sendNote") + """
const S = { claude: true };
const out = { fresh: sendNote(null), none: sendNote({ log: [] }), sent: sendNote({ log: [{ kind: 'message' }] }) };
S.claude = false;
out.nokey = sendNote({ log: [] });
console.log(JSON.stringify(out));"""], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got == {"fresh": "What you type goes to Claude (Anthropic's AI) to design it.",
                   "none": "What you type goes to Claude (Anthropic's AI) to design it.", "sent": "", "nokey": ""}
