"""Command-line entry point: `python -m app.cli <command>`.

`seed` is filled in by P04 (synthetic dataset + demo users); `backup` by P22.
The surface exists now so the Makefile targets and deploy scripts are stable.
"""

from __future__ import annotations

import argparse


def cmd_seed(_: argparse.Namespace) -> int:
    print("Demo seeding is not implemented yet: the dataset generator lands in P04.")
    return 0


def cmd_backup(_: argparse.Namespace) -> int:
    print("Backup is not implemented yet: the SQLite .backup command lands in P22.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relayops", description="RelayOps maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed", help="load the demo project, users and artifacts")
    seed.set_defaults(func=cmd_seed)

    backup = subparsers.add_parser("backup", help="take a consistent copy of the SQLite database")
    backup.set_defaults(func=cmd_backup)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
