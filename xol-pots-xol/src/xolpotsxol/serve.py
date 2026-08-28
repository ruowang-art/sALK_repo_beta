"""Entry point for ``python -m xolpotsxol.serve`` / the ``xolpotsxol-serve``
console script — starts the local web app.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from xolpotsxol.web import run_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xolpotsxol-serve", description="Start the Xol-Pots-Xol web app.")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path.cwd() / "xolpotsxol_runtime",
        help="Where generated consolidated workbooks are written (default: ./xolpotsxol_runtime)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    run_server(
        args.runtime_root, host=args.host, port=args.port, open_browser=not args.no_browser
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
