from __future__ import annotations

import argparse
import sys
from pathlib import Path

from xolpotsxol.consolidator import DEFAULT_FEMALE_DOB_WINDOW_DAYS, DEFAULT_MALE_DOB_WINDOW_DAYS
from xolpotsxol.exceptions import XolPotsXolError
from xolpotsxol.pipeline import run_consolidation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xolpotsxol",
        description=(
            "Consolidate sparse Live Label cage-card workbooks (produced by "
            "Möuseley Kräs) into fuller cages, up to 5 mice each."
        ),
    )
    parser.add_argument(
        "cage_card_files", nargs="+", type=Path, help="One or more Live Label .xlsx files"
    )
    parser.add_argument("--output", type=Path, required=True, help="Path to write the result to")
    parser.add_argument("--male-dob-window-days", type=int, default=DEFAULT_MALE_DOB_WINDOW_DAYS)
    parser.add_argument(
        "--female-dob-window-days", type=int, default=DEFAULT_FEMALE_DOB_WINDOW_DAYS
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        uploaded = [(path, path.name) for path in args.cage_card_files]
        result, read_warnings = run_consolidation(
            uploaded,
            args.output,
            male_dob_window_days=args.male_dob_window_days,
            female_dob_window_days=args.female_dob_window_days,
        )
    except XolPotsXolError as error:
        print(f"Xol-Pots-Xol error: {error}", file=sys.stderr)
        return 1
    except FileExistsError as error:
        print(f"Xol-Pots-Xol error: {error}", file=sys.stderr)
        return 1

    preserved_cage_count = len({mouse.source_cage_key for mouse in result.unconsolidated_mice})
    print(f"Read {result.input_mouse_count} mice from {result.input_cage_count} input cage(s).")
    print(
        f"Wrote {len(result.consolidated_cages)} consolidated cage(s) and "
        f"{preserved_cage_count} preserved (unconsolidated) cage(s) to {args.output}"
    )
    for warning in read_warnings + result.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
