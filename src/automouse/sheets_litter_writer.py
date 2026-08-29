"""Optional write-back of newly entered litters to the primary Google Sheet
inventory, used only by the Mouse Inventory Update (litter entry) portal.

This is a separate, narrower opt-in from the read-only DOB/Wean_By overlay in
``sheets_overlay.py`` (``sheets_overlay.write_new_litters``, off by default,
requires ``sheets_overlay.enabled`` as well — see CLAUDE.md and
``config.validate_config``). It requests its own read-write-scoped
credential from the same service-account key file, rather than reusing the
overlay's read-only-scoped one, so the DOB/Wean_By read path can never write
regardless of how this flag is set.

Conflict handling: immediately before appending, the sheet's current
identifier column(s) are re-fetched and checked against the litter's mouse
IDs, since another lab member may be editing the live sheet concurrently.
Any collision is reported to the caller as an existing identifier, never
written past — the same "never overwrite, only report" rule this project
applies everywhere else. Any other failure (network, auth, quota, a missing
identifier column) raises :class:`SheetsLitterWriteError`; callers must
treat that as "the local inventory copy was updated, the sheet was not" and
turn it into a run warning, never a fatal error for the whole litter.
"""

from __future__ import annotations

from dataclasses import dataclass

from automouse.config import InventoryConfig, SheetsOverlayConfig

SHEETS_READWRITE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class SheetsLitterWriteError(Exception):
    """The sheet could not be checked or written to. Callers must warn, not fail the run."""


@dataclass(slots=True)
class SheetState:
    header_row: list[str]
    existing_identifiers: set[str]


def _build_service(config: SheetsOverlayConfig):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as error:
        raise SheetsLitterWriteError(
            "Google Sheets libraries are not installed. Install the 'sheets' "
            "extra (pip install -e '.[sheets]') to write new litters to the Sheet."
        ) from error

    if config.credentials_file is None or not config.credentials_file.is_file():
        raise SheetsLitterWriteError(
            f"Service account credentials file not found: {config.credentials_file}"
        )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(config.credentials_file), scopes=[SHEETS_READWRITE_SCOPE]
        )
        return build("sheets", "v4", credentials=credentials, cache_discovery=False)
    except Exception as error:  # noqa: BLE001 - any auth/transport failure must warn, not crash
        raise SheetsLitterWriteError(f"Could not authenticate to the Google Sheet: {error}") from error


def fetch_sheet_state(config: SheetsOverlayConfig, inventory_config: InventoryConfig) -> SheetState:
    """Fetch the sheet's header row and every non-blank value currently in
    its identifier column(s) (Mouse/ID/Sample, located by header text, same
    as ``inventory_config.identifier_roles`` everywhere else in this
    project). Used immediately before an append, to catch a mouse ID added
    to the live sheet by hand since Möuseley Kräs last read it.
    """
    service = _build_service(config)
    try:
        response = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=config.spreadsheet_id, range=config.worksheet)
            .execute()
        )
    except Exception as error:  # noqa: BLE001 - any transport/API failure must warn, not crash
        raise SheetsLitterWriteError(f"Could not fetch the Google Sheet: {error}") from error

    rows = response.get("values", [])
    if not rows:
        raise SheetsLitterWriteError("The Google Sheet returned no rows.")

    header_row = [str(cell) for cell in rows[0]]
    header_index = {cell.strip().casefold(): position for position, cell in enumerate(header_row)}

    id_columns = [
        header_index[expected.strip().casefold()]
        for role in inventory_config.identifier_roles
        if (expected := inventory_config.expected_headers.get(role, ""))
        and expected.strip().casefold() in header_index
    ]
    if not id_columns:
        raise SheetsLitterWriteError(
            "No identifier column (Mouse/ID/Sample) was found in the Google Sheet; "
            "cannot safely check for conflicts before writing."
        )

    existing_identifiers: set[str] = set()
    for data_row in rows[1:]:
        for column in id_columns:
            if column < len(data_row):
                value = data_row[column].strip()
                if value:
                    existing_identifiers.add(value)

    return SheetState(header_row=header_row, existing_identifiers=existing_identifiers)


def append_litter_rows_to_sheet(
    config: SheetsOverlayConfig,
    inventory_config: InventoryConfig,
    sheet_state: SheetState,
    mice: list[dict[str, str]],
) -> None:
    """Append one row per mouse in ``mice`` (each a ``{role: value}`` dict,
    e.g. ``{"mouse_id": ..., "strain": ..., "dob": ..., "sex": ...}``) to the
    live sheet, aligned to its actual column order via
    ``inventory_config.expected_headers`` — never by position. A role with
    no matching header in the sheet is silently left blank for that column,
    the same permissive behavior the read overlay already uses. Raises
    :class:`SheetsLitterWriteError` on any failure; nothing is partially
    written from the caller's point of view (the Sheets API append call
    itself is one atomic request).
    """
    if not mice:
        return

    header_index = {
        cell.strip().casefold(): position for position, cell in enumerate(sheet_state.header_row)
    }
    if "mouse_id" not in inventory_config.expected_headers or (
        inventory_config.expected_headers["mouse_id"].strip().casefold() not in header_index
    ):
        raise SheetsLitterWriteError(
            "No Mouse ID column was found in the Google Sheet; refusing to append rows "
            "that could land in the wrong place."
        )

    role_columns = {
        role: header_index[expected.strip().casefold()]
        for role, expected in inventory_config.expected_headers.items()
        if expected.strip().casefold() in header_index
    }
    width = len(sheet_state.header_row)

    values: list[list[str]] = []
    for mouse in mice:
        row = [""] * width
        for role, value in mouse.items():
            column = role_columns.get(role)
            if column is not None and value:
                row[column] = value
        values.append(row)

    service = _build_service(config)
    try:
        service.spreadsheets().values().append(
            spreadsheetId=config.spreadsheet_id,
            range=config.worksheet,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
    except Exception as error:  # noqa: BLE001 - any transport/API failure must warn, not crash
        raise SheetsLitterWriteError(f"Could not write to the Google Sheet: {error}") from error
