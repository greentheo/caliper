"""CALI-88 (#64, item 1 on the page): a part's History says its strength check's number cut toward safe, never rounded up.

Item 1 made the cards and replies cut a safety (a fail at 1.96 against 2 is "1.9 times over", never "2"), and the server
stores every number cut to two places (`verdicts.cut`). The History line still rounded it with toFixed(1): a check that
failed at 1.96 read "strength check: fails, 2x", the number it needed. Rule 6: never greener than the check."""
import json
import os
import subprocess

import pytest

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _line(safety, kind="fails"):
    src = open(JS).read()
    h = {"kind": "load", "action": "studied", "safety": safety, "verdict": {"kind": kind, "word": kind}}
    script = "const esc = (s) => String(s);\n" + _fn(src, "historyItem") + f"\nconsole.log(JSON.stringify(historyItem({json.dumps(h)}, 3)));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@pytest.mark.parametrize("safety,kind,shown", [(1.96, "fails", ", 1.9x"), (1.99, "fails", ", 1.9x"), (3.11, "holds", ", 3.1x"),
                                               (9.96, "holds", ", 9.9x"), (2.0, "holds", ", 2x"), (0.04, "fails", ", under 0.1x")])
def test_the_history_line_cuts_the_number_toward_safe(safety, kind, shown):
    line = _line(safety, kind)
    assert f"strength check: {kind}{shown}</li>" in line, line
