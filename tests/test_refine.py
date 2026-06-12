"""CALI-1.M1 — refinement: NL change → mutated spec (params + assertions in sync) → re-derive."""

import pytest

from caliper import intake, refine


def _base(with_cable=True):
    intent = "a 60 mm corner bracket for 2020 extrusion with four M5 holes"
    if with_cable:
        intent += " and a cable pass-through"
    return intake.offline_draft(intent).spec


def _get(spec, name):
    p = spec.parameters[name]
    return getattr(p, "init", getattr(p, "value", None))


def test_resize_holes_updates_param_and_assertion():
    r = refine.offline_refine(_base(), "make the holes 8 mm")
    assert r.changed
    assert _get(r.spec, "hole_d") == 8.0
    bolt = next(a for a in r.spec.assertions if a.id == "bolt_pattern")
    assert "diameter=8" in bolt.expr  # assertion re-synced to the new geometry


def test_m_size_holes():
    r = refine.offline_refine(_base(), "switch to M6 holes")
    assert _get(r.spec, "hole_d") == 6.6  # M6 clearance
    assert _get(r.spec, "hole_count") == 4  # 'M6 holes' is NOT read as '6 holes'


def test_bigger_spacing_is_relative():
    r = refine.offline_refine(_base(), "make the holes 8 mm bigger spacing")
    assert _get(r.spec, "bolt_circle") == 68.0  # 60 + 8, spacing takes priority over diameter


def test_set_spacing_absolute():
    r = refine.offline_refine(_base(), "set the bolt spacing to 75 mm")
    assert _get(r.spec, "bolt_circle") == 75.0


def test_hole_count_change():
    r = refine.offline_refine(_base(), "use 6 holes instead")
    assert _get(r.spec, "hole_count") == 6
    bolt = next(a for a in r.spec.assertions if a.id == "bolt_pattern")
    assert "count=6" in bolt.expr


def test_one_hole_per_side_is_two_total():
    r = refine.offline_refine(_base(), "only do one hole on each side, directly in the middle")
    assert r.changed
    assert _get(r.spec, "hole_count") == 2  # 1 per flange × 2 flanges
    bolt = next(a for a in r.spec.assertions if a.id == "bolt_pattern")
    assert "count=2" in bolt.expr
    assert any("centred" in c for c in r.changes)


def test_word_number_and_per_side_count():
    r = refine.offline_refine(_base(), "put three holes per leg")
    assert _get(r.spec, "hole_count") == 6  # three per leg × 2


def test_thicker_walls_relative():
    r = refine.offline_refine(_base(), "make the walls thicker")
    assert _get(r.spec, "wall") == 4.0  # 3 + 1


def test_wall_absolute():
    r = refine.offline_refine(_base(), "set the wall to 4.5 mm")
    assert _get(r.spec, "wall") == 4.5


def test_add_rib():
    r = refine.offline_refine(_base(), "add a stiffening rib")
    assert _get(r.spec, "rib_count") == 1


def test_add_cable_bore_when_missing():
    r = refine.offline_refine(_base(with_cable=False), "add a 12 mm cable pass-through")
    assert _get(r.spec, "cable_bore") == 12.0
    assert any(a.id == "cable_fits" for a in r.spec.assertions)  # assertion added too


def test_no_recognized_change_is_a_noop():
    r = refine.offline_refine(_base(), "make it look nicer please")
    assert not r.changed


def test_llm_failure_falls_back_to_offline():
    class Boom:
        class messages:
            @staticmethod
            def create(**_):
                raise RuntimeError("no network")

    r = refine.apply_refinement(_base(), "make the holes 8 mm", use_llm=True, client=Boom())
    assert r.source == "offline"
    assert _get(r.spec, "hole_d") == 8.0


# --- end-to-end: the refinement flows all the way to the mesh (needs OCCT) ---
def test_refinement_changes_the_geometry():
    pytest.importorskip("cadquery")
    from caliper import generate, measure

    spec = _base(with_cable=False)
    built = generate.build(spec)
    assert built.build_ok and measure.holes_matching(built.geometry, diameter=5.2, count=4)

    refined = refine.offline_refine(spec, "make the holes 8 mm").spec
    rebuilt = generate.build(refined)
    assert rebuilt.build_ok, rebuilt.error
    eight = [h for h in measure.holes(rebuilt.geometry) if abs(h.diameter - 8.0) <= 0.3]
    assert len(eight) == 4  # the part actually changed
