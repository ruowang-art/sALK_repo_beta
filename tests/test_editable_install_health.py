"""Regression check for the recurring macOS hidden-.pth editable-install bug.

Root cause (see scripts/fix_hidden_venv.sh): some macOS actions mark files
inside .venv with the UF_HIDDEN flag, and Python 3.14's site.py silently
skips hidden .pth files - which are exactly what an editable install
(`pip install -e .`) uses to register this package's source directory. The
package then "disappears" even though pip still reports it as installed.
This has recurred multiple times in this project; this test exists so a
future setup run that reintroduces it fails loudly in CI/test output instead
of surfacing later as a confusing ModuleNotFoundError.
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
    def test_automouse_editable_pth_is_not_hidden(self) -> None:
        site_packages = Path(sysconfig.get_paths()["purelib"])
        matches = sorted(site_packages.glob("__editable__.automouse-*.pth"))
        if not matches:
            self.skipTest(
                "automouse is not editable-installed in the interpreter running "
                f"this test ({sys.executable}); run AutoMouse_Setup.command first."
            )
        for pth_file in matches:
            flags = pth_file.stat().st_flags
            self.assertFalse(
                flags & stat.UF_HIDDEN,
                f"{pth_file} is marked hidden (UF_HIDDEN) - Python's site.py will "
                "silently skip it and automouse will fail to import. Run "
                "scripts/fix_hidden_venv.sh (with zsh, not bash) to repair it.",
            )


if __name__ == "__main__":
    unittest.main()
