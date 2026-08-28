"""Data model for Xol-Pots-Xol.

Xol-Pots-Xol is a standalone tool, independent of Möuseley Kräs: it never
reads or writes anything Möuseley Kräs owns (the inventory, raw Transnetyx
files, or the cage-card template). Its only input is one or more already
-produced Live Label cage-card workbooks; its only output is a new workbook
of the same shape, built from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

EXPECTED_HEADERS = (
    "Experiment URL", "Strain", "# IN CAGE", "# IN LITTER", "SEX",
    "DATE WEANED", "DATE BORN", "MOUSE 1", "MOUSE 2", "MOUSE 3",
    "MOUSE 4", "MOUSE 5", "MOUSE 1 GENOTYPE", "MOUSE 2 GENOTYPE",
    "MOUSE 3 GENOTYPE", "MOUSE 4 GENOTYPE", "MOUSE 5 GENOTYPE",
    "DAM", "DAM GENOTYPE", "SIRE", "SIRE GENOTYPE", "BREEDER? (B)",
    "Set up date",
)

MAX_MICE_PER_CAGE = 5


@dataclass(slots=True)
class SourceMouse:
    """One mouse read from one row of an uploaded Live Label workbook."""

    mouse_id: str
    genotype: str
    sex: str
    strain: str
    dob_min: date | None
    dob_max: date | None
    dam: str
    dam_genotype: str
    sire: str
    sire_genotype: str
    breeder: str
    experiment_url: str
    source_file: str
    source_row: int
    source_in_litter: int

    @property
    def source_cage_key(self) -> tuple[str, int]:
        """Identifies the original cage row this mouse came from, so a
        consolidated cage's "# IN LITTER" can sum each distinct original
        row's count exactly once, even if several of its mice end up here.
        """
        return (self.source_file, self.source_row)


@dataclass(slots=True)
class ConsolidatedCage:
    """A new cage row built by Xol-Pots-Xol from one or more source rows."""

    mice: list[SourceMouse]
    warnings: list[str]


@dataclass(slots=True)
class ConsolidationResult:
    consolidated_cages: list[ConsolidatedCage]
    unconsolidated_mice: list[SourceMouse]
    warnings: list[str]
    input_cage_count: int
    input_mouse_count: int
