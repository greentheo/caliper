"""CALI-28 — the Design object + store.

The container for "the thing I am building": root prompt, clarified requirements, a part tree, and
per-part feedback history. Most of this is deliberately CadQuery-free so the regression guard stays
fast; the two tests that prove a design *measures* like an ordinary assembly are OCCT-gated.
"""

import json
import os

import pytest

from caliper.assembly import Assembly, Mate
from caliper.design import Design, DesignStore, slugify
from caliper.spec import Assertion, Spec

BOX_PY = (
    "def build(params):\n"
    "    import cadquery as cq\n"
    "    return cq.Workplane('XY').box({dx}, 20, 10)\n"
)


def _script(dx=40):
    return BOX_PY.format(dx=dx)


@pytest.fixture
def store(tmp_path):
    return DesignStore.create("a 3D printer gantry, 300x300x400 build volume",
                              base=str(tmp_path / "designs"))


# --- slugs + creation ------------------------------------------------------
def test_slugify_is_filesystem_safe_and_bounded():
    assert slugify("A 3D Printer Gantry!") == "a-3d-printer-gantry"
    assert slugify("   ") == "design"
    assert "/" not in slugify("a/b\\c") and len(slugify("x" * 200)) <= 48


def test_create_lays_out_the_directory_and_seeds_both_records(store):
    assert os.path.isdir(os.path.join(store.root, "parts"))
    assert os.path.exists(store.design_path) and os.path.exists(store.assembly_path)
    assert store.design.prompt.startswith("a 3D printer gantry")
    # a design IS an assembly — the engine can consume it with no design-specific code
    assert isinstance(store.assembly, Assembly) and store.assembly.parts == []
    assert store.log()[0]["kind"] == "created"


def test_slug_collisions_resolve_deterministically(tmp_path):
    base = str(tmp_path / "designs")
    a = DesignStore.create("gantry", base=base)
    b = DesignStore.create("gantry", base=base)
    c = DesignStore.create("gantry", base=base)
    assert [a.design.slug, b.design.slug, c.design.slug] == ["gantry", "gantry-2", "gantry-3"]
    assert a.root != b.root != c.root


# --- round-trip ------------------------------------------------------------
def test_design_round_trips_losslessly():
    d = Design(slug="g", name="Gantry", prompt="a gantry", machine="ender3")
    assert Design.from_yaml(d.to_yaml()) == d
    assert Design.from_json(d.to_json()) == d


def test_load_reads_back_everything_that_was_written(store):
    store.add_requirement("extrusion profile?", "2040 V-slot")
    store.write_part("carriage", _script(), intent="the X carriage")
    again = DesignStore.load(store.root)
    assert again.design.requirements[0].answer == "2040 V-slot"
    assert again.design.part("carriage").intent == "the X carriage"
    assert [p.id for p in again.assembly.parts] == ["carriage"]
    # loadable by slug from the designs dir too
    by_slug = DesignStore.load(store.design.slug, base=os.path.dirname(store.root))
    assert by_slug.design.slug == store.design.slug


def test_list_designs_summarises_newest_first(tmp_path):
    base = str(tmp_path / "designs")
    DesignStore.create("first", base=base)
    second = DesignStore.create("second", base=base)
    second.add_requirement("q", "a")                       # bumps `updated`
    listed = DesignStore.list_designs(base=base)
    assert [d["slug"] for d in listed] == ["second", "first"]
    assert listed[0]["parts"] == 0
    # a junk directory must not sink the listing
    os.makedirs(os.path.join(base, "not-a-design"), exist_ok=True)
    assert len(DesignStore.list_designs(base=base)) == 2


# --- requirements ----------------------------------------------------------
def test_requirements_are_upserted_not_duplicated(store):
    store.add_requirement("rail type?", "MGN12")
    store.add_requirement("rail type?", "MGN15")
    assert len(store.design.requirements) == 1
    assert store.design.requirements[0].answer == "MGN15"


def test_assumptions_are_marked_as_such(store):
    store.add_requirement("belt or leadscrew?", "belt", source="assumed")
    assert "[assumed]" in store.prompt_context()


# --- versioning ------------------------------------------------------------
def test_write_part_snapshots_every_revision_and_never_overwrites(store):
    v1 = store.write_part("carriage", _script(40), intent="the X carriage")
    v2 = store.write_part("carriage", _script(50), feedback="make it wider", action="refine")
    assert (v1, v2) == (1, 2)
    assert store.versions("carriage") == [1, 2]
    # the canonical script is the latest; the snapshots keep the earlier one recoverable
    assert "50" in store.read_script("carriage")
    with open(os.path.join(store.version_dir("carriage", 1), "part.py")) as f:
        assert "40" in f.read()
    assert store.design.part("carriage").version == 2
    assert [p.source for p in store.assembly.parts] == [os.path.join("parts", "carriage", "part.py")]


def test_restore_rolls_back_as_a_new_revision(store):
    store.write_part("carriage", _script(40))
    store.write_part("carriage", _script(50))
    v3 = store.restore("carriage", 1)
    assert v3 == 3 and "40" in store.read_script("carriage")
    assert store.history("carriage")[-1]["restored_from"] == 1   # the rollback is itself history


def test_report_is_snapshotted_with_the_revision(store):
    store.write_part("carriage", _script(), report={"all_pass": False, "results": []})
    with open(os.path.join(store.version_dir("carriage", 1), "report.json")) as f:
        assert json.load(f)["all_pass"] is False
    assert store.history("carriage")[-1]["result"] == "fail"


def test_part_ids_must_be_identifiers(store):
    for bad in ["../escape", "has space", "9lives", ""]:
        with pytest.raises(ValueError):
            store.write_part(bad, _script())


# --- history + log ---------------------------------------------------------
def test_history_is_append_only_and_records_the_feedback_that_caused_a_change(store):
    store.write_part("carriage", _script(40), intent="the X carriage")
    store.write_part("carriage", _script(50), feedback="needs to clear the rail",
                     action="refine", measured={"min_clearance(rail)": {"before": 0.4, "after": 1.6}})
    hist = store.history("carriage")
    assert [h["action"] for h in hist] == ["author", "refine"]
    assert hist[1]["feedback"] == "needs to clear the rail"
    assert hist[1]["measured"]["min_clearance(rail)"]["after"] == 1.6
    assert all("ts" in h and h["part"] == "carriage" for h in hist)


def test_a_torn_history_line_does_not_make_the_history_unreadable(store):
    store.write_part("carriage", _script())
    with open(store.history_path("carriage"), "a") as f:
        f.write('{"kind": "revision", trunc')      # simulate a crash mid-append
    assert len(store.history("carriage")) == 1     # the good line still reads


# --- spec / assertion surface (what CALI-30 will promote into) -------------
def test_spec_can_be_updated_without_cutting_a_geometry_revision(store):
    spec = Spec(part="carriage", intent="the X carriage")
    store.write_part("carriage", _script(), spec=spec)
    spec.assertions.append(Assertion(id="clears_rail", expr="bbox.dx <= 60"))
    store.write_spec("carriage", spec)
    assert store.design.part("carriage").version == 1          # no new revision
    assert [a.id for a in store.read_spec("carriage").assertions] == ["clears_rail"]


# --- prompt context --------------------------------------------------------
def test_prompt_context_carries_requirements_parts_mates_and_distilled_history(store):
    store.add_requirement("extrusion profile?", "2040 V-slot")
    store.write_part("carriage", _script(), intent="the X carriage")
    store.write_part("rail", _script(), intent="the linear rail")
    store.write_part("carriage", _script(50), feedback="needs to clear the rail", action="refine")
    store.assembly.mates.append(Mate(id="carriage_on_rail", between=["carriage", "rail"],
                                     kind="no_interference"))
    spec = Spec(part="carriage", intent="x",
                assertions=[Assertion(id="clears_rail", expr="bbox.dx <= 60")])
    store.write_spec("carriage", spec)

    ctx = store.prompt_context("carriage")
    assert "2040 V-slot" in ctx                                  # clarified once, permanent
    assert "the linear rail" in ctx                              # knows what else exists
    assert "carriage_on_rail" in ctx                             # knows what must keep holding
    assert "clears_rail: bbox.dx <= 60" in ctx                   # the enforced residue
    assert "needs to clear the rail" in ctx                      # the narrative
    assert "<- the part in question" in ctx                      # scope is explicit


def test_prompt_context_history_is_bounded(store):
    store.write_part("carriage", _script())
    for i in range(20):
        store.write_part("carriage", _script(), feedback=f"tweak {i}", action="refine")
    ctx = store.prompt_context("carriage", history_limit=3)
    assert "tweak 19" in ctx and "tweak 0" not in ctx


# --- adopting an existing run ---------------------------------------------
def test_adopt_run_keeps_an_authored_script_revisable(store, tmp_path):
    run = tmp_path / "run_0001"
    run.mkdir()
    (run / "part.py").write_text(_script(33))
    (run / "spec.yaml").write_text(Spec(part="p", intent="adopted").to_yaml())
    store.adopt_run(str(run), "adopted_part", intent="from an old run")
    assert store.design.part("adopted_part").origin == "adopted"
    assert "33" in store.read_script("adopted_part")
    # and it keeps revising like any other design part
    assert store.write_part("adopted_part", _script(44), action="refine") == 2


def test_adopt_run_without_a_script_is_marked_imported(store, tmp_path):
    run = tmp_path / "run_0002"
    run.mkdir()
    (run / "part.stl").write_text("solid x\nendsolid x\n")
    store.adopt_run(str(run), "legacy", intent="template bracket")
    entry = store.design.part("legacy")
    assert entry.origin == "imported"
    # honest: the assembly points at the run dir because there's no script to revise
    assert [p.source for p in store.assembly.parts] == [str(run)]
    assert "no part.py" in store.history("legacy")[-1]["note"]


def test_adopt_run_rejects_an_empty_run(store, tmp_path):
    empty = tmp_path / "run_0003"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        store.adopt_run(str(empty), "nope")


# --- a design measures like an ordinary assembly (OCCT-gated) -------------
def test_single_part_design_evaluates_through_evaluate_assembly(store):
    pytest.importorskip("cadquery")
    store.write_part("carriage", _script(40), intent="the X carriage")
    store.assembly.assertions.append(Assertion(id="nothing_collides",
                                               expr="max_interference() <= 0"))
    store.save()
    report = store.evaluate()
    assert report.all_pass                       # one part can't collide with itself


def test_a_revision_is_measured_not_cached(store):
    """The rewrite must invalidate the build cache — otherwise a re-measure 'proves' the old part."""
    pytest.importorskip("cadquery")
    from caliper.assembly import load_parts
    from caliper.measure import bounding_box

    store.write_part("carriage", _script(40))
    assert bounding_box(load_parts(store.assembly, base_dir=store.root)["carriage"]).dx == \
        pytest.approx(40, abs=0.1)
    store.write_part("carriage", _script(80), feedback="twice as wide", action="refine")
    assert bounding_box(load_parts(store.assembly, base_dir=store.root)["carriage"]).dx == \
        pytest.approx(80, abs=0.1)


def test_a_broken_part_is_named_not_fatal(store):
    """CALI-27's discipline, inherited: one bad part must not sink the whole design."""
    pytest.importorskip("cadquery")
    store.write_part("good", _script(40))
    store.write_part("bad", "def build(params):\n    raise RuntimeError('boom')\n")
    report, errors = store.evaluate(tolerant=True)
    assert "bad" in errors and "boom" in errors["bad"]
    assert "good" not in errors


def test_prompt_context_carries_design_rules_that_involve_the_part(store):
    """CALI-30 promotes cross-part rules onto the assembly; the author has to SEE them."""
    store.write_part("carriage", _script(), intent="the X carriage")
    store.write_part("rail", _script(), intent="the rail")
    store.assembly.assertions.append(
        Assertion(id="carriage_clears_rail", expr="min_clearance(carriage, rail) >= 2.0"))
    store.assembly.assertions.append(
        Assertion(id="foot_height", expr="bbox(foot).dz <= 10"))
    store.save()

    ctx = store.prompt_context("carriage")
    assert "DESIGN RULES IN FORCE" in ctx
    assert "carriage_clears_rail: min_clearance(carriage, rail) >= 2.0" in ctx
    assert "foot_height" not in ctx            # not about this part — don't crowd the prompt
