from __future__ import annotations

import unittest
from pathlib import Path

from automouse.cage_card_formatter import build_cage_card_records
from automouse.config import CageCardConfig, InventoryConfig
from automouse.inventory_manager import InventoryTable


class WeaningCardTests(unittest.TestCase):
    def test_litter_sex_grouping_and_five_mouse_split(self) -> None:
        headers = [f"Column {index}" for index in range(1, 22)]
        rows: list[list[str]] = []
        groups = [
            (range(11527, 11536), "CM11078/CM11079", "CM10997", "7/12/26", "Male", "Kras/p53/Tom/Cas9/Cpt2"),
            (range(11536, 11544), "CM11107/CM11109", "CM10251", "7/11/26", "Female", "Kras/p53/Tom/Cas9/Cpt1a"),
            (range(11544, 11550), "CM11107/CM11109", "CM10251", "7/11/26", "Male", "Kras/p53/Tom/Cas9/Cpt1a"),
            (range(11550, 11554), "CM11080/CM11093", "CM11016", "7/12/26", "Female", "Kras/p53/Tom/Cas9/Cpt2"),
            (range(11554, 11556), "CM11080/CM11093", "CM11016", "7/12/26", "Male", "Kras/p53/Tom/Cas9/Cpt2"),
            (range(11556, 11557), "CM11012/CM10988", "CM10141", "7/12/26", "Female", "Kras/p53/Tom/Cas9/Cpt2"),
            (range(11557, 11559), "CM11012/CM10988", "CM10141", "7/12/26", "Male", "Kras/p53/Tom/Cas9/Cpt2"),
        ]
        for mouse_numbers, mother, father, dob, sex, strain in groups:
            for number in mouse_numbers:
                row = [""] * 21
                row[0] = f"CM{number}"
                row[3] = strain
                row[12] = row[0]
                row[13] = mother
                row[14] = father
                row[15] = dob
                row[16] = sex
                row[17] = "8/9/26" if dob == "7/12/26" else "8/8/26"
                row[19] = row[0]
                row[20] = "+/+"
                rows.append(row)

        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 4, "cage_id": 5,
                "revised_strain": 6, "id": 13, "mother": 14,
                "father": 15, "dob": 16, "sex": 17, "wean_date": 18,
                "sample": 20, "genotype": 21,
            },
        )
        inventory = InventoryTable(Path("fixture.csv"), headers, rows, config)
        eligible = {row[0] for row in rows}
        records, issues, warnings = build_cage_card_records(
            inventory,
            eligible,
            CageCardConfig(
                template=Path("template.xlsx"),
                grouping_strategy="weaning_litter_sex",
            ),
        )

        self.assertEqual(issues, {})
        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 10)
        self.assertEqual(
            [record.animal_count for record in records],
            [5, 4, 5, 3, 5, 1, 4, 2, 1, 2],
        )
        self.assertEqual(
            [record.litter_count for record in records],
            [9, 9, 14, 14, 14, 14, 6, 6, 3, 3],
        )
        self.assertEqual(
            [record.sex for record in records],
            ["Male", "Male", "Female", "Female", "Male", "Male", "Female", "Male", "Female", "Male"],
        )
        self.assertEqual(records[0].mouse_ids, [f"CM{number}" for number in range(11527, 11532)])
        self.assertEqual(records[-1].mouse_ids, ["CM11557", "CM11558"])

    def test_compatible_grouping_allows_dob_window_but_separates_kras(self) -> None:
        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 2, "revised_strain": 3,
                "mother": 4, "father": 5, "dob": 6, "sex": 7,
                "wean_date": 8, "genotype": 9,
            },
        )
        headers = ["Mouse", "Strain", "Revised", "Mother", "Father", "DOB", "Sex", "Wean", "Genotype"]
        rows = [
            ["CM1", "Kras/p53", "", "CM10", "CM20", "7/1/26", "Male", "7/22/26", "K/+; P/+"],
            ["CM2", "Kras/p53", "", "CM11", "CM21", "7/5/26", "Male", "7/26/26", "LSL-G12D/+; P/+"],
            ["CM3", "Kras/p53", "", "CM12", "CM22", "7/20/26", "Male", "8/10/26", "K/+; P/+"],
            ["CM4", "Kras/p53", "", "CM13", "CM23", "7/3/26", "Male", "7/24/26", "+/+; P/+"],
        ]
        inventory = InventoryTable(Path("fixture.csv"), headers, rows, config)
        records, issues, warnings = build_cage_card_records(
            inventory,
            {"CM1", "CM2", "CM3", "CM4"},
            CageCardConfig(template=Path("template.xlsx")),
        )

        self.assertEqual(issues, {})
        self.assertEqual([record.mouse_ids for record in records], [["CM1", "CM2"], ["CM3"], ["CM4"]])
        self.assertEqual(records[0].animal_count, 2)
        self.assertEqual(records[0].date_born, "07/01/26 - 07/05/26")
        self.assertEqual(records[0].date_weaned, "07/29/26 - 08/02/26")
        self.assertTrue(any("source litters" in warning for warning in warnings))

    def test_compatible_grouping_balances_six_mice_instead_of_five_and_one(self) -> None:
        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 2, "revised_strain": 3,
                "mother": 4, "father": 5, "dob": 6, "sex": 7,
                "wean_date": 8, "genotype": 9,
            },
        )
        headers = ["Mouse", "Strain", "Revised", "Mother", "Father", "DOB", "Sex", "Wean", "Genotype"]
        rows = [
            [
                f"CM{number}",
                "Kras/p53",
                "",
                "CM10",
                "CM20",
                "7/1/26",
                "Female",
                "7/22/26",
                "K/+; P/+",
            ]
            for number in range(1, 7)
        ]
        inventory = InventoryTable(Path("fixture.csv"), headers, rows, config)
        records, issues, _ = build_cage_card_records(
            inventory,
            {row[0] for row in rows},
            CageCardConfig(template=Path("template.xlsx")),
        )

        self.assertEqual(issues, {})
        self.assertEqual([record.animal_count for record in records], [3, 3])

    def test_compatible_grouping_builds_raw_cards_without_dob(self) -> None:
        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 2, "revised_strain": 3,
                "mother": 4, "father": 5, "dob": 6, "sex": 7,
                "wean_date": 8, "genotype": 9,
            },
        )
        headers = ["Mouse", "Strain", "Revised", "Mother", "Father", "DOB", "Sex", "Wean", "Genotype"]
        rows = [
            ["CM1", "Kras/p53", "", "", "", "", "Male", "", "K/+; P/+"],
            ["CM2", "Kras/p53", "", "", "", "", "Male", "", "LSL-G12D/+; P/+"],
            ["CM3", "Kras/p53", "", "", "", "", "Male", "", "+/+; P/+"],
            ["CM4", "Kras/p53", "", "", "", "", "Female", "", "K/+; P/+"],
        ]
        inventory = InventoryTable(Path("fixture.csv"), headers, rows, config)
        records, issues, warnings = build_cage_card_records(
            inventory,
            {"CM1", "CM2", "CM3", "CM4"},
            CageCardConfig(template=Path("template.xlsx")),
        )

        self.assertEqual(issues, {})
        self.assertEqual([record.mouse_ids for record in records], [["CM1", "CM2"], ["CM3"], ["CM4"]])
        self.assertEqual(records[0].date_born, None)
        self.assertEqual(records[0].date_weaned, None)
        self.assertEqual(records[0].sex, "Male")
        self.assertEqual(records[0].strain, "Kras/p53")
        self.assertEqual(records[0].animal_count, 2)
        self.assertTrue(any("no DOB metadata" in warning for warning in warnings))

    def test_missing_weaning_metadata_is_not_grouped(self) -> None:
        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 2, "revised_strain": 3,
                "mother": 4, "father": 5, "dob": 6, "sex": 7,
                "wean_date": 8, "genotype": 9,
            },
        )
        inventory = InventoryTable(
            Path("fixture.csv"),
            ["Mouse", "Strain", "Revised", "Mother", "Father", "DOB", "Sex", "Wean", "Genotype"],
            [["CM1", "Strain", "", "", "CM9", "7/1/26", "Male", "7/22/26", "+/+" ]],
            config,
        )
        records, issues, _ = build_cage_card_records(
            inventory,
            {"CM1"},
            CageCardConfig(
                template=Path("template.xlsx"),
                grouping_strategy="weaning_litter_sex",
            ),
        )
        self.assertEqual(records, [])
        self.assertIn("CM1", issues)

    def test_parent_genotype_requires_every_listed_parent_to_resolve(self) -> None:
        config = InventoryConfig(
            file=Path("fixture.csv"),
            columns={
                "mouse_id": 1, "strain": 2, "revised_strain": 3,
                "mother": 4, "father": 5, "dob": 6, "sex": 7,
                "wean_date": 8, "genotype": 9,
            },
        )
        headers = ["Mouse", "Strain", "Revised", "Mother", "Father", "DOB", "Sex", "Wean", "Genotype"]
        rows = [
            ["CM1", "Strain A", "", "CM10/CM11", "CM12", "7/1/26", "Female", "7/22/26", "+/+"],
            ["CM2", "Strain B", "", "CM10/CM99", "CM12", "7/2/26", "Male", "7/23/26", "+/+"],
            ["CM10", "", "", "", "", "", "", "", "K/+"],
            ["CM11", "", "", "", "", "", "", "", "K/+"],
            ["CM12", "", "", "", "", "", "", "", "L/L"],
        ]
        inventory = InventoryTable(Path("fixture.csv"), headers, rows, config)
        records, issues, _ = build_cage_card_records(
            inventory,
            {"CM1", "CM2"},
            CageCardConfig(template=Path("template.xlsx")),
        )

        self.assertEqual(issues, {})
        by_mouse = {record.mouse_ids[0]: record for record in records}
        self.assertEqual(by_mouse["CM1"].dam_genotype, "K/+")
        self.assertEqual(by_mouse["CM1"].sire_genotype, "L/L")
        self.assertEqual(by_mouse["CM2"].dam_genotype, "")


if __name__ == "__main__":
    unittest.main()
