"""Caliper CLI. M0 end-to-end (CALI-8) lands here; for now a thin entry point."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="caliper", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    p_spec = sub.add_parser("spec", help="load a spec file and echo it back (round-trip check)")
    p_spec.add_argument("path")

    args = parser.parse_args(argv)

    if args.cmd == "spec":
        from .spec import Spec

        spec = Spec.load(args.path)
        print(spec.to_yaml())
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
