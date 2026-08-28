"""Local, single-user web interface for Xol-Pots-Xol.

A thin presentation layer over ``xolpotsxol.pipeline.run_consolidation`` —
no matching/consolidation logic lives here. Runs locally
(``127.0.0.1``) for one person at a time, the same way Möuseley Kräs's own
web app does, but this is otherwise an entirely separate tool: it never
touches the inventory, raw Transnetyx files, or the cage-card template.
"""

from __future__ import annotations

import secrets
import shutil
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, abort, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from xolpotsxol.exceptions import XolPotsXolError
from xolpotsxol.pipeline import run_consolidation


def _save_uploads(files: list[Any], directory: Path) -> list[tuple[Path, str]]:
    saved: list[tuple[Path, str]] = []
    for storage in files:
        if not storage or not storage.filename:
            continue
        safe_name = secure_filename(storage.filename) or "cage_cards.xlsx"
        destination = directory / safe_name
        counter = 1
        while destination.exists():
            destination = directory / f"{destination.stem}_{counter}{destination.suffix}"
            counter += 1
        storage.save(destination)
        saved.append((destination, storage.filename))
    return saved


def create_app(runtime_root: Path) -> Flask:
    app = Flask(__name__)
    app.config["RUNTIME_ROOT"] = runtime_root.resolve()
    app.config["RUNTIME_ROOT"].mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index() -> str:
        return render_template("upload.html")

    @app.post("/consolidate")
    def consolidate_route() -> Any:
        uploaded_files = request.files.getlist("cage_card_files")
        if not uploaded_files or all(not item.filename for item in uploaded_files):
            return (
                render_template(
                    "error.html",
                    message="Choose one or more Live Label cage-card workbooks before continuing.",
                ),
                400,
            )

        upload_directory = Path(tempfile.mkdtemp(prefix="xolpotsxol_upload_"))
        saved = _save_uploads(uploaded_files, upload_directory)
        if not saved:
            shutil.rmtree(upload_directory, ignore_errors=True)
            return render_template("error.html", message="No usable files were uploaded."), 400

        run_id = secrets.token_urlsafe(8)
        output_directory = app.config["RUNTIME_ROOT"] / run_id
        output_path = output_directory / "consolidated_cage_cards.xlsx"

        try:
            result, read_warnings = run_consolidation(saved, output_path)
        except XolPotsXolError as error:
            shutil.rmtree(upload_directory, ignore_errors=True)
            return render_template("error.html", message=str(error)), 422
        finally:
            shutil.rmtree(upload_directory, ignore_errors=True)

        preserved_cage_count = len(
            {mouse.source_cage_key for mouse in result.unconsolidated_mice}
        )
        download_url = url_for(
            "download", run_id=run_id, filename="consolidated_cage_cards.xlsx"
        )
        return render_template(
            "result.html",
            input_cage_count=result.input_cage_count,
            input_mouse_count=result.input_mouse_count,
            consolidated_cage_count=len(result.consolidated_cages),
            preserved_cage_count=preserved_cage_count,
            warnings=read_warnings + result.warnings,
            download_url=download_url,
        )

    @app.get("/download/<run_id>/<filename>")
    def download(run_id: str, filename: str) -> Any:
        root = app.config["RUNTIME_ROOT"]
        candidate = (root / run_id / filename).resolve()
        if candidate != root and not candidate.is_relative_to(root):
            abort(404)
        if not candidate.is_file():
            abort(404)
        return send_file(candidate, as_attachment=True)

    return app


def run_server(
    runtime_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    open_browser: bool = True,
) -> None:
    app = create_app(runtime_root)
    url = f"http://{host}:{port}/"
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Xol-Pots-Xol web app running at {url} (press Ctrl+C to stop)")
    app.run(host=host, port=port, debug=False, use_reloader=False)
