class XolPotsXolError(Exception):
    """Base class for expected, user-facing Xol-Pots-Xol failures."""


class CageCardFormatError(XolPotsXolError):
    """An uploaded workbook does not look like a Live Label cage-card export."""
