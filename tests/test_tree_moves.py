"""CALI-102 (#94, slice b) — drag a part in the tree to reorder it, or onto another part to sit under it. Display only: a move changes no
part's id, file, version or check. A piece moving into another part would change two scripts, so it isn't this (#3)."""
import hashlib
import json
import os
import subprocess

import pytest

from caliper import design_api, scorecard, tree
from caliper.design import DesignStore

from .test_carve_click import _fn, _node

JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")
pytest.importorskip("cadquery")

BOX = "import cadquery as cq\n\ndef build(params):\n    return cq.Workplane('XY').box(%d, 20, 10)\n"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path / "shop.yaml"))
    s = DesignStore.create("three parts", base=str(tmp_path / "designs"))
    for i, pid in enumerate(("a", "b", "c")):
        s.write_part(pid, BOX % (20 + i), intent=pid)
    return s


def _fingerprint(store):
    out = {}
    for here, _, files in os.walk(store.root):
        for f in files:
            if f == "design.yaml" or f.startswith(".") or "__pycache__" in here or f.endswith("log.jsonl"):
                continue
            with open(os.path.join(here, f), "rb") as fh:
                out[os.path.relpath(os.path.join(here, f), store.root)] = hashlib.sha1(fh.read()).hexdigest()
    return out


def test_with_no_moves_it_is_the_parts_in_their_own_order(store):
    assert tree.layout(store) == {"order": ["a", "b", "c"], "parent": {}}


def test_a_move_is_saved(store):
    tree.set_layout(store, ["c", "a", "b"], {"b": "a"})
    again = DesignStore.load(store.root)
    assert tree.layout(again) == {"order": ["c", "a", "b"], "parent": {"b": "a"}}


def test_a_move_changes_no_id_file_version_or_check(store):
    card = scorecard.compute(store)
    ids = [(p.id, p.version) for p in store.design.parts]
    before = _fingerprint(store)
    state_was = design_api.design_state(store)
    tree.set_layout(store, ["c", "a", "b"], {"b": "a"})
    again = DesignStore.load(store.root)
    assert [(p.id, p.version) for p in again.design.parts] == ids          # the design's own list, order and all
    assert _fingerprint(again) == before
    assert scorecard.list_cards(again, 1)[0]["versions"] == card["versions"] and not scorecard.list_cards(again, 1)[0].get("outdated")
    state = design_api.design_state(again)
    assert [p["id"] for p in state["parts"]] == [p["id"] for p in state_was["parts"]]
    assert state["tree"] == {"order": ["c", "a", "b"], "parent": {"b": "a"}}


@pytest.mark.parametrize("order,parent,word", [(["a", "b"], {}, "every part"), (["a", "b", "b"], {}, "every part"), (["a", "b", "z"], {}, "every part"),
                                               (["a", "b", "c"], {"a": "a"}, "inside itself"), (["a", "b", "c"], {"a": "b", "b": "a"}, "inside itself"),
                                               (["a", "b", "c"], {"a": "b", "b": "c", "c": "a"}, "inside itself"), (["a", "b", "c"], {"z": "a"}, "no part")])
def test_a_bad_move_is_refused(store, order, parent, word):
    with pytest.raises(ValueError, match=word):
        tree.set_layout(store, order, parent)
    assert tree.layout(store) == {"order": ["a", "b", "c"], "parent": {}}


def test_a_part_added_later_comes_last(store):
    tree.set_layout(store, ["c", "b", "a"], {})
    store.write_part("d", BOX % 30, intent="d")
    assert tree.layout(store)["order"] == ["c", "b", "a", "d"]


def test_a_part_removed_takes_its_place_with_it_and_what_sat_under_it_comes_up(store):
    from caliper import trash

    tree.set_layout(store, ["a", "b", "c"], {"b": "a", "c": "b"})
    trash.remove(store, "a")
    got = tree.layout(DesignStore.load(store.root))
    assert got["order"] == ["b", "c"] and got["parent"] == {"c": "b"}


def test_through_the_route(store):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    c = TestClient(create_app())
    slug = store.design.slug
    got = c.post(f"/api/designs/{slug}/tree", json={"order": ["b", "a", "c"], "parent": {"c": "b"}})
    assert got.status_code == 200 and got.json()["tree"] == {"order": ["b", "a", "c"], "parent": {"c": "b"}}
    assert c.post(f"/api/designs/{slug}/tree", json={"order": ["a"], "parent": {}}).status_code == 422


# --- the page ----------------------------------------------------------------------------------------------------------
def _page(body, tree_=None):
    src = open(JS).read()
    head = "const D = " + json.dumps({"parts": [{"id": i} for i in "abcd"], "tree": tree_ or {}}) + ";\n"
    script = head + "".join(_fn(src, n) for n in ("treeRows", "underPart", "dropped", "dropZone")) + f"\nconsole.log(JSON.stringify((() => {{ {body} }})()));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _rows(tree_):
    return [[r[0], r[1]] for r in _page("return treeRows(D).map((r) => [r.p.id, r.depth]);", tree_)]


def test_an_old_design_shows_its_parts_in_order():
    assert _rows({}) == [["a", 0], ["b", 0], ["c", 0], ["d", 0]]


def test_what_sits_under_a_part_follows_it():
    assert _rows({"order": ["c", "a", "b", "d"], "parent": {"b": "c", "d": "b"}}) == [["c", 0], ["b", 1], ["d", 2], ["a", 0]]


@pytest.mark.parametrize("drag,target,zone,order,parent", [
    ("d", "a", "before", ["d", "a", "b", "c"], {}), ("a", "c", "after", ["b", "c", "a", "d"], {}),
    ("c", "a", "into", ["a", "c", "b", "d"], {"c": "a"})])
def test_where_a_drop_puts_a_part(drag, target, zone, order, parent):
    assert _page(f"return dropped(D, '{drag}', '{target}', '{zone}');") == {"order": order, "parent": parent}


def test_a_drop_beside_a_nested_part_joins_its_level():
    assert _page("return dropped(D, 'd', 'b', 'after');", {"order": list("abcd"), "parent": {"b": "a"}})["parent"] == {"b": "a", "d": "a"}


def test_a_drop_at_the_top_level_comes_out_of_its_parent():
    assert _page("return dropped(D, 'b', 'c', 'after');", {"order": list("abcd"), "parent": {"b": "a"}})["parent"] == {}


@pytest.mark.parametrize("drag,target", [("a", "a"), ("a", "b"), ("a", "c")])
def test_a_part_can_t_go_on_itself_or_inside_itself(drag, target):
    assert _page(f"return {{ r: dropped(D, '{drag}', '{target}', 'into') }};", {"order": list("abcd"), "parent": {"b": "a", "c": "b"}}) == {"r": None}


@pytest.mark.parametrize("y,zone", [(1, "before"), (10, "into"), (19, "after")])
def test_where_on_the_row_says_what_a_drop_does(y, zone):
    assert _page(f"return {{ z: dropZone({{ clientY: {y} }}, {{ getBoundingClientRect: () => ({{ top: 0, height: 20 }}) }}) }};")["z"] == zone


def test_a_part_s_eye_hides_what_sits_under_it():
    assert _page("return underPart(D, 'a');", {"parent": {"b": "a", "c": "b"}}) == ["b", "c"]
    assert "[id, ...underPart(S.design, d.eye)]" in open(JS).read()
