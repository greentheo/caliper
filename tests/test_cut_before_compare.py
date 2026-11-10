"""CALI-152 (#213): a safety rounded to two places before it was compared turned a fail into a pass: a true 1.995
against 2 was stored as 2.0 and read "holds". Every producer that makes a verdict now stores its safety cut toward
safe (verdicts.cut), so nothing compared with it afterwards is greener than the check."""

import os
import re

import numpy as np
import pytest

from caliper import verdicts

SRC = os.path.join(os.path.dirname(verdicts.__file__))


@pytest.mark.parametrize("x, got", [(1.995, 1.99), (1.9999, 1.99), (2.0, 2.0), (0.999, 0.99), (3.117, 3.11)])
def test_cut_never_raises_a_number(x, got):
    assert verdicts.cut(x) == got and verdicts.cut(x) <= x


def test_no_producer_rounds_a_safety():
    """Each safety a verdict is made from is cut, not rounded: "safety…": round(…) or safety… = round(…) anywhere is
    a fail that can read as a pass."""
    bad = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".py"):
            continue
        for i, line in enumerate(open(os.path.join(SRC, name)), 1):
            if re.search(r"""["'][a-z_]*safety[a-z_]*["']\s*:\s*round\(|\b[a-z_]*safety[a-z_]*\s*=\s*round\(""", line):
                bad.append(f"{name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_the_plate_checks_number_at_1_995_against_2_fails(tmp_path):
    """The beam check on #106's bench top, with the plywood's strength set so its number is 1.995 across the grain:
    stored 1.99, and the case it governs doesn't hold at 2."""
    from caliper import load_study as L
    from caliper.design import DesignStore

    from .test_beam_width import TOP

    store = DesignStore.create("a bench", base=str(tmp_path))
    store.write_part("bench", TOP, intent="a bench")
    ctx = L.prepare(store, "bench")
    (load,) = ctx["loads"]
    mat = dict(ctx.get("plate_mat") or ctx["mat"])
    first = L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))
    mat["strength"] = 1.995 * first["stress_mpa"] / mat["across"]
    got = L.plate_check(ctx["pieces"], load, mat, ctx["tol"], under=ctx.get("under"))
    assert got["safety_across"] == 1.99, got["safety_across"]


def test_tipping_cuts_too():
    from caliper import tipping

    square = np.array([[-100.0, -100.0], [100.0, -100.0], [100.0, 100.0], [-100.0, 100.0]])
    # 1000 N at the middle, 100 mm from the edge it tips about: 100,000 N mm restoring; a push 1 m up giving
    # 100,000 / 1.995 N mm overturning is 1.995 times over, a fail at 2
    got = tipping.moments(square, [(1000.0, np.array([0.0, 0.0]))], 100000.0 / 1.995 / 1000.0, np.array([1.0, 0.0]), 1000.0)
    assert got["safety"] == 1.99, got
