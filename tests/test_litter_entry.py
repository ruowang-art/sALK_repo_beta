from __future__ import annotations

import unittest

from automouse.exceptions import InputValidationError
from automouse.litter_entry import LitterSubmission, expand_litter


def _submission(**overrides) -> LitterSubmission:
    defaults = dict(
        strain="Kras/Lkb1",
        dob="2026-01-19",
        mother="CM9001",
        father="CM9002",
        total_pups=3,
        female_count=1,
        male_count=2,
        first_mouse_id="CM1000",
        last_mouse_id="CM1002",
        plate_id="T1234567",
        transnetyx_order_date="2026-01-20",
    )
    defaults.update(overrides)
    return LitterSubmission(**defaults)


class ExpandLitterTests(unittest.TestCase):
    def test_females_take_the_earliest_ids_then_males(self) -> None:
        mice = expand_litter(
            _submission(total_pups=13, female_count=6, male_count=7,
                        first_mouse_id="CM12000", last_mouse_id="CM12012")
        )
        self.assertEqual(len(mice), 13)
        self.assertEqual([m.mouse_id for m in mice[:6]], [f"CM1200{i}" for i in range(6)])
        self.assertEqual(
            [m.mouse_id for m in mice[6:]],
            ["CM12006", "CM12007", "CM12008", "CM12009", "CM12010", "CM12011", "CM12012"],
        )
        self.assertEqual([m.sex for m in mice[:6]], ["Female"] * 6)
        self.assertEqual([m.sex for m in mice[6:]], ["Male"] * 7)

    def test_preserves_zero_padding_width(self) -> None:
        mice = expand_litter(
            _submission(total_pups=2, female_count=1, male_count=1,
                        first_mouse_id="CM007", last_mouse_id="CM008")
        )
        self.assertEqual([m.mouse_id for m in mice], ["CM007", "CM008"])

    def test_all_female_or_all_male_litter(self) -> None:
        mice = expand_litter(
            _submission(total_pups=2, female_count=2, male_count=0,
                        first_mouse_id="CM001", last_mouse_id="CM002")
        )
        self.assertEqual([m.sex for m in mice], ["Female", "Female"])

    def test_sex_counts_must_sum_to_total_pups(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "does not equal"):
            expand_litter(_submission(total_pups=3, female_count=1, male_count=1))

    def test_at_least_one_sex_required(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "at least one"):
            expand_litter(
                _submission(
                    total_pups=2, female_count=0, male_count=0,
                    first_mouse_id="CM001", last_mouse_id="CM002",
                )
            )

    def test_id_range_size_must_match_total_pups(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "contains 3 ID"):
            expand_litter(
                _submission(
                    total_pups=2, female_count=1, male_count=1,
                    first_mouse_id="CM1000", last_mouse_id="CM1002",
                )
            )

    def test_mismatched_id_prefixes_are_rejected(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "same prefix"):
            expand_litter(_submission(first_mouse_id="CM1000", last_mouse_id="CF1002"))

    def test_last_before_first_is_rejected(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "must not come before"):
            expand_litter(
                _submission(
                    total_pups=1, female_count=1, male_count=0,
                    first_mouse_id="CM1005", last_mouse_id="CM1000",
                )
            )

    def test_non_numeric_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "does not end in a number"):
            expand_litter(_submission(first_mouse_id="CM-abc", last_mouse_id="CM1002"))

    def test_negative_pups_rejected(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "positive"):
            expand_litter(_submission(total_pups=0))

    def test_plate_id_must_be_t_plus_seven_digits(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "Plate ID"):
            expand_litter(_submission(plate_id="PLATE-01"))
        with self.assertRaisesRegex(InputValidationError, "Plate ID"):
            expand_litter(_submission(plate_id="T123456"))  # only six digits
        with self.assertRaisesRegex(InputValidationError, "Plate ID"):
            expand_litter(_submission(plate_id="T12345678"))  # eight digits
        expand_litter(_submission(plate_id="T1234567"))  # does not raise

    def test_transnetyx_order_date_must_be_iso_format(self) -> None:
        with self.assertRaisesRegex(InputValidationError, "Transnetyx Order Date"):
            expand_litter(_submission(transnetyx_order_date="01/20/2026"))
        with self.assertRaisesRegex(InputValidationError, "Transnetyx Order Date"):
            expand_litter(_submission(transnetyx_order_date="not a date"))
        expand_litter(_submission(transnetyx_order_date="2026-01-20"))  # does not raise


if __name__ == "__main__":
    unittest.main()
