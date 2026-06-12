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
    from . import generate
    from .intake import draft_spec
    from .loop import make_eval_fn, persist_run, run_loop

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

    print("── running loop (build → measure → evaluate → decide) ──")
    result = run_loop(intake_res.spec, make_eval_fn(), max_iter=args.max_iter)
    print(f"\nstatus: {result.status}  ({result.iterations} iteration(s))")
    print(result.report.to_text())

    # rebuild the final spec to emit geometry + STL
    build = generate.build(result.spec)
    out_dir = _next_run_dir()
    persist_run(out_dir, result.spec, result.report, build.geometry if build.build_ok else None)
    if build.build_ok:
        stl = os.path.join(out_dir, "part.stl")
        print(f"\nSTL: {stl}")
        print(f"run saved: {out_dir}")
    else:
        print(f"\nbuild failed:\n{build.error}")
        return 1
    return 0 if result.status == "passed" else 3


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

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
