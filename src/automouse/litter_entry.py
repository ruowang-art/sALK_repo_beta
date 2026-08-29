"""Pure logic for the manual litter-entry mouse-inventory-update portal.

A litter is entered by hand right after birth — before any Transnetyx
genotyping — as strain, DOB, parents, a female/male pup count, and the
first and last mouse ID assigned to the litter. This module only expands
that into one (mouse_id, sex) pair per pup and validates internal
consistency; it never touches the inventory or any file. See
``app.append_litter_to_inventory`` for where a validated litter is actually
written, and ``CLAUDE.md`` for why this never guesses at a mismatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from automouse.exceptions import InputValidationError

_TRAILING_NUMBER = re.compile(r"^(.*?)(\d+)$")
_PLATE_ID = re.compile(r"^T\d{7}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(slots=True)
class LitterSubmission:
    strain: str
    dob: str
    mother: str
    father: str
    total_pups: int
    female_count: int
    male_count: int
    first_mouse_id: str
    last_mouse_id: str
    plate_id: str
    transnetyx_order_date: str


@dataclass(slots=True)
class LitterMouse:
    mouse_id: str
    sex: str


def _split_trailing_number(value: str, field_name: str) -> tuple[str, str]:
    match = _TRAILING_NUMBER.match(value.strip())
    if not match:
        raise InputValidationError(
            f"{field_name} {value!r} does not end in a number; cannot infer a "
            "litter ID range from it."
        )
    return match.group(1), match.group(2)


def expand_litter(submission: LitterSubmission) -> list[LitterMouse]:
    """Validate one litter submission and expand it into one (mouse_id,
    sex) entry per pup, females first. Raises :class:`InputValidationError`
    on any inconsistency between the pup counts, the sex counts, and the
    mouse ID range, or on a Plate ID/Transnetyx Order Date that doesn't
    match the required format — nothing here is ever guessed or silently
    reconciled. This is the one validation funnel shared by the CLI and the
    web form, so the two can never enforce different contracts.
    """
    if submission.total_pups <= 0:
        raise InputValidationError("Number of pups must be a positive number.")
    if submission.female_count < 0 or submission.male_count < 0:
        raise InputValidationError("Number of females/males cannot be negative.")
    if submission.female_count == 0 and submission.male_count == 0:
        raise InputValidationError("Enter at least one female or male pup.")
    if submission.female_count + submission.male_count != submission.total_pups:
        raise InputValidationError(
            "Number of females plus number of males "
            f"({submission.female_count} + {submission.male_count} = "
            f"{submission.female_count + submission.male_count}) does not equal "
            f"the number of pups ({submission.total_pups})."
        )
    if not _PLATE_ID.match(submission.plate_id.strip()):
        raise InputValidationError(
            f"Plate ID {submission.plate_id!r} must be 'T' followed by seven digits "
            "(e.g. T1234567)."
        )
    if not _ISO_DATE.match(submission.transnetyx_order_date.strip()):
        raise InputValidationError(
            f"Transnetyx Order Date {submission.transnetyx_order_date!r} must be a date in "
            "YYYY-MM-DD format."
        )

    first_prefix, first_number = _split_trailing_number(submission.first_mouse_id, "First mouse ID")
    last_prefix, last_number = _split_trailing_number(submission.last_mouse_id, "Last mouse ID")
    if first_prefix != last_prefix:
        raise InputValidationError(
            "The first and last mouse IDs must share the same prefix: "
            f"{submission.first_mouse_id!r} vs {submission.last_mouse_id!r}."
        )
    first_value = int(first_number)
    last_value = int(last_number)
    if last_value < first_value:
        raise InputValidationError(
            f"The last mouse ID ({submission.last_mouse_id}) must not come before "
            f"the first ({submission.first_mouse_id})."
        )
    width = len(first_number)
    range_count = last_value - first_value + 1
    if range_count != submission.total_pups:
        raise InputValidationError(
            f"The mouse ID range {submission.first_mouse_id}-{submission.last_mouse_id} "
            f"contains {range_count} ID(s), which does not match the number of pups "
            f"({submission.total_pups})."
        )

    mouse_ids = [
        f"{first_prefix}{number:0{width}d}" for number in range(first_value, last_value + 1)
    ]
    mice: list[LitterMouse] = []
    for index, mouse_id in enumerate(mouse_ids):
        sex = "Female" if index < submission.female_count else "Male"
        mice.append(LitterMouse(mouse_id=mouse_id, sex=sex))
    return mice
