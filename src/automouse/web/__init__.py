"""Local, single-user web interface for Möuseley Kräs.

This is a thin presentation layer over ``automouse.app.run_batch``: it does
not implement any matching, translation, or inventory-safety logic of its
own. It exists so lab staff can run Möuseley Kräs from a browser instead of
the Terminal, without changing any of the underlying data-safety guarantees.

The server is meant to be started locally (``127.0.0.1``) for one person at
a time; it is not designed or hardened for multi-user or network exposure.
"""

from __future__ import annotations

import secrets
import shutil
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from automouse.app import append_litter_to_inventory, run_batch
from automouse.config import AppConfig
from automouse.exceptions import AutoMouseError, DuplicateInputError
from automouse.litter_entry import LitterSubmission


@dataclass(slots=True)
class PendingUpload:
    """An upload awaiting an explicit decision after a duplicate-input block."""

    directory: Path
    file_paths: list[Path]
    dry_run: bool


class PendingUploadStore:
    """In-memory registry of uploads awaiting a duplicate-input confirmation.

    Möuseley Kräs's web app is single-user and local, so a process-lifetime
    dictionary keyed by a random token is sufficient. Entries are removed as
    soon as they are resolved (confirmed or cancelled), so no upload, and no
    copy of a raw file, outlives its decision.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, PendingUpload] = {}

    def add(self, upload: PendingUpload) -> str:
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._pending[token] = upload
        return token

    def pop(self, token: str) -> PendingUpload | None:
        with self._lock:
            return self._pending.pop(token, None)


_DOWNLOAD_LABELS: dict[str, str] = {
    "updated_inventory_file": "Updated inventory copy",
    "inventory_backup_file": "Inventory backup",
    "exception_report_file": "Exception workbook",
    "audit_file": "Audit log (CSV)",
    "cage_card_file": "Live Label cage-card workbook",
    "run_summary_file": "Run summary (JSON)",
    "log_file": "Run log",
}


def _save_uploads(files: list[Any], directory: Path) -> list[Path]:
    saved: list[Path] = []
    for storage in files:
        if not storage or not storage.filename:
            continue
        safe_name = secure_filename(storage.filename) or "upload.csv"
        destination = directory / safe_name
        counter = 1
        while destination.exists():
            destination = directory / f"{destination.stem}_{counter}{destination.suffix}"
            counter += 1
        storage.save(destination)
        saved.append(destination)
    return saved


def _cleanup(directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)


def _download_links(artifacts: dict[str, str], config: AppConfig) -> list[dict[str, str]]:
    root = config.runtime_root.resolve()
    links: list[dict[str, str]] = []
    for key, label in _DOWNLOAD_LABELS.items():
        value = artifacts.get(key)
        if not value:
            continue
        path = Path(value).resolve()
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        links.append(
            {
                "label": label,
                "url": url_for("download", relative_path=relative.as_posix()),
                "name": path.name,
            }
        )
    return links


def create_app(config: AppConfig) -> Flask:
    app = Flask(__name__)
    app.config["AUTOMOUSE_CONFIG"] = config
    app.config["PENDING_UPLOADS"] = PendingUploadStore()
    # This secret only signs Flask's own flash/session plumbing for one local
    # process lifetime; it never needs to be stable across restarts.
    app.secret_key = secrets.token_hex(32)

    @app.context_processor
    def inject_inventory_source_link() -> dict[str, str]:
        # Convenience link only: Möuseley Kräs never reads from or writes to this
        # sheet automatically. Only render it if it looks like a real link,
        # so a blank/misconfigured value never renders as a dead or unsafe href.
        url = config.inventory.source_sheet_url.strip() if config.inventory else ""
        if not url.startswith(("http://", "https://")):
            url = ""
        return {"inventory_source_url": url}

    @app.get("/")
    def index() -> str:
        return render_template("upload.html")

    @app.post("/run")
    def run() -> Any:
        uploaded_files = request.files.getlist("raw_files")
        dry_run = request.form.get("dry_run") == "on"
        if not uploaded_files or all(not item.filename for item in uploaded_files):
            return (
                render_template(
                    "error.html",
                    message="Choose at least one raw Transnetyx CSV file before running Möuseley Kräs.",
                ),
                400,
            )

        directory = Path(tempfile.mkdtemp(prefix="automouse_upload_"))
        saved_paths = _save_uploads(uploaded_files, directory)
        if not saved_paths:
            _cleanup(directory)
            return render_template("error.html", message="No usable files were uploaded."), 400

        try:
            context = run_batch(
                saved_paths,
                config,
                dry_run=dry_run,
                complete_pipeline=True,
            )
        except DuplicateInputError as error:
            token = app.config["PENDING_UPLOADS"].add(
                PendingUpload(directory=directory, file_paths=saved_paths, dry_run=dry_run)
            )
            return render_template(
                "confirm_duplicate.html",
                message=str(error),
                token=token,
                file_names=[path.name for path in saved_paths],
            )
        except AutoMouseError as error:
            _cleanup(directory)
            return render_template("error.html", message=str(error)), 422

        _cleanup(directory)
        return render_template(
            "results.html",
            summary=context.to_summary(),
            downloads=_download_links(context.artifacts, config),
        )

    @app.post("/run/confirm")
    def confirm() -> Any:
        token = request.form.get("token", "")
        pending = app.config["PENDING_UPLOADS"].pop(token)
        if pending is None:
            return (
                render_template(
                    "error.html",
                    message=(
                        "This confirmation has expired or was already used. "
                        "Please choose the file(s) again."
                    ),
                ),
                410,
            )
        try:
            context = run_batch(
                pending.file_paths,
                config,
                dry_run=pending.dry_run,
                allow_duplicate_input=True,
                complete_pipeline=True,
            )
        except AutoMouseError as error:
            return render_template("error.html", message=str(error)), 422
        else:
            return render_template(
                "results.html",
                summary=context.to_summary(),
                downloads=_download_links(context.artifacts, config),
            )
        finally:
            _cleanup(pending.directory)

    @app.post("/run/cancel")
    def cancel() -> Any:
        token = request.form.get("token", "")
        pending = app.config["PENDING_UPLOADS"].pop(token)
        if pending is not None:
            _cleanup(pending.directory)
        return redirect(url_for("index"))

    @app.get("/download/<path:relative_path>")
    def download(relative_path: str) -> Any:
        root = config.runtime_root.resolve()
        candidate = (root / relative_path).resolve()
        if candidate != root and not candidate.is_relative_to(root):
            abort(404)
        if not candidate.is_file():
            abort(404)
        return send_file(candidate, as_attachment=True)

    @app.get("/inventory")
    def inventory_upload() -> str:
        known_strains = config.inventory.known_strains if config.inventory else ()
        return render_template("inventory_upload.html", known_strains=known_strains)

    @app.post("/inventory/submit")
    def inventory_submit() -> Any:
        form = request.form

        def _int_field(name: str) -> int:
            raw = (form.get(name) or "").strip()
            try:
                return int(raw)
            except ValueError:
                raise AutoMouseError(f"{name.replace('_', ' ').title()} must be a whole number.")

        def _required_field(name: str, label: str) -> str:
            value = (form.get(name) or "").strip()
            if not value:
                raise AutoMouseError(f"{label} is required.")
            return value

        try:
            total_pups = _int_field("total_pups")
            female_count = _int_field("female_count") if form.get("female_count") else 0
            male_count = _int_field("male_count") if form.get("male_count") else 0
            submission = LitterSubmission(
                strain=(form.get("strain") or "").strip(),
                dob=(form.get("dob") or "").strip(),
                mother=(form.get("mother") or "").strip(),
                father=(form.get("father") or "").strip(),
                total_pups=total_pups,
                female_count=female_count,
                male_count=male_count,
                first_mouse_id=(form.get("first_mouse_id") or "").strip(),
                last_mouse_id=(form.get("last_mouse_id") or "").strip(),
                plate_id=_required_field("plate_id", "Plate ID"),
                transnetyx_order_date=_required_field(
                    "transnetyx_order_date", "Transnetyx Order Date"
                ),
            )
            dry_run = form.get("dry_run") == "on"
            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                submission, config, dry_run=dry_run
            )
        except AutoMouseError as error:
            return render_template("error.html", message=str(error)), 422

        return render_template(
            "inventory_result.html",
            run_id=run_id,
            entries=entries,
            dry_run=dry_run,
            downloads=_download_links(artifacts, config),
            warnings=warnings,
        )

    return app


def run_server(
    config: AppConfig,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    app = create_app(config)
    url = f"http://{host}:{port}/"
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Möuseley Kräs web app running at {url} (press Ctrl+C to stop)")
    app.run(host=host, port=port, debug=False, use_reloader=False)
