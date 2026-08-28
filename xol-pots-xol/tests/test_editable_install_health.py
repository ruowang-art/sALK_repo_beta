"""Regression check for the recurring macOS hidden-.pth editable-install bug.

See tests/test_editable_install_health.py in the root Möuseley Kräs project
for the full explanation. Xol-Pots-Xol has its own venv (xol-pots-xol/.venv)
and hit the identical failure, so it gets the identical check.
"""

from __future__ import annotations

import platform
import stat
import sys
import sysconfig
import unittest
from pathlib import Path


@unittest.skipUnless(platform.system() == "Darwin", "UF_HIDDEN is a macOS-only file flag")
class EditableInstallNotHiddenTests(unittest.TestCase):
    def test_xolpotsxol_editable_pth_is_not_hidden(self) -> None:
        site_packages = Path(sysconfig.get_paths()["purelib"])
        matches = sorted(site_packages.glob("__editable__.xolpotsxol-*.pth"))
        if not matches:
            self.skipTest(
                "xolpotsxol is not editable-installed in the interpreter running "
                f"this test ({sys.executable}); run XolPotsXol_Setup.command first."
            )
        for pth_file in matches:
            flags = pth_file.stat().st_flags
            self.assertFalse(
                flags & stat.UF_HIDDEN,
                f"{pth_file} is marked hidden (UF_HIDDEN) - Python's site.py will "
                "silently skip it and xolpotsxol will fail to import. Run "
                "scripts/fix_hidden_venv.sh (with zsh, not bash) to repair it.",
            )


if __name__ == "__main__":
    unittest.main()
