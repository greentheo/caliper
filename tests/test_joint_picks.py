"""CALI-178 (#222 slice D): the designer's joint rules, the shop's joint tools, and a pick that names a joint.

1. The shop knows a table saw, a pocket-hole jig and a doweling jig, and which joints each makes; the round fails a joint the
   shop can't make, and names what it needs.
2. The designer's guide carries the JOINTS rules (§3), and its prompt says which joints this shop can make.
3. A picked edge on the seam where two pieces meet is "the joint between the side and the top"; "make that a rabbet" is
   told to the designer as that pair's entry, and checked: landed, missed or couldn't tell.
Synthetic parts and a scratch shop, never Theo's.
"""

import numpy as np
import pytest

from caliper import joints, shop

T, H, W, D, K = 19.05, 400.0, 400.0, 300.0, 6.35

#: A side under a top, the side's top edge against the top's underside: the inside corner is a seam.
CORNER = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 400.0, "d": 300.0, "h": 400.0, "into": 0.0}
JOINTS_LINE


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    top = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h - t))
    side = cq.Workplane().box(t, d, h - t + p["into"], centered=False)
    return top.union(side)


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h, k = p["t"], p["w"], p["d"], p["h"], p["into"]
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h - t + k), (0, 0, h - t + k)]},
            {"name": "top", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]}]
'''


def _script(joint=None, into=0.0):
    line = f"JOINTS = [{{'pieces': ['side', 'top'], 'kind': '{joint}', 'fix': ['glue', 'screws']}}]" if joint else ""
    return CORNER.replace("JOINTS_LINE", line).replace('"into": 0.0', f'"into": {into}')


def _store(tmp_path, script):
    pytest.importorskip("cadquery")
    from caliper.design import DesignStore

    s = DesignStore.create("a corner", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a side under a top")
    return s


@pytest.fixture
def tools(tmp_path, monkeypatch):
    """A scratch shop with what's asked for."""
    def make(*hand, machines=()):
        p = tmp_path / "shop.yaml"
        import yaml

        p.write_text(yaml.safe_dump({"hand": list(hand), "machines": [{"id": m, "kind": m} for m in machines]}))
        monkeypatch.setenv("CALIPER_SHOP", str(p))
        return shop.read()
    return make


# --- 1: the shop's joint tools ---------------------------------------------------------------------------------------------
def test_the_shop_knows_the_joint_tools():
    for tool in ("table saw", "pocket-hole jig", "doweling jig"):
        assert tool in shop.HAND and shop.HAND[tool], tool


def test_which_joints_a_shop_can_make(tools):
    plain = tools("jigsaw", "drill", "circular saw")
    assert shop.joint_kinds(plain) == ["butt", "bevel", "mitre", "glue block", "through tenon", "notch"]
    assert shop.joint_needs("rabbet", plain) == "a table saw or a router"
    assert shop.joint_needs("pocket screw", plain) == "a pocket-hole jig"
    assert shop.joint_needs("dowel", plain) == "a doweling jig"
    assert shop.joint_needs("printed connector", plain) == "a 3D printer"
    assert shop.joint_needs("butt", plain) is None and shop.joint_needs("glue block", plain) is None
    full = tools("jigsaw", "drill", "circular saw", "table saw", "pocket-hole jig", "doweling jig", machines=("printer",))
    assert all(shop.joint_needs(k, full) is None for k in joints.KINDS)
    assert shop.joint_needs("dado", tools("drill", machines=("router",))) is None           # a router does it too
    assert shop.joint_needs("bevel", tools("drill")) == "a circular saw or a table saw"


def test_the_round_fails_a_joint_the_shop_can_t_make(tools, tmp_path):
    from caliper import construction as C
    from caliper.design import DesignStore

    script = _script("rabbet", into=K)
    s = DesignStore.create("a corner", base=str(tmp_path / "d"))
    s.write_part("stool", script, intent="x")
    mesh, declared = s.part_geometry("stool").require_mesh(), C.declared(s, "stool")
    tools("jigsaw", "drill", "circular saw")
    (got,) = [r for r in joints.check(script, declared, mesh) if r.id == "joints"]
    assert not got.passed and ("JOINTS makes the side and the top a rabbet, which needs a table saw or a router, and "
                               "your shop hasn't got one") in got.detail, got.detail
    tools("jigsaw", "drill", "circular saw", "table saw")
    (got,) = [r for r in joints.check(script, declared, mesh) if r.id == "joints"]
    assert got.passed, got.detail


# --- 2: the designer -------------------------------------------------------------------------------------------------------
def test_the_designer_s_guide_has_the_joint_rules(tools):
    from caliper import authoring

    tools("jigsaw", "drill", "circular saw")
    prompt = authoring.system_prompt()
    assert "## How its pieces join: JOINTS" in prompt
    rules = prompt[prompt.index("## How its pieces join: JOINTS"):]
    order = ["Bearing first", "Sideways load through face glue", "Never pull a screw out of an edge",
             "A splay or a rack needs a tie", "The shop decides what's possible"]
    at = [rules.index(r) for r in order]
    assert at == sorted(at), at
    assert "a dado would carry this in glue; it needs a router or table saw" in rules
    assert "## Your shop" in prompt and "Joints it can make: butt, bevel, mitre, glue block, through tenon, notch." in prompt
    assert "Not without another tool: rabbet and dado (a table saw or a router)" in prompt


def test_the_prompt_follows_the_shop(tools):
    from caliper import authoring

    tools("jigsaw", "drill", "circular saw", "table saw", "pocket-hole jig")
    prompt = authoring.system_prompt()
    assert "Joints it can make: butt, bevel, mitre, rabbet, dado, pocket screw, glue block, through tenon, notch." in prompt


# --- 3: a pick names a joint -----------------------------------------------------------------------------------------------
def test_a_point_on_the_seam_names_the_joint(tmp_path):
    s = _store(tmp_path, _script())
    name = joints.namer(s, "stool")
    got = name((T, D / 2, H - T))                                                    # the inside corner
    assert got == {"pieces": ["side", "top"], "said": "the joint between the side and the top", "kind": "butt"}, got
    assert name((W / 2, D / 2, H)) is None                                           # the top's own face: no seam
    assert name((T / 2, D / 2, 100.0)) is None


def test_the_seam_s_edge_is_said_as_the_joint(tmp_path):
    from caliper import features

    s = _store(tmp_path, _script())
    got = features.with_words(features.for_part(s, "stool"), False, joint=joints.namer(s, "stool"))
    seam = [e for e in got["edges"] if np.allclose(e["local"], (T, D / 2, H - T), atol=0.6)]
    assert len(seam) == 1 and seam[0]["said"].startswith("joint between the side and the top: "), seam
    assert seam[0]["joint"]["pieces"] == ["side", "top"]
    assert not any(e["said"].startswith("joint") for e in got["edges"] if e is not seam[0])


def test_the_kind_a_request_asks_for():
    assert joints.asked_kind("make that a rabbet") == "rabbet"
    assert joints.asked_kind("About this joint: use a dado here") == "dado"
    assert joints.asked_kind("pocket holes please") == "pocket screw"
    assert joints.asked_kind("make it a miter") == "mitre"
    assert joints.asked_kind("glue block it") == "glue block"
    assert joints.asked_kind("fillet this 3 mm") is None


def test_the_designer_is_told_which_entry(tmp_path):
    s = _store(tmp_path, _script())
    joint = joints.namer(s, "stool")((T, D / 2, H - T))
    said = joints.focus(joint, "rabbet", (T, D / 2, H - T))
    assert ("The picked edge is the joint between the side and the top. Make that joint a rabbet: set its JOINTS entry, "
            "pieces [\"side\", \"top\"], to \"kind\": \"rabbet\" with \"at\": (19.05, 150.0, 380.95)") in said, said
    assert "cut the step into the piece whose face the other's edge meets" in said


@pytest.mark.parametrize("after, asked, landed, words", [
    (_script("rabbet", into=K), "rabbet", True, "Checked: the joint between the side and the top is now a rabbet, 1/4 in deep."),
    (_script(), "rabbet", False, "The joint between the side and the top is still a butt (assumed): its JOINTS entry didn't change."),
    # #285 review: the pieces show no step, or the entry is another kind: a miss, never "couldn't tell"
    (_script("rabbet"), "rabbet", False, "Its JOINTS entry says rabbet, but the pieces show no step: neither runs "
                                                  "into the other."),
    (_script("dowel"), "rabbet", False, "Its JOINTS entry now says dowel, not rabbet."),
    # a kind the pieces can't show here: said as the entry only, never "Checked"
    (_script("bevel"), "bevel", None, "Its JOINTS entry now says bevel: the shape isn't checked here."),
], ids=["landed", "missed", "no step", "another kind", "unmeasured"])
def test_did_it_land(after, asked, landed, words, tmp_path):
    s = _store(tmp_path, after)
    pick_joint = {"pieces": ["side", "top"], "said": "the joint between the side and the top", "kind": "butt"}
    got = joints.landed(_script(), after, s, "stool", pick_joint, asked, inches=True)
    assert got["landed"] == landed and words in got["said"], got
    assert ("Checked" in got["said"]) == (landed is True)


def test_the_turn_tells_the_designer_and_checks_it(tmp_path, tools):
    from caliper import chat, features

    tools("jigsaw", "drill", "circular saw", "table saw")
    s = _store(tmp_path, _script())
    seam = next(e for e in features.for_part(s, "stool")["edges"] if np.allclose(e["local"], (T, D / 2, H - T), atol=0.6))
    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return _script("rabbet", into=K)
    got = chat.refine_part(s, "stool", "About this joint between the side and the top: make that a rabbet", author=author,
                           use_llm=False, max_rounds=1, promote_feedback=False,
                           pick={"kind": "edge", "id": seam["id"], "text": "make that a rabbet"})
    assert any("Make that joint a rabbet: set its JOINTS entry" in f for f in seen), seen
    # the design's own units: this one is in millimetres
    assert got.ok and "Checked: the joint between the side and the top is now a rabbet, 6 mm deep." in got.reply, got.reply
    assert "Its shape didn't change" not in got.reply, got.reply                     # the same solid: a rabbet lands in it


def test_a_missed_joint_fails_the_turn(tmp_path, tools):
    from caliper import chat, features

    tools("jigsaw", "drill", "circular saw", "table saw")
    s = _store(tmp_path, _script())
    seam = next(e for e in features.for_part(s, "stool")["edges"] if np.allclose(e["local"], (T, D / 2, H - T), atol=0.6))
    got = chat.refine_part(s, "stool", "About this joint between the side and the top: make that a rabbet",
                           author=lambda sp, f, p: _script().replace("PARAMS = {", "# a rabbet, honest\nPARAMS = {"),
                           use_llm=False, max_rounds=1, promote_feedback=False,
                           pick={"kind": "edge", "id": seam["id"], "text": "make that a rabbet"})
    assert not got.ok and got.reply.startswith("✗ The joint between the side and the top is still a butt"), got.reply


def test_the_app_s_pick_chip_names_the_joint(tmp_path, monkeypatch):
    """The features route the viewport picks from says the seam's edge as its joint, so the chip and the request do."""
    import os

    from fastapi.testclient import TestClient

    from caliper.server import create_app

    s = _store(tmp_path, _script())
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(s.root))
    got = TestClient(create_app()).get(f"/api/designs/{os.path.basename(s.root)}/parts/stool/features.json").json()
    seam = [e for e in got["edges"] if np.allclose(e["local"], (T, D / 2, H - T), atol=0.6)]
    assert len(seam) == 1 and seam[0]["said"].startswith("joint between the side and the top: "), seam


#: The corner with a front rail under the top, against the side: three pieces meet at one corner.
RAILED = CORNER.replace('''    return top.union(side)''', '''    rail = cq.Workplane().box(w - t, t, 100.0, centered=False).translate((t, 0, h - t - 100.0))
    return top.union(side).union(rail)''').replace('''             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]}]''',
                                               '''             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]},
            {"name": "rail", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(t, 0, h - t - 100.0), (w, 0, h - t - 100.0), (w, 0, h - t), (t, 0, h - t)]}]''').replace(
    "JOINTS_LINE", "")


def test_a_corner_where_three_pieces_meet_is_no_one_joint(tmp_path):
    assert RAILED.count("rail") >= 3
    name = joints.namer(_store(tmp_path, RAILED), "stool")
    assert name((T, T, H - T)) is None                                               # side, top and rail all meet here
    assert name((T, D / 2, H - T))["pieces"] == ["side", "top"]                       # along the seam, away from the rail



def _turn(s, edge, words, script):
    from caliper import chat

    seen = []

    def author(spec, feedback, prior):
        seen.append(feedback)
        return script
    got = chat.refine_part(s, "stool", f"About this {words}", author=author, use_llm=False, max_rounds=1,
                           promote_feedback=False, pick={"kind": "edge", "id": edge["id"], "text": words})
    return got, seen


def _edge_at(s, at):
    from caliper import features

    return next(e for e in features.for_part(s, "stool")["edges"] if np.allclose(e["local"], at, atol=0.6))


def test_no_step_is_a_miss_and_the_turn_says_so(tmp_path, tools):
    tools("jigsaw", "drill", "circular saw", "table saw")
    s = _store(tmp_path, _script())
    got, _ = _turn(s, _edge_at(s, (T, D / 2, H - T)), "make that a rabbet", _script("rabbet"))
    assert not got.ok and got.reply.startswith("✗ Its JOINTS entry says rabbet, but the pieces show no step"), got.reply


def test_an_unmeasured_kind_is_said_as_the_entry_never_checked(tmp_path, tools):
    tools("jigsaw", "drill", "circular saw")
    s = _store(tmp_path, _script())
    got, _ = _turn(s, _edge_at(s, (T, D / 2, H - T)), "make that a bevel", _script("bevel"))
    assert "Its JOINTS entry now says bevel: the shape isn't checked here." in got.reply and "Checked:" not in got.reply


def test_an_outside_corner_on_a_flush_seam_asks_for_the_inside_corner(tmp_path, tools):
    """#285 review: the top's end and the side's face are one face, so the flush seam has no edge; the outside corner next to
    it named nothing, and the turn read ✓ "couldn't tell". It says where the joint is, and asks."""
    tools("jigsaw", "drill", "circular saw", "table saw")
    s = _store(tmp_path, _script())
    got, seen = _turn(s, _edge_at(s, (0.0, D / 2, H)), "make that a rabbet", _script("rabbet", into=K))
    assert not seen, seen                                                            # the designer isn't asked: nothing changes
    assert not got.ok and got.version is None
    assert ("That edge is the top's outside corner, not where two pieces meet. The joint between the side and the top is "
            "where they meet inside: pick that inside corner, or name the pieces (\"the joint between the side and the "
            "top\").") in got.reply, got.reply
    assert "couldn't tell" not in got.reply


def test_an_edge_with_no_joint_near_it_goes_the_ordinary_way(tmp_path, tools):
    from caliper import features

    tools("jigsaw", "drill", "circular saw", "table saw")
    s = _store(tmp_path, _script())
    far = _edge_at(s, (W, D / 2, H))                                                 # the top's far end: no piece near it
    got, seen = _turn(s, far, "make that a rabbet", _script())
    assert seen and features.NOT_MEASURED in got.reply
