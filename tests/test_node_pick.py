"""CALI-237: the page's tests run design.js in a Node that can import three.js, 20 or newer, or skip saying why.

After a restart, the PATH's node was v18, which can't import three.module.js, and every three.js page test failed, on
main too. The tests took whatever `node` came first."""
import os
import stat

import pytest

from . import _node


def _fake(tmp_path, name, version):
    """A stand-in node that says its version, as `node --version` does."""
    p = tmp_path / name
    p.write_text(f"#!/bin/sh\necho v{version}\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_an_old_node_first_on_the_path_is_passed_over_for_one_that_imports_three(tmp_path):
    old, new = _fake(tmp_path, "node18", "18.20.6"), _fake(tmp_path, "node22", "22.17.1")
    got, tried = _node.pick([old, new])
    assert got == new and tried == [f"{old} (v18.20.6)"]


def test_none_new_enough_is_a_skip_with_the_versions_never_a_failure(tmp_path, monkeypatch):
    old = _fake(tmp_path, "node18", "18.19.0")
    monkeypatch.setattr(_node, "candidates", lambda: [old, str(tmp_path / "gone")])
    _node._found.cache_clear()
    try:
        with pytest.raises(pytest.skip.Exception, match=r"no Node 20\+ to import three.js with: .*node18 \(v18.19.0\), .*gone \(does not run\)"):
            _node.node()
    finally:
        _node._found.cache_clear()


def test_nvm_s_are_tried_ci_s_major_first_then_newest(tmp_path, monkeypatch):
    for v in ("18.20.6", "22.4.0", "22.17.1", "24.22.2"):
        d = tmp_path / ".nvm" / "versions" / "node" / f"v{v}" / "bin"
        d.mkdir(parents=True)
        _fake(d, "node", v)
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(tmp_path)))
    monkeypatch.setattr(_node.shutil, "which", lambda n: None)
    got = [os.path.basename(os.path.dirname(os.path.dirname(p))) for p in _node.candidates()]
    assert got == ["v22.17.1", "v22.4.0", "v24.22.2", "v18.20.6"]


def test_every_page_test_takes_its_node_from_here():
    here = os.path.dirname(__file__)
    for f in sorted(os.listdir(here)):
        if f.endswith(".py") and f not in ("_node.py", "test_node_pick.py"):
            src = open(os.path.join(here, f)).read()
            assert 'shutil.which("node")' not in src and "v22.17.1/bin/node" not in src, f
