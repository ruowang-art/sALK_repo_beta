from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from automouse.config import (
    AppConfig,
    CageCardConfig,
    InventoryConfig,
    RConfig,
    TransnetyxConfig,
    TranslationConfig,
)
from automouse.models import RRunResult
from automouse.web import create_app


FIXTURES = Path(__file__).parent / "fixtures"

_TEMPLATE_HEADERS = (
    "Experiment URL", "Strain", "# IN CAGE", "# IN LITTER", "SEX",
    "DATE WEANED", "DATE BORN", "MOUSE 1", "MOUSE 2", "MOUSE 3",
    "MOUSE 4", "MOUSE 5", "MOUSE 1 GENOTYPE", "MOUSE 2 GENOTYPE",
    "MOUSE 3 GENOTYPE", "MOUSE 4 GENOTYPE", "MOUSE 5 GENOTYPE",
    "DAM", "DAM GENOTYPE", "SIRE", "SIRE GENOTYPE", "BREEDER? (B)",
    "Set up date",
)


def _fake_translation(input_path: Path, output_path: Path, *_: object, **__: object) -> RRunResult:
    output_path.write_bytes((FIXTURES / "translated_valid.csv").read_bytes())
    return RRunResult([], 0, "", "", output_path, 0.01)


class WebAppTests(unittest.TestCase):
    def _make_config(
        self, root: Path, source_sheet_url: str = "", *, append_only: bool = False
    ) -> AppConfig:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "master.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for index, value in {
            1: "Mouse", 4: "Strain", 5: "Cage", 6: "Revised Strain",
            13: "ID", 14: "Mother", 15: "Father", 16: "DOB", 17: "Sex",
            18: "Wean_By", 20: "Sample", 21: "Genotype",
        }.items():
            headers[index - 1] = value
        rows = []
        for mouse in ("CM0001", "CM0002"):
            row = [""] * 21
            row[0] = mouse
            row[3] = "Kras"
            row[12] = mouse
            row[19] = mouse
            rows.append(row)
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)

        template_path = root / "template.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet.append(_TEMPLATE_HEADERS)
        workbook.save(template_path)

        return AppConfig(
            project_root=root,
            runtime_root=root / "runtime",
            application_version="test",
            r=RConfig(executable, translation, wrapper),
            transnetyx=TransnetyxConfig(),
            translation=TranslationConfig(),
            inventory=InventoryConfig(
                file=inventory_path,
                append_only=append_only,
                columns={
                    "mouse_id": 1, "strain": 4, "cage_id": 5,
                    "revised_strain": 6, "id": 13, "mother": 14,
                    "father": 15, "dob": 16, "sex": 17, "wean_date": 18,
                    "sample": 20, "genotype": 21,
                },
                expected_headers={
                    "mouse_id": "Mouse", "strain": "Strain", "cage_id": "Cage",
                    "revised_strain": "Revised Strain", "id": "ID",
                    "mother": "Mother", "father": "Father", "dob": "DOB",
                    "sex": "Sex", "wean_date": "Wean_By", "sample": "Sample",
                    "genotype": "Genotype",
                },
                source_sheet_url=source_sheet_url,
            ),
            cage_card=CageCardConfig(
                template=template_path,
                expected_headers=_TEMPLATE_HEADERS,
            ),
        )

    def test_index_renders_accessible_upload_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            client = create_app(config).test_client()
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn('<html lang="en">', body)
            self.assertIn('for="raw_files"', body)
            self.assertIn('name="raw_files"', body)
            self.assertIn("Skip to main content", body)

    def test_inventory_source_link_shown_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(
                Path(directory_name),
                source_sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
            )
            client = create_app(config).test_client()
            body = client.get("/").get_data(as_text=True)
            self.assertIn("https://docs.google.com/spreadsheets/d/abc123/edit", body)
            self.assertIn('target="_blank"', body)
            self.assertIn('rel="noopener noreferrer"', body)

    def test_inventory_source_link_absent_when_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            client = create_app(config).test_client()
            body = client.get("/").get_data(as_text=True)
            self.assertNotIn("docs.google.com", body)
            self.assertNotIn("primary mouse inventory", body)

    def test_run_with_no_file_selected_shows_friendly_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            client = create_app(config).test_client()
            response = client.post("/run", data={}, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertIn("Choose at least one", response.get_data(as_text=True))

    def test_successful_run_shows_summary_and_download_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            client = create_app(config).test_client()
            raw_bytes = (FIXTURES / "raw_valid.csv").read_bytes()

            with patch("automouse.app.run_r_translation", side_effect=_fake_translation):
                response = client.post(
                    "/run",
                    data={
                        "raw_files": (io.BytesIO(raw_bytes), "raw_valid.csv"),
                    },
                    content_type="multipart/form-data",
                )

            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn("Run ", body)
            self.assertIn("Raw records read", body)
            self.assertIn("/download/", body)

    def test_duplicate_input_offers_confirmation_then_allows_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            app = create_app(config)
            client = app.test_client()
            raw_bytes = (FIXTURES / "raw_valid.csv").read_bytes()

            with patch("automouse.app.run_r_translation", side_effect=_fake_translation):
                first = client.post(
                    "/run",
                    data={"raw_files": (io.BytesIO(raw_bytes), "raw_valid.csv")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(first.status_code, 200)

                second = client.post(
                    "/run",
                    data={"raw_files": (io.BytesIO(raw_bytes), "raw_valid.csv")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(second.status_code, 200)
                second_body = second.get_data(as_text=True)
                self.assertIn("already processed", second_body)
                self.assertEqual(len(app.config["PENDING_UPLOADS"]._pending), 1)
                token = next(iter(app.config["PENDING_UPLOADS"]._pending))
                self.assertIn(f'value="{token}"', second_body)

                confirmed = client.post("/run/confirm", data={"token": token})
                self.assertEqual(confirmed.status_code, 200)
                self.assertIn("Raw records read", confirmed.get_data(as_text=True))
                self.assertEqual(app.config["PENDING_UPLOADS"]._pending, {})

    def test_duplicate_input_cancel_discards_the_pending_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            app = create_app(config)
            client = app.test_client()
            raw_bytes = (FIXTURES / "raw_valid.csv").read_bytes()

            with patch("automouse.app.run_r_translation", side_effect=_fake_translation):
                client.post(
                    "/run",
                    data={"raw_files": (io.BytesIO(raw_bytes), "raw_valid.csv")},
                    content_type="multipart/form-data",
                )
                second = client.post(
                    "/run",
                    data={"raw_files": (io.BytesIO(raw_bytes), "raw_valid.csv")},
                    content_type="multipart/form-data",
                )
                token = next(iter(app.config["PENDING_UPLOADS"]._pending))
                pending_directory = app.config["PENDING_UPLOADS"]._pending[token].directory

                cancelled = client.post("/run/cancel", data={"token": token})
                self.assertEqual(cancelled.status_code, 302)
                self.assertEqual(app.config["PENDING_UPLOADS"]._pending, {})
                self.assertFalse(pending_directory.exists())

    def test_download_rejects_paths_outside_the_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._make_config(root)
            secret = root / "outside.txt"
            secret.write_text("do not serve me", encoding="utf-8")
            client = create_app(config).test_client()

            response = client.get("/download/../outside.txt")
            self.assertEqual(response.status_code, 404)

    def test_portal_nav_links_to_both_portals(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name))
            client = create_app(config).test_client()
            body = client.get("/").get_data(as_text=True)
            self.assertIn("Cage Card Production", body)
            self.assertIn("Mouse Inventory Update", body)
            self.assertIn("/inventory", body)

    def test_inventory_upload_page_renders(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name), append_only=True)
            client = create_app(config).test_client()
            response = client.get("/inventory")
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn("Mouse Inventory Update", body)
            self.assertIn('name="first_mouse_id"', body)

    def test_inventory_submit_adds_pups_with_correct_sex(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._make_config(root, append_only=True)
            client = create_app(config).test_client()

            response = client.post(
                "/inventory/submit",
                data={
                    "strain": "Kras/Lkb1",
                    "dob": "2026-01-19",
                    "mother": "CM9001",
                    "father": "CM9002",
                    "total_pups": "3",
                    "female_count": "1",
                    "male_count": "2",
                    "first_mouse_id": "CM2000",
                    "last_mouse_id": "CM2002",
                    "plate_id": "T1234567",
                    "transnetyx_order_date": "2026-01-20",
                },
            )
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            self.assertIn("CM2000", body)
            self.assertIn("CM2001", body)
            self.assertIn("CM2002", body)
            self.assertIn("LITTER_ENTERED", body)

    def test_inventory_submit_mismatch_is_a_friendly_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name), append_only=True)
            client = create_app(config).test_client()

            response = client.post(
                "/inventory/submit",
                data={
                    "strain": "Kras/Lkb1",
                    "dob": "2026-01-19",
                    "mother": "CM9001",
                    "father": "CM9002",
                    "total_pups": "5",
                    "female_count": "1",
                    "male_count": "2",
                    "first_mouse_id": "CM2000",
                    "last_mouse_id": "CM2002",
                    "plate_id": "T1234567",
                    "transnetyx_order_date": "2026-01-20",
                },
            )
            self.assertEqual(response.status_code, 422)
            self.assertIn("does not equal", response.get_data(as_text=True))

    def test_inventory_submit_conflict_is_reported_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name), append_only=True)
            client = create_app(config).test_client()

            # CM0001 already exists in the fixture inventory.
            response = client.post(
                "/inventory/submit",
                data={
                    "strain": "Kras/Lkb1",
                    "dob": "2026-01-19",
                    "mother": "CM9001",
                    "father": "CM9002",
                    "total_pups": "1",
                    "female_count": "1",
                    "male_count": "0",
                    "first_mouse_id": "CM0001",
                    "last_mouse_id": "CM0001",
                    "plate_id": "T1234567",
                    "transnetyx_order_date": "2026-01-20",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("CONFLICT", response.get_data(as_text=True))

    def test_inventory_submit_rejects_a_malformed_plate_id(self) -> None:
        # The browser's HTML pattern is only a UI hint; a direct HTTP request
        # (bypassing the browser) must be rejected the same way.
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name), append_only=True)
            client = create_app(config).test_client()

            response = client.post(
                "/inventory/submit",
                data={
                    "strain": "Kras/Lkb1",
                    "dob": "2026-01-19",
                    "mother": "CM9001",
                    "father": "CM9002",
                    "total_pups": "1",
                    "female_count": "1",
                    "male_count": "0",
                    "first_mouse_id": "CM2000",
                    "last_mouse_id": "CM2000",
                    "plate_id": "PLATE-01",
                    "transnetyx_order_date": "2026-01-20",
                },
            )
            self.assertEqual(response.status_code, 422)
            self.assertIn("Plate ID", response.get_data(as_text=True))

    def test_inventory_submit_rejects_a_non_iso_order_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._make_config(Path(directory_name), append_only=True)
            client = create_app(config).test_client()

            response = client.post(
                "/inventory/submit",
                data={
                    "strain": "Kras/Lkb1",
                    "dob": "2026-01-19",
                    "mother": "CM9001",
                    "father": "CM9002",
                    "total_pups": "1",
                    "female_count": "1",
                    "male_count": "0",
                    "first_mouse_id": "CM2000",
                    "last_mouse_id": "CM2000",
                    "plate_id": "T1234567",
                    "transnetyx_order_date": "01/20/2026",
                },
            )
            self.assertEqual(response.status_code, 422)
            self.assertIn("Transnetyx Order Date", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
