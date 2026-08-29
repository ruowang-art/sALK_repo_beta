from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from xolpotsxol.models import EXPECTED_HEADERS
from xolpotsxol.web import create_app


def _build_workbook_bytes(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(EXPECTED_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


_ROW_TEMPLATE = [
    "", "Kras/Lkb1", 1, 1, "Male", "02/16/26", "01/19/26",
    "CM0001", "", "", "", "", "+/+", "", "", "", "",
    "", "", "", "", "", "",
]


class WebAppTests(unittest.TestCase):
    def test_index_renders_upload_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            client = create_app(Path(directory_name)).test_client()
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn('name="cage_card_files"', response.get_data(as_text=True))

    def test_consolidate_without_files_is_a_friendly_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            client = create_app(Path(directory_name)).test_client()
            response = client.post(
                "/consolidate", data={}, content_type="multipart/form-data"
            )
            self.assertEqual(response.status_code, 400)

    def test_consolidate_then_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            client = create_app(Path(directory_name)).test_client()
            file_bytes = _build_workbook_bytes([_ROW_TEMPLATE])
            response = client.post(
                "/consolidate",
                data={"cage_card_files": (io.BytesIO(file_bytes), "cards.xlsx")},
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn("Download consolidated workbook", body)

            import re

            match = re.search(r'href="(/download/[^"]+)"', body)
            self.assertIsNotNone(match)
            download_response = client.get(match.group(1))
            try:
                self.assertEqual(download_response.status_code, 200)
                self.assertGreater(len(download_response.data), 0)
            finally:
                # Must close before the `with` block above tears down
                # directory_name: addCleanup would defer this past the end
                # of the test method, after that teardown already ran. On
                # Windows, deleting a directory that still has an open file
                # handle inside it raises PermissionError (WinError 32);
                # POSIX allows it silently, which is why this was invisible
                # until a real Windows run (Phase 4) exercised it.
                download_response.close()

    def test_bad_workbook_format_is_a_clear_error_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            client = create_app(Path(directory_name)).test_client()
            workbook = Workbook()
            workbook.active.append(["Not", "A", "Cage", "Card"])
            buffer = io.BytesIO()
            workbook.save(buffer)
            response = client.post(
                "/consolidate",
                data={"cage_card_files": (io.BytesIO(buffer.getvalue()), "bad.xlsx")},
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 422)
            self.assertIn("does not look like", response.get_data(as_text=True))

    def test_download_rejects_paths_outside_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            secret = root.parent / "outside.txt"
            secret.write_text("do not serve me", encoding="utf-8")
            client = create_app(root).test_client()
            response = client.get("/download/../outside.txt")
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
