"""CALI-8 — the Caliper CLI: the M0 one-shot, end to end.

    caliper run "a 60mm corner bracket for 2020 extrusion with four M5 holes"

drives intent → spec → build → measure → report → STL through the loop controller. ``--no-llm`` uses
the deterministic offline intake so demos and the smoke test are reproducible without a network/key.
"""

from __future__ import annotations

import argparse
import os
import sys


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


def _run_and_emit(spec, max_iter: int) -> int:
    """Run the loop on a spec, print the report, and emit STL + run dir. Shared by run/refine."""
    from . import generate
    from .loop import make_eval_fn, persist_run, run_loop

    print("── running loop (build → measure → evaluate → decide) ──")
    result = run_loop(spec, make_eval_fn(), max_iter=max_iter)
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
        print("No recognized refinement — try naming a dimension (holes, spacing, wall, "
              "cable bore, ribs), or run with the LLM path for free-form edits.")
        return 2
    print(f"── changes ({res.source}) ──")
    for c in res.changes:
        print(f"  • {c}")
    print()
    return _run_and_emit(res.spec, args.max_iter)


def main(argv: list[str] | None = None) -> int:
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

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
