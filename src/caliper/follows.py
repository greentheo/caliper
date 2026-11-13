"""CALI-171 (#266) — a part added to fit another reads that part's numbers live, never copies them.

Theo's step-stool-5: the fillet strips added to fit the stool set their own ``stool_h`` 508 (a 20 in stool), when he'd made
it 16 in through Parameters. And had they read it right, a later Parameters change wouldn't have moved them.

A follower says what it reads, at module level, its ``PARAMS`` holding the current values::

    FOLLOWS = {"stool_h": ("step_stool", "height"), "ply_t": ("step_stool", "ply_t")}

Writing the source writes its followers (:func:`update`, from :meth:`DesignStore.write_part`), as a mirror follows its
source (#246) and the skeleton drives its readers (#143): each follower's ``PARAMS`` set through ``aero.set_params`` and
written as its own new version in the same turn, so every reader still sees a plain script and the sandbox builds it
alone. The source's reply names what followed (:func:`said`). A follower whose source is gone keeps its last values and
says so on its next build (:func:`check`); a cycle is refused in words (:func:`refuse_cycle`).
"""

from __future__ import annotations

import ast
from typing import Optional

NAME = "FOLLOWS"
#: How close a copied number must be to the source's to be taken as the same number (mm).
SAME_MM = 0.05


def declared(script: str) -> dict[str, tuple[str, str]]:
    """``{param: (source part, source param)}`` from a script's module-level ``FOLLOWS``; {} where it has none."""
    try:
        tree = ast.parse(script or "")
    except SyntaxError:
        return {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == NAME and isinstance(node.value, ast.Dict)):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                if (isinstance(k, ast.Constant) and isinstance(k.value, str) and isinstance(v, (ast.Tuple, ast.List))
                        and len(v.elts) == 2 and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in v.elts)):
                    out[k.value] = (v.elts[0].value, v.elts[1].value)
            return out
    return {}


def part_said(pid: str) -> str:
    """A part as the drive line says it (#253): "the inside fillets"."""
    return "the " + pid.replace("_", " ")


def _follow_word(pid: str) -> str:
    return "follow" if pid.rstrip().endswith("s") else "follows"


def followers_of(store, source: str) -> list[str]:
    """The parts whose ``FOLLOWS`` read ``source``. Never a mirror: its generated script carries its source's ``FOLLOWS``, and
    it follows through its source, written again from it (#271 review: taken as a follower of its own, writing it was
    refused, and a Parameters change stopped half way)."""
    from . import mirror

    out = []
    for p in store.design.parts:
        if (p.id != source and store.is_scripted(p.id) and not mirror.source_of(store, p.id)
                and any(s == source for s, _ in declared(store.read_script(p.id)).values())):
            out.append(p.id)
    return out


def refuse_cycle(store, part_id: str, script: str) -> None:
    """Raises, in words, where ``part_id`` would follow a part that follows it, however far round (as #246 refuses a mirror
    of a mirror)."""
    seen, todo = set(), [s for s, _ in declared(script).values()]
    while todo:
        src = todo.pop()
        if src in seen:
            continue
        seen.add(src)
        if src == part_id:
            continue
        if not store.design.part(src) or not store.is_scripted(src):
            continue
        reads = {s for s, _ in declared(store.read_script(src)).values()}
        if part_id in reads:
            raise ValueError(f"{part_said(part_id)} can't follow {part_said(src)}: {part_said(src)} {_follow_word(src)} "
                             f"{part_said(part_id)}. One of them has to own the number.")
        todo.extend(reads)


def _unit(name: str, note: str = "") -> str:
    from .params import unit_of

    return " mm" if unit_of(name, note) == "mm" else ""


def update(store, source: str) -> list[dict]:
    """Write each follower of ``source`` again with the numbers it reads from it, where they've changed: ``[{part, values}]``,
    also kept on the store for the turn's reply (:func:`said`)."""
    from . import aero

    if not store.is_scripted(source):
        return []
    have = aero.read_params(store.read_script(source)) or {}
    done = []
    for pid in followers_of(store, source):
        script = store.read_script(pid)
        now = aero.read_params(script) or {}
        new = {n: float(have[k]) for n, (s, k) in declared(script).items()
               if s == source and k in have and n in now and abs(float(now[n]) - float(have[k])) > 1e-9}
        if not new:
            continue
        words = "; ".join(f"{n} set to {v:g}{_unit(n)} by {part_said(source)}" for n, v in new.items())
        store.write_part(pid, aero.set_params(script, new), action="follow", feedback=words, extra={"followed": source})
        done.append({"part": pid, "source": source, "values": new})
    store.followed = list(getattr(store, "followed", []) or []) + done
    return done


def said(store, clear: bool = True) -> str:
    """What followed this turn, as the source's reply says it (#253's rule: part names): "the inside fillets follow the
    stool: stool_h now 457.2 mm". '' where nothing did."""
    got = list(getattr(store, "followed", []) or [])
    if clear:
        store.followed = []
    lines = []
    for d in got:
        nums = ", ".join(f"{n} now {v:g}{_unit(n)}" for n, v in d["values"].items())
        lines.append(f"{part_said(d['part'])} {_follow_word(d['part'])} {part_said(d['source'])}: {nums}")
    return "; ".join(lines)


def _size(name: str) -> tuple[str, str]:
    from .skeleton import SIZES, _subject

    if name.lower() in SIZES:
        return "", SIZES[name.lower()]
    return _subject(name)


def _named(name: str, key: str, source: str) -> bool:
    """Whether ``name`` is the source's ``key`` by its name, as ``skeleton_shadow`` matches (#243): the same size word, and
    the same subject, or the source itself as its subject (``stool_h`` for the stool's ``h``)."""
    if name == key:
        return True
    (sn, zn), (sk, zk) = _size(name), _size(key)
    if not zn or zn != zk:
        return False
    own = {source, *source.split("_")}
    return sn == sk or (sn in own and (not sk or sk in own))


def check(script: str, sources: dict[str, Optional[dict]], part_id: str, on: Optional[str] = None):
    """The round's check of a follower (#266), one :class:`AssertionResult`, ``follows``:

    - a number it follows that isn't the source's now fails ("stool_h is 508 mm, but the stool's h is 406.4 mm now");
    - a number its name says is ``on``'s, not listed in ``FOLLOWS``, fails: it's a copy;
    - a number equal to one of ``on``'s by chance (19.05, 25.4) is a note, never a fail;
    - a source that's gone, or a number it no longer has, is a note: it keeps its last values.

    ``sources``: each source part's ``PARAMS`` (None where it isn't in the design)."""
    from . import aero
    from .evaluate import AssertionResult

    mine = aero.read_params(script or "") or {}
    fol = declared(script)
    wrong, notes = [], []
    for n, (src, key) in fol.items():
        have = sources.get(src)
        kept = f"{mine[n]:g}{_unit(n)}" if n in mine else "its own"
        if have is None:
            notes.append(f"{n} follows {part_said(src)}'s {key}, but there's no {part_said(src)[4:]} in the design now: "
                         f"it keeps {kept}")
        elif key not in have:
            notes.append(f"{n} follows {part_said(src)}'s {key}, but {part_said(src)} has no {key} now: it keeps {kept}")
        elif n in mine and abs(float(mine[n]) - float(have[key])) > SAME_MM:
            wrong.append(f"{n} is {mine[n]:g}{_unit(n)}, but {part_said(src)}'s {key} is {float(have[key]):g}{_unit(n)} now: "
                         f"it follows it, so set it to {float(have[key]):g}")
    other = sources.get(on) if on else None
    for n, v in mine.items():
        if n in fol or other is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        for k, w in other.items():
            if not isinstance(w, (int, float)) or isinstance(w, bool):
                continue
            same = abs(float(v) - float(w)) <= SAME_MM
            if _named(n, k, on):
                wrong.append(f"{n} copies {part_said(on)}'s {k} ({float(w):g}{_unit(n)}): read it through {NAME}" if same
                             else f"{n} is {part_said(on)}'s {k} by its name, at {float(v):g}{_unit(n)} against "
                                  f"{float(w):g}{_unit(n)} on it: read it through {NAME}")
                break
            if same:
                notes.append(f"{n} is {part_said(on)}'s {k} ({float(w):g}{_unit(n)}) too: if it's the same thing, read it "
                             f"through {NAME}")
                break
    ok = not wrong
    return AssertionResult(id="follows", expr=f"{part_id} reads the numbers it shares through {NAME}",
                           status="pass" if ok else "fail", passed=ok, actual=len(wrong),
                           detail="; ".join(wrong + notes))


def sources_of(store, script: str, on: Optional[str] = None) -> dict[str, Optional[dict]]:
    """Each part a script follows (and ``on``), with its ``PARAMS``; None where it isn't in the design."""
    from . import aero

    out = {}
    for src in {s for s, _ in declared(script).values()} | ({on} if on else set()):
        out[src] = (aero.read_params(store.read_script(src)) or {}) if store.design.part(src) and store.is_scripted(src) else None
    return out


def told(store, on: str) -> str:
    """What the designer of a part added on ``on`` reads (#266): ``on``'s numbers, its comments true, and to follow them."""
    if not store.design.part(on) or not store.is_scripted(on):
        return ""
    import re

    from . import aero

    script = store.read_script(on)
    node = aero._params_node(ast.parse(script))
    if node is None:
        return ""
    lines = script.splitlines()
    block = "\n".join(lines[node.lineno - 1:node.end_lineno])
    some = next(iter(aero.read_params(script) or {"h": 0}), "h")
    return (f"\n\n{part_said(on)[:1].upper() + part_said(on)[1:]}'s numbers (its PARAMS, in mm):\n{block}\n"
            f"Read any of these your part uses through a module-level {NAME} dict, never copy one: "
            f'FOLLOWS = {{"your_name": ("{on}", "{some}")}}, with your PARAMS holding its value now. When {on} changes, your '
            f"part's number follows it.") if re.search(r"\S", block) else ""
