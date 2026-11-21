"""The Node the page's tests run design.js in: one that actually imports the vendored three.js.

After a restart, the PATH's node was v18, which can't import three.module.js, so every three.js page test failed, on main too
(CALI-237: reviewer-3 briefly blamed main). A version number isn't the test: here v21.5 and v22.4 fail the import too
("Unexpected token 'export'", #405 review). Each Node is asked to import it, and the first that does is taken: the PATH's,
then nvm's, CI's major first, newest first.

With none, a test skips locally and says what it tried. On CI (``CI`` set) it fails instead: there a Node that can't run the
page's tests is the runner's fault, and a silent skip would hide every page test."""

from __future__ import annotations

import functools
import glob
import os
import shutil
import subprocess

import pytest

#: What CI runs (.github/workflows/tests.yml), so tried first among nvm's.
CI = 22
#: The vendored three.js every page test that draws imports.
THREE = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "vendor", "three", "three.module.js")


def version(node: str) -> str:
    """``node``'s version as it says it ("v22.17.1"), or "" where it doesn't run."""
    try:
        return subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def imports_three(node: str) -> bool:
    """Whether ``node`` imports three.module.js, as the page's tests do (an ES module, by file URL)."""
    url = "file://" + os.path.abspath(THREE)
    try:
        got = subprocess.run([node, "--input-type=module", "-e", f"import * as T from {url!r}; if (!T.REVISION) process.exit(1);"],
                             capture_output=True, text=True, timeout=30)
        return got.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _major(path: str) -> int:
    v = os.path.basename(os.path.dirname(os.path.dirname(path))).lstrip("v").split(".")
    return int(v[0]) if v and v[0].isdigit() else 0


def _numbers(path: str) -> tuple:
    return tuple(int(x) for x in os.path.basename(os.path.dirname(os.path.dirname(path))).lstrip("v").split(".") if x.isdigit())


def candidates() -> list[str]:
    """The PATH's node, then nvm's: CI's major first, then newest first."""
    nvm = glob.glob(os.path.expanduser("~/.nvm/versions/node/v*/bin/node"))
    return [p for p in [shutil.which("node"), *sorted(nvm, key=lambda p: (_major(p) == CI, _numbers(p)), reverse=True)] if p]


def pick(found: list[str]) -> tuple[str | None, list[str]]:
    """The first of ``found`` that imports three.js, and what each one passed over was (for the reason given)."""
    tried = []
    for n in dict.fromkeys(found):
        if imports_three(n):
            return n, tried
        v = version(n)
        tried.append(f"{n} ({v + ': no three.js' if v else 'does not run'})")
    return None, tried


@functools.lru_cache(maxsize=1)
def _found() -> tuple[str | None, tuple[str, ...]]:
    n, tried = pick(candidates())
    return n, tuple(tried)


def node() -> str:
    """The Node to run design.js in. With none: a skip that says what it tried, or on CI a failure."""
    n, tried = _found()
    if n is None:
        why = "no Node that imports three.js: " + (", ".join(tried) or "none found")
        if os.environ.get("CI"):
            pytest.fail(why + " (CI: the runner's Node can't run the page's tests)", pytrace=False)
        pytest.skip(why)
    return n
