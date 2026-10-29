"""Command line: python -m mta run [options]"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import Settings
from .pipeline import QualityGateError, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mta", description="Multi-touch marketing attribution pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Generate (if needed), load, attribute, check and report")
    p.add_argument("--regenerate", action="store_true", help="Regenerate synthetic raw data")
    p.add_argument("--users", type=int, default=50_000)
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lookback-days", type=int, default=30)
    p.add_argument("--half-life-days", type=float, default=7.0)
    p.add_argument("--data-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)

    args = parser.parse_args(argv)
    settings = Settings(lookback_days=args.lookback_days, time_decay_half_life_days=args.half_life_days)
    if args.data_dir:
        settings.data_dir = args.data_dir
    if args.output_dir:
        settings.output_dir = args.output_dir

    print("Running attribution pipeline")
    try:
        result = run(settings, regenerate=args.regenerate, users=args.users, days=args.days,
                     start=args.start, seed=args.seed)
    except QualityGateError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1
    print(f"\nReport: {result['files']['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
