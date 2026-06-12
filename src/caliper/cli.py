"""CALI-8 — the Caliper CLI: the M0 one-shot, end to end.

    caliper run "a 60mm corner bracket for 2020 extrusion with four M5 holes"

drives intent → spec → build → measure → report → STL through the loop controller. ``--no-llm`` uses
the deterministic offline intake so demos and the smoke test are reproducible without a network/key.
"""

from __future__ import annotations

import argparse
import os
import sys


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from a `.env` file (cwd, then repo root) without overriding the shell.

    Lets you keep ANTHROPIC_API_KEY / CALIPER_MODEL in a gitignored `.env` instead of exporting them.
    No dependency — a tiny parser; values already in the environment win.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for path in (os.path.join(os.getcwd(), ".env"), os.path.join(repo_root, ".env")):
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)


def _next_run_dir(base: str = "runs") -> str:
    os.makedirs(base, exist_ok=True)
    n = len([d for d in os.listdir(base) if d.startswith("run_")])
    return os.path.join(base, f"run_{n:04d}")


def _cmd_spec(args) -> int:
    from .spec import Spec

    print(Spec.load(args.path).to_yaml())
    return 0


def _cmd_run(args) -> int:
    from .intake import draft_spec

    print(f"▶ intent: {args.intent}\n")
    intake_res = draft_spec(args.intent, machine=args.machine, use_llm=not args.no_llm)
    print(f"── draft spec ({intake_res.source}) ──")
    if not args.no_llm and intake_res.source == "offline":
        print("  (LLM path unavailable — used offline. Set ANTHROPIC_API_KEY, or CALIPER_DEBUG=1 for why.)")
    print(intake_res.spec.to_yaml())

    # Ask-don't-assume gate (design spec §5): stop for confirmation before building.
    if intake_res.needs_confirmation:
        print("── clarifying questions ──")
        for q in intake_res.questions:
            print(f"  • {q}")
        if not args.yes:
            if sys.stdin.isatty():
                ans = input("\nProceed with the assumptions above? [y/N] ").strip().lower()
                if ans not in ("y", "yes"):
                    print("Aborted — refine the intent and re-run.")
                    return 2
            else:
                print("\nNon-interactive: re-run with --yes to accept the assumptions and build.")
                return 2
        print()

    return _run_and_emit(intake_res.spec, args.max_iter)


def _run_and_emit(spec, max_iter: int, references=None) -> int:
    """Run the loop on a spec, print the report, and emit STL + run dir. Shared by run/refine/fit."""
    from . import generate
    from .loop import make_eval_fn, persist_run, run_loop

    print("── running loop (build → measure → evaluate → decide) ──")
    result = run_loop(spec, make_eval_fn(references=references), max_iter=max_iter)
    print(f"\nstatus: {result.status}  ({result.iterations} iteration(s))")
    print(result.report.to_text())

    build = generate.build(result.spec)
    out_dir = _next_run_dir()
    persist_run(out_dir, result.spec, result.report, build.geometry if build.build_ok else None)
    if not build.build_ok:
        print(f"\nbuild failed:\n{build.error}")
        return 1
    print(f"\nSTL: {os.path.join(out_dir, 'part.stl')}")
    print(f"run saved: {out_dir}")
    return 0 if result.status == "passed" else 3


def _load_spec_from_source(source: str):
    """Load a spec from a run dir (``runs/run_0000``) or a spec file (``spec.yaml``/``.json``)."""
    from .spec import Spec

    if os.path.isdir(source):
        source = os.path.join(source, "spec.yaml")
    return Spec.load(source)


def _cmd_refine(args) -> int:
    from .refine import apply_refinement

    spec = _load_spec_from_source(args.source)
    print(f"▶ refining {args.source}: \"{args.instruction}\"\n")
    res = apply_refinement(spec, args.instruction, use_llm=not args.no_llm)
    if not res.changed:
        hint = "" if args.no_llm else " (LLM path needs ANTHROPIC_API_KEY; CALIPER_DEBUG=1 shows why)"
        print("No recognized refinement — try naming a dimension (holes, spacing, wall, "
              f"cable bore, ribs), or use the LLM path for free-form edits.{hint}")
        return 2
    print(f"── changes ({res.source}) ──")
    for c in res.changes:
        print(f"  • {c}")
    print()
    return _run_and_emit(res.spec, args.max_iter)


def _pick_free_param(spec) -> str | None:
    from .decide import FIT_PARAM_PREFERENCE

    for name in FIT_PARAM_PREFERENCE:
        if name in spec.parameters:
            return name
    return next(iter(spec.parameters), None)


def _ensure_tunable(spec, name: str) -> str | None:
    """Make ``name`` a continuous parameter so the optimizer can resize the part to fit.

    A fit needs a free dimension; intake often locks the bracket size as ``fixed``. Promote it to a
    continuous range around its current value (shrink to clear, room to grow) without touching the
    rest of the spec.
    """
    from .spec import ContinuousParam

    if not name or name not in spec.parameters:
        return None
    prm = spec.parameters[name]
    if getattr(prm, "type", None) == "continuous":
        return name
    v = float(getattr(prm, "init", getattr(prm, "value", 60.0)) or 60.0)
    spec.parameters[name] = ContinuousParam(
        min=max(8.0, round(v * 0.3, 1)), max=round(v * 1.5, 1), init=v,
        unit=getattr(prm, "unit", None) or "mm",
    )
    return name


def _cmd_fit(args) -> int:
    """Attach imported STL reference(s) to a prior part and iterate it to fit them (CALI-10)."""
    from .measure import Geometry
    from .spec import Assertion, Reference

    spec = _load_spec_from_source(args.source)
    # default constraint: if none specified, enforce no collision with the reference.
    no_overlap = args.no_overlap or args.min_clearance is None
    references: dict = {}
    summary: list[str] = []
    for item in args.ref:
        rid, _, path = item.partition("=")
        rid, path = rid.strip(), path.strip()
        if not rid or not path:
            print(f"bad --ref {item!r}; expected ID=path/to/reference.stl")
            return 2
        if not os.path.isfile(path):
            print(f"reference file not found: {path}")
            return 2
        abspath = os.path.abspath(path)
        spec.references = [r for r in spec.references if r.id != rid]  # replace same-id
        spec.references.append(Reference(id=rid, file=abspath))
        references[rid] = Geometry.from_stl(abspath)
        # drop any prior fit assertions for this id, then add the requested ones
        spec.assertions = [a for a in spec.assertions if not a.id.startswith(f"{rid}_")]
        if no_overlap:
            spec.assertions.append(Assertion(id=f"{rid}_no_interference", expr=f"interference({rid}) <= 0"))
        if args.min_clearance is not None:
            spec.assertions.append(
                Assertion(id=f"{rid}_clearance", expr=f"min_clearance({rid}) >= {args.min_clearance}")
            )
        summary.append(f"{rid} ← {path}")

    if not references:
        print("no references given; use --ref ID=path/to/reference.stl (repeatable)")
        return 2
    free = _ensure_tunable(spec, args.free or _pick_free_param(spec))
    print(f"▶ fitting {args.source} to: {', '.join(summary)}")
    if free:
        p = spec.parameters[free]
        print(f"  free dimension: {free} ∈ [{p.min:g}, {p.max:g}] mm (optimizer resizes to fit)\n")
    else:
        print("  (warning: no continuous parameter to vary — the fit can't resize the part)\n")
    print(f"── fit constraints ──")
    for a in spec.assertions:
        if any(a.id.endswith(s) for s in ("_no_interference", "_clearance")):
            print(f"  • {a.id}: {a.expr}")
    print()
    return _run_and_emit(spec, args.max_iter, references=references)


def _cmd_serve(args) -> int:
    from .server import serve

    print(f"▶ Caliper webapp on http://{args.host}:{args.port}  (Ctrl-C to stop)")
    serve(host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="caliper", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    p_spec = sub.add_parser("spec", help="load a spec file and echo it back (round-trip check)")
    p_spec.add_argument("path")
    p_spec.set_defaults(func=_cmd_spec)

    p_run = sub.add_parser("run", help="intent → spec → build → measure → report → STL")
    p_run.add_argument("intent")
    p_run.add_argument("--machine", default="generic")
    p_run.add_argument("--no-llm", action="store_true", help="use deterministic offline intake")
    p_run.add_argument("--yes", action="store_true", help="accept intake assumptions without prompting")
    p_run.add_argument("--max-iter", type=int, default=4)
    p_run.set_defaults(func=_cmd_run)

    p_ref = sub.add_parser("refine", help="apply a natural-language change to a prior run/spec, re-run")
    p_ref.add_argument("source", help="a run dir (runs/run_0000) or a spec file (.yaml/.json)")
    p_ref.add_argument("instruction", help='e.g. "make the holes 8mm" or "bigger spacing"')
    p_ref.add_argument("--no-llm", action="store_true", help="use the deterministic offline refiner")
    p_ref.add_argument("--max-iter", type=int, default=4)
    p_ref.set_defaults(func=_cmd_refine)

    p_fit = sub.add_parser("fit", help="fit a prior part to imported STL reference(s) (interference/clearance)")
    p_fit.add_argument("source", help="a run dir (runs/run_0000) or a spec file (.yaml/.json)")
    p_fit.add_argument("--ref", action="append", default=[], metavar="ID=FILE.stl",
                       help="attach a reference STL as role:fixed (repeatable)")
    p_fit.add_argument("--min-clearance", type=float, default=None, metavar="MM",
                       help="require min_clearance(ref) >= MM for each reference")
    p_fit.add_argument("--no-overlap", action="store_true",
                       help="require interference(ref) <= 0 for each reference (no collision)")
    p_fit.add_argument("--free", default=None, metavar="PARAM",
                       help="parameter the optimizer may resize to fit (default: auto-pick a size param)")
    p_fit.add_argument("--max-iter", type=int, default=6)
    p_fit.set_defaults(func=_cmd_fit)

    p_serve = sub.add_parser("serve", help="launch the webapp (3D viewer + spec/report + refine)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
