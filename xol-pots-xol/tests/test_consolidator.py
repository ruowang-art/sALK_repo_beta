from __future__ import annotations

import unittest
from datetime import date

from xolpotsxol.consolidator import consolidate, normalize_kras_genotype, normalize_sex
from xolpotsxol.models import SourceMouse


def _mouse(
    mouse_id: str,
    *,
    sex: str = "Male",
    strain: str = "Kras/Lkb1",
    genotype: str = "+/+",
    dob: date | None = date(2026, 1, 1),
    dob_max: date | None = None,
    source_row: int = 1,
    source_file: str = "a.xlsx",
    source_in_litter: int = 1,
) -> SourceMouse:
    return SourceMouse(
        mouse_id=mouse_id,
        genotype=genotype,
        sex=sex,
        strain=strain,
        dob_min=dob,
        dob_max=dob_max if dob_max is not None else dob,
        dam="",
        dam_genotype="",
        sire="",
        sire_genotype="",
        breeder="",
        experiment_url="",
        source_file=source_file,
        source_row=source_row,
        source_in_litter=source_in_litter,
    )


class NormalizeTests(unittest.TestCase):
    def test_normalize_sex(self) -> None:
        self.assertEqual(normalize_sex("male"), "Male")
        self.assertEqual(normalize_sex("F"), "Female")
        self.assertIsNone(normalize_sex("unknown"))

    def test_normalize_kras_genotype_groups_g12d_with_k(self) -> None:
        self.assertEqual(normalize_kras_genotype("K/+"), "K/+")
        self.assertEqual(normalize_kras_genotype("LSL-G12D/+"), "K/+")
        self.assertEqual(normalize_kras_genotype("+/+"), "+/+")

    def test_normalize_kras_genotype_uses_first_locus_only(self) -> None:
        self.assertEqual(normalize_kras_genotype("+/+; L/L; T/T; HC9/+"), "+/+")

    def test_normalize_kras_genotype_unrecognized_is_none(self) -> None:
        self.assertIsNone(normalize_kras_genotype("weird"))
        self.assertIsNone(normalize_kras_genotype(""))


class ConsolidateGroupingTests(unittest.TestCase):
    def test_merges_within_male_window_across_two_source_cages(self) -> None:
        mice = [
            _mouse("CM0001", source_row=1, source_in_litter=1, dob=date(2026, 1, 19)),
            _mouse("CM0002", source_row=2, source_in_litter=2, dob=date(2026, 1, 20)),
            _mouse("CM0003", source_row=2, source_in_litter=2, dob=date(2026, 1, 20)),
        ]
        result = consolidate(mice, male_dob_window_days=2, female_dob_window_days=7)
        self.assertEqual(len(result.consolidated_cages), 1)
        cage = result.consolidated_cages[0]
        self.assertEqual({m.mouse_id for m in cage.mice}, {"CM0001", "CM0002", "CM0003"})
        self.assertEqual(len(result.unconsolidated_mice), 0)

    def test_does_not_merge_beyond_male_window(self) -> None:
        mice = [
            _mouse("CM0001", dob=date(2026, 1, 1)),
            _mouse("CM0002", dob=date(2026, 1, 5)),  # 4 days apart > 2-day male window
        ]
        result = consolidate(mice, male_dob_window_days=2, female_dob_window_days=7)
        self.assertEqual(len(result.consolidated_cages), 2)
        self.assertEqual({len(c.mice) for c in result.consolidated_cages}, {1})

    def test_female_window_is_wider(self) -> None:
        mice = [
            _mouse("CF0001", sex="Female", dob=date(2026, 1, 1)),
            _mouse("CF0002", sex="Female", dob=date(2026, 1, 7)),  # 6 days: within 7-day window
        ]
        result = consolidate(mice, male_dob_window_days=2, female_dob_window_days=7)
        self.assertEqual(len(result.consolidated_cages), 1)
        self.assertEqual(len(result.consolidated_cages[0].mice), 2)

    def test_range_dob_uses_outer_bounds(self) -> None:
        # First cage's own DOB was already a range (02/16-02/17); a second,
        # single-DOB cage at 02/18 is checked against the outer bound
        # (02/16), not just one representative date: combined span is 2
        # days, exactly at the male window limit, so it merges.
        mice = [
            _mouse("CM0001", dob=date(2026, 2, 16), dob_max=date(2026, 2, 17)),
            _mouse("CM0002", dob=date(2026, 2, 18), dob_max=date(2026, 2, 18)),
        ]
        result = consolidate(mice, male_dob_window_days=2, female_dob_window_days=7)
        self.assertEqual(len(result.consolidated_cages), 1)
        self.assertEqual(len(result.consolidated_cages[0].mice), 2)

        # One day later and the combined span (3 days) exceeds the window,
        # even though each cage's own internal spread is unchanged.
        mice_too_far = [
            _mouse("CM0001", dob=date(2026, 2, 16), dob_max=date(2026, 2, 17)),
            _mouse("CM0002", dob=date(2026, 2, 19), dob_max=date(2026, 2, 19)),
        ]
        result_too_far = consolidate(mice_too_far, male_dob_window_days=2, female_dob_window_days=7)
        self.assertEqual(len(result_too_far.consolidated_cages), 2)

    def test_different_genotype_never_merges(self) -> None:
        mice = [
            _mouse("CM0001", genotype="+/+", dob=date(2026, 1, 1)),
            _mouse("CM0002", genotype="K/+", dob=date(2026, 1, 1)),
        ]
        result = consolidate(mice)
        self.assertEqual(len(result.consolidated_cages), 2)

    def test_different_sex_never_merges(self) -> None:
        mice = [
            _mouse("CM0001", sex="Male", dob=date(2026, 1, 1)),
            _mouse("CF0001", sex="Female", dob=date(2026, 1, 1)),
        ]
        result = consolidate(mice)
        self.assertEqual(len(result.consolidated_cages), 2)

    def test_different_strain_never_merges(self) -> None:
        mice = [
            _mouse("CM0001", strain="Kras/Lkb1", dob=date(2026, 1, 1)),
            _mouse("CM0002", strain="Kras/p53", dob=date(2026, 1, 1)),
        ]
        result = consolidate(mice)
        self.assertEqual(len(result.consolidated_cages), 2)

    def test_missing_required_field_is_left_unconsolidated(self) -> None:
        mice = [
            _mouse("CM0001", genotype=""),
            _mouse("CM0002", sex=""),
            _mouse("CM0003", dob=None),
        ]
        result = consolidate(mice)
        self.assertEqual(len(result.consolidated_cages), 0)
        self.assertEqual(len(result.unconsolidated_mice), 3)

    def test_caps_consolidated_cage_at_five_mice_with_balanced_split(self) -> None:
        mice = [_mouse(f"CM{index:04d}", dob=date(2026, 1, 1)) for index in range(6)]
        result = consolidate(mice)
        sizes = sorted(len(cage.mice) for cage in result.consolidated_cages)
        self.assertEqual(sizes, [3, 3])  # not 5 + 1

    def test_in_litter_sums_distinct_source_cages_once(self) -> None:
        mice = [
            _mouse("CM0001", source_row=1, source_in_litter=3, dob=date(2026, 1, 1)),
            _mouse("CM0002", source_row=1, source_in_litter=3, dob=date(2026, 1, 1)),
            _mouse("CM0003", source_row=2, source_in_litter=2, dob=date(2026, 1, 1)),
        ]
        result = consolidate(mice)
        self.assertEqual(len(result.consolidated_cages), 1)
        from xolpotsxol.writer import _litter_count

        self.assertEqual(_litter_count(result.consolidated_cages[0].mice), 5)


if __name__ == "__main__":
    unittest.main()
