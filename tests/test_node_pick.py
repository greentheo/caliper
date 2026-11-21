"""CALI-237: the page's tests run design.js in a Node that actually imports three.js, or skip saying why (fail on CI).

After a restart, the PATH's node was v18, which can't import three.module.js, and every three.js page test failed, on main
too. A version number isn't the test: here v21.5 and v22.4 fail the import as well (#405 review)."""
import os
import re
import stat

import pytest

from . import _node


def _fake(tmp_path, name, version, imports=True):
    """A stand-in node: it says its version, and imports three.js or not, as asked."""
    p = tmp_path / name
    p.write_text(f'#!/bin/sh\nif [ "$1" = --version ]; then echo v{version}; exit 0; fi\nexit {0 if imports else 1}\n')
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_a_node_that_can_t_import_three_is_passed_over_whatever_its_version(tmp_path):
    """#405 review: v22.4 is past 20, and fails the import with "Unexpected token 'export'"."""
    old = _fake(tmp_path, "node18", "18.20.6", imports=False)
    new_but_not = _fake(tmp_path, "node22_4", "22.4.0", imports=False)
    good = _fake(tmp_path, "node22_17", "22.17.1")
    got, tried = _node.pick([old, new_but_not, good])
    assert got == good
    assert tried == [f"{old} (v18.20.6: no three.js)", f"{new_but_not} (v22.4.0: no three.js)"]


def _none(tmp_path, monkeypatch):
    bad = _fake(tmp_path, "node21", "21.5.0", imports=False)
    monkeypatch.setattr(_node, "candidates", lambda: [bad, str(tmp_path / "gone")])
    _node._found.cache_clear()
    return bad


def test_none_that_imports_it_is_a_skip_that_says_what_it_tried(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    _none(tmp_path, monkeypatch)
    try:
        with pytest.raises(BaseException) as got:
            _node.node()
        assert got.type is pytest.skip.Exception
        assert re.search(r"no Node that imports three.js: .*node21 \(v21.5.0: no three.js\), .*gone \(does not run\)", str(got.value))
    finally:
        _node._found.cache_clear()


def test_on_ci_none_that_imports_it_fails_never_a_silent_skip(tmp_path, monkeypatch):
    """#405 review's should-fix: on CI a skip would hide every page test."""
    monkeypatch.setenv("CI", "true")
    _none(tmp_path, monkeypatch)
    try:
        with pytest.raises(BaseException) as got:            # a skip mustn't pass for this, nor be skipped itself
            _node.node()
        assert got.type is pytest.fail.Exception and "CI: the runner's Node can't run the page's tests" in str(got.value)
    finally:
        _node._found.cache_clear()


def test_the_real_three_is_what_s_imported(tmp_path):
    """The check is an import of the vendored three.module.js itself, not a version: a Node that runs but can't import it
    (a script that only says a version) is passed over."""
    says_only = tmp_path / "says"
    says_only.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo v24.0.0; exit 0; fi\nexit 3\n')
    says_only.chmod(says_only.stat().st_mode | stat.S_IEXEC)
    assert not _node.imports_three(str(says_only)) and os.path.exists(_node.THREE)


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
