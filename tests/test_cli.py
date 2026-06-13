"""CALI-8 — CLI: spec round-trip (no kernel) + the M0 one-shot smoke test (needs OCCT)."""

import os

import pytest

from caliper import cli

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "corner_bracket.yaml")


def test_spec_subcommand_round_trips(capsys):
    rc = cli.main(["spec", FIXTURE])
    assert rc == 0
    out = capsys.readouterr().out
    assert "corner_bracket" in out


def test_run_gate_blocks_without_yes_noninteractive(capsys):
    # Ask-don't-assume: non-interactive run without --yes must stop at the clarify gate (rc 2),
    # before any build — so this works even without the geometry kernel.
    rc = cli.main(["run", "a 60 mm bracket with four M5 holes", "--no-llm"])
    assert rc == 2
    assert "re-run with --yes" in capsys.readouterr().out


def test_run_end_to_end_smoke(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.chdir(tmp_path)  # runs/ artifacts land in a temp dir
    rc = cli.main([
        "run", "a 60 mm corner bracket for 2020 extrusion with four M5 holes",
        "--no-llm", "--yes", "--max-iter", "2",
    ])
    assert rc in (0, 3)  # 0 = all pass, 3 = built but not every assertion green
    # an STL must have been produced under runs/
    runs = tmp_path / "runs"
    stls = list(runs.glob("run_*/part.stl"))
    assert stls, "expected an STL artifact"


def test_fit_end_to_end(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    import trimesh

    monkeypatch.chdir(tmp_path)
    assert cli.main(["run", "a 60 mm corner bracket for 2020 extrusion with four M5 holes",
                     "--no-llm", "--yes", "--max-iter", "2"]) in (0, 3)
    # an obstacle that collides with the 60mm flange end → the fit must shrink the bracket to clear it.
    obstacle = tmp_path / "obstacle.stl"
    m = trimesh.creation.box(extents=(20, 24, 8))
    m.apply_translation([52, 0, 2])
    m.export(str(obstacle))
    rc = cli.main(["fit", "runs/run_0000", "--ref", f"obstacle={obstacle}",
                   "--min-clearance", "2", "--max-iter", "6"])
    assert rc == 0  # converged to a clearing fit
    # the fitted spec must carry the reference and a fit assertion, and shrink the bracket.
    from caliper.spec import Spec

    fitted = Spec.load(str(tmp_path / "runs" / "run_0001" / "spec.yaml"))
    assert any(r.id == "obstacle" for r in fitted.references)
    assert any("clearance" in a.id for a in fitted.assertions)
    leg = fitted.parameters["bolt_circle"].init
    assert leg < 60.0  # resized smaller to fit


def test_fit_and_refine_route_authored_through_author_loop(tmp_path, monkeypatch):
    # CALI-22: fit/refine of an LLM-authored part (part.py present) now route through the author loop
    # (seeded with the existing script), revising the REAL part instead of refusing / building a bracket.
    pytest.importorskip("cadquery")
    import trimesh

    import caliper.authoring as authoring

    monkeypatch.chdir(tmp_path)
    box = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(40, 30, 4)\n"
    monkeypatch.setattr(authoring, "author_script",
                        lambda spec, feedback=None, prior=None, client=None, model=None: box)

    d = tmp_path / "runs" / "run_0000"
    d.mkdir(parents=True)
    (d / "spec.yaml").write_text("part: gizmo\n")
    (d / "part.py").write_text(box)
    ref = tmp_path / "ref.stl"
    m = trimesh.creation.box(extents=(10, 10, 10)); m.apply_translation([100, 0, 0]); m.export(str(ref))

    # fit: the part (x∈[-20,20]) already clears the far reference → routes through the author loop, passes
    rc = cli.main(["fit", str(d), "--ref", f"o={ref}", "--no-overlap", "--max-iter", "1"])
    assert rc in (0, 3)
    assert (tmp_path / "runs" / "run_0001" / "part.py").exists()

    # refine: the LLM edits the authored script; instruction is folded into the persisted intent
    rc = cli.main(["refine", str(d), "make it a touch wider", "--max-iter", "1"])
    assert rc in (0, 3)
    new_spec = (tmp_path / "runs" / "run_0002" / "spec.yaml").read_text()
    assert "make it a touch wider" in new_spec


def test_fit_missing_reference_file_returns_2(capsys):
    rc = cli.main(["fit", FIXTURE, "--ref", "obstacle=/nonexistent/obstacle.stl"])
    assert rc == 2
    assert "not found" in capsys.readouterr().out


def test_gen_cli_wires_author_to_build(tmp_path, monkeypatch):
    # CALI-16: `caliper gen` drives intake → authored script → build → measure → persist (part.py).
    # The LLM author is monkeypatched to a known script so this is deterministic + offline.
    pytest.importorskip("cadquery")
    monkeypatch.chdir(tmp_path)
    import caliper.authoring as authoring

    good = "def build(params):\n    import cadquery as cq\n    return cq.Workplane('XY').box(40, 30, 4)\n"
    monkeypatch.setattr(authoring, "author_script",
                        lambda spec, feedback=None, prior=None, client=None, model=None: good)
    rc = cli.main(["gen", "a 40x30x4 mounting plate", "--no-llm", "--yes", "--max-rounds", "1"])
    assert rc in (0, 3)  # built; assertions may or may not all pass against the offline spec
    assert (tmp_path / "runs" / "run_0000" / "part.py").read_text().strip() == good.strip()
    assert (tmp_path / "runs" / "run_0000" / "part.stl").exists()


def test_refine_noop_returns_2(capsys):
    rc = cli.main(["refine", FIXTURE, "paint it a nicer colour", "--no-llm"])
    assert rc == 2
    assert "No recognized refinement" in capsys.readouterr().out


def test_refine_end_to_end(tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["run", "a 60 mm corner bracket with four M5 holes",
                     "--no-llm", "--yes", "--max-iter", "2"]) in (0, 3)
    # refine the run we just produced
    rc = cli.main(["refine", "runs/run_0000", "make the holes 8 mm", "--no-llm", "--max-iter", "2"])
    assert rc in (0, 3)
    stls = sorted((tmp_path / "runs").glob("run_*/part.stl"))
    assert len(stls) >= 2  # original + refined
