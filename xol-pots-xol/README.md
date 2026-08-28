# Xol-Pots-Xol

Xol-Pots-Xol is a standalone tool, separate from Möuseley Kräs, that consolidates sparse Live Label
cage-card workbooks (as produced by Möuseley Kräs) into fuller cages. It never reads from or writes
to Möuseley Kräs's inventory, raw Transnetyx files, or cage-card template — its only input is one or
more already-produced Live Label `.xlsx` workbooks, and its only output is a new workbook built from
them.

## Merge rule

Two mice can share a consolidated cage, up to 5 mice per cage, only if all of the following match:

- the same (normalized) sex;
- the same (normalized) strain;
- the same (normalized) Kras genotype — `LSL-G12D/+` and `K/+` are treated as one group, `+/+` is a
  separate group, and the two are never mixed;
- a date-of-birth window of at most 2 days apart for males, 7 days apart for females. If a source
  cage's own `DATE BORN` is already a range (its mice didn't share one exact DOB), its outer bounds
  are used: a merge is only allowed if every mouse involved still falls within the window of every
  other mouse.

A mouse missing a recognized sex, strain, Kras genotype, or usable date of birth is never guessed
into a group — it's kept in its original cage grouping in the output (the `Unconsolidated` sheet),
and listed with its specific reason(s) in the `Review Needed` sheet of the result workbook.

### The Kras genotype grammar is a narrow, versioned contract

Xol-Pots-Xol is deliberately **not** a general genotype parser — the only genotype content it
understands is the Kras locus, read as the first `;`-separated segment of the genotype string,
using exactly the allele tokens `+`, `K`, and `LSL-G12D` (see `KRAS_ALLELE_SHORTHAND` and
`KRAS_GENOTYPE_GRAMMAR_VERSION` in `consolidator.py`, and `normalize_kras_genotype`). Every other
locus, and every other field, is treated as opaque text. If Möuseley Kräs's genotype-translation
output format ever changes in a way that affects the Kras locus's position or token names, update
`consolidator.py` and bump `KRAS_GENOTYPE_GRAMMAR_VERSION` together — do not broaden this parsing
to guess at new tokens.

### Result workbook sheets

The output workbook always has four sheets:

- **Sheet1** — successfully consolidated cages only.
- **Unconsolidated** — mice that couldn't be grouped, preserved in their original cage-row shape
  (same Live Label column layout as Sheet1), kept separate so they're never mistaken for a
  consolidated cage.
- **Review Needed** — one row per unconsolidated mouse, with its source file, source row, strain,
  sex, raw genotype text, and the specific reason(s) it was excluded.
- **Report** — the Kras grammar version, input/output counts, and a per-input-file `.xlsx` hash
  and row count, for reproducibility.

## Setup

Xol-Pots-Xol is a standalone sibling project with its own virtual environment — it never shares
Möuseley Kräs's `.venv`, so the two projects can't drift into depending on each other's installed
package versions. From the project root, double-click `XolPotsXol_Setup.command`, or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

This registers the `xolpotsxol` and `xolpotsxol-serve` commands directly in `.venv/bin/` — no
`PYTHONPATH` needed for normal use.

`requirements.lock.txt` (generated with `pip-tools` using Python 3.11, the oldest supported
version, as the resolving interpreter, so it doesn't pin a package version with no wheel for an
older supported Python; regenerate with any 3.11 interpreter:
`python3.11 -m pip-tools compile --extra dev pyproject.toml`, or the equivalent `pip-compile` call
from a 3.11 venv with `pip-tools` installed) pins the exact dependency versions verified working,
checked to install cleanly on Python 3.11–3.14. `XolPotsXol_Setup.command` reconciles to it on
every run, not just when a package is missing.

If `xolpotsxol`/`xolpotsxol-serve` ever fails with `ModuleNotFoundError` right after a successful
setup, run `../scripts/fix_hidden_venv.sh` from this directory.

## Web app

```bash
.venv/bin/xolpotsxol-serve
```

or double-click `XolPotsXol_WebApp.command` from the project root. Upload one or more Live Label
`.xlsx` files, review the consolidation summary and warnings, and download the result.

## Command line

```bash
.venv/bin/xolpotsxol \
  path/to/cage_cards_1.xlsx path/to/cage_cards_2.xlsx \
  --output path/to/consolidated.xlsx
```

`--male-dob-window-days` and `--female-dob-window-days` override the defaults (2 and 7).

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The `PYTHONPATH="$PWD/src" ../.venv/bin/python ...` source-path style still works as a fallback
(e.g. against a different Python without reinstalling), but is no longer the primary supported
way to run this project.
