"""Cross-workbook cage-card consolidation.

Two mice can share a consolidated cage only if all of the following match:

- the same (normalized) sex,
- the same (normalized) strain,
- the same (normalized) Kras genotype — ``LSL-G12D/+`` and ``K/+`` are
  treated as one group, ``+/+`` is a separate group, and the two are never
  mixed,
- a date-of-birth window: at most 2 days apart for males, 7 days apart for
  females. A cage whose own DATE BORN is already a range (its mice didn't
  share one exact DOB) is treated by its outer bounds — a merge is allowed
  only if every mouse involved still falls within the window of every
  other mouse.

A mouse missing any of sex, strain, a recognized Kras genotype, or a usable
DOB is left out of consolidation entirely (returned separately, unchanged)
rather than guessed into a group.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from xolpotsxol.models import MAX_MICE_PER_CAGE, ConsolidatedCage, ConsolidationResult, SourceMouse

DEFAULT_MALE_DOB_WINDOW_DAYS = 2
DEFAULT_FEMALE_DOB_WINDOW_DAYS = 7


def _natural_key(value: str) -> list:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_sex(value: str) -> str | None:
    normalized = _normalize_text(value).casefold()
    if normalized in {"m", "male"}:
        return "Male"
    if normalized in {"f", "female"}:
        return "Female"
    return None


def normalize_strain_key(value: str) -> str:
    return _normalize_text(value).casefold()


def normalize_kras_genotype(value: str) -> str | None:
    genotype = _normalize_text(value).lstrip("'")
    if not genotype:
        return None
    first_locus = genotype.split(";", 1)[0].strip()
    alleles = [
        allele.strip()
        for allele in first_locus.replace(" ", "").split("/")
        if allele.strip()
    ]
    if len(alleles) != 2:
        return None
    normalized = [KRAS_ALLELE_SHORTHAND.get(allele) for allele in alleles]
    if any(allele is None for allele in normalized):
        return None
    if normalized.count("K") == 1 and normalized.count("+") == 1:
        return "K/+"
    if normalized == ["+", "+"]:
        return "+/+"
    return None


# The only genotype grammar this tool understands, as a versioned contract:
# Xol-Pots-Xol is deliberately NOT a general genotype parser. It recognizes
# exactly the Kras locus, expressed as the first ";"-separated segment of a
# genotype string, using exactly these allele tokens. Anything else (a
# reordered locus list, a different Kras allele name, any other gene) is
# left unconsolidated rather than guessed. If Möuseley Kräs's genotype
# translation script ever changes this convention, update this dict and
# bump KRAS_GENOTYPE_GRAMMAR_VERSION together.
KRAS_GENOTYPE_GRAMMAR_VERSION = 1
KRAS_ALLELE_SHORTHAND = {"+": "+", "K": "K", "LSL-G12D": "K"}


def unconsolidated_reasons(mouse: SourceMouse) -> list[str]:
    """Human-readable reason(s) a mouse was left out of consolidation.

    Mirrors exactly the eligibility check in :func:`consolidate` — kept as
    its own function so the writer/report layer can explain *why* a mouse
    is unconsolidated without duplicating that logic.
    """
    reasons: list[str] = []
    if normalize_sex(mouse.sex) is None:
        reasons.append(f"Unrecognized sex: {mouse.sex!r}")
    if not normalize_strain_key(mouse.strain):
        reasons.append("Blank strain")
    if normalize_kras_genotype(mouse.genotype) is None:
        reasons.append(f"Unrecognized/unsupported Kras genotype: {mouse.genotype!r}")
    if mouse.dob_min is None or mouse.dob_max is None:
        reasons.append("No usable date of birth")
    return reasons or ["Unknown"]


def _uniform(values: list[str]) -> str:
    unique = sorted({value.strip() for value in values if value.strip()})
    return unique[0] if len(unique) == 1 else ""


def _chunk(items: list, max_size: int) -> list[list]:
    chunks: list[list] = []
    start = 0
    while start < len(items):
        remaining = len(items) - start
        if remaining <= max_size:
            chunks.append(items[start:])
            break
        if remaining == max_size + 1:
            split_size = (remaining + 1) // 2
        elif remaining - max_size == 1:
            split_size = max_size - 1
        else:
            split_size = max_size
        chunks.append(items[start : start + split_size])
        start += split_size
    return chunks


@dataclass(slots=True)
class _Eligible:
    sex: str
    strain_key: str
    genotype_key: str
    mouse: SourceMouse


def _build_cage(chunk: list[SourceMouse]) -> ConsolidatedCage:
    warnings: list[str] = []
    source_keys_seen: set[tuple[str, int]] = set()
    litter_total = 0
    for mouse in chunk:
        if mouse.source_cage_key not in source_keys_seen:
            source_keys_seen.add(mouse.source_cage_key)
            litter_total += mouse.source_in_litter
    if len(chunk) == 1:
        warnings.append(
            f"{chunk[0].mouse_id} could not be paired with a compatible cage-mate "
            "within the DOB window; still a single-mouse cage."
        )
    if len(source_keys_seen) > 1:
        mouse_ids = ", ".join(mouse.mouse_id for mouse in chunk)
        warnings.append(f"Cage [{mouse_ids}] combines mice from {len(source_keys_seen)} source cages.")
    return ConsolidatedCage(mice=list(chunk), warnings=warnings)


def consolidate(
    mice: list[SourceMouse],
    *,
    male_dob_window_days: int = DEFAULT_MALE_DOB_WINDOW_DAYS,
    female_dob_window_days: int = DEFAULT_FEMALE_DOB_WINDOW_DAYS,
) -> ConsolidationResult:
    input_cage_keys = {mouse.source_cage_key for mouse in mice}

    eligible: list[_Eligible] = []
    unconsolidated: list[SourceMouse] = []
    for mouse in mice:
        sex = normalize_sex(mouse.sex)
        strain_key = normalize_strain_key(mouse.strain)
        genotype_key = normalize_kras_genotype(mouse.genotype)
        if sex is None or not strain_key or genotype_key is None or mouse.dob_min is None or mouse.dob_max is None:
            unconsolidated.append(mouse)
            continue
        eligible.append(_Eligible(sex=sex, strain_key=strain_key, genotype_key=genotype_key, mouse=mouse))

    grouped: dict[tuple[str, str, str], list[SourceMouse]] = {}
    for item in eligible:
        grouped.setdefault((item.sex, item.strain_key, item.genotype_key), []).append(item.mouse)

    consolidated_cages: list[ConsolidatedCage] = []
    for group_key in sorted(grouped):
        sex, _strain_key, _genotype_key = group_key
        window_days = male_dob_window_days if sex == "Male" else female_dob_window_days
        group_mice = sorted(
            grouped[group_key],
            key=lambda mouse: (mouse.dob_min, _natural_key(mouse.mouse_id)),
        )

        clusters: list[list[SourceMouse]] = []
        current: list[SourceMouse] = []
        current_min = None
        current_max = None
        for mouse in group_mice:
            if not current:
                current = [mouse]
                current_min = mouse.dob_min
                current_max = mouse.dob_max
                continue
            candidate_max = max(current_max, mouse.dob_max)
            if (candidate_max - current_min).days <= window_days:
                current.append(mouse)
                current_max = candidate_max
            else:
                clusters.append(current)
                current = [mouse]
                current_min = mouse.dob_min
                current_max = mouse.dob_max
        if current:
            clusters.append(current)

        for cluster in clusters:
            for chunk in _chunk(cluster, MAX_MICE_PER_CAGE):
                consolidated_cages.append(_build_cage(chunk))

    warnings = [warning for cage in consolidated_cages for warning in cage.warnings]
    return ConsolidationResult(
        consolidated_cages=consolidated_cages,
        unconsolidated_mice=unconsolidated,
        warnings=warnings,
        input_cage_count=len(input_cage_keys),
        input_mouse_count=len(mice),
    )
