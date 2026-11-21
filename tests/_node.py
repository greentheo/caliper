"""The Node the page's tests run design.js in: one that can import the vendored three.js.

three.module.js is ES2022 and more; Node 18 can't import it, so after a restart that left v18 first on the PATH, every
three.js page test failed, on main too (CALI-237, the foreman: reviewer-3 briefly blamed main). The first Node that's 20
or newer is taken: the PATH's, then nvm's, v22 first (what CI runs), newest first. With none, the test skips and says what
it found, never a failure that reads as the code's."""

from __future__ import annotations

import functools
import glob
import os
import shutil
import subprocess

import pytest

#: The oldest Node that imports three.module.js.
MIN = 20
#: What CI runs (.github/workflows/tests.yml), so tried first among nvm's.
CI = 22


def version(node: str) -> tuple[int, ...]:
    """``node``'s version as numbers, ``()`` where it doesn't run."""
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        return tuple(int(x) for x in out.lstrip("v").split("."))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ()


def candidates() -> list[str]:
    """The PATH's node, then nvm's: CI's major first, then newest first."""
    nvm = glob.glob(os.path.expanduser("~/.nvm/versions/node/v*/bin/node"))
    key = lambda p: (os.path.basename(os.path.dirname(os.path.dirname(p))).lstrip("v").split(".")[0] == str(CI),
                     tuple(int(x) for x in os.path.basename(os.path.dirname(os.path.dirname(p))).lstrip("v").split(".")
                           if x.isdigit()))
    return [p for p in [shutil.which("node"), *sorted(nvm, key=key, reverse=True)] if p]


def pick(found: list[str]) -> tuple[str | None, list[str]]:
    """The first of ``found`` that's ``MIN`` or newer, and what each one tried was (for the skip's reason)."""
    tried = []
    for n in dict.fromkeys(found):
        v = version(n)
        if v and v[0] >= MIN:
            return n, tried
        tried.append(f"{n} ({'v' + '.'.join(map(str, v)) if v else 'does not run'})")
    return None, tried


@functools.lru_cache(maxsize=1)
def _found() -> tuple[str | None, tuple[str, ...]]:
    n, tried = pick(candidates())
    return n, tuple(tried)


def node() -> str:
    """The Node to run design.js in, or the test skips, saying why."""
    n, tried = _found()
    if n is None:
        pytest.skip(f"no Node {MIN}+ to import three.js with: " + (", ".join(tried) or "none found"))
    return n
