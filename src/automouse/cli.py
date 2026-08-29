from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from automouse.app import append_litter_to_inventory, run_batch
from automouse.config import load_config
from automouse.exceptions import AutoMouseError, DuplicateInputError
from automouse.litter_entry import LitterSubmission
from automouse.transnetyx_validator import validate_transnetyx_csv

# Distinct exit code so callers (scripts, the .command launchers) can tell a
# blocked reprocess of an already-archived file apart from other failures and
# offer an explicit retry, instead of only seeing a generic error.
DUPLICATE_INPUT_EXIT_CODE = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="automouse",
        description=(
            "Translate a Transnetyx CSV, safely update a mouse-inventory copy, "
            "and generate Live Label cage-card data."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/pipeline_run.yaml"),
        help="Configuration path (default: config/pipeline_run.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-input", help="Validate a raw Transnetyx CSV")
    validate.add_argument("input", type=Path)

    for name, help_text in (
        ("translate", "Archive, validate, translate, and validate the R output"),
        ("run", "Execute the complete inventory and cage-card workflow"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "input",
            type=Path,
            nargs="+",
            help="One or more raw Transnetyx CSV files processed as one batch",
        )
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--allow-duplicate-input", action="store_true")
        command.add_argument("--verbose", action="store_true")

    enter_litter = subparsers.add_parser(
        "enter-litter",
        help=(
            "Add one manually-recorded litter (strain, DOB, parents, pup counts, "
            "and mouse ID range) to the inventory as brand-new mice"
        ),
    )
    enter_litter.add_argument("--strain", required=True)
    enter_litter.add_argument("--dob", required=True, help="Date of birth, e.g. 2026-01-19")
    enter_litter.add_argument("--mother", required=True)
    enter_litter.add_argument("--father", required=True)
    enter_litter.add_argument("--total-pups", type=int, required=True)
    enter_litter.add_argument("--female-count", type=int, default=0)
    enter_litter.add_argument("--male-count", type=int, default=0)
    enter_litter.add_argument("--first-mouse-id", required=True)
    enter_litter.add_argument("--last-mouse-id", required=True)
    enter_litter.add_argument("--plate-id", required=True)
    enter_litter.add_argument("--transnetyx-order-date", required=True)
    enter_litter.add_argument("--dry-run", action="store_true")
    enter_litter.add_argument("--verbose", action="store_true")

    serve = subparsers.add_parser(
        "serve", help="Start the local Möuseley Kräs web app (upload files from a browser)"
    )
    serve.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    serve.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser tab automatically",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Möuseley Kräs requires Python 3.11 or later.", file=sys.stderr)
        return 2

    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-input":
            result = validate_transnetyx_csv(args.input, config.transnetyx)
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.valid else 1

        if args.command == "enter-litter":
            submission = LitterSubmission(
                strain=args.strain,
                dob=args.dob,
                mother=args.mother,
                father=args.father,
                total_pups=args.total_pups,
                female_count=args.female_count,
                male_count=args.male_count,
                first_mouse_id=args.first_mouse_id,
                last_mouse_id=args.last_mouse_id,
                plate_id=args.plate_id,
                transnetyx_order_date=args.transnetyx_order_date,
            )
            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                submission, config, dry_run=args.dry_run, verbose=args.verbose
            )
            print(
                json.dumps(
                    {
                        "run_id": run_id,
                        "artifacts": artifacts,
                        "entries": [entry.to_dict() for entry in entries],
                        "warnings": warnings,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "serve":
            try:
                from automouse.web import run_server
            except ImportError:
                print(
                    "The web app requires Flask, which is not installed. "
                    "Install it with: .venv/bin/python -m pip install 'Flask>=3.0'",
                    file=sys.stderr,
                )
                return 2
            run_server(
                config,
                host=args.host,
                port=args.port,
                open_browser=not args.no_browser,
            )
            return 0

        context = run_batch(
            args.input,
            config,
            allow_duplicate_input=args.allow_duplicate_input,
            dry_run=args.dry_run,
            verbose=args.verbose,
            complete_pipeline=args.command == "run",
        )
        print(json.dumps(context.to_summary(), indent=2, sort_keys=True))
        return 0
    except DuplicateInputError as error:
        print(f"Möuseley Kräs error: {error}", file=sys.stderr)
        return DUPLICATE_INPUT_EXIT_CODE
    except AutoMouseError as error:
        print(f"Möuseley Kräs error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Möuseley Kräs was interrupted by the user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
