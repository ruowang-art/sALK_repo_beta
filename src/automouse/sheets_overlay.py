"""Optional, read-only overlay of DOB/Wean_By values from the primary Google
Sheet inventory, used only to fill in *blank* DOB/Wean_By cells before Live
Label cage cards are built.

This is a narrow, explicitly-scoped exception to the rule that Möuseley Kräs
never reads from or writes to the shared Google Sheet automatically (see
CLAUDE.md): it may fetch exactly two fields (DOB, Wean_By) with a read-only
service-account credential, and it never overwrites a DOB/Wean_By value
already present in the local inventory copy. It never touches genotype
matching, never writes back to the sheet, and any fetch failure degrades to
a run warning rather than failing the batch.
"""

from __future__ import annotations

import logging

from automouse.config import InventoryConfig, SheetsOverlayConfig
from automouse.inventory_manager import InventoryTable

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

_OVERLAY_ROLES = ("dob", "wean_date")


class SheetsOverlayError(Exception):
    """The sheet could not be fetched or parsed. Callers must warn, not fail the run."""


def fetch_dob_wean_overlay(
    config: SheetsOverlayConfig, inventory_config: InventoryConfig
) -> dict[str, dict[str, str]]:
    """Fetch ``{identifier: {"dob": ..., "wean_date": ...}}`` from the sheet.

    Identifiers and the DOB/Wean_By columns are located by matching the
    sheet's header row against ``inventory_config.expected_headers`` — the
    same exact header text already required of the local inventory CSV —
    rather than any position-based or fuzzy lookup.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as error:
        raise SheetsOverlayError(
            "Google Sheets libraries are not installed. Install the 'sheets' "
            "extra (pip install -e '.[sheets]') to use the DOB/Wean_By overlay."
        ) from error

    if config.credentials_file is None or not config.credentials_file.is_file():
        raise SheetsOverlayError(
            f"Service account credentials file not found: {config.credentials_file}"
        )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(config.credentials_file), scopes=[SHEETS_READONLY_SCOPE]
        )
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        response = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=config.spreadsheet_id, range=config.worksheet)
            .execute()
        )
    except SheetsOverlayError:
        raise
    except Exception as error:  # noqa: BLE001 - any transport/auth/API failure must warn, not crash
        raise SheetsOverlayError(f"Could not fetch the Google Sheet: {error}") from error

    rows = response.get("values", [])
    if not rows:
        raise SheetsOverlayError("The Google Sheet returned no rows.")

    header_row = rows[0]
    header_index = {
        str(cell).strip().casefold(): position for position, cell in enumerate(header_row)
    }

    def _column_for(role: str) -> int | None:
        expected = inventory_config.expected_headers.get(role, "")
        if not expected:
            return None
        return header_index.get(expected.strip().casefold())

    role_columns = {role: _column_for(role) for role in _OVERLAY_ROLES}
    if all(column is None for column in role_columns.values()):
        raise SheetsOverlayError(
            "Neither the DOB nor Wean_By header was found in the Google Sheet."
        )

    id_columns = [
        column
        for column in (_column_for(role) for role in inventory_config.identifier_roles)
        if column is not None
    ]
    if not id_columns:
        raise SheetsOverlayError(
            "No identifier column (Mouse/ID/Sample) was found in the Google Sheet."
        )

    overlay: dict[str, dict[str, str]] = {}
    for data_row in rows[1:]:
        role_values = {
            role: data_row[column].strip()
            for role, column in role_columns.items()
            if column is not None and column < len(data_row)
        }
        if not any(role_values.values()):
            continue
        for id_column in id_columns:
            if id_column >= len(data_row):
                continue
            identifier = data_row[id_column].strip()
            if not identifier:
                continue
            entry = overlay.setdefault(identifier, {})
            for role, value in role_values.items():
                if value:
                    entry.setdefault(role, value)
    return overlay


def apply_dob_wean_overlay(
    inventory: InventoryTable,
    overlay: dict[str, dict[str, str]],
    logger: logging.Logger,
    *,
    fill_log: list[str] | None = None,
) -> int:
    """Fill blank DOB/Wean_By cells in ``inventory`` from ``overlay``, in place.

    Never overwrites a value already present in the inventory copy. Returns
    the number of cells filled, for logging/warning purposes. If ``fill_log``
    is provided, one human-readable message per filled cell (identifying the
    mouse ID and field) is appended to it, for run-manifest auditability.
    """
    identifier_index = inventory.identifier_index()
    filled = 0
    for identifier, values in overlay.items():
        for row_index in identifier_index.get(identifier, []):
            mouse_id = (
                inventory.value(row_index, "mouse_id")
                if "mouse_id" in inventory.config.columns
                else ""
            ) or identifier
            for role in _OVERLAY_ROLES:
                sheet_value = values.get(role, "")
                if not sheet_value or inventory.value(row_index, role):
                    continue
                inventory.set_value(row_index, role, sheet_value)
                filled += 1
                if fill_log is not None:
                    fill_log.append(f"{mouse_id}: filled {role} = {sheet_value!r} from Sheets overlay")
    if filled:
        logger.info(
            "Filled %d DOB/Wean_By cell(s) from the Google Sheet overlay.", filled
        )
    return filled
